from __future__ import annotations

from typing import Any

from .http_helpers import query_bool, query_int, query_value
from .read_payloads_policy import read_unavailable_payload


class LocalApiInventoryReadPayloadMixin:
    def _queue_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("queue")
        return self.facade.get_queue_preview(resolved).to_mapping()

    def _completed_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("completed")
        return self.facade.get_completed_preview(resolved, limit=query_int(query, "limit", 100)).to_mapping()

    def _failures_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("failures")
        limit = query_int(query, "limit", 100)
        source_kind = query_value(query, "source", "latest_json")
        return self.facade.get_failure_preview(resolved, source_kind=source_kind, limit=limit).to_mapping()

    def _audit_results_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("audit results")
        return self.facade.get_audit_preview(
            resolved,
            priority_only=query_bool(query, "priority_only", False),
            limit=query_int(query, "limit", 100),
        ).to_mapping()

    def _pending_publish_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("pending publish")
        return self.facade.get_pending_publish_preview(resolved).to_mapping()

    def _publish_reconciliation_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("publish reconciliation")
        return self.facade.get_publish_reconciliation_preview(resolved, limit=query_int(query, "limit", 250)).to_mapping()
