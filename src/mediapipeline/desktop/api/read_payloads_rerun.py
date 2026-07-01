from __future__ import annotations

from typing import Any

from mediapipeline.core.api.command_results import resolved_paths_unavailable_payload
from mediapipeline.core.processes.rerun_results import rerun_results_payload


class LocalApiRerunReadPayloadMixin:
    def _rerun_results_payload(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.results", "snapshot")
        try:
            limit = int((query or {}).get("limit") or 24)
        except (TypeError, ValueError):
            limit = 24
        return rerun_results_payload(resolved, service=getattr(self.facade, "service", None), limit=max(1, min(100, limit)))
