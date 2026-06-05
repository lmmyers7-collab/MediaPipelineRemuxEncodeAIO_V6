"""Audit launch facade adapter."""

from __future__ import annotations

from typing import Any

from mediapipeline.desktop.application.dto_commands import CommandResult
from mediapipeline.desktop.models import ResolvedPaths

from mediapipeline.core.processes.audit_policy import (
    audit_missing_library_root_result,
    audit_start_active_work_result,
    audit_start_config_blocked_result,
    audit_start_exception_result,
    audit_start_success_result,
    resolve_audit_library_root,
)
from mediapipeline.core.config.identity import config_operation_block_data, config_operation_block_message


class AuditLaunchFacadeMixin:
    """Audit process start command adapter for the application facade."""

    def start_audit_process(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        config_identity = dict(getattr(resolved, "config_identity", {}) or {})
        if config_identity.get("blocks_operations") is True:
            return audit_start_config_blocked_result(
                config_operation_block_message(config_identity, "Audit start"),
                config_operation_block_data(config_identity),
            )
        library_root = resolve_audit_library_root(request, resolved.config_data)
        if not library_root:
            return audit_missing_library_root_result()
        launch_lock, lock_message = self._acquire_process_launch_lock("Audit start")
        if lock_message:
            return audit_start_active_work_result(lock_message)
        try:
            block_message = self._active_work_block_message(resolved, "Audit start")
            if block_message:
                return audit_start_active_work_result(block_message)
            launch_prep_messages: list[str] = []
            runtime_prep = getattr(self.service, "prepare_audit_runtime_for_launch", None)
            if callable(runtime_prep):
                launch_prep_messages.extend(str(item) for item in runtime_prep(resolved))
            starter = getattr(self.service, "start_audit", None)
            if not callable(starter):
                raise RuntimeError("Audit start service is not available.")
            proc = starter(
                resolved=resolved,
                library_root=library_root,
                include_sidecars=bool(request.get("include_sidecars", False)),
                show_console=bool(request.get("show_console", False)),
            )
            pid = int(getattr(proc, "pid", 0) or 0)
            launch_logs = ""
            log_method = getattr(self.service, "launch_log_summary", None)
            if callable(log_method):
                launch_logs = str(log_method() or "")
        except Exception as exc:
            return audit_start_exception_result(exc)
        finally:
            self._release_process_launch_lock(launch_lock)
        return audit_start_success_result(
            library_root=library_root,
            include_sidecars=bool(request.get("include_sidecars", False)),
            pid=pid,
            launch_prep_messages=launch_prep_messages,
            launch_logs=launch_logs,
        )

__all__ = [
    "AuditLaunchFacadeMixin",
]
