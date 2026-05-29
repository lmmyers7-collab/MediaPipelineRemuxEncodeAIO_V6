from __future__ import annotations

from typing import Any
import uuid


OPTIONS_RESPONSE_HEADERS = [
    ("Allow", "GET, POST, OPTIONS"),
    ("Access-Control-Allow-Origin", "http://127.0.0.1"),
    ("Access-Control-Allow-Headers", "Authorization, X-MediaPipeline-Token, Content-Type"),
    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
    ("Content-Length", "0"),
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


def route_validation_error_payload(route: str, exc: Exception) -> dict[str, Any]:
    return {"error": bounded_error_text(exc), "path": route}


def should_record_command_payload(status: int) -> bool:
    return int(status) < 400
