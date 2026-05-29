"""Completed-job preview facade adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.completed.policy import (
    COMPLETED_RUNTIME_OUTCOME_EVENT_LIMIT,
    bounded_completed_limit,
    completed_history_read_error_result,
    completed_history_service_unavailable_result,
    completed_preview_from_records,
    completed_record_key,
    completed_record_to_row,
    format_bytes_compact,
)
from mediapipeline_desktop_app.models import CompletedJobRecord, ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_inventory import CompletedPreviewDto


class CompletedFacadeMixin:
    """Completed-manifest preview adapter for application facades."""

    service: object

    def get_completed_preview(self, resolved: ResolvedPaths, limit: int = 100) -> CompletedPreviewDto:
        loader = getattr(self.service, "load_recent_completed_jobs", None)
        if not callable(loader):
            return completed_history_service_unavailable_result()
        bounded_limit = bounded_completed_limit(limit)
        try:
            records = loader(resolved, limit=bounded_limit)
        except Exception as exc:
            return completed_history_read_error_result(resolved.completed_manifest_path, exc)
        runtime_events: list[dict[str, object]] = []
        runtime_outcome_warning = ""
        read_events = getattr(self.service, "read_pipeline_events_tail", None)
        if callable(read_events):
            try:
                runtime_events = read_events(resolved, line_count=COMPLETED_RUNTIME_OUTCOME_EVENT_LIMIT)
            except Exception as exc:
                runtime_outcome_warning = f"Completed runtime outcome history could not be read: {exc}"
        elif resolved.event_file:
            runtime_outcome_warning = "Completed runtime outcome history reader is not available."
        return completed_preview_from_records(
            records,
            source=str(resolved.completed_manifest_path or ""),
            manifest_path=resolved.completed_manifest_path,
            runtime_events=runtime_events,
            runtime_event_count=len(runtime_events),
            runtime_outcome_source=str(resolved.event_file or ""),
            runtime_outcome_warning=runtime_outcome_warning,
        )

    def _completed_record_to_row(self, record: CompletedJobRecord) -> dict[str, Any]:
        return completed_record_to_row(record)

    @staticmethod
    def _completed_record_key(record: CompletedJobRecord) -> str:
        return completed_record_key(record)

    @staticmethod
    def _format_bytes_compact(raw_bytes: int) -> str:
        return format_bytes_compact(raw_bytes)

__all__ = [
    "CompletedFacadeMixin",
]
