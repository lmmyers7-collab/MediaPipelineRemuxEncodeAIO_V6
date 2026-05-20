from __future__ import annotations

from typing import Any

from .command_payloads_policy import resolved_paths_unavailable_payload


class LocalApiMaintenanceCommandPayloadMixin:
    def _maintenance_release_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.run_release_dry_run(request).to_mapping()

    def _maintenance_release_build_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("maintenance.release_build", "maintenance")
        return self.facade.run_release_build(resolved, request).to_mapping()

    def _maintenance_completed_backfill_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("maintenance.completed_backfill_dry_run", "maintenance")
        return self.facade.run_completed_backfill_dry_run(resolved, request).to_mapping()
