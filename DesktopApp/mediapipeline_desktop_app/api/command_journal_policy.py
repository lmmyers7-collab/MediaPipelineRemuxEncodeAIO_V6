from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


COMMAND_HISTORY_SCHEMA_VERSION = "desktop_command_history.v1"
COMMAND_RESULT_SCHEMA_VERSION = "desktop_command_result.v1"


def is_command_result_payload(payload: Mapping[str, Any]) -> bool:
    return str(payload.get("schema_version") or "") == COMMAND_RESULT_SCHEMA_VERSION


def scalar_text(value: Any, *, limit: int) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "..."


def string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [scalar_text(item, limit=500) for item in value[:limit]]


def string_dict(value: Any, *, limit: int) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for index, (key, item) in enumerate(value.items()):
        if index >= limit:
            break
        result[scalar_text(key, limit=120)] = scalar_text(item, limit=500)
    return result


def summarize_command_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "command": scalar_text(payload.get("command"), limit=160) or "unknown",
        "ok": bool(payload.get("ok")),
        "severity": scalar_text(payload.get("severity"), limit=40) or "info",
        "message": scalar_text(payload.get("message"), limit=2000),
        "job_id": scalar_text(payload.get("job_id"), limit=120),
        "refresh_hint": scalar_text(payload.get("refresh_hint"), limit=80),
        "warnings": string_list(payload.get("warnings"), limit=20),
        "errors": string_list(payload.get("errors"), limit=20),
        "log_paths": string_dict(payload.get("log_paths"), limit=12),
    }


def bounded_history_limit(limit: int, max_entries: int) -> int:
    return max(1, min(int(limit or 20), max_entries))


def command_history_mapping(entries: list[dict[str, Any]], *, limit: int, max_entries: int) -> dict[str, Any]:
    safe_limit = bounded_history_limit(limit, max_entries)
    safe_entries = [dict(entry) for entry in entries[:safe_limit]]
    return {
        "schema_version": COMMAND_HISTORY_SCHEMA_VERSION,
        "count": len(safe_entries),
        "entries": safe_entries,
    }


def sanitize_journal_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "at": scalar_text(entry.get("at"), limit=80),
        "command": scalar_text(entry.get("command"), limit=160) or "unknown",
        "ok": bool(entry.get("ok")),
        "severity": scalar_text(entry.get("severity"), limit=40) or "info",
        "message": scalar_text(entry.get("message"), limit=2000),
        "job_id": scalar_text(entry.get("job_id"), limit=120),
        "refresh_hint": scalar_text(entry.get("refresh_hint"), limit=80),
        "warnings": string_list(entry.get("warnings"), limit=20),
        "errors": string_list(entry.get("errors"), limit=20),
        "log_paths": string_dict(entry.get("log_paths"), limit=12),
    }


def valid_journal_entries(value: Any, *, max_entries: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    safe_max_entries = max(1, int(max_entries))
    return [sanitize_journal_entry(entry) for entry in value if isinstance(entry, dict)][:safe_max_entries]
