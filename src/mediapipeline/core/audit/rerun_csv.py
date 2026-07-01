from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mediapipeline.core.audit.contracts import AuditRecord
from mediapipeline.core.audit.rerun_records import audit_row_value, rerun_media_kind_from_audit

RERUN_CSV_COLUMNS = (
    "enabled",
    "source_path",
    "media_kind",
    "audit_issue_codes",
    "stage_mode",
    "post_success_original",
    "return_mode",
    "plex_planned_path",
    "source_size",
    "source_mtime_utc",
    "source_identity_v2",
    "priority_fix_level",
    "effective_bucket",
    "primary_issue_code",
    "lookup_title",
    "relative_path",
    "notes",
)


def build_rerun_csv_row(
    record: AuditRecord,
    *,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
) -> dict[str, str] | None:
    source_path = record.path
    if not source_path:
        return None
    return {
        "enabled": "true",
        "source_path": str(source_path),
        "media_kind": rerun_media_kind_from_audit(record),
        "audit_issue_codes": record.row.get("NonSidecarIssueCodes", "").strip()
        or record.row.get("IssueCodes", "").strip()
        or record.primary_issue_code,
        "stage_mode": stage_mode,
        "post_success_original": original_mode,
        "return_mode": return_mode,
        "plex_planned_path": audit_row_value(record, "plex_planned_path", "PlannedOutputPath", "OutputPath"),
        "source_size": "",
        "source_mtime_utc": "",
        "source_identity_v2": audit_row_value(record, "source_identity_v2", "SourceIdentityV2"),
        "priority_fix_level": record.priority_fix_level,
        "effective_bucket": record.effective_bucket,
        "primary_issue_code": record.primary_issue_code,
        "lookup_title": record.lookup_title,
        "relative_path": record.relative_path,
        "notes": "",
    }


def apply_rerun_source_metadata(row: dict[str, str], metadata: dict[str, Any] | None) -> dict[str, str]:
    updated = dict(row)
    if not metadata:
        return updated
    updated["source_size"] = str(metadata.get("source_size") or "")
    updated["source_mtime_utc"] = str(metadata.get("source_mtime_utc") or "")
    if not updated["source_identity_v2"]:
        updated["source_identity_v2"] = str(metadata.get("source_identity_v2") or "")
    if not bool(metadata.get("exists", False)):
        updated["enabled"] = "false"
        updated["notes"] = f"source metadata failed: {metadata.get('error') or 'source unavailable'}"
    return updated


def source_stat_to_rerun_values(st_size: int, st_mtime: float) -> tuple[str, str]:
    return str(st_size), datetime.fromtimestamp(st_mtime, timezone.utc).isoformat()
