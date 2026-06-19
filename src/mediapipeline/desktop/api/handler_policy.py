from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import uuid

from .command_journal_policy import COMMAND_RESULT_SCHEMA_VERSION
from .contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
from .http_helpers import LOCAL_API_CONTENT_SECURITY_POLICY

LOCAL_API_SECURITY_RESPONSE_HEADERS = [
    ("Cache-Control", "no-store"),
    ("Content-Security-Policy", LOCAL_API_CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
]

_COMMAND_ROUTE_BY_PATH = {
    str(row.get("path") or ""): row
    for row in LOCAL_API_COMMAND_ROUTE_CONTRACT
    if isinstance(row, dict)
}


def options_response_headers(allowed_origin: str = "http://127.0.0.1") -> list[tuple[str, str]]:
    origin = str(allowed_origin or "").strip() or "http://127.0.0.1"
    return [
        ("Allow", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Origin", origin),
        ("Vary", "Origin"),
        ("Access-Control-Allow-Headers", "Authorization, X-MediaPipeline-Token, Content-Type"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Content-Length", "0"),
        *LOCAL_API_SECURITY_RESPONSE_HEADERS,
    ]


OPTIONS_RESPONSE_HEADERS = options_response_headers()


def cors_response_headers(allowed_origin: str = "http://127.0.0.1") -> list[tuple[str, str]]:
    origin = str(allowed_origin or "").strip() or "http://127.0.0.1"
    return [
        ("Access-Control-Allow-Origin", origin),
        ("Vary", "Origin"),
    ]


def bounded_error_text(value: object, *, limit: int = 2000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def unauthorized_payload() -> dict[str, Any]:
    return {"error": "unauthorized"}


def not_found_payload(route: str) -> dict[str, Any]:
    return {"error": "not found", "path": route}


def route_exception_payload(route: str, exc: Exception) -> dict[str, Any]:
    _ = exc
    return {"error": "internal route error", "path": route, "error_id": uuid.uuid4().hex[:12]}


def route_exception_journal_payload(route: str, response_payload: Mapping[str, Any]) -> dict[str, Any]:
    path = bounded_error_text(response_payload.get("path") or route, limit=500)
    error_id = bounded_error_text(response_payload.get("error_id"), limit=80)
    return {
        "schema_version": COMMAND_RESULT_SCHEMA_VERSION,
        "command": "local_api.route_exception",
        "ok": False,
        "severity": "error",
        "message": f"Command route failed for {path}.",
        "errors": ["Internal route error."],
        "refresh_hint": "diagnostics",
        "data": {
            "path": path,
            "status": 500,
            "error_id": error_id,
        },
    }


def route_validation_error_payload(route: str, exc: Exception) -> dict[str, Any]:
    return {"error": bounded_error_text(exc), "path": route}


def route_validation_journal_payload(route: str, exc: Exception) -> dict[str, Any]:
    error = bounded_error_text(exc)
    return {
        "schema_version": COMMAND_RESULT_SCHEMA_VERSION,
        "command": "local_api.validation_failed",
        "ok": False,
        "severity": "error",
        "message": f"Rejected invalid command payload for {route}.",
        "errors": [error],
        "data": {
            "path": route,
            "status": 400,
        },
    }


def should_record_validation_failure_journal(route: str) -> bool:
    metadata = _COMMAND_ROUTE_BY_PATH.get(str(route or ""))
    if not isinstance(metadata, dict):
        return True
    if metadata.get("journaled") is False:
        return False
    if str(metadata.get("effect") or "").casefold() == "secret-transfer":
        return False
    return True


def should_record_route_exception_journal(route: str) -> bool:
    return should_record_validation_failure_journal(route)


def should_record_command_payload(status: int) -> bool:
    return int(status) < 400
