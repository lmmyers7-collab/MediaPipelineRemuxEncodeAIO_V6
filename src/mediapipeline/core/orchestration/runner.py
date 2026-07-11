"""Single Python subprocess boundary for PowerShell stage execution."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.contracts.stages import (
    DecidePayload,
    IngestPayload,
    ProbePayload,
    StageName,
    StagePayload,
    StageRequest,
    StageResult,
    build_stage_request,
    make_stage_result,
    stage_contract,
    validate_stage_data,
)
from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_ENTRYPOINT = REPO_ROOT / "ops" / "pipeline" / "engine" / "entrypoint.ps1"
BUNDLED_PWSH = REPO_ROOT / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
COMMAND_RESULT_SCHEMA_VERSION = "desktop_command_result.v1"


@dataclass(frozen=True)
class StageProcessResult:
    args: Sequence[str]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    kill_message: str = ""


RunCapture = Callable[..., StageProcessResult]
JournalRecord = Callable[[Mapping[str, Any]], None]
OperationJournalRecord = Callable[[Mapping[str, Any]], Mapping[str, Any] | None]


@dataclass(frozen=True)
class RunnerOptions:
    timeout_seconds: float = 60.0
    cwd: Path | str | None = None
    env: Mapping[str, str] | None = None
    powershell_path: Path | str | None = None
    entrypoint_path: Path | str = DEFAULT_ENTRYPOINT
    run_capture_func: RunCapture | None = None
    journal_record: JournalRecord | None = None
    operation_journal_record: OperationJournalRecord | None = None
    state_db_root: Path | str | None = None
    force_payload_file: bool = False
    payload_file_threshold: int = 7000
    extra_environment: Mapping[str, str] = field(default_factory=dict)


def resolve_powershell_path(explicit: Path | str | None = None) -> str | None:
    if explicit is not None:
        path = Path(explicit)
        return str(path) if path.exists() else str(explicit)
    if BUNDLED_PWSH.exists():
        return str(BUNDLED_PWSH)
    found = shutil.which("pwsh")
    return found


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _error_result(
    *,
    stage: StageName | str,
    started_at: datetime,
    code: str,
    message: str,
    details: Mapping[str, Any] | None = None,
) -> StageResult:
    return make_stage_result(
        stage=stage,
        ok=False,
        started_at=started_at,
        error={
            "code": code,
            "message": message,
            "details": dict(details or {}),
        },
    )


def _run_capture(
    args: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: Path | str | None,
    env: Mapping[str, str] | None,
) -> StageProcessResult:
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    if env is not None:
        kwargs["env"] = dict(env)
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True

    proc: subprocess.Popen[Any] | None = None
    try:
        proc = subprocess.Popen(list(args), **kwargs)
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        return StageProcessResult(
            args=list(args),
            returncode=proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
        )
    except subprocess.TimeoutExpired:
        kill_message = "process kill status unknown"
        if proc is not None:
            try:
                proc.kill()
                kill_message = "process killed"
            except Exception as exc:  # pragma: no cover - platform cleanup edge
                kill_message = f"process kill failed: {exc}"
            try:
                stdout, stderr = proc.communicate(timeout=2)
            except Exception:
                stdout, stderr = "", ""
            return StageProcessResult(
                args=list(args),
                returncode=proc.returncode,
                stdout=stdout or "",
                stderr=stderr or "",
                timed_out=True,
                kill_message=kill_message,
            )
        return StageProcessResult(
            args=list(args),
            returncode=None,
            stdout="",
            stderr="",
            timed_out=True,
            kill_message=kill_message,
        )


def _tail(text: str, *, limit: int = 2000) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[-limit:]


def _result_message(result: StageResult) -> str:
    if result.ok:
        return f"Stage {result.stage} completed."
    return result.error.message if result.error is not None else f"Stage {result.stage} failed."


def _record_journal(options: RunnerOptions, request: StageRequest, result: StageResult) -> None:
    if options.journal_record is None:
        return
    job_id = getattr(request.payload, "job_id", "") or getattr(request.payload, "run_id", "")
    result_data = result.data if isinstance(result.data, dict) else {}
    evidence_path = str(result_data.get("evidence_path") or result_data.get("manifest_path") or result_data.get("undo_record_path") or "")
    journal_data: dict[str, Any] = {
        "stage": result.stage,
        "journal_event_type": result.journal_event_type,
    }
    for key in (
        "scratch_path",
        "evidence_path",
        "manifest_path",
        "undo_record_path",
        "source_unchanged",
        "rollback_actions",
        "recovery_actions",
        "boundary_checks",
    ):
        if key in result_data:
            journal_data[key] = result_data[key]
    payload: dict[str, Any] = {
        "schema_version": COMMAND_RESULT_SCHEMA_VERSION,
        "command": f"stage.{request.stage.value}",
        "ok": result.ok,
        "severity": "info" if result.ok else "error",
        "message": _result_message(result),
        "job_id": job_id,
        "refresh_hint": "pipeline-stage",
        "warnings": [],
        "errors": [] if result.ok else [result.error.code if result.error else "stage_failed"],
        "log_paths": {"stage_evidence": evidence_path} if evidence_path else {},
        "data": journal_data,
    }
    try:
        options.journal_record(payload)
    except Exception:
        # Journal persistence must not mask the stage result.
        return


def _record_stage_event(options: RunnerOptions, request: StageRequest, result: StageResult) -> None:
    if options.state_db_root is None:
        return


def _operation_journal_event(
    options: RunnerOptions,
    *,
    event: str,
    request: StageRequest,
    result: StageResult | None = None,
) -> Mapping[str, Any] | None:
    recorder = options.operation_journal_record
    if recorder is None:
        raise RuntimeError("Guarded ingest execute requires a strict operation journal adapter.")
    payload: dict[str, Any] = {
        "schema_version": "pipeline_stage_operation.v1",
        "event": event,
        "stage": request.stage.value,
        "operation_id": getattr(request.payload, "operation_id", ""),
        "scratch_reservation_id": getattr(request.payload, "scratch_reservation_id", ""),
        "dry_run_fingerprint": getattr(request.payload, "dry_run_fingerprint", ""),
    }
    if result is not None:
        payload["result"] = result.model_dump(mode="json")
    return recorder(payload)
    try:
        from mediapipeline.core.storage.db import maybe_maintain_state_db, open_state_db

        open_state_db(options.state_db_root).record_stage_event(
            {
                "event_type": result.journal_event_type,
                "run_id": getattr(request.payload, "run_id", ""),
                "command_id": getattr(request.payload, "job_id", ""),
                "stage": result.stage,
                "ok": result.ok,
                "request": request.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
            }
        )
        maybe_maintain_state_db(options.state_db_root)
    except Exception:
        return


def _parse_result(stage: StageName, started_at: datetime, captured: StageProcessResult) -> StageResult:
    stdout = captured.stdout.strip()
    if not stdout:
        return _error_result(
            stage=stage,
            started_at=started_at,
            code="stage.process_nonzero" if captured.returncode else "stage.result_missing",
            message="Stage process did not write a JSON result to stdout.",
            details={
                "returncode": captured.returncode,
                "stderr_tail": _tail(captured.stderr),
            },
        )
    try:
        raw = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return _error_result(
            stage=stage,
            started_at=started_at,
            code="stage.result_json_invalid",
            message=f"Stage process wrote malformed JSON: {exc.msg}.",
            details={
                "returncode": captured.returncode,
                "stdout_tail": _tail(captured.stdout),
                "stderr_tail": _tail(captured.stderr),
            },
        )
    try:
        parsed = StageResult.model_validate(raw)
    except Exception as exc:
        return _error_result(
            stage=stage,
            started_at=started_at,
            code="stage.result_contract_invalid",
            message=f"Stage JSON result failed contract validation: {exc}",
            details={
                "returncode": captured.returncode,
                "stdout_tail": _tail(captured.stdout),
                "stderr_tail": _tail(captured.stderr),
            },
        )
    if parsed.stage != stage.value:
        return _error_result(
            stage=stage,
            started_at=started_at,
            code="stage.result_stage_mismatch",
            message=f"Stage JSON result reported stage {parsed.stage!r} for requested stage {stage.value!r}.",
            details={
                "returncode": captured.returncode,
                "stdout_tail": _tail(captured.stdout),
                "stderr_tail": _tail(captured.stderr),
            },
        )
    if captured.returncode not in (0, None) and parsed.ok:
        return _error_result(
            stage=stage,
            started_at=started_at,
            code="stage.process_nonzero",
            message=f"Stage process exited with code {captured.returncode} after reporting success.",
            details={
                "returncode": captured.returncode,
                "stderr_tail": _tail(captured.stderr),
            },
        )
    if parsed.ok:
        try:
            data = validate_stage_data(stage, parsed.data or {})
        except Exception as exc:
            return _error_result(
                stage=stage,
                started_at=started_at,
                code="stage.result_contract_invalid",
                message=f"Stage JSON result data failed {stage.value!r} contract validation: {exc}",
                details={
                    "returncode": captured.returncode,
                    "stdout_tail": _tail(captured.stdout),
                    "stderr_tail": _tail(captured.stderr),
                },
            )
        parsed.data = data.model_dump(mode="json")
    return parsed


def _write_payload_arg(request: StageRequest, options: RunnerOptions) -> tuple[str, Path | None]:
    payload_json = request.model_dump_json()
    if not options.force_payload_file and len(payload_json) <= options.payload_file_threshold:
        return payload_json, None
    fd, name = tempfile.mkstemp(prefix="mediapipeline-stage-", suffix=".json")
    tmp_path = Path(name)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload_json)
        handle.write("\n")
    return str(tmp_path), tmp_path


def run_stage(
    stage: StageName | str,
    payload: StagePayload | Mapping[str, Any] | StageRequest,
    options: RunnerOptions | None = None,
) -> StageResult:
    """Run one pipeline stage through ops/pipeline/engine/entrypoint.ps1."""

    opts = options or RunnerOptions()
    started_at = _utc_now()
    try:
        stage_name = StageName(stage)
    except ValueError:
        return _error_result(
            stage=str(stage),
            started_at=started_at,
            code="stage.unknown",
            message=f"Unknown stage {str(stage)!r}.",
        )
    try:
        request = payload if isinstance(payload, StageRequest) else build_stage_request(stage_name, payload)
    except Exception as exc:
        return _error_result(
            stage=stage_name,
            started_at=started_at,
            code="stage.invalid_payload",
            message=f"Stage request failed {stage_name.value!r} payload validation: {exc}",
        )
    if request.stage != stage_name:
        result = _error_result(
            stage=stage_name,
            started_at=started_at,
            code="stage.request_stage_mismatch",
            message=f"Request stage {request.stage.value!r} does not match requested stage {stage_name.value!r}.",
        )
        _record_stage_event(opts, request, result)
        _record_journal(opts, request, result)
        return result

    if not stage_contract(stage_name).enabled_in_entrypoint:
        result = _error_result(
            stage=stage_name,
            started_at=started_at,
            code="stage.not_enabled",
            message=f"Stage {stage_name.value!r} is declared but disabled by the Python dispatcher.",
        )
        _record_stage_event(opts, request, result)
        _record_journal(opts, request, result)
        return result

    guarded_ingest_execute = stage_name is StageName.ingest and getattr(request.payload, "intent", "") == "execute"
    if guarded_ingest_execute:
        try:
            previous = _operation_journal_event(opts, event="accepted", request=request)
        except Exception as exc:
            return _error_result(
                stage=stage_name,
                started_at=started_at,
                code="stage.operation_journal_required",
                message=f"Guarded ingest execute blocked because strict operation journaling is unavailable: {exc}",
            )
        if previous:
            prior_result = previous.get("result") if isinstance(previous, Mapping) else None
            if isinstance(prior_result, Mapping):
                try:
                    return StageResult.model_validate(prior_result)
                except Exception:
                    pass
            return _error_result(
                stage=stage_name,
                started_at=started_at,
                code="stage.operation_in_progress",
                message="Guarded ingest operation is already accepted and has no terminal result yet.",
            )

    entrypoint = Path(opts.entrypoint_path)
    if not entrypoint.exists():
        result = _error_result(
            stage=stage_name,
            started_at=started_at,
            code="stage.entrypoint_missing",
            message=f"Stage entrypoint not found: {entrypoint}",
            details={"entrypoint_path": str(entrypoint)},
        )
        _record_stage_event(opts, request, result)
        _record_journal(opts, request, result)
        return result

    powershell = resolve_powershell_path(opts.powershell_path)
    if not powershell:
        result = _error_result(
            stage=stage_name,
            started_at=started_at,
            code="stage.powershell_missing",
            message="PowerShell executable was not found.",
        )
        _record_stage_event(opts, request, result)
        _record_journal(opts, request, result)
        return result

    payload_arg, tmp_path = _write_payload_arg(request, opts)
    try:
        env = dict(os.environ)
        if opts.env is not None:
            env.update(dict(opts.env))
        env.update(dict(opts.extra_environment))
        env["MEDIAPIPELINE_STAGE_RUNNER"] = "1"
        args = [
            str(powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(entrypoint),
            "-Stage",
            stage_name.value,
            "-PayloadJson",
            payload_arg,
        ]
        run_capture = opts.run_capture_func or _run_capture
        captured = run_capture(
            args,
            timeout_seconds=opts.timeout_seconds,
            cwd=opts.cwd or REPO_ROOT,
            env=env,
        )
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    if captured.timed_out:
        result = _error_result(
            stage=stage_name,
            started_at=started_at,
            code="stage.timeout",
            message=f"Stage process exceeded timeout of {opts.timeout_seconds:g} seconds.",
            details={
                "returncode": captured.returncode,
                "kill_message": captured.kill_message,
                "stderr_tail": _tail(captured.stderr),
            },
        )
    else:
        result = _parse_result(stage_name, started_at, captured)
    if guarded_ingest_execute:
        try:
            _operation_journal_event(opts, event="completed", request=request, result=result)
        except Exception as exc:
            result = _error_result(
                stage=stage_name,
                started_at=started_at,
                code="stage.operation_journal_failed",
                message=(
                    "Guarded ingest finished but its strict terminal journal record failed; "
                    f"the scratch reservation must remain unavailable pending recovery: {exc}"
                ),
            )
    _record_stage_event(opts, request, result)
    _record_journal(opts, request, result)
    return result


def run_decide_stage(
    payload: DecidePayload | Mapping[str, Any],
    options: RunnerOptions | None = None,
) -> StageResult:
    """Compatibility helper for low-risk route-decision callers."""

    return run_stage(StageName.decide, payload, options)


def run_probe_stage(
    payload: ProbePayload | Mapping[str, Any],
    options: RunnerOptions | None = None,
) -> StageResult:
    """Compatibility helper for low-risk media probe callers."""

    return run_stage(StageName.probe, payload, options)


def run_ingest_stage(
    payload: IngestPayload | Mapping[str, Any],
    options: RunnerOptions | None = None,
) -> StageResult:
    """Run the guarded source-to-scratch ingest stage.

    This is intentionally the only mutation-capable compatibility helper in
    this slice. The stage copies a source into a scratch-root child path and
    relies on the stage contract/entrypoint for execute confirmation.
    """

    return run_stage(StageName.ingest, payload, options)


__all__ = [
    "RunnerOptions",
    "StageProcessResult",
    "resolve_powershell_path",
    "run_stage",
    "run_decide_stage",
    "run_probe_stage",
    "run_ingest_stage",
]
