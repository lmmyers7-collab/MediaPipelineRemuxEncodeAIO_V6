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


from mediapipeline.core.diagnostics.autonomy_health_support import *  # noqa: F403

def _category(
    key: str,
    status: str,
    *,
    label: str | None = None,
    metrics: Mapping[str, Any] | None = None,
    summary_lines: list[str] | None = None,
    blockers: list[dict[str, Any]] | None = None,
    review_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return autonomy_category(
        key,
        status,
        labels=AUTONOMY_CATEGORY_LABELS,
        label=label,
        metrics=metrics,
        summary_lines=summary_lines,
        blockers=blockers,
        review_items=review_items,
    )


def _evaluate_category(key: str, factory: Any) -> dict[str, Any]:
    return autonomy_evaluate_category(key, factory)


def _category_evaluation_error(key: str, exc: Exception | None) -> dict[str, Any]:
    return autonomy_category_evaluation_error(key, exc or RuntimeError("Unknown autonomy category evaluation error."))


def _issue(
    code: str,
    category: str,
    severity: str,
    message: str,
    *,
    evidence_path: str = "",
    age_seconds: int | float | None = None,
    next_action: str,
    recovery_action: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return autonomy_issue(
        code,
        category,
        severity,
        message,
        evidence_path=evidence_path,
        age_seconds=age_seconds,
        next_action=next_action,
        recovery_action=recovery_action,
    )


def _issue_status(blockers: list[dict[str, Any]], review_items: list[dict[str, Any]]) -> str:
    return autonomy_issue_status(blockers, review_items)


def _overall_status(statuses: Iterable[str]) -> str:
    return autonomy_overall_status(statuses)


def _status_state(status: str) -> str:
    return autonomy_status_state(status)


def _flatten_issue(categories: Iterable[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for category in categories:
        issues.extend(dict(item) for item in category.get(key, []) if isinstance(item, Mapping))
    return issues


def _summary_lines(
    overall_status: str,
    categories: Mapping[str, Mapping[str, Any]],
    blockers: list[Mapping[str, Any]],
    review_items: list[Mapping[str, Any]],
) -> list[str]:
    counts: dict[str, int] = {}
    for category in categories.values():
        status = str(category.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    lines = [
        f"Autonomy health: {overall_status}.",
        f"Categories: ready={counts.get('ready', 0)}; review={counts.get('review', 0)}; blocked={counts.get('blocked', 0)}.",
        f"Blockers: {len(blockers)}; review items: {len(review_items)}.",
        "Policy: blocked health gates new work only; active work is not forcibly stopped by this pilot check.",
    ]
    if blockers:
        lines.append(f"First blocker: {blockers[0].get('message')}")
    return lines


def _external_alert_payload(
    overall_status: str,
    blockers: list[Mapping[str, Any]],
    review_items: list[Mapping[str, Any]],
    summary_lines: list[str],
) -> dict[str, Any]:
    blocker_codes = _issue_codes(blockers)
    review_codes = _issue_codes(review_items)
    level = _external_alert_level(overall_status)
    return {
        "schema_version": "desktop_autonomy_alert.v1",
        "effect": "none",
        "read_only": True,
        "operator_attention_required": overall_status != "ready",
        "alert_level": level,
        "subject": _external_alert_subject(overall_status),
        "dedupe_key": _external_alert_dedupe_key(overall_status, blocker_codes, review_codes),
        "recommended_poll_interval_seconds": _external_alert_poll_interval(overall_status),
        "would_send_notifications": False,
        "would_write_files": False,
        "polling_endpoint_hint": "/api/diagnostics/state-summary",
        "cli_hint": "mediapipeline.tools.autonomy_health_gate",
        "policy": (
            "External monitors may poll this metadata and send their own alerts. "
            "The backend payload does not send email, call webhooks, write export files, or mutate pipeline state."
        ),
        "blocker_codes": blocker_codes,
        "review_codes": review_codes,
        "first_blocker": _alert_issue_summary(blockers[0]) if blockers else {},
        "first_review": _alert_issue_summary(review_items[0]) if review_items else {},
        "next_action": _launch_gate_next_action(blockers, review_items),
        "summary_lines": list(summary_lines[:5]),
    }


def _growth_projection_payload(
    resolved: Any,
    pending_publish: Mapping[str, Any] | None,
    path_health: Mapping[str, Any] | None,
    categories: Mapping[str, Mapping[str, Any]],
    blockers: list[Mapping[str, Any]],
    review_items: list[Mapping[str, Any]],
    checked_at: datetime,
    growth_history: Mapping[str, Any] | None,
    policy: AutonomyPolicy,
) -> dict[str, Any]:
    disk_metrics = _category_metrics(categories, "disk_state")
    journal_metrics = _category_metrics(categories, "journals")
    runtime_metrics = _category_metrics(categories, "runtime_health")
    pending_bytes = _safe_int((pending_publish or {}).get("total_bytes")) if isinstance(pending_publish, Mapping) else 0
    state_root_bytes = _safe_int(disk_metrics.get("state_root_size_bytes"))
    local_base_bytes = _safe_int(disk_metrics.get("local_base_scanned_size_bytes"))
    journal_bytes = _safe_int(journal_metrics.get("total_size_bytes"))
    active_jobs_count = _safe_int(runtime_metrics.get("active_jobs_total_count"))
    worker_process_count = _safe_int(runtime_metrics.get("worker_slot_active_child_count"))
    storage_roots = _growth_storage_roots(path_health, policy=policy)
    minimum_free_bytes = _minimum_present(row.get("free_bytes") for row in storage_roots)
    unique_scanned_bytes = unique_observed_bytes(
        [
            (_path_or_none(getattr(resolved, "state_root", None)), state_root_bytes),
            (_path_or_none(getattr(resolved, "local_base", None)), local_base_bytes),
        ]
    )
    observed_bytes_legacy = state_root_bytes + local_base_bytes + pending_bytes
    observed_bytes = unique_scanned_bytes + pending_bytes
    current_budget = {
        "state_root_size_bytes": state_root_bytes,
        "state_root_scan_truncated": bool(disk_metrics.get("state_root_scan_truncated")),
        "state_root_size_lower_bound": bool(disk_metrics.get("state_root_size_lower_bound")),
        "local_base_scanned_size_bytes": local_base_bytes,
        "local_base_scan_truncated": bool(disk_metrics.get("local_base_scan_truncated")),
        "local_base_size_lower_bound": bool(disk_metrics.get("local_base_size_lower_bound")),
        "journal_file_bytes": journal_bytes,
        "pending_publish_bytes": pending_bytes,
        "pending_publish_oldest_age_seconds": runtime_metrics.get("pending_publish_oldest_age_seconds"),
        "pending_done_oldest_age_seconds": runtime_metrics.get("worker_pending_report_oldest_age_seconds"),
        "process_count": active_jobs_count + worker_process_count,
        "process_count_source": "active_jobs_plus_worker_slots_lower_bound",
        "state_db_size_bytes": runtime_metrics.get("sqlite_db_size_bytes"),
        "state_db_wal_size_bytes": runtime_metrics.get("sqlite_wal_size_bytes"),
        "state_db_completed_jobs_count": runtime_metrics.get("sqlite_completed_jobs_count"),
        "state_db_completed_jobs_max_rows": runtime_metrics.get("sqlite_completed_jobs_max_rows"),
        "log_size_bytes": runtime_metrics.get("debug_log_size_bytes"),
        "log_max_bytes": runtime_metrics.get("debug_log_max_bytes"),
        "log_rotation_state": runtime_metrics.get("debug_log_rotation_state"),
        "failure_ledger_size": runtime_metrics.get("coordinator_failure_ledger_count"),
        "failure_ledger_max_entries": runtime_metrics.get("coordinator_failure_ledger_max_entries"),
        "reclaimed_source_quarantine_count": runtime_metrics.get("coordinator_reclaimed_source_quarantine_count"),
        "reclaimed_source_quarantine_oldest_age_seconds": runtime_metrics.get(
            "coordinator_reclaimed_source_quarantine_oldest_age_seconds"
        ),
        "observed_filesystem_bytes_unique": unique_scanned_bytes,
        "observed_bytes": observed_bytes,
        "observed_bytes_legacy_may_overlap": observed_bytes_legacy,
        "minimum_free_bytes": minimum_free_bytes,
        "storage_row_count": len(storage_roots),
        "current_only_may_overlap_scanned_roots": False,
        "autonomy_scan_limit": policy.scan_limit,
    }
    trend = _growth_projection_from_history(growth_history, current_budget, checked_at)
    blocker_codes = _issue_codes(blockers)
    review_codes = _issue_codes(review_items)
    return {
        "schema_version": "desktop_autonomy_growth_projection.v1",
        "effect": "none",
        "read_only": True,
        "operator_status": "blocked" if blocker_codes else "review" if review_codes else "ready",
        "confidence": trend["confidence"],
        "historical_samples_available": trend["historical_samples_available"],
        "required_snapshot_count": AUTONOMY_GROWTH_REQUIRED_SNAPSHOTS,
        "history_sample_count": trend["history_sample_count"],
        "snapshot_source": trend["snapshot_source"],
        "would_write_snapshots": False,
        "would_delete_or_cleanup": False,
        "pilot_window_days": AUTONOMY_GROWTH_PILOT_DAYS,
        "projection_window_days": AUTONOMY_GROWTH_PROJECTION_DAYS,
        "current_budget": current_budget,
        "storage_roots": storage_roots,
        "current_blocker_codes": blocker_codes,
        "current_review_codes": review_codes,
        "basis_snapshot_recorded_at_utc": trend["basis_snapshot_recorded_at_utc"],
        "observed_growth_bytes": trend["observed_growth_bytes"],
        "trend_window_seconds": trend["trend_window_seconds"],
        "growth_rate_bytes_per_day": trend["growth_rate_bytes_per_day"],
        "projected_7_day_growth_bytes": trend["projected_7_day_growth_bytes"],
        "projected_30_day_growth_bytes": trend["projected_30_day_growth_bytes"],
        "days_to_budget_exhaustion": trend["days_to_budget_exhaustion"],
        "next_action": _growth_projection_next_action(blocker_codes, review_codes),
        "policy": (
            "This payload reports current growth-budget evidence and optional history-based estimates. "
            "It does not persist trend snapshots, rotate logs, clean files, or change launch/publish behavior."
        ),
    }


def _category_metrics(categories: Mapping[str, Mapping[str, Any]], key: str) -> Mapping[str, Any]:
    category = categories.get(key)
    if not isinstance(category, Mapping):
        return {}
    metrics = category.get("metrics")
    if isinstance(metrics, Mapping):
        return metrics
    return {}


def _growth_storage_roots(path_health: Mapping[str, Any] | None, *, policy: AutonomyPolicy) -> list[dict[str, Any]]:
    if not isinstance(path_health, Mapping):
        return []
    rows = path_health.get("rows")
    if not isinstance(rows, list):
        return []
    storage_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        free_gb = _safe_float(row.get("free_space_gb"), row.get("free_gb"))
        if free_gb is None:
            continue
        reserve_gb = _safe_float(row.get("reserve_gb"))
        threshold_gb = reserve_gb if reserve_gb and reserve_gb > 0 else policy.storage_min_free_gb
        storage_rows.append(
            {
                "key": str(row.get("key") or ""),
                "label": str(row.get("label") or row.get("key") or ""),
                "role": str(row.get("role") or ""),
                "path": str(row.get("path") or ""),
                "free_bytes": _gb_to_bytes(free_gb),
                "threshold_bytes": _gb_to_bytes(threshold_gb),
                "storage_status": str(row.get("storage_status") or ""),
                "operator_status": str(row.get("operator_status") or row.get("status") or ""),
            }
        )
    return storage_rows


def _growth_projection_from_history(
    growth_history: Mapping[str, Any] | None,
    current_budget: Mapping[str, Any],
    checked_at: datetime,
) -> dict[str, Any]:
    no_history = {
        "confidence": "current_evidence_only",
        "historical_samples_available": False,
        "history_sample_count": 0,
        "snapshot_source": "not_persisted_by_v1",
        "basis_snapshot_recorded_at_utc": "",
        "observed_growth_bytes": None,
        "trend_window_seconds": None,
        "growth_rate_bytes_per_day": None,
        "projected_7_day_growth_bytes": None,
        "projected_30_day_growth_bytes": None,
        "days_to_budget_exhaustion": None,
    }
    if not isinstance(growth_history, Mapping):
        return no_history
    snapshots = _valid_growth_snapshots(growth_history.get("snapshots"), checked_at)
    if not snapshots:
        result = dict(no_history)
        result["snapshot_source"] = str(growth_history.get("snapshot_path") or "provided_history")
        return result
    basis = snapshots[-1]
    basis_at = basis["recorded_at"]
    trend_window_seconds = max(0, int((checked_at - basis_at).total_seconds()))
    if trend_window_seconds <= 0:
        result = dict(no_history)
        result["history_sample_count"] = len(snapshots)
        result["snapshot_source"] = str(growth_history.get("snapshot_path") or "provided_history")
        return result
    current_observed = _safe_int(current_budget.get("observed_bytes"))
    observed_growth = current_observed - _safe_int(basis["snapshot"].get("current_budget", {}).get("observed_bytes"))
    growth_per_day = int(max(0.0, observed_growth / (trend_window_seconds / 86400.0)))
    minimum_free = current_budget.get("minimum_free_bytes")
    days_to_exhaustion = None
    if growth_per_day > 0 and minimum_free is not None:
        remaining_bytes = max(0, _safe_int(minimum_free) - current_observed)
        days_to_exhaustion = remaining_bytes / growth_per_day
    return {
        "confidence": "historical_projection",
        "historical_samples_available": True,
        "history_sample_count": len(snapshots),
        "snapshot_source": str(growth_history.get("snapshot_path") or "provided_history"),
        "basis_snapshot_recorded_at_utc": basis["snapshot"].get("recorded_at_utc", ""),
        "observed_growth_bytes": observed_growth,
        "trend_window_seconds": trend_window_seconds,
        "growth_rate_bytes_per_day": growth_per_day,
        "projected_7_day_growth_bytes": growth_per_day * AUTONOMY_GROWTH_PILOT_DAYS,
        "projected_30_day_growth_bytes": growth_per_day * AUTONOMY_GROWTH_PROJECTION_DAYS,
        "days_to_budget_exhaustion": days_to_exhaustion,
    }


def _valid_growth_snapshots(raw_snapshots: Any, checked_at: datetime) -> list[dict[str, Any]]:
    if not isinstance(raw_snapshots, list):
        return []
    snapshots: list[dict[str, Any]] = []
    for item in raw_snapshots:
        if not isinstance(item, Mapping):
            continue
        recorded_at = _parse_datetime(item.get("recorded_at_utc"))
        budget = item.get("current_budget")
        if recorded_at is None or not isinstance(budget, Mapping):
            continue
        if recorded_at >= checked_at:
            continue
        snapshots.append({"recorded_at": recorded_at, "snapshot": dict(item)})
    return sorted(snapshots, key=lambda item: item["recorded_at"])


def _growth_snapshot_path(resolved: Any) -> Path | None:
    state_root = getattr(resolved, "state_root", None)
    if state_root is None:
        return None
    return Path(state_root) / "Diagnostics" / AUTONOMY_GROWTH_SNAPSHOT_FILE_NAME


def _growth_snapshot_from_payload(health_payload: Mapping[str, Any], recorded_at: datetime) -> dict[str, Any]:
    projection = health_payload.get("growth_projection")
    current_budget = projection.get("current_budget") if isinstance(projection, Mapping) else {}
    blocker_codes = projection.get("current_blocker_codes") if isinstance(projection, Mapping) else []
    review_codes = projection.get("current_review_codes") if isinstance(projection, Mapping) else []
    return {
        "schema_version": "desktop_autonomy_growth_snapshot.v1",
        "recorded_at_utc": recorded_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "health_checked_at_utc": str(health_payload.get("checked_at_utc") or ""),
        "overall_status": str(health_payload.get("overall_status") or "unknown"),
        "current_budget": dict(current_budget or {}),
        "current_blocker_codes": list(blocker_codes) if isinstance(blocker_codes, list) else [],
        "current_review_codes": list(review_codes) if isinstance(review_codes, list) else [],
    }


def _growth_snapshot_write_result(
    *,
    snapshot_path: Path | None,
    snapshot: Mapping[str, Any],
    retained_snapshot_count: int,
    max_snapshots: int,
    wrote_snapshot: bool,
    error: str,
    lock_path: Path | None = None,
) -> dict[str, Any]:
    return growth_snapshot_write_result(
        snapshot_path=snapshot_path,
        snapshot=snapshot,
        retained_snapshot_count=retained_snapshot_count,
        max_snapshots=max_snapshots,
        wrote_snapshot=wrote_snapshot,
        error=error,
        lock_path=lock_path,
    )


def _acquire_growth_snapshot_lock(lock_path: Path) -> tuple[int | None, str]:
    return acquire_growth_snapshot_lock(lock_path, timeout_seconds=AUTONOMY_GROWTH_SNAPSHOT_LOCK_TIMEOUT_SECONDS)


def _release_growth_snapshot_lock(fd: int | None, lock_path: Path) -> None:
    release_growth_snapshot_lock(fd, lock_path)


def _bounded_snapshot_limit(max_snapshots: int | None, *, policy: AutonomyPolicy | None = None) -> int:
    return bounded_snapshot_limit(max_snapshots, policy=policy)


def _minimum_present(values: Iterable[Any]) -> int | None:
    return minimum_present(values)


def _gb_to_bytes(value: float) -> int:
    return int(value * GIB_BYTES)


def _growth_projection_next_action(blocker_codes: list[str], review_codes: list[str]) -> str:
    if blocker_codes:
        return "Resolve current autonomy blockers before using growth projection for unattended work."
    if review_codes:
        return "Review current autonomy findings before relying on growth projection for an unattended pilot."
    return "Current budgets are ready; persist at least two future health snapshots before enabling rate-based alerts."


def _external_alert_level(overall_status: str) -> str:
    if overall_status == "blocked":
        return "critical"
    if overall_status == "review":
        return "warning"
    return "none"


def _external_alert_subject(overall_status: str) -> str:
    if overall_status == "blocked":
        return "MediaPipeline autonomy health blocked"
    if overall_status == "review":
        return "MediaPipeline autonomy health needs review"
    return "MediaPipeline autonomy health ready"


def _external_alert_poll_interval(overall_status: str) -> int:
    if overall_status == "blocked":
        return 300
    if overall_status == "review":
        return 900
    return 3600


def _external_alert_dedupe_key(overall_status: str, blocker_codes: list[str], review_codes: list[str]) -> str:
    codes = blocker_codes if blocker_codes else review_codes
    code_text = ",".join(codes[:5]) if codes else "none"
    return f"{overall_status}:{len(blocker_codes)}:{len(review_codes)}:{code_text}"


def _issue_codes(issues: list[Mapping[str, Any]]) -> list[str]:
    codes: list[str] = []
    for issue in issues:
        code = str(issue.get("code") or "").strip()
        if code:
            codes.append(code)
    return codes


def _alert_issue_summary(issue: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": str(issue.get("code") or ""),
        "category": str(issue.get("category") or ""),
        "severity": str(issue.get("severity") or ""),
        "message": str(issue.get("message") or ""),
        "age_seconds": issue.get("age_seconds"),
        "next_action": str(issue.get("next_action") or ""),
    }


def _launch_gate_next_action(blockers: list[Mapping[str, Any]], review_items: list[Mapping[str, Any]]) -> str:
    if blockers:
        return str(blockers[0].get("next_action") or "Resolve blocked autonomy health before launching new work.")
    if review_items:
        return "Review non-blocking autonomy health findings before a 7-day unattended run."
    return "Autonomy health is ready for new work under the 7-day pilot gate."


def _launch_gate_recovery_action(
    blockers: list[Mapping[str, Any]],
    review_items: list[Mapping[str, Any]],
) -> dict[str, Any]:
    for issue in [*blockers, *review_items]:
        action = issue.get("recovery_action")
        if isinstance(action, Mapping):
            return dict(action)
    return {}


def _pending_publish_drain_action() -> dict[str, Any]:
    return pending_publish_drain_action()


def _pending_publish_recovery_plan_action(*, row_key: str = "") -> dict[str, Any]:
    return pending_publish_recovery_plan_action(row_key=row_key)


def _journal_archive_action(path: Path | None) -> dict[str, Any]:
    return journal_archive_action(path)


def _pending_retry_count(row: Mapping[str, Any]) -> int:
    direct = _safe_int(row.get("retry_count"), row.get("RetryCount"))
    if direct:
        return direct
    manifest_path = _path_or_none(row.get("manifest_path"))
    if manifest_path is None or not manifest_path.exists():
        return 0
    payload = _read_json_mapping(manifest_path)
    return _safe_int(payload.get("retry_count"), payload.get("RetryCount"), payload.get("pending_retry_count"))



__all__ = [
    "_category",
    "_evaluate_category",
    "_category_evaluation_error",
    "_issue",
    "_issue_status",
    "_overall_status",
    "_status_state",
    "_flatten_issue",
    "_summary_lines",
    "_external_alert_payload",
    "_growth_projection_payload",
    "_category_metrics",
    "_growth_storage_roots",
    "_growth_projection_from_history",
    "_valid_growth_snapshots",
    "_growth_snapshot_path",
    "_growth_snapshot_from_payload",
    "_growth_snapshot_write_result",
    "_acquire_growth_snapshot_lock",
    "_release_growth_snapshot_lock",
    "_bounded_snapshot_limit",
    "_minimum_present",
    "_gb_to_bytes",
    "_growth_projection_next_action",
    "_external_alert_level",
    "_external_alert_subject",
    "_external_alert_poll_interval",
    "_external_alert_dedupe_key",
    "_issue_codes",
    "_alert_issue_summary",
    "_launch_gate_next_action",
    "_launch_gate_recovery_action",
    "_pending_publish_drain_action",
    "_pending_publish_recovery_plan_action",
    "_journal_archive_action",
    "_pending_retry_count",
]
