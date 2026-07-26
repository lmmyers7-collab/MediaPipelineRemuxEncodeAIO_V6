"""Compatibility shim. Moved to ``mediapipeline.core.kernel.contracts`` by ADR-0013 (Wave 5).

Re-exports the contracts aggregator public namespace from the new home so
existing imports (``from mediapipeline.desktop.contracts import ...``)
keep working. New code should import from ``mediapipeline.core.kernel.contracts`` directly;
this shim package is removed in the ADR-0013 Wave 6 cleanup.
"""
from mediapipeline.core.kernel import contracts as _moved
globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved

__all__ = [
    "ACCEPTED_RUN_ROWS_FINGERPRINT_SCHEMA",
    "ACTIVE_JOB_SCHEMA_VERSION",
    "ACTIVE_JOB_STATUSES",
    "ActiveJobRecord",
    "CompletedJob",
    "ContractError",
    "CONTROL_FLAG_ACTIONS",
    "CONTROL_FLAG_SCHEMA_VERSION",
    "ControlFlagRecord",
    "PendingPushManifest",
    "PENDING_PUSH_MANIFEST_STATES",
    "PipelineEvent",
    "ProcessFileResult",
    "ProgressState",
    "QueuePlanExcludedRow",
    "QueuePlanRow",
    "QueuePlanSnapshot",
    "accepted_run_rows_fingerprint",
]
