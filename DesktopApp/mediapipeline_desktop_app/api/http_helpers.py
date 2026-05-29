from __future__ import annotations

from collections.abc import Callable
import http.server
import ipaddress
import json
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


JsonSender = Callable[[dict[str, Any], int], None]

NO_TOKEN_DEV_ENV_VAR = "MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV"


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


def _strip_host_brackets(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("[") and "]" in text:
        return text[1 : text.index("]")]
    return text


def split_host_port(value: str) -> tuple[str, int | None]:
    text = str(value or "").strip()
    if not text:
        return "", None
    if text.startswith("[") and "]" in text:
        host = text[1 : text.index("]")]
        remainder = text[text.index("]") + 1 :]
        if remainder.startswith(":") and remainder[1:].isdigit():
            return host, int(remainder[1:])
        return host, None
    if text.count(":") == 1:
        host, raw_port = text.rsplit(":", 1)
        if raw_port.isdigit():
            return host, int(raw_port)
    return text, None


def is_loopback_host(host: str) -> bool:
    text = _strip_host_brackets(host).strip().casefold()
    if text == "localhost":
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def no_token_dev_allowed(host: str, *, environ: dict[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    enabled = str(env.get(NO_TOKEN_DEV_ENV_VAR, "") or "").strip().casefold() in {"1", "true", "yes", "on"}
    return enabled and is_loopback_host(host)


def local_api_allowed_hosts(bind_host: str, port: int) -> set[str]:
    allowed = {"127.0.0.1", "localhost", "::1"}
    host = _strip_host_brackets(bind_host).strip().casefold()
    if host and host not in {"0.0.0.0", "::"}:
        allowed.add(host)
    return allowed


def host_header_authorized(host_header: str, *, bind_host: str, port: int) -> bool:
    host, supplied_port = split_host_port(host_header)
    if not host:
        return False
    if supplied_port is not None and int(supplied_port) != int(port):
        return False
    return _strip_host_brackets(host).strip().casefold() in local_api_allowed_hosts(bind_host, port)


def local_api_allowed_origins(*, bind_host: str, port: int, shell_surface: str = "webview") -> set[str]:
    origins = set()
    for host in local_api_allowed_hosts(bind_host, port):
        display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        origins.add(f"http://{display_host}:{int(port)}")
    if str(shell_surface or "").strip().casefold() == "tauri":
        origins.add("tauri://localhost")
    return origins


def origin_header_authorized(
    origin_header: str,
    *,
    bind_host: str,
    port: int,
    shell_surface: str = "webview",
) -> bool:
    origin = str(origin_header or "").strip()
    if not origin:
        return True
    parsed = urlsplit(origin)
    if not parsed.scheme or not parsed.hostname:
        return False
    if parsed.scheme == "tauri":
        return origin in local_api_allowed_origins(bind_host=bind_host, port=port, shell_surface=shell_surface)
    if parsed.scheme != "http":
        return False
    try:
        parsed_port = parsed.port if parsed.port is not None else 80
    except ValueError:
        return False
    candidate_host = parsed.hostname.casefold()
    return (
        parsed_port == int(port)
        and candidate_host in local_api_allowed_hosts(bind_host, port)
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
    )


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
