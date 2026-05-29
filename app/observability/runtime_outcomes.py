"""Runtime outcome extraction helpers for status-like preview surfaces."""

from __future__ import annotations

import os
from typing import Any, Iterable

from app.observability.artifact_freshness import datetime_freshness_fields


RUNTIME_OUTCOME_EVENT_LIMIT = 300
RUNTIME_OUTCOME_STALE_AFTER_SECONDS = 7 * 24 * 3600
RUNTIME_OUTCOME_EVENT_TYPES = {"job_completed", "failure_recorded"}


def source_identity_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return os.path.normcase(os.path.abspath(text))
    except (OSError, ValueError):
        return text.casefold()


def runtime_event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def runtime_event_source_path(event: dict[str, Any]) -> str:
    data = runtime_event_data(event)
    return str(event.get("source_path") or data.get("source_path") or "").strip()


def runtime_bool(value: Any, default: bool | None = None) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "succeeded", "success", "processed", "published"}:
        return True
    if text in {"0", "false", "no", "n", "failed", "failure", "skipped", "stopped"}:
        return False
    return default


def runtime_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def runtime_outcome_status(event: dict[str, Any], data: dict[str, Any]) -> str:
    event_type = str(event.get("event_type") or "").strip()
    raw_status = str(data.get("completion_status") or event.get("status") or data.get("classification") or "").strip()
    success = runtime_bool(data.get("success"), None)
    if event_type == "failure_recorded":
        classification = raw_status.casefold()
        if classification in {"transient", "permanent", "operator_required"}:
            return f"{classification}_failure"
        return "failure_recorded"
    if success is True:
        return "succeeded"
    if success is False and not raw_status:
        return "failed"
    return raw_status or "unknown"


def runtime_outcome_from_event(event: Any) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    event_type = str(event.get("event_type") or "").strip()
    if event_type not in RUNTIME_OUTCOME_EVENT_TYPES:
        return None
    source_path = runtime_event_source_path(event)
    if not source_path:
        return None
    data = runtime_event_data(event)
    timestamp = str(event.get("timestamp") or event.get("created_at") or "").strip()
    success = runtime_bool(data.get("success"), str(event.get("status") or "").casefold() == "succeeded")
    status = runtime_outcome_status(event, data)
    reason = str(data.get("reason") or data.get("suggested_action") or "").strip()
    error_code = str(data.get("error_code") or data.get("ErrorCode") or "").strip()
    outcome = {
        "runtime_outcome_event_type": event_type,
        "runtime_outcome_event_id": str(event.get("event_id") or "").strip(),
        "runtime_outcome_status": status,
        "runtime_outcome_success": success,
        "runtime_outcome_at": timestamp,
        "runtime_outcome_stage": str(event.get("stage") or data.get("stage") or data.get("Stage") or "").strip(),
        "runtime_outcome_route": str(data.get("route") or event.get("route") or "").strip(),
        "runtime_outcome_reason": reason,
        "runtime_outcome_error_code": error_code,
        "runtime_outcome_completion_status": str(data.get("completion_status") or "").strip(),
        "runtime_outcome_queue_terminal": runtime_bool(data.get("queue_terminal"), None),
        "runtime_outcome_retryable": runtime_bool(data.get("retryable"), None),
        "runtime_outcome_publish_state": str(data.get("publish_state") or "").strip(),
        "runtime_outcome_publish_mode": str(data.get("publish_mode") or "").strip(),
        "runtime_outcome_output_path": str(data.get("output_path") or "").strip(),
        "runtime_outcome_output_size_bytes": runtime_int(data.get("output_size_bytes"), 0),
        "runtime_outcome_source_path": source_path,
        "runtime_outcome_match": "exact_source_path",
    }
    outcome.update(
        datetime_freshness_fields(
            timestamp,
            prefix="runtime_outcome",
            stale_after_seconds=RUNTIME_OUTCOME_STALE_AFTER_SECONDS,
        )
    )
    return outcome


def runtime_outcome_index(events: Iterable[Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for event in events:
        outcome = runtime_outcome_from_event(event)
        if outcome is None:
            continue
        source_key = source_identity_key(outcome.get("runtime_outcome_source_path"))
        if source_key:
            index[source_key] = outcome
    return index
