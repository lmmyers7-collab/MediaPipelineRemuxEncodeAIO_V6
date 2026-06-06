from __future__ import annotations

from typing import Any

from .command_results import resolved_paths_unavailable_payload


class LocalApiSubtitleQaCommandPayloadMixin:
    def _subtitle_qa_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/subtitle-qa/preview -- non-mutating QA preview for loaded rows."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("subtitle_qa.preview", "subtitle_qa")
        item_id = (
            request.get("id")
            or request.get("row_key")
            or request.get("source_path")
            or request.get("output_path")
            or request.get("path")
            or ""
        )
        preview = self.facade.get_subtitle_qa_item(resolved, item_id, limit=request.get("limit", 250))
        ok = str(preview.get("posture") or "").strip().casefold() not in {"blocked"}
        return {
            "schema_version": "subtitle_qa_preview.v1",
            "command": "subtitle_qa.preview",
            "ok": ok,
            "severity": "warning" if str(preview.get("posture") or "").strip().casefold() in {"review", "unknown"} else "info",
            "message": preview.get("summary") or "Subtitle QA preview generated.",
            "preview": preview,
            "guardrail": "Subtitle QA preview is read-only; it does not probe, convert, OCR, sync, repair, rewrite manifests, publish, drain, or touch media.",
        }
