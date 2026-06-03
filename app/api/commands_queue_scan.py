from __future__ import annotations

from typing import Any

from .command_results import resolved_paths_unavailable_payload


class LocalApiQueueScanCommandPayloadMixin:
    def _queue_scan_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.scan", "queue")
        return self.facade.start_queue_scan(resolved, request).to_mapping()
