"""Failure preview policy and result helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.failures.retry_state import retry_state_for_failure_row, retry_state_payload
from mediapipeline.core.failures.contracts import FailureRecord

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_inventory import FailurePreviewDto


FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE = "Failure marker service is not available."
FAILURE_MARKERS_EMPTY_MESSAGE = "No failure markers are available from the state store."
FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE = "Failure report service is not available."
FAILURE_NO_JSON_REPORT_MESSAGE = "No failure JSON report is available yet."
FAILURE_LOADER_UNAVAILABLE_MESSAGE = "Failure report loader is not available."
FAILURE_JSON_EMPTY_MESSAGE = "Latest failure JSON contains no rows."


FAILURE_RESOLUTION_SCHEMA_VERSION = "desktop_failure_resolution.v1"
FAILURE_RESOLUTION_GROUP_SCHEMA_VERSION = "desktop_failure_resolution_group.v1"
FAILURE_EVIDENCE_DETAILS_SCHEMA_VERSION = "desktop_failure_evidence_details.v1"
FAILURE_EVIDENCE_MAX_LINES = 10
FAILURE_EVIDENCE_MAX_STREAM_ROWS = 16
FAILURE_EVIDENCE_MAX_PROOF_FIELDS = 16
FAILURE_OPEN_TARGETS = {
    "artifact": "failure artifact",
    "repro": "reproduction file",
    "record_file": "failure record file",
    "record_folder": "failure record folder",
}
FAILURE_RESOLUTION_OWNER_PAGES = {
    "Pending Publish": "pending",
    "Queue": "queue",
    "Settings": "settings",
    "Completed": "completed",
    "Diagnostics": "diagnostics",
    "Manual review": "diagnostics",
    "Backend retry": "",
}
FAILURE_LIFECYCLE_LABELS = {
    "new": "New",
    "acknowledged": "Acknowledged",
    "working": "Working",
    "waiting_backend": "Waiting retry",
    "ready_to_clear": "Ready to clear",
    "resolved": "Resolved",
    "reopened": "Reopened",
}
FAILURE_LIFECYCLE_TRANSITION_LABELS = {
    "acknowledge": "Acknowledge",
    "start_work": "Start work",
    "complete_step": "Complete step",
    "waive_step": "Waive step",
    "mark_resolved": "Mark resolved",
    "reopen": "Reopen",
}



from mediapipeline.core.failures.policy_support import *  # noqa: F403

from mediapipeline.core.failures.policy_evidence import *  # noqa: F403

from mediapipeline.core.failures.policy_markers import *  # noqa: F403

from mediapipeline.core.failures.policy_resolution import *  # noqa: F403

def _failure_triage(row: dict[str, object], retry_state: dict[str, object]) -> dict[str, object]:
    classification = _failure_text(row.get("classification")).casefold()
    status_state = _failure_text(retry_state.get("status_state")).casefold()
    if status_state == "blocked" or classification in {"operator_required", "permanent"}:
        status_label = "Needs operator"
        severity = "blocked"
    elif retry_state.get("retry_allowed") is True:
        status_label = "Will retry"
        severity = "warning"
    elif _failure_text(row.get("reason")) or _failure_text(row.get("error_code")):
        status_label = "Review"
        severity = "warning"
    else:
        status_label = "Recorded"
        severity = "info"
    detail_available = any(
        _failure_text(row.get(key))
        for key in ("reason", "error_code", "stage", "artifact_path", "repro_path", "source_json")
    ) or bool(
        isinstance(row.get("evidence_details"), dict)
        and row.get("evidence_details", {}).get("structured") is True
    )
    return {
        "status_label": status_label,
        "severity": severity,
        "plain_summary": _failure_plain_summary(row),
        "suggested_fix": _failure_suggested_fix(row),
        "safe_next_action": _failure_text(retry_state.get("safe_next_action")) or _failure_suggested_fix(row),
        "detail_available": detail_available,
    }


def _failure_clear_error(
    row: dict[str, object],
    *,
    source_kind: str,
    marker_lookup: dict[str, list[str]] | None,
) -> dict[str, object]:
    if source_kind == "markers":
        marker_path = _failure_text(row.get("source_json"))
        if marker_path:
            return _failure_clear_error_available([marker_path])
        return _failure_clear_error_unavailable("This marker row did not include an active marker path.")

    if marker_lookup is None:
        return _failure_clear_error_unavailable("Active failure markers could not be loaded for this failure row.")
    lookup_keys = _failure_marker_lookup_keys_for_row(row)
    if not lookup_keys:
        return _failure_clear_error_unavailable(
            "This failure row did not include source or job evidence that can be matched to an active marker."
        )
    marker_paths = _unique_failure_marker_paths(
        [path for key in lookup_keys for path in marker_lookup.get(key, [])]
    )
    if marker_paths:
        return _failure_clear_error_available(marker_paths)
    return _failure_clear_error_unavailable(
        "No active failure marker matched this latest-report row. If markers were already cleared, switch to Use failure markers to view active retry blockers only."
    )


def failure_record_to_row(
    record: FailureRecord,
    *,
    source_kind: str = "latest_json",
    marker_lookup: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "source_path": record.source_path_text,
        "job_id": record.job_id,
        "correlation_id": record.correlation_id,
        "stage": record.stage,
        "reason": record.reason,
        "classification": record.classification,
        "error_code": record.error_code,
        "media_type": record.media_type,
        "lookup_title": record.lookup_title,
        "recorded_at": record.recorded_at,
        "retry_count": record.retry_count,
        "retry_limit": record.retry_limit,
        "retryable": record.retryable,
        "escalated": record.escalated,
        "artifact_path": str(record.artifact_path or ""),
        "repro_path": str(record.repro_path or ""),
        "suggested_action": record.suggested_action,
        "suggested_rename": record.suggested_rename,
        "source_json": str(record.source_json),
    }
    row["evidence_details"] = _failure_evidence_details(record.payload)
    retry_state = retry_state_for_failure_row(row)
    row["retry_status_state"] = retry_state["status_state"]
    row["retry_allowed"] = retry_state["retry_allowed"]
    row["retry_route_or_command"] = retry_state["retry_route_or_command"]
    row["retry_safe_next_action"] = retry_state["safe_next_action"]
    row["row_key"] = _failure_row_key(row)
    normalized_source_kind = normalize_failure_source_kind(source_kind)
    row["triage"] = _failure_triage(row, retry_state)
    row["clear_error"] = _failure_clear_error(
        row,
        source_kind=normalized_source_kind,
        marker_lookup=marker_lookup,
    )
    return row


def failure_preview_fields(
    records: object,
    *,
    source: str,
    source_kind: str,
    limit: int,
    empty_warning: str,
    marker_lookup: dict[str, list[str]] | None = None,
    resolution_journal: dict[str, object] | None = None,
) -> dict[str, object]:
    valid_records = [record for record in records or [] if isinstance(record, FailureRecord)]
    all_rows = [
        failure_record_to_row(record, source_kind=source_kind, marker_lookup=marker_lookup)
        for record in valid_records
    ]
    rows = all_rows[:limit]
    classifications = [str(row.get("classification") or "").casefold() for row in all_rows]
    warnings = [] if rows else [empty_warning]
    if len(valid_records) > len(rows):
        warnings.append(f"Showing {len(rows)} of {len(valid_records)} failure row(s).")
    resolution_groups = _failure_resolution_groups(all_rows, journal_state=resolution_journal)
    resolution_summary = _failure_resolution_summary(
        rows=all_rows,
        groups=resolution_groups,
        source=source,
        source_kind=source_kind,
        warnings=warnings,
    )
    return {
        "rows": rows,
        "source": source,
        "source_kind": source_kind,
        "count": len(valid_records),
        "visible_count": len(rows),
        "hidden_count": max(0, len(all_rows) - len(rows)),
        "hidden_blocker_count": sum(
            1
            for row in all_rows[len(rows) :]
            if str(row.get("classification") or "").casefold() in {"operator_required", "permanent"}
            or str((row.get("triage") or {}).get("severity") or "").casefold() == "blocked"
        ),
        "details_complete": len(rows) == len(all_rows),
        "operator_required_count": sum(1 for item in classifications if item == "operator_required"),
        "permanent_count": sum(1 for item in classifications if item == "permanent"),
        "transient_count": sum(1 for item in classifications if item == "transient"),
        "retry_state": retry_state_payload(rows, source=source, source_kind=source_kind),
        "resolution_summary": resolution_summary,
        "resolution_groups": resolution_groups,
        "warnings": warnings,
    }


def failure_marker_service_unavailable_result() -> FailurePreviewDto:
    message = FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE
    return _failure_preview_dto(
        source_kind="markers",
        warnings=[message],
        availability="unavailable",
        error=message,
    )


def failure_markers_read_error_result(markers_path: Path | str | None, exc: Exception) -> FailurePreviewDto:
    message = f"Failure markers could not be read: {exc}"
    return _failure_preview_dto(
        source=str(markers_path or ""),
        source_kind="markers",
        warnings=[message],
        availability="unavailable",
        error=message,
    )


def failure_report_service_unavailable_result() -> FailurePreviewDto:
    return _failure_preview_dto(
        warnings=[FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE],
        availability="unavailable",
        error=FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE,
    )


def failure_latest_json_resolution_error_result(exc: Exception) -> FailurePreviewDto:
    message = f"Latest failure JSON could not be resolved: {exc}"
    return _failure_preview_dto(warnings=[message], availability="unavailable", error=message)


def failure_no_json_report_result() -> FailurePreviewDto:
    return _failure_preview_dto(warnings=[FAILURE_NO_JSON_REPORT_MESSAGE], availability="absent")


def failure_loader_unavailable_result(report_path: Path | str) -> FailurePreviewDto:
    return _failure_preview_dto(
        source=str(report_path),
        warnings=[FAILURE_LOADER_UNAVAILABLE_MESSAGE],
        availability="unavailable",
        error=FAILURE_LOADER_UNAVAILABLE_MESSAGE,
    )


def failure_json_read_error_result(report_path: Path | str, exc: Exception) -> FailurePreviewDto:
    message = f"Failure JSON could not be read: {exc}"
    return _failure_preview_dto(
        source=str(report_path),
        warnings=[message],
        availability="unavailable",
        error=message,
    )


def failure_preview_from_records(
    records: object,
    *,
    source: str,
    source_kind: str,
    limit: int,
    empty_warning: str,
    marker_lookup: dict[str, list[str]] | None = None,
    resolution_journal: dict[str, object] | None = None,
) -> FailurePreviewDto:
    return _failure_preview_dto(
        **failure_preview_fields(
            records,
            source=source,
            source_kind=source_kind,
            limit=limit,
            empty_warning=empty_warning,
            marker_lookup=marker_lookup,
            resolution_journal=resolution_journal,
        )
    )

__all__ = (
    "_failure_triage",
    "_failure_clear_error",
    "failure_record_to_row",
    "failure_preview_fields",
    "failure_marker_service_unavailable_result",
    "failure_markers_read_error_result",
    "failure_report_service_unavailable_result",
    "failure_latest_json_resolution_error_result",
    "failure_no_json_report_result",
    "failure_loader_unavailable_result",
    "failure_json_read_error_result",
    "failure_preview_from_records",
)
