"""Failure preview policy and result helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.failures.retry_state import retry_state_for_failure_row, retry_state_payload
from mediapipeline.desktop.models import FailureRecord

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto import FailurePreviewDto


FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE = "Failure marker service is not available."
FAILURE_MARKERS_EMPTY_MESSAGE = "No failure markers are available from the state store."
FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE = "Failure report service is not available."
FAILURE_NO_JSON_REPORT_MESSAGE = "No failure JSON report is available yet."
FAILURE_LOADER_UNAVAILABLE_MESSAGE = "Failure report loader is not available."
FAILURE_JSON_EMPTY_MESSAGE = "Latest failure JSON contains no rows."


def _failure_preview_dto(**kwargs: Any) -> "FailurePreviewDto":
    from mediapipeline.desktop.application.dto_inventory import FailurePreviewDto

    return FailurePreviewDto(**kwargs)


def normalize_failure_source_kind(value: Any) -> str:
    return str(value or "latest_json").strip().casefold()


def bounded_failure_limit(value: Any, *, default: int = 100, minimum: int = 1, maximum: int = 500) -> int:
    try:
        limit = int(value or default)
    except (TypeError, ValueError):
        limit = default
    return min(maximum, max(minimum, limit))


def _failure_text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_failure_source_path(value: Any) -> str:
    text = _failure_text(value)
    if not text:
        return ""
    normalized = os.path.normcase(os.path.normpath(text))
    return normalized.replace("/", "\\").casefold()


def _unique_failure_marker_paths(marker_paths: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for marker_path in marker_paths:
        text = _failure_text(marker_path)
        if not text:
            continue
        key = os.path.normcase(os.path.abspath(text)).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def failure_marker_lookup(records: object) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for record in records or []:
        if not isinstance(record, FailureRecord):
            continue
        key = _normalized_failure_source_path(record.source_path_text)
        marker_path = _failure_text(record.source_json)
        if key and marker_path:
            lookup[key] = _unique_failure_marker_paths([*lookup.get(key, []), marker_path])
    return lookup


def _failure_clear_error_available(marker_paths: list[str]) -> dict[str, object]:
    clean_paths = _unique_failure_marker_paths(marker_paths)
    return {
        "available": bool(clean_paths),
        "marker_path": clean_paths[0] if clean_paths else "",
        "marker_paths": clean_paths,
        "marker_count": len(clean_paths),
        "unavailable_reason": "",
    }


def _failure_clear_error_unavailable(reason: str) -> dict[str, object]:
    return {
        "available": False,
        "marker_path": "",
        "marker_paths": [],
        "marker_count": 0,
        "unavailable_reason": reason,
    }


def _failure_plain_summary(row: dict[str, object]) -> str:
    reason = _failure_text(row.get("reason"))
    if reason:
        return reason if len(reason) <= 180 else f"{reason[:177].rstrip()}..."
    code = _failure_text(row.get("error_code"))
    stage = _failure_text(row.get("stage"))
    if code and stage:
        return f"{code} during {stage}."
    if code:
        return code
    if stage:
        return f"Failure recorded during {stage}."
    return "Failure recorded. Open details for evidence."


def _failure_suggested_fix(row: dict[str, object]) -> str:
    explicit = _failure_text(row.get("suggested_action"))
    if explicit:
        return explicit
    classification = _failure_text(row.get("classification")).casefold()
    if classification == "transient":
        return "Backend will retry this transient failure on the next backend queue pass. Compare logs first."
    if classification in {"operator_required", "permanent"}:
        return "Open diagnostics and review the source before retry."
    return "Review diagnostics before retry."


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
    source_key = _normalized_failure_source_path(row.get("source_path"))
    if not source_key:
        return _failure_clear_error_unavailable(
            "This failure row did not include a source path that can be matched to an active marker."
        )
    marker_paths = marker_lookup.get(source_key, [])
    if marker_paths:
        return _failure_clear_error_available(marker_paths)
    return _failure_clear_error_unavailable("No active failure marker matched this failure row.")


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
    retry_state = retry_state_for_failure_row(row)
    row["retry_status_state"] = retry_state["status_state"]
    row["retry_allowed"] = retry_state["retry_allowed"]
    row["retry_route_or_command"] = retry_state["retry_route_or_command"]
    row["retry_safe_next_action"] = retry_state["safe_next_action"]
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
) -> dict[str, object]:
    valid_records = [record for record in records or [] if isinstance(record, FailureRecord)]
    rows = [
        failure_record_to_row(record, source_kind=source_kind, marker_lookup=marker_lookup)
        for record in valid_records[:limit]
    ]
    classifications = [str(row.get("classification") or "").casefold() for row in rows]
    warnings = [] if rows else [empty_warning]
    if len(valid_records) > len(rows):
        warnings.append(f"Showing {len(rows)} of {len(valid_records)} failure row(s).")
    return {
        "rows": rows,
        "source": source,
        "source_kind": source_kind,
        "count": len(valid_records),
        "operator_required_count": sum(1 for item in classifications if item == "operator_required"),
        "permanent_count": sum(1 for item in classifications if item == "permanent"),
        "transient_count": sum(1 for item in classifications if item == "transient"),
        "retry_state": retry_state_payload(rows, source=source, source_kind=source_kind),
        "warnings": warnings,
    }


def failure_marker_service_unavailable_result() -> FailurePreviewDto:
    return _failure_preview_dto(
        source_kind="markers",
        warnings=[FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE],
    )


def failure_markers_read_error_result(markers_path: Path | str | None, exc: Exception) -> FailurePreviewDto:
    return _failure_preview_dto(
        source=str(markers_path or ""),
        source_kind="markers",
        warnings=[f"Failure markers could not be read: {exc}"],
    )


def failure_report_service_unavailable_result() -> FailurePreviewDto:
    return _failure_preview_dto(warnings=[FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE])


def failure_latest_json_resolution_error_result(exc: Exception) -> FailurePreviewDto:
    return _failure_preview_dto(warnings=[f"Latest failure JSON could not be resolved: {exc}"])


def failure_no_json_report_result() -> FailurePreviewDto:
    return _failure_preview_dto(warnings=[FAILURE_NO_JSON_REPORT_MESSAGE])


def failure_loader_unavailable_result(report_path: Path | str) -> FailurePreviewDto:
    return _failure_preview_dto(
        source=str(report_path),
        warnings=[FAILURE_LOADER_UNAVAILABLE_MESSAGE],
    )


def failure_json_read_error_result(report_path: Path | str, exc: Exception) -> FailurePreviewDto:
    return _failure_preview_dto(
        source=str(report_path),
        warnings=[f"Failure JSON could not be read: {exc}"],
    )


def failure_preview_from_records(
    records: object,
    *,
    source: str,
    source_kind: str,
    limit: int,
    empty_warning: str,
    marker_lookup: dict[str, list[str]] | None = None,
) -> FailurePreviewDto:
    return _failure_preview_dto(
        **failure_preview_fields(
            records,
            source=source,
            source_kind=source_kind,
            limit=limit,
            empty_warning=empty_warning,
            marker_lookup=marker_lookup,
        )
    )


__all__ = [
    "FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE",
    "FAILURE_MARKERS_EMPTY_MESSAGE",
    "FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE",
    "FAILURE_NO_JSON_REPORT_MESSAGE",
    "FAILURE_LOADER_UNAVAILABLE_MESSAGE",
    "FAILURE_JSON_EMPTY_MESSAGE",
    "normalize_failure_source_kind",
    "bounded_failure_limit",
    "failure_marker_lookup",
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
]
