"""Backend-only lifecycle recovery classification and one-shot resumption."""

from __future__ import annotations

import threading
from typing import Any, Callable

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore


RECOVERY_STATUS_SCHEMA_VERSION = "desktop_lifecycle_recovery.v1"


def initial_recovery_status() -> dict[str, Any]:
    return {
        "schema_version": RECOVERY_STATUS_SCHEMA_VERSION,
        "status": "idle",
        "classification": "unknown",
        "operator_action_required": "Backend startup reconciliation has not started.",
        "items": [],
    }


class LifecycleRecoveryCoordinator:
    def __init__(self, *, store_factory: Callable[[Any], LifecycleLeaseStore] = LifecycleLeaseStore) -> None:
        self._lock = threading.Lock()
        self._status = initial_recovery_status()
        self._store_factory = store_factory

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {**self._status, "items": [dict(item) for item in self._status.get("items", [])]}

    def _set_status(self, **updates: Any) -> dict[str, Any]:
        with self._lock:
            self._status = {**self._status, **updates, "schema_version": RECOVERY_STATUS_SCHEMA_VERSION}
            return {**self._status, "items": [dict(item) for item in self._status.get("items", [])]}

    def run(
        self,
        resolved: ResolvedPaths,
        *,
        resume: Callable[[str, dict[str, Any], str], dict[str, Any]],
    ) -> dict[str, Any]:
        if resolved.state_root is None:
            return self._set_status(
                status="blocked",
                classification="unknown",
                operator_action_required="Lifecycle state root is unavailable; backend cannot prove recovery safety.",
                items=[],
            )
        self._set_status(status="reconciling", classification="unknown", operator_action_required="Backend is reconciling durable lifecycle state.", items=[])
        store = self._store_factory(resolved.state_root)
        posture = store.status()
        status = str(posture.get("status") or "unknown")
        if status == "idle":
            return self._set_status(status="complete", classification="completed", operator_action_required="", items=[])
        if status in {"active", "unknown", "indeterminate"}:
            return self._set_status(
                status="blocked",
                classification="blocked" if status == "active" else "unknown",
                operator_action_required=str(posture.get("reason") or "Lifecycle state is not safe to resume or close."),
                items=[dict(posture)],
            )
        if status != "stale":
            return self._set_status(status="blocked", classification="unknown", operator_action_required="Unexpected lifecycle recovery posture.", items=[dict(posture)])
        lease_value = posture.get("lease")
        lease: dict[str, Any] = dict(lease_value) if isinstance(lease_value, dict) else {}
        recovery_value = lease.get("recovery")
        recovery: dict[str, Any] = dict(recovery_value) if isinstance(recovery_value, dict) else {}
        route = str(recovery.get("route") or "")
        request_value = recovery.get("request")
        request: dict[str, Any] = dict(request_value) if isinstance(request_value, dict) else {}
        if not _safe_auto_resume(route, request):
            reason = "Interrupted work was conclusively stopped and was not replayed. Existing media and progress evidence remain unchanged."
            try:
                terminal = store.retire_stale_without_replay(reason=reason)
            except Exception as exc:
                return self._set_status(
                    status="blocked",
                    classification="blocked",
                    operator_action_required=f"Interrupted work could not be retired safely: {exc}",
                    items=[dict(posture)],
                )
            return self._set_status(
                status="complete",
                classification="interrupted",
                operator_action_required="",
                items=[
                    {
                        "status": "interrupted",
                        "reason": reason,
                        "terminal_lease": terminal,
                    }
                ],
            )
        try:
            descriptor = store.begin_one_recovery_attempt()
        except Exception as exc:
            return self._set_status(status="blocked", classification="blocked", operator_action_required=str(exc), items=[dict(posture)])
        self._set_status(status="recovering", classification="recoverable", operator_action_required="Backend is automatically resuming one recoverable operation.", items=[descriptor])
        try:
            outcome = resume(route, request, str(descriptor.get("command_id") or ""))
        except Exception as exc:
            outcome = {"ok": False, "message": f"Automatic recovery execution failed: {exc}"}
        if bool(outcome.get("ok")):
            return self._set_status(status="complete", classification="recovered", operator_action_required="", items=[{**descriptor, "outcome": outcome}])
        store.mark_indeterminate(
            command_id=str(descriptor.get("command_id") or ""),
            route=route,
            reason=str(outcome.get("message") or "Automatic recovery did not produce a successful terminal result."),
        )
        return self._set_status(
            status="blocked",
            classification="parked",
            operator_action_required="Automatic resume failed; do not retry until backend reconciliation is reviewed.",
            items=[{**descriptor, "outcome": outcome}],
        )


def _safe_auto_resume(route: str, request: dict[str, Any]) -> bool:
    # Only no-media or plan-only work has a proven restart boundary today.
    # Potentially partial media work is never replayed; a conclusively dead
    # lease is retired as interrupted evidence by run() instead.
    if route == "/api/pipeline/start":
        return str(request.get("mode") or "").casefold() == "validate"
    if route == "/api/audit/start":
        return True
    if route == "/api/rerun/start":
        return bool(request.get("dry_run") is True or request.get("plan_only") is True)
    return False


__all__ = ["LifecycleRecoveryCoordinator", "RECOVERY_STATUS_SCHEMA_VERSION", "initial_recovery_status"]
