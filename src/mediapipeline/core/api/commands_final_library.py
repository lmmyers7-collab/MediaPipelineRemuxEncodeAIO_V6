from __future__ import annotations

from typing import Any

from .command_results import resolved_paths_unavailable_payload


class LocalApiFinalLibraryPromotionCommandPayloadMixin:
    def _final_library_promote_queue_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("final_library.promote_queue", "snapshot")
        return self.facade.start_final_library_promotion(resolved, request).to_mapping()

    def _final_library_promotion_pause_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("final_library.pause", "snapshot")
        return self.facade.pause_final_library_promotion(resolved, request).to_mapping()

    def _final_library_promotion_resume_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("final_library.resume", "snapshot")
        return self.facade.resume_final_library_promotion(resolved, request).to_mapping()


__all__ = ["LocalApiFinalLibraryPromotionCommandPayloadMixin"]
