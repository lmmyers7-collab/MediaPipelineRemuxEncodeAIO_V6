"""CSV rerun launch facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.desktop.application.dto_commands import CommandResult
from mediapipeline.desktop.models import ResolvedPaths

from mediapipeline.core.processes.rerun_policy import (
    rerun_csv_path_missing_result,
    rerun_csv_path_from_request,
    rerun_dry_run_from_request,
    rerun_mode_error_result,
    rerun_modes_are_supported,
    rerun_modes_from_request,
    rerun_plan_flags_are_supported,
    rerun_plan_mode_error_result,
    rerun_plan_only_from_request,
    rerun_start_active_work_result,
    rerun_start_config_blocked_result,
    rerun_start_exception_result,
    rerun_start_success_result,
)
from mediapipeline.core.processes.rerun_preview import (
    materialize_scoped_rerun_csv,
    request_needs_scoped_csv,
    rerun_csv_preview_payload,
)
from mediapipeline.core.config.identity import config_operation_block_data, config_operation_block_message


class RerunLaunchFacadeMixin:
    """CSV rerun process start command adapter for the application facade."""

    def preview_rerun_csv(self, resolved: ResolvedPaths, request: dict[str, Any]) -> dict[str, Any]:
        return rerun_csv_preview_payload(resolved, request, service=self.service)

    def start_rerun_csv_process(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        config_identity = dict(getattr(resolved, "config_identity", {}) or {})
        if config_identity.get("blocks_operations") is True:
            return rerun_start_config_blocked_result(
                config_operation_block_message(config_identity, "CSV rerun start"),
                config_operation_block_data(config_identity),
            )
        csv_path = rerun_csv_path_from_request(request)
        if csv_path is None:
            return rerun_csv_path_missing_result()
        stage_mode, original_mode, return_mode = rerun_modes_from_request(request)
        if not rerun_modes_are_supported(stage_mode, original_mode, return_mode):
            return rerun_mode_error_result()
        dry_run = rerun_dry_run_from_request(request)
        plan_only = rerun_plan_only_from_request(request)
        if not rerun_plan_flags_are_supported(dry_run, plan_only):
            return rerun_plan_mode_error_result()
        preview = self.preview_rerun_csv(resolved, request)
        if plan_only:
            return CommandResult(
                command="rerun.start",
                ok=bool(preview.get("ok")),
                message=str(preview.get("message") or "CSV rerun preview complete."),
                severity=str(preview.get("severity") or "info"),
                errors=[str(item) for item in preview.get("errors") or []],
                warnings=[str(item) for item in preview.get("warnings") or []],
                refresh_hint="",
                data=preview,
            )
        if preview.get("status") == "blocked":
            return CommandResult(
                command="rerun.start",
                ok=False,
                message=str(preview.get("message") or "CSV rerun preview is blocked."),
                severity="error",
                errors=[str(item) for item in preview.get("errors") or []] or [str(preview.get("message") or "CSV rerun preview is blocked.")],
                warnings=[str(item) for item in preview.get("warnings") or []],
                refresh_hint="",
                data=preview,
            )
        launch_csv_path = csv_path
        scoped_csv_path = None
        scoped_info: dict[str, Any] = {}
        needs_scoped_csv = request_needs_scoped_csv(request, preview)
        launch_lock, lock_message = self._acquire_process_launch_lock("CSV rerun start")
        if lock_message:
            return rerun_start_active_work_result(lock_message)
        try:
            block_message = self._active_work_block_message(resolved, "CSV rerun start")
            if block_message:
                return rerun_start_active_work_result(block_message)
            if needs_scoped_csv:
                scoped_info = materialize_scoped_rerun_csv(resolved, request, preview=preview, service=self.service)
                launch_csv_path = Path(str(scoped_info.get("scoped_csv_path") or csv_path))
                scoped_csv_path = launch_csv_path
            starter = getattr(self.service, "start_rerun_csv", None)
            if not callable(starter):
                raise RuntimeError("CSV rerun start service is not available.")
            proc = starter(
                resolved=resolved,
                csv_path=launch_csv_path,
                dry_run=dry_run,
                plan_only=plan_only,
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
            csv_path=launch_csv_path,
            dry_run=dry_run,
            plan_only=plan_only,
            stage_mode=stage_mode,
            original_mode=original_mode,
            return_mode=return_mode,
            pid=pid,
            launch_logs=launch_logs,
            source_csv_path=csv_path,
            scoped_csv_path=scoped_csv_path,
            scope=dict(preview.get("scope") or scoped_info.get("scope") or {}),
            preview_counts=dict(preview.get("counts") or {}),
        )

__all__ = [
    "RerunLaunchFacadeMixin",
]
