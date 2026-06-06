from __future__ import annotations

from typing import Any
import uuid

from .command_journal_policy import COMMAND_RESULT_SCHEMA_VERSION
from .http_helpers import LOCAL_API_CONTENT_SECURITY_POLICY

LOCAL_API_SECURITY_RESPONSE_HEADERS = [
    ("Cache-Control", "no-store"),
    ("Content-Security-Policy", LOCAL_API_CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
]


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


def should_record_command_payload(status: int) -> bool:
    return int(status) < 400
