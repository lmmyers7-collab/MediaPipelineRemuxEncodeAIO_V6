"""Pipeline control command facade adapter."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from mediapipeline.desktop.application.dto_commands import CommandResult
from mediapipeline.desktop.models import ResolvedPaths

from mediapipeline.core.processes.control_policy import (
    PIPELINE_CONTROL_ACTION_ERROR,
    is_supported_pipeline_control_action,
    normalize_pipeline_control_action,
    pipeline_control_command,
    pipeline_control_success_data,
)
from mediapipeline.core.processes.file_io import atomic_write_text

_IDLE_STAGES = frozenset({"idle", "startup", ""})


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
    if current_stage in _IDLE_STAGES:
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
        return f"progress stage reset from '{current_stage}' to idle"
    except Exception as exc:
        if logger is not None:
            try:
                logger.warning("force-reset: could not write idle progress to %s: %s", progress_file, exc)
            except Exception:
                pass
        return f"progress reset failed: {exc}"


class ProcessControlFacadeMixin:
    """Control-flag commands for the active PowerShell pipeline."""

    def request_pipeline_control(self, resolved: ResolvedPaths, action: str) -> CommandResult:
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
                method = getattr(self.service, "write_flag", None)
                if not callable(method):
                    raise RuntimeError("Stop control service is not available.")
                message = str(method(resolved.stop_flag, "Stop"))
                flag_path = resolved.stop_flag
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
                messages = [str(item) for item in method(resolved)]
                logger = getattr(getattr(self, "service", None), "logger", None)
                reset_msg = _write_idle_progress_file(resolved.progress_file, logger)
                kill_summary = "; ".join(messages) if messages else "No related pipeline, audit, or CSV rerun processes found to kill."
                message = f"{kill_summary}; {reset_msg}"
                success_extra = {
                    "kill_report": messages,
                    "killed_process_tree_count": len(messages),
                    "progress_reset": reset_msg,
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
