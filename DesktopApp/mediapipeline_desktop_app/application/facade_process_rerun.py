from __future__ import annotations

from typing import Any

from ..models import ResolvedPaths
from .dto import CommandResult
from .facade_process_rerun_policy import (
    rerun_csv_path_missing_result,
    rerun_csv_path_from_request,
    rerun_mode_error_result,
    rerun_modes_are_supported,
    rerun_modes_from_request,
    rerun_start_active_work_result,
    rerun_start_exception_result,
    rerun_start_success_result,
)


class RerunLaunchFacadeMixin:
    """CSV rerun process start command adapter for the application facade."""

    def start_rerun_csv_process(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        csv_path = rerun_csv_path_from_request(request)
        if csv_path is None:
            return rerun_csv_path_missing_result()
        stage_mode, original_mode, return_mode = rerun_modes_from_request(request)
        if not rerun_modes_are_supported(stage_mode, original_mode, return_mode):
            return rerun_mode_error_result()
        launch_lock, lock_message = self._acquire_process_launch_lock("CSV rerun start")
        if lock_message:
            return rerun_start_active_work_result(lock_message)
        try:
            block_message = self._active_work_block_message(resolved, "CSV rerun start")
            if block_message:
                return rerun_start_active_work_result(block_message)
            starter = getattr(self.service, "start_rerun_csv", None)
            if not callable(starter):
                raise RuntimeError("CSV rerun start service is not available.")
            proc = starter(
                resolved=resolved,
                csv_path=csv_path,
                dry_run=bool(request.get("dry_run", False)),
                stage_mode=stage_mode,
                original_mode=original_mode,
                return_mode=return_mode,
                show_console=bool(request.get("show_console", False)),
            )
            pid = int(getattr(proc, "pid", 0) or 0)
            launch_logs = ""
            log_method = getattr(self.service, "launch_log_summary", None)
            if callable(log_method):
                launch_logs = str(log_method() or "")
        except Exception as exc:
            return rerun_start_exception_result(exc)
        finally:
            self._release_process_launch_lock(launch_lock)
        return rerun_start_success_result(
            csv_path=csv_path,
            dry_run=bool(request.get("dry_run", False)),
            stage_mode=stage_mode,
            original_mode=original_mode,
            return_mode=return_mode,
            pid=pid,
            launch_logs=launch_logs,
        )

__all__ = [
    "RerunLaunchFacadeMixin",
]
