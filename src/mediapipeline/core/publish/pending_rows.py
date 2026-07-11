from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from collections.abc import Mapping

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.core.kernel.contracts.pending_publish import (
    PENDING_PUSH_MANIFEST_DRAINABLE_STATES,
    PENDING_PUSH_RETRY_LIMIT,
    PENDING_PUSH_MANIFEST_SCHEMA_VERSION,
)
from .pending_contracts import (
    PENDING_FILE_INVENTORY_SCHEMA_VERSION,
    PENDING_PUBLISH_INVENTORY_PROGRESS_SCHEMA_VERSION,
    _json_safe,
    _pending_publish_preview_dto,
    int_value,
)
from .pending_policy_parts.status_rules import (
    row_operator_guidance as _row_operator_guidance,
    row_recovery_action as _row_recovery_action,
    row_recovery_class as _row_recovery_class,
)
from .pending_policy_parts.trust_fields import build_pending_publish_row_trust_fields

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_inventory import PendingPublishPreviewDto


def pending_publish_error_warning(error: str) -> list[str]:
    text = str(error or "").strip()
    return [text] if text else []


def pending_publish_inventory_progress_payload(
    *,
    rows_loaded: int,
    rows_scanned: int | None = None,
    source: str = "",
    status: str = "complete",
    detail: str = "",
) -> dict[str, Any]:
    loaded = max(0, int(rows_loaded or 0))
    scanned = max(loaded, int(rows_scanned if rows_scanned is not None else loaded))
    updated_at = datetime.now().isoformat(timespec="seconds")
    progress_detail = detail or f"Pending publish inventory scanned {scanned} row(s) and loaded {loaded} row(s)."
    bar = {
        "id": "pending_inventory",
        "label": "Pending inventory",
        "mode": "determinate",
        "percent": 100.0 if status == "complete" else 0.0,
        "status": status,
        "detail": progress_detail,
        "source": source or "pending_publish.preview",
        "updated_at": updated_at,
        "stale": False,
    }
    return {
        "schema_version": PENDING_PUBLISH_INVENTORY_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "rows_scanned": scanned,
        "rows_loaded": loaded,
        "source": source,
        "detail": progress_detail,
        "updated_at": updated_at,
        "progress_bars": [bar],
    }


def pending_publish_file_inventory_payload(
    value: Any,
    *,
    pending_root: str = "",
    exists: bool = False,
    status: str = "unknown",
    error: str = "",
) -> dict[str, Any]:
    if isinstance(value, Mapping):
        safe = _json_safe(dict(value))
        rows = safe.get("rows") if isinstance(safe.get("rows"), list) else []
        safe["rows"] = rows
        safe.setdefault("schema_version", PENDING_FILE_INVENTORY_SCHEMA_VERSION)
        safe.setdefault("pending_root", pending_root)
        safe.setdefault("exists", bool(exists))
        safe.setdefault("status", status)
        safe.setdefault("row_limit", 0)
        safe.setdefault("total_count", len(rows))
        safe.setdefault("shown_count", len(rows))
        safe.setdefault("truncated", False)
        safe.setdefault("total_bytes", 0)
        safe.setdefault("total_size_text", "0 B")
        safe.setdefault("manifest_count", 0)
        safe.setdefault("payload_like_count", 0)
        safe.setdefault("referenced_payload_count", 0)
        safe.setdefault("orphan_payload_count", 0)
        safe.setdefault("kind_counts", {})
        safe.setdefault("role_counts", {})
        safe.setdefault("summary_lines", [])
        safe.setdefault("error", error)
        return safe
    return {
        "schema_version": PENDING_FILE_INVENTORY_SCHEMA_VERSION,
        "pending_root": pending_root,
        "exists": bool(exists),
        "status": status,
        "rows": [],
        "row_limit": 0,
        "total_count": 0,
        "shown_count": 0,
        "truncated": False,
        "total_bytes": 0,
        "total_size_text": "0 B",
        "manifest_count": 0,
        "payload_like_count": 0,
        "referenced_payload_count": 0,
        "orphan_payload_count": 0,
        "kind_counts": {},
        "role_counts": {},
        "summary_lines": [
            "Pending parked file inventory:",
            f"Pending root: {pending_root or 'not resolved'}",
            f"Status: {status}",
            "Rows shown: 0",
            "Evidence boundary: directory listing only; file bytes were not read and no files were changed.",
        ],
        "error": error,
    }


def pending_publish_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in value or []:
        if not isinstance(row, dict):
            continue
        safe = _json_safe(dict(row))
        safe["row_key"] = pending_publish_row_key(safe)
        safe["issue_summary"] = pending_publish_row_issue_summary(safe)
        safe["ready_to_drain"] = pending_publish_row_ready_to_drain(safe)
        safe.update(pending_publish_row_diagnostics(safe))
        rows.append(safe)
    return rows


def pending_publish_row_key(row: Mapping[str, Any]) -> str:
    return "\x1f".join(
        [
            str(row.get("manifest_path") or ""),
            str(row.get("local_file") or ""),
            str(row.get("server_out") or ""),
            str(row.get("state") or ""),
        ]
    ).casefold()


def pending_publish_preview_fields(raw: Mapping[str, Any]) -> dict[str, Any]:
    from .pending_drain_confidence import pending_publish_drain_confidence_payload

    error = str(raw.get("error") or "").strip()
    pending_root = str(raw.get("pending_root") or "")
    exists = bool(raw.get("exists", False))
    rows = pending_publish_rows(raw.get("rows"))
    health_rows = pending_publish_rows(raw.get("health_rows"))
    issue_count = sum(1 for row in rows if not pending_publish_row_ready_to_drain(row))
    row_count = int_value(raw.get("count"))
    rows_scanned = row_count or len(rows)
    progress = pending_publish_inventory_progress_payload(
        rows_loaded=len(rows),
        rows_scanned=rows_scanned,
        source=pending_root,
        status="blocked" if error else "complete",
        detail=error or "",
    )
    fields = {
        "pending_root": pending_root,
        "exists": exists,
        "rows": rows,
        "health_rows": health_rows,
        "count": row_count,
        "payload_count": int_value(raw.get("payload_count")),
        "total_bytes": int_value(raw.get("total_bytes")),
        "total_size_text": str(raw.get("total_size_text") or "0 B"),
        "missing_local_count": int_value(raw.get("missing_local_count")),
        "health_count": int_value(raw.get("health_count")),
        "state_counts": count_pending_publish_rows(rows, "state"),
        "route_counts": count_pending_publish_rows(rows, "route"),
        "diagnostic_status_counts": count_pending_publish_rows(rows, "diagnostic_status"),
        "diagnostic_status_state_counts": count_pending_publish_rows(rows, "diagnostic_status_state"),
        "diagnostic_severity_counts": count_pending_publish_rows(rows, "diagnostic_severity", default="ok"),
        "operator_trust_state_counts": count_pending_publish_rows(rows, "operator_trust_state"),
        "recovery_class_counts": count_pending_publish_rows(rows, "recovery_class"),
        "recommended_open_target_counts": count_pending_publish_row_targets(rows),
        "available_open_target_counts": count_pending_publish_row_targets(rows, "available_open_targets"),
        "issue_count": issue_count,
        "ready_count": max(0, len(rows) - issue_count),
        "orphan_payload_count": sum(1 for row in rows if str(row.get("state") or "").casefold() == "orphan_payload"),
        "invalid_manifest_count": sum(1 for row in rows if str(row.get("diagnostic_status") or "").casefold() in {"invalid_manifest", "unreadable_manifest"}),
        "missing_sidecar_count": sum(int_value(row.get("missing_sidecar_count")) for row in rows),
        "retry_exhausted_count": sum(1 for row in rows if pending_publish_row_retry_exhausted(row)),
        "retry_budget": pending_publish_retry_budget_payload(rows),
        "recovery_summary": pending_publish_recovery_summary(rows, raw),
        "drain_summary": _json_safe(raw.get("drain_summary") or {}),
        "file_inventory": pending_publish_file_inventory_payload(
            raw.get("file_inventory"),
            pending_root=pending_root,
            exists=exists,
            status="blocked" if error else "complete" if exists else "missing",
            error=error,
        ),
        "inventory_progress": progress,
        "progress_bars": progress["progress_bars"],
        "warnings": pending_publish_error_warning(error),
        "error": error,
    }
    fields["drain_confidence"] = pending_publish_drain_confidence_payload(fields, rows)
    return fields


def count_pending_publish_rows(rows: list[dict[str, Any]], key: str, *, default: str = "unknown") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or default).strip() or default
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_pending_publish_row_targets(rows: list[dict[str, Any]], key: str = "recommended_open_targets") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for target in row.get(key) or []:
            target_key = str(target or "").strip() or "unknown"
            counts[target_key] = counts.get(target_key, 0) + 1
    return dict(sorted(counts.items()))


def pending_publish_row_ready_to_drain(row: Mapping[str, Any]) -> bool:
    state = str(row.get("state") or "").casefold()
    schema_version = str(row.get("schema_version") or "").strip()
    return not (
        row.get("error")
        or pending_publish_row_retry_exhausted(row)
        or row.get("local_exists") is False
        or int_value(row.get("missing_sidecar_count")) > 0
        or schema_version != PENDING_PUSH_MANIFEST_SCHEMA_VERSION
        or state not in PENDING_PUSH_MANIFEST_DRAINABLE_STATES
        or state in {"orphan_payload", "invalid_manifest", "unreadable_manifest", "invalid_contract", "unreadable"}
        or str(row.get("drain_attempt_status") or "").casefold() == "in_progress"
    )


def pending_publish_row_issue_summary(row: Mapping[str, Any]) -> str:
    issues: list[str] = []
    state = str(row.get("state") or "").casefold()
    if row.get("error"):
        issues.append(str(row.get("error")))
    if pending_publish_row_retry_exhausted(row):
        issues.append(
            f"retry count exhausted ({pending_publish_row_retry_count(row)}/{pending_publish_row_retry_limit(row)})"
        )
    if row.get("local_exists") is False:
        issues.append("local payload missing")
    if str(row.get("copy_proof_state") or "").casefold() == "legacy_weak_copy_proof":
        issues.append("legacy manifest has no SHA-256 copy proof")
    if str(row.get("drain_attempt_status") or "").casefold() == "in_progress":
        issues.append("a drain attempt is recorded in progress")
    missing_sidecars = int_value(row.get("missing_sidecar_count"))
    if missing_sidecars:
        issues.append(f"{missing_sidecars} sidecar(s) missing")
    if state == "orphan_payload":
        issues.append("payload has no manifest")
    elif state in {"invalid_manifest", "invalid_contract"}:
        issues.append("manifest is invalid")
    elif state in {"unreadable_manifest", "unreadable"}:
        issues.append("manifest is unreadable")
    schema_version = str(row.get("schema_version") or "").strip()
    if schema_version and schema_version != PENDING_PUSH_MANIFEST_SCHEMA_VERSION and "Legacy pending manifest" not in "; ".join(issues):
        issues.append("manifest schema is not drainable")
    if schema_version == PENDING_PUSH_MANIFEST_SCHEMA_VERSION and state and state not in PENDING_PUSH_MANIFEST_DRAINABLE_STATES:
        issues.append(f"manifest state '{state}' is not drainable")
    return "; ".join(issues)


def pending_publish_row_available_open_targets(row: Mapping[str, Any]) -> list[str]:
    targets: list[str] = []
    local_file = str(row.get("local_file") or "").strip()
    if local_file:
        if row.get("local_exists") is not False and Path(local_file).suffix.lower() in MEDIA_FILE_SUFFIXES:
            targets.append("play_local_file")
        targets.append("local_file")
    if row.get("manifest_path"):
        targets.append("manifest")
    if row.get("server_out"):
        targets.append("destination_folder")
    if row.get("source_path"):
        targets.append("source_folder")
    return targets


def pending_publish_row_diagnostic_status(row: Mapping[str, Any]) -> str:
    state = str(row.get("state") or "").casefold()
    error = str(row.get("error") or "")
    schema_version = str(row.get("schema_version") or "").strip()
    if state in {"orphan_payload"}:
        return state
    if state in {"invalid_manifest", "invalid_contract"}:
        return "invalid_manifest"
    if state in {"unreadable_manifest", "unreadable"}:
        return "unreadable_manifest"
    if schema_version != PENDING_PUSH_MANIFEST_SCHEMA_VERSION:
        return "invalid_manifest"
    if state not in PENDING_PUSH_MANIFEST_DRAINABLE_STATES:
        return "invalid_manifest"
    if pending_publish_row_retry_exhausted(row):
        return "retry_exhausted"
    if "Duplicate pending publish" in error:
        return "duplicate_target"
    if row.get("local_exists") is False:
        return "missing_payload"
    if int_value(row.get("missing_sidecar_count")) > 0:
        return "missing_sidecar"
    if error.strip():
        return "row_error"
    return "ready"


def pending_publish_row_drain_recommendation(status: str) -> str:
    if status == "ready":
        return "ready_to_drain"
    if status in {"duplicate_target", "invalid_manifest", "unreadable_manifest", "missing_payload", "retry_exhausted", "row_error"}:
        return "do_not_drain"
    return "review_before_drain"


def pending_publish_row_diagnostic_severity(status: str) -> str:
    if status == "ready":
        return "ok"
    if status in {"orphan_payload", "missing_sidecar"}:
        return "warning"
    return "error"


def pending_publish_row_diagnostic_status_state(
    row: Mapping[str, Any],
    status: str,
    severity: str,
    recommendation: str,
) -> str:
    normalized_status = str(status or "").strip().casefold()
    normalized_severity = str(severity or "").strip().casefold()
    normalized_recommendation = str(recommendation or "").strip().casefold()
    if normalized_recommendation == "do_not_drain" or normalized_severity in {"error", "critical"} or row.get("local_exists") is False:
        return "failed"
    if normalized_severity == "warning" or normalized_recommendation != "ready_to_drain":
        return "warning"
    if normalized_status == "ready":
        return "match"
    return "warning"


def pending_publish_row_operator_guidance(status: str) -> str:
    return _row_operator_guidance(status)


def pending_publish_row_recovery_class(status: str) -> str:
    return _row_recovery_class(status)


def pending_publish_row_recovery_action(status: str) -> str:
    return _row_recovery_action(status)


def pending_publish_row_evidence_fields(row: Mapping[str, Any], status: str) -> list[str]:
    fields: list[str] = []
    for key in ("manifest_path", "local_file", "server_out", "source_path"):
        if row.get(key):
            fields.append(key)
    if int_value(row.get("missing_sidecar_count")) > 0 or status == "missing_sidecar":
        fields.append("sidecar_paths")
    if status == "retry_exhausted":
        fields.append("retry_count")
    if row.get("error"):
        fields.append("error")
    return fields or ["manifest_path", "local_file", "server_out"]


def pending_publish_row_recommended_open_targets(row: Mapping[str, Any], status: str) -> list[str]:
    available = set(pending_publish_row_available_open_targets(row))
    priority_by_status = {
        "ready": ["play_local_file", "local_file", "manifest", "destination_folder"],
        "missing_payload": ["manifest", "destination_folder", "source_folder"],
        "missing_sidecar": ["manifest", "local_file", "source_folder"],
        "orphan_payload": ["local_file"],
        "invalid_manifest": ["manifest", "local_file"],
        "unreadable_manifest": ["manifest", "local_file"],
        "duplicate_target": ["manifest", "destination_folder", "local_file"],
        "retry_exhausted": ["manifest", "local_file", "destination_folder"],
        "row_error": ["manifest", "local_file", "destination_folder"],
    }
    ordered = [target for target in priority_by_status.get(status, ["manifest", "local_file"]) if target in available]
    return ordered or sorted(available)


def pending_publish_row_diagnostics(row: Mapping[str, Any]) -> dict[str, Any]:
    status = pending_publish_row_diagnostic_status(row)
    severity = pending_publish_row_diagnostic_severity(status)
    recommendation = pending_publish_row_drain_recommendation(status)
    fields = {
        "diagnostic_status": status,
        "diagnostic_status_state": pending_publish_row_diagnostic_status_state(row, status, severity, recommendation),
        "diagnostic_severity": severity,
        "drain_recommendation": recommendation,
        "operator_guidance": pending_publish_row_operator_guidance(status),
        "recovery_class": pending_publish_row_recovery_class(status),
        "recovery_action": pending_publish_row_recovery_action(status),
        "evidence_fields": pending_publish_row_evidence_fields(row, status),
        "available_open_targets": pending_publish_row_available_open_targets(row),
        "recommended_open_targets": pending_publish_row_recommended_open_targets(row, status),
        "retry_count": pending_publish_row_retry_count(row),
        "retry_limit": pending_publish_row_retry_limit(row),
        "retry_exhausted": pending_publish_row_retry_exhausted(row),
        "dead_letter_status": pending_publish_row_dead_letter_status(row),
    }
    fields.update(pending_publish_row_trust_fields(row, fields))
    return fields


def pending_publish_row_trust_fields(row: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    return build_pending_publish_row_trust_fields(
        row,
        diagnostics,
        missing_sidecars=int_value(row.get("missing_sidecar_count")),
        ready_to_drain=bool(diagnostics.get("ready_to_drain") or pending_publish_row_ready_to_drain(row)),
    )


def pending_publish_row_is_recovery_blocker(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("drain_recommendation") or "").casefold() == "do_not_drain"
        or str(row.get("diagnostic_severity") or "").casefold() == "error"
    )


def pending_publish_row_retry_count(row: Mapping[str, Any]) -> int:
    return max(0, int_value(row.get("retry_count")))


def pending_publish_row_retry_limit(row: Mapping[str, Any]) -> int:
    return max(1, int_value(row.get("retry_limit")) or PENDING_PUSH_RETRY_LIMIT)


def pending_publish_row_retry_exhausted(row: Mapping[str, Any]) -> bool:
    if bool(row.get("retry_exhausted")):
        return True
    return pending_publish_row_retry_count(row) >= pending_publish_row_retry_limit(row)


def pending_publish_row_dead_letter_status(row: Mapping[str, Any]) -> str:
    if pending_publish_row_retry_exhausted(row):
        return "retry_exhausted_review"
    if pending_publish_row_retry_count(row) > 0:
        return "retrying"
    return "active"


def pending_publish_retry_budget_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    exhausted = [row for row in rows if pending_publish_row_retry_exhausted(row)]
    retrying = [row for row in rows if pending_publish_row_retry_count(row) > 0 and row not in exhausted]
    max_retry_count = max((pending_publish_row_retry_count(row) for row in rows), default=0)
    status = "blocked" if exhausted else "review" if retrying else "ready"
    return {
        "schema_version": "desktop_pending_publish_retry_budget.v1",
        "status": status,
        "retry_limit": PENDING_PUSH_RETRY_LIMIT,
        "row_count": len(rows),
        "retrying_count": len(retrying),
        "exhausted_count": len(exhausted),
        "max_retry_count": max_retry_count,
        "summary_lines": [
            f"Pending publish retry budget: status={status}; exhausted={len(exhausted)}; retrying={len(retrying)}; limit={PENDING_PUSH_RETRY_LIMIT}.",
            "Retry-exhausted rows stay parked and require operator review; this preview does not move, delete, drain, or repair files.",
        ],
    }


def pending_publish_recovery_summary(rows: list[dict[str, Any]], raw: Mapping[str, Any]) -> dict[str, Any]:
    if raw.get("error"):
        return {
            "status": "unavailable",
            "primary_action": "Open Diagnostics > Pending Publish, Last Stderr, and Run Logs before retrying a drain.",
            "blocker_count": 1,
            "review_count": 0,
            "ready_count": 0,
            "class_counts": {},
            "next_steps": [
                "Do not drain while the pending publish scan is unavailable.",
                "Confirm whether the pending root is locked, disconnected, or malformed.",
            ],
        }
    if not rows:
        return {
            "status": "empty",
            "primary_action": "No parked rows are waiting; compare Completed and Run Logs before reprocessing expected outputs.",
            "blocker_count": 0,
            "review_count": 0,
            "ready_count": 0,
            "class_counts": {},
            "next_steps": [
                "Do not treat an empty pending folder as proof of missing outputs.",
                "Use Completed history and diagnostics logs when an expected file is not visible.",
            ],
        }
    class_counts = count_pending_publish_rows(rows, "recovery_class")
    blockers = [row for row in rows if pending_publish_row_is_recovery_blocker(row)]
    reviews = [
        row for row in rows
        if not pending_publish_row_is_recovery_blocker(row)
        and str(row.get("recovery_class") or "") != "ready_to_validate"
    ]
    ready = [row for row in rows if str(row.get("recovery_class") or "") == "ready_to_validate"]
    if blockers:
        status = "blocked"
        primary_action = "Do not drain; inspect blocker rows and backend diagnostics evidence first."
    elif reviews:
        status = "review"
        primary_action = "Review warning rows and evidence before using Drain Parked Outputs."
    else:
        status = "ready"
        primary_action = "Rows look drain-ready; Drain Parked Outputs remains the authoritative backend validation path."
    next_steps: list[str] = []
    if class_counts.get("manifest_repair"):
        next_steps.append("Open unreadable/invalid manifests and Last Stderr before any drain retry.")
    if class_counts.get("payload_missing"):
        next_steps.append("Confirm missing parked payloads against destination/source folders before rerun.")
    if class_counts.get("sidecar_missing"):
        next_steps.append("Compare manifest sidecar paths with disk before draining.")
    if class_counts.get("duplicate_resolution"):
        next_steps.append("Resolve duplicate pending targets before publishing parked outputs.")
    if class_counts.get("orphan_payload_review"):
        next_steps.append("Classify orphan payloads before cleanup, rerun, or manual move.")
    if not next_steps:
        next_steps.append(primary_action)
    return {
        "status": status,
        "primary_action": primary_action,
        "blocker_count": len(blockers),
        "review_count": len(reviews),
        "ready_count": len(ready),
        "class_counts": class_counts,
        "next_steps": next_steps[:5],
    }


def pending_publish_scan_exception_fields(pending_root: Any, exists: bool, error: Exception) -> dict[str, Any]:
    detail = f"Pending publish scan failed: {error}"
    progress = pending_publish_inventory_progress_payload(
        rows_loaded=0,
        rows_scanned=0,
        source=str(pending_root or ""),
        status="blocked",
        detail=detail,
    )
    return {
        "pending_root": str(pending_root or ""),
        "exists": bool(exists),
        "error": str(error),
        "file_inventory": pending_publish_file_inventory_payload(
            None,
            pending_root=str(pending_root or ""),
            exists=bool(exists),
            status="blocked",
            error=str(error),
        ),
        "inventory_progress": progress,
        "progress_bars": progress["progress_bars"],
        "warnings": [detail],
    }


def pending_publish_preview_result(raw: Mapping[str, Any]) -> PendingPublishPreviewDto:
    return _pending_publish_preview_dto(**pending_publish_preview_fields(raw))


__all__ = [
    "int_value",
    "pending_publish_error_warning",
    "pending_publish_inventory_progress_payload",
    "pending_publish_file_inventory_payload",
    "pending_publish_rows",
    "pending_publish_row_key",
    "pending_publish_preview_fields",
    "count_pending_publish_rows",
    "count_pending_publish_row_targets",
    "pending_publish_row_ready_to_drain",
    "pending_publish_row_issue_summary",
    "pending_publish_row_available_open_targets",
    "pending_publish_row_diagnostic_status",
    "pending_publish_row_drain_recommendation",
    "pending_publish_row_diagnostic_severity",
    "pending_publish_row_diagnostic_status_state",
    "pending_publish_row_operator_guidance",
    "pending_publish_row_recovery_class",
    "pending_publish_row_recovery_action",
    "pending_publish_row_evidence_fields",
    "pending_publish_row_recommended_open_targets",
    "pending_publish_row_diagnostics",
    "pending_publish_row_trust_fields",
    "pending_publish_row_is_recovery_blocker",
    "pending_publish_row_retry_count",
    "pending_publish_row_retry_limit",
    "pending_publish_row_retry_exhausted",
    "pending_publish_row_dead_letter_status",
    "pending_publish_retry_budget_payload",
    "pending_publish_recovery_summary",
    "pending_publish_scan_exception_fields",
    "pending_publish_preview_result",
]
