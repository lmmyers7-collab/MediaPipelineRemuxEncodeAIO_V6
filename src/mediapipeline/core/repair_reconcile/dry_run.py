from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from mediapipeline.core.kernel.contracts.base import ContractError
from mediapipeline.core.kernel.contracts.pending_publish import (
    PENDING_PUSH_MANIFEST_REQUIRED_ARRAY_FIELDS,
    PENDING_PUSH_MANIFEST_REQUIRED_TEXT_FIELDS,
    PENDING_PUSH_MANIFEST_SCHEMA_VERSION,
    PendingPushManifest,
)
from mediapipeline.core.storage.db import CURRENT_SCHEMA_VERSION, STATE_DB_FILENAME


REPAIR_RECONCILE_DRY_RUN_SCHEMA_VERSION = "desktop_repair_reconcile_dry_run.v1"
STARTUP_RECONCILIATION_DRY_RUN_SCHEMA_VERSION = "desktop_startup_reconciliation_dry_run.v1"
REPAIR_RECONCILE_EFFECT_NONE = "none"

STARTUP_RECONCILE_STATE_COMMAND = "startup.reconcile_state"
COMPLETED_RECONCILE_MANIFEST_COMMAND = "completed.reconcile_manifest"
COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND = "completed.repair_sidecar_metadata"
PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND = "pending_publish.repair_manifest"
PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND = "pending_publish.reconcile_orphan_payloads"

DRY_RUN_COMMAND_BY_CANDIDATE = {
    STARTUP_RECONCILE_STATE_COMMAND: "startup.reconcile_state_dry_run",
    COMPLETED_RECONCILE_MANIFEST_COMMAND: "completed.reconcile_manifest_dry_run",
    COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND: "completed.repair_sidecar_metadata_dry_run",
    PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND: "pending_publish.repair_manifest_dry_run",
    PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND: "pending_publish.reconcile_orphan_payloads_dry_run",
}


def dry_run_command_name(candidate_command: str) -> str:
    return DRY_RUN_COMMAND_BY_CANDIDATE.get(candidate_command, f"{candidate_command}_dry_run")


def repair_reconcile_dry_run_fingerprint(payload: Mapping[str, Any]) -> str:
    """Stable operator-confirmation fingerprint for a backend dry-run payload."""

    selected = {
        "schema_version": payload.get("schema_version"),
        "candidate_command": payload.get("candidate_command"),
        "scope": payload.get("scope"),
        "selected_row_keys": payload.get("selected_row_keys") or [],
        "precondition_results": payload.get("precondition_results") or [],
        "diff_summary": payload.get("diff_summary") or {},
        "would_write_paths": payload.get("would_write_paths") or [],
        "would_move_paths": payload.get("would_move_paths") or [],
        "would_delete_paths": payload.get("would_delete_paths") or [],
        "safe_to_apply": bool(payload.get("safe_to_apply")),
    }
    encoded = json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8", errors="replace")).hexdigest()


def normalize_repair_reconcile_scope(value: object, row_key: object | None = None) -> str:
    scope = str(value or "").strip().casefold()
    if scope in {"all", "selected"}:
        return scope
    if str(row_key or "").strip():
        return "selected"
    return "all"


def bounded_repair_reconcile_limit(value: object, *, default: int = 100, maximum: int = 500) -> int:
    try:
        parsed = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(maximum, parsed))


def requested_row_key(request: Mapping[str, Any]) -> str:
    return str(request.get("row_key") or "").strip()


def _precondition(key: str, status: str, evidence: str, action: str) -> dict[str, str]:
    return {
        "key": key,
        "status": status,
        "evidence": evidence,
        "action": action,
    }


def active_work_precondition(block_message: str) -> dict[str, str]:
    if block_message:
        return _precondition(
            "pipeline_idle",
            "blocked",
            block_message,
            "Wait for active MediaPipeline work to finish before designing a mutation route.",
        )
    return _precondition(
        "pipeline_idle",
        "ok",
        "No active MediaPipeline work was reported by backend close-readiness guards.",
        "No operator action required for this dry-run.",
    )


def backend_path_authority_precondition(domain: str) -> dict[str, str]:
    return _precondition(
        "backend_path_authority",
        "ok",
        f"{domain} paths are derived from backend preview/scan evidence; request payload paths are not accepted.",
        "Do not add client-submitted path, patch, destination, manifest, or sidecar fields.",
    )


def _required_would_not_touch() -> dict[str, str]:
    return {
        "source_media": "no read/write/delete/rename/move",
        "scratch_media": "no create/delete/cleanup",
        "output_media": "no create/delete/overwrite/publish",
        "pending_payload_bytes": "no move/delete/drain/publish",
        "completed_manifest": "not written by dry-run",
        "pending_manifest": "not written by dry-run",
        "sidecar_json": "not written by dry-run",
        "command_journal": "suppressed for dry-run preview only",
    }


def _startup_would_not_touch() -> dict[str, str]:
    result = _required_would_not_touch()
    result.update(
        {
            "active_jobs": "read-only scan; not reconciled, killed, archived, or rewritten",
            "sqlite_mirror": "read-only metadata/count check; no migration, rebuild, vacuum, or write",
            "pending_drain_summary": "not written by dry-run",
            "failure_markers": "not cleared by dry-run",
        }
    )
    return result


def _base_payload(
    *,
    candidate_command: str,
    scope: str,
    selected_row_keys: list[str],
    preconditions: list[dict[str, str]],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": REPAIR_RECONCILE_DRY_RUN_SCHEMA_VERSION,
        "candidate_command": candidate_command,
        "dry_run_only": True,
        "effect": REPAIR_RECONCILE_EFFECT_NONE,
        "scope": scope,
        "selected_row_keys": selected_row_keys,
        "precondition_results": preconditions,
        "diff_summary": {
            "schema_version": "desktop_repair_reconcile_diff_summary.v1",
            "candidate_count": 0,
            "blocked_count": 0,
            "review_count": 0,
            "rows": [],
            "summary_lines": [],
        },
        "would_write_paths": [],
        "would_move_paths": [],
        "would_delete_paths": [],
        "would_not_touch": _required_would_not_touch(),
        "safe_to_apply": False,
        "mutation_route_available": True,
        "apply_route_available": True,
        "operator_confirmation_scope": "A confirmed apply route exists but will reject unless safe_to_apply is true and the dry_run_fingerprint matches.",
        "suppress_command_journal": True,
        "rollback_preview": {
            "backup_required_for_future_mutation": True,
            "backup_created_by_dry_run": False,
            "temp_file_created_by_dry_run": False,
            "journal_recorded_by_dry_run": False,
        },
        "request_summary": {
            "scope": scope,
            "row_key_present": bool(requested_row_key(request)),
            "limit": bounded_repair_reconcile_limit(request.get("limit")),
            "reason_present": bool(str(request.get("reason") or "").strip()),
        },
    }


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


def _startup_status(findings: list[Mapping[str, Any]]) -> str:
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
                "blocked",
                "high",
                f"ActiveJobs folder could not be listed: {exc}",
                evidence_path=str(active_dir),
                next_action="Restore ActiveJobs folder readability before startup repair or launch.",
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
                    "blocked",
                    "high",
                    f"ActiveJobs record could not be read: {exc}",
                    evidence_path=str(record_path),
                    next_action="Keep launch gated until unreadable ActiveJobs evidence is repaired or archived by a proven route.",
                )
            )
            continue
        if not isinstance(payload, Mapping):
            findings.append(
                _startup_finding(
                    "startup_active_job_invalid_shape",
                    "active_jobs",
                    "blocked",
                    "high",
                    "ActiveJobs record JSON root is not an object.",
                    evidence_path=str(record_path),
                    next_action="Repair invalid ActiveJobs evidence before startup repair or launch.",
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
                    "blocked",
                    "high",
                    "ActiveJobs record reports active work with no PID.",
                    evidence_path=str(record_path),
                    next_action="Do not launch new work; dry-run cannot prove whether this active job is safe to reconcile.",
                )
            )
        else:
            findings.append(
                _startup_finding(
                    "startup_active_job_unverified",
                    "active_jobs",
                    "blocked",
                    "high",
                    f"ActiveJobs record reports active work for PID {pid}; identity was not reconciled by this dry-run.",
                    evidence_path=str(record_path),
                    next_action="Use close-readiness/lifecycle evidence before any ActiveJobs repair. This dry-run does not kill or rewrite records.",
                )
            )
    return _startup_category(
        "active_jobs",
        "ActiveJobs",
        findings=findings,
        metrics={"record_count": record_count, "active_record_count": active_count},
        summary_lines=[
            f"ActiveJobs records scanned: {record_count}; active/launching records: {active_count}.",
            "No ActiveJobs record was rewritten and no process was killed.",
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


def _row_key(row: Mapping[str, Any]) -> str:
    return str(row.get("row_key") or "").strip()


def _select_rows(
    rows: list[dict[str, Any]],
    *,
    scope: str,
    row_key: str,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    preconditions: list[dict[str, str]] = []
    if scope == "selected":
        selected = [row for row in rows if _row_key(row).casefold() == row_key.casefold()]
        if not row_key:
            preconditions.append(
                _precondition(
                    "selected_row_key_present",
                    "blocked",
                    "scope=selected requires row_key.",
                    "Submit row_key for selected dry-runs.",
                )
            )
        elif not selected:
            preconditions.append(
                _precondition(
                    "selected_row_exists",
                    "blocked",
                    f"Selected row_key was not found in the loaded backend evidence: {row_key}",
                    "Refresh the preview and select an existing backend row.",
                )
            )
        else:
            preconditions.append(
                _precondition(
                    "selected_row_exists",
                    "ok",
                    f"Selected backend row exists: {row_key}",
                    "No operator action required for this dry-run.",
                )
            )
        return selected[:1], preconditions
    return rows[:limit], [
        _precondition(
            "scope_rows_loaded",
            "ok",
            f"{min(len(rows), limit)} loaded backend row(s) selected from {len(rows)} available row(s).",
            "Use scope=selected with row_key to narrow a future review.",
        )
    ]


def _path_exists_text(path_text: str) -> tuple[bool | None, str]:
    if not path_text:
        return None, "path not reported"
    try:
        return Path(path_text).exists(), path_text
    except OSError as exc:
        return None, f"{path_text} ({exc})"


def _read_json_object(path_text: str) -> tuple[dict[str, Any] | None, str]:
    if not path_text:
        return None, "path not reported"
    try:
        path = Path(path_text)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "JSON root is not an object."
    return payload, ""


def _blocked(preconditions: list[Mapping[str, Any]]) -> bool:
    return any(str(row.get("status") or "").casefold() == "blocked" for row in preconditions)


def _set_summary(
    payload: dict[str, Any],
    *,
    rows: list[dict[str, Any]],
    summary_lines: list[str],
    would_write_paths: list[dict[str, str]] | None = None,
    would_move_paths: list[dict[str, str]] | None = None,
    would_delete_paths: list[dict[str, str]] | None = None,
    require_mutation_candidate: bool = True,
) -> dict[str, Any]:
    would_write = list(would_write_paths or [])
    would_move = list(would_move_paths or [])
    would_delete = list(would_delete_paths or [])
    payload["would_write_paths"] = would_write
    payload["would_move_paths"] = would_move
    payload["would_delete_paths"] = would_delete
    candidate_count = sum(1 for row in rows if str(row.get("status") or "").casefold() == "candidate")
    blocked_count = sum(1 for row in rows if str(row.get("status") or "").casefold() == "blocked")
    review_count = sum(1 for row in rows if str(row.get("status") or "").casefold() == "review")
    payload["diff_summary"] = {
        "schema_version": "desktop_repair_reconcile_diff_summary.v1",
        "candidate_count": candidate_count,
        "blocked_count": blocked_count,
        "review_count": review_count,
        "rows": rows,
        "summary_lines": summary_lines,
    }
    preconditions = payload["precondition_results"]
    no_blockers = not _blocked(preconditions) and blocked_count == 0
    has_selected_candidate = any(str(row.get("status") or "").casefold() == "candidate" for row in rows)
    has_mutation_candidate = bool(
        (has_selected_candidate and (would_write or would_move or would_delete)) or not require_mutation_candidate
    )
    payload["safe_to_apply"] = bool(no_blockers and has_mutation_candidate)
    payload["dry_run_fingerprint"] = repair_reconcile_dry_run_fingerprint(payload)
    if payload["safe_to_apply"]:
        payload["operator_confirmation_scope"] = "Submit the selected row key and dry_run_fingerprint to the matching confirmed apply route."
    return payload


def completed_manifest_reconcile_dry_run(
    *,
    preview: Mapping[str, Any],
    resolved: Any,
    request: Mapping[str, Any],
    base_preconditions: list[dict[str, str]],
) -> dict[str, Any]:
    scope = normalize_repair_reconcile_scope(request.get("scope"), request.get("row_key"))
    limit = bounded_repair_reconcile_limit(request.get("limit"))
    row_key = requested_row_key(request)
    rows = [dict(row) for row in preview.get("rows") or [] if isinstance(row, Mapping)]
    selected_rows, selection_preconditions = _select_rows(rows, scope=scope, row_key=row_key, limit=limit)
    selected_keys = [_row_key(row) for row in selected_rows if _row_key(row)]
    preconditions = [*base_preconditions, backend_path_authority_precondition("completed"), *selection_preconditions]
    manifest_path = str(getattr(resolved, "completed_manifest_path", "") or preview.get("source") or "")
    manifest_error = str(preview.get("manifest_error") or "").strip()
    if manifest_error:
        preconditions.append(
            _precondition(
                "completed_manifest_readable",
                "blocked",
                manifest_error,
                "Repair the completed manifest read error before designing a mutation.",
            )
        )
    else:
        preconditions.append(
            _precondition(
                "completed_manifest_readable",
                "ok" if manifest_path else "review",
                manifest_path or "completed manifest path is not reported",
                "Use backend-resolved completed manifest evidence only.",
            )
        )
    payload = _base_payload(
        candidate_command=COMPLETED_RECONCILE_MANIFEST_COMMAND,
        scope=scope,
        selected_row_keys=selected_keys,
        preconditions=preconditions,
        request=request,
    )
    diff_rows: list[dict[str, Any]] = []
    would_write: list[dict[str, str]] = []
    for row in selected_rows:
        issues = [str(issue) for issue in row.get("consistency_issues") or [] if str(issue).strip()]
        relevant = [issue for issue in issues if issue in {"manifest_missing_output_path", "output_sidecar_mismatch"}]
        output_path = str(row.get("output_path") or "").strip()
        output_exists = row.get("output_exists")
        if "missing_output" in issues or output_exists is False:
            diff_rows.append(
                {
                    "row_key": _row_key(row),
                    "status": "blocked",
                    "action": "completed_manifest_reconcile",
                    "reasons": sorted(set(issues or ["missing_output"])),
                    "safe_next_action": "Resolve missing completed output before any manifest repair design.",
                }
            )
            preconditions.append(
                _precondition(
                    f"completed_row_output_exists:{_row_key(row)}",
                    "blocked",
                    output_path or "output path not reported",
                    "Do not rewrite completed manifest evidence while the output is missing.",
                )
            )
            continue
        if not relevant:
            diff_rows.append(
                {
                    "row_key": _row_key(row),
                    "status": "unchanged",
                    "action": "completed_manifest_reconcile",
                    "reasons": issues,
                    "safe_next_action": "No completed manifest reconcile candidate detected in this loaded row.",
                }
            )
            continue
        diff_rows.append(
            {
                "row_key": _row_key(row),
                "status": "candidate",
                "action": "completed_manifest_reconcile",
                "reasons": relevant,
                "current": {
                    "manifest_output_path": str(row.get("manifest_output_path") or ""),
                    "manifest_output_file": str(row.get("manifest_output_file") or ""),
                    "sidecar_path": str(row.get("sidecar_path") or ""),
                },
                "proposed": {
                    "output_path": output_path,
                    "output_file": str(row.get("output_file") or Path(output_path).name if output_path else ""),
                    "expected_sidecar_path": str(row.get("expected_sidecar_path") or ""),
                },
                "safe_next_action": "Review the dry-run diff; no completed manifest write route exists.",
            }
        )
    if manifest_path and any(row.get("status") == "candidate" for row in diff_rows):
        would_write.append({"path": manifest_path, "reason": "future completed manifest reconcile mutation would rewrite affected row fields"})
    return _set_summary(
        payload,
        rows=diff_rows,
        summary_lines=[
            f"Completed manifest dry-run reviewed {len(selected_rows)} loaded completed row(s).",
            "No completed manifest, sidecar, output, source, or scratch file was written.",
        ],
        would_write_paths=would_write,
    )


def completed_sidecar_metadata_repair_dry_run(
    *,
    preview: Mapping[str, Any],
    request: Mapping[str, Any],
    base_preconditions: list[dict[str, str]],
) -> dict[str, Any]:
    scope = normalize_repair_reconcile_scope(request.get("scope"), request.get("row_key"))
    limit = bounded_repair_reconcile_limit(request.get("limit"))
    row_key = requested_row_key(request)
    rows = [dict(row) for row in preview.get("rows") or [] if isinstance(row, Mapping)]
    selected_rows, selection_preconditions = _select_rows(rows, scope=scope, row_key=row_key, limit=limit)
    selected_keys = [_row_key(row) for row in selected_rows if _row_key(row)]
    preconditions = [*base_preconditions, backend_path_authority_precondition("completed"), *selection_preconditions]
    payload = _base_payload(
        candidate_command=COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND,
        scope=scope,
        selected_row_keys=selected_keys,
        preconditions=preconditions,
        request=request,
    )
    diff_rows: list[dict[str, Any]] = []
    would_write: list[dict[str, str]] = []
    for row in selected_rows:
        key = _row_key(row)
        sidecar_path = str(row.get("sidecar_path") or "").strip()
        exists, evidence = _path_exists_text(sidecar_path)
        if exists is not True:
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "blocked",
                    "action": "completed_sidecar_metadata_repair",
                    "sidecar_path": sidecar_path,
                    "reasons": ["missing_sidecar"],
                    "safe_next_action": "Restore or regenerate the backend-selected sidecar before metadata repair.",
                }
            )
            preconditions.append(
                _precondition(
                    f"completed_sidecar_readable:{key}",
                    "blocked",
                    evidence,
                    "Missing sidecars are review evidence only in this dry-run.",
                )
            )
            continue
        sidecar, error = _read_json_object(sidecar_path)
        if sidecar is None:
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "blocked",
                    "action": "completed_sidecar_metadata_repair",
                    "sidecar_path": sidecar_path,
                    "reasons": ["unreadable_sidecar"],
                    "error": error,
                    "safe_next_action": "Fix sidecar JSON readability before metadata repair.",
                }
            )
            preconditions.append(
                _precondition(
                    f"completed_sidecar_readable:{key}",
                    "blocked",
                    error,
                    "Sidecar metadata repair cannot be previewed from unreadable JSON.",
                )
            )
            continue
        preconditions.append(
            _precondition(
                f"completed_sidecar_readable:{key}",
                "ok",
                sidecar_path,
                "Sidecar JSON was read for diff evidence only.",
            )
        )
        proposed = {
            "source_path": str(row.get("source_path") or ""),
            "output_path": str(row.get("output_path") or ""),
            "output_file": str(row.get("output_file") or ""),
        }
        current = {field: str(sidecar.get(field) or "") for field in proposed}
        changed = {field: {"current": current[field], "proposed": proposed[field]} for field in proposed if current[field] != proposed[field]}
        if not changed:
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "unchanged",
                    "action": "completed_sidecar_metadata_repair",
                    "sidecar_path": sidecar_path,
                    "changed_fields": {},
                    "safe_next_action": "No sidecar metadata repair candidate detected in this loaded row.",
                }
            )
            continue
        diff_rows.append(
            {
                "row_key": key,
                "status": "candidate",
                "action": "completed_sidecar_metadata_repair",
                "sidecar_path": sidecar_path,
                "changed_fields": changed,
                "safe_next_action": "Review the dry-run diff; no sidecar write route exists.",
            }
        )
        would_write.append({"path": sidecar_path, "reason": "future sidecar metadata repair mutation would rewrite JSON metadata fields"})
    return _set_summary(
        payload,
        rows=diff_rows,
        summary_lines=[
            f"Completed sidecar dry-run reviewed {len(selected_rows)} loaded completed row(s).",
            "No sidecar JSON, completed manifest, output, source, or scratch file was written.",
        ],
        would_write_paths=would_write,
    )


def _set_pending_manifest_field(
    proposed: dict[str, Any],
    changed: dict[str, dict[str, Any]],
    field: str,
    value: Any,
) -> None:
    current_value = proposed.get(field) if field in proposed else "<missing>"
    if current_value == value:
        return
    proposed[field] = value
    changed[field] = {"current": current_value, "proposed": value}


def _pending_manifest_sidecar_paths(sidecar_files: list[Any]) -> list[Path]:
    paths: list[Path] = []
    for sidecar in sidecar_files:
        if not isinstance(sidecar, Mapping):
            continue
        raw = str(sidecar.get("local_file") or sidecar.get("parked_file") or "").strip()
        if raw:
            paths.append(Path(raw))
    return paths


def _pending_orphan_missing_manifest_evidence(row: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    if not str(row.get("manifest_path") or "").strip():
        missing.append("manifest_path")
    if str(row.get("schema_version") or "").strip() != PENDING_PUSH_MANIFEST_SCHEMA_VERSION:
        missing.append("schema_version")
    for field in PENDING_PUSH_MANIFEST_REQUIRED_TEXT_FIELDS:
        if not str(row.get(field) or "").strip():
            missing.append(field)
    if "output_size" not in row or row.get("output_size") in (None, ""):
        missing.append("output_size")
    for field in PENDING_PUSH_MANIFEST_REQUIRED_ARRAY_FIELDS:
        if not isinstance(row.get(field), list):
            missing.append(field)
    return missing


def _pending_manifest_repair_candidate_row(
    *,
    row: Mapping[str, Any],
    key: str,
    manifest_path: str,
    diagnostic_status: str,
) -> dict[str, Any]:
    manifest, read_error = _read_json_object(manifest_path)
    if manifest is None:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "error": read_error,
            "safe_next_action": "Fix pending manifest readability before any backend manifest repair.",
        }

    proposed = dict(manifest)
    changed: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []
    for field in PENDING_PUSH_MANIFEST_REQUIRED_ARRAY_FIELDS:
        if field not in proposed or proposed.get(field) is None:
            _set_pending_manifest_field(proposed, changed, field, [])
            reasons.append(f"missing_{field}")

    local_file = str(proposed.get("local_file") or "").strip()
    parked_file = str(proposed.get("parked_file") or "").strip()
    if not local_file and parked_file:
        parked_path = Path(parked_file)
        if parked_path.exists() and parked_path.is_file():
            _set_pending_manifest_field(proposed, changed, "local_file", parked_file)
            reasons.append("missing_local_file_copied_from_parked_file")

    output_size_missing = "output_size" not in proposed or proposed.get("output_size") in (None, "")
    if output_size_missing:
        local_text = str(proposed.get("local_file") or "").strip()
        if local_text:
            local_path = Path(local_text)
            try:
                if local_path.exists() and local_path.is_file():
                    _set_pending_manifest_field(proposed, changed, "output_size", local_path.stat().st_size)
                    reasons.append("missing_output_size_inferred_from_payload")
            except OSError:
                pass

    if not changed:
        try:
            PendingPushManifest.from_mapping(manifest)
        except ContractError as exc:
            return {
                "row_key": key,
                "status": "blocked",
                "action": "pending_manifest_repair",
                "manifest_path": manifest_path,
                "diagnostic_status": diagnostic_status,
                "error": f"Current pending manifest contract invalid and no safe backend normalization is available: {exc}",
                "safe_next_action": "Repair pending manifest contract fields manually before confirmed apply.",
            }
        return {
            "row_key": key,
            "status": "unchanged",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "safe_next_action": "No backend-derived manifest-field repair candidate detected for this pending row.",
        }

    try:
        validated = PendingPushManifest.from_mapping(proposed)
    except ContractError as exc:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "changed_fields": changed,
            "missing_or_unsafe_fields": sorted(changed),
            "error": f"Backend proposed manifest still fails pending manifest contract: {exc}",
            "safe_next_action": "Repair the remaining manifest contract fields manually before confirmed apply.",
        }

    payload_path = Path(validated.local_file)
    if not payload_path.exists() or not payload_path.is_file():
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "changed_fields": changed,
            "missing_or_unsafe_fields": sorted(changed),
            "error": "Backend proposed manifest points at a missing pending payload.",
            "safe_next_action": "Restore the pending payload before confirmed manifest repair.",
        }

    missing_sidecars = [str(path) for path in _pending_manifest_sidecar_paths(validated.sidecar_files) if not path.exists()]
    if missing_sidecars:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "changed_fields": changed,
            "missing_or_unsafe_fields": sorted(changed),
            "missing_sidecar_paths": missing_sidecars,
            "error": "Backend proposed manifest references missing pending sidecar payloads.",
            "safe_next_action": "Restore missing sidecar payloads before confirmed manifest repair.",
        }

    return {
        "row_key": key,
        "status": "candidate",
        "action": "pending_manifest_repair",
        "manifest_path": manifest_path,
        "diagnostic_status": diagnostic_status,
        "local_file": validated.local_file,
        "source_path": validated.source_path,
        "output_path": validated.server_out,
        "reasons": reasons,
        "changed_fields": changed,
        "proposed": {
            "local_file": validated.local_file,
            "source_path": validated.source_path,
            "output_path": validated.server_out,
            "manifest_state": validated.manifest_state,
            "schema_version": PENDING_PUSH_MANIFEST_SCHEMA_VERSION,
        },
        "proposed_manifest": proposed,
        "safe_next_action": "Review the backend-derived manifest diff, then submit the matching dry-run fingerprint to confirmed apply.",
    }


def pending_manifest_repair_dry_run(
    *,
    preview: Mapping[str, Any],
    request: Mapping[str, Any],
    base_preconditions: list[dict[str, str]],
) -> dict[str, Any]:
    scope = normalize_repair_reconcile_scope(request.get("scope"), request.get("row_key"))
    limit = bounded_repair_reconcile_limit(request.get("limit"))
    row_key = requested_row_key(request)
    rows = [dict(row) for row in preview.get("rows") or [] if isinstance(row, Mapping)]
    selected_rows, selection_preconditions = _select_rows(rows, scope=scope, row_key=row_key, limit=limit)
    selected_keys = [_row_key(row) for row in selected_rows if _row_key(row)]
    preconditions = [*base_preconditions, backend_path_authority_precondition("pending_publish"), *selection_preconditions]
    pending_error = str(preview.get("error") or "").strip()
    preconditions.append(
        _precondition(
            "pending_publish_scan_readable",
            "blocked" if pending_error else "ok",
            pending_error or f"{len(rows)} pending publish row(s) loaded from existing scan.",
            "Resolve pending publish scan errors before mutation design." if pending_error else "Use current pending-publish scan evidence only.",
        )
    )
    payload = _base_payload(
        candidate_command=PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND,
        scope=scope,
        selected_row_keys=selected_keys,
        preconditions=preconditions,
        request=request,
    )
    diff_rows: list[dict[str, Any]] = []
    would_write: list[dict[str, str]] = []
    for row in selected_rows:
        key = _row_key(row)
        status = str(row.get("diagnostic_status") or "").strip().casefold()
        manifest_path = str(row.get("manifest_path") or "").strip()
        if status in {"unreadable_manifest", "duplicate_target"}:
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "blocked",
                    "action": "pending_manifest_repair",
                    "manifest_path": manifest_path,
                    "diagnostic_status": status,
                    "error": str(row.get("error") or ""),
                    "safe_next_action": "Review the backend manifest evidence manually; this dry-run does not accept patches.",
                }
            )
            preconditions.append(
                _precondition(
                    f"pending_manifest_repairable:{key}",
                    "blocked",
                    status or "pending manifest status is not repairable",
                    "Do not build a mutation from unreadable, invalid, or duplicate-target pending manifests.",
                )
            )
            continue
        if not manifest_path:
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "unchanged",
                    "action": "pending_manifest_repair",
                    "diagnostic_status": status,
                    "safe_next_action": "No manifest path exists for this row; use orphan-payload dry-run instead.",
                }
            )
            continue
        if status == "ready":
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "unchanged",
                    "action": "pending_manifest_repair",
                    "manifest_path": manifest_path,
                    "diagnostic_status": status,
                    "safe_next_action": "No pending manifest repair candidate detected.",
                }
            )
            continue
        candidate = _pending_manifest_repair_candidate_row(
            row=row,
            key=key,
            manifest_path=manifest_path,
            diagnostic_status=status,
        )
        diff_rows.append(candidate)
        if candidate.get("status") == "candidate":
            preconditions.append(
                _precondition(
                    f"pending_manifest_repairable:{key}",
                    "ok",
                    "Backend-derived proposed manifest validates pending_push_manifest.v1 and preserves payload/source/output paths.",
                    "Confirmed apply may write only this manifest after matching fingerprint and strict confirmation.",
                )
            )
            would_write.append({"path": manifest_path, "reason": "pending manifest repair will rewrite backend-validated manifest fields"})
        elif candidate.get("status") == "blocked":
            preconditions.append(
                _precondition(
                    f"pending_manifest_repairable:{key}",
                    "blocked",
                    str(candidate.get("error") or status or "pending manifest is not repairable"),
                    "Do not apply pending manifest repair until backend evidence can build a complete proposed manifest.",
                )
            )
    return _set_summary(
        payload,
        rows=diff_rows,
        summary_lines=[
            f"Pending manifest dry-run reviewed {len(selected_rows)} pending-publish row(s).",
            "Existing pending scan, recovery classification, file inventory, and drain summary evidence were reused.",
            "No pending manifest, payload, sidecar, output, source, or scratch file was written or moved.",
        ],
        would_write_paths=would_write,
    )


def pending_orphan_payload_reconcile_dry_run(
    *,
    preview: Mapping[str, Any],
    request: Mapping[str, Any],
    base_preconditions: list[dict[str, str]],
) -> dict[str, Any]:
    scope = normalize_repair_reconcile_scope(request.get("scope"), request.get("row_key"))
    limit = bounded_repair_reconcile_limit(request.get("limit"))
    row_key = requested_row_key(request)
    rows = [dict(row) for row in preview.get("rows") or [] if isinstance(row, Mapping)]
    selected_rows, selection_preconditions = _select_rows(rows, scope=scope, row_key=row_key, limit=limit)
    selected_keys = [_row_key(row) for row in selected_rows if _row_key(row)]
    preconditions = [*base_preconditions, backend_path_authority_precondition("pending_publish"), *selection_preconditions]
    pending_error = str(preview.get("error") or "").strip()
    preconditions.append(
        _precondition(
            "pending_publish_scan_readable",
            "blocked" if pending_error else "ok",
            pending_error or f"{len(rows)} pending publish row(s) loaded from existing scan.",
            "Resolve pending publish scan errors before mutation design." if pending_error else "Use current pending-publish scan evidence only.",
        )
    )
    payload = _base_payload(
        candidate_command=PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND,
        scope=scope,
        selected_row_keys=selected_keys,
        preconditions=preconditions,
        request=request,
    )
    diff_rows: list[dict[str, Any]] = []
    for row in selected_rows:
        key = _row_key(row)
        status = str(row.get("diagnostic_status") or "").strip().casefold()
        if status == "duplicate_target":
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "blocked",
                    "action": "pending_orphan_payload_reconcile",
                    "local_file": str(row.get("local_file") or ""),
                    "diagnostic_status": status,
                    "safe_next_action": "Resolve duplicate pending targets before any orphan-payload mutation design.",
                }
            )
            preconditions.append(
                _precondition(
                    f"pending_payload_ambiguity:{key}",
                    "blocked",
                    "duplicate pending target collision",
                    "Do not move or delete payloads while target ownership is ambiguous.",
                )
            )
            continue
        if status != "orphan_payload" and str(row.get("state") or "").casefold() != "orphan_payload":
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "unchanged",
                    "action": "pending_orphan_payload_reconcile",
                    "local_file": str(row.get("local_file") or ""),
                    "diagnostic_status": status,
                    "safe_next_action": "No orphan payload reconcile candidate detected.",
                }
            )
            continue
        missing_manifest_fields = _pending_orphan_missing_manifest_evidence(row)
        diff_rows.append(
            {
                "row_key": key,
                "status": "blocked",
                "action": "pending_orphan_payload_reconcile",
                "local_file": str(row.get("local_file") or ""),
                "output_size": row.get("output_size") or 0,
                "diagnostic_status": status,
                "missing_required_manifest_fields": missing_manifest_fields,
                "required_backend_evidence": (
                    "A manifest-only orphan reconcile requires a complete backend-derived "
                    f"{PENDING_PUSH_MANIFEST_SCHEMA_VERSION} proposal; WebView/request payloads must not supply fields."
                ),
                "proposed_manifest_available": False,
                "safe_next_action": (
                    "Restore the original pending manifest or rerun with backend manifest evidence; this route will not "
                    "infer destination/source from filename and will not move, delete, drain, or publish payloads."
                ),
            }
        )
        preconditions.append(
            _precondition(
                f"pending_payload_manifest_evidence:{key}",
                "blocked",
                "orphan payload lacks complete backend-derived pending_push_manifest.v1 evidence",
                "Restore the manifest or provide backend-owned manifest evidence before any confirmed apply; do not infer source/destination in the frontend.",
            )
        )
    return _set_summary(
        payload,
        rows=diff_rows,
        summary_lines=[
            f"Pending orphan-payload dry-run reviewed {len(selected_rows)} pending-publish row(s).",
            "Existing pending scan, file inventory, recovery classification, and drain summary evidence were reused.",
            "No backend-derived orphan manifest candidates were safe to apply unless a complete pending_push_manifest.v1 proposal is present.",
            "No pending payload, manifest, sidecar, output, source, or scratch file was moved, deleted, drained, or written.",
        ],
        would_move_paths=[],
        would_delete_paths=[],
    )


__all__ = [
    "COMPLETED_RECONCILE_MANIFEST_COMMAND",
    "COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND",
    "PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND",
    "PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND",
    "REPAIR_RECONCILE_DRY_RUN_SCHEMA_VERSION",
    "STARTUP_RECONCILE_STATE_COMMAND",
    "STARTUP_RECONCILIATION_DRY_RUN_SCHEMA_VERSION",
    "active_work_precondition",
    "bounded_repair_reconcile_limit",
    "completed_manifest_reconcile_dry_run",
    "completed_sidecar_metadata_repair_dry_run",
    "dry_run_command_name",
    "normalize_repair_reconcile_scope",
    "pending_manifest_repair_dry_run",
    "pending_orphan_payload_reconcile_dry_run",
    "repair_reconcile_dry_run_fingerprint",
    "startup_reconciliation_dry_run",
]
