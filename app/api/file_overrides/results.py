from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.contracts.config import Config


FILE_OVERRIDE_POST_KEYS = frozenset(
    {"path", "audio", "subtitles", "routing", "video", "clear", "clear_all", "clear_fields"}
)
ROUTE_PREVIEW_POST_KEYS = frozenset({"path", "proposed_override"})
ROUTE_PREVIEW_SCHEMA_VERSION = "queue_file_override_route_preview.v1"
ROUTE_PREVIEW_COMMAND = "queue.file_overrides.route_preview"
FOLDER_PREVIEW_POST_KEYS = frozenset({"folder_path", "proposed_override", "options"})
FOLDER_PREVIEW_SCHEMA_VERSION = "queue_file_override_folder_preview.v1"
FOLDER_PREVIEW_COMMAND = "queue.file_overrides.folder_preview"
FOLDER_RULE_POST_KEYS = frozenset({"folder_path", "override", "confirmation", "clear"})
FOLDER_RULE_COMMAND = "queue.file_overrides.folder_rule"
TRACKS_SCHEMA_VERSION = "queue_file_override_tracks.v1"
TRACKS_COMMAND = "queue.file_overrides.tracks"


def _fo_command_result_payload(payload: dict) -> dict:
    result = dict(payload)
    result["schema_version"] = "desktop_command_result.v1"
    result.setdefault("refresh_hint", "queue")
    if not result.get("ok") and "errors" not in result:
        result["errors"] = [str(result.get("message") or "File override command failed.")]
    return result


def _fo_unavailable(reason: str, *, command_result: bool = False) -> dict:
    payload = {
        "ok":       False,
        "command":  "queue.file_overrides",
        "severity": "error",
        "message":  f"File overrides service unavailable: {reason}",
    }
    return _fo_command_result_payload(payload) if command_result else payload


def _fo_error(message: str) -> dict:
    return _fo_command_result_payload({
        "ok":       False,
        "command":  "queue.file_overrides",
        "severity": "error",
        "message":  message,
    })


def _fo_validation_error(errors: list[str]) -> dict:
    return _fo_command_result_payload({
        "ok":       False,
        "command":  "queue.file_overrides",
        "severity": "error",
        "message":  "Invalid file override payload.",
        "errors":   errors,
    })


def _fo_read_error(command: str, message: str) -> dict:
    return {
        "ok":       False,
        "command":  command,
        "severity": "error",
        "message":  message,
    }


def _unsupported_post_key_errors(request: Mapping[str, Any]) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in FILE_OVERRIDE_POST_KEYS)
    if not unknown:
        return []
    return [
        "Unsupported file override request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(FILE_OVERRIDE_POST_KEYS))}."
    ]


def _unsupported_route_preview_key_errors(request: Mapping[str, Any]) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in ROUTE_PREVIEW_POST_KEYS)
    if not unknown:
        return []
    return [
        "Unsupported route preview request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(ROUTE_PREVIEW_POST_KEYS))}."
    ]


def _unsupported_folder_preview_key_errors(request: Mapping[str, Any]) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in FOLDER_PREVIEW_POST_KEYS)
    if not unknown:
        return []
    return [
        "Unsupported folder preview request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(FOLDER_PREVIEW_POST_KEYS))}."
    ]


def _unsupported_folder_rule_key_errors(request: Mapping[str, Any]) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in FOLDER_RULE_POST_KEYS)
    if not unknown:
        return []
    return [
        "Unsupported folder rule request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(FOLDER_RULE_POST_KEYS))}."
    ]


def _query_text(query: dict[str, Any] | None, key: str) -> str:
    if not query or not isinstance(query, dict):
        return ""
    value = query.get(key, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _literal_choices(field_name: str) -> tuple[str, ...]:
    from typing import get_args

    field = Config.model_fields.get(field_name)
    return tuple(str(item) for item in get_args(field.annotation)) if field is not None else ()


def _choice_error(field_path: str, value: Any, choices: tuple[str, ...]) -> str | None:
    text = str(value or "").strip().casefold()
    if not text or text not in choices:
        return f"'{field_path}' must be one of: {', '.join(choices)}."
    return None


def _positive_int_value(errors: list[str], field_path: str, value: Any, *, minimum: int, maximum: int) -> int | None:
    if type(value) is not int:
        errors.append(f"'{field_path}' must be an integer.")
        return None
    if value < minimum or value > maximum:
        errors.append(f"'{field_path}' must be between {minimum} and {maximum}.")
        return None
    return int(value)


def _route_preview_base_payload(*, ok: bool, severity: str, message: str) -> dict[str, Any]:
    return {
        "ok":             ok,
        "command":        ROUTE_PREVIEW_COMMAND,
        "severity":       severity,
        "schema_version": ROUTE_PREVIEW_SCHEMA_VERSION,
        "message":        message,
    }


def _route_preview_error(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    payload = _route_preview_base_payload(ok=False, severity="error", message=message)
    payload["errors"] = errors or [message]
    return payload


def _route_preview_validation_error(errors: list[str]) -> dict[str, Any]:
    return _route_preview_error("Invalid route preview payload.", errors)


def _folder_preview_base_payload(*, ok: bool, severity: str, message: str) -> dict[str, Any]:
    return {
        "ok":             ok,
        "command":        FOLDER_PREVIEW_COMMAND,
        "severity":       severity,
        "schema_version": FOLDER_PREVIEW_SCHEMA_VERSION,
        "message":        message,
        "preview_only":   True,
    }


def _folder_preview_error(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    payload = _folder_preview_base_payload(ok=False, severity="error", message=message)
    payload["errors"] = errors or [message]
    return payload


def _folder_preview_validation_error(errors: list[str]) -> dict[str, Any]:
    return _folder_preview_error("Invalid folder preview payload.", errors)


def _folder_rule_error(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    payload = {
        "ok":       False,
        "command":  FOLDER_RULE_COMMAND,
        "severity": "error",
        "message":  message,
    }
    if errors:
        payload["errors"] = errors
    return _fo_command_result_payload(payload)


def _folder_rule_validation_error(errors: list[str]) -> dict[str, Any]:
    return _folder_rule_error("Invalid folder rule payload.", errors)
