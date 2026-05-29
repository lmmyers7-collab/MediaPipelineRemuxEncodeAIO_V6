from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult
    from mediapipeline_desktop_app.application.dto_inventory import PendingPublishPreviewDto


def _json_safe(value: Any) -> Any:
    from mediapipeline_desktop_app.application.dto_base import json_safe

    return json_safe(value)


def _command_result(**fields: Any) -> "CommandResult":
    from mediapipeline_desktop_app.application.dto_commands import CommandResult

    return CommandResult(**fields)


def _pending_publish_preview_dto(**fields: Any) -> "PendingPublishPreviewDto":
    from mediapipeline_desktop_app.application.dto_inventory import PendingPublishPreviewDto

    return PendingPublishPreviewDto(**fields)


PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE = "Pending publish service is not available."
PENDING_PUBLISH_INVALID_RESULT_MESSAGE = "Pending publish service returned an invalid result."
PENDING_PUBLISH_OPEN_COMMAND = "pending_publish.open"
PENDING_PUBLISH_RECOVERY_PLAN_COMMAND = "pending_publish.recovery_plan_dry_run"
PENDING_PUBLISH_RECOVERY_PLAN_SCHEMA_VERSION = "pending_publish_recovery_plan.v1"
PENDING_PUBLISH_INVENTORY_PROGRESS_SCHEMA_VERSION = "desktop_pending_publish_inventory_progress.v1"
PENDING_PUBLISH_OPEN_TARGETS = {
    "local_file": "parked local payload",
    "manifest": "pending manifest",
    "destination_folder": "destination folder",
    "source_folder": "source folder",
}


def int_value(value: Any) -> int:
    try:
        if value not in (None, ""):
            return int(float(value))
    except (TypeError, ValueError):
        return 0
    return 0


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
    error = str(raw.get("error") or "").strip()
    rows = pending_publish_rows(raw.get("rows"))
    health_rows = pending_publish_rows(raw.get("health_rows"))
    issue_count = sum(1 for row in rows if not pending_publish_row_ready_to_drain(row))
    row_count = int_value(raw.get("count"))
    rows_scanned = row_count or len(rows)
    progress = pending_publish_inventory_progress_payload(
        rows_loaded=len(rows),
        rows_scanned=rows_scanned,
        source=str(raw.get("pending_root") or ""),
        status="blocked" if error else "complete",
        detail=error or "",
    )
    return {
        "pending_root": str(raw.get("pending_root") or ""),
        "exists": bool(raw.get("exists", False)),
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
        "recovery_summary": pending_publish_recovery_summary(rows, raw),
        "drain_summary": _json_safe(raw.get("drain_summary") or {}),
        "inventory_progress": progress,
        "progress_bars": progress["progress_bars"],
        "warnings": pending_publish_error_warning(error),
        "error": error,
    }


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
    return not (
        row.get("error")
        or row.get("local_exists") is False
        or int_value(row.get("missing_sidecar_count")) > 0
        or state in {"orphan_payload", "invalid_manifest", "unreadable_manifest", "invalid_contract", "unreadable"}
    )


def pending_publish_row_issue_summary(row: Mapping[str, Any]) -> str:
    issues: list[str] = []
    state = str(row.get("state") or "").casefold()
    if row.get("error"):
        issues.append(str(row.get("error")))
    if row.get("local_exists") is False:
        issues.append("local payload missing")
    missing_sidecars = int_value(row.get("missing_sidecar_count"))
    if missing_sidecars:
        issues.append(f"{missing_sidecars} sidecar(s) missing")
    if state == "orphan_payload":
        issues.append("payload has no manifest")
    elif state in {"invalid_manifest", "invalid_contract"}:
        issues.append("manifest is invalid")
    elif state in {"unreadable_manifest", "unreadable"}:
        issues.append("manifest is unreadable")
    return "; ".join(issues)


def pending_publish_row_available_open_targets(row: Mapping[str, Any]) -> list[str]:
    targets: list[str] = []
    if row.get("local_file"):
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
    if state in {"orphan_payload"}:
        return state
    if state in {"invalid_manifest", "invalid_contract"}:
        return "invalid_manifest"
    if state in {"unreadable_manifest", "unreadable"}:
        return "unreadable_manifest"
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
    if status in {"duplicate_target", "invalid_manifest", "unreadable_manifest", "missing_payload", "row_error"}:
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
    guidance = {
        "ready": "Ready-looking row; backend drain still performs final publish validation.",
        "missing_payload": "Parked media file is missing. Open the manifest and destination/source folders before retrying or reprocessing.",
        "missing_sidecar": "One or more sidecars referenced by the manifest are missing. Review the manifest and payload before drain.",
        "orphan_payload": "Payload has no manifest. Confirm whether it is leftover from a failed parking or manual copy before cleanup or retry.",
        "invalid_manifest": "Manifest is invalid. Regenerate or repair from pipeline logs before drain.",
        "unreadable_manifest": "Manifest could not be read. Check file locking, permissions, and JSON validity before drain.",
        "duplicate_target": "Multiple pending manifests reference the same payload or destination. Resolve duplicates before drain.",
        "row_error": "Pending row has a backend-reported error. Inspect manifest, payload, and run logs before drain.",
    }
    return guidance.get(status, "Review this pending row before drain.")


def pending_publish_row_recovery_class(status: str) -> str:
    classes = {
        "ready": "ready_to_validate",
        "missing_payload": "payload_missing",
        "missing_sidecar": "sidecar_missing",
        "orphan_payload": "orphan_payload_review",
        "invalid_manifest": "manifest_repair",
        "unreadable_manifest": "manifest_repair",
        "duplicate_target": "duplicate_resolution",
        "row_error": "manual_review",
    }
    return classes.get(status, "manual_review")


def pending_publish_row_recovery_action(status: str) -> str:
    actions = {
        "ready": "Use Publish Parked Outputs only after the current pending scan still shows this row ready.",
        "missing_payload": "Open the manifest and destination/source folders, then confirm whether the parked payload was moved, deleted, or never written.",
        "missing_sidecar": "Open the manifest and payload, then compare expected sidecar paths against disk before draining.",
        "orphan_payload": "Open the orphan payload and run logs before deciding whether it is a leftover, manual copy, or failed parking artifact.",
        "invalid_manifest": "Repair or regenerate the pending manifest from logs/sidecar evidence before another drain attempt.",
        "unreadable_manifest": "Check locking, permissions, and JSON validity before another drain attempt.",
        "duplicate_target": "Compare duplicate manifests and destinations before draining; one row may be stale or manually copied.",
        "row_error": "Inspect manifest, payload, destination, Last Stderr, and Run Logs before another drain attempt.",
    }
    return actions.get(status, "Review this row with Pending Publish diagnostics before draining.")


def pending_publish_row_evidence_fields(row: Mapping[str, Any], status: str) -> list[str]:
    fields: list[str] = []
    for key in ("manifest_path", "local_file", "server_out", "source_path"):
        if row.get(key):
            fields.append(key)
    if int_value(row.get("missing_sidecar_count")) > 0 or status == "missing_sidecar":
        fields.append("sidecar_paths")
    if row.get("error"):
        fields.append("error")
    return fields or ["manifest_path", "local_file", "server_out"]


def pending_publish_row_recommended_open_targets(row: Mapping[str, Any], status: str) -> list[str]:
    available = set(pending_publish_row_available_open_targets(row))
    priority_by_status = {
        "ready": ["local_file", "manifest", "destination_folder"],
        "missing_payload": ["manifest", "destination_folder", "source_folder"],
        "missing_sidecar": ["manifest", "local_file", "source_folder"],
        "orphan_payload": ["local_file"],
        "invalid_manifest": ["manifest", "local_file"],
        "unreadable_manifest": ["manifest", "local_file"],
        "duplicate_target": ["manifest", "destination_folder", "local_file"],
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
    }
    fields.update(pending_publish_row_trust_fields(row, fields))
    return fields


def pending_publish_row_trust_fields(row: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    status = str(diagnostics.get("diagnostic_status") or "unknown").strip()
    severity = str(diagnostics.get("diagnostic_severity") or "unknown").strip().casefold()
    recommendation = str(diagnostics.get("drain_recommendation") or "review").strip().casefold()
    state = str(row.get("state") or "").strip().casefold()
    issues: list[str] = []
    if recommendation == "do_not_drain":
        issues.append("backend marked do_not_drain")
    if severity == "error":
        issues.append("diagnostic severity is error")
    if row.get("local_exists") is False:
        issues.append("local payload missing")
    missing_sidecars = int_value(row.get("missing_sidecar_count"))
    if missing_sidecars > 0:
        issues.append(f"{missing_sidecars} missing sidecar{'s' if missing_sidecars != 1 else ''}")
    if state in {"invalid_manifest", "unreadable_manifest", "invalid_contract", "unreadable"} or status in {"invalid_manifest", "unreadable_manifest"}:
        issues.append("manifest unreadable or invalid")
    if state == "orphan_payload" or status == "orphan_payload":
        issues.append("orphan payload")
    if row.get("error"):
        issues.append(f"row error: {row.get('error')}")

    if recommendation == "do_not_drain" or severity == "error":
        trust_state = "do-not-drain"
        safe_action = "Do not drain; inspect pending manifest/payload/sidecar evidence, Last Stderr, and Run Logs first."
    elif issues:
        trust_state = "review-before-drain"
        safe_action = "Review backend-selected row targets before Publish Parked Outputs; backend drain validation remains authoritative."
    elif diagnostics.get("ready_to_drain") or pending_publish_row_ready_to_drain(row):
        trust_state = "ready-looking"
        safe_action = "Use only backend-owned Publish Parked Outputs after page-level validation still agrees."
    else:
        trust_state = "review-before-drain"
        safe_action = "Treat this row as review-needed until a refreshed pending scan marks it ready."

    proof = [
        f"diagnostic={status} / {diagnostics.get('diagnostic_severity') or 'unknown'}",
        f"drain={diagnostics.get('drain_recommendation') or 'review'}",
        f"recovery={diagnostics.get('recovery_class') or 'manual_review'}",
        f"payload={row.get('local_file') or 'not reported'}",
        f"manifest={row.get('manifest_path') or 'not reported'}",
        f"destination={row.get('server_out') or 'not reported'}",
    ]
    diagnostics_targets = ["pending_publish", "run_logs", "last_stderr_log"]
    if trust_state == "do-not-drain" or "manifest unreadable or invalid" in issues:
        diagnostics_targets.append("state")
    return {
        "operator_trust_state": trust_state,
        "primary_concern": "; ".join(issues) if issues else "row has no blocker in the loaded pending publish scan",
        "safe_next_action": safe_action,
        "unsafe_if_ignored": "Draining review or blocker rows can lose parked output context, overwrite the wrong destination, or strand payload/sidecar evidence.",
        "proof_summary": proof,
        "recommended_diagnostics_targets": diagnostics_targets,
    }


def pending_publish_row_is_recovery_blocker(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("drain_recommendation") or "").casefold() == "do_not_drain"
        or str(row.get("diagnostic_severity") or "").casefold() == "error"
    )


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
        primary_action = "Review warning rows and evidence before using Publish Parked Outputs."
    else:
        status = "ready"
        primary_action = "Rows look drain-ready; Publish Parked Outputs remains the authoritative backend validation path."
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
        "inventory_progress": progress,
        "progress_bars": progress["progress_bars"],
        "warnings": [detail],
    }


def pending_publish_service_unavailable_result() -> PendingPublishPreviewDto:
    progress = pending_publish_inventory_progress_payload(
        rows_loaded=0,
        rows_scanned=0,
        status="blocked",
        detail=PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
    )
    return _pending_publish_preview_dto(
        inventory_progress=progress,
        progress_bars=progress["progress_bars"],
        warnings=[PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE],
    )


def pending_publish_scan_exception_result(pending_root: Any, exists: bool, error: Exception) -> PendingPublishPreviewDto:
    return _pending_publish_preview_dto(
        **pending_publish_scan_exception_fields(pending_root, exists, error)
    )


def pending_publish_invalid_result() -> PendingPublishPreviewDto:
    progress = pending_publish_inventory_progress_payload(
        rows_loaded=0,
        rows_scanned=0,
        status="blocked",
        detail=PENDING_PUBLISH_INVALID_RESULT_MESSAGE,
    )
    return _pending_publish_preview_dto(
        inventory_progress=progress,
        progress_bars=progress["progress_bars"],
        warnings=[PENDING_PUBLISH_INVALID_RESULT_MESSAGE],
    )


def pending_publish_preview_result(raw: Mapping[str, Any]) -> PendingPublishPreviewDto:
    return _pending_publish_preview_dto(**pending_publish_preview_fields(raw))


def normalize_pending_publish_open_target(value: Any) -> str:
    return str(value or "").strip().casefold()


def pending_publish_open_target_label(target: str) -> str | None:
    return PENDING_PUBLISH_OPEN_TARGETS.get(target)


def normalize_pending_publish_row_key(value: Any) -> str:
    return str(value or "").strip(" \t\r\n").casefold()


def pending_publish_open_allowed_targets_text() -> str:
    return f"Allowed targets: {', '.join(sorted(PENDING_PUBLISH_OPEN_TARGETS))}"


def normalize_pending_publish_recovery_scope(value: Any, row_key: str = "") -> str:
    text = str(value or "").strip().casefold()
    if text in {"all", "selected"}:
        return text
    return "selected" if row_key else "all"


def pending_publish_recovery_plan_action(row: Mapping[str, Any]) -> str:
    status = str(row.get("diagnostic_status") or "").strip().casefold()
    actions = {
        "ready": "validate_with_backend_drain",
        "missing_payload": "locate_payload_or_reprocess_source",
        "missing_sidecar": "compare_manifest_sidecars_before_drain",
        "orphan_payload": "classify_orphan_payload_before_cleanup_or_rerun",
        "invalid_manifest": "repair_or_regenerate_manifest_from_logs",
        "unreadable_manifest": "unlock_or_repair_manifest_json",
        "duplicate_target": "resolve_duplicate_pending_targets",
        "row_error": "manual_review_with_logs",
    }
    return actions.get(status, "manual_review_with_pending_diagnostics")


def pending_publish_recovery_plan_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "row_key": str(row.get("row_key") or pending_publish_row_key(row)),
        "state": str(row.get("state") or ""),
        "diagnostic_status": str(row.get("diagnostic_status") or "unknown"),
        "diagnostic_severity": str(row.get("diagnostic_severity") or "unknown"),
        "drain_recommendation": str(row.get("drain_recommendation") or "review"),
        "operator_trust_state": str(row.get("operator_trust_state") or "review-before-drain"),
        "recovery_class": str(row.get("recovery_class") or "manual_review"),
        "planned_action": pending_publish_recovery_plan_action(row),
        "dry_run_only": True,
        "would_mutate": False,
        "safe_next_action": str(row.get("safe_next_action") or row.get("operator_guidance") or "Review pending publish diagnostics before drain."),
        "unsafe_if_ignored": str(row.get("unsafe_if_ignored") or "Running drain without evidence review can strand payloads or publish the wrong target."),
        "primary_concern": str(row.get("primary_concern") or row.get("issue_summary") or ""),
        "issue_summary": str(row.get("issue_summary") or row.get("error") or ""),
        "proof_summary": _json_safe(row.get("proof_summary") or []),
        "evidence_fields": _json_safe(row.get("evidence_fields") or []),
        "recommended_open_targets": _json_safe(row.get("recommended_open_targets") or []),
        "recommended_diagnostics_targets": _json_safe(row.get("recommended_diagnostics_targets") or ["pending_publish", "run_logs", "last_stderr_log"]),
        "local_file": str(row.get("local_file") or ""),
        "manifest_path": str(row.get("manifest_path") or ""),
        "server_out": str(row.get("server_out") or ""),
        "source_path": str(row.get("source_path") or ""),
    }


def pending_publish_recovery_plan_action_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        action = str(row.get("planned_action") or "manual_review_with_pending_diagnostics")
        counts[action] = counts.get(action, 0) + 1
    return dict(sorted(counts.items()))


def pending_publish_recovery_plan_summary_lines(data: Mapping[str, Any]) -> list[str]:
    rows = int_value(data.get("row_count"))
    blockers = int_value(data.get("blocker_count"))
    reviews = int_value(data.get("review_count"))
    ready = int_value(data.get("ready_count"))
    lines = [
        f"Dry-run recovery plan scope: {data.get('scope') or 'all'}",
        f"Rows planned: {rows}",
        f"Blockers/review/ready: {blockers} / {reviews} / {ready}",
        "Mutation guardrail: this plan does not move, delete, drain, repair, rewrite, or publish files.",
    ]
    if blockers:
        lines.append("Safe next action: do not drain; inspect blocker rows and diagnostics evidence first.")
    elif reviews:
        lines.append("Safe next action: review warning rows before using backend-owned Publish Parked Outputs.")
    elif ready:
        lines.append("Safe next action: rows look ready; Publish Parked Outputs remains the authoritative backend validation path.")
    else:
        lines.append("Safe next action: no parked rows were included in this plan.")
    return lines


def pending_publish_recovery_plan_data(rows: list[dict[str, Any]], *, scope: str, row_key: str) -> dict[str, Any]:
    plan_rows = [pending_publish_recovery_plan_row(row) for row in rows]
    blocker_count = sum(1 for row in rows if pending_publish_row_is_recovery_blocker(row))
    review_count = sum(
        1
        for row in rows
        if not pending_publish_row_is_recovery_blocker(row)
        and str(row.get("operator_trust_state") or "").casefold() != "ready-looking"
        and str(row.get("recovery_class") or "").casefold() != "ready_to_validate"
    )
    ready_count = max(0, len(rows) - blocker_count - review_count)
    data: dict[str, Any] = {
        "schema_version": PENDING_PUBLISH_RECOVERY_PLAN_SCHEMA_VERSION,
        "scope": scope,
        "selected_row_key": row_key,
        "row_count": len(rows),
        "blocker_count": blocker_count,
        "review_count": review_count,
        "ready_count": ready_count,
        "action_counts": pending_publish_recovery_plan_action_counts(plan_rows),
        "rows": plan_rows,
        "dry_run_only": True,
        "would_mutate": False,
        "mutation_guardrail": "This plan does not move, delete, drain, repair, rewrite, or publish files.",
    }
    data["summary_lines"] = pending_publish_recovery_plan_summary_lines(data)
    return data


def pending_publish_recovery_plan_result(rows: list[dict[str, Any]], request: Mapping[str, Any]) -> CommandResult:
    row_key = normalize_pending_publish_row_key(request.get("row_key"))
    scope = normalize_pending_publish_recovery_scope(request.get("scope"), row_key)
    selected_rows = rows
    if scope == "selected":
        if not row_key:
            return pending_publish_recovery_plan_missing_row_result(row_key)
        selected_rows = [row for row in rows if pending_publish_row_key(row) == row_key]
        if not selected_rows:
            return pending_publish_recovery_plan_missing_row_result(row_key)
    data = pending_publish_recovery_plan_data(selected_rows, scope=scope, row_key=row_key)
    severity = "info"
    message = "Pending publish recovery plan built. No files were changed."
    warnings: list[str] = []
    if data["blocker_count"]:
        severity = "warning"
        warnings.append("One or more pending publish rows are do-not-drain blockers.")
        message = "Pending publish recovery plan found blocker rows. No files were changed."
    elif data["review_count"]:
        severity = "warning"
        warnings.append("One or more pending publish rows require review before drain.")
        message = "Pending publish recovery plan found review rows. No files were changed."
    elif data["row_count"] == 0:
        message = "Pending publish recovery plan found no parked rows. No files were changed."
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=True,
        message=message,
        severity=severity,
        warnings=warnings,
        data=data,
        refresh_hint="pending_publish",
    )


def pending_publish_recovery_plan_missing_row_result(row_key: str) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=False,
        message="Pending publish recovery plan row was not found in the current backend scan.",
        severity="warning",
        warnings=["Refresh pending publish and select the row again, or build an all-rows dry-run plan."],
        data={"row_key": row_key, "dry_run_only": True, "would_mutate": False},
        refresh_hint="pending_publish",
    )


def pending_publish_recovery_plan_service_unavailable_result() -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=False,
        message=PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
        severity="error",
        errors=[PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE],
        data={"dry_run_only": True, "would_mutate": False},
        refresh_hint="pending_publish",
    )


def pending_publish_recovery_plan_invalid_scan_result() -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=False,
        message=PENDING_PUBLISH_INVALID_RESULT_MESSAGE,
        severity="error",
        errors=[PENDING_PUBLISH_INVALID_RESULT_MESSAGE],
        data={"dry_run_only": True, "would_mutate": False},
        refresh_hint="pending_publish",
    )


def pending_publish_recovery_plan_scan_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=False,
        message=f"Pending publish scan failed before recovery plan: {exc}",
        severity="error",
        errors=[str(exc)],
        data={"dry_run_only": True, "would_mutate": False},
        refresh_hint="pending_publish",
    )


def optional_pending_publish_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    return Path(text) if text else None


def pending_publish_open_path(row: Mapping[str, Any], target: str) -> Path | None:
    if target == "local_file":
        return optional_pending_publish_path(row.get("local_file"))
    if target == "manifest":
        return optional_pending_publish_path(row.get("manifest_path"))
    if target == "destination_folder":
        destination = optional_pending_publish_path(row.get("server_out"))
        return destination.parent if destination else None
    if target == "source_folder":
        source = optional_pending_publish_path(row.get("source_path"))
        return source.parent if source else None
    return None


def pending_publish_open_result_data(target: str, row_key: str, path: Path | None = None) -> dict[str, str]:
    data = {"target": target, "row_key": row_key}
    if path is not None:
        data["path"] = str(path)
    return data


def pending_publish_open_disallowed_target_result() -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message="Pending publish open target is not allowed.",
        severity="error",
        errors=[pending_publish_open_allowed_targets_text()],
        refresh_hint="pending_publish",
    )


def pending_publish_open_missing_row_result(row_key: str) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message="Pending publish row was not found in the current backend scan.",
        severity="warning",
        warnings=["Refresh pending publish and select the row again."],
        data={"row_key": row_key},
        refresh_hint="pending_publish",
    )


def pending_publish_open_scan_exception_result(row_key: str, exc: Exception) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message=f"Pending publish scan failed before open: {exc}",
        severity="error",
        errors=[str(exc)],
        data={"row_key": row_key},
        refresh_hint="pending_publish",
    )


def pending_publish_open_missing_path_result(target: str, row_key: str) -> CommandResult:
    label = PENDING_PUBLISH_OPEN_TARGETS.get(target, target)
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message=f"No path is available for {label}.",
        severity="warning",
        warnings=[f"No path is available for target '{target}'."],
        data=pending_publish_open_result_data(target, row_key),
        refresh_hint="pending_publish",
    )


def pending_publish_open_service_unavailable_result(target: str, row_key: str, path: Path) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message="Path open service is not available.",
        severity="error",
        errors=["Path open service is not available."],
        data=pending_publish_open_result_data(target, row_key, path),
        refresh_hint="pending_publish",
    )


def pending_publish_open_exception_result(target: str, row_key: str, path: Path, exc: Exception) -> CommandResult:
    label = PENDING_PUBLISH_OPEN_TARGETS.get(target, target)
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message=f"Could not open {label}: {exc}",
        severity="error",
        errors=[str(exc)],
        data=pending_publish_open_result_data(target, row_key, path),
        refresh_hint="pending_publish",
    )


def pending_publish_open_success_result(target: str, row_key: str, path: Path) -> CommandResult:
    label = PENDING_PUBLISH_OPEN_TARGETS.get(target, target)
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=True,
        message=f"Opened {label}.",
        severity="info",
        data=pending_publish_open_result_data(target, row_key, path),
        refresh_hint="pending_publish",
    )

__all__ = [
    "PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE",
    "PENDING_PUBLISH_INVALID_RESULT_MESSAGE",
    "PENDING_PUBLISH_OPEN_COMMAND",
    "PENDING_PUBLISH_RECOVERY_PLAN_COMMAND",
    "PENDING_PUBLISH_RECOVERY_PLAN_SCHEMA_VERSION",
    "PENDING_PUBLISH_INVENTORY_PROGRESS_SCHEMA_VERSION",
    "PENDING_PUBLISH_OPEN_TARGETS",
    "int_value",
    "pending_publish_error_warning",
    "pending_publish_inventory_progress_payload",
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
    "pending_publish_recovery_summary",
    "pending_publish_scan_exception_fields",
    "pending_publish_service_unavailable_result",
    "pending_publish_scan_exception_result",
    "pending_publish_invalid_result",
    "pending_publish_preview_result",
    "normalize_pending_publish_open_target",
    "pending_publish_open_target_label",
    "normalize_pending_publish_row_key",
    "pending_publish_open_allowed_targets_text",
    "normalize_pending_publish_recovery_scope",
    "pending_publish_recovery_plan_action",
    "pending_publish_recovery_plan_row",
    "pending_publish_recovery_plan_action_counts",
    "pending_publish_recovery_plan_summary_lines",
    "pending_publish_recovery_plan_data",
    "pending_publish_recovery_plan_result",
    "pending_publish_recovery_plan_missing_row_result",
    "pending_publish_recovery_plan_service_unavailable_result",
    "pending_publish_recovery_plan_invalid_scan_result",
    "pending_publish_recovery_plan_scan_exception_result",
    "optional_pending_publish_path",
    "pending_publish_open_path",
    "pending_publish_open_result_data",
    "pending_publish_open_disallowed_target_result",
    "pending_publish_open_missing_row_result",
    "pending_publish_open_scan_exception_result",
    "pending_publish_open_missing_path_result",
    "pending_publish_open_service_unavailable_result",
    "pending_publish_open_exception_result",
    "pending_publish_open_success_result",
]
