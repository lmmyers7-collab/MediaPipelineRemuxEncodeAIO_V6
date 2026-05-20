"""
network.auth
============
Token generation and validation for the coordinator HTTP API.

Designed to be simple and stdlib-only.  The token is a shared secret
transmitted as a bearer token in the ``Authorization`` header.  This is
sufficient for LAN-only use where TLS is not required.

For future TLS support, wrap the ``ThreadingHTTPServer`` with an
``ssl.SSLContext`` in ``network/coordinator.py`` — no changes needed here.
"""
from __future__ import annotations

import hmac
import secrets


# Number of random bytes → 64-char hex string.
_TOKEN_BYTES = 32


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
