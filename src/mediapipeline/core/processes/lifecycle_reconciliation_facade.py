"""Operator-facing lifecycle evidence reconciliation facade."""

from __future__ import annotations

from typing import Any

from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.lifecycle_reconciliation import LifecycleReconciliationService


LIFECYCLE_RECONCILIATION_SCHEMA_VERSION = "desktop_lifecycle_reconciliation.v1"


class LifecycleReconciliationFacadeMixin:
    """Expose a preview-bound, backend-owned recovery action."""

    def _lifecycle_reconciliation_state_root(self, resolved: ResolvedPaths):
        if resolved.state_root is not None:
            return resolved.state_root
        if resolved.local_base is not None:
            return resolved.local_base / "State"
        return None

    def preview_lifecycle_reconciliation(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> CommandResult:
        state_root = self._lifecycle_reconciliation_state_root(resolved)
        if state_root is None:
            return CommandResult(
                command="backend.lifecycle.reconcile_dry_run",
                ok=False,
                severity="error",
                message="Lifecycle reconciliation preview could not resolve the backend state root.",
                errors=["state_root_unavailable"],
                data={
                    "schema_version": LIFECYCLE_RECONCILIATION_SCHEMA_VERSION,
                    "effect": "none",
                    "safe_to_apply": False,
                    "suppress_command_journal": True,
                },
            )
        preview = LifecycleReconciliationService(state_root).preview()
        data = {
            **preview,
            "schema_version": LIFECYCLE_RECONCILIATION_SCHEMA_VERSION,
            "effect": "none",
            "reason": str(request.get("reason") or "").strip(),
            "suppress_command_journal": True,
        }
        safe = bool(data.get("safe_to_apply"))
        return CommandResult(
            command="backend.lifecycle.reconcile_dry_run",
            ok=True,
            severity="info" if safe else "warning",
            message=(
                "Lifecycle evidence is terminal, correlated, and safe to archive."
                if safe
                else "Lifecycle evidence reconciliation is blocked by the preview checks."
            ),
            warnings=[] if safe else [str(item) for item in data.get("blockers", [])],
            data=data,
        )

    def apply_lifecycle_reconciliation(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> CommandResult:
        state_root = self._lifecycle_reconciliation_state_root(resolved)
        if state_root is None:
            return CommandResult(
                command="backend.lifecycle.reconcile",
                ok=False,
                severity="error",
                message="Lifecycle evidence reconciliation could not resolve the backend state root.",
                errors=["state_root_unavailable"],
                data={"schema_version": LIFECYCLE_RECONCILIATION_SCHEMA_VERSION, "applied": False},
            )

        lock = getattr(self, "_process_launch_lock", None)
        if lock is None:
            return CommandResult(
                command="backend.lifecycle.reconcile",
                ok=False,
                severity="error",
                message="Lifecycle evidence reconciliation could not verify the process command lock.",
                errors=["process_launch_lock_unavailable"],
                data={"schema_version": LIFECYCLE_RECONCILIATION_SCHEMA_VERSION, "applied": False},
            )
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            return CommandResult(
                command="backend.lifecycle.reconcile",
                ok=False,
                severity="error",
                message="Lifecycle evidence reconciliation could not acquire the process command lock.",
                errors=[str(exc)],
                data={"schema_version": LIFECYCLE_RECONCILIATION_SCHEMA_VERSION, "applied": False},
            )
        if not acquired:
            return CommandResult(
                command="backend.lifecycle.reconcile",
                ok=False,
                severity="warning",
                message="Lifecycle evidence reconciliation is blocked by another process command.",
                errors=["process_command_in_progress"],
                data={"schema_version": LIFECYCLE_RECONCILIATION_SCHEMA_VERSION, "applied": False},
            )

        try:
            active_block = self._active_work_block_message(
                resolved,
                "Lifecycle reconciliation",
                ignore_lifecycle_recovery_evidence=True,
            )
            if active_block:
                return CommandResult(
                    command="backend.lifecycle.reconcile",
                    ok=False,
                    severity="warning",
                    message=active_block,
                    errors=["active_work_not_conclusively_absent"],
                    data={"schema_version": LIFECYCLE_RECONCILIATION_SCHEMA_VERSION, "applied": False},
                )
            result = LifecycleReconciliationService(state_root).apply(
                dry_run_fingerprint=str(request.get("dry_run_fingerprint") or ""),
                confirm_apply=request.get("confirm_apply"),
                reason=str(request.get("reason") or ""),
            )
        finally:
            lock.release()

        data = {
            **result,
            "schema_version": LIFECYCLE_RECONCILIATION_SCHEMA_VERSION,
            "effect": "lifecycle-evidence-reconciliation",
        }
        applied = bool(result.get("ok")) and bool(result.get("applied"))
        if applied:
            self.set_recovery_status(
                {
                    "schema_version": "desktop_lifecycle_recovery.v1",
                    "status": "complete",
                    "classification": "reconciled",
                    "operator_action_required": "",
                    "items": [],
                }
            )
        return CommandResult(
            command="backend.lifecycle.reconcile",
            ok=applied,
            severity="info" if applied else "error",
            message=(
                "Terminal lifecycle recovery evidence was archived and the launch gate was reconciled."
                if applied
                else "Lifecycle evidence reconciliation was not applied."
            ),
            errors=[str(item) for item in result.get("errors", [])],
            refresh_hint="diagnostics" if applied else "",
            data=data,
        )


__all__ = ["LifecycleReconciliationFacadeMixin"]
