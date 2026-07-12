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
from mediapipeline.core.diagnostics.autonomy_health_runtime import (
    _active_liveness_evidence,
    _active_liveness_watchdog,
)

def _pending_publish_category(
    pending_publish: Mapping[str, Any] | None,
    now: datetime,
    *,
    policy: AutonomyPolicy,
) -> dict[str, Any]:
    if not isinstance(pending_publish, Mapping):
        return _category(
            "pending_publish",
            "review",
            summary_lines=["Pending publish scan was not available to autonomy health."],
            review_items=[
                _issue(
                    "autonomy_pending_scan_unavailable",
                    "pending_publish",
                    "medium",
                    "Pending publish scan was not available.",
                    next_action="Refresh Pending Publish diagnostics before starting unattended work.",
                    recovery_action=_pending_publish_recovery_plan_action(),
                )
            ],
        )
    rows = [row for row in pending_publish.get("rows", []) if isinstance(row, Mapping)]
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    total_bytes = _safe_int(pending_publish.get("total_bytes"))
    error = str(pending_publish.get("error") or "").strip()
    if error:
        issue = _issue(
            "autonomy_pending_scan_error",
            "pending_publish",
            "critical",
            f"Pending publish could not be scanned: {error}",
            next_action="Fix PendingServerPush readability before launching new work.",
            recovery_action=_pending_publish_recovery_plan_action(),
        )
        if "not resolved" in error.casefold() and not rows:
            issue["severity"] = "medium"
            review_items.append(issue)
        else:
            blockers.append(
                issue
            )
    if total_bytes >= policy.pending_total_block_bytes:
        blockers.append(
            _issue(
                "autonomy_pending_bytes_over_budget",
                "pending_publish",
                "high",
                f"Pending publish parked bytes exceed the blocked budget ({total_bytes} bytes).",
                next_action=(
                    "Publish the parked outputs, or review the ones that are not ready, "
                    "before starting more queue work."
                ),
                recovery_action=_pending_publish_drain_action(),
            )
        )
    elif total_bytes >= policy.pending_total_review_bytes:
        review_items.append(
            _issue(
                "autonomy_pending_bytes_review",
                "pending_publish",
                "medium",
                f"Pending publish parked bytes exceed the review budget ({total_bytes} bytes).",
                next_action="Review parked output growth before a 7-day unattended run.",
                recovery_action=_pending_publish_recovery_plan_action(),
            )
        )
    oldest_age = 0
    for row in rows:
        row_error = str(row.get("error") or "").strip()
        evidence_path = str(row.get("manifest_path") or row.get("path") or "")
        age_seconds = _row_age_seconds(row, now)
        oldest_age = max(oldest_age, int(age_seconds or 0))
        retry_count = _pending_retry_count(row)
        if row_error:
            issue = _issue(
                "autonomy_pending_manifest_untrusted",
                "pending_publish",
                "critical",
                _pending_publish_untrusted_message(row, row_error, evidence_path),
                evidence_path=evidence_path,
                age_seconds=age_seconds,
                next_action=_pending_publish_untrusted_next_action(),
                recovery_action=_pending_publish_recovery_plan_action(row_key=str(row.get("row_key") or "")),
            )
            issue.update(_pending_publish_untrusted_issue_fields(row))
            blockers.append(issue)
        if retry_count >= policy.pending_retry_block_count:
            blockers.append(
                _issue(
                    "autonomy_pending_retry_exhausted",
                    "pending_publish",
                    "high",
                    f"Pending publish retry count is {retry_count}, at or above the unattended gate.",
                    evidence_path=evidence_path,
                    age_seconds=age_seconds,
                    next_action="Dead-letter or manually review this parked output before starting more queue work.",
                    recovery_action=_pending_publish_recovery_plan_action(row_key=str(row.get("row_key") or "")),
                )
            )
        if age_seconds is not None and age_seconds >= policy.pending_block_seconds:
            blockers.append(
                _issue(
                    "autonomy_pending_oldest_blocked",
                    "pending_publish",
                    "high",
                    "Pending publish item has been parked for at least 72 hours.",
                    evidence_path=evidence_path,
                    age_seconds=age_seconds,
                    next_action=(
                        "Publish the old parked output, or review it if it is not ready, "
                        "before starting more queue work."
                    ),
                    recovery_action=_pending_publish_drain_action(),
                )
            )
        elif age_seconds is not None and age_seconds >= policy.pending_review_seconds:
            review_items.append(
                _issue(
                    "autonomy_pending_oldest_review",
                    "pending_publish",
                    "medium",
                    "Pending publish item has been parked for at least 24 hours.",
                    evidence_path=evidence_path,
                    age_seconds=age_seconds,
                    next_action="Review Pending Publish before the unattended pilot continues.",
                    recovery_action=_pending_publish_recovery_plan_action(row_key=str(row.get("row_key") or "")),
                )
            )
    inventory = pending_publish.get("file_inventory")
    if isinstance(inventory, Mapping) and _safe_int(inventory.get("orphan_payload_count")) > 0:
        review_items.append(
            _issue(
                "autonomy_pending_orphan_payloads",
                "pending_publish",
                "medium",
                "Pending publish contains unreferenced payload-like file(s).",
                evidence_path=str(inventory.get("pending_root") or ""),
                next_action="Inspect unreferenced payloads before cleanup, rerun, or drain.",
                recovery_action=_pending_publish_recovery_plan_action(),
            )
        )
    return _category(
        "pending_publish",
        _issue_status(blockers, review_items),
        metrics={
            "manifest_count": _safe_int(pending_publish.get("count")),
            "row_count": len(rows),
            "total_bytes": total_bytes,
            "oldest_age_seconds": oldest_age,
            "health_count": _safe_int(pending_publish.get("health_count")),
        },
        summary_lines=[
            f"Pending rows: {len(rows)}; bytes={total_bytes}; oldest_age_seconds={oldest_age}.",
            "Blocked rows keep files parked; this health check does not drain, delete, repair, or rerun.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _pending_publish_untrusted_message(row: Mapping[str, Any], row_error: str, evidence_path: str) -> str:
    context = _pending_publish_untrusted_context(row, evidence_path)
    suffix = f" Evidence: {context}." if context else ""
    return f"Pending Publish manifest is not trusted: {row_error}{suffix}"


def _pending_publish_untrusted_next_action() -> str:
    return (
        "Open Pending Publish, select the blocked row, then run Recovery Plan or Repair Manifest dry-run. "
        "Apply only a backend-authored repair candidate that validates; if none is available, inspect "
        "Diagnostics > Pending Publish and docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md for "
        "pending_push_manifest.v1 required fields. Keep the file parked and do not rerun or drain blindly."
    )


def _pending_publish_untrusted_context(row: Mapping[str, Any], evidence_path: str) -> str:
    fields = {
        "manifest": evidence_path,
        "row_key": row.get("row_key"),
        "state": row.get("state"),
        "diagnostic_status": row.get("diagnostic_status"),
        "local_file": row.get("local_file"),
        "server_out": row.get("server_out"),
    }
    return "; ".join(
        f"{key}={str(value).strip()}"
        for key, value in fields.items()
        if str(value or "").strip()
    )


def _pending_publish_untrusted_issue_fields(row: Mapping[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key in ("row_key", "state", "diagnostic_status", "local_file", "server_out", "source_path"):
        text = str(row.get(key) or "").strip()
        if text:
            fields[key] = text
    return fields


def _failures_category(findings: list[dict[str, Any]], *, policy: AutonomyPolicy) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    operator_required = [item for item in findings if item["operator_required"]]
    infrastructure = [item for item in findings if item["infrastructure"]]
    if len(operator_required) > policy.failure_operator_required_block_count:
        blockers.append(
            _issue(
                "autonomy_failure_operator_required_count",
                "failures",
                "high",
                f"{len(operator_required)} operator-required failure artifact(s) remain unresolved.",
                next_action="Clear, classify, or resolve old operator-required failures before unattended launch.",
            )
        )
    old_operator_required = [
        item for item in operator_required if item.get("age_seconds") is not None and item["age_seconds"] >= policy.failure_operator_required_block_seconds
    ]
    for item in old_operator_required[:3]:
        blockers.append(
            _issue(
                "autonomy_failure_operator_required_old",
                "failures",
                "high",
                "Operator-required failure is older than 72 hours.",
                evidence_path=str(item.get("path") or ""),
                age_seconds=item.get("age_seconds"),
                next_action="Review the failure artifact and clear it only through backend-owned recovery.",
            )
        )
    if len(infrastructure) >= policy.failure_infrastructure_block_count:
        blockers.append(
            _issue(
                "autonomy_failure_infrastructure_repeated",
                "failures",
                "high",
                f"{len(infrastructure)} infrastructure-like failure artifact(s) are present.",
                next_action="Resolve repeated network/share/disk/copy/publish failures before unattended launch.",
            )
        )
    if findings and not blockers:
        review_items.append(
            _issue(
                "autonomy_failure_artifacts_present",
                "failures",
                "medium",
                f"{len(findings)} failure artifact(s) are present.",
                next_action="Review failure artifacts before a 7-day unattended run.",
            )
        )
    return _category(
        "failures",
        _issue_status(blockers, review_items),
        metrics={
            "artifact_count": len(findings),
            "operator_required_count": len(operator_required),
            "infrastructure_count": len(infrastructure),
        },
        summary_lines=[
            f"Failure artifacts: {len(findings)}; operator_required={len(operator_required)}; infrastructure={len(infrastructure)}.",
            "Failure health is read-only and uses active failure markers; historical round reports are not launch warnings.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _workers_category(
    resolved: Any,
    now: datetime,
    *,
    psutil_module: Any = None,
    policy: AutonomyPolicy,
) -> dict[str, Any]:
    active_dir = resolved.active_jobs_path or (resolved.state_root / "ActiveJobs" if resolved.state_root else None)
    watchdog_records: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    active_count = 0
    malformed_count = 0
    stale_count = 0
    if not active_dir or not active_dir.exists():
        return _category(
            "workers",
            "ready",
            metrics={
                "active_count": 0,
                "malformed_count": 0,
                "active_read_first_count": 0,
                "active_jobs_ignored_count": 0,
                "ambiguous_read_first": False,
                "active_liveness_watchdog": _active_liveness_watchdog([], policy=policy),
            },
            summary_lines=["No ActiveJobs folder is present yet, or it contains no active job evidence."],
        )
    for path in _iter_files(active_dir, "*.json", limit=policy.scan_limit):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            malformed_count += 1
            watchdog_records.append(
                {
                    "path": str(path),
                    "status": "passive_malformed",
                    "read_error": str(exc),
                    "blocking_disabled": True,
                }
            )
            continue
        if not isinstance(payload, Mapping):
            malformed_count += 1
            watchdog_records.append(
                {
                    "path": str(path),
                    "status": "passive_invalid_shape",
                    "blocking_disabled": True,
                }
            )
            continue
        status = str(payload.get("status") or "").casefold()
        if status not in {"launching", "active"}:
            continue
        if psutil_module is not None and _active_job_definitely_dead(payload, psutil_module):
            continue
        active_count += 1
        evidence = _active_liveness_evidence(resolved, payload, path, now, policy=policy)
        watchdog_records.append(evidence)
        age_seconds = evidence.get("latest_evidence_age_seconds")
        evidence["blocking_disabled"] = True
        evidence["ambiguous_read_first"] = False
        evidence["status"] = (
            "passive_stale"
            if age_seconds is not None and age_seconds >= _safe_int(evidence.get("block_after_seconds"))
            else "passive_active"
        )
        if evidence["status"] == "passive_stale":
            stale_count += 1
    if malformed_count:
        review_items.append(
            _issue(
                "autonomy_active_jobs_malformed",
                "workers",
                "medium",
                f"{malformed_count} ActiveJobs record(s) could not be read as trusted liveness evidence.",
                evidence_path=str(active_dir),
                next_action="Inspect malformed ActiveJobs evidence; it remains non-blocking but can hide stale process state.",
            )
        )
    if stale_count:
        review_items.append(
            _issue(
                "autonomy_active_jobs_passive_stale",
                "workers",
                "medium",
                f"{stale_count} ActiveJobs record(s) have stale passive liveness evidence.",
                evidence_path=str(active_dir),
                next_action="Use backend-owned active-work and close-readiness controls as authority before unattended launch.",
            )
        )
    return _category(
        "workers",
        _issue_status([], review_items),
        metrics={
            "active_count": active_count,
            "malformed_count": malformed_count,
            "stale_count": stale_count,
            "active_read_first_count": 0,
            "active_jobs_ignored_count": 0,
            "ambiguous_read_first": False,
            "active_liveness_watchdog": _active_liveness_watchdog(watchdog_records, policy=policy),
        },
        summary_lines=[
            f"Active worker records: {active_count}; malformed records: {malformed_count}.",
            "ActiveJobs evidence is passive and does not block launch, Shutdown Readiness, or autonomy health; stale or malformed records are review evidence only.",
        ],
        review_items=review_items,
    )
