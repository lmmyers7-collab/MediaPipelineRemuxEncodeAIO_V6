"""Pipeline control command facade adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.paths.contracts import ResolvedPaths

from mediapipeline.core.processes.control_policy import (
    PIPELINE_CONTROL_ACTION_ERROR,
    is_supported_pipeline_control_action,
    normalize_pipeline_control_action,
    pipeline_control_command,
    pipeline_control_success_data,
)
from mediapipeline.core.processes.file_io import atomic_write_text
from mediapipeline.core.processes.kill import RelatedProcessKillEvidence, RelatedProcessKillReport
from mediapipeline.core.status.active_jobs import active_job_detail_rows
from mediapipeline.core.status.run_monitor import terminalize_force_stopped_run

_IDLE_STAGES = frozenset({"idle", "startup", ""})
_IDLE_STATUSES = frozenset({"", "idle", "none"})
_ACTIVE_PIPELINE_STATUSES = frozenset({"launching", "active"})


def _active_pipeline_stop_target(
    resolved: ResolvedPaths,
    *,
    expected_run_id: str = "",
) -> tuple[str, int, str]:
    rows = active_job_detail_rows(resolved.active_jobs_path, max_items=100000)
    uncertain = [row for row in rows if str(row.get("source") or "") != "contract"]
    if uncertain:
        raise RuntimeError(
            "Stop After Current could not verify ActiveJobs because one or more records are unreadable or invalid."
        )
    active = [
        row
        for row in rows
        if str(row.get("job_kind") or "").casefold() == "pipeline"
        and str(row.get("status") or "").casefold() in _ACTIVE_PIPELINE_STATUSES
    ]
    if len(active) != 1:
        raise RuntimeError(f"Stop After Current requires exactly one active pipeline; found {len(active)}.")
    target = active[0]
    try:
        target_pid = int(target.get("pid") or 0)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Stop After Current requires an exact active pipeline PID.") from exc
    target_launch_id = str(target.get("launch_id") or "").strip()
    if target_pid <= 0 or not target_launch_id:
        raise RuntimeError("Stop After Current requires an exact active pipeline PID and launch ID.")
    raw_metadata = target.get("metadata")
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    run_id = str(metadata.get("run_id") or "").strip()
    row_mode = str(target.get("mode") or "").strip().casefold()
    metadata_mode = str(metadata.get("mode") or "").strip().casefold()
    single_file = str(metadata.get("single_file") or "").strip()
    queue_fingerprint = str(metadata.get("expected_queue_plan_fingerprint") or "").strip()
    expected_raw = str(expected_run_id or "")
    expected = expected_raw.strip()
    if expected and (
        expected != expected_raw
        or len(expected) > 128
        or not expected[0].isalnum()
        or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in expected)
    ):
        raise RuntimeError("Stop After Current expected_run_id is invalid.")

    backend_queue_once_candidate = row_mode == "once" and not single_file
    if backend_queue_once_candidate:
        if metadata_mode != "once" or "single_file" not in metadata or not queue_fingerprint:
            raise RuntimeError(
                "Stop After Current could not verify exact Run Once · Backend Queue launch metadata."
            )
        if not expected:
            raise RuntimeError(
                "Stop After Current requires expected_run_id from the active Current Work monitor."
            )
        if not run_id:
            raise RuntimeError(
                "Stop After Current requires a nonblank run ID in the active Backend Queue launch record."
            )
        if run_id != expected:
            raise RuntimeError(
                "Stop After Current expected_run_id does not match the active Backend Queue run. Refresh Current Work before retrying."
            )
    elif expected:
        raise RuntimeError(
            "A run-correlated Stop After Current request may target only Run Once · Backend Queue work, not Continuous or Single File work."
        )
    return run_id, target_pid, target_launch_id


@dataclass(frozen=True)
class _ForceStopRunTarget:
    run_id: str
    pid: int
    command_id: str
    launch_id: str


def _active_pipeline_force_stop_targets(resolved: ResolvedPaths) -> list[_ForceStopRunTarget]:
    """Snapshot exact contract-backed targets; emergency kill is never blocked."""

    rows = active_job_detail_rows(resolved.active_jobs_path, max_items=100000)
    targets: list[_ForceStopRunTarget] = []
    for row in rows:
        if str(row.get("source") or "") != "contract":
            continue
        if str(row.get("job_kind") or "").casefold() != "pipeline":
            continue
        if str(row.get("status") or "").casefold() not in _ACTIVE_PIPELINE_STATUSES:
            continue
        raw_metadata = row.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        run_id = str(metadata.get("run_id") or "").strip()
        launch_id = str(row.get("launch_id") or "").strip()
        try:
            pid = int(row.get("pid") or 0)
        except (TypeError, ValueError):
            continue
        if not run_id or not launch_id or pid <= 0:
            continue
        target = _ForceStopRunTarget(
            run_id=run_id,
            pid=pid,
            command_id=str(metadata.get("command_id") or "").strip(),
            launch_id=launch_id,
        )
        if target not in targets:
            targets.append(target)
    return targets


def _correlated_force_stop_run_ids(
    targets: list[_ForceStopRunTarget],
    evidence_rows: tuple[RelatedProcessKillEvidence, ...],
) -> tuple[list[str], list[str]]:
    """Require exact killed PID + process RunId proof before monitor takeover."""

    proven_targets: set[_ForceStopRunTarget] = set()
    errors: list[str] = []
    for evidence in evidence_rows:
        if not evidence.exit_verified or "pipeline" not in evidence.matched_job_kinds or not evidence.run_id:
            continue
        matches = [
            target
            for target in targets
            if target.pid == evidence.pid
            and target.run_id == evidence.run_id
            and (not target.command_id or target.command_id == evidence.command_id)
        ]
        if len(matches) != 1:
            if matches:
                errors.append(
                    f"{evidence.run_id}: killed pipeline PID {evidence.pid} matched multiple ActiveJobs records; "
                    "Run Monitor was left unchanged"
                )
            continue
        proven_targets.add(matches[0])
    run_ids: list[str] = []
    for run_id in dict.fromkeys(target.run_id for target in targets):
        run_targets = [target for target in targets if target.run_id == run_id]
        if run_targets and all(target in proven_targets for target in run_targets):
            run_ids.append(run_id)
            continue
        if any(target in proven_targets for target in run_targets):
            errors.append(
                f"{run_id}: not every active pipeline target has exact killed PID/RunId proof; "
                "Run Monitor was left unchanged"
            )
        elif not any(error.startswith(f"{run_id}:") for error in errors):
            errors.append(f"{run_id}: no exact killed pipeline PID/RunId proof; Run Monitor was left unchanged")
    return run_ids, errors


def _write_idle_progress_file(progress_file: Path | None, logger: Any = None) -> str:
    """Reset a stuck pipeline_progress.json to idle stage.

    Best-effort: logs on failure but never raises so it does not mask the kill result.
    Returns a short human-readable status string.
    """
    if not progress_file:
        return "progress file path not configured"
    if not progress_file.exists():
        return "progress file not found; nothing to reset"
    try:
        existing: dict[str, Any] = json.loads(progress_file.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        if logger is not None:
            try:
                logger.warning("force-reset: could not read progress file %s: %s", progress_file, exc)
            except Exception:
                pass
        return f"could not read progress file: {exc}"

    current_stage = str(existing.get("CurrentStage") or "").lower()
    status = str(existing.get("Status") or "").strip().lower()
    if current_stage in _IDLE_STAGES and status in _IDLE_STATUSES:
        return "progress file was already idle; no change needed"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    idle_payload: dict[str, Any] = {
        "ProgressVersion": existing.get("ProgressVersion", 2),
        "LastUpdate": now,
        "SessionStartedAt": existing.get("SessionStartedAt"),
        "CurrentFile": None,
        "CurrentFileDisplay": None,
        "CurrentFilePath": None,
        "CurrentMediaType": None,
        "CurrentQueuePhase": None,
        "CurrentQueueIndex": 0,
        "CurrentQueueTotal": 0,
        "CurrentRoute": None,
        "CurrentStage": "idle",
        "CurrentStagePercent": None,
        "CurrentItemStartedAt": None,
        "CurrentStageStartedAt": None,
        "CopyState": None,
        "PushState": None,
        "SidecarState": None,
        "CopyBytesCopied": None,
        "CopyTotalBytes": None,
        "CopyPercent": None,
        "CopyAttempt": None,
        "CopySource": None,
        "CopyDestination": None,
        "CopyStartedAt": None,
        "CopyUpdatedAt": None,
        "SubtitleProgress": None,
        "AudioProgress": None,
        "PendingDrainProgress": None,
        "PauseRequested": False,
        "StopRequested": False,
        "ControlRequests": existing.get("ControlRequests"),
        "Status": "Idle",
        "TotalProcessed": existing.get("TotalProcessed", 0),
        "Encoded": existing.get("Encoded", 0),
        "Remuxed": existing.get("Remuxed", 0),
        "Failed": existing.get("Failed", 0),
        "Movies": existing.get("Movies", 0),
        "TVEpisodes": existing.get("TVEpisodes", 0),
    }
    try:
        atomic_write_text(progress_file, json.dumps(idle_payload, indent=2) + "\n")
        return f"progress reset from stage='{current_stage}', status='{status}' to idle"
    except Exception as exc:
        if logger is not None:
            try:
                logger.warning("force-reset: could not write idle progress to %s: %s", progress_file, exc)
            except Exception:
                pass
        return f"progress reset failed: {exc}"


class ProcessControlFacadeMixin:
    """Control-flag commands for the active PowerShell pipeline."""

    service: Any

    def request_pipeline_control(
        self,
        resolved: ResolvedPaths,
        action: str,
        *,
        confirm_force_stop: bool = False,
        expected_run_id: str = "",
    ) -> CommandResult:
        normalized = normalize_pipeline_control_action(action)
        command = pipeline_control_command(normalized)
        lock: object | None = None
        success_extra: dict[str, Any] = {}
        try:
            if not is_supported_pipeline_control_action(normalized):
                return CommandResult(
                    command=command,
                    ok=False,
                    message="Unsupported pipeline control action.",
                    severity="error",
                    errors=[PIPELINE_CONTROL_ACTION_ERROR],
                )
            if normalized == "kill" and confirm_force_stop is not True:
                return CommandResult(
                    command=command,
                    ok=False,
                    message="Force stop requires explicit backend confirmation.",
                    severity="error",
                    errors=["confirm_force_stop=true is required for action=kill."],
                )
            lock, block_message = self._acquire_process_control_lock(command)
            if block_message:
                return CommandResult(
                    command=command,
                    ok=False,
                    message=block_message,
                    severity="warning",
                    warnings=[block_message],
                    refresh_hint="snapshot",
                )
            if normalized == "pause":
                method = getattr(self.service, "toggle_pause_flag", None)
                if not callable(method):
                    raise RuntimeError("Pause control service is not available.")
                message = str(method(resolved))
                flag_path = resolved.pause_flag
            elif normalized == "stop":
                method = getattr(self.service, "write_stop_after_current_flag", None)
                if not callable(method):
                    raise RuntimeError("Stop After Current control service is not available.")
                run_id, target_pid, target_launch_id = _active_pipeline_stop_target(
                    resolved,
                    expected_run_id=expected_run_id,
                )
                message = str(
                    method(
                        resolved.stop_after_current_flag,
                        run_id=run_id,
                        target_pid=target_pid,
                        target_launch_id=target_launch_id,
                    )
                )
                flag_path = resolved.stop_after_current_flag
                success_extra = {
                    "semantic_action": "stop_after_current",
                    "run_id": run_id,
                    "target_pid": target_pid,
                    "target_launch_id": target_launch_id,
                }
            elif normalized == "rescan":
                method = getattr(self.service, "write_flag", None)
                if not callable(method):
                    raise RuntimeError("Rescan control service is not available.")
                message = str(method(resolved.rescan_flag, "Rescan"))
                flag_path = resolved.rescan_flag
            elif normalized == "kill":
                method = getattr(self.service, "kill_related_pipeline_processes", None)
                if not callable(method):
                    raise RuntimeError("Kill control service is not available.")
                force_stop_targets = _active_pipeline_force_stop_targets(resolved)
                kill_result = method(resolved)
                messages = [str(item) for item in kill_result]
                termination_evidence = (
                    kill_result.termination_evidence
                    if isinstance(kill_result, RelatedProcessKillReport)
                    else ()
                )
                force_stop_run_ids, monitor_errors = _correlated_force_stop_run_ids(
                    force_stop_targets,
                    termination_evidence,
                )
                logger = getattr(getattr(self, "service", None), "logger", None)
                reset_msg = _write_idle_progress_file(resolved.progress_file, logger)
                kill_summary = "; ".join(messages) if messages else "No related pipeline, audit, or CSV rerun processes found to kill."
                message = f"{kill_summary}; {reset_msg}"
                terminalized_run_ids: list[str] = []
                monitor_state_root = resolved.state_root
                if monitor_state_root is None and resolved.run_monitor_path is not None:
                    monitor_state_root = resolved.run_monitor_path.parent
                for run_id in force_stop_run_ids:
                    if monitor_state_root is None:
                        monitor_errors.append(f"{run_id}: Run Monitor state root is unavailable")
                        continue
                    try:
                        if terminalize_force_stopped_run(monitor_state_root, run_id):
                            terminalized_run_ids.append(run_id)
                    except Exception as exc:
                        monitor_errors.append(f"{run_id}: {exc}")
                success_extra = {
                    "kill_report": messages,
                    "killed_process_tree_count": len(messages),
                    "progress_reset": reset_msg,
                    "force_stopped_run_ids": terminalized_run_ids,
                    "force_stop_monitor_errors": monitor_errors,
                }
                flag_path = None
        except Exception as exc:
            return CommandResult(
                command=command,
                ok=False,
                message=f"Pipeline control failed: {exc}",
                severity="error",
                errors=[str(exc)],
                refresh_hint="snapshot",
            )
        finally:
            self._release_process_control_lock(lock)
        return CommandResult(
            command=command,
            ok=True,
            message=message,
            severity="info",
            refresh_hint="snapshot",
            data=pipeline_control_success_data(normalized, flag_path, success_extra),
        )

    def _acquire_process_control_lock(self, command: str) -> tuple[object | None, str]:
        lock = getattr(self, "_process_control_lock", None)
        if lock is None:
            return None, ""
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            self._log_process_control_exception("Process control lock acquisition failed", exc)
            return None, f"{command} blocked because the process control lock could not be verified: {exc}"
        if not acquired:
            return None, f"{command} blocked because another pipeline control command is already in progress."
        return lock, ""

    def _release_process_control_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        try:
            lock.release()  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_process_control_exception("Process control lock release failed", exc)

    def _log_process_control_exception(self, message: str, exc: Exception) -> None:
        logger = getattr(getattr(self, "service", None), "logger", None)
        if logger is None:
            return
        try:
            logger.warning("%s: %s", message, exc, exc_info=True)
        except Exception:
            return

__all__ = [
    "ProcessControlFacadeMixin",
]
