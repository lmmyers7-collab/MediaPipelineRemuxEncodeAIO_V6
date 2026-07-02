from __future__ import annotations

from dataclasses import replace
from datetime import datetime, UTC
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
from mediapipeline.core.diagnostics.autonomy_policy import (
    AutonomyPolicy,
    autonomy_policy_from_resolved,
)
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

AUTONOMY_HEALTH_SCHEMA_VERSION = "desktop_autonomy_health.v1"

PENDING_REVIEW_SECONDS = 24 * 60 * 60
PENDING_BLOCK_SECONDS = 72 * 60 * 60
PENDING_RETRY_BLOCK_COUNT = PENDING_PUSH_RETRY_LIMIT
PENDING_TOTAL_REVIEW_BYTES = 100 * 1024**3
PENDING_TOTAL_BLOCK_BYTES = 250 * 1024**3

FAILURE_OPERATOR_REQUIRED_BLOCK_SECONDS = 72 * 60 * 60
FAILURE_OPERATOR_REQUIRED_BLOCK_COUNT = 10
FAILURE_INFRASTRUCTURE_BLOCK_COUNT = 3
FAILURE_INFRASTRUCTURE_TEXT_KEYS = {
    "category",
    "classification",
    "error",
    "error_code",
    "message",
    "operation",
    "operator_action",
    "reason",
    "stage",
    "suggested_action",
    "tool",
}

ACTIVE_JOB_TIMEOUT_GRACE_SECONDS = 15 * 60
ACTIVE_JOB_NO_TIMEOUT_BLOCK_SECONDS = 30 * 60

DEFAULT_STORAGE_MIN_FREE_GB = 100.0
STATE_FILE_REVIEW_BYTES = 100 * 1024**2
STATE_FILE_BLOCK_BYTES = 500 * 1024**2
AUTONOMY_SCAN_LIMIT = 500
AUTONOMY_GROWTH_PILOT_DAYS = 7
AUTONOMY_GROWTH_PROJECTION_DAYS = 30
AUTONOMY_GROWTH_REQUIRED_SNAPSHOTS = 2
AUTONOMY_GROWTH_SNAPSHOT_MAX_COUNT = 64
AUTONOMY_GROWTH_SNAPSHOT_FILE_NAME = "autonomy_growth_snapshots.jsonl"
AUTONOMY_GROWTH_SNAPSHOT_LOCK_TIMEOUT_SECONDS = 5.0
GIB_BYTES = 1024**3

AUTONOMY_CATEGORY_LABELS: dict[str, str] = {
    "pending_publish": "Pending publish",
    "failures": "Failure review",
    "workers": "Workers",
    "runtime_health": "Runtime health counters",
    "disk_state": "Disk and state growth",
    "path_health": "Configured path health",
    "journals": "Journals and manifests",
    "publish_recency": "Publish recency",
    "subtitles_ocr": "Subtitle and OCR review",
    "audio_policy_reviews": "Audio policy review",
}


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
                next_action="Drain or review parked outputs before launching new work.",
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
                    next_action="Drain or review old parked output before launching new work.",
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


def _runtime_health_category(runtime_reliability: Mapping[str, Any], *, policy: AutonomyPolicy) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    continuous_round_state = runtime_reliability.get("continuous_round_state")
    if isinstance(continuous_round_state, Mapping):
        consecutive = _safe_int(continuous_round_state.get("consecutive_unexpected_round_failures"))
        limit = _safe_int(continuous_round_state.get("block_limit"))
        if bool(continuous_round_state.get("blocked")):
            blockers.append(
                _issue(
                    "autonomy_round_failures_blocked",
                    "runtime_health",
                    "high",
                    f"Continuous pipeline round failures reached the block threshold: consecutive={consecutive}; limit={limit}.",
                    next_action="Inspect the latest pipeline_round_unexpected_failure events before starting or trusting unattended work.",
                )
            )
    control_flags = runtime_reliability.get("control_flags")
    if isinstance(control_flags, Mapping):
        pause_age = _safe_int(control_flags.get("pause_age_seconds"))
        pause_review = _safe_int(control_flags.get("pause_review_seconds"))
        pause_block = _safe_int(control_flags.get("pause_block_seconds"))
        if bool(control_flags.get("pause_flag_present")) and pause_age > 0:
            issue = _issue(
                "autonomy_pause_flag_stale",
                "runtime_health",
                "medium" if pause_age < pause_block else "high",
                f"Pipeline pause flag is present; age_seconds={pause_age}.",
                evidence_path=str(control_flags.get("pause_flag_path") or ""),
                next_action="Confirm whether the operator pause is intentional before unattended operation.",
            )
            if pause_age >= pause_block:
                blockers.append(issue)
            elif pause_age >= pause_review:
                review_items.append(issue)
    pending_backpressure = runtime_reliability.get("pending_publish_backpressure")
    if isinstance(pending_backpressure, Mapping) and bool(pending_backpressure.get("blocked")):
        blockers.append(
            _issue(
                "autonomy_pending_backlog_blocked",
                "runtime_health",
                "high",
                f"Pending publish backpressure is blocking new work: {pending_backpressure.get('block_reason') or 'threshold'}.",
                evidence_path=str(pending_backpressure.get("path") or ""),
                next_action="Use backend-owned Pending Publish diagnostics/recovery before adding more unattended work.",
            )
        )
    worker_slots = runtime_reliability.get("worker_slots")
    if isinstance(worker_slots, Mapping):
        stale_heartbeats = _safe_int(worker_slots.get("stale_heartbeat_count"))
        if stale_heartbeats > 0:
            blockers.append(
                _issue(
                    "autonomy_worker_slot_stale",
                    "runtime_health",
                    "high",
                    f"Local worker heartbeat evidence is stale for {stale_heartbeats} slot(s).",
                    evidence_path=str(worker_slots.get("workers_root") or ""),
                    next_action="Let backend lifecycle cleanup reconcile stale local worker slots before starting more unattended work.",
                )
            )
    progress = runtime_reliability.get("progress_persistence")
    if isinstance(progress, Mapping):
        progress_healthy = bool(progress.get("healthy", True))
        progress_failures = _safe_int(progress.get("write_failures"))
        if not progress_healthy or progress_failures > 0:
            blockers.append(
                _issue(
                    "autonomy_progress_persistence_unhealthy",
                    "runtime_health",
                    "high",
                    f"Progress persistence is unhealthy; write_failures={progress_failures}.",
                    evidence_path=str(progress.get("path") or ""),
                    next_action="Fix progress-state persistence before launching unattended work; progress writes are the stop reason evidence.",
                )
            )
    round_failures = runtime_reliability.get("round_failures")
    if isinstance(round_failures, Mapping):
        round_failure_count = _safe_int(round_failures.get("round_failure_count"))
        unexpected_item_count = _safe_int(round_failures.get("unexpected_queue_entry_failures"))
        unexpected_round_count = _safe_int(round_failures.get("unexpected_round_failures"))
        if round_failure_count > 0 or unexpected_item_count > 0 or unexpected_round_count > 0:
            review_items.append(
                _issue(
                    "autonomy_runtime_round_failures_present",
                    "runtime_health",
                    "medium",
                    f"Runtime failure counters are nonzero: round={round_failure_count}; item={unexpected_item_count}; loop={unexpected_round_count}.",
                    next_action="Review the latest failure markers and event log before trusting a long unattended run.",
                )
            )
    native_processes = runtime_reliability.get("native_processes")
    if isinstance(native_processes, Mapping):
        abort_count = _safe_int(native_processes.get("native_no_progress_abort_count"))
        if abort_count > 0:
            review_items.append(
                _issue(
                    "autonomy_native_no_progress_aborts_present",
                    "runtime_health",
                    "medium",
                    f"Native no-progress watchdog aborts recorded: {abort_count}.",
                    next_action="Inspect FFmpeg/MKVToolNix no-progress abort evidence before starting more unattended work.",
                )
            )
    worker_reports = runtime_reliability.get("worker_pending_reports")
    if isinstance(worker_reports, Mapping):
        pending_reports = _safe_int(worker_reports.get("pending_report_count"))
        if pending_reports > 0:
            review_items.append(
                _issue(
                    "autonomy_worker_pending_done_reports_present",
                    "runtime_health",
                    "medium",
                    f"Worker pending done report evidence remains queued or under review: {pending_reports}.",
                    evidence_path=str(worker_reports.get("state_dir") or ""),
                    next_action="Let backend worker recovery deliver or quarantine pending done reports before trusting new claims.",
                )
            )
    heartbeat_failure = runtime_reliability.get("worker_heartbeat_failure")
    if isinstance(heartbeat_failure, Mapping) and bool(heartbeat_failure.get("abort_due")):
        blockers.append(
            _issue(
                "autonomy_worker_heartbeat_failure_abort_due",
                "runtime_health",
                "high",
                f"Worker heartbeat POST failures have exceeded the local abort threshold: age_seconds={heartbeat_failure.get('age_seconds')}.",
                next_action="Inspect worker/coordinator connectivity before starting more network work.",
            )
        )
    sqlite_mirror = runtime_reliability.get("sqlite_mirror")
    if isinstance(sqlite_mirror, Mapping):
        db_size = _safe_int(sqlite_mirror.get("db_size_bytes"))
        wal_size = _safe_int(sqlite_mirror.get("wal_size_bytes"))
        if db_size > policy.state_file_block_bytes or wal_size > policy.state_file_block_bytes:
            blockers.append(
                _issue(
                    "autonomy_sqlite_mirror_blocked_size",
                    "runtime_health",
                    "high",
                    f"SQLite mirror DB/WAL exceeds the blocked size budget: db={db_size}; wal={wal_size}.",
                    evidence_path=str(sqlite_mirror.get("path") or ""),
                    next_action="Run backend-owned SQLite mirror maintenance or archive planning before unattended launch.",
                )
            )
        elif db_size > policy.state_file_review_bytes or wal_size > policy.state_file_review_bytes:
            review_items.append(
                _issue(
                    "autonomy_sqlite_mirror_review_size",
                    "runtime_health",
                    "medium",
                    f"SQLite mirror DB/WAL exceeds the review size budget: db={db_size}; wal={wal_size}.",
                    evidence_path=str(sqlite_mirror.get("path") or ""),
                    next_action="Review SQLite mirror maintenance posture before a long unattended run.",
                )
            )
    state_db = runtime_reliability.get("state_db")
    if isinstance(state_db, Mapping):
        wal_size = _safe_int(state_db.get("wal_size_bytes"))
        wal_review = _safe_int(state_db.get("wal_review_bytes"))
        last_maintenance = state_db.get("last_maintenance")
        maintenance_error = ""
        if isinstance(last_maintenance, Mapping):
            maintenance_error = str(last_maintenance.get("error") or "")
        if wal_review > 0 and wal_size >= wal_review:
            review_items.append(
                _issue(
                    "autonomy_state_db_maintenance_overdue",
                    "runtime_health",
                    "medium",
                    f"SQLite mirror WAL is at or above the review threshold: wal={wal_size}; threshold={wal_review}.",
                    evidence_path=str(state_db.get("maintenance_path") or state_db.get("path") or ""),
                    next_action="Confirm backend-owned mirror maintenance is running; JSON files remain authoritative.",
                )
            )
        if maintenance_error:
            review_items.append(
                _issue(
                    "autonomy_state_db_maintenance_overdue",
                    "runtime_health",
                    "medium",
                    f"Last SQLite mirror maintenance failed: {maintenance_error}.",
                    evidence_path=str(state_db.get("maintenance_path") or state_db.get("path") or ""),
                    next_action="Inspect maintenance diagnostics; do not delete authoritative JSON state files.",
                )
            )
    metrics = _runtime_health_metrics(runtime_reliability)
    return _category(
        "runtime_health",
        _issue_status(blockers, review_items),
        metrics=metrics,
        summary_lines=[
            (
                "Runtime counters: "
                f"current_file_age_seconds={metrics['current_file_age_seconds']}; "
                f"round_failures={metrics['round_failure_count']}; "
                f"native_no_progress_aborts={metrics['native_no_progress_abort_count']}."
            ),
            (
                "Backlog counters: "
                f"pending_publish={metrics['pending_publish_backlog_count']}; "
                f"worker_pending_reports={metrics['worker_pending_report_count']}; "
                f"active_jobs_total={metrics['active_jobs_total_count']}; "
                f"active_jobs_blocking={metrics['active_jobs_blocking_count']}."
            ),
            (
                "State counters: "
                f"sqlite_db_bytes={metrics['sqlite_db_size_bytes']}; "
                f"sqlite_wal_bytes={metrics['sqlite_wal_size_bytes']}; "
                f"progress_persistence_healthy={metrics['progress_persistence_healthy']}."
            ),
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _runtime_health_metrics(runtime_reliability: Mapping[str, Any]) -> dict[str, Any]:
    current_file = runtime_reliability.get("current_file") if isinstance(runtime_reliability, Mapping) else {}
    round_failures = runtime_reliability.get("round_failures") if isinstance(runtime_reliability, Mapping) else {}
    native_processes = runtime_reliability.get("native_processes") if isinstance(runtime_reliability, Mapping) else {}
    pending_publish = runtime_reliability.get("pending_publish") if isinstance(runtime_reliability, Mapping) else {}
    worker_reports = runtime_reliability.get("worker_pending_reports") if isinstance(runtime_reliability, Mapping) else {}
    active_jobs = runtime_reliability.get("active_jobs") if isinstance(runtime_reliability, Mapping) else {}
    sqlite_mirror = runtime_reliability.get("sqlite_mirror") if isinstance(runtime_reliability, Mapping) else {}
    progress = runtime_reliability.get("progress_persistence") if isinstance(runtime_reliability, Mapping) else {}
    continuous_round_state = runtime_reliability.get("continuous_round_state") if isinstance(runtime_reliability, Mapping) else {}
    control_flags = runtime_reliability.get("control_flags") if isinstance(runtime_reliability, Mapping) else {}
    pending_backpressure = runtime_reliability.get("pending_publish_backpressure") if isinstance(runtime_reliability, Mapping) else {}
    worker_slots = runtime_reliability.get("worker_slots") if isinstance(runtime_reliability, Mapping) else {}
    state_db = runtime_reliability.get("state_db") if isinstance(runtime_reliability, Mapping) else {}
    heartbeat_failure = runtime_reliability.get("worker_heartbeat_failure") if isinstance(runtime_reliability, Mapping) else {}
    coordinator_state = runtime_reliability.get("coordinator_state") if isinstance(runtime_reliability, Mapping) else {}
    debug_log = runtime_reliability.get("debug_log") if isinstance(runtime_reliability, Mapping) else {}
    return {
        "current_file_age_seconds": None if not isinstance(current_file, Mapping) else current_file.get("age_seconds"),
        "round_failure_count": _safe_int(round_failures.get("round_failure_count")) if isinstance(round_failures, Mapping) else 0,
        "unexpected_queue_entry_failures": _safe_int(round_failures.get("unexpected_queue_entry_failures")) if isinstance(round_failures, Mapping) else 0,
        "unexpected_round_failures": _safe_int(round_failures.get("unexpected_round_failures")) if isinstance(round_failures, Mapping) else 0,
        "consecutive_unexpected_round_failures": _safe_int(continuous_round_state.get("consecutive_unexpected_round_failures")) if isinstance(continuous_round_state, Mapping) else 0,
        "continuous_round_blocked": bool(continuous_round_state.get("blocked")) if isinstance(continuous_round_state, Mapping) else False,
        "pause_flag_present": bool(control_flags.get("pause_flag_present")) if isinstance(control_flags, Mapping) else False,
        "pause_age_seconds": control_flags.get("pause_age_seconds") if isinstance(control_flags, Mapping) else None,
        "native_no_progress_abort_count": _safe_int(native_processes.get("native_no_progress_abort_count")) if isinstance(native_processes, Mapping) else 0,
        "pending_publish_backlog_count": _safe_int(pending_publish.get("backlog_count")) if isinstance(pending_publish, Mapping) else 0,
        "pending_publish_health_count": _safe_int(pending_publish.get("health_count")) if isinstance(pending_publish, Mapping) else 0,
        "pending_publish_oldest_age_seconds": pending_backpressure.get("oldest_age_seconds") if isinstance(pending_backpressure, Mapping) else None,
        "pending_publish_backpressure_blocked": bool(pending_backpressure.get("blocked")) if isinstance(pending_backpressure, Mapping) else False,
        "pending_publish_backpressure_reason": str(pending_backpressure.get("block_reason") or "") if isinstance(pending_backpressure, Mapping) else "",
        "worker_pending_report_count": _safe_int(worker_reports.get("pending_report_count")) if isinstance(worker_reports, Mapping) else 0,
        "worker_pending_report_oldest_age_seconds": worker_reports.get("oldest_pending_report_age_seconds") if isinstance(worker_reports, Mapping) else None,
        "worker_heartbeat_failure_age_seconds": heartbeat_failure.get("age_seconds") if isinstance(heartbeat_failure, Mapping) else None,
        "worker_heartbeat_failure_abort_threshold_seconds": _safe_int(heartbeat_failure.get("abort_threshold_seconds")) if isinstance(heartbeat_failure, Mapping) else 0,
        "worker_heartbeat_failure_abort_due": bool(heartbeat_failure.get("abort_due")) if isinstance(heartbeat_failure, Mapping) else False,
        "worker_slot_active_child_count": _safe_int(worker_slots.get("active_child_count")) if isinstance(worker_slots, Mapping) else 0,
        "worker_slot_stale_heartbeat_count": _safe_int(worker_slots.get("stale_heartbeat_count")) if isinstance(worker_slots, Mapping) else 0,
        "active_jobs_total_count": _safe_int(active_jobs.get("total_count")) if isinstance(active_jobs, Mapping) else 0,
        "active_jobs_blocking_count": _safe_int(active_jobs.get("blocking_count")) if isinstance(active_jobs, Mapping) else 0,
        "active_jobs_ambiguous_count": _safe_int(active_jobs.get("ambiguous_count")) if isinstance(active_jobs, Mapping) else 0,
        "active_jobs_ambiguous_read_first": bool(active_jobs.get("ambiguous_read_first")) if isinstance(active_jobs, Mapping) else False,
        "sqlite_db_size_bytes": _safe_int(sqlite_mirror.get("db_size_bytes")) if isinstance(sqlite_mirror, Mapping) else 0,
        "sqlite_wal_size_bytes": _safe_int(sqlite_mirror.get("wal_size_bytes")) if isinstance(sqlite_mirror, Mapping) else 0,
        "sqlite_completed_jobs_count": sqlite_mirror.get("completed_jobs_count") if isinstance(sqlite_mirror, Mapping) else None,
        "sqlite_completed_jobs_max_rows": _safe_int(sqlite_mirror.get("completed_jobs_max_rows")) if isinstance(sqlite_mirror, Mapping) else 0,
        "sqlite_completed_jobs_count_error": str(sqlite_mirror.get("completed_jobs_count_error") or "") if isinstance(sqlite_mirror, Mapping) else "",
        "state_db_wal_review_bytes": _safe_int(state_db.get("wal_review_bytes")) if isinstance(state_db, Mapping) else 0,
        "sqlite_write_failures": sqlite_mirror.get("write_failures") if isinstance(sqlite_mirror, Mapping) else None,
        "progress_persistence_healthy": bool(progress.get("healthy", True)) if isinstance(progress, Mapping) else True,
        "progress_write_failures": _safe_int(progress.get("write_failures")) if isinstance(progress, Mapping) else 0,
        "coordinator_reclaimed_source_quarantine_count": _safe_int(coordinator_state.get("reclaimed_source_quarantine_count")) if isinstance(coordinator_state, Mapping) else 0,
        "coordinator_reclaimed_source_quarantine_oldest_age_seconds": coordinator_state.get("reclaimed_source_quarantine_oldest_age_seconds") if isinstance(coordinator_state, Mapping) else None,
        "coordinator_pending_done_report_count": _safe_int(coordinator_state.get("late_terminal_report_count")) if isinstance(coordinator_state, Mapping) else 0,
        "coordinator_failure_ledger_count": _safe_int(coordinator_state.get("failure_ledger_count")) if isinstance(coordinator_state, Mapping) else 0,
        "coordinator_failure_ledger_max_entries": _safe_int(coordinator_state.get("failure_ledger_max_entries")) if isinstance(coordinator_state, Mapping) else 0,
        "debug_log_size_bytes": _safe_int(debug_log.get("size_bytes")) if isinstance(debug_log, Mapping) else 0,
        "debug_log_max_bytes": _safe_int(debug_log.get("max_bytes")) if isinstance(debug_log, Mapping) else 0,
        "debug_log_rotation_state": str(debug_log.get("rotation_state") or "") if isinstance(debug_log, Mapping) else "",
    }


def _active_liveness_watchdog(records: list[dict[str, Any]], *, policy: AutonomyPolicy) -> dict[str, Any]:
    retained = records[: policy.watchdog_record_limit]
    return {
        "schema_version": "desktop_active_liveness_watchdog.v1",
        "effect": "none",
        "read_only": True,
        "would_kill_active_processes": False,
        "would_rewrite_active_jobs": False,
        "policy": (
            "Passive ActiveJobs evidence only. ActiveJobs records do not block launch, Shutdown Readiness, "
            "or autonomy health."
        ),
        "native_timeout_grace_seconds": policy.active_job_timeout_grace_seconds,
        "no_native_timeout_block_after_seconds": policy.active_job_no_timeout_block_seconds,
        "record_count": len(retained),
        "record_total_count": len(records),
        "records_truncated": len(records) > len(retained),
        "record_limit": policy.watchdog_record_limit,
        "records": retained,
    }


def _active_liveness_evidence(
    resolved: Any,
    payload: Mapping[str, Any],
    active_job_path: Path,
    now: datetime,
    *,
    policy: AutonomyPolicy,
) -> dict[str, Any]:
    heartbeat_age = _age_seconds(_first_text(payload, "last_update", "launched_at"), active_job_path, now)
    evidence_candidates = [
        {
            "source": "active_job",
            "path": str(active_job_path),
            "age_seconds": heartbeat_age,
        }
    ]
    progress = _progress_liveness_evidence(resolved.progress_file, now)
    if progress is not None:
        evidence_candidates.append(progress)
    for source, path in (("event_file", resolved.event_file), ("log_file", resolved.log_file)):
        file_evidence = _file_mtime_liveness_evidence(source, path, now)
        if file_evidence is not None:
            evidence_candidates.append(file_evidence)
    latest = _latest_liveness_candidate(evidence_candidates)
    native_timeout_source, native_timeout_seconds = _native_timeout_for_active_job(payload, resolved.config_data)
    block_after = (
        native_timeout_seconds + policy.active_job_timeout_grace_seconds
        if native_timeout_seconds is not None
        else policy.active_job_no_timeout_block_seconds
    )
    return {
        "status": "ready",
        "active_job_path": str(active_job_path),
        "pid": payload.get("pid"),
        "job_kind": str(payload.get("job_kind") or ""),
        "mode": str(payload.get("mode") or ""),
        "active_status": str(payload.get("status") or ""),
        "heartbeat_age_seconds": heartbeat_age,
        "latest_evidence_source": str(latest.get("source") or ""),
        "latest_evidence_path": str(latest.get("path") or ""),
        "latest_evidence_age_seconds": latest.get("age_seconds"),
        "native_timeout_source": native_timeout_source,
        "native_timeout_seconds": native_timeout_seconds,
        "native_timeout_grace_seconds": policy.active_job_timeout_grace_seconds,
        "block_after_seconds": block_after,
        "evidence_candidates": evidence_candidates,
    }


def _progress_liveness_evidence(path: Path | None, now: datetime) -> dict[str, Any] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    payload = _read_json_mapping(path)
    if "_read_error" in payload or "_json_root" in payload:
        return None
    status = _first_text(payload, "Status", "status", "CurrentStage", "current_stage").casefold()
    if status in {"completed", "complete", "failed", "idle", "stopped", "not_running", "not running"}:
        return None
    age_seconds = _age_seconds(
        _first_text(payload, "LastUpdate", "last_update", "updated_at", "timestamp", "Timestamp"),
        path,
        now,
    )
    return {
        "source": "progress_file",
        "path": str(path),
        "age_seconds": age_seconds,
    }


def _file_mtime_liveness_evidence(source: str, path: Path | None, now: datetime) -> dict[str, Any] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    return {
        "source": source,
        "path": str(path),
        "age_seconds": _age_seconds("", path, now),
    }


def _latest_liveness_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    with_age = [item for item in candidates if item.get("age_seconds") is not None]
    if not with_age:
        return candidates[0] if candidates else {"source": "", "path": "", "age_seconds": None}
    return min(with_age, key=lambda item: int(item.get("age_seconds") or 0))


def _native_timeout_for_active_job(payload: Mapping[str, Any], config_data: Mapping[str, Any] | None) -> tuple[str, int | None]:
    if not isinstance(config_data, Mapping):
        return "", None
    text = " ".join(
        str(payload.get(key) or "")
        for key in ("job_kind", "mode", "stage", "current_stage", "operation", "label")
    ).casefold()
    candidate_keys: list[str] = []
    if "cpu" in text and "encode" in text:
        candidate_keys.append("FFmpegCpuEncodeTimeoutSeconds")
    if "encode" in text:
        candidate_keys.append("FFmpegEncodeTimeoutSeconds")
    if "remux" in text:
        if "mkvmerge" in text:
            candidate_keys.append("MkvmergeRemuxTimeoutSeconds")
        candidate_keys.extend(["FFmpegRemuxTimeoutSeconds", "MkvmergeRemuxTimeoutSeconds"])
    if "subtitle" in text or "tx3g" in text or "ass" in text or "ssa" in text:
        candidate_keys.append("SubtitleExtractTimeoutSeconds")
    if "bdpgs" in text:
        candidate_keys.append("BdpgsOcrTimeoutSeconds")
    if "vobsub" in text:
        candidate_keys.append("VobSubOcrTimeoutSeconds")
    if "copy" in text or "publish" in text or "robocopy" in text:
        candidate_keys.append("RobocopyTimeoutSeconds")
    if "scan" in text or "audit" in text:
        candidate_keys.extend(["SourceScanTimeoutSeconds", "IndexScanTimeoutSeconds"])
    for key in candidate_keys:
        value = _safe_int(config_data.get(key))
        if value > 0:
            return key, value
    return "", None


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


def _read_json_mapping(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"_read_error": str(path)}
    return payload if isinstance(payload, Mapping) else {"_json_root": type(payload).__name__}


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


def _row_age_seconds(row: Mapping[str, Any], now: datetime) -> int | None:
    text = _first_text(row, "parked_at", "recorded_at", "last_update", "modified_at")
    path = _path_or_none(row.get("manifest_path") or row.get("path"))
    return _age_seconds(text, path, now)


def _age_seconds(text: str, path: Path | None, now: datetime) -> int | None:
    parsed = _parse_datetime(text)
    if parsed is None and path is not None:
        try:
            parsed = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        except OSError:
            return None
    if parsed is None:
        return None
    return max(0, int((now - parsed.astimezone(UTC)).total_seconds()))


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _first_text(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _path_or_none(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return Path(text)
    except TypeError:
        return None


def _safe_int(*values: Any) -> int:
    for value in values:
        try:
            if value in (None, ""):
                continue
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _safe_float(*values: Any) -> float | None:
    for value in values:
        try:
            if value in (None, ""):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _iter_files(root: Path, pattern: str = "*", *, limit: int = AUTONOMY_SCAN_LIMIT) -> list[Path]:
    return _limited_iter_files(root, pattern, limit=limit)[0]


def _limited_iter_files(root: Path, pattern: str = "*", *, limit: int = AUTONOMY_SCAN_LIMIT) -> tuple[list[Path], bool]:
    scan = limited_iter_files(root, pattern, limit=limit)
    return scan.paths, scan.truncated


def _directory_size(root: Path | None, *, limit: int = AUTONOMY_SCAN_LIMIT) -> int:
    return int(_directory_size_scan(root, limit=limit)["size_bytes"])


def _directory_size_scan(root: Path | None, *, limit: int = AUTONOMY_SCAN_LIMIT) -> dict[str, Any]:
    return directory_size_scan(root, limit=limit)


def _journal_paths(resolved: Any) -> list[Path | None]:
    return [
        resolved.event_file,
        resolved.completed_manifest_path,
        resolved.queue_snapshot_path,
        resolved.progress_file,
        resolved.log_file,
    ]


def _queue_runnable_count(path: Path | None) -> int:
    if path is None or not path.exists() or not path.is_file():
        return 0
    payload = _read_json_mapping(path)
    for key in ("runnable_count", "RunnableCount"):
        if key in payload:
            return _safe_int(payload.get(key))
    items = payload.get("items")
    if isinstance(items, list):
        return len(items)
    rows = payload.get("rows")
    if isinstance(rows, list):
        return len(rows)
    return 0


def _active_job_definitely_dead(payload: Mapping[str, Any], psutil_module: Any) -> bool:
    pid = payload.get("pid")
    try:
        process = psutil_module.Process(int(pid))
        return not (bool(process.is_running()) and process.status() != psutil_module.STATUS_ZOMBIE)
    except psutil_module.NoSuchProcess:
        return True
    except Exception:
        return False


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
