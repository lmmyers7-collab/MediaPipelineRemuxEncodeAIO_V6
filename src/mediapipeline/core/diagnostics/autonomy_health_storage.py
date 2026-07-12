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
from mediapipeline.core.diagnostics.autonomy_health_projection import *  # noqa: F403
from mediapipeline.core.diagnostics.autonomy_health_runtime import _active_liveness_watchdog

def _disk_state_category(
    resolved: Any,
    path_health: Mapping[str, Any] | None,
    *,
    policy: AutonomyPolicy,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    rows = path_health.get("rows") if isinstance(path_health, Mapping) else []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            role = str(row.get("role") or "").casefold()
            if role not in {"scratch", "output"}:
                continue
            free_gb = _safe_float(row.get("free_space_gb"), row.get("free_gb"))
            reserve_gb = _safe_float(row.get("reserve_gb"))
            threshold_gb = reserve_gb if reserve_gb and reserve_gb > 0 else policy.storage_min_free_gb
            storage_status = str(row.get("storage_status") or "").casefold()
            if storage_status == "low" or (free_gb is not None and free_gb < threshold_gb):
                blockers.append(
                    _issue(
                        "autonomy_storage_free_space_low",
                        "disk_state",
                        "critical",
                        f"{row.get('label') or row.get('key') or 'Storage root'} has insufficient free space for unattended launch.",
                        evidence_path=str(row.get("path") or ""),
                        next_action="Free space or adjust backend storage reserve settings before launching new work.",
                    )
                )
            elif storage_status == "unknown":
                review_items.append(
                    _issue(
                        "autonomy_storage_free_space_unknown",
                        "disk_state",
                        "medium",
                        f"{row.get('label') or row.get('key') or 'Storage root'} free space could not be determined.",
                        evidence_path=str(row.get("path") or ""),
                        next_action="Refresh path health and verify free space before unattended launch.",
                    )
                )
    state_scan = _directory_size_scan(resolved.state_root, limit=policy.scan_limit)
    local_scan = _directory_size_scan(resolved.local_base, limit=policy.scan_limit)
    if bool(state_scan["truncated"]) or bool(local_scan["truncated"]):
        review_items.append(
            _issue(
                "autonomy_scan_truncated",
                "disk_state",
                "medium",
                f"Autonomy file enumeration hit the scan limit of {policy.scan_limit}; size metrics are lower bounds.",
                next_action="Use the lower-bound sizes as soak telemetry only; raise the scan limit or inspect storage externally before trusting capacity projections.",
            )
        )
    stat_error_count = _safe_int(state_scan.get("stat_error_count")) + _safe_int(local_scan.get("stat_error_count"))
    if stat_error_count:
        review_items.append(
            _issue(
                "autonomy_scan_stat_errors",
                "disk_state",
                "medium",
                f"Autonomy file enumeration skipped {stat_error_count} file(s) due to stat/read errors.",
                next_action="Inspect LocalBase/State readability before relying on growth projection.",
            )
        )
    return _category(
        "disk_state",
        _issue_status(blockers, review_items),
        metrics={
            "state_root_size_bytes": state_scan["size_bytes"],
            "state_root_size_lower_bound": bool(state_scan["truncated"]),
            "state_root_scan_truncated": bool(state_scan["truncated"]),
            "state_root_scanned_file_count": state_scan["scanned_file_count"],
            "local_base_scanned_size_bytes": local_scan["size_bytes"],
            "local_base_size_lower_bound": bool(local_scan["truncated"]),
            "local_base_scan_truncated": bool(local_scan["truncated"]),
            "local_base_scanned_file_count": local_scan["scanned_file_count"],
            "state_root_scan_stat_error_count": _safe_int(state_scan.get("stat_error_count")),
            "local_base_scan_stat_error_count": _safe_int(local_scan.get("stat_error_count")),
            "autonomy_scan_limit": policy.scan_limit,
        },
        summary_lines=[
            f"State root scanned bytes: {state_scan['size_bytes']}; lower_bound={state_scan['truncated']}.",
            f"LocalBase scanned bytes: {local_scan['size_bytes']}; lower_bound={local_scan['truncated']}.",
            "No cleanup is performed by autonomy health.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _path_health_category(path_health: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(path_health, Mapping) or not path_health.get("rows"):
        return _category(
            "path_health",
            "ready",
            metrics={"row_count": 0},
            summary_lines=["No configured path health rows were available; launch-specific checks still run separately."],
        )
    operator_status = str(path_health.get("operator_status") or "unknown").casefold()
    rows = [row for row in path_health.get("rows", []) if isinstance(row, Mapping)]
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("operator_status") or row.get("status") or "").casefold()
        if status == "blocked":
            blockers.append(
                _issue(
                    "autonomy_configured_path_blocked",
                    "path_health",
                    "critical",
                    str(row.get("message") or "Configured path health is blocked."),
                    evidence_path=str(row.get("path") or ""),
                    next_action=str(row.get("safe_next_action") or "Restore configured roots before launch."),
                )
            )
        elif status in {"review", "unknown"}:
            review_items.append(
                _issue(
                    "autonomy_configured_path_review",
                    "path_health",
                    "medium",
                    str(row.get("message") or "Configured path health needs review."),
                    evidence_path=str(row.get("path") or ""),
                    next_action=str(row.get("safe_next_action") or "Review configured path health before launch."),
                )
            )
    status = "blocked" if operator_status == "blocked" else _issue_status(blockers, review_items)
    return _category(
        "path_health",
        status,
        metrics={"row_count": len(rows), "operator_status": operator_status},
        summary_lines=[
            str(path_health.get("operator_summary") or f"Configured path health: {operator_status}."),
            "Path health is read-only; no settings, files, or shares are mutated.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _journals_category(resolved: Any, *, policy: AutonomyPolicy) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    file_count = 0
    total_size = 0
    largest_file_size = 0
    for path in _journal_paths(resolved):
        if path is None or not path.exists() or not path.is_file():
            continue
        file_count += 1
        try:
            size = int(path.stat().st_size)
        except OSError as exc:
            review_items.append(
                _issue(
                    "autonomy_journal_stat_failed",
                    "journals",
                    "medium",
                    f"Could not stat journal/state file: {exc}",
                    evidence_path=str(path),
                    next_action="Inspect state file readability before unattended launch.",
                )
            )
            continue
        total_size += size
        largest_file_size = max(largest_file_size, size)
        if size > policy.state_file_block_bytes:
            blockers.append(
                _issue(
                    "autonomy_journal_file_blocked_size",
                    "journals",
                    "high",
                    f"Journal/state file is larger than the blocked budget ({size} bytes).",
                    evidence_path=str(path),
                    next_action="Archive or rotate state/log evidence with backend-approved tooling before launch.",
                    recovery_action=_journal_archive_action(path),
                )
            )
        elif size > policy.state_file_review_bytes:
            review_items.append(
                _issue(
                    "autonomy_journal_file_review_size",
                    "journals",
                    "medium",
                    f"Journal/state file is larger than the review budget ({size} bytes).",
                    evidence_path=str(path),
                    next_action="Review state/log growth before the unattended pilot.",
                    recovery_action=_journal_archive_action(path),
                )
            )
    return _category(
        "journals",
        _issue_status(blockers, review_items),
        metrics={
            "file_count": file_count,
            "total_size_bytes": total_size,
            "largest_file_size_bytes": largest_file_size,
        },
        summary_lines=[
            f"Journal/state files found: {file_count}.",
            f"Journal/state bytes found: {total_size}.",
            "This health payload is read-only; use backend-approved recovery actions to archive oversized runtime event evidence.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _publish_recency_category(resolved: Any, now: datetime, *, policy: AutonomyPolicy) -> dict[str, Any]:
    runnable_count = _queue_runnable_count(resolved.queue_snapshot_path)
    manifest = resolved.completed_manifest_path
    review_items: list[dict[str, Any]] = []
    if runnable_count > 0 and (manifest is None or not manifest.exists()):
        review_items.append(
            _issue(
                "autonomy_publish_recency_missing_manifest",
                "publish_recency",
                "medium",
                "Queue snapshot has runnable work but completed manifest is missing.",
                evidence_path=str(manifest or ""),
                next_action="Confirm whether this is a first run or a completed-manifest state issue.",
            )
        )
    elif runnable_count > 0 and manifest is not None and manifest.exists():
        age_seconds = _age_seconds("", manifest, now)
        if age_seconds is not None and age_seconds >= policy.pending_review_seconds:
            review_items.append(
                _issue(
                    "autonomy_publish_recency_stale",
                    "publish_recency",
                    "medium",
                    "Queue snapshot has runnable work and no recent completed-manifest update.",
                    evidence_path=str(manifest),
                    age_seconds=age_seconds,
                    next_action="Confirm queue liveness before unattended operation.",
                )
            )
    return _category(
        "publish_recency",
        _issue_status([], review_items),
        metrics={"queue_runnable_count": runnable_count},
        summary_lines=[
            f"Queue runnable count from snapshot: {runnable_count}.",
            "Publish recency is advisory; it does not mutate queue or completed evidence.",
        ],
        review_items=review_items,
    )


def _topic_failure_category(
    key: str,
    label: str,
    findings: list[dict[str, Any]],
    needles: tuple[str, ...],
) -> dict[str, Any]:
    matched = [item for item in findings if any(needle in item["search_text"] for needle in needles)]
    review_items: list[dict[str, Any]] = []
    if matched:
        review_items.append(
            _issue(
                f"autonomy_{key}_failure_review",
                key,
                "medium",
                f"{len(matched)} related failure artifact(s) need review.",
                evidence_path=str(matched[0].get("path") or ""),
                age_seconds=matched[0].get("age_seconds"),
                next_action=f"Review {label.lower()} evidence before unattended launch.",
            )
        )
    return _category(
        key,
        _issue_status([], review_items),
        label=label,
        metrics={"failure_count": len(matched)},
        summary_lines=[f"Related failure artifacts: {len(matched)}."],
        review_items=review_items,
    )


def _failure_findings(resolved: Any, now: datetime, *, policy: AutonomyPolicy) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    roots = [resolved.failed_markers_path]
    for root in roots:
        if root is None or not root.exists():
            continue
        for path in _iter_files(root, "*.json", limit=policy.scan_limit):
            payload = _read_json_mapping(path)
            search_text = _failure_search_text(payload, path)
            age_seconds = _age_seconds(_first_text(payload, "recorded_at", "RecordedAt", "timestamp", "Timestamp"), path, now)
            findings.append(
                {
                    "path": str(path),
                    "payload": payload,
                    "search_text": search_text,
                    "age_seconds": age_seconds,
                    "operator_required": _is_operator_required_failure(payload, search_text),
                    "infrastructure": _is_infrastructure_failure(payload),
                }
            )
    return findings[: policy.scan_limit]


def _failure_search_text(payload: Mapping[str, Any], path: Path) -> str:
    values = [path.name]
    for key, value in payload.items():
        if isinstance(value, str | int | float | bool):
            values.append(f"{key}={value}")
    return " ".join(values).casefold()


def _is_operator_required_failure(payload: Mapping[str, Any], text: str) -> bool:
    if bool(payload.get("Escalated") or payload.get("escalated")):
        return True
    return any(term in text for term in ("operator_required", "operator required", "manual_review", "manual review"))


def _is_infrastructure_failure(payload: Mapping[str, Any]) -> bool:
    text = _failure_infrastructure_text(payload)
    return any(term in text for term in ("network", "share", "smb", "disk", "space", "robocopy", "copy", "publish", "pending", "path"))


def _failure_infrastructure_text(payload: Mapping[str, Any]) -> str:
    values: list[str] = []
    for key, value in payload.items():
        if str(key).casefold() not in FAILURE_INFRASTRUCTURE_TEXT_KEYS:
            continue
        if isinstance(value, str | int | float | bool):
            values.append(str(value))
    return " ".join(values).casefold()
