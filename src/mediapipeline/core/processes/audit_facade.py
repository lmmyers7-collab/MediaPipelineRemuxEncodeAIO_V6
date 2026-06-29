"""Audit launch facade adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from mediapipeline.desktop.application.dto_commands import CommandResult
from mediapipeline.desktop.models import ResolvedPaths

from mediapipeline.core.processes.audit_policy import (
    AUDIT_STOP_COMMAND,
    audit_missing_library_root_result,
    audit_start_active_work_result,
    audit_start_config_blocked_result,
    audit_start_exception_result,
    audit_start_success_result,
    audit_stop_active_work_result,
    audit_stop_confirm_required_result,
    audit_stop_exception_result,
    audit_stop_success_result,
    resolve_audit_library_roots,
)
from mediapipeline.core.config.identity import config_operation_block_data, config_operation_block_message
from mediapipeline.core.processes.file_io import atomic_write_text, read_json_file


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _stopped_audit_progress_payload(existing: dict[str, Any], *, messages: list[str], reason: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    processed = _coerce_int(existing.get("processed_files", existing.get("ProcessedFiles", 0)))
    total = _coerce_int(existing.get("total_files", existing.get("TotalFiles", 0)))
    raw_percent = existing.get("percent_complete", existing.get("PercentComplete", 0))
    try:
        percent = float(raw_percent or 0)
    except (TypeError, ValueError):
        percent = 0.0
    if total > 0 and processed > 0:
        percent = max(percent, min(100.0, round((processed / total) * 100.0, 1)))
    payload = dict(existing)
    payload.update(
        {
            "schema_version": str(existing.get("schema_version") or "desktop_audit_progress.v1"),
            "status": "stopped",
            "completed": False,
            "failed": False,
            "last_update": now,
            "updated_at": now,
            "processed_files": processed,
            "total_files": total,
            "percent_complete": percent,
            "current_file": "",
            "current_operation": "Stopped by operator from Reports Stop Audit.",
            "stop_requested": True,
            "stop_requested_at": now,
            "stop_reason": reason,
            "stop_messages": messages,
            "progress_persistence_healthy": True,
            "progress_write_failures": 0,
        }
    )
    return payload


def _write_stopped_audit_progress_file(
    resolved: ResolvedPaths,
    *,
    messages: list[str],
    reason: str,
) -> str:
    audit_reports_path = resolved.audit_reports_path
    if audit_reports_path is None:
        return "audit_progress.json was not available to mark stopped."
    progress_path = audit_reports_path / "audit_progress.json"
    existing: dict[str, Any] = {}
    if progress_path.exists():
        try:
            loaded = read_json_file(progress_path, retries=1)
            if isinstance(loaded, dict):
                existing = loaded
        except Exception as exc:
            existing = {"progress_read_error": str(exc)}
    payload = _stopped_audit_progress_payload(existing, messages=messages, reason=reason)
    atomic_write_text(progress_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return f"marked {progress_path} stopped"


class AuditLaunchFacadeMixin:
    """Audit process start command adapter for the application facade."""

    def start_audit_process(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        config_identity = dict(getattr(resolved, "config_identity", {}) or {})
        if config_identity.get("blocks_operations") is True:
            return audit_start_config_blocked_result(
                config_operation_block_message(config_identity, "Audit start"),
                config_operation_block_data(config_identity),
            )
        library_roots = resolve_audit_library_roots(request, resolved.config_data)
        library_root = library_roots[0] if library_roots else ""
        if not library_roots:
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
            start_kwargs = {
                "resolved": resolved,
                "library_root": library_root,
                "include_sidecars": bool(request.get("include_sidecars", False)),
                "show_console": bool(request.get("show_console", False)),
            }
            if len(library_roots) > 1:
                start_kwargs["library_roots"] = library_roots
            proc = starter(**start_kwargs)
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
            library_roots=library_roots,
            include_sidecars=bool(request.get("include_sidecars", False)),
            pid=pid,
            launch_prep_messages=launch_prep_messages,
            launch_logs=launch_logs,
        )

    def stop_audit_process(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        if request.get("confirm_stop") is not True:
            return audit_stop_confirm_required_result()
        reason = str(request.get("reason") or "Reports Stop Audit button").strip() or "Reports Stop Audit button"
        lock: object | None = None
        try:
            lock, block_message = self._acquire_process_control_lock(AUDIT_STOP_COMMAND)
            if block_message:
                return audit_stop_active_work_result(block_message)
            messages: list[str] = []
            cleanup_tracked = getattr(self.service, "kill_active_spawned_processes", None)
            if callable(cleanup_tracked):
                messages.extend(str(item) for item in cleanup_tracked(job_kinds={"audit"}))
            cleanup_related = getattr(self.service, "kill_related_pipeline_processes", None)
            if callable(cleanup_related):
                messages.extend(str(item) for item in cleanup_related(resolved, job_kinds={"audit"}))
            progress_reset = _write_stopped_audit_progress_file(resolved, messages=messages, reason=reason)
        except Exception as exc:
            return audit_stop_exception_result(exc)
        finally:
            self._release_process_control_lock(lock)
        return audit_stop_success_result(messages=messages, progress_reset=progress_reset, reason=reason)

__all__ = [
    "AuditLaunchFacadeMixin",
]
