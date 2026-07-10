"""Completed-job preview facade adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mediapipeline.core.completed.manifest import DEFAULT_COMPLETED_PROOF_MODE
from mediapipeline.core.completed.policy import (
    COMPLETED_RUNTIME_OUTCOME_EVENT_LIMIT,
    completed_history_read_error_result,
    completed_history_service_unavailable_result,
    completed_preview_from_records,
    completed_preview_limit,
    completed_record_key,
    completed_record_to_row,
    format_bytes_compact,
)
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.completed.contracts import CompletedJobRecord
from mediapipeline.core.publish.pending_rows import pending_publish_rows

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_inventory import CompletedPreviewDto


class CompletedFacadeMixin:
    """Completed-manifest preview adapter for application facades."""

    service: object

    def get_completed_preview(
        self,
        resolved: ResolvedPaths,
        limit: int | str | None = 100,
        *,
        force_refresh: bool = False,
        proof_mode: str = DEFAULT_COMPLETED_PROOF_MODE,
        include_pending_publish_overlay: bool = False,
    ) -> CompletedPreviewDto:
        loader = getattr(self.service, "load_recent_completed_jobs", None)
        if not callable(loader):
            return completed_history_service_unavailable_result()
        requested_limit = completed_preview_limit(limit)
        try:
            records = loader(
                resolved,
                limit=requested_limit,
                force_refresh=force_refresh,
                proof_mode=proof_mode,
            )
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
        pending_rows: list[dict[str, object]] = []
        overlay_warnings: list[str] = []
        scanner = getattr(self.service, "scan_pending_publish", None)
        if include_pending_publish_overlay and callable(scanner) and resolved.pending_push_path is not None:
            try:
                pending_limit = requested_limit if requested_limit is not None else 500
                pending_raw = scanner(
                    resolved,
                    manifest_limit=pending_limit,
                    include_orphan_rows=False,
                )
                if isinstance(pending_raw, dict):
                    pending_rows = pending_publish_rows(pending_raw.get("rows"))
                    overlay_warnings.extend(
                        str(item).strip()
                        for item in (pending_raw.get("warnings") or [])
                        if str(item).strip()
                    )
            except Exception as exc:
                overlay_warnings.append(f"Completed parked-output overlay could not be read: {exc}")
        preview = completed_preview_from_records(
            records,
            source=str(resolved.completed_manifest_path or ""),
            manifest_path=resolved.completed_manifest_path,
            runtime_events=runtime_events,
            runtime_event_count=len(runtime_events),
            runtime_outcome_source=str(resolved.event_file or ""),
            runtime_outcome_warning=runtime_outcome_warning,
            pending_publish_rows=pending_rows,
            warnings=overlay_warnings,
            parse_health=getattr(self.service, "_completed_history_parse_health", {}),
        )
        annotator = getattr(self.service, "annotate_final_library_promotion_rows", None)
        if not callable(annotator):
            return preview
        try:
            payload = preview.to_mapping()
            rows, promotion_status = annotator(resolved, records, list(payload.get("rows") or []))
            payload["rows"] = rows
            payload["final_library_promotion"] = promotion_status
            from mediapipeline.core.kernel.dto_inventory import CompletedPreviewDto

            return CompletedPreviewDto(**payload)
        except Exception:
            return preview

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
