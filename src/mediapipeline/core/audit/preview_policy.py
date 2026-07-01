"""Audit preview policy and result helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.audit.ignore_manifest import audit_ignore_entry_for_path
from mediapipeline.core.audit.contracts import AuditRecord

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_inventory import AuditPreviewDto


AUDIT_REPORT_SERVICE_UNAVAILABLE_MESSAGE = "Audit report service is not available."
AUDIT_NO_CSV_REPORT_MESSAGE = "No audit CSV report is available yet."
AUDIT_LOADER_UNAVAILABLE_MESSAGE = "Audit CSV loader is not available."
AUDIT_EMPTY_CSV_MESSAGE = "Latest audit CSV contains no rows."


def _audit_preview_dto(**kwargs: Any) -> "AuditPreviewDto":
    from mediapipeline.core.kernel.dto_inventory import AuditPreviewDto

    return AuditPreviewDto(**kwargs)


def bounded_audit_limit(value: Any, *, default: int = 100, minimum: int = 1, maximum: int = 500) -> int:
    try:
        limit = int(value or default)
    except (TypeError, ValueError):
        limit = default
    return min(maximum, max(minimum, limit))


def audit_record_key(record: AuditRecord, row_index: int) -> str:
    parts = [
        str(record.source_csv or ""),
        str(row_index),
        str(record.path or ""),
        record.relative_path,
        record.primary_issue_code,
        str(record.priority_score),
    ]
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8", errors="replace")).hexdigest()
    return digest[:24]


def audit_record_to_row(
    record: AuditRecord,
    *,
    row_index: int = 0,
    ignore_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = record.path
    return {
        "row_key": audit_record_key(record, row_index),
        "row_index": row_index,
        "path": str(path or ""),
        "source_root": record.source_root,
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
        "ignored": ignore_entry is not None,
        "ignore_reason": str((ignore_entry or {}).get("reason") or ""),
        "ignore_set_at": str((ignore_entry or {}).get("set_at") or ""),
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
    ignore_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    valid_records = [record for record in records or [] if isinstance(record, AuditRecord)]
    visible_records: list[tuple[int, AuditRecord]] = []
    ignored_count = 0
    for index, record in enumerate(valid_records):
        if audit_ignore_entry_for_path(ignore_manifest, record.path):
            ignored_count += 1
            continue
        visible_records.append((index, record))
    rows = [
        audit_record_to_row(record, row_index=index)
        for index, record in visible_records[:limit]
    ]
    buckets = [str(row.get("effective_bucket") or "").upper() for row in rows]
    priority_levels = [str(row.get("priority_fix_level") or "").upper() for row in rows]
    warnings = [] if rows else [empty_warning]
    if len(visible_records) > len(rows):
        warnings.append(f"Showing {len(rows)} of {len(visible_records)} audit row(s).")
    if ignored_count:
        warnings.append(f"{ignored_count} audit row(s) hidden by the audit ignore manifest.")
    return {
        "rows": rows,
        "source": source,
        "priority_only": bool(priority_only),
        "count": len(visible_records),
        "total_count": len(valid_records),
        "ignored_count": ignored_count,
        "high_priority_count": sum(1 for item in priority_levels if item == "HIGH"),
        "rerun_count": sum(1 for item in buckets if item == "RERUN_PIPELINE"),
        "redownload_count": sum(1 for item in buckets if item == "REDOWNLOAD_CANDIDATE"),
        "review_count": sum(1 for item in buckets if item == "REVIEW"),
        "duplicate_group_count": audit_duplicate_group_count(valid_records),
        "warnings": warnings,
    }


def audit_visible_records(
    records: object,
    *,
    ignore_manifest: dict[str, Any] | None = None,
    limit: int | None = None,
) -> list[tuple[int, AuditRecord]]:
    visible: list[tuple[int, AuditRecord]] = []
    for index, record in enumerate(record for record in records or [] if isinstance(record, AuditRecord)):
        if audit_ignore_entry_for_path(ignore_manifest, record.path):
            continue
        visible.append((index, record))
        if limit is not None and len(visible) >= limit:
            break
    return visible


def audit_records_for_row_keys(
    records: object,
    row_keys: object,
    *,
    ignore_manifest: dict[str, Any] | None = None,
    limit: int | None = None,
) -> list[AuditRecord]:
    visible = audit_visible_records(records, ignore_manifest=ignore_manifest, limit=limit)
    keys = [str(key).strip() for key in row_keys or [] if str(key).strip()]
    if not keys:
        return [record for _, record in visible]
    wanted = set(keys)
    return [
        record
        for index, record in visible
        if audit_record_key(record, index) in wanted
    ]


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
    ignore_manifest: dict[str, Any] | None = None,
) -> AuditPreviewDto:
    return _audit_preview_dto(
        **audit_preview_fields(
            records,
            source=source,
            priority_only=priority_only,
            limit=limit,
            empty_warning=empty_warning,
            ignore_manifest=ignore_manifest,
        )
    )


__all__ = [
    "AUDIT_REPORT_SERVICE_UNAVAILABLE_MESSAGE",
    "AUDIT_NO_CSV_REPORT_MESSAGE",
    "AUDIT_LOADER_UNAVAILABLE_MESSAGE",
    "AUDIT_EMPTY_CSV_MESSAGE",
    "audit_record_key",
    "audit_records_for_row_keys",
    "audit_visible_records",
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
