from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence

from mediapipeline.core.kernel.contracts.base import ContractError
from mediapipeline.core.kernel.contracts.pending_publish import (
    PENDING_PUSH_MANIFEST_REQUIRED_ARRAY_FIELDS,
    PENDING_PUSH_MANIFEST_REQUIRED_TEXT_FIELDS,
    PENDING_PUSH_MANIFEST_SCHEMA_VERSION,
    PendingPushManifest,
)
from mediapipeline.core.storage.db import CURRENT_SCHEMA_VERSION, STATE_DB_FILENAME
from mediapipeline.core.repair_reconcile.dry_run_contract import *  # noqa: F403
from mediapipeline.core.repair_reconcile.dry_run_support import *  # noqa: F403
from mediapipeline.core.repair_reconcile.dry_run_completed import (
    completed_manifest_reconcile_dry_run, completed_sidecar_metadata_repair_dry_run,
)
from mediapipeline.core.repair_reconcile.dry_run_pending import (
    pending_manifest_repair_dry_run, pending_orphan_payload_reconcile_dry_run,
)

def _startup_finding(
    code: str,
    category: str,
    status: str,
    severity: str,
    message: str,
    *,
    evidence_path: str = "",
    next_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "category": category,
        "status": status,
        "severity": severity,
        "message": message,
        "evidence_path": evidence_path,
        "next_action": next_action,
    }


def _startup_category(
    key: str,
    label: str,
    *,
    findings: list[dict[str, Any]] | None = None,
    metrics: Mapping[str, Any] | None = None,
    summary_lines: list[str] | None = None,
) -> dict[str, Any]:
    rows = list(findings or [])
    status = _startup_status(rows)
    return {
        "key": key,
        "label": label,
        "status": status,
        "metrics": dict(metrics or {}),
        "findings": rows,
        "summary_lines": list(summary_lines or []),
    }


def _startup_status(findings: Sequence[Mapping[str, Any]]) -> str:
    statuses = {str(row.get("status") or "").casefold() for row in findings}
    if "blocked" in statuses:
        return "blocked"
    if "review" in statuses:
        return "review"
    return "ready"


def _startup_overall_status(categories: Mapping[str, Mapping[str, Any]]) -> str:
    statuses = {str(category.get("status") or "").casefold() for category in categories.values()}
    if "blocked" in statuses:
        return "blocked"
    if "review" in statuses:
        return "review"
    return "ready"


def _startup_pending_manifest_category(pending_publish: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(pending_publish, Mapping):
        finding = _startup_finding(
            "startup_pending_scan_unavailable",
            "pending_manifests",
            "review",
            "medium",
            "Pending publish scan was unavailable during startup reconciliation dry-run.",
            next_action="Refresh Pending Publish diagnostics before trusting restart state.",
        )
        return _startup_category("pending_manifests", "Pending manifests", findings=[finding])
    rows = [row for row in pending_publish.get("rows") or [] if isinstance(row, Mapping)]
    findings: list[dict[str, Any]] = []
    scan_error = str(pending_publish.get("error") or "").strip()
    if scan_error:
        findings.append(
            _startup_finding(
                "startup_pending_scan_error",
                "pending_manifests",
                "blocked",
                "high",
                f"Pending publish scan failed: {scan_error}",
                evidence_path=str(pending_publish.get("source") or ""),
                next_action="Repair pending-publish state readability before any startup repair or launch.",
            )
        )
    blocked_statuses = {"unreadable_manifest", "invalid_manifest", "duplicate_target"}
    review_statuses = {"retry_exhausted", "missing_payload", "row_error"}
    blocked_count = 0
    review_count = 0
    for row in rows:
        status = str(row.get("diagnostic_status") or row.get("status") or "").strip().casefold()
        evidence_path = str(row.get("manifest_path") or row.get("path") or "")
        if status in blocked_statuses:
            blocked_count += 1
            findings.append(
                _startup_finding(
                    "startup_pending_manifest_untrusted",
                    "pending_manifests",
                    "blocked",
                    "high",
                    f"Pending manifest is not trusted for automated repair: {status}.",
                    evidence_path=evidence_path,
                    next_action="Keep parked files intact and review manifest identity before any repair route exists.",
                )
            )
        elif status in review_statuses:
            review_count += 1
            findings.append(
                _startup_finding(
                    "startup_pending_manifest_review",
                    "pending_manifests",
                    "review",
                    "medium",
                    f"Pending manifest needs operator review before startup repair: {status}.",
                    evidence_path=evidence_path,
                    next_action="Review pending-publish evidence; dry-run does not rewrite manifests or retry drain.",
                )
            )
    return _startup_category(
        "pending_manifests",
        "Pending manifests",
        findings=findings,
        metrics={
            "row_count": len(rows),
            "blocked_manifest_count": blocked_count,
            "review_manifest_count": review_count,
        },
        summary_lines=[
            f"Pending manifest rows scanned: {len(rows)}.",
            "No pending manifest, payload, sidecar, destination output, or drain summary was changed.",
        ],
    )


def _startup_orphan_payload_category(pending_publish: Mapping[str, Any] | None) -> dict[str, Any]:
    rows = [row for row in (pending_publish or {}).get("rows") or [] if isinstance(row, Mapping)]
    findings: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("diagnostic_status") or row.get("state") or "").strip().casefold()
        if status != "orphan_payload":
            continue
        findings.append(
            _startup_finding(
                "startup_pending_orphan_payload",
                "orphaned_parked_outputs",
                "review",
                "medium",
                "Pending publish contains an orphaned parked payload without manifest-selected destination evidence.",
                evidence_path=str(row.get("local_file") or row.get("path") or ""),
                next_action="Leave the payload parked; do not move or delete without manifest-backed repair design.",
            )
        )
    return _startup_category(
        "orphaned_parked_outputs",
        "Orphaned parked outputs",
        findings=findings,
        metrics={"orphan_payload_count": len(findings)},
        summary_lines=[
            f"Orphaned parked payload rows: {len(findings)}.",
            "No parked payload was moved, deleted, drained, or published.",
        ],
    )


def _startup_active_jobs_category(resolved: Any) -> dict[str, Any]:
    state_root = getattr(resolved, "state_root", None)
    active_dir = getattr(resolved, "active_jobs_path", None) or (Path(state_root) / "ActiveJobs" if state_root else None)
    if active_dir is None or not Path(active_dir).exists():
        return _startup_category(
            "active_jobs",
            "ActiveJobs",
            metrics={"record_count": 0, "active_record_count": 0},
            summary_lines=["No ActiveJobs folder exists yet, or no ActiveJobs evidence is configured."],
        )
    findings: list[dict[str, Any]] = []
    record_count = 0
    active_count = 0
    try:
        records = sorted(Path(active_dir).glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        findings.append(
            _startup_finding(
                "startup_active_jobs_unreadable",
                "active_jobs",
                "review",
                "medium",
                f"ActiveJobs folder could not be listed: {exc}",
                evidence_path=str(active_dir),
                next_action="Restore ActiveJobs folder readability only if passive launch diagnostics are needed.",
            )
        )
        records = []
    for record_path in records[: bounded_repair_reconcile_limit(None)]:
        record_count += 1
        try:
            payload = json.loads(record_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            findings.append(
                _startup_finding(
                    "startup_active_job_unreadable",
                    "active_jobs",
                    "review",
                    "medium",
                    f"ActiveJobs record could not be read: {exc}",
                    evidence_path=str(record_path),
                    next_action="Treat this as passive diagnostics debt; launch and close-readiness do not depend on this record.",
                )
            )
            continue
        if not isinstance(payload, Mapping):
            findings.append(
                _startup_finding(
                    "startup_active_job_invalid_shape",
                    "active_jobs",
                    "review",
                    "medium",
                    "ActiveJobs record JSON root is not an object.",
                    evidence_path=str(record_path),
                    next_action="Repair invalid ActiveJobs evidence only if passive launch diagnostics are needed.",
                )
            )
            continue
        status = str(payload.get("status") or "").strip().casefold()
        if status not in {"launching", "active"}:
            continue
        active_count += 1
        pid = payload.get("pid")
        if pid in (None, ""):
            findings.append(
                _startup_finding(
                    "startup_active_job_missing_pid",
                    "active_jobs",
                    "review",
                    "medium",
                    "ActiveJobs record reports passive active-work evidence with no PID.",
                    evidence_path=str(record_path),
                    next_action="Use process/progress close-readiness for lifecycle decisions; this record is passive diagnostics evidence.",
                )
            )
        else:
            findings.append(
                _startup_finding(
                    "startup_active_job_unverified",
                    "active_jobs",
                    "review",
                    "medium",
                    f"ActiveJobs record reports passive active-work evidence for PID {pid}; identity was not reconciled by this dry-run.",
                    evidence_path=str(record_path),
                    next_action="Use process/progress close-readiness for lifecycle decisions. This dry-run does not kill or rewrite records.",
                )
            )
    return _startup_category(
        "active_jobs",
        "ActiveJobs",
        findings=findings,
        metrics={"record_count": record_count, "active_record_count": active_count},
        summary_lines=[
            f"ActiveJobs records scanned: {record_count}; active/launching records: {active_count}.",
            "ActiveJobs records are passive diagnostics here; no record was rewritten and no process was killed.",
        ],
    )


def _startup_sqlite_mirror_category(resolved: Any, completed_preview: Mapping[str, Any] | None) -> dict[str, Any]:
    state_root = getattr(resolved, "state_root", None)
    if state_root is None:
        finding = _startup_finding(
            "startup_sqlite_state_root_missing",
            "sqlite_mirror",
            "review",
            "medium",
            "State root is not configured; SQLite mirror posture cannot be checked.",
            next_action="Resolve LocalBase/state_root before relying on SQLite mirror evidence.",
        )
        return _startup_category("sqlite_mirror", "SQLite mirror", findings=[finding])
    db_path = Path(state_root) / STATE_DB_FILENAME
    if not db_path.exists():
        finding = _startup_finding(
            "startup_sqlite_mirror_missing",
            "sqlite_mirror",
            "review",
            "medium",
            "SQLite mirror file is missing; JSON state remains authoritative.",
            evidence_path=str(db_path),
            next_action="Treat this as shadow-state gap only; do not rebuild mirror without a proven rebuild route.",
        )
        return _startup_category(
            "sqlite_mirror",
            "SQLite mirror",
            findings=[finding],
            metrics={"db_exists": False, "completed_preview_count": _completed_preview_count(completed_preview)},
        )
    findings: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {"db_exists": True, "db_path": str(db_path)}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        findings.append(
            _startup_finding(
                "startup_sqlite_mirror_unreadable",
                "sqlite_mirror",
                "blocked",
                "high",
                f"SQLite mirror could not be opened read-only: {exc}",
                evidence_path=str(db_path),
                next_action="Keep JSON/manifests authoritative; inspect or rebuild SQLite only through a proven route.",
            )
        )
        return _startup_category("sqlite_mirror", "SQLite mirror", findings=findings, metrics=metrics)
    try:
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        metrics["user_version"] = user_version
        if user_version > CURRENT_SCHEMA_VERSION:
            findings.append(
                _startup_finding(
                    "startup_sqlite_mirror_newer_schema",
                    "sqlite_mirror",
                    "blocked",
                    "high",
                    f"SQLite mirror schema version {user_version} is newer than supported version {CURRENT_SCHEMA_VERSION}.",
                    evidence_path=str(db_path),
                    next_action="Do not migrate or rebuild automatically; use a compatible build or explicit repair plan.",
                )
            )
        completed_preview_count = _completed_preview_count(completed_preview)
        metrics["completed_preview_count"] = completed_preview_count
        if _sqlite_table_exists(conn, "completed_jobs"):
            mirror_completed_count = int(conn.execute("SELECT COUNT(*) FROM completed_jobs").fetchone()[0])
            metrics["sqlite_completed_jobs_count"] = mirror_completed_count
            if completed_preview_count != mirror_completed_count:
                findings.append(
                    _startup_finding(
                        "startup_sqlite_completed_mirror_count_mismatch",
                        "sqlite_mirror",
                        "review",
                        "medium",
                        (
                            "SQLite completed_jobs mirror count does not match completed manifest preview "
                            f"({mirror_completed_count} != {completed_preview_count})."
                        ),
                        evidence_path=str(db_path),
                        next_action="Treat completed JSON/manifests as authoritative; rebuild SQLite only through a proven dry-run and repair route.",
                    )
                )
        else:
            metrics["sqlite_completed_jobs_count"] = None
            findings.append(
                _startup_finding(
                    "startup_sqlite_completed_table_missing",
                    "sqlite_mirror",
                    "review",
                    "medium",
                    "SQLite mirror is missing completed_jobs table.",
                    evidence_path=str(db_path),
                    next_action="Do not create tables from startup dry-run; use a proven migration/rebuild route.",
                )
            )
    except sqlite3.Error as exc:
        findings.append(
            _startup_finding(
                "startup_sqlite_mirror_query_failed",
                "sqlite_mirror",
                "blocked",
                "high",
                f"SQLite mirror read-only query failed: {exc}",
                evidence_path=str(db_path),
                next_action="Keep JSON/manifests authoritative and inspect SQLite before any rebuild.",
            )
        )
    finally:
        conn.close()
    return _startup_category(
        "sqlite_mirror",
        "SQLite mirror",
        findings=findings,
        metrics=metrics,
        summary_lines=[
            f"SQLite mirror path: {db_path}.",
            "The mirror was opened read-only; no migrations, rebuilds, or writes were attempted.",
        ],
    )


def _sqlite_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _completed_preview_count(completed_preview: Mapping[str, Any] | None) -> int:
    rows = completed_preview.get("rows") if isinstance(completed_preview, Mapping) else []
    return len(rows) if isinstance(rows, list) else 0


def startup_reconciliation_dry_run(
    *,
    resolved: Any,
    pending_publish: Mapping[str, Any] | None,
    completed_preview: Mapping[str, Any] | None,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    scope = normalize_repair_reconcile_scope(request.get("scope"), request.get("row_key"))
    limit = bounded_repair_reconcile_limit(request.get("limit"))
    preconditions = [
        _precondition(
            "startup_reconciliation_read_only",
            "ok",
            "Startup reconciliation dry-run uses backend-resolved state evidence only.",
            "No repair mutation is available from this dry-run.",
        ),
        backend_path_authority_precondition("startup_reconciliation"),
    ]
    if scope != "all":
        preconditions.append(
            _precondition(
                "startup_scope_all_only",
                "blocked",
                "Startup reconciliation dry-run is aggregate-only; selected rows are not accepted.",
                "Use the completed or pending-publish row-specific dry-run routes for selected evidence.",
            )
        )
    categories = {
        "pending_manifests": _startup_pending_manifest_category(pending_publish),
        "orphaned_parked_outputs": _startup_orphan_payload_category(pending_publish),
        "active_jobs": _startup_active_jobs_category(resolved),
        "sqlite_mirror": _startup_sqlite_mirror_category(resolved, completed_preview),
    }
    rows = [
        dict(finding)
        for category in categories.values()
        for finding in category.get("findings", [])
        if isinstance(finding, Mapping)
    ]
    overall_status = "blocked" if _blocked(preconditions) else _startup_overall_status(categories)
    blocked_count = sum(1 for row in rows if str(row.get("status") or "").casefold() == "blocked")
    review_count = sum(1 for row in rows if str(row.get("status") or "").casefold() == "review")
    return {
        "schema_version": STARTUP_RECONCILIATION_DRY_RUN_SCHEMA_VERSION,
        "candidate_command": STARTUP_RECONCILE_STATE_COMMAND,
        "dry_run_only": True,
        "effect": REPAIR_RECONCILE_EFFECT_NONE,
        "scope": scope,
        "selected_row_keys": [],
        "precondition_results": preconditions,
        "categories": categories,
        "overall_status": overall_status,
        "safe_to_start_after_review": overall_status != "blocked",
        "diff_summary": {
            "schema_version": "desktop_startup_reconciliation_diff_summary.v1",
            "candidate_count": review_count,
            "blocked_count": blocked_count,
            "review_count": review_count,
            "rows": rows[:limit],
            "summary_lines": [
                f"Startup reconciliation dry-run status: {overall_status}.",
                f"Blocked findings: {blocked_count}; review findings: {review_count}.",
                "JSON/manifests remain authoritative; no repair, drain, cleanup, or mirror rebuild ran.",
            ],
        },
        "would_write_paths": [],
        "would_move_paths": [],
        "would_delete_paths": [],
        "would_not_touch": _startup_would_not_touch(),
        "safe_to_apply": False,
        "mutation_route_available": False,
        "startup_repair_available": False,
        "apply_route_available": False,
        "operator_confirmation_scope": "No startup repair mutation route exists in this build; backend dry-run evidence only.",
        "suppress_command_journal": True,
        "rollback_preview": {
            "backup_required_for_future_mutation": True,
            "backup_created_by_dry_run": False,
            "temp_file_created_by_dry_run": False,
            "journal_recorded_by_dry_run": False,
            "sqlite_rebuild_created_by_dry_run": False,
        },
        "request_summary": {
            "scope": scope,
            "row_key_present": bool(requested_row_key(request)),
            "limit": limit,
            "reason_present": bool(str(request.get("reason") or "").strip()),
        },
        "summary_lines": [
            f"Startup reconciliation dry-run status: {overall_status}.",
            "Covered pending manifests, orphaned parked payloads, ActiveJobs, and SQLite mirror posture.",
            "No files, manifests, ActiveJobs records, SQLite tables, parked payloads, source media, scratch media, or output media were changed.",
        ],
    }
