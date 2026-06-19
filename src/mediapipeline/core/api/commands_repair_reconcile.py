from __future__ import annotations

from typing import Any

from mediapipeline.core.repair_reconcile.dry_run import (
    COMPLETED_RECONCILE_MANIFEST_COMMAND,
    COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND,
    PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND,
    PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND,
    STARTUP_RECONCILE_STATE_COMMAND,
    dry_run_command_name,
)

from .command_results import resolved_paths_unavailable_payload


class LocalApiRepairReconcileCommandPayloadMixin:
    def _repair_reconcile_dry_run_payload(self, request: dict[str, Any], *, candidate_command: str, refresh_hint: str) -> dict[str, Any]:
        resolved = self._resolved()
        command = dry_run_command_name(candidate_command)
        if resolved is None:
            return resolved_paths_unavailable_payload(command, refresh_hint)
        return self.facade.plan_repair_reconcile_dry_run(
            resolved,
            candidate_command=candidate_command,
            request=request,
        ).to_mapping()

    def _repair_reconcile_apply_payload(self, request: dict[str, Any], *, candidate_command: str, refresh_hint: str) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(candidate_command, refresh_hint)
        return self.facade.apply_repair_reconcile(
            resolved,
            candidate_command=candidate_command,
            request=request,
        ).to_mapping()

    def _completed_reconcile_manifest_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._repair_reconcile_dry_run_payload(
            request,
            candidate_command=COMPLETED_RECONCILE_MANIFEST_COMMAND,
            refresh_hint="completed",
        )

    def _completed_reconcile_manifest_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._repair_reconcile_apply_payload(
            request,
            candidate_command=COMPLETED_RECONCILE_MANIFEST_COMMAND,
            refresh_hint="completed",
        )

    def _completed_repair_sidecar_metadata_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._repair_reconcile_dry_run_payload(
            request,
            candidate_command=COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND,
            refresh_hint="completed",
        )

    def _completed_repair_sidecar_metadata_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._repair_reconcile_apply_payload(
            request,
            candidate_command=COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND,
            refresh_hint="completed",
        )

    def _pending_publish_repair_manifest_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._repair_reconcile_dry_run_payload(
            request,
            candidate_command=PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND,
            refresh_hint="pending_publish",
        )

    def _pending_publish_repair_manifest_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._repair_reconcile_apply_payload(
            request,
            candidate_command=PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND,
            refresh_hint="pending_publish",
        )

    def _pending_publish_reconcile_orphan_payloads_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._repair_reconcile_dry_run_payload(
            request,
            candidate_command=PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND,
            refresh_hint="pending_publish",
        )

    def _pending_publish_reconcile_orphan_payloads_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._repair_reconcile_apply_payload(
            request,
            candidate_command=PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND,
            refresh_hint="pending_publish",
        )

    def _startup_reconcile_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        command = dry_run_command_name(STARTUP_RECONCILE_STATE_COMMAND)
        if resolved is None:
            return resolved_paths_unavailable_payload(command, "diagnostics")
        return self.facade.plan_startup_reconciliation_dry_run(
            resolved,
            request=request,
        ).to_mapping()


__all__ = [
    "LocalApiRepairReconcileCommandPayloadMixin",
]
