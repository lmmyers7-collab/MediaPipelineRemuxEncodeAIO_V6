from __future__ import annotations

from collections.abc import Callable
import http.server
import json
import secrets
from pathlib import Path
from typing import Any


JsonSender = Callable[[dict[str, Any], int], None]


LOCAL_API_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'none'"
)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value is not allowed: {value}")


def query_value(query: dict[str, list[str]], name: str, default: str = "") -> str:
    values = query.get(name)
    if not values:
        return default
    return str(values[0])


def query_int(query: dict[str, list[str]], name: str, default: int) -> int:
    try:
        return int(query_value(query, name, str(default)))
    except (TypeError, ValueError):
        return int(default)


def query_bool(query: dict[str, list[str]], name: str, default: bool = False) -> bool:
    raw = query_value(query, name, "true" if default else "false").strip().casefold()
    return raw in {"1", "true", "yes", "on"}


def request_authorized(
    headers: Any,
    query: dict[str, list[str]],
    *,
    token: str,
    require_token: bool,
) -> bool:
    if not require_token:
        return True
    candidates = [
        str(headers.get("X-MediaPipeline-Token") or ""),
    ]
    authorization = str(headers.get("Authorization") or "")
    if authorization.casefold().startswith("bearer "):
        candidates.append(authorization[7:].strip())
    return any(candidate and secrets.compare_digest(candidate, token) for candidate in candidates)


def read_json_body(
    handler: http.server.BaseHTTPRequestHandler,
    send_json: JsonSender,
    *,
    max_bytes: int = 1_000_000,
) -> dict[str, Any] | None:
    raw_length = str(handler.headers.get("Content-Length") or "0").strip()
    try:
        length = int(raw_length)
    except ValueError:
        send_json({"error": "invalid content length"}, 400)
        return None
    if length < 0:
        send_json({"error": "invalid content length"}, 400)
        return None
    if length > max_bytes:
        send_json({"error": "request body is too large"}, 413)
        return None
    raw_body = handler.rfile.read(length) if length else b"{}"
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}", parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        send_json({"error": f"invalid json body: {exc}"}, 400)
        return None
    if not isinstance(payload, dict):
        send_json({"error": "json body must be an object"}, 400)
        return None
    return payload


def discard_request_body(
    handler: http.server.BaseHTTPRequestHandler,
    *,
    max_bytes: int = 1_000_000,
) -> None:
    raw_length = str(handler.headers.get("Content-Length") or "0").strip()
    try:
        length = int(raw_length)
    except ValueError:
        return
    if length <= 0 or length > max_bytes:
        return

    connection = getattr(handler, "connection", None)
    old_timeout: float | None = None
    timeout_changed = False
    try:
        if hasattr(connection, "gettimeout") and hasattr(connection, "settimeout"):
            old_timeout = connection.gettimeout()
            connection.settimeout(0.5)
            timeout_changed = True
        remaining = length
        while remaining > 0:
            chunk = handler.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)
    except OSError:
        return
    finally:
        if timeout_changed and hasattr(connection, "settimeout"):
            try:
                connection.settimeout(old_timeout)
            except OSError:
                pass


def send_bytes(
    handler: http.server.BaseHTTPRequestHandler,
    body: bytes,
    *,
    status: int = 200,
    content_type: str = "application/octet-stream",
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Security-Policy", LOCAL_API_CONTENT_SECURITY_POLICY)
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.end_headers()
    handler.wfile.write(body)


def content_type_for(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".js":
        return "text/javascript; charset=utf-8"
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".html":
        return "text/html; charset=utf-8"
    if suffix == ".json":
        return "application/json; charset=utf-8"
    return "application/octet-stream"


def resolve_asset_path(static_root: Path, route: str) -> Path | None:
    relative = route.removeprefix("/assets/").strip("/")
    if not relative or "\\" in relative or ".." in relative.split("/"):
        return None
    asset_root = (static_root / "assets").resolve()
    path = (asset_root / relative).resolve()
    try:
        path.relative_to(asset_root)
    except ValueError:
        return None
    if not path.exists() or not path.is_file():
        return None
    return path
