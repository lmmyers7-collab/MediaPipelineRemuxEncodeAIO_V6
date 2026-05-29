"""Queue preview and source-open facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.queue.policy import (
    INVALID_QUEUE_SNAPSHOT_WARNING,
    NO_QUEUE_SNAPSHOT_WARNING,
    QUEUE_OPEN_SCOPES,
    QUEUE_OPEN_TARGETS,
    QUEUE_RUNTIME_OUTCOME_EVENT_LIMIT,
    QUEUE_PREVIEW_SERVICE_WARNING,
    normalize_queue_open_scope,
    normalize_queue_open_target,
    queue_apply_runtime_outcomes,
    queue_excluded_row_key,
    queue_open_disallowed_scope_result,
    queue_open_disallowed_target_result,
    queue_open_exception_result,
    queue_open_path,
    queue_open_path_missing_result,
    queue_open_path_service_unavailable_result,
    queue_open_requires_row_result,
    queue_open_row_missing_result,
    queue_open_success_result,
    queue_preview_metadata,
    queue_preview_rows,
    queue_preview_warnings,
    queue_record_to_row,
    queue_row_key,
    queue_source_scan_progress_payload,
)
from mediapipeline_desktop_app.models import QueueRecord, ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult
    from mediapipeline_desktop_app.application.dto_inventory import QueuePreviewDto


def _queue_preview_dto(**fields: object) -> "QueuePreviewDto":
    from mediapipeline_desktop_app.application.dto_inventory import QueuePreviewDto

    return QueuePreviewDto(**fields)


class QueueFacadeMixin:
    """Read-only queue snapshot adapter for the application facade."""

    def get_queue_preview(self, resolved: ResolvedPaths) -> QueuePreviewDto:
        """Return the last queue snapshot without spawning a dry-run process."""
        snapshot_path = resolved.queue_snapshot_path
        if not snapshot_path or not snapshot_path.exists():
            return self._queue_preview_with_progress_warning(str(snapshot_path or ""), NO_QUEUE_SNAPSHOT_WARNING)
        read_snapshot = getattr(self.service, "_read_queue_snapshot", None)
        row_factory = getattr(self.service, "_queue_record_from_snapshot_row", None)
        if not callable(read_snapshot) or not callable(row_factory):
            return self._queue_preview_with_progress_warning(str(snapshot_path), QUEUE_PREVIEW_SERVICE_WARNING, status="blocked")
        try:
            snapshot = read_snapshot(snapshot_path)
        except Exception as exc:
            return self._queue_preview_with_progress_warning(str(snapshot_path), f"Queue snapshot could not be read: {exc}")
        if not isinstance(snapshot, dict):
            return self._queue_preview_with_progress_warning(str(snapshot_path), INVALID_QUEUE_SNAPSHOT_WARNING)
        rows = queue_preview_rows(snapshot.get("rows") or [], row_factory)
        runtime_events: list[dict[str, object]] = []
        runtime_outcome_warning = ""
        read_events = getattr(self.service, "read_pipeline_events_tail", None)
        if callable(read_events):
            try:
                runtime_events = read_events(resolved, line_count=QUEUE_RUNTIME_OUTCOME_EVENT_LIMIT)
            except Exception as exc:
                runtime_outcome_warning = f"Runtime outcome history could not be read: {exc}"
        elif resolved.event_file:
            runtime_outcome_warning = "Runtime outcome history reader is not available."
        rows = queue_apply_runtime_outcomes(rows, runtime_events)
        warnings = queue_preview_warnings(rows)
        if runtime_outcome_warning:
            warnings.append(runtime_outcome_warning)
        metadata = queue_preview_metadata(
            snapshot,
            rows,
            snapshot_path=snapshot_path,
            runtime_event_count=len(runtime_events),
            runtime_outcome_source=str(resolved.event_file or ""),
            runtime_outcome_warning=runtime_outcome_warning,
        )
        queue_progress = queue_source_scan_progress_payload(
            source=str(snapshot_path),
            row_count=len(rows),
            metadata=metadata,
            warnings=warnings,
        )
        return _queue_preview_dto(
            rows=rows,
            source=str(snapshot_path),
            queue_progress=queue_progress,
            progress_bars=list(queue_progress["progress_bars"]),
            **metadata,
            warnings=warnings,
        )

    @staticmethod
    def _queue_preview_with_progress_warning(source: str, warning: str, *, status: str = "warning") -> QueuePreviewDto:
        progress = queue_source_scan_progress_payload(
            source=source,
            warnings=[warning],
            status=status,
            detail=warning,
        )
        return _queue_preview_dto(
            source=source,
            warnings=[warning],
            queue_progress=progress,
            progress_bars=list(progress["progress_bars"]),
        )

    @staticmethod
    def _queue_record_to_row(record: QueueRecord) -> dict[str, object]:
        return queue_record_to_row(record)

    def open_queue_location(self, resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
        """Open a path selected from the backend queue snapshot, not a raw frontend path."""
        row_key = str(request.get("row_key") or "").strip().casefold()
        target = normalize_queue_open_target(request.get("target"))
        row_scope = normalize_queue_open_scope(request.get("row_scope"))
        if not row_key:
            return queue_open_requires_row_result()
        if row_scope not in QUEUE_OPEN_SCOPES:
            return queue_open_disallowed_scope_result(row_scope)
        if target not in QUEUE_OPEN_TARGETS:
            return queue_open_disallowed_target_result()

        preview = self.get_queue_preview(resolved)
        selected = self._queue_open_selected_row(preview, row_key, row_scope)
        if selected is None:
            return queue_open_row_missing_result(row_key)
        path = self._queue_open_path(selected, target)
        if path is None:
            return queue_open_path_missing_result(target, row_key, row_scope)
        opener = getattr(self.service, "open_path", None)
        if not callable(opener):
            return queue_open_path_service_unavailable_result(target, row_key, path, row_scope)
        try:
            opener(path)
        except Exception as exc:
            return queue_open_exception_result(target, row_key, path, exc, row_scope)
        return queue_open_success_result(target, row_key, path, row_scope)

    @staticmethod
    def _queue_open_path(row: dict[str, object], target: str) -> Path | None:
        return queue_open_path(row, target)

    @staticmethod
    def _queue_open_selected_row(preview: QueuePreviewDto, row_key: str, row_scope: str) -> dict[str, object] | None:
        if row_scope == "excluded":
            return next((row for row in preview.excluded_rows if queue_excluded_row_key(row) == row_key), None)
        return next((row for row in preview.rows if queue_row_key(row) == row_key), None)

__all__ = [
    "QueueFacadeMixin",
]
