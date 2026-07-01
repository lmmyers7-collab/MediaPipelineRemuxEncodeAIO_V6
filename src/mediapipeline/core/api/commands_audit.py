from __future__ import annotations

from typing import Any

from .command_results import resolved_paths_unavailable_payload


class LocalApiAuditCommandPayloadMixin:
    def _audit_sources_command_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("audit.sources", "audit-controls")
        return self.facade.save_audit_sources(resolved, request).to_mapping()

    def _audit_sources_scan_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("audit.sources.scan", "audit-controls")
        return self.facade.scan_audit_sources(resolved, request).to_mapping()

    def _audit_score_policy_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("audit.score_policy", "audit-controls")
        return self.facade.save_audit_score_policy(resolved, request).to_mapping()

    def _audit_ignore_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("audit.ignore", "audit-controls")
        return self.facade.update_audit_ignore(resolved, request).to_mapping()

    def _audit_export_rerun_csv_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("audit.export_rerun_csv", "audit-controls")
        return self.facade.export_audit_rerun_csv(resolved, request).to_mapping()


__all__ = [
    "LocalApiAuditCommandPayloadMixin",
]
