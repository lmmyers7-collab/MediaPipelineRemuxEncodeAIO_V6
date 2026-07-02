"""Close-readiness policy helpers for active process guards."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping


ACTIVE_CLOSE_STATES = frozenset({"processing", "paused", "audit"})
NON_BLOCKING_CLOSE_STATES = frozenset({"idle", "completed", "failed", "stale", "stopped", "unknown"})
INACTIVE_PIPELINE_PROGRESS_STAGES = frozenset({"", "idle", "sleeping", "stopped", "completed"})
INACTIVE_AUDIT_PROGRESS_STATUSES = frozenset({"", "idle", "completed", "failed", "stopped"})
SNAPSHOT_UNAVAILABLE_WARNING = "Snapshot was unavailable while evaluating close readiness."
NO_ACTIVE_WORK_REASON = "No active pipeline, audit, or CSV rerun work was detected."
UNKNOWN_CLOSE_READINESS_REASON = "Close readiness is unknown because no snapshot was available."


def close_readiness_fields(
    *,
    state: str,
    snapshot_available: bool,
    block_message: str,
    continuous_watcher: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    warnings = [] if snapshot_available else [SNAPSHOT_UNAVAILABLE_WARNING]
    active_work = bool(block_message) or state in ACTIVE_CLOSE_STATES or not snapshot_available
    if not active_work and state not in NON_BLOCKING_CLOSE_STATES:
        active_work = True
    if block_message:
        reason = block_message
    elif active_work:
        reason = f"Shell close blocked because current pipeline state is {state}."
    elif state == "unknown":
        reason = UNKNOWN_CLOSE_READINESS_REASON
    else:
        reason = NO_ACTIVE_WORK_REASON
    return {
        "safe_to_close": not active_work,
        "state": state,
        "reason": reason,
        "active_work": active_work,
        "continuous_watcher": dict(continuous_watcher or {}),
        "warnings": warnings,
    }


def pipeline_progress_indicates_active_work(progress: Mapping[str, Any]) -> bool:
    stage = str(progress.get("CurrentStage", "") or "").strip().casefold()
    if stage in INACTIVE_PIPELINE_PROGRESS_STAGES:
        return False
    return True


def audit_progress_indicates_active_work(audit_progress: Mapping[str, Any]) -> bool:
    if bool(audit_progress.get("completed", False)) or bool(audit_progress.get("failed", False)):
        return False
    status = str(audit_progress.get("status", "") or "").strip().casefold()
    return status not in INACTIVE_AUDIT_PROGRESS_STATUSES


__all__ = [
    "ACTIVE_CLOSE_STATES",
    "NON_BLOCKING_CLOSE_STATES",
    "INACTIVE_PIPELINE_PROGRESS_STAGES",
    "INACTIVE_AUDIT_PROGRESS_STATUSES",
    "SNAPSHOT_UNAVAILABLE_WARNING",
    "NO_ACTIVE_WORK_REASON",
    "UNKNOWN_CLOSE_READINESS_REASON",
    "close_readiness_fields",
    "pipeline_progress_indicates_active_work",
    "audit_progress_indicates_active_work",
]
