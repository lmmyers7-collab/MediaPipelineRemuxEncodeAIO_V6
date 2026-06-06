from __future__ import annotations

from typing import Any

from .command_results import resolved_paths_unavailable_payload


class LocalApiMetricsCommandPayloadMixin:
    def _metrics_sources_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("metrics.sources", "metrics")
        return self.facade.save_metrics_sources(resolved, request).to_mapping()

    def _metrics_backfill_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("metrics.backfill", "metrics")
        return self.facade.run_metrics_backfill(resolved, request).to_mapping()
