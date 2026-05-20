from __future__ import annotations

from typing import Any

from .command_payloads_policy import resolved_paths_unavailable_payload


class LocalApiFileCommandPayloadMixin:
    def _queue_open_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.open", "queue")
        return self.facade.open_queue_location(resolved, request).to_mapping()

    def _completed_open_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("completed.open", "completed")
        return self.facade.open_completed_location(resolved, request).to_mapping()

    def _diagnostics_open_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("diagnostics.open", "diagnostics")
        return self.facade.open_diagnostics_location(resolved, request).to_mapping()

    def _pending_publish_open_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("pending_publish.open", "pending_publish")
        return self.facade.open_pending_publish_location(resolved, request).to_mapping()

    def _pending_publish_recovery_plan_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("pending_publish.recovery_plan_dry_run", "pending_publish")
        return self.facade.plan_pending_publish_recovery(resolved, request).to_mapping()
