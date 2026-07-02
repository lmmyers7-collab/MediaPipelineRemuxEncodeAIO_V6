"""Config-backed autonomy health policy defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.kernel.contracts.pending_publish import PENDING_PUSH_RETRY_LIMIT

GIB_BYTES = 1024**3

AUTONOMY_POLICY_CONFIG_KEYS = (
    "AutonomyPendingReviewSeconds",
    "AutonomyPendingBlockSeconds",
    "AutonomyPendingRetryBlockCount",
    "AutonomyPendingTotalReviewBytes",
    "AutonomyPendingTotalBlockBytes",
    "AutonomyFailureOperatorRequiredBlockSeconds",
    "AutonomyFailureOperatorRequiredBlockCount",
    "AutonomyFailureInfrastructureBlockCount",
    "AutonomyActiveJobTimeoutGraceSeconds",
    "AutonomyActiveJobNoTimeoutBlockSeconds",
    "AutonomyStorageMinFreeGB",
    "AutonomyStateFileReviewBytes",
    "AutonomyStateFileBlockBytes",
    "AutonomyScanLimit",
    "AutonomyGrowthSnapshotMaxCount",
    "AutonomyWatchdogRecordLimit",
)


@dataclass(frozen=True)
class AutonomyPolicy:
    pending_review_seconds: int = 24 * 60 * 60
    pending_block_seconds: int = 72 * 60 * 60
    pending_retry_block_count: int = PENDING_PUSH_RETRY_LIMIT
    pending_total_review_bytes: int = 100 * GIB_BYTES
    pending_total_block_bytes: int = 250 * GIB_BYTES
    failure_operator_required_block_seconds: int = 72 * 60 * 60
    failure_operator_required_block_count: int = 10
    failure_infrastructure_block_count: int = 3
    active_job_timeout_grace_seconds: int = 15 * 60
    active_job_no_timeout_block_seconds: int = 30 * 60
    storage_min_free_gb: float = 100.0
    state_file_review_bytes: int = 100 * 1024**2
    state_file_block_bytes: int = 500 * 1024**2
    scan_limit: int = 500
    growth_snapshot_max_count: int = 64
    watchdog_record_limit: int = 50


def _safe_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum or parsed > maximum:
        return default
    return parsed


def _safe_float(value: Any, default: float, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum or parsed > maximum:
        return default
    return parsed


def autonomy_policy_from_config(config: Mapping[str, Any] | None) -> AutonomyPolicy:
    defaults = AutonomyPolicy()
    data = config if isinstance(config, Mapping) else {}
    return AutonomyPolicy(
        pending_review_seconds=_safe_int(
            data.get("AutonomyPendingReviewSeconds"),
            defaults.pending_review_seconds,
            minimum=60,
            maximum=30 * 24 * 60 * 60,
        ),
        pending_block_seconds=_safe_int(
            data.get("AutonomyPendingBlockSeconds"),
            defaults.pending_block_seconds,
            minimum=60,
            maximum=30 * 24 * 60 * 60,
        ),
        pending_retry_block_count=_safe_int(
            data.get("AutonomyPendingRetryBlockCount"),
            defaults.pending_retry_block_count,
            minimum=1,
            maximum=100,
        ),
        pending_total_review_bytes=_safe_int(
            data.get("AutonomyPendingTotalReviewBytes"),
            defaults.pending_total_review_bytes,
            minimum=1024**2,
            maximum=10 * 1024**4,
        ),
        pending_total_block_bytes=_safe_int(
            data.get("AutonomyPendingTotalBlockBytes"),
            defaults.pending_total_block_bytes,
            minimum=1024**2,
            maximum=10 * 1024**4,
        ),
        failure_operator_required_block_seconds=_safe_int(
            data.get("AutonomyFailureOperatorRequiredBlockSeconds"),
            defaults.failure_operator_required_block_seconds,
            minimum=60,
            maximum=30 * 24 * 60 * 60,
        ),
        failure_operator_required_block_count=_safe_int(
            data.get("AutonomyFailureOperatorRequiredBlockCount"),
            defaults.failure_operator_required_block_count,
            minimum=1,
            maximum=1000,
        ),
        failure_infrastructure_block_count=_safe_int(
            data.get("AutonomyFailureInfrastructureBlockCount"),
            defaults.failure_infrastructure_block_count,
            minimum=1,
            maximum=1000,
        ),
        active_job_timeout_grace_seconds=_safe_int(
            data.get("AutonomyActiveJobTimeoutGraceSeconds"),
            defaults.active_job_timeout_grace_seconds,
            minimum=60,
            maximum=24 * 60 * 60,
        ),
        active_job_no_timeout_block_seconds=_safe_int(
            data.get("AutonomyActiveJobNoTimeoutBlockSeconds"),
            defaults.active_job_no_timeout_block_seconds,
            minimum=60,
            maximum=24 * 60 * 60,
        ),
        storage_min_free_gb=_safe_float(
            data.get("AutonomyStorageMinFreeGB"),
            defaults.storage_min_free_gb,
            minimum=1.0,
            maximum=10000.0,
        ),
        state_file_review_bytes=_safe_int(
            data.get("AutonomyStateFileReviewBytes"),
            defaults.state_file_review_bytes,
            minimum=1024**2,
            maximum=10 * 1024**4,
        ),
        state_file_block_bytes=_safe_int(
            data.get("AutonomyStateFileBlockBytes"),
            defaults.state_file_block_bytes,
            minimum=1024**2,
            maximum=10 * 1024**4,
        ),
        scan_limit=_safe_int(
            data.get("AutonomyScanLimit"),
            defaults.scan_limit,
            minimum=50,
            maximum=5000,
        ),
        growth_snapshot_max_count=_safe_int(
            data.get("AutonomyGrowthSnapshotMaxCount"),
            defaults.growth_snapshot_max_count,
            minimum=2,
            maximum=256,
        ),
        watchdog_record_limit=_safe_int(
            data.get("AutonomyWatchdogRecordLimit"),
            defaults.watchdog_record_limit,
            minimum=10,
            maximum=500,
        ),
    )


def autonomy_policy_from_resolved(resolved: Any) -> AutonomyPolicy:
    return autonomy_policy_from_config(getattr(resolved, "config_data", None))


__all__ = [
    "AUTONOMY_POLICY_CONFIG_KEYS",
    "AutonomyPolicy",
    "GIB_BYTES",
    "autonomy_policy_from_config",
    "autonomy_policy_from_resolved",
]
