"""Subtitle QA read-only facade mixin."""

from __future__ import annotations

from typing import Any

from mediapipeline.core.completed.manifest import DEFAULT_COMPLETED_PROOF_MODE
from mediapipeline.core.subtitles.qa import subtitle_qa_item_from_payloads, subtitle_qa_summary_from_payloads
from mediapipeline.core.paths.contracts import ResolvedPaths


class SubtitleQaFacadeMixin:
    """Read-only subtitle QA evidence assembled from Queue and Completed payloads."""

    def get_subtitle_qa_summary(self, resolved: ResolvedPaths, *, limit: Any = 250) -> dict[str, Any]:
        queue_payload = self.get_queue_preview(resolved).to_mapping()
        completed_payload = self.get_completed_preview(
            resolved,
            limit=limit,
            proof_mode=DEFAULT_COMPLETED_PROOF_MODE,
        ).to_mapping()
        return subtitle_qa_summary_from_payloads(queue_payload, completed_payload, limit=limit)

    def get_subtitle_qa_item(self, resolved: ResolvedPaths, item_id: Any, *, limit: Any = 250) -> dict[str, Any]:
        queue_payload = self.get_queue_preview(resolved).to_mapping()
        completed_payload = self.get_completed_preview(
            resolved,
            limit=limit,
            proof_mode=DEFAULT_COMPLETED_PROOF_MODE,
        ).to_mapping()
        return subtitle_qa_item_from_payloads(queue_payload, completed_payload, item_id, limit=limit)


__all__ = ["SubtitleQaFacadeMixin"]
