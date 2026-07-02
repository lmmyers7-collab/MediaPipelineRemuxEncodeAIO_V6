from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, UTC
import math
from typing import Any

from mediapipeline.core.network.url_policy import redact_network_secret_text


COMMAND_HISTORY_SCHEMA_VERSION = "desktop_command_history.v1"
COMMAND_RESULT_SCHEMA_VERSION = "desktop_command_result.v1"
COMMAND_EVIDENCE_DICT_LIMIT = 80
COMMAND_EVIDENCE_LIST_LIMIT = 20
COMMAND_EVIDENCE_TEXT_LIMIT = 500
COMMAND_EVIDENCE_DEPTH_LIMIT = 4
REDACTED_COMMAND_EVIDENCE_VALUE = "<redacted>"
SENSITIVE_COMMAND_EVIDENCE_TERMS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "join_blob",
    "joinblob",
    "password",
    "secret",
    "token",
)


def is_command_result_payload(payload: Mapping[str, Any]) -> bool:
    return str(payload.get("schema_version") or "") == COMMAND_RESULT_SCHEMA_VERSION


def scalar_text(value: Any, *, limit: int) -> str:
    if value is None:
        return ""
    text = redact_network_secret_text(value).replace("\r\n", "\n").replace("\r", "\n")
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


def sensitive_command_evidence_key(key: Any) -> bool:
    text = str(key or "").casefold()
    return any(term in text for term in SENSITIVE_COMMAND_EVIDENCE_TERMS)


def bounded_command_evidence(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else scalar_text(value, limit=COMMAND_EVIDENCE_TEXT_LIMIT)
    if isinstance(value, str):
        return scalar_text(value, limit=COMMAND_EVIDENCE_TEXT_LIMIT)
    if depth >= COMMAND_EVIDENCE_DEPTH_LIMIT:
        return scalar_text(value, limit=COMMAND_EVIDENCE_TEXT_LIMIT)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= COMMAND_EVIDENCE_DICT_LIMIT:
                break
            safe_key = scalar_text(key, limit=120) or "unknown"
            result[safe_key] = REDACTED_COMMAND_EVIDENCE_VALUE if sensitive_command_evidence_key(safe_key) else bounded_command_evidence(item, depth=depth + 1)
        return result
    if isinstance(value, tuple | list):
        return [bounded_command_evidence(item, depth=depth + 1) for item in value[:COMMAND_EVIDENCE_LIST_LIMIT]]
    return scalar_text(value, limit=COMMAND_EVIDENCE_TEXT_LIMIT)


def summarize_command_payload(payload: Mapping[str, Any], *, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
    entry = {
        "at": datetime.now(UTC).isoformat(),
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
    if "data" in payload:
        entry["data"] = bounded_command_evidence(payload.get("data"))
    request_evidence = request
    if request_evidence is None:
        raw_request = payload.get("request") or payload.get("submitted_request")
        request_evidence = raw_request if isinstance(raw_request, Mapping) else None
    if request_evidence is not None:
        entry["request"] = bounded_command_evidence(request_evidence)
    return entry


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
    safe = {
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
    if "data" in entry:
        safe["data"] = bounded_command_evidence(entry.get("data"))
    if "request" in entry:
        safe["request"] = bounded_command_evidence(entry.get("request"))
    return safe


def valid_journal_entries(value: Any, *, max_entries: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    safe_max_entries = max(1, int(max_entries))
    return [sanitize_journal_entry(entry) for entry in value if isinstance(entry, dict)][:safe_max_entries]
