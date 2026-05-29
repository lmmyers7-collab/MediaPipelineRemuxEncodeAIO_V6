"""Read-only retry-state contract for failure preview rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

RETRY_STATE_SCHEMA_VERSION = "desktop_retry_state.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(row.get(key))
        if value:
            return value
    return ""


def _row_int(row: dict[str, Any], *keys: str) -> int:
    raw: Any = None
    for key in keys:
        if key in row:
            raw = row.get(key)
            break
    try:
        return max(0, int(raw)) if raw not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


def _row_bool_or_none(row: dict[str, Any], *keys: str) -> bool | None:
    raw: Any = None
    found = False
    for key in keys:
        if key in row:
            raw = row.get(key)
            found = True
            break
    if not found:
        return None
    if isinstance(raw, bool):
        return raw
    text = _text(raw).casefold()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _row_identity(row: dict[str, Any]) -> str:
    parts = [
        _row_text(row, "source_json"),
        _row_text(row, "source_path"),
        _row_text(row, "job_id"),
        _row_text(row, "stage"),
        _row_text(row, "error_code"),
        _row_text(row, "recorded_at"),
    ]
    return "\u001f".join(parts).casefold()


def _source_name(path_text: str) -> str:
    if not path_text:
        return ""
    try:
        return Path(path_text).name
    except Exception:
        return path_text


def retry_state_for_failure_row(row: dict[str, Any]) -> dict[str, object]:
    classification = _row_text(row, "classification", "class").casefold()
    retryable_raw = _row_bool_or_none(row, "retryable")
    retryable = retryable_raw if retryable_raw is not None else classification == "transient"
    attempt = _row_int(row, "retry_count", "RetryCount")
    max_attempts = _row_int(row, "retry_limit", "RetryLimit")
    exhausted = max_attempts > 0 and attempt >= max_attempts
    blocked = classification in {"operator_required", "permanent"} or exhausted or retryable is False
    retry_allowed = bool(classification == "transient" and retryable and not exhausted)
    reason = _row_text(row, "reason", "last_failure_reason", "message", "error")
    suggested_action = _row_text(row, "suggested_action", "operator_action", "recommended_action", "next_step")
    source_path = _row_text(row, "source_path", "SourcePath", "source_full_path")
    source_json = _row_text(row, "source_json")
    job_id = _row_text(row, "job_id", "JobId")
    status_state = "unknown"
    unavailable_reason = ""
    if retry_allowed and max_attempts > 0:
        status_state = "retrying"
    elif retry_allowed:
        status_state = "warning"
        unavailable_reason = "Retry limit was not reported; transient failures are retried by the backend queue pass."
    elif blocked:
        status_state = "blocked"
    elif classification or reason:
        status_state = "warning"
        unavailable_reason = "Retry eligibility could not be determined from the failure row."
    else:
        unavailable_reason = "No failure classification or retry evidence was reported."

    if retry_allowed:
        route_or_command = "automatic_next_queue_pass"
        safe_next_action = (
            "Backend will retry this transient failure on the next backend queue pass. Compare logs first; no WebView retry button is exposed."
        )
    elif classification in {"operator_required", "permanent"} or exhausted:
        route_or_command = "none_exposed"
        safe_next_action = (
            suggested_action
            or "Fix the root cause, inspect the marker, clear it only when appropriate, then launch/rerun through backend-owned controls."
        )
    else:
        route_or_command = "none_exposed"
        safe_next_action = suggested_action or "Review failure evidence before deciding whether a backend rerun is safe."

    if exhausted and "retry limit" not in safe_next_action.casefold():
        safe_next_action = f"{safe_next_action} Retry limit {max_attempts} is reached."

    return {
        "schema_version": RETRY_STATE_SCHEMA_VERSION,
        "row_key": _row_identity(row),
        "job_id": job_id,
        "source_path": source_path,
        "source_name": _source_name(source_path),
        "source_json": source_json,
        "stage": _row_text(row, "stage", "Stage", "operation"),
        "error_code": _row_text(row, "error_code", "ErrorCode"),
        "classification": classification,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "last_failure_reason": reason,
        "retry_allowed": retry_allowed,
        "retry_route_or_command": route_or_command,
        "safe_next_action": safe_next_action,
        "status_state": status_state,
        "unavailable_reason": unavailable_reason,
        "read_only": True,
    }


def retry_state_payload(
    rows: object,
    *,
    source: str = "",
    source_kind: str = "",
) -> dict[str, object]:
    valid_rows = [row for row in rows or [] if isinstance(row, dict)]
    retry_rows = [retry_state_for_failure_row(row) for row in valid_rows]
    retryable_count = sum(1 for row in retry_rows if row.get("retry_allowed") is True)
    blocked_count = sum(1 for row in retry_rows if row.get("status_state") == "blocked")
    warning_count = sum(1 for row in retry_rows if row.get("status_state") == "warning")
    unavailable_count = sum(1 for row in retry_rows if row.get("unavailable_reason"))
    if retryable_count:
        status_state = "retrying"
    elif blocked_count:
        status_state = "blocked"
    elif warning_count:
        status_state = "warning"
    elif retry_rows:
        status_state = "loaded"
    else:
        status_state = "idle"
    return {
        "schema_version": RETRY_STATE_SCHEMA_VERSION,
        "read_only": True,
        "source": source,
        "source_kind": source_kind,
        "status_state": status_state,
        "row_count": len(retry_rows),
        "retryable_count": retryable_count,
        "blocked_count": blocked_count,
        "warning_count": warning_count,
        "unavailable_count": unavailable_count,
        "rows": retry_rows,
        "operator_guidance": (
            "Retry state is evidence-only. Transient rows retry on the next backend queue pass; blocked rows require operator review before marker clear or rerun."
        ),
    }


__all__ = [
    "RETRY_STATE_SCHEMA_VERSION",
    "retry_state_for_failure_row",
    "retry_state_payload",
]
