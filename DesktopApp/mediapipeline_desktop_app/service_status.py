from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import ResolvedPaths, Snapshot
from .service_status_active_jobs import format_active_job_summary
from .service_status_presentation import (
    activity_from_pipeline_events,
    build_current_activity as build_current_activity_text,
    display_current_file,
    display_current_file_from_pipeline_events,
    display_current_file_from_progress,
    display_library_relative_path,
    format_pipeline_event_summary,
    normalized_status,
    pipeline_event_data,
    pipeline_event_stage_label,
    status_from_pipeline_events,
    structured_status_from_pipeline_event,
    structured_status_from_progress,
)
from .service_status_errors import format_recent_error_summary
from .service_status_files import (
    latest_audit_csv as latest_audit_csv_file,
    latest_failure_json as latest_failure_json_file,
    latest_matching_file as latest_matching_report_file,
)
from .service_status_progress import (
    datetime_is_stale,
    format_audit_progress as format_audit_progress_text,
    is_audit_progress_stale as audit_progress_is_stale,
    is_progress_stale as progress_is_stale,
    parse_progress_datetime,
)
from .service_status_readers import (
    read_audit_progress_file,
    read_log_tail_file,
    read_pipeline_events_tail_file,
    read_progress_file,
)
from .service_status_snapshot_runner import build_snapshot_for_service
from .service_status_summary import build_status_summary as build_status_summary_text


class StatusServiceMixin:
    def read_progress(self, resolved: ResolvedPaths) -> dict[str, Any] | None:
        return read_progress_file(resolved.progress_file, self.logger)

    def read_audit_progress(self, resolved: ResolvedPaths) -> dict[str, Any] | None:
        return read_audit_progress_file(resolved.audit_reports_path, self.logger)

    def read_log_tail(self, resolved: ResolvedPaths, line_count: int = 150) -> str:
        return read_log_tail_file(resolved.log_file, line_count=line_count)

    def read_pipeline_events_tail(self, resolved: ResolvedPaths, line_count: int = 100) -> list[dict[str, Any]]:
        return read_pipeline_events_tail_file(resolved.event_file, line_count=line_count, logger=self.logger)

    def _format_active_job_summary(self, resolved: ResolvedPaths, *, max_items: int = 6) -> list[str]:
        return format_active_job_summary(resolved.active_jobs_path, max_items=max_items)

    def _format_recent_error_summary(
        self,
        resolved: ResolvedPaths,
        pipeline_events: list[dict[str, Any]],
        log_tail: str,
        latest_failure_json: Path | None,
        *,
        max_items: int = 8,
    ) -> list[str]:
        return format_recent_error_summary(
            resolved=resolved,
            pipeline_events=pipeline_events,
            log_tail=log_tail,
            latest_failure_json=latest_failure_json,
            max_items=max_items,
        )

    def format_diagnostics_error_summary(self, snapshot: Snapshot, *, max_items: int = 12) -> str:
        rows = self._format_recent_error_summary(
            resolved=snapshot.resolved,
            pipeline_events=snapshot.pipeline_events,
            log_tail=snapshot.log_tail,
            latest_failure_json=snapshot.latest_failure_json,
            max_items=max_items,
        )
        return "\n".join(rows)

    def format_diagnostics_event_summary(self, snapshot: Snapshot, *, max_items: int = 12) -> str:
        rows = self._format_pipeline_event_summary(snapshot.pipeline_events, max_items=max_items)
        return "\n".join(rows) if rows else "No recent pipeline events found."

    def latest_matching_file(self, folder: Path | None, pattern: str) -> Path | None:
        return latest_matching_report_file(folder, pattern)

    def latest_audit_csv(self, resolved: ResolvedPaths, priority_only: bool) -> Path | None:
        return latest_audit_csv_file(resolved, priority_only)

    def latest_failure_json(self, resolved: ResolvedPaths) -> Path | None:
        return latest_failure_json_file(resolved)

    def build_snapshot(self, resolved: ResolvedPaths, audit_root: str) -> Snapshot:
        return build_snapshot_for_service(self, resolved, audit_root)

    def _parse_progress_datetime(self, raw: str) -> datetime | None:
        return parse_progress_datetime(raw)

    def _datetime_is_stale(self, raw: str, stale_after_seconds: float) -> bool:
        return datetime_is_stale(raw, stale_after_seconds)

    def is_progress_stale(self, progress: dict[str, Any] | None, *, stale_after_seconds: float = 5.0) -> bool:
        return progress_is_stale(progress, stale_after_seconds=stale_after_seconds)

    def is_audit_progress_stale(self, audit_progress: dict[str, Any] | None, *, stale_after_seconds: float = 5.0) -> bool:
        return audit_progress_is_stale(audit_progress, stale_after_seconds=stale_after_seconds)

    def _build_status_summary(
        self,
        resolved: ResolvedPaths,
        progress: dict[str, Any] | None,
        audit_progress: dict[str, Any] | None,
        pipeline_events: list[dict[str, Any]],
        audit_root: str,
        latest_failure_report: Path | None,
        latest_failure_json: Path | None,
        latest_audit_csv: Path | None,
        latest_priority_csv: Path | None,
    ) -> str:
        recent_errors = self._format_recent_error_summary(
            resolved=resolved,
            pipeline_events=pipeline_events,
            log_tail=self.read_log_tail(resolved, line_count=80),
            latest_failure_json=latest_failure_json,
        )
        event_summary = self._format_pipeline_event_summary(pipeline_events)
        return build_status_summary_text(
            resolved=resolved,
            progress=progress,
            audit_progress=audit_progress,
            audit_root=audit_root,
            latest_failure_report=latest_failure_report,
            latest_failure_json=latest_failure_json,
            latest_audit_csv=latest_audit_csv,
            latest_priority_csv=latest_priority_csv,
            active_jobs=self._format_active_job_summary(resolved),
            recent_errors=recent_errors,
            event_summary=event_summary,
            progress_is_stale=self.is_progress_stale(progress),
            audit_progress_is_stale=self.is_audit_progress_stale(audit_progress),
        )

    def format_audit_progress(self, audit_progress: dict[str, Any] | None) -> str:
        return format_audit_progress_text(audit_progress)

    def _build_current_activity(
        self,
        resolved: ResolvedPaths,
        progress: dict[str, Any] | None,
        log_tail: str,
        pipeline_events: list[dict[str, Any]] | None = None,
    ) -> str:
        _ = resolved, log_tail
        return build_current_activity_text(progress, pipeline_events)

    def _format_pipeline_event_summary(self, events: list[dict[str, Any]], *, max_items: int = 8) -> list[str]:
        return format_pipeline_event_summary(events, max_items=max_items)

    def _display_current_file_from_progress(self, progress: dict[str, Any]) -> str:
        return display_current_file_from_progress(progress)

    def _display_library_relative_path(self, path_text: str, media_type: str) -> str:
        return display_library_relative_path(path_text, media_type)

    def _structured_status_from_progress(self, progress: dict[str, Any]) -> str:
        return structured_status_from_progress(progress)

    def _display_current_file(self, current_file: str) -> str:
        return display_current_file(current_file)

    def _normalized_status(self, status: str) -> str:
        return normalized_status(status)

    @staticmethod
    def _pipeline_event_data(event: dict[str, Any]) -> dict[str, Any]:
        return pipeline_event_data(event)

    def _activity_from_pipeline_events(self, events: list[dict[str, Any]]) -> str:
        return activity_from_pipeline_events(events)

    def _status_from_pipeline_events(self, events: list[dict[str, Any]]) -> str:
        return status_from_pipeline_events(events)

    def _display_current_file_from_pipeline_events(self, events: list[dict[str, Any]]) -> str:
        return display_current_file_from_pipeline_events(events)

    def _pipeline_event_stage_label(self, stage: str, route: str, status: str = "") -> str:
        return pipeline_event_stage_label(stage, route, status)

    def _structured_status_from_pipeline_event(self, event: dict[str, Any]) -> str:
        return structured_status_from_pipeline_event(event)
