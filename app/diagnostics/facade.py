"""Diagnostics read/open facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.diagnostics.open_policy import (
    diagnostics_allowed_targets_error,
    diagnostics_open_disallowed_target_result,
    diagnostics_open_exception_result,
    diagnostics_open_missing_result,
    diagnostics_open_path,
    diagnostics_open_service_unavailable_result,
    diagnostics_open_success_result,
    diagnostics_open_target_label,
    normalize_diagnostics_open_target,
)

from app.diagnostics.policy import (
    clamp_diagnostics_tail_bytes,
    diagnostics_active_job_detail_rows,
    diagnostics_active_job_rows,
    diagnostics_launch_log_summary,
    diagnostics_summary_lines,
    diagnostics_tail_disallowed_payload,
    diagnostics_tail_file_payload,
    diagnostics_tail_missing_payload,
    diagnostics_warnings,
)
from app.diagnostics.state_summary import (
    DIAGNOSTICS_STATE_SUMMARY_TARGETS,
    diagnostics_should_include_settings_tool_path_evidence,
    diagnostics_state_summary_payload,
)
from app.status.active_jobs import worker_progress_payload
from app.status.eta import eta_payload
from app.status.ffmpeg_progress import ffmpeg_progress_payload
from mediapipeline_desktop_app.application.dto_commands import CommandResult
from mediapipeline_desktop_app.application.dto_status import DiagnosticsDto
from app.config.settings_policy import settings_tool_path_evidence
from app.processes.path_evidence import configured_path_health
from mediapipeline_desktop_app.models import ResolvedPaths, Snapshot


class DiagnosticsFacadeMixin:
    """Diagnostics read/open adapter for UI-neutral application facades."""

    service: object
    app_version: str

    def get_diagnostics(self, snapshot: Snapshot) -> DiagnosticsDto:
        active_jobs = self._active_job_rows(snapshot.resolved)
        recent_errors = self._summary_method_lines("format_diagnostics_error_summary", snapshot)
        recent_events = self._summary_method_lines("format_diagnostics_event_summary", snapshot)
        worker_progress = worker_progress_payload(snapshot.resolved.active_jobs_path, snapshot.progress or {}, snapshot.log_tail)
        return DiagnosticsDto(
            app_version=self.app_version,
            active_jobs=active_jobs,
            active_job_rows=diagnostics_active_job_detail_rows(snapshot.resolved),
            worker_progress=worker_progress,
            ffmpeg_progress=ffmpeg_progress_payload(snapshot.progress or {}, snapshot.log_tail, worker_progress=worker_progress),
            eta=eta_payload(worker_progress),
            recent_errors=recent_errors,
            recent_events=recent_events,
            status_summary=str(snapshot.status_summary or ""),
            log_tail=str(snapshot.log_tail or ""),
            launch_logs=diagnostics_launch_log_summary(getattr(self.service, "launch_log_summary", None)),
            warnings=diagnostics_warnings(snapshot),
        )

    def get_diagnostics_for_resolved(self, resolved: ResolvedPaths, audit_root: str = "") -> DiagnosticsDto:
        build_snapshot = getattr(self.service, "build_snapshot", None)
        if not callable(build_snapshot):
            raise RuntimeError("Application facade service does not support build_snapshot().")
        snapshot = build_snapshot(resolved, audit_root)
        if not isinstance(snapshot, Snapshot):
            raise RuntimeError("Application facade service returned an invalid snapshot.")
        return self.get_diagnostics(snapshot)

    def open_diagnostics_location(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Open a backend-allowlisted diagnostics location in the OS shell."""
        target = normalize_diagnostics_open_target(request.get("target"))
        target_label = diagnostics_open_target_label(target)
        if target_label is None:
            return diagnostics_open_disallowed_target_result()
        path = self._diagnostics_open_path(resolved, target)
        if path is None:
            return diagnostics_open_missing_result(target)
        opener = getattr(self.service, "open_path", None)
        if not callable(opener):
            return diagnostics_open_service_unavailable_result(target, path)
        try:
            opener(path)
        except Exception as exc:
            return diagnostics_open_exception_result(target, path, exc)
        return diagnostics_open_success_result(target, path)

    def read_diagnostics_tail(self, resolved: ResolvedPaths, request: dict[str, Any]) -> dict[str, Any]:
        """Read a bounded tail from a backend-allowlisted diagnostics file."""
        target = normalize_diagnostics_open_target(request.get("target"))
        max_bytes = clamp_diagnostics_tail_bytes(request.get("max_bytes"))
        target_label = diagnostics_open_target_label(target)
        if target_label is None:
            return diagnostics_tail_disallowed_payload(target, max_bytes, diagnostics_allowed_targets_error())
        path = self._diagnostics_open_path(resolved, target)
        if path is None:
            return diagnostics_tail_missing_payload(target, target_label, max_bytes)
        return diagnostics_tail_file_payload(target, target_label, path, max_bytes)

    def read_diagnostics_state_summary(self, resolved: ResolvedPaths) -> dict[str, Any]:
        """Read a bounded backend-owned summary of important diagnostics/state artifacts."""
        items = []
        for target in DIAGNOSTICS_STATE_SUMMARY_TARGETS:
            label = diagnostics_open_target_label(target) or target
            items.append(
                {
                    "target": target,
                    "label": label,
                    "path": self._diagnostics_open_path(resolved, target),
                }
            )
        config = resolved.config_data if isinstance(resolved.config_data, dict) else {}
        tool_path_evidence = (
            settings_tool_path_evidence(resolved, config)
            if diagnostics_should_include_settings_tool_path_evidence(config)
            else None
        )
        path_health = configured_path_health(resolved)
        return diagnostics_state_summary_payload(
            items,
            settings_tool_path_evidence=tool_path_evidence,
            path_health=path_health,
        )

    def _active_job_rows(self, resolved: ResolvedPaths) -> list[str]:
        return diagnostics_active_job_rows(getattr(self.service, "_format_active_job_summary", None), resolved)

    def _summary_method_lines(self, method_name: str, snapshot: Snapshot) -> list[str]:
        return diagnostics_summary_lines(method_name, getattr(self.service, method_name, None), snapshot)

    def _diagnostics_open_path(self, resolved: ResolvedPaths, target: str) -> Path | None:
        return diagnostics_open_path(
            resolved,
            target,
            latest_failure_report=self._optional_service_path("latest_failure_report", resolved),
            latest_failure_json=self._optional_service_path("latest_failure_json", resolved),
            latest_audit_csv=self._optional_audit_csv_path(resolved, False),
            latest_priority_csv=self._optional_audit_csv_path(resolved, True),
            last_stdout_log=getattr(self.service, "_last_spawn_stdout_log", None),
            last_stderr_log=getattr(self.service, "_last_spawn_stderr_log", None),
        )

    def _optional_audit_csv_path(self, resolved: ResolvedPaths, priority_only: bool) -> Path | None:
        return self._optional_service_path("newest_audit_csv", resolved, priority_only) or self._optional_service_path(
            "latest_audit_csv",
            resolved,
            priority_only,
        )

    def _optional_service_path(self, method_name: str, resolved: ResolvedPaths, *args: Any) -> Path | None:
        method = getattr(self.service, method_name, None)
        if not callable(method):
            return None
        try:
            path = method(resolved, *args)
        except Exception as exc:
            logger = getattr(self.service, "logger", None)
            if logger is not None:
                try:
                    logger.warning("Diagnostics path lookup failed for %s: %s", method_name, exc, exc_info=True)
                except Exception:
                    pass
            return None
        return path if isinstance(path, Path) else Path(path) if path else None

__all__ = [
    "DiagnosticsFacadeMixin",
]
