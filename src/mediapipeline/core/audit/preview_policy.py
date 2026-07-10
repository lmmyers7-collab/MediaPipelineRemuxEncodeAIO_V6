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


def _audit_preview_dto(**kwargs: Any) -> AuditPreviewDto:
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
    duplicate_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = record.path
    duplicate = duplicate_info or {}
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
        "duplicate_group": bool(duplicate),
        "duplicate_group_key": str(duplicate.get("key") or ""),
        "duplicate_group_size": int(duplicate.get("size") or 0),
        "duplicate_group_type": str(duplicate.get("type") or ""),
        "duplicate_group_label": str(duplicate.get("label") or ""),
    }


def _path_leaf_key(record: AuditRecord) -> str:
    raw = str(record.path or record.relative_path or "").strip()
    if not raw:
        return ""
    return raw.replace("\\", "/").rsplit("/", 1)[-1].casefold().strip()


def _duplicate_group_candidates(record: AuditRecord) -> list[tuple[str, str, str]]:
    candidates: list[tuple[str, str, str]] = []
    leaf = _path_leaf_key(record)
    if leaf:
        candidates.append(("same_leaf", f"leaf:{leaf}", f"Same file name: {leaf}"))
    if record.media_type.casefold() == "movie":
        title = record.normalized_lookup_title
        if title:
            candidates.append(("movie_title", f"movie-title:{title}", f"Movie title: {title}"))
    return candidates


def audit_duplicate_group_metadata(records: list[AuditRecord]) -> dict[int, dict[str, Any]]:
    candidate_counts: dict[str, int] = {}
    per_record_candidates: list[list[tuple[str, str, str]]] = []
    for record in records:
        candidates = _duplicate_group_candidates(record)
        per_record_candidates.append(candidates)
        for _kind, key, _label in candidates:
            candidate_counts[key] = candidate_counts.get(key, 0) + 1

    duplicate_rows: dict[int, dict[str, Any]] = {}
    for index, candidates in enumerate(per_record_candidates):
        for kind, key, label in candidates:
            size = candidate_counts.get(key, 0)
            if size > 1:
                duplicate_rows[index] = {
                    "key": key,
                    "size": size,
                    "type": kind,
                    "label": label,
                }
                break
    return duplicate_rows


def audit_duplicate_group_count(records: list[AuditRecord]) -> int:
    duplicate_rows = audit_duplicate_group_metadata(records)
    return len({str(info.get("key") or "") for info in duplicate_rows.values() if info.get("key")})


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
    visible_record_list = [record for _index, record in visible_records]
    duplicate_rows = audit_duplicate_group_metadata(visible_record_list)
    rows = [
        audit_record_to_row(record, row_index=index, duplicate_info=duplicate_rows.get(visible_index))
        for visible_index, (index, record) in enumerate(visible_records[:limit])
    ]
    buckets = [str(record.effective_bucket or "").upper() for record in visible_record_list]
    priority_levels = [str(record.priority_fix_level or "").upper() for record in visible_record_list]
    actionable_count = sum(
        1
        for bucket, priority_level in zip(buckets, priority_levels, strict=False)
        if bucket in {"RERUN_PIPELINE", "REDOWNLOAD_CANDIDATE"} or priority_level in {"HIGH", "MEDIUM"}
    )
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
        "medium_priority_count": sum(1 for item in priority_levels if item == "MEDIUM"),
        "priority_count": sum(1 for item in priority_levels if item in {"HIGH", "MEDIUM"}),
        "rerun_count": sum(1 for item in buckets if item == "RERUN_PIPELINE"),
        "redownload_count": sum(1 for item in buckets if item == "REDOWNLOAD_CANDIDATE"),
        "review_count": sum(1 for item in buckets if item == "REVIEW"),
        "duplicate_group_count": len({str(info.get("key") or "") for info in duplicate_rows.values() if info.get("key")}),
        "actionable_count": actionable_count,
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
    message = AUDIT_REPORT_SERVICE_UNAVAILABLE_MESSAGE
    return _audit_preview_dto(
        priority_only=bool(priority_only),
        warnings=[message],
        error=message,
    )


def audit_latest_csv_resolution_error_result(priority_only: bool, exc: Exception) -> AuditPreviewDto:
    message = f"Latest audit CSV could not be resolved: {exc}"
    return _audit_preview_dto(
        priority_only=bool(priority_only),
        warnings=[message],
        error=message,
    )


def audit_no_csv_report_result(priority_only: bool) -> AuditPreviewDto:
    return _audit_preview_dto(
        priority_only=bool(priority_only),
        warnings=[AUDIT_NO_CSV_REPORT_MESSAGE],
    )


def audit_loader_unavailable_result(csv_path: Path | str, priority_only: bool) -> AuditPreviewDto:
    message = AUDIT_LOADER_UNAVAILABLE_MESSAGE
    return _audit_preview_dto(
        source=str(csv_path),
        priority_only=bool(priority_only),
        warnings=[message],
        error=message,
    )


def audit_csv_read_error_result(csv_path: Path | str, priority_only: bool, exc: Exception) -> AuditPreviewDto:
    message = f"Audit CSV could not be read: {exc}"
    return _audit_preview_dto(
        source=str(csv_path),
        priority_only=bool(priority_only),
        warnings=[message],
        error=message,
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
    "audit_duplicate_group_metadata",
    "audit_duplicate_group_count",
    "audit_preview_fields",
    "audit_report_service_unavailable_result",
    "audit_latest_csv_resolution_error_result",
    "audit_no_csv_report_result",
    "audit_loader_unavailable_result",
    "audit_csv_read_error_result",
    "audit_preview_from_records",
]
