"""Authentication helpers for :class:`CoordinatorDispatcher`."""
from __future__ import annotations

import logging

from ..config_keys import KEY_COORDINATOR_AUTH_TOKEN
from .auth import AuthValidationResult, generate_token, validate_request_auth_result

_log = logging.getLogger("mediapipeline.desktop.network.coordinator")

COORDINATOR_AUTH_TOKEN_MIN_LENGTH = 16


def validate_coordinator_auth_token(token: str, *, label: str = "Coordinator auth token") -> str:
    """Return a nonblank, strong coordinator token or raise a redacted error."""
    normalized = str(token or "").strip()
    if not normalized:
        raise ValueError(
            f"{label} cannot be empty. Generate a new token via "
            "secrets.token_hex(32) instead of clearing it."
        )
    if len(normalized) < COORDINATOR_AUTH_TOKEN_MIN_LENGTH:
        raise ValueError(
            f"{label} is too short (minimum {COORDINATOR_AUTH_TOKEN_MIN_LENGTH} characters). "
            "Use a cryptographically random token."
        )
    return normalized


class CoordinatorAuthMixin:
    def _load_or_generate_token(self) -> str:
        # 1. User-configured token in PSD1 config takes precedence.
        token = str(self._config().get(KEY_COORDINATOR_AUTH_TOKEN, "") or "").strip()
        if token:
            return validate_coordinator_auth_token(token, label="Configured coordinator auth token")

        # 2. Auto-generated token persisted in app state.
        try:
            state = self._app.service.load_app_state()
        except Exception:
            _log.exception("Could not read coordinator token from app state.")
        else:
            token = str(state.get("coordinator_auth_token", "") or "").strip()
            if token:
                return validate_coordinator_auth_token(token, label="Persisted coordinator auth token")

        # 3. Generate a fresh token and persist it.
        token = generate_token()
        try:
            self._app.service.save_app_state({"coordinator_auth_token": token})
        except Exception:
            _log.exception("Could not persist new coordinator token to app state.")
            _log.warning(
                "Generated coordinator auth token is active for this run only; "
                "persistence failed, so workers may need a new token after restart."
            )
        else:
            _log.info("Generated new coordinator auth token (stored in app state).")
        return token

    def _validate_request_auth(
        self,
        headers: dict,
        *,
        method: str,
        path_with_query: str,
        body: bytes,
    ) -> bool:
        return self._request_auth_result(
            headers,
            method=method,
            path_with_query=path_with_query,
            body=body,
        ).ok

    def _request_auth_result(
        self,
        headers: dict,
        *,
        method: str,
        path_with_query: str,
        body: bytes,
    ) -> AuthValidationResult:
        with self._auth_nonce_lock:
            return validate_request_auth_result(
                headers,
                self._auth_token,
                method=method,
                path_with_query=path_with_query,
                body=body,
                nonce_cache=self._auth_nonce_cache,
            )

    def get_auth_token(self) -> str:
        """Return the active bearer token (for settings display)."""
        return self._auth_token

    def update_auth_token(self, new_token: str) -> None:
        """Hot-swap the bearer token without restarting the HTTP server.

        Takes effect immediately for all subsequent requests — no reload or
        restart needed.  Called from the Network tab when the user regenerates
        the coordinator token.

        N7 — refuses an empty / whitespace-only token (which would have
        opened the API to anonymous access on the LAN) and persists the
        new token to app_state so a coordinator restart preserves it.
        Raises ``ValueError`` when the supplied token is blank.
        """
        new_token = validate_coordinator_auth_token(new_token)
        self._auth_token = new_token
        # Persist so the next start picks up the rotated token instead of
        # silently reverting to the old auto-generated one in app_state.
        try:
            self._app.service.save_app_state({"coordinator_auth_token": new_token})
        except Exception:
            _log.exception("Could not persist rotated coordinator token to app state.")
            _log.warning(
                "Coordinator auth token updated live, but persistence failed; "
                "workers may need a new token after coordinator restart."
            )
        else:
            _log.info("Coordinator auth token updated and persisted (hot-swap, no restart required).")
        self._safe_log_cluster_event(
            "auth-token-rotated",
            level="INFO",
            event="auth_token_rotated",
            message="Coordinator auth token rotated via hot-swap.",
        )
