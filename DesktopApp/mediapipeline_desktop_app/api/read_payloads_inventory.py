from __future__ import annotations

from typing import Any

from app.publish.reconciliation_policy import publish_reconciliation_from_payloads

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
        payload = self.facade.get_completed_preview(
            resolved,
            limit=query_value(query, "limit", "100"),
            force_refresh=query_bool(query, "force_refresh", False),
        ).to_mapping()
        try:
            pending_payload = self.facade.get_pending_publish_preview(resolved).to_mapping()
            reconciliation = publish_reconciliation_from_payloads(
                payload,
                pending_payload,
                limit=query_int(query, "pending_proof_limit", 250),
            ).to_mapping()
            payload["completed_pending_proof"] = reconciliation.get("completed_pending_proof") or {}
        except Exception as exc:  # pragma: no cover - defensive route isolation
            payload["completed_pending_proof"] = {
                "schema_version": "desktop_completed_pending_proof.v1",
                "evidence_authority": "backend",
                "render_contract": "completedView.evidence.js",
                "status": "Pending proof unavailable",
                "rows": [],
                "summary_lines": [
                    "Completed-to-Pending output proof cross-check:",
                    f"Backend pending proof DTO unavailable: {exc}",
                    "Safe next step: use Completed Manifest, Pending Publish, Run Logs, and Last Stderr diagnostics before acting.",
                    "Mutation guardrail: failed proof DTO generation did not repair, rerun, drain, publish, rewrite manifests, or touch media.",
                ],
                "error": str(exc),
            }
        return payload

    def _final_library_promotion_status_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("final library promotion")
        return self.facade.get_final_library_promotion_status(resolved)

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
