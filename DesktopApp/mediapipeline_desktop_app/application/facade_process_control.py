from __future__ import annotations

from ..models import ResolvedPaths
from .dto import CommandResult
from .facade_process_control_policy import (
    PIPELINE_CONTROL_ACTION_ERROR,
    is_supported_pipeline_control_action,
    normalize_pipeline_control_action,
    pipeline_control_command,
    pipeline_control_success_data,
)


class ProcessControlFacadeMixin:
    """Control-flag commands for the active PowerShell pipeline."""

    def request_pipeline_control(self, resolved: ResolvedPaths, action: str) -> CommandResult:
        normalized = normalize_pipeline_control_action(action)
        command = pipeline_control_command(normalized)
        lock: object | None = None
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
                messages = method(resolved)
                message = (
                    "; ".join(messages)
                    if messages
                    else "No active pipeline processes found to kill."
                )
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
            data=pipeline_control_success_data(normalized, flag_path),
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
