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

def _normalized_failure_source_path(value: Any) -> str:
    text = _failure_text(value)
    if not text:
        return ""
    normalized = os.path.normcase(os.path.normpath(text))
    return normalized.replace("/", "\\").casefold()


def _failure_lookup_key(kind: str, *values: Any) -> str:
    parts = [_failure_text(value).casefold() for value in values]
    if not all(parts):
        return ""
    return "\u001f".join([kind, *parts])


def _failure_marker_lookup_keys_for_record(record: FailureRecord) -> list[str]:
    keys: list[str] = []
    source_key = _normalized_failure_source_path(record.source_path_text)
    if source_key:
        keys.append(source_key)
    job_key = _failure_lookup_key("job", record.job_id, record.stage, record.error_code)
    if job_key:
        keys.append(job_key)
    correlation_key = _failure_lookup_key(
        "correlation",
        record.correlation_id,
        record.source_path_text,
        record.stage,
        record.error_code,
    )
    if correlation_key:
        keys.append(correlation_key)
    return keys


def _failure_marker_lookup_keys_for_row(row: dict[str, object]) -> list[str]:
    keys: list[str] = []
    source_key = _normalized_failure_source_path(row.get("source_path"))
    if source_key:
        keys.append(source_key)
    job_key = _failure_lookup_key("job", row.get("job_id"), row.get("stage"), row.get("error_code"))
    if job_key:
        keys.append(job_key)
    correlation_key = _failure_lookup_key(
        "correlation",
        row.get("correlation_id"),
        row.get("source_path"),
        row.get("stage"),
        row.get("error_code"),
    )
    if correlation_key:
        keys.append(correlation_key)
    return keys


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
        marker_path = _failure_text(record.source_json)
        if not marker_path:
            continue
        for key in _failure_marker_lookup_keys_for_record(record):
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
    return "Failure recorded. Review grouped evidence."


def _failure_row_key(row: dict[str, object]) -> str:
    return "\u001f".join(
        [
            _failure_text(row.get("source_json")),
            _failure_text(row.get("source_path")),
            _failure_text(row.get("stage")),
            _failure_text(row.get("error_code")),
            _failure_text(row.get("recorded_at")),
        ]
    ).casefold()

__all__ = (
    "_normalized_failure_source_path",
    "_failure_lookup_key",
    "_failure_marker_lookup_keys_for_record",
    "_failure_marker_lookup_keys_for_row",
    "_unique_failure_marker_paths",
    "failure_marker_lookup",
    "_failure_clear_error_available",
    "_failure_clear_error_unavailable",
    "_failure_plain_summary",
    "_failure_row_key",
)
