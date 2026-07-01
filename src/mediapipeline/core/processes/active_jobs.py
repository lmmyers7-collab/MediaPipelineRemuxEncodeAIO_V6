from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from mediapipeline.core.kernel.contracts import ActiveJobRecord, ContractError
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.constants import ACTIVE_JOB_SCHEMA_VERSION, ACTIVE_JOB_STALE_VALIDATE_HEARTBEAT_SECONDS
from mediapipeline.core.processes.file_io import atomic_write_text, read_json_file
from mediapipeline.core.processes.kill import kill_psutil_process_tree


class InfoWarningLogger(Protocol):
    def info(self, message: object, *args: object, **kwargs: object) -> None: ...

    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


ACTIVE_JOB_BLOCKING_STATUSES = frozenset({"launching", "active"})
VALIDATE_ONLY_ARG = "-validateonly"


def active_jobs_dir_for_resolved(resolved: ResolvedPaths | None) -> Path | None:
    if resolved is None:
        return None
    if resolved.active_jobs_path:
        return resolved.active_jobs_path
    if resolved.state_root:
        return resolved.state_root / "ActiveJobs"
    return None


def active_job_record_path_for_proc(proc: Any | None) -> Path | None:
    if proc is None:
        return None
    raw = getattr(proc, "_mediapipeline_active_job_record", None)
    return Path(raw) if raw else None


def write_active_job_payload(record_path: Path, payload: dict[str, Any]) -> None:
    record_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        normalized = ActiveJobRecord.from_mapping(payload).to_mapping()
    except ContractError as exc:
        raise RuntimeError(f"ActiveJobs record contract invalid for {record_path}: {exc}") from exc
    atomic_write_text(record_path, json.dumps(normalized, indent=2, sort_keys=True) + "\n")


def write_active_job_launch_record(
    proc: Any,
    *,
    resolved: ResolvedPaths | None,
    job_kind: str,
    mode: str,
    command_line: str,
    args: list[str],
    launch_cwd: Path,
    show_console: bool,
    metadata: dict[str, Any],
    stdout_log: Path | None,
    stderr_log: Path | None,
    app_pid: int | None = None,
    logger: InfoWarningLogger | None = None,
) -> Path | None:
    active_jobs_dir = active_jobs_dir_for_resolved(resolved)
    if active_jobs_dir is None:
        return None
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    safe_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    launch_id = f"{safe_stamp}_{job_kind}_{proc.pid}_{uuid.uuid4().hex[:8]}"
    record_path = active_jobs_dir / f"{launch_id}.json"
    payload = {
        "schema_version": ACTIVE_JOB_SCHEMA_VERSION,
        "launch_id": launch_id,
        "job_kind": job_kind,
        "mode": mode,
        "status": "launching",
        "pid": proc.pid,
        "app_pid": os.getpid() if app_pid is None else app_pid,
        "command_line": command_line,
        "args": [str(arg) for arg in args],
        "cwd": str(launch_cwd),
        "stdout_log": str(stdout_log) if stdout_log else "",
        "stderr_log": str(stderr_log) if stderr_log else "",
        "show_console": bool(show_console),
        "metadata": metadata,
        "launched_at": stamp,
        "last_update": stamp,
        "return_code": None,
    }
    write_active_job_payload(record_path, payload)
    setattr(proc, "_mediapipeline_active_job_record", str(record_path))
    if logger is not None:
        logger.info("Wrote active job launch record: %s", record_path)
    return record_path


def _parse_record_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed


def _record_update_age_seconds(record: ActiveJobRecord, record_path: Path, now: datetime) -> float | None:
    updated_at = _parse_record_datetime(record.last_update) or _parse_record_datetime(record.launched_at)
    if updated_at is None:
        try:
            updated_at = datetime.fromtimestamp(record_path.stat().st_mtime, timezone.utc)
        except OSError:
            return None
    return max(0.0, (now - updated_at.astimezone(now.tzinfo)).total_seconds())


def _record_has_validate_only_arg(record: ActiveJobRecord) -> bool:
    pieces = list(record.args)
    pieces.append(record.command_line)
    return VALIDATE_ONLY_ARG in " ".join(str(piece) for piece in pieces).replace("/", "\\").casefold()


def _stale_validate_only_reason(
    record: ActiveJobRecord,
    record_path: Path,
    *,
    now: datetime,
    stale_after_seconds: float,
) -> str:
    if record.status not in ACTIVE_JOB_BLOCKING_STATUSES:
        return ""
    if str(record.job_kind or "").casefold() != "pipeline":
        return ""
    if str(record.mode or "").casefold() != "validate":
        return ""
    if not _record_has_validate_only_arg(record):
        return ""
    age_seconds = _record_update_age_seconds(record, record_path, now)
    if age_seconds is None or age_seconds < stale_after_seconds:
        return ""
    return f"validate-only heartbeat stale for {int(age_seconds)}s (limit {int(stale_after_seconds)}s)"


def _write_reconciled_active_job_record(
    record_path: Path,
    record: ActiveJobRecord,
    *,
    status: str,
    reason: str,
    now_text: str,
    return_code: int | None = None,
) -> None:
    updated = record.to_mapping()
    updated["status"] = status
    updated["return_code"] = return_code
    updated["last_update"] = now_text
    updated["completed_at"] = now_text
    updated["reconciled_at"] = now_text
    updated["reconcile_reason"] = reason
    write_active_job_payload(record_path, updated)


def active_job_pid_is_alive(pid: int, psutil_module: Any) -> bool | None:
    if psutil_module is None:
        return None
    try:
        process = psutil_module.Process(pid)
        return bool(process.is_running()) and process.status() != psutil_module.STATUS_ZOMBIE
    except psutil_module.NoSuchProcess:
        return False
    except Exception:
        return None


def _normalize_process_text(value: object) -> str:
    return str(value or "").strip().replace("/", "\\").casefold()


def _normalize_process_path(value: object) -> str:
    return os.path.normcase(os.path.normpath(str(value or "").strip()))


def _process_cmdline_matches_record(process: Any, record: ActiveJobRecord) -> bool | None:
    expected_args = [_normalize_process_text(arg) for arg in record.args if str(arg).strip()]
    if not expected_args:
        return None
    try:
        actual_args = [_normalize_process_text(arg) for arg in (process.cmdline() or []) if str(arg).strip()]
    except Exception:
        return None
    if actual_args == expected_args:
        return True
    actual_text = " ".join(actual_args)
    expected_needles = [
        arg
        for arg in expected_args
        if arg.endswith(".ps1") or "mediapipeline" in arg or arg.endswith("pwsh.exe") or arg.endswith("powershell.exe")
    ]
    if expected_needles and all(needle in actual_text for needle in expected_needles):
        return True
    return False


def _process_cwd_matches_record(process: Any, record: ActiveJobRecord) -> bool | None:
    if not record.cwd.strip():
        return None
    try:
        actual_cwd = process.cwd()
    except Exception:
        return None
    return _normalize_process_path(actual_cwd) == _normalize_process_path(record.cwd)


def active_job_pid_matches_record(record: ActiveJobRecord, psutil_module: Any) -> bool | None:
    """Return whether the recorded PID still appears to be this launch.

    ``False`` means the PID is dead or belongs to a clearly different
    process, so the stale ActiveJobs row can be ignored/reconciled. ``None``
    means the PID exists but identity could not be inspected; close-readiness
    must continue to fail closed in that case.
    """
    if record.pid is None or psutil_module is None:
        return None
    try:
        process = psutil_module.Process(record.pid)
        is_alive = bool(process.is_running()) and process.status() != psutil_module.STATUS_ZOMBIE
    except psutil_module.NoSuchProcess:
        return False
    except Exception:
        return None
    if not is_alive:
        return False

    identity_checks = [
        _process_cwd_matches_record(process, record),
        _process_cmdline_matches_record(process, record),
    ]
    if any(result is True for result in identity_checks):
        return True
    if any(result is None for result in identity_checks):
        return None
    if record.cwd.strip() or record.args:
        return False
    return True


def reconcile_active_job_records(
    resolved: ResolvedPaths,
    *,
    max_items: int | None = None,
    psutil_module: Any = None,
    logger: WarningLogger | None = None,
) -> list[str]:
    """Mark stale launch records whose tracked PID is definitely gone.

    This is diagnostics-only reconciliation. Ambiguous cases, such as
    access-denied process inspection, are left untouched.
    """
    folder = active_jobs_dir_for_resolved(resolved)
    if psutil_module is None or not folder or not folder.exists():
        return []
    try:
        records = sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        message = f"ActiveJobs folder could not be reconciled: {exc}"
        if logger is not None:
            logger.warning(message)
        return [message]

    messages: list[str] = []
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for record_path in (records if max_items is None else records[:max_items]):
        try:
            payload = read_json_file(record_path, retries=1)
            record = ActiveJobRecord.from_mapping(payload)
        except Exception as exc:
            message = f"ActiveJobs record {record_path.name} could not be reconciled: {exc}"
            if logger is not None:
                logger.warning(message)
            messages.append(message)
            continue
        if record.status not in {"launching", "active"}:
            continue
        if record.pid is None:
            reason = "missing pid"
            matches_record = False
        else:
            alive = active_job_pid_is_alive(record.pid, psutil_module)
            if alive is False:
                matches_record = False
                reason = f"pid {record.pid} is no longer running"
            else:
                matches_record = active_job_pid_matches_record(record, psutil_module)
                reason = f"pid {record.pid} no longer matches the launch record"
        if matches_record is not False:
            continue
        updated = record.to_mapping()
        updated["status"] = "orphaned"
        updated["return_code"] = None
        updated["last_update"] = now
        updated["completed_at"] = now
        updated["reconciled_at"] = now
        updated["reconcile_reason"] = reason
        write_active_job_payload(record_path, updated)
        message = f"Marked ActiveJobs record {record_path.name} orphaned: {reason}."
        if logger is not None:
            logger.warning(message)
        messages.append(message)
    return messages


def cleanup_stale_validate_active_jobs(
    resolved: ResolvedPaths,
    *,
    max_items: int | None = None,
    stale_after_seconds: float = ACTIVE_JOB_STALE_VALIDATE_HEARTBEAT_SECONDS,
    psutil_module: Any = None,
    logger: WarningLogger | None = None,
) -> list[str]:
    """Stop stale validate-only launch guards after heartbeat timeout.

    This intentionally does not touch continuous/run-once/audit/rerun work.
    Validate-only launches do not process media; if the backend that launched
    them dies before updating the ActiveJobs record, they should not keep the
    operator from starting a real scan indefinitely.
    """
    folder = active_jobs_dir_for_resolved(resolved)
    if psutil_module is None or not folder or not folder.exists():
        return []
    try:
        records = sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        message = f"ActiveJobs folder could not be checked for stale validate-only launches: {exc}"
        if logger is not None:
            logger.warning(message)
        return [message]

    messages: list[str] = []
    now = datetime.now().astimezone()
    now_text = now.isoformat(timespec="seconds")
    for record_path in (records if max_items is None else records[:max_items]):
        try:
            payload = read_json_file(record_path, retries=1)
            record = ActiveJobRecord.from_mapping(payload)
        except Exception as exc:
            message = f"ActiveJobs record {record_path.name} could not be checked for stale validate-only cleanup: {exc}"
            if logger is not None:
                logger.warning(message)
            messages.append(message)
            continue

        stale_reason = _stale_validate_only_reason(
            record,
            record_path,
            now=now,
            stale_after_seconds=stale_after_seconds,
        )
        if not stale_reason:
            continue

        if record.pid is None:
            reason = f"{stale_reason}; missing pid"
            _write_reconciled_active_job_record(
                record_path,
                record,
                status="orphaned",
                reason=reason,
                now_text=now_text,
            )
            message = f"Marked stale validate-only ActiveJobs record {record_path.name} orphaned: {reason}."
            if logger is not None:
                logger.warning(message)
            messages.append(message)
            continue

        matches_record = active_job_pid_matches_record(record, psutil_module)
        if matches_record is False:
            reason = f"{stale_reason}; pid {record.pid} no longer matches the launch record"
            _write_reconciled_active_job_record(
                record_path,
                record,
                status="orphaned",
                reason=reason,
                now_text=now_text,
            )
            message = f"Marked stale validate-only ActiveJobs record {record_path.name} orphaned: {reason}."
            if logger is not None:
                logger.warning(message)
            messages.append(message)
            continue
        if matches_record is None:
            message = (
                f"Stale validate-only ActiveJobs record {record_path.name} was left blocking because "
                f"PID {record.pid} identity could not be verified."
            )
            if logger is not None:
                logger.warning(message)
            messages.append(message)
            continue

        try:
            process = psutil_module.Process(record.pid)
            kill_psutil_process_tree(
                process,
                "stale validate-only launch",
                psutil_module=psutil_module,
                logger=logger or _NullWarningLogger(),
            )
        except psutil_module.NoSuchProcess:
            reason = f"{stale_reason}; pid {record.pid} is no longer running"
            _write_reconciled_active_job_record(
                record_path,
                record,
                status="orphaned",
                reason=reason,
                now_text=now_text,
            )
            message = f"Marked stale validate-only ActiveJobs record {record_path.name} orphaned: {reason}."
            if logger is not None:
                logger.warning(message)
            messages.append(message)
            continue
        except Exception as exc:
            message = f"Stale validate-only cleanup could not stop PID {record.pid} for {record_path.name}: {exc}"
            if logger is not None:
                logger.warning(message)
            messages.append(message)
            continue

        alive = active_job_pid_is_alive(record.pid, psutil_module)
        if alive is not False:
            message = (
                f"Stale validate-only cleanup could not verify PID {record.pid} exited for {record_path.name}; "
                "leaving record active."
            )
            if logger is not None:
                logger.warning(message)
            messages.append(message)
            continue

        reason = f"{stale_reason}; killed stale validate-only PID {record.pid}"
        _write_reconciled_active_job_record(
            record_path,
            record,
            status="killed",
            reason=reason,
            now_text=now_text,
        )
        message = f"Cleaned stale validate-only ActiveJobs record {record_path.name}: {reason}."
        if logger is not None:
            logger.warning(message)
        messages.append(message)

    return messages


class _NullWarningLogger:
    def warning(self, _message: object, *args: object, **kwargs: object) -> None:
        _ = args, kwargs


def update_active_job_record(
    proc: Any | None,
    *,
    status: str | None = None,
    return_code: int | None = None,
    app_pid: int | None = None,
    logger: WarningLogger | None = None,
) -> None:
    record_path = active_job_record_path_for_proc(proc)
    if record_path is None or not record_path.exists():
        return
    try:
        payload = read_json_file(record_path, retries=1)
        if not isinstance(payload, dict):
            if logger is not None:
                logger.warning("ActiveJobs record %s had unexpected JSON shape; repairing with default fields.", record_path.name)
            payload = {}
    except Exception as exc:
        if logger is not None:
            logger.warning(
                "ActiveJobs record %s could not be read during update; repairing with default fields: %s",
                record_path.name,
                exc,
            )
        payload = {}
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    if proc is not None and return_code is None and proc.poll() is not None:
        return_code = proc.returncode
    payload.setdefault("schema_version", ACTIVE_JOB_SCHEMA_VERSION)
    payload.setdefault("launch_id", record_path.stem)
    payload.setdefault("job_kind", "process")
    payload.setdefault("mode", "")
    payload.setdefault("pid", getattr(proc, "pid", None) if proc is not None else None)
    payload.setdefault("app_pid", os.getpid() if app_pid is None else app_pid)
    payload.setdefault("command_line", "")
    payload.setdefault("args", [])
    payload.setdefault("cwd", "")
    payload.setdefault("stdout_log", "")
    payload.setdefault("stderr_log", "")
    payload.setdefault("show_console", False)
    payload.setdefault("metadata", {})
    payload.setdefault("launched_at", now)
    payload["status"] = status or ("completed" if return_code == 0 else "failed")
    payload["return_code"] = return_code
    payload["last_update"] = now
    if payload["status"] not in {"active", "launching"}:
        payload["completed_at"] = now
    write_active_job_payload(record_path, payload)
