from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import uuid

from .command_journal_policy import COMMAND_RESULT_SCHEMA_VERSION


# These routes either own process lifecycle or alter media/manifests. Their
# evidence is durable before execution; ordinary settings and read-only routes
# intentionally keep the existing lightweight command history policy.
STRICT_DURABLE_COMMAND_ROUTES = frozenset(
    {
        "/api/pipeline/start",
        "/api/pipeline/control",
        "/api/audit/start",
        "/api/audit/stop",
        "/api/rerun/start",
        "/api/rerun/control",
        "/api/rerun/continue",
        "/api/rerun/promote",
        "/api/rerun/network/start",
        "/api/rename/apply",
        "/api/rename/undo",
        "/api/pending-publish/repair-manifest",
        "/api/pending-publish/reconcile-orphan-payloads",
        "/api/completed/reconcile-manifest",
        "/api/completed/repair-sidecar-metadata",
        "/api/network/coordinator/start",
        "/api/network/coordinator/stop",
        "/api/network/worker/start",
        "/api/network/worker/stop",
        "/api/backend/shutdown",
        "/api/final-library-promotion/promote-queue",
    }
)


def requires_strict_durable_command_journal(route: str) -> bool:
    return route in STRICT_DURABLE_COMMAND_ROUTES
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


class OperatorRouteError(RuntimeError):
    """A safe, retryable route failure with an operator-facing explanation."""

    def __init__(self, *, code: str, operator_message: str, status: int = 503) -> None:
        super().__init__(operator_message)
        self.code = str(code or "backend_unavailable").strip() or "backend_unavailable"
        self.operator_message = bounded_error_text(operator_message, limit=500)
        self.status = int(status) if 400 <= int(status) <= 599 else 503


def _response_header_origin(allowed_origin: str) -> str:
    """Return a defense-in-depth CR/LF-free origin header value."""
    raw_origin = str(allowed_origin or "")
    sanitized_origin = raw_origin.replace("\r", "").replace("\n", "")
    if sanitized_origin != raw_origin:
        return "http://127.0.0.1"
    return sanitized_origin.strip() or "http://127.0.0.1"


def options_response_headers(allowed_origin: str = "http://127.0.0.1") -> list[tuple[str, str]]:
    origin = _response_header_origin(allowed_origin)
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
    origin = _response_header_origin(allowed_origin)
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
    if isinstance(exc, OperatorRouteError):
        return {
            "error": exc.operator_message,
            "code": exc.code,
            "path": route,
            "retryable": True,
            "status": exc.status,
            "error_id": uuid.uuid4().hex[:12],
        }
    return {"error": "internal route error", "path": route, "error_id": uuid.uuid4().hex[:12]}


def route_exception_status(exc: Exception) -> int:
    return exc.status if isinstance(exc, OperatorRouteError) else 500


def route_exception_journal_payload(route: str, response_payload: Mapping[str, Any]) -> dict[str, Any]:
    path = bounded_error_text(response_payload.get("path") or route, limit=500)
    error_id = bounded_error_text(response_payload.get("error_id"), limit=80)
    code = bounded_error_text(response_payload.get("code"), limit=120)
    error = (
        bounded_error_text(response_payload.get("error") or "Internal route error.", limit=500)
        if code
        else "Internal route error."
    )
    status = response_payload.get("status", 500)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 500
    return {
        "schema_version": COMMAND_RESULT_SCHEMA_VERSION,
        "command": "local_api.route_exception",
        "ok": False,
        "severity": "error",
        "message": f"Command route failed for {path}.",
        "errors": [error],
        "refresh_hint": "diagnostics",
        "data": {
            "path": path,
            "status": status,
            "error_id": error_id,
            "code": code,
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
