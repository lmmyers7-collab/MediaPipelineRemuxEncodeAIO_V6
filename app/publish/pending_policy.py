from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .pending_policy_parts.status_rules import (
    recovery_plan_action as _recovery_plan_action,
    row_operator_guidance as _row_operator_guidance,
    row_recovery_action as _row_recovery_action,
    row_recovery_class as _row_recovery_class,
)
from .pending_policy_parts.trust_fields import build_pending_publish_row_trust_fields

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
PENDING_DRAIN_CONFIDENCE_SCHEMA_VERSION = "desktop_pending_drain_confidence.v1"
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
    fields = {
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
    fields["drain_confidence"] = pending_publish_drain_confidence_payload(fields, rows)
    return fields


def _pending_evidence_class(row: Mapping[str, Any]) -> str:
    recommendation = str(row.get("drain_recommendation") or "").casefold()
    severity = str(row.get("diagnostic_severity") or "").casefold()
    status = str(row.get("diagnostic_status") or "").casefold()
    state = str(row.get("state") or "").casefold()
    if recommendation == "do_not_drain":
        return "do-not-drain"
    if severity == "error":
        return "diagnostic-error"
    if row.get("local_exists") is False or status == "missing_payload":
        return "missing-payload"
    if status in {"invalid_manifest", "unreadable_manifest"} or state in {"invalid_manifest", "unreadable_manifest", "invalid_contract", "unreadable"}:
        return "manifest-invalid"
    if state == "orphan_payload" or status == "orphan_payload":
        return "orphan-payload"
    if int_value(row.get("missing_sidecar_count")) > 0 or status == "missing_sidecar":
        return "missing-sidecar"
    if severity == "warning" or recommendation == "review_before_drain" or row.get("ready_to_drain") is False:
        return "review"
    return "ready-evidence"


def _pending_evidence_rank(row: Mapping[str, Any]) -> int:
    ranks = {
        "do-not-drain": 0,
        "diagnostic-error": 1,
        "missing-payload": 2,
        "manifest-invalid": 3,
        "orphan-payload": 4,
        "missing-sidecar": 5,
        "review": 6,
        "ready-evidence": 7,
    }
    return ranks.get(_pending_evidence_class(row), 99)


def _pending_evidence_rows(rows: list[dict[str, Any]], *, include_ready: bool = False) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        evidence_class = _pending_evidence_class(row)
        if include_ready or evidence_class != "ready-evidence":
            entries.append({"row": row, "index": index, "evidenceClass": evidence_class})
    return sorted(entries, key=lambda entry: (_pending_evidence_rank(entry["row"]), entry["index"]))


def _pending_evidence_status(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> str:
    if payload.get("error"):
        return "Diagnostics first"
    if payload.get("exists") is False:
        return "No pending root"
    if not rows:
        return "No parked rows"
    evidence_rows = _pending_evidence_rows(rows)
    if any(entry["evidenceClass"] in {"do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"} for entry in evidence_rows):
        return "Blocked evidence"
    if evidence_rows:
        return "Review evidence"
    return "No blockers"


def _pending_row_has_health_issue(row: Mapping[str, Any]) -> bool:
    return bool(
        row.get("error")
        or row.get("local_exists") is False
        or int_value(row.get("missing_sidecar_count")) > 0
        or str(row.get("diagnostic_severity") or "").casefold() in {"warning", "error", "critical"}
        or str(row.get("drain_recommendation") or "").casefold() in {"do_not_drain", "review_before_drain"}
    )


def _pending_validation_status(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> str:
    if payload.get("error"):
        return "Unavailable"
    if payload.get("exists") is False:
        return "No root"
    if not rows:
        return "Empty"
    do_not_drain = [row for row in rows if str(row.get("drain_recommendation") or "").casefold() == "do_not_drain"]
    severe = [row for row in rows if str(row.get("diagnostic_severity") or "").casefold() == "error"]
    invalid = [row for row in rows if str(row.get("state") or "").casefold() in {"invalid_manifest", "unreadable_manifest"}]
    missing_payload = [row for row in rows if row.get("local_exists") is False]
    missing_sidecar = [row for row in rows if int_value(row.get("missing_sidecar_count")) > 0]
    if (
        do_not_drain
        or severe
        or invalid
        or missing_payload
        or missing_sidecar
        or int_value(payload.get("health_count")) > 0
        or int_value(payload.get("missing_local_count")) > 0
    ):
        return "Do not drain"
    warnings = [item for item in payload.get("warnings") or [] if item]
    if warnings or int_value(payload.get("issue_count")) > 0 or any(_pending_row_has_health_issue(row) for row in rows):
        return "Review"
    return "Ready"


def _pending_drain_summary_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = payload.get("drain_summary")
    return summary if isinstance(summary, Mapping) else {}


def _pending_drain_summary_status(payload: Mapping[str, Any]) -> str:
    summary = _pending_drain_summary_payload(payload)
    if summary.get("read_error"):
        return "Unreadable summary"
    if summary.get("exists") is False:
        return "No summary"
    if not summary.get("started_at") and not summary.get("completed_at"):
        return "No summary"
    if summary.get("deferred"):
        return "Deferred"
    if summary.get("stopped"):
        return "Stopped"
    if int_value(summary.get("error_count")) > 0:
        return "Review drain"
    if int_value(summary.get("succeeded_count")) > 0 or int_value(summary.get("already_published_count")) > 0:
        return "Last drain complete"
    if int_value(summary.get("attempted_count")) == 0:
        return "No attempts"
    return "Last drain recorded"


def _pending_drain_summary_issue_level(summary: Mapping[str, Any]) -> str:
    if summary.get("read_error"):
        return "blocked"
    if summary.get("exists") is False or (not summary.get("started_at") and not summary.get("completed_at")):
        return "none"
    if summary.get("stopped") or int_value(summary.get("error_count")) > 0:
        return "blocked"
    if summary.get("deferred") or int_value(summary.get("skipped_count")) > 0 or int_value(summary.get("remaining_count")) > 0:
        return "review"
    return "ok"


def _pending_drain_confidence_status(rows: list[dict[str, Any]]) -> str:
    if any(row.get("confidence") == "blocked" for row in rows):
        return "Do not drain"
    if any(row.get("confidence") == "review" for row in rows):
        return "Review first"
    if any(row.get("confidence") == "unknown" for row in rows):
        return "Evidence incomplete"
    return "Ready-looking" if rows else "Not evaluated"


def _pending_drain_confidence_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("confidence") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def pending_publish_drain_confidence_payload(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_rows = _pending_evidence_rows(rows)
    blocking_evidence = [entry for entry in evidence_rows if entry["evidenceClass"] in {"do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"}]
    review_evidence = [entry for entry in evidence_rows if entry["evidenceClass"] not in {"do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"}]
    summary = _pending_drain_summary_payload(payload)
    rows_out: list[dict[str, Any]] = []

    def add(check: str, confidence: str, evidence: str, action: str) -> None:
        rows_out.append({
            "check": check,
            "confidence": confidence,
            "evidence": evidence,
            "action": action,
            "evidence_authority": "backend",
        })

    if payload.get("error"):
        add(
            "Pending scan",
            "blocked",
            f"scan unavailable: {payload.get('error')}",
            "Open Diagnostics > Pending Publish, Run Logs, and Last Stderr before any drain attempt.",
        )
    else:
        exists = payload.get("exists")
        add(
            "Current parked rows",
            "unknown" if exists is False else "ready" if not rows else "blocked" if blocking_evidence else "review" if review_evidence else "ready",
            f"root={'missing' if exists is False else 'available'}; rows={payload.get('count') or len(rows) or 0}; ready={payload.get('ready_count') or 0}; issues={payload.get('issue_count') or 0}",
            "No pending root exists. Confirm Completed and Run Logs before rerun."
            if exists is False
            else "No parked outputs are waiting. Do not reprocess solely because Pending Publish is empty."
            if not rows
            else "Review row-level evidence below before pressing Publish Parked Outputs.",
        )
        add(
            "Blocker evidence",
            "blocked" if blocking_evidence else "review" if review_evidence else "ready",
            f"blocking={len(blocking_evidence)}; review={len(review_evidence)}; evidence status={_pending_evidence_status(payload, rows)}",
            "Do not drain. Select the highest-risk evidence row and inspect backend-selected targets or build a recovery dry-run plan."
            if blocking_evidence
            else "Review warning/orphan/sidecar rows before drain."
            if review_evidence
            else "No loaded row exposes drain-blocking evidence.",
        )
        validation = _pending_validation_status(payload, rows)
        add(
            "Validation checklist",
            "blocked" if validation == "Do not drain" else "review" if validation == "Review" else "ready",
            f"validation={validation}; health={payload.get('health_count') or 0}; missing payloads={payload.get('missing_local_count') or 0}; missing sidecars={payload.get('missing_sidecar_count') or 0}",
            "Use the Real-media Validation Checklist as the page-level pre-drain gate; backend drain validation remains authoritative.",
        )
        summary_level = _pending_drain_summary_issue_level(summary)
        add(
            "Durable drain summary",
            "blocked" if summary_level == "blocked" else "review" if summary_level == "review" else "ready" if summary_level == "ok" else "unknown",
            f"status={_pending_drain_summary_status(payload)}; attempted={summary.get('attempted_count') or 0}; errors={summary.get('error_count') or 0}; remaining={summary.get('remaining_count') or 0}",
            "Treat the durable summary as last-attempt evidence; the current pending rows remain the source of truth for what is still parked.",
        )

    counts = _pending_drain_confidence_counts(rows_out)
    return {
        "schema_version": PENDING_DRAIN_CONFIDENCE_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "render_contract": "pendingPublishView.confidence.js",
        "render_complete": False,
        "status": _pending_drain_confidence_status(rows_out),
        "counts": counts,
        "rows": _json_safe(rows_out),
        "summary_lines": [
            "Pending Publish backend drain confidence:",
            f"Rows: {len(rows_out)}; ready={counts.get('ready', 0)}; review={counts.get('review', 0)}; blocked={counts.get('blocked', 0)}; unknown={counts.get('unknown', 0)}.",
            "Backend rows cover parked-row, blocker, validation, and durable-summary evidence; WebView still adds display-scope, command-history, recovery-plan, runtime-event, and selection context.",
            "Mutation guardrail: this DTO is read-only and cannot drain, repair, rewrite, move, delete, publish, or bypass backend validation.",
        ],
        "boundary": "read_only_no_media_mutation",
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
    return _recovery_plan_action(row)


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


def pending_publish_open_scan_service_unavailable_result(row_key: str) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_OPEN_COMMAND,
        ok=False,
        message=PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
        severity="error",
        errors=[PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE],
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
    "pending_publish_drain_confidence_payload",
    "PENDING_DRAIN_CONFIDENCE_SCHEMA_VERSION",
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
    "pending_publish_open_scan_service_unavailable_result",
    "pending_publish_open_missing_path_result",
    "pending_publish_open_service_unavailable_result",
    "pending_publish_open_exception_result",
    "pending_publish_open_success_result",
]
