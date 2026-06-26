"""Failure resolution lifecycle journal helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FAILURE_RESOLUTION_JOURNAL_SCHEMA_VERSION = "failure_resolution_journal.v1"
FAILURE_RESOLUTION_EVENT_SCHEMA_VERSION = "failure_resolution_event.v1"
FAILURE_LIFECYCLE_PREVIEW_SCHEMA_VERSION = "failure_lifecycle_transition_preview.v1"
FAILURE_LIFECYCLE_RESULT_SCHEMA_VERSION = "failure_lifecycle_transition_result.v1"

FAILURE_LIFECYCLE_TRANSITIONS: dict[str, str] = {
    "acknowledge": "acknowledged",
    "start_work": "working",
    "complete_step": "working",
    "waive_step": "working",
    "mark_resolved": "resolved",
    "reopen": "reopened",
}
FAILURE_LIFECYCLE_PREVIEW_REQUIRED = {"mark_resolved", "reopen", "waive_step"}
FAILURE_LIFECYCLE_REASON_REQUIRED = {"mark_resolved", "reopen", "waive_step"}


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def failure_resolution_journal_root(resolved: Any) -> Path:
    state_root = getattr(resolved, "state_root", None)
    local_base = getattr(resolved, "local_base", None)
    app_root = getattr(resolved, "app_root", None)
    state_root = state_root or (local_base / "State" if local_base else app_root / "State")
    return state_root / "Failures" / "ResolutionJournal"


def failure_resolution_journal_path(resolved: Any) -> Path:
    return failure_resolution_journal_root(resolved) / "events.jsonl"


def _bounded_text(value: Any, *, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_json(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def failure_resolution_read_events(resolved: Any, *, limit: int = 5000) -> list[dict[str, Any]]:
    path = failure_resolution_journal_path(resolved)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines[-max(1, limit):]:
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def failure_resolution_journal_state(resolved: Any) -> dict[str, Any]:
    events = failure_resolution_read_events(resolved)
    by_key: dict[str, dict[str, Any]] = {}
    for event in events:
        journal_key = _bounded_text(event.get("journal_key"), limit=256)
        if not journal_key:
            continue
        by_key[journal_key] = event
    return {
        "schema_version": FAILURE_RESOLUTION_JOURNAL_SCHEMA_VERSION,
        "path": str(failure_resolution_journal_path(resolved)),
        "event_count": len(events),
        "events": events,
        "by_journal_key": by_key,
    }


def failure_lifecycle_fingerprint(
    *,
    journal_key: str,
    transition: str,
    step_id: str,
    group: dict[str, Any],
    reason: str = "",
) -> str:
    clearable_paths = sorted(str(path) for path in group.get("clearable_marker_paths") or [] if str(path or "").strip())
    payload = {
        "journal_key": journal_key,
        "transition": transition,
        "step_id": step_id,
        "reason": _bounded_text(reason, limit=200),
        "row_count": int(group.get("row_count") or 0),
        "clearable_marker_paths": clearable_paths,
        "lifecycle_state": group.get("lifecycle_state") or "",
        "last_transition_at": group.get("last_transition_at") or "",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def failure_lifecycle_transition_preview(
    *,
    journal_key: str,
    transition: str,
    step_id: str,
    group: dict[str, Any],
    reason: str = "",
) -> dict[str, Any]:
    next_state = FAILURE_LIFECYCLE_TRANSITIONS.get(transition, "")
    active_marker_count = int(group.get("clearable_count") or 0)
    blockers: list[str] = []
    if transition == "mark_resolved" and active_marker_count > 0:
        blockers.append("Active failure markers remain; preview marker clear and clear markers before marking resolved.")
    if transition not in FAILURE_LIFECYCLE_TRANSITIONS:
        blockers.append(f"Unsupported failure lifecycle transition: {transition}")
    if transition in FAILURE_LIFECYCLE_REASON_REQUIRED and not _bounded_text(reason):
        blockers.append(f"Failure lifecycle transition '{transition}' requires a non-empty reason.")
    return {
        "schema_version": FAILURE_LIFECYCLE_PREVIEW_SCHEMA_VERSION,
        "journal_key": journal_key,
        "transition": transition,
        "step_id": step_id,
        "current_state": group.get("lifecycle_state") or "new",
        "next_state": next_state,
        "active_marker_count": active_marker_count,
        "active_failure_row_count": int(group.get("row_count") or 0),
        "dry_run_fingerprint": failure_lifecycle_fingerprint(
            journal_key=journal_key,
            transition=transition,
            step_id=step_id,
            group=group,
            reason=reason,
        ),
        "safe_to_apply": not blockers,
        "blockers": blockers,
        "would_write_paths": [str(failure_resolution_journal_path_for_group(group))],
        "would_not_touch": [
            "source media",
            "scratch media",
            "output media",
            "completed manifests",
            "pending publish state",
            "failure reports",
            "active failure markers",
        ],
    }


def failure_resolution_journal_path_for_group(group: dict[str, Any]) -> str:
    return str(group.get("resolution_journal_path") or "State\\Failures\\ResolutionJournal\\events.jsonl")


def failure_resolution_append_event(
    resolved: Any,
    *,
    journal_key: str,
    transition: str,
    step_id: str = "",
    reason: str = "",
    operator_note: str = "",
    group: dict[str, Any] | None = None,
    dry_run_fingerprint: str = "",
) -> dict[str, Any]:
    next_state = FAILURE_LIFECYCLE_TRANSITIONS[transition]
    event = {
        "schema_version": FAILURE_RESOLUTION_EVENT_SCHEMA_VERSION,
        "recorded_at": _utc_now_text(),
        "journal_key": _bounded_text(journal_key, limit=256),
        "transition": transition,
        "lifecycle_state": next_state,
        "step_id": _bounded_text(step_id, limit=120),
        "reason": _bounded_text(reason, limit=500),
        "operator_note": _bounded_text(operator_note, limit=500),
        "dry_run_fingerprint": _bounded_text(dry_run_fingerprint, limit=128),
        "group_snapshot": _safe_json(
            {
                "group_key": group.get("group_key") if group else "",
                "owner": group.get("owner") if group else "",
                "stage": group.get("stage") if group else "",
                "error_code": group.get("error_code") if group else "",
                "row_count": group.get("row_count") if group else 0,
                "clearable_count": group.get("clearable_count") if group else 0,
                "affected_sources": (group.get("affected_sources") or [])[:5] if group else [],
            }
        ),
        "touches_media": False,
        "writes_failure_resolution_journal": True,
    }
    path = failure_resolution_journal_path(resolved)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
    return event


__all__ = [
    "FAILURE_LIFECYCLE_PREVIEW_REQUIRED",
    "FAILURE_LIFECYCLE_REASON_REQUIRED",
    "FAILURE_LIFECYCLE_TRANSITIONS",
    "FAILURE_RESOLUTION_EVENT_SCHEMA_VERSION",
    "FAILURE_RESOLUTION_JOURNAL_SCHEMA_VERSION",
    "failure_lifecycle_fingerprint",
    "failure_lifecycle_transition_preview",
    "failure_resolution_append_event",
    "failure_resolution_journal_path",
    "failure_resolution_journal_state",
]
