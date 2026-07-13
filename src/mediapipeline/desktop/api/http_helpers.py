from __future__ import annotations

from collections.abc import Callable
import errno
from http.cookies import SimpleCookie
import http.server
import ipaddress
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote
from urllib.parse import urlsplit

from mediapipeline.core.validation.strict_json import loads_strict_json


JsonSender = Callable[[dict[str, Any], int], None]

NO_TOKEN_DEV_ENV_VAR = "MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV"
CLIENT_DISCONNECT_WINERRORS = frozenset({10053, 10054})
CLIENT_DISCONNECT_ERRNOS = frozenset(
    code
    for code in (
        getattr(errno, "EPIPE", None),
        getattr(errno, "ECONNABORTED", None),
        getattr(errno, "ECONNRESET", None),
    )
    if code is not None
)


LOCAL_API_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'none'"
)
LOCAL_API_AUTH_COOKIE_NAME = "MediaPipelineAuth"


class QueryValidationError(ValueError):
    """Raised when a GET query parameter fails route validation."""


def is_client_disconnect_error(exc: BaseException) -> bool:
    if isinstance(exc, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)):
        return True
    if not isinstance(exc, OSError):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror in CLIENT_DISCONNECT_WINERRORS:
        return True
    errno_value = getattr(exc, "errno", None)
    return errno_value in CLIENT_DISCONNECT_ERRNOS


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


def query_json_object(query: dict[str, list[str]], name: str) -> dict[str, Any]:
    raw = query_value(query, name, "")
    if not raw:
        return {}
    try:
        value = loads_strict_json(raw)
    except (TypeError, ValueError) as exc:
        raise QueryValidationError(f"invalid query parameter {name}: {exc}") from exc
    if not isinstance(value, dict):
        raise QueryValidationError(f"query parameter {name} must be a JSON object")
    return value


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
    cookie_token = local_api_auth_cookie_value(str(headers.get("Cookie") or ""))
    if cookie_token:
        candidates.append(cookie_token)
    return any(candidate and secrets.compare_digest(candidate, token) for candidate in candidates)


def local_api_auth_cookie_value(cookie_header: str) -> str:
    if not cookie_header:
        return ""
    try:
        cookies = SimpleCookie()
        cookies.load(cookie_header)
    except Exception:
        return ""
    morsel = cookies.get(LOCAL_API_AUTH_COOKIE_NAME)
    if morsel is None:
        return ""
    try:
        return unquote(str(morsel.value or ""))
    except Exception:
        return str(morsel.value or "")


def local_api_auth_cookie_header(
    *,
    token: str,
    require_token: bool,
    shell_surface: str,
) -> str | None:
    if not require_token:
        return None
    if str(shell_surface or "").casefold() == "tauri":
        return None
    value = quote(str(token or ""), safe="")
    if not value:
        return None
    return f"{LOCAL_API_AUTH_COOKIE_NAME}={value}; HttpOnly; SameSite=Strict; Path=/"


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


def canonical_local_api_origin(
    origin_header: str,
    *,
    bind_host: str,
    port: int,
    shell_surface: str = "webview",
) -> str | None:
    """Return the server-authored origin matching an allowed request origin."""
    supplied_origin = str(origin_header or "").strip()
    if not supplied_origin:
        return None
    for allowed_origin in local_api_allowed_origins(
        bind_host=bind_host,
        port=port,
        shell_surface=shell_surface,
    ):
        if secrets.compare_digest(supplied_origin, allowed_origin):
            return allowed_origin
    return None


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
        return canonical_local_api_origin(
            origin,
            bind_host=bind_host,
            port=port,
            shell_surface=shell_surface,
        ) is not None
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
        and canonical_local_api_origin(
            origin,
            bind_host=bind_host,
            port=port,
            shell_surface=shell_surface,
        ) is not None
    )


def read_json_body(
    handler: http.server.BaseHTTPRequestHandler,
    send_json: JsonSender,
    *,
    max_bytes: int = 1_000_000,
) -> dict[str, Any] | None:
    raw_content_type = str(handler.headers.get("Content-Type") or "").strip()
    content_type = raw_content_type.split(";", 1)[0].strip().casefold()
    if content_type != "application/json":
        send_json({"error": "unsupported media type; use application/json"}, 415)
        return None
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
        payload = loads_strict_json(raw_body, default_text="{}")
    except ValueError as exc:
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
    extra_headers: list[tuple[str, str]] | None = None,
) -> None:
    try:
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Security-Policy", LOCAL_API_CONTENT_SECURITY_POLICY)
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        for name, value in extra_headers or []:
            handler.send_header(name, value.replace("\n", "").replace("\r", ""))
        handler.end_headers()
        handler.wfile.write(body)
    except OSError as exc:
        if is_client_disconnect_error(exc):
            return
        raise


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
    decoded_relative = unquote(relative)
    for candidate in (relative, decoded_relative):
        if not candidate or "\\" in candidate or ".." in candidate.split("/"):
            return None
    asset_root = (static_root / "assets").resolve()
    path = (asset_root / decoded_relative).resolve()
    try:
        path.relative_to(asset_root)
    except ValueError:
        return None
    if not path.exists() or not path.is_file():
        return None
    return path
