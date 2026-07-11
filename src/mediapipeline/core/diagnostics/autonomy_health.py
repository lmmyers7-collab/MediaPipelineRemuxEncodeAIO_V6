from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any
import uuid
from collections.abc import Iterable, Mapping

from mediapipeline.core.diagnostics.autonomy_evaluators import (
    category_evaluation_error as autonomy_category_evaluation_error,
    evaluate_category as autonomy_evaluate_category,
)
from mediapipeline.core.diagnostics.autonomy_growth import (
    acquire_growth_snapshot_lock,
    bounded_snapshot_limit,
    growth_snapshot_write_result,
    minimum_present,
    release_growth_snapshot_lock,
)
from mediapipeline.core.diagnostics.autonomy_policy import AutonomyPolicy, autonomy_policy_from_resolved
from mediapipeline.core.diagnostics.autonomy_recovery import (
    journal_archive_action,
    pending_publish_drain_action,
    pending_publish_recovery_plan_action,
)
from mediapipeline.core.diagnostics.autonomy_scan import (
    directory_size_scan,
    limited_iter_files,
    unique_observed_bytes,
)
from mediapipeline.core.diagnostics.autonomy_types import (
    category as autonomy_category,
    issue as autonomy_issue,
    issue_status as autonomy_issue_status,
    overall_status as autonomy_overall_status,
    status_state as autonomy_status_state,
)
from mediapipeline.core.kernel.contracts.pending_publish import PENDING_PUSH_RETRY_LIMIT
from mediapipeline.core.status.runtime_health import runtime_reliability_counters

from mediapipeline.core.diagnostics.autonomy_health_constants import *  # noqa: F403



def _autonomy_policy(resolved: Any) -> AutonomyPolicy:
    base = autonomy_policy_from_resolved(resolved)
    config = getattr(resolved, "config_data", None)
    data = config if isinstance(config, Mapping) else {}
    overrides: dict[str, Any] = {}
    if "AutonomyPendingReviewSeconds" not in data:
        overrides["pending_review_seconds"] = PENDING_REVIEW_SECONDS
    if "AutonomyPendingBlockSeconds" not in data:
        overrides["pending_block_seconds"] = PENDING_BLOCK_SECONDS
    if "AutonomyPendingRetryBlockCount" not in data:
        overrides["pending_retry_block_count"] = PENDING_RETRY_BLOCK_COUNT
    if "AutonomyPendingTotalReviewBytes" not in data:
        overrides["pending_total_review_bytes"] = PENDING_TOTAL_REVIEW_BYTES
    if "AutonomyPendingTotalBlockBytes" not in data:
        overrides["pending_total_block_bytes"] = PENDING_TOTAL_BLOCK_BYTES
    if "AutonomyFailureOperatorRequiredBlockSeconds" not in data:
        overrides["failure_operator_required_block_seconds"] = FAILURE_OPERATOR_REQUIRED_BLOCK_SECONDS
    if "AutonomyFailureOperatorRequiredBlockCount" not in data:
        overrides["failure_operator_required_block_count"] = FAILURE_OPERATOR_REQUIRED_BLOCK_COUNT
    if "AutonomyFailureInfrastructureBlockCount" not in data:
        overrides["failure_infrastructure_block_count"] = FAILURE_INFRASTRUCTURE_BLOCK_COUNT
    if "AutonomyActiveJobTimeoutGraceSeconds" not in data:
        overrides["active_job_timeout_grace_seconds"] = ACTIVE_JOB_TIMEOUT_GRACE_SECONDS
    if "AutonomyActiveJobNoTimeoutBlockSeconds" not in data:
        overrides["active_job_no_timeout_block_seconds"] = ACTIVE_JOB_NO_TIMEOUT_BLOCK_SECONDS
    if "AutonomyStorageMinFreeGB" not in data:
        overrides["storage_min_free_gb"] = DEFAULT_STORAGE_MIN_FREE_GB
    if "AutonomyStateFileReviewBytes" not in data:
        overrides["state_file_review_bytes"] = STATE_FILE_REVIEW_BYTES
    if "AutonomyStateFileBlockBytes" not in data:
        overrides["state_file_block_bytes"] = STATE_FILE_BLOCK_BYTES
    if "AutonomyScanLimit" not in data:
        overrides["scan_limit"] = AUTONOMY_SCAN_LIMIT
    if "AutonomyGrowthSnapshotMaxCount" not in data:
        overrides["growth_snapshot_max_count"] = AUTONOMY_GROWTH_SNAPSHOT_MAX_COUNT
    return replace(base, **overrides)


def autonomy_health_payload(
    resolved: Any,
    *,
    pending_publish: Mapping[str, Any] | None = None,
    path_health: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    psutil_module: Any = None,
    growth_history: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return read-only health evidence for unattended launch gating."""
    checked_at = (now or datetime.now(UTC)).astimezone(UTC)
    policy = _autonomy_policy(resolved)
    failure_findings: list[dict[str, Any]] = []
    failure_findings_error: Exception | None = None
    try:
        failure_findings = _failure_findings(resolved, checked_at, policy=policy)
    except Exception as exc:
        failure_findings_error = exc
    runtime_reliability: Mapping[str, Any] = {}
    runtime_reliability_error: Exception | None = None
    try:
        runtime_reliability = runtime_reliability_counters(
            resolved,
            pending_publish=pending_publish,
            now=checked_at,
        )
    except Exception as exc:
        runtime_reliability_error = exc
    categories = {
        "pending_publish": _evaluate_category(
            "pending_publish",
            lambda: _pending_publish_category(pending_publish, checked_at, policy=policy),
        ),
        "failures": _category_evaluation_error("failures", failure_findings_error)
        if failure_findings_error is not None
        else _evaluate_category("failures", lambda: _failures_category(failure_findings, policy=policy)),
        "workers": _evaluate_category(
            "workers",
            lambda: _workers_category(
                resolved,
                checked_at,
                psutil_module=psutil_module,
                policy=policy,
            ),
        ),
        "runtime_health": _category_evaluation_error("runtime_health", runtime_reliability_error)
        if runtime_reliability_error is not None
        else _evaluate_category("runtime_health", lambda: _runtime_health_category(runtime_reliability, policy=policy)),
        "disk_state": _evaluate_category("disk_state", lambda: _disk_state_category(resolved, path_health, policy=policy)),
        "path_health": _evaluate_category("path_health", lambda: _path_health_category(path_health)),
        "journals": _evaluate_category("journals", lambda: _journals_category(resolved, policy=policy)),
        "publish_recency": _evaluate_category("publish_recency", lambda: _publish_recency_category(resolved, checked_at, policy=policy)),
        "subtitles_ocr": _evaluate_category("subtitles_ocr", lambda: _topic_failure_category(
            "subtitles_ocr",
            "Subtitle and OCR review",
            failure_findings,
            ("subtitle", "subtitles", "ocr", "tx3g", "bdpgs", "vobsub", "ass", "ssa"),
        )),
        "audio_policy_reviews": _evaluate_category("audio_policy_reviews", lambda: _topic_failure_category(
            "audio_policy_reviews",
            "Audio policy review",
            failure_findings,
            ("audio", "downmix", "passthrough", "transcode", "channel"),
        )),
    }
    blockers = _flatten_issue(categories.values(), "blockers")
    review_items = _flatten_issue(categories.values(), "review_items")
    overall_status = _overall_status(category["status"] for category in categories.values())
    summary_lines = _summary_lines(overall_status, categories, blockers, review_items)
    return {
        "schema_version": AUTONOMY_HEALTH_SCHEMA_VERSION,
        "checked_at_utc": checked_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "overall_status": overall_status,
        "overall_status_state": _status_state(overall_status),
        "read_only": True,
        "guardrail": (
            "Backend-owned read-only autonomy health. This payload gates new launches when blocked; "
            "it does not stop active work, repair state, drain pending publish, delete files, or mutate media."
        ),
        "launch_gate": {
            "schema_version": "desktop_autonomy_launch_gate.v1",
            "can_start_new_work": overall_status != "blocked",
            "blocked_reason": str(blockers[0].get("message") or "") if blockers else "",
            "safe_next_action": _launch_gate_next_action(blockers, review_items),
            "recovery_action": _launch_gate_recovery_action(blockers, review_items),
            "policy": "Gate new work only; active workers/processes are left to existing timeout and lifecycle controls.",
        },
        "external_alert": _external_alert_payload(overall_status, blockers, review_items, summary_lines),
        "growth_projection": _growth_projection_payload(
            resolved,
            pending_publish,
            path_health,
            categories,
            blockers,
            review_items,
            checked_at,
            growth_history,
            policy,
        ),
        "runtime_reliability": runtime_reliability,
        "categories": categories,
        "blockers": blockers,
        "review_items": review_items,
        "blocked_count": len(blockers),
        "review_count": len(review_items),
        "summary_lines": summary_lines,
    }


def autonomy_health_is_blocked(payload: Mapping[str, Any] | None) -> bool:
    return str((payload or {}).get("overall_status") or "").casefold() == "blocked"


def load_autonomy_growth_history(
    resolved: Any,
    *,
    max_snapshots: int | None = None,
) -> dict[str, Any]:
    snapshot_path = _growth_snapshot_path(resolved)
    policy = _autonomy_policy(resolved)
    limit = _bounded_snapshot_limit(max_snapshots, policy=policy)
    snapshots: list[dict[str, Any]] = []
    invalid_line_count = 0
    read_error = ""
    if snapshot_path is not None and snapshot_path.exists() and snapshot_path.is_file():
        try:
            with snapshot_path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        invalid_line_count += 1
                        continue
                    if isinstance(item, Mapping):
                        snapshots.append(dict(item))
                    else:
                        invalid_line_count += 1
        except OSError as exc:
            read_error = str(exc)
    retained = snapshots[-limit:]
    return {
        "schema_version": "desktop_autonomy_growth_history.v1",
        "effect": "none",
        "read_only": True,
        "snapshot_path": str(snapshot_path or ""),
        "snapshot_count": len(retained),
        "total_snapshot_count": len(snapshots),
        "invalid_line_count": invalid_line_count,
        "max_snapshot_count": limit,
        "read_error": read_error,
        "snapshots": retained,
    }


def record_autonomy_growth_snapshot(
    resolved: Any,
    health_payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_snapshots: int | None = None,
) -> dict[str, Any]:
    snapshot_path = _growth_snapshot_path(resolved)
    recorded_at = (now or datetime.now(UTC)).astimezone(UTC)
    snapshot = _growth_snapshot_from_payload(health_payload, recorded_at)
    policy = _autonomy_policy(resolved)
    limit = _bounded_snapshot_limit(max_snapshots, policy=policy)
    if snapshot_path is None:
        return _growth_snapshot_write_result(
            snapshot_path=None,
            snapshot=snapshot,
            retained_snapshot_count=0,
            max_snapshots=limit,
            wrote_snapshot=False,
            error="state_root is unavailable",
        )
    lock_path = snapshot_path.with_name(f"{snapshot_path.name}.lock")
    lock_fd, lock_error = _acquire_growth_snapshot_lock(lock_path)
    if lock_fd is None:
        return _growth_snapshot_write_result(
            snapshot_path=snapshot_path,
            snapshot=snapshot,
            retained_snapshot_count=0,
            max_snapshots=limit,
            wrote_snapshot=False,
            error=lock_error or "snapshot lock unavailable",
            lock_path=lock_path,
        )
    try:
        history = load_autonomy_growth_history(resolved, max_snapshots=limit)
        snapshots = [item for item in history.get("snapshots", []) if isinstance(item, Mapping)]
        retained = [dict(item) for item in snapshots] + [snapshot]
        retained = retained[-limit:]
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = snapshot_path.with_name(f".{snapshot_path.name}.{uuid.uuid4().hex}.tmp")
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            for item in retained:
                handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")))
                handle.write("\n")
        os.replace(temp_path, snapshot_path)
    except OSError as exc:
        return _growth_snapshot_write_result(
            snapshot_path=snapshot_path,
            snapshot=snapshot,
            retained_snapshot_count=0,
            max_snapshots=limit,
            wrote_snapshot=False,
            error=str(exc),
            lock_path=lock_path,
        )
    finally:
        _release_growth_snapshot_lock(lock_fd, lock_path)
    return _growth_snapshot_write_result(
        snapshot_path=snapshot_path,
        snapshot=snapshot,
        retained_snapshot_count=len(retained),
        max_snapshots=limit,
        wrote_snapshot=True,
        error="",
        lock_path=lock_path,
    )



from mediapipeline.core.diagnostics.autonomy_health_projection import (
    _acquire_growth_snapshot_lock,
    _bounded_snapshot_limit,
    _category_evaluation_error,
    _evaluate_category,
    _external_alert_payload,
    _flatten_issue,
    _growth_projection_payload,
    _growth_snapshot_from_payload,
    _growth_snapshot_path,
    _growth_snapshot_write_result,
    _launch_gate_next_action,
    _launch_gate_recovery_action,
    _overall_status,
    _release_growth_snapshot_lock,
    _status_state,
    _summary_lines,
)
from mediapipeline.core.diagnostics.autonomy_health_publish import (
    _failures_category, _pending_publish_category, _workers_category,
)
from mediapipeline.core.diagnostics.autonomy_health_runtime import _runtime_health_category
from mediapipeline.core.diagnostics.autonomy_health_storage import (
    _disk_state_category,
    _failure_findings,
    _journals_category,
    _path_health_category,
    _publish_recency_category,
    _topic_failure_category,
)
from mediapipeline.core.diagnostics.autonomy_health_support import _parse_datetime

__all__ = [
    "AUTONOMY_HEALTH_SCHEMA_VERSION",
    "PENDING_REVIEW_SECONDS",
    "PENDING_BLOCK_SECONDS",
    "PENDING_RETRY_BLOCK_COUNT",
    "STATE_FILE_REVIEW_BYTES",
    "STATE_FILE_BLOCK_BYTES",
    "DEFAULT_STORAGE_MIN_FREE_GB",
    "autonomy_health_is_blocked",
    "autonomy_health_payload",
    "load_autonomy_growth_history",
    "record_autonomy_growth_snapshot",
]
