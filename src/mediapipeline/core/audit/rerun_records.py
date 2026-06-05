from __future__ import annotations

import re
from typing import Any

from mediapipeline.desktop.models import AuditRecord, CompletedJobRecord, FailureRecord


def audit_correlation_lookup_key(value: str) -> str:
    normalized = str(value or "").casefold()
    normalized = re.sub(r"\((?:19|20)\d{2}\)", " ", normalized)
    normalized = re.sub(r"\bseason\s*\d{1,2}\b", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bs\d{1,2}\b", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def correlate_audit_record(
    record: AuditRecord,
    completed_records: list[CompletedJobRecord],
    failure_records: list[FailureRecord],
) -> dict[str, Any]:
    audit_path = str(record.path or "").strip().casefold()
    audit_lookup = record.normalized_lookup_title

    completed_matches: list[CompletedJobRecord] = []
    for completed in completed_records:
        source_path = completed.source_path_text.casefold()
        lookup = audit_correlation_lookup_key(completed.lookup_title)
        if (audit_path and source_path == audit_path) or (audit_lookup and lookup == audit_lookup):
            completed_matches.append(completed)

    failure_matches: list[FailureRecord] = []
    for failure in failure_records:
        source_path = failure.source_path_text.casefold()
        lookup = audit_correlation_lookup_key(failure.lookup_title)
        if (audit_path and source_path == audit_path) or (audit_lookup and lookup == audit_lookup):
            failure_matches.append(failure)

    return {
        "completed_count": len(completed_matches),
        "failure_count": len(failure_matches),
        "completed_jobs": completed_matches,
        "failures": failure_matches,
        "latest_completed": completed_matches[0] if completed_matches else None,
        "latest_failure": failure_matches[0] if failure_matches else None,
    }


def format_audit_correlation(
    record: AuditRecord,
    completed_records: list[CompletedJobRecord],
    failure_records: list[FailureRecord],
) -> list[str]:
    correlation = correlate_audit_record(record, completed_records, failure_records)
    completed = correlation["latest_completed"]
    failure = correlation["latest_failure"]
    completed_text = "(none)"
    if completed:
        completed_text = f"{correlation['completed_count']} matched; latest {completed.route_label} {completed.completed_at_text}"
    failure_text = "(none)"
    if failure:
        failure_text = f"{correlation['failure_count']} matched; latest {failure.error_code or failure.stage or 'failure'}"
    return [
        f"Completed Jobs      : {completed_text}",
        f"Failure Records     : {failure_text}",
    ]


def audit_row_value(record: AuditRecord, *names: str) -> str:
    for name in names:
        value = str(record.row.get(name, "") or "").strip()
        if value:
            return value
    return ""


def rerun_media_kind_from_audit(record: AuditRecord) -> str:
    for value in (
        record.media_type,
        audit_row_value(record, "media_kind", "MediaKind", "MediaType"),
    ):
        normalized = str(value or "").strip().casefold()
        if normalized in {"tv", "episode", "episodes", "series"}:
            return "TV"
        if normalized in {"movie", "movies", "film"}:
            return "Movie"
    return ""
