from __future__ import annotations

from typing import Any

from mediapipeline.core.repair_reconcile.dry_run import (
    COMPLETED_RECONCILE_MANIFEST_COMMAND,
    COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND,
    PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND,
    PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND,
    STARTUP_RECONCILE_STATE_COMMAND,
    active_work_precondition,
    completed_manifest_reconcile_dry_run,
    completed_sidecar_metadata_repair_dry_run,
    dry_run_command_name,
    pending_manifest_repair_dry_run,
    pending_orphan_payload_reconcile_dry_run,
    startup_reconciliation_dry_run,
)
from mediapipeline.core.repair_reconcile.apply import apply_repair_reconcile_from_dry_run
from mediapipeline.core.kernel.dto_commands import CommandResult


class RepairReconcileDryRunFacadeMixin:
    """Backend-owned repair/reconcile dry-run adapter."""

    service: object

    def _repair_reconcile_active_work_preconditions(self, resolved: Any) -> list[dict[str, str]]:
        try:
            block_message = self._active_work_block_message(resolved, "Repair/reconcile dry-run")
        except Exception as exc:
            block_message = f"Repair/reconcile dry-run blocked because active work could not be verified: {exc}"
        return [active_work_precondition(block_message)]

    def plan_repair_reconcile_dry_run(
        self,
        resolved: Any,
        *,
        candidate_command: str,
        request: dict[str, Any],
    ) -> CommandResult:
        base_preconditions = self._repair_reconcile_active_work_preconditions(resolved)
        if candidate_command in {COMPLETED_RECONCILE_MANIFEST_COMMAND, COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND}:
            preview = self.get_completed_preview(resolved, limit=request.get("limit") or 100, force_refresh=True).to_mapping()
            if candidate_command == COMPLETED_RECONCILE_MANIFEST_COMMAND:
                data = completed_manifest_reconcile_dry_run(
                    preview=preview,
                    resolved=resolved,
                    request=request,
                    base_preconditions=base_preconditions,
                )
            else:
                data = completed_sidecar_metadata_repair_dry_run(
                    preview=preview,
                    request=request,
                    base_preconditions=base_preconditions,
                )
            refresh_hint = "completed"
        elif candidate_command in {PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND, PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND}:
            preview = self.get_pending_publish_preview(resolved).to_mapping()
            if candidate_command == PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND:
                data = pending_manifest_repair_dry_run(
                    preview=preview,
                    request=request,
                    base_preconditions=base_preconditions,
                )
            else:
                data = pending_orphan_payload_reconcile_dry_run(
                    preview=preview,
                    request=request,
                    base_preconditions=base_preconditions,
                )
            refresh_hint = "pending_publish"
        else:
            return CommandResult(
                command=dry_run_command_name(candidate_command),
                ok=False,
                severity="error",
                message="Unsupported repair/reconcile dry-run command.",
                errors=[f"Unsupported candidate_command: {candidate_command}"],
                refresh_hint="",
                data={
                    "schema_version": "desktop_repair_reconcile_dry_run.v1",
                    "candidate_command": candidate_command,
                    "dry_run_only": True,
                    "effect": "none",
                    "suppress_command_journal": True,
                },
            )
        safe_to_apply = bool(data.get("safe_to_apply"))
        blocked = any(
            str(row.get("status") or "").casefold() == "blocked"
            for row in data.get("precondition_results") or []
            if isinstance(row, dict)
        )
        return CommandResult(
            command=dry_run_command_name(candidate_command),
            ok=True,
            severity="info" if safe_to_apply else "warning",
            message=(
                f"{candidate_command} dry-run complete; "
                f"safe_to_apply={'yes' if safe_to_apply else 'no'}; "
                f"mutation_route_available={'yes' if data.get('mutation_route_available') else 'no'}."
            ),
            warnings=[] if not blocked else ["One or more repair/reconcile dry-run preconditions are blocked."],
            refresh_hint=refresh_hint,
            data=data,
        )

    def apply_repair_reconcile(
        self,
        resolved: Any,
        *,
        candidate_command: str,
        request: dict[str, Any],
    ) -> CommandResult:
        dry_run_request = {
            "scope": request.get("scope"),
            "row_key": request.get("row_key"),
            "limit": request.get("limit"),
            "reason": request.get("reason"),
        }
        current = self.plan_repair_reconcile_dry_run(
            resolved,
            candidate_command=candidate_command,
            request=dry_run_request,
        )
        dry_run = dict(current.data or {})
        return apply_repair_reconcile_from_dry_run(
            resolved=resolved,
            candidate_command=candidate_command,
            request=request,
            dry_run=dry_run,
        )

    def plan_startup_reconciliation_dry_run(
        self,
        resolved: Any,
        *,
        request: dict[str, Any],
    ) -> CommandResult:
        pending_preview = self.get_pending_publish_preview(resolved).to_mapping()
        completed_preview = self.get_completed_preview(resolved, limit=request.get("limit") or 100, force_refresh=True).to_mapping()
        data = startup_reconciliation_dry_run(
            resolved=resolved,
            pending_publish=pending_preview,
            completed_preview=completed_preview,
            request=request,
        )
        blocked = str(data.get("overall_status") or "").casefold() == "blocked"
        review = str(data.get("overall_status") or "").casefold() == "review"
        return CommandResult(
            command=dry_run_command_name(STARTUP_RECONCILE_STATE_COMMAND),
            ok=True,
            severity="warning" if blocked or review else "info",
            message=(
                "startup.reconcile_state dry-run complete; "
                f"overall_status={data.get('overall_status')}; mutation_route_available=no."
            ),
            warnings=[] if not blocked else ["Startup reconciliation dry-run found blocked restart ambiguity."],
            refresh_hint="diagnostics",
            data=data,
        )


__all__ = [
    "RepairReconcileDryRunFacadeMixin",
]
