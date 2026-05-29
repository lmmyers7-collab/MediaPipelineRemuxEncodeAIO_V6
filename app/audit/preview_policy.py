"""Audit preview policy and result helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline_desktop_app.models import AuditRecord

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto import AuditPreviewDto


AUDIT_REPORT_SERVICE_UNAVAILABLE_MESSAGE = "Audit report service is not available."
AUDIT_NO_CSV_REPORT_MESSAGE = "No audit CSV report is available yet."
AUDIT_LOADER_UNAVAILABLE_MESSAGE = "Audit CSV loader is not available."
AUDIT_EMPTY_CSV_MESSAGE = "Latest audit CSV contains no rows."


def _audit_preview_dto(**kwargs: Any) -> "AuditPreviewDto":
    from mediapipeline_desktop_app.application.dto_inventory import AuditPreviewDto

    return AuditPreviewDto(**kwargs)


def bounded_audit_limit(value: Any, *, default: int = 100, minimum: int = 1, maximum: int = 500) -> int:
    try:
        limit = int(value or default)
    except (TypeError, ValueError):
        limit = default
    return min(maximum, max(minimum, limit))


def audit_record_to_row(record: AuditRecord) -> dict[str, Any]:
    path = record.path
    return {
        "path": str(path or ""),
        "relative_path": record.relative_path,
        "lookup_title": record.lookup_title,
        "media_type": record.media_type,
        "effective_bucket": record.effective_bucket,
        "priority_fix_level": record.priority_fix_level,
        "priority_score": record.priority_score,
        "primary_issue_code": record.primary_issue_code,
        "primary_suggested_action": record.primary_suggested_action,
        "issue_messages": record.issue_messages,
        "source_csv": str(record.source_csv),
    }


def audit_duplicate_group_count(records: list[AuditRecord]) -> int:
    counts: dict[str, int] = {}
    for record in records:
        key = record.normalized_lookup_title
        if key:
            counts[key] = counts.get(key, 0) + 1
    return sum(1 for count in counts.values() if count > 1)


def audit_preview_fields(
    records: object,
    *,
    source: str,
    priority_only: bool,
    limit: int,
    empty_warning: str,
) -> dict[str, Any]:
    valid_records = [record for record in records or [] if isinstance(record, AuditRecord)]
    rows = [audit_record_to_row(record) for record in valid_records[:limit]]
    buckets = [str(row.get("effective_bucket") or "").upper() for row in rows]
    priority_levels = [str(row.get("priority_fix_level") or "").upper() for row in rows]
    warnings = [] if rows else [empty_warning]
    if len(valid_records) > len(rows):
        warnings.append(f"Showing {len(rows)} of {len(valid_records)} audit row(s).")
    return {
        "rows": rows,
        "source": source,
        "priority_only": bool(priority_only),
        "count": len(valid_records),
        "high_priority_count": sum(1 for item in priority_levels if item == "HIGH"),
        "rerun_count": sum(1 for item in buckets if item == "RERUN_PIPELINE"),
        "redownload_count": sum(1 for item in buckets if item == "REDOWNLOAD_CANDIDATE"),
        "review_count": sum(1 for item in buckets if item == "REVIEW"),
        "duplicate_group_count": audit_duplicate_group_count(valid_records),
        "warnings": warnings,
    }


def audit_report_service_unavailable_result(priority_only: bool) -> AuditPreviewDto:
    return _audit_preview_dto(
        priority_only=bool(priority_only),
        warnings=[AUDIT_REPORT_SERVICE_UNAVAILABLE_MESSAGE],
    )


def audit_latest_csv_resolution_error_result(priority_only: bool, exc: Exception) -> AuditPreviewDto:
    return _audit_preview_dto(
        priority_only=bool(priority_only),
        warnings=[f"Latest audit CSV could not be resolved: {exc}"],
    )


def audit_no_csv_report_result(priority_only: bool) -> AuditPreviewDto:
    return _audit_preview_dto(
        priority_only=bool(priority_only),
        warnings=[AUDIT_NO_CSV_REPORT_MESSAGE],
    )


def audit_loader_unavailable_result(csv_path: Path | str, priority_only: bool) -> AuditPreviewDto:
    return _audit_preview_dto(
        source=str(csv_path),
        priority_only=bool(priority_only),
        warnings=[AUDIT_LOADER_UNAVAILABLE_MESSAGE],
    )


def audit_csv_read_error_result(csv_path: Path | str, priority_only: bool, exc: Exception) -> AuditPreviewDto:
    return _audit_preview_dto(
        source=str(csv_path),
        priority_only=bool(priority_only),
        warnings=[f"Audit CSV could not be read: {exc}"],
    )


def audit_preview_from_records(
    records: object,
    *,
    source: str,
    priority_only: bool,
    limit: int,
    empty_warning: str = AUDIT_EMPTY_CSV_MESSAGE,
) -> AuditPreviewDto:
    return _audit_preview_dto(
        **audit_preview_fields(
            records,
            source=source,
            priority_only=priority_only,
            limit=limit,
            empty_warning=empty_warning,
        )
    )


__all__ = [
    "AUDIT_REPORT_SERVICE_UNAVAILABLE_MESSAGE",
    "AUDIT_NO_CSV_REPORT_MESSAGE",
    "AUDIT_LOADER_UNAVAILABLE_MESSAGE",
    "AUDIT_EMPTY_CSV_MESSAGE",
    "bounded_audit_limit",
    "audit_record_to_row",
    "audit_duplicate_group_count",
    "audit_preview_fields",
    "audit_report_service_unavailable_result",
    "audit_latest_csv_resolution_error_result",
    "audit_no_csv_report_result",
    "audit_loader_unavailable_result",
    "audit_csv_read_error_result",
    "audit_preview_from_records",
]
