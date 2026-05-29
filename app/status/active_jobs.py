from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from mediapipeline_desktop_app.contracts import ActiveJobRecord, ContractError
from app.shared.utils import _read_json_file
from app.status.progress import parse_progress_datetime

ReadJsonFileFunc = Callable[[Path], Any]

WORKER_PROGRESS_SCHEMA_VERSION = "desktop_worker_progress.v1"


def active_job_status_state(status: str = "", issue: str = "", source: str = "") -> str:
    combined = " ".join(str(value or "").strip().casefold() for value in (status, issue, source))
    normalized_status = str(status or "").strip().casefold()
    if any(term in combined for term in ("invalid", "unreadable", "failed", "failure", "killed", "orphan", "blocked", "malformed", "corrupt")):
        return "blocked"
    if any(term in normalized_status for term in ("launching", "active", "running", "processing")):
        return "running"
    if any(term in combined for term in ("stale", "unknown", "review")):
        return "warning"
    if "completed" in normalized_status:
        return "completed"
    return "unknown"


def format_active_job_summary(
    folder: Path | None,
    *,
    max_items: int = 6,
    read_json_file: ReadJsonFileFunc = _read_json_file,
) -> list[str]:
    if not folder or not folder.exists():
        return ["No ActiveJobs records found."]
    try:
        records = sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        return [f"ActiveJobs unreadable: {exc}"]

    rows: list[str] = []
    for record_path in records[:max_items]:
        try:
            payload = read_json_file(record_path)
        except Exception as exc:
            rows.append(f"{record_path.name}: unreadable ({exc})")
            continue
        if not isinstance(payload, dict):
            rows.append(f"{record_path.name}: unexpected JSON shape")
            continue
        try:
            record = ActiveJobRecord.from_mapping(payload)
        except ContractError as exc:
            if str(payload.get("schema_version") or "").strip():
                rows.append(f"{record_path.name}: invalid active job contract ({exc})")
                continue
            kind = str(payload.get("job_kind") or "job")
            mode = str(payload.get("mode") or "").strip()
            status = str(payload.get("status") or "unknown")
            pid = str(payload.get("pid") or "")
            launched = str(payload.get("launched_at") or "")
            return_code = payload.get("return_code")
        else:
            kind = record.job_kind
            mode = record.mode
            status = record.status
            pid = "" if record.pid is None else str(record.pid)
            launched = record.launched_at
            return_code = record.return_code
        pid_text = f"pid {pid}" if pid else "pid unknown"
        mode_text = f" {mode}" if mode else ""
        rc_text = "" if return_code is None else f" rc={return_code}"
        rows.append(f"{kind}{mode_text}: {status} ({pid_text}){rc_text} launched {launched}")
    return rows or ["ActiveJobs folder is empty."]


def active_job_detail_rows(
    folder: Path | None,
    *,
    max_items: int = 20,
    read_json_file: ReadJsonFileFunc = _read_json_file,
) -> list[dict[str, Any]]:
    if not folder or not folder.exists():
        return []
    try:
        records = sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        return [
            {
                "record_file": "",
                "record_path": str(folder),
                "source": "unreadable",
                "status": "unreadable",
                "issue": f"ActiveJobs unreadable: {exc}",
            }
        ]

    rows: list[dict[str, Any]] = []
    for record_path in records[:max_items]:
        base = {
            "record_file": record_path.name,
            "record_path": str(record_path),
        }
        try:
            payload = read_json_file(record_path)
        except Exception as exc:
            status = "unreadable"
            issue = f"unreadable: {exc}"
            rows.append({**base, "source": "unreadable", "status": status, "status_state": active_job_status_state(status, issue, "unreadable"), "issue": issue})
            continue
        if not isinstance(payload, dict):
            status = "invalid"
            issue = "unexpected JSON shape"
            rows.append({**base, "source": "invalid", "status": status, "status_state": active_job_status_state(status, issue, "invalid"), "issue": issue})
            continue
        try:
            record = ActiveJobRecord.from_mapping(payload)
        except ContractError as exc:
            if str(payload.get("schema_version") or "").strip():
                status = str(payload.get("status") or "invalid")
                issue = f"invalid active job contract: {exc}"
                rows.append(
                    {
                        **base,
                        "source": "invalid",
                        "schema_version": str(payload.get("schema_version") or ""),
                        "launch_id": str(payload.get("launch_id") or ""),
                        "job_kind": str(payload.get("job_kind") or "job"),
                        "mode": str(payload.get("mode") or ""),
                        "status": status,
                        "status_state": active_job_status_state(status, issue, "invalid"),
                        "pid": payload.get("pid"),
                        "app_pid": payload.get("app_pid"),
                        "launched_at": str(payload.get("launched_at") or ""),
                        "last_update": str(payload.get("last_update") or ""),
                        "completed_at": str(payload.get("completed_at") or ""),
                        "return_code": payload.get("return_code"),
                        "stdout_log": str(payload.get("stdout_log") or ""),
                        "stderr_log": str(payload.get("stderr_log") or ""),
                        "cwd": str(payload.get("cwd") or ""),
                        "show_console": bool(payload.get("show_console")),
                        "command_line": str(payload.get("command_line") or ""),
                        "issue": issue,
                    }
                )
                continue
            status = str(payload.get("status") or "unknown")
            issue = "legacy active job record; contract validation was not applied"
            rows.append(
                {
                    **base,
                    "source": "legacy",
                    "schema_version": "",
                    "launch_id": str(payload.get("launch_id") or ""),
                    "job_kind": str(payload.get("job_kind") or "job"),
                    "mode": str(payload.get("mode") or ""),
                    "status": status,
                    "status_state": active_job_status_state(status, issue, "legacy"),
                    "pid": payload.get("pid"),
                    "app_pid": payload.get("app_pid"),
                    "launched_at": str(payload.get("launched_at") or ""),
                    "last_update": str(payload.get("last_update") or ""),
                    "completed_at": str(payload.get("completed_at") or ""),
                    "return_code": payload.get("return_code"),
                    "stdout_log": str(payload.get("stdout_log") or ""),
                    "stderr_log": str(payload.get("stderr_log") or ""),
                    "cwd": str(payload.get("cwd") or ""),
                    "show_console": bool(payload.get("show_console")),
                    "command_line": str(payload.get("command_line") or ""),
                    "issue": issue,
                }
            )
            continue
        issue = ""
        rows.append(
            {
                **base,
                "source": "contract",
                "schema_version": record.schema_version,
                "launch_id": record.launch_id,
                "job_kind": record.job_kind,
                "mode": record.mode,
                "status": record.status,
                "status_state": active_job_status_state(record.status, issue, "contract"),
                "pid": record.pid,
                "app_pid": record.app_pid,
                "launched_at": record.launched_at,
                "last_update": record.last_update,
                "completed_at": record.completed_at,
                "return_code": record.return_code,
                "stdout_log": record.stdout_log,
                "stderr_log": record.stderr_log,
                "cwd": record.cwd,
                "show_console": record.show_console,
                "command_line": record.command_line,
                "args_count": len(record.args),
                "metadata": dict(record.metadata),
                "issue": issue,
            }
        )
    return rows


def _text_from_mapping(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _float_percent_from_mapping(mapping: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = mapping.get(key)
        if value in (None, ""):
            continue
        try:
            result = float(value)
        except (TypeError, ValueError):
            continue
        return max(0.0, min(100.0, result))
    return None


def _last_nonempty_log_line(log_tail: str, *, max_chars: int = 240) -> str:
    for raw_line in reversed(str(log_tail or "").splitlines()):
        line = raw_line.strip()
        if line:
            return line if len(line) <= max_chars else f"{line[: max_chars - 3]}..."
    return ""


def _progress_id(*values: object) -> str:
    text = "_".join(str(value or "").strip().casefold() for value in values if str(value or "").strip())
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "local"


def _elapsed_seconds(started_at: str, updated_at: str, now: datetime | None = None) -> int | None:
    start = parse_progress_datetime(started_at)
    if start is None:
        return None
    end = parse_progress_datetime(updated_at)
    if end is None:
        end = now or datetime.now(start.tzinfo or timezone.utc)
    if start.tzinfo is None and end.tzinfo is not None:
        end = end.replace(tzinfo=None)
    elif start.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=start.tzinfo)
    elapsed = (end - start).total_seconds()
    if elapsed < 0:
        return 0
    return int(elapsed)


def _progress_active(progress: Mapping[str, Any]) -> bool:
    status = _text_from_mapping(progress, "Status", "status").casefold()
    stage = _text_from_mapping(progress, "CurrentStage", "current_stage").casefold()
    text = f"{status} {stage}".strip()
    if not text:
        return False
    if any(token in text for token in ("idle", "sleeping", "stopped")):
        return False
    return True


def _progress_status_state(progress: Mapping[str, Any], *, stale: bool) -> str:
    if stale:
        return "warning"
    status = _text_from_mapping(progress, "Status", "status")
    stage = _text_from_mapping(progress, "CurrentStage", "current_stage")
    text = f"{status} {stage}".casefold()
    if any(token in text for token in ("failed", "error", "blocked", "killed", "stopped")):
        return "blocked"
    if any(token in text for token in ("processing", "running", "active", "publishing", "copying", "encoding", "remuxing", "scanning", "retry")):
        return "running"
    if any(token in text for token in ("complete", "completed", "published", "deferred")):
        return "completed"
    if text.strip():
        return "unknown"
    return "empty"


def _progress_is_stale(progress: Mapping[str, Any], *, stale_after_seconds: float, now: datetime | None = None) -> bool:
    if not progress or not _progress_active(progress):
        return False
    updated_at = _text_from_mapping(progress, "LastUpdate", "UpdatedAt", "updated_at")
    parsed = parse_progress_datetime(updated_at)
    if parsed is None:
        return False
    reference = now or (datetime.now(parsed.tzinfo) if parsed.tzinfo is not None else datetime.now())
    if parsed.tzinfo is None and reference.tzinfo is not None:
        reference = reference.replace(tzinfo=None)
    elif parsed.tzinfo is not None and reference.tzinfo is None:
        reference = reference.replace(tzinfo=parsed.tzinfo)
    return (reference - parsed).total_seconds() > stale_after_seconds


def _worker_progress_bar(row: Mapping[str, Any]) -> dict[str, Any]:
    status = str(row.get("status_state") or "unknown")
    percent = row.get("percent")
    mode = "determinate" if isinstance(percent, (int, float)) else "indeterminate" if status == "running" else "determinate"
    if mode == "determinate" and percent is None:
        percent = 100.0 if status == "completed" else 0.0
    detail = "; ".join(
        part
        for part in (
            f"stage={row.get('stage')}" if row.get("stage") else "",
            f"file={row.get('source')}" if row.get("source") else "",
            f"job={row.get('job_id')}" if row.get("job_id") else "",
            f"last={row.get('last_log_line')}" if row.get("last_log_line") else "",
        )
        if part
    )
    return {
        "id": f"worker_{_progress_id(row.get('worker_id'), row.get('job_id'))}",
        "label": str(row.get("worker_label") or row.get("worker_id") or "Local worker"),
        "mode": mode,
        "percent": percent if mode != "indeterminate" else None,
        "status": status,
        "detail": detail or "No worker progress detail reported.",
        "source": str(row.get("progress_source") or "desktop_worker_progress.v1"),
        "updated_at": str(row.get("updated_at") or ""),
        "stale": bool(row.get("stale")),
    }


def _worker_progress_candidate(row: Mapping[str, Any]) -> bool:
    status_state = str(row.get("status_state") or "").casefold()
    if status_state == "running":
        return True
    if status_state not in {"warning", "blocked"}:
        return False
    source = str(row.get("source") or "").casefold()
    if source in {"invalid", "unreadable"}:
        return True
    if _text_from_mapping(row, "completed_at"):
        return False
    if row.get("return_code") is not None:
        return False
    return True


def _active_job_worker_row(
    row: Mapping[str, Any],
    *,
    progress: Mapping[str, Any] | None,
    log_tail: str,
    stale_after_seconds: float,
    now: datetime | None,
) -> dict[str, Any]:
    row_status_state = str(
        row.get("status_state")
        or active_job_status_state(
            str(row.get("status") or ""),
            str(row.get("issue") or ""),
            str(row.get("source") or ""),
        )
    )
    merged_progress = (
        progress
        if progress and row_status_state == "running" and _text_from_mapping(row, "job_kind").casefold() == "pipeline"
        else None
    )
    progress_stale = _progress_is_stale(merged_progress or {}, stale_after_seconds=stale_after_seconds, now=now) if merged_progress else False
    updated_at = (
        _text_from_mapping(merged_progress or {}, "LastUpdate", "UpdatedAt", "updated_at")
        or _text_from_mapping(row, "last_update", "launched_at")
    )
    started_at = (
        _text_from_mapping(merged_progress or {}, "CurrentItemStartedAt", "CurrentStageStartedAt", "SessionStartedAt")
        or _text_from_mapping(row, "launched_at")
    )
    status_state = _progress_status_state(merged_progress or {}, stale=progress_stale) if merged_progress else row_status_state
    return {
        "worker_id": "local" if _text_from_mapping(row, "job_kind").casefold() == "pipeline" else f"local-{_progress_id(row.get('job_kind'), row.get('launch_id'), row.get('record_file'))}",
        "worker_label": "Local pipeline" if _text_from_mapping(row, "job_kind").casefold() == "pipeline" else f"Local {row.get('job_kind') or 'job'}",
        "job_id": _text_from_mapping(row, "launch_id", "record_file"),
        "job_kind": _text_from_mapping(row, "job_kind"),
        "mode": _text_from_mapping(row, "mode"),
        "pid": row.get("pid"),
        "source": _text_from_mapping(merged_progress or {}, "CurrentFilePath", "CurrentFileDisplay", "CurrentFile"),
        "stage": _text_from_mapping(merged_progress or {}, "CurrentStage", "Status") or _text_from_mapping(row, "status"),
        "status": _text_from_mapping(row, "status"),
        "status_state": status_state,
        "percent": _float_percent_from_mapping(merged_progress or {}, "CurrentStagePercent"),
        "elapsed_seconds": _elapsed_seconds(started_at, updated_at, now=now),
        "last_log_line": _last_nonempty_log_line(log_tail),
        "updated_at": updated_at,
        "stale_after_seconds": int(stale_after_seconds),
        "stale": bool(progress_stale),
        "progress_source": "pipeline_progress.json + ActiveJobs" if merged_progress else "ActiveJobs",
        "record_file": _text_from_mapping(row, "record_file"),
        "record_path": _text_from_mapping(row, "record_path"),
        "issue": _text_from_mapping(row, "issue"),
    }


def _progress_only_worker_row(
    progress: Mapping[str, Any],
    *,
    log_tail: str,
    stale_after_seconds: float,
    now: datetime | None,
) -> dict[str, Any]:
    updated_at = _text_from_mapping(progress, "LastUpdate", "UpdatedAt", "updated_at")
    started_at = _text_from_mapping(progress, "CurrentItemStartedAt", "CurrentStageStartedAt", "SessionStartedAt")
    stale = _progress_is_stale(progress, stale_after_seconds=stale_after_seconds, now=now)
    return {
        "worker_id": "local",
        "worker_label": "Local pipeline",
        "job_id": _text_from_mapping(progress, "RunId", "SessionId", "SessionStartedAt") or "pipeline_progress",
        "job_kind": "pipeline",
        "mode": "",
        "pid": None,
        "source": _text_from_mapping(progress, "CurrentFilePath", "CurrentFileDisplay", "CurrentFile"),
        "stage": _text_from_mapping(progress, "CurrentStage", "Status"),
        "status": _text_from_mapping(progress, "Status"),
        "status_state": _progress_status_state(progress, stale=stale),
        "percent": _float_percent_from_mapping(progress, "CurrentStagePercent"),
        "elapsed_seconds": _elapsed_seconds(started_at, updated_at, now=now),
        "last_log_line": _last_nonempty_log_line(log_tail),
        "updated_at": updated_at,
        "stale_after_seconds": int(stale_after_seconds),
        "stale": bool(stale),
        "progress_source": "pipeline_progress.json",
        "record_file": "",
        "record_path": "",
        "issue": "",
    }


def worker_progress_payload(
    folder: Path | None,
    progress: Mapping[str, Any] | None,
    log_tail: str,
    *,
    stale_after_seconds: float = 5.0,
    max_items: int = 8,
    read_json_file: ReadJsonFileFunc = _read_json_file,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a read-only operator telemetry payload from existing runtime evidence."""
    progress_mapping = progress if isinstance(progress, Mapping) else {}
    raw_active_rows = active_job_detail_rows(folder, max_items=20, read_json_file=read_json_file)
    active_rows = [
        row
        for row in raw_active_rows
        if _worker_progress_candidate(row)
    ]
    rows: list[dict[str, Any]] = [
        _active_job_worker_row(
            row,
            progress=progress_mapping,
            log_tail=log_tail,
            stale_after_seconds=stale_after_seconds,
            now=now,
        )
        for row in active_rows[:max_items]
    ]
    if not rows and progress_mapping and _progress_active(progress_mapping):
        rows.append(
            _progress_only_worker_row(
                progress_mapping,
                log_tail=log_tail,
                stale_after_seconds=stale_after_seconds,
                now=now,
            )
        )

    bars = [_worker_progress_bar(row) for row in rows]
    active_count = sum(1 for row in rows if row.get("status_state") == "running")
    blocked_count = sum(1 for row in rows if row.get("status_state") == "blocked")
    warning_count = sum(1 for row in rows if row.get("status_state") == "warning")
    completed_count = sum(1 for row in rows if row.get("status_state") == "completed")
    status = "blocked" if blocked_count else "warning" if warning_count else "running" if active_count else "completed" if completed_count else "idle"
    return {
        "schema_version": WORKER_PROGRESS_SCHEMA_VERSION,
        "mode": "local_worker_progress",
        "status": status,
        "row_count": len(rows),
        "active_count": active_count,
        "blocked_count": blocked_count,
        "warning_count": warning_count,
        "completed_count": completed_count,
        "stale_after_seconds": int(stale_after_seconds),
        "rows": rows,
        "progress_bars": bars,
        "summary_lines": [
            f"Worker progress: {status}",
            f"Rows: {len(rows)}; running={active_count}; blocked={blocked_count}; warning={warning_count}; completed={completed_count}.",
            "Data sources: pipeline_progress.json, ActiveJobs records, and bounded pipeline log tail.",
            "Mutation guardrail: worker progress is read-only telemetry; WebView does not launch, stop, retry, clear state, mutate queue state, or touch media files.",
        ],
        "read_only": True,
    }


__all__ = [
    "WORKER_PROGRESS_SCHEMA_VERSION",
    "active_job_detail_rows",
    "active_job_status_state",
    "format_active_job_summary",
    "worker_progress_payload",
]
