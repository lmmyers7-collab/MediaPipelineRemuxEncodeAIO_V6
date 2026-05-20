from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import FailureRecord
from .dto import FailurePreviewDto


FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE = "Failure marker service is not available."
FAILURE_MARKERS_EMPTY_MESSAGE = "No failure markers are available from the state store."
FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE = "Failure report service is not available."
FAILURE_NO_JSON_REPORT_MESSAGE = "No failure JSON report is available yet."
FAILURE_LOADER_UNAVAILABLE_MESSAGE = "Failure report loader is not available."
FAILURE_JSON_EMPTY_MESSAGE = "Latest failure JSON contains no rows."


def normalize_failure_source_kind(value: Any) -> str:
    return str(value or "latest_json").strip().casefold()


def bounded_failure_limit(value: Any, *, default: int = 100, minimum: int = 1, maximum: int = 500) -> int:
    try:
        limit = int(value or default)
    except (TypeError, ValueError):
        limit = default
    return min(maximum, max(minimum, limit))


def failure_record_to_row(record: FailureRecord) -> dict[str, object]:
    return {
        "source_path": record.source_path_text,
        "stage": record.stage,
        "reason": record.reason,
        "classification": record.classification,
        "error_code": record.error_code,
        "media_type": record.media_type,
        "lookup_title": record.lookup_title,
        "recorded_at": record.recorded_at,
        "retry_count": record.retry_count,
        "retry_limit": record.retry_limit,
        "escalated": record.escalated,
        "artifact_path": str(record.artifact_path or ""),
        "repro_path": str(record.repro_path or ""),
        "suggested_action": record.suggested_action,
        "suggested_rename": record.suggested_rename,
        "source_json": str(record.source_json),
    }


def failure_preview_fields(
    records: object,
    *,
    source: str,
    source_kind: str,
    limit: int,
    empty_warning: str,
) -> dict[str, object]:
    valid_records = [record for record in records or [] if isinstance(record, FailureRecord)]
    rows = [failure_record_to_row(record) for record in valid_records[:limit]]
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
        "warnings": warnings,
    }


def failure_marker_service_unavailable_result() -> FailurePreviewDto:
    return FailurePreviewDto(
        source_kind="markers",
        warnings=[FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE],
    )


def failure_markers_read_error_result(markers_path: Path | str | None, exc: Exception) -> FailurePreviewDto:
    return FailurePreviewDto(
        source=str(markers_path or ""),
        source_kind="markers",
        warnings=[f"Failure markers could not be read: {exc}"],
    )


def failure_report_service_unavailable_result() -> FailurePreviewDto:
    return FailurePreviewDto(warnings=[FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE])


def failure_latest_json_resolution_error_result(exc: Exception) -> FailurePreviewDto:
    return FailurePreviewDto(warnings=[f"Latest failure JSON could not be resolved: {exc}"])


def failure_no_json_report_result() -> FailurePreviewDto:
    return FailurePreviewDto(warnings=[FAILURE_NO_JSON_REPORT_MESSAGE])


def failure_loader_unavailable_result(report_path: Path | str) -> FailurePreviewDto:
    return FailurePreviewDto(
        source=str(report_path),
        warnings=[FAILURE_LOADER_UNAVAILABLE_MESSAGE],
    )


def failure_json_read_error_result(report_path: Path | str, exc: Exception) -> FailurePreviewDto:
    return FailurePreviewDto(
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
) -> FailurePreviewDto:
    return FailurePreviewDto(
        **failure_preview_fields(
            records,
            source=source,
            source_kind=source_kind,
            limit=limit,
            empty_warning=empty_warning,
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
