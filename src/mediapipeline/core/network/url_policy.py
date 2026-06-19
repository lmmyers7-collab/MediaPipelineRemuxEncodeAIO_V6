"""Network URL validation and secret redaction helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_URL_RE = re.compile(r"\bhttps?://[^\s<>'\"]+", re.IGNORECASE)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_]*(?:token|secret|password|authorization|auth|apikey|api_key)[A-Za-z0-9_]*)=([^&#\s;]+)"
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\b(Authorization:\s*Bearer\s+)([^\s;]+)")


def redact_url(value: Any) -> str:
    """Return a display-safe URL with userinfo, query, and fragment removed."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except Exception:
        return "present_redacted"
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port:
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        host = f"{host}:{port}"
    if host:
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    safe_netloc = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, safe_netloc, parsed.path, "", ""))


def redact_network_secret_text(value: Any) -> str:
    """Redact URL secrets and token-like assignment values from free text."""
    text = str(value or "")
    if not text:
        return ""

    def _redact_match(match: re.Match[str]) -> str:
        return redact_url(match.group(0))

    redacted = _URL_RE.sub(_redact_match, text)
    redacted = _BEARER_TOKEN_RE.sub(lambda m: f"{m.group(1)}<redacted>", redacted)
    return _SENSITIVE_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}=<redacted>", redacted)


def validate_coordinator_url(raw: str) -> str:
    """Validate and normalize a worker coordinator base URL."""
    url = (raw or "").strip().rstrip("/")
    if not url:
        raise ValueError(
            "WorkerCoordinatorUrl is empty. Enter the coordinator base URL "
            "(for example http://192.168.1.10:7830) in Settings > Network."
        )
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            "WorkerCoordinatorUrl must start with http:// or https:// "
            f"(got {parsed.scheme or '(no scheme)'})."
        )
    if not parsed.hostname:
        raise ValueError("WorkerCoordinatorUrl must include a coordinator host.")
    if parsed.hostname in ("0.0.0.0", "::"):
        raise ValueError(
            "WorkerCoordinatorUrl must use the coordinator machine name or LAN IP, "
            "not a bind-all listen address such as 0.0.0.0 or ::."
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("WorkerCoordinatorUrl port must be in 1..65535.") from exc
    if port is None:
        raise ValueError(
            "WorkerCoordinatorUrl must include the coordinator TCP port "
            "(for example http://192.168.1.10:7830)."
        )
    if port < 1 or port > 65535:
        raise ValueError("WorkerCoordinatorUrl port must be in 1..65535.")
    if parsed.path and parsed.path not in ("", "/"):
        raise ValueError("WorkerCoordinatorUrl must be the coordinator base URL only, without a path component.")
    if parsed.query or parsed.fragment:
        raise ValueError("WorkerCoordinatorUrl must not include a query string or fragment.")
    if parsed.username or parsed.password:
        raise ValueError(
            "WorkerCoordinatorUrl must not embed userinfo; use WorkerAuthToken for the shared token."
        )
    return url


__all__ = [
    "redact_network_secret_text",
    "redact_url",
    "validate_coordinator_url",
]
