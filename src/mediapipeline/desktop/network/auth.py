"""
network.auth
============
Token generation and validation for the coordinator HTTP API.

Designed to be simple and stdlib-only. The coordinator token is a shared
secret used to sign requests with HMAC-SHA256 so the token is not sent on
the LAN for normal worker/coordinator traffic.

For future TLS support, wrap the ``ThreadingHTTPServer`` with an
``ssl.SSLContext`` in ``network/coordinator.py`` — no changes needed here.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from collections.abc import MutableMapping
from dataclasses import dataclass


# Number of random bytes → 64-char hex string.
_TOKEN_BYTES = 32
AUTH_VERSION = "mp-hmac-v1"
AUTH_TIMESTAMP_HEADER = "X-MediaPipeline-Timestamp"
AUTH_NONCE_HEADER = "X-MediaPipeline-Nonce"
AUTH_SIGNATURE_HEADER = "X-MediaPipeline-Signature"
AUTH_VERSION_HEADER = "X-MediaPipeline-Auth-Version"
AUTH_MAX_SKEW_SECONDS = 300
LEGACY_BEARER_ENV_VAR = "MEDIAPIPELINE_ALLOW_LEGACY_COORDINATOR_BEARER"
AUTH_FAILURE_AUTH_FAILED = "auth_failed"
AUTH_FAILURE_CLOCK_SKEW = "clock_skew"


@dataclass(frozen=True)
class AuthValidationResult:
    ok: bool
    reason: str = ""


def generate_token() -> str:
    """Return a cryptographically random 64-character hex token."""
    return secrets.token_hex(_TOKEN_BYTES)


def validate_header(headers: dict, expected_token: str) -> bool:
    """Return True if the Authorization header contains the expected token.

    Uses ``hmac.compare_digest`` for constant-time comparison to prevent
    timing-based token enumeration.

    Parameters
    ----------
    headers:
        Mapping of HTTP header names to values.  Lookups are case-
        insensitive across the canonical, lowercase, and uppercase
        spellings to handle clients that emit non-titlecased headers.
    expected_token:
        The token that was generated and stored in coordinator config.

        N1 fix — an empty/blank ``expected_token`` is now treated as a
        misconfiguration and returns ``False`` instead of admitting all
        callers.  ``CoordinatorDispatcher`` always seeds a token on
        first start (auto-generated when the user hasn't provided one),
        so reaching this branch means something has cleared it at
        runtime — almost certainly an accidental UI blank-and-save —
        and the safe default is to refuse all requests until the
        operator restores a real token.
    """
    if not expected_token or not expected_token.strip():
        return False

    # Case-insensitive lookup. BaseHTTPRequestHandler.headers is an
    # email.message.Message which is case-insensitive natively, but
    # callers pass dict(self.headers) which preserves whatever casing
    # arrived on the wire. Try common spellings.
    auth_header: str = ""
    for key in ("Authorization", "authorization", "AUTHORIZATION"):
        value = headers.get(key)
        if value:
            auth_header = str(value)
            break
    if not auth_header:
        # Last resort: walk the dict for any case-folded match.
        for k, v in headers.items():
            if isinstance(k, str) and k.lower() == "authorization":
                auth_header = str(v or "")
                break
    if not auth_header.startswith("Bearer "):
        return False

    provided = auth_header[len("Bearer "):]
    # Both sides must be str for compare_digest.
    try:
        return hmac.compare_digest(provided.strip(), expected_token.strip())
    except (TypeError, ValueError):
        return False


def make_auth_header(token: str) -> dict[str, str]:
    """Return an ``Authorization`` header dict for use in worker requests."""
    return {"Authorization": f"Bearer {token}"}


def _header_value(headers: dict, name: str) -> str:
    value = headers.get(name)
    if value is not None:
        return str(value)
    folded = name.casefold()
    for key, item in headers.items():
        if str(key).casefold() == folded:
            return str(item)
    return ""


def body_sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


def canonical_request(method: str, path_with_query: str, timestamp: str, nonce: str, body: bytes) -> str:
    return "\n".join(
        [
            str(method or "").upper(),
            str(path_with_query or ""),
            str(timestamp or ""),
            str(nonce or ""),
            body_sha256_hex(body),
        ]
    )


def sign_request(
    method: str,
    path_with_query: str,
    body: bytes,
    token: str,
    *,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    timestamp_text = str(int(time.time() if timestamp is None else timestamp))
    nonce_text = str(nonce or secrets.token_urlsafe(24))
    secret = str(token or "").strip()
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical_request(method, path_with_query, timestamp_text, nonce_text, body).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        AUTH_VERSION_HEADER: AUTH_VERSION,
        AUTH_TIMESTAMP_HEADER: timestamp_text,
        AUTH_NONCE_HEADER: nonce_text,
        AUTH_SIGNATURE_HEADER: signature,
    }


def validate_signed_request(
    headers: dict,
    expected_token: str,
    *,
    method: str,
    path_with_query: str,
    body: bytes,
    nonce_cache: MutableMapping[str, float] | None = None,
    now: float | None = None,
    max_skew_seconds: int = AUTH_MAX_SKEW_SECONDS,
) -> bool:
    return validate_signed_request_result(
        headers,
        expected_token,
        method=method,
        path_with_query=path_with_query,
        body=body,
        nonce_cache=nonce_cache,
        now=now,
        max_skew_seconds=max_skew_seconds,
    ).ok


def validate_signed_request_result(
    headers: dict,
    expected_token: str,
    *,
    method: str,
    path_with_query: str,
    body: bytes,
    nonce_cache: MutableMapping[str, float] | None = None,
    now: float | None = None,
    max_skew_seconds: int = AUTH_MAX_SKEW_SECONDS,
) -> AuthValidationResult:
    secret = str(expected_token or "").strip()
    if not secret:
        return AuthValidationResult(False, "missing_token")
    if _header_value(headers, AUTH_VERSION_HEADER) != AUTH_VERSION:
        return AuthValidationResult(False, AUTH_FAILURE_AUTH_FAILED)
    timestamp_text = _header_value(headers, AUTH_TIMESTAMP_HEADER).strip()
    nonce = _header_value(headers, AUTH_NONCE_HEADER).strip()
    provided_signature = _header_value(headers, AUTH_SIGNATURE_HEADER).strip()
    if not timestamp_text or not nonce or not provided_signature:
        return AuthValidationResult(False, AUTH_FAILURE_AUTH_FAILED)
    try:
        timestamp = int(timestamp_text)
    except ValueError:
        return AuthValidationResult(False, AUTH_FAILURE_AUTH_FAILED)
    current = float(time.time() if now is None else now)
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        canonical_request(method, path_with_query, timestamp_text, nonce, body).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    try:
        if not hmac.compare_digest(provided_signature, expected_signature):
            return AuthValidationResult(False, AUTH_FAILURE_AUTH_FAILED)
    except (TypeError, ValueError):
        return AuthValidationResult(False, AUTH_FAILURE_AUTH_FAILED)
    if abs(current - float(timestamp)) > int(max_skew_seconds):
        return AuthValidationResult(False, AUTH_FAILURE_CLOCK_SKEW)
    if nonce_cache is not None:
        expired = [key for key, expires_at in nonce_cache.items() if float(expires_at) < current]
        for key in expired:
            nonce_cache.pop(key, None)
        if nonce in nonce_cache:
            return AuthValidationResult(False, AUTH_FAILURE_AUTH_FAILED)
        nonce_cache[nonce] = current + int(max_skew_seconds)
    return AuthValidationResult(True, "")


def validate_request_auth(
    headers: dict,
    expected_token: str,
    *,
    method: str,
    path_with_query: str,
    body: bytes,
    nonce_cache: MutableMapping[str, float] | None = None,
) -> bool:
    return validate_request_auth_result(
        headers,
        expected_token,
        method=method,
        path_with_query=path_with_query,
        body=body,
        nonce_cache=nonce_cache,
    ).ok


def validate_request_auth_result(
    headers: dict,
    expected_token: str,
    *,
    method: str,
    path_with_query: str,
    body: bytes,
    nonce_cache: MutableMapping[str, float] | None = None,
) -> AuthValidationResult:
    signed = validate_signed_request_result(
        headers,
        expected_token,
        method=method,
        path_with_query=path_with_query,
        body=body,
        nonce_cache=nonce_cache,
    )
    if signed.ok:
        return signed
    legacy_enabled = str(os.environ.get(LEGACY_BEARER_ENV_VAR, "") or "").strip().casefold() in {"1", "true", "yes", "on"}
    if legacy_enabled and validate_header(headers, expected_token):
        return AuthValidationResult(True, "legacy_bearer")
    return signed if signed.reason == AUTH_FAILURE_CLOCK_SKEW else AuthValidationResult(False, AUTH_FAILURE_AUTH_FAILED)
