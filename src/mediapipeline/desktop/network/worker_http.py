"""HTTP helpers for :class:`WorkerDispatcher`."""
from __future__ import annotations

import logging
from typing import Any

from .auth import sign_request as _sign_request_headers
from .http_json import HTTP_TIMEOUT as _HTTP_TIMEOUT
from .http_json import http_get_json, http_post_json

_log = logging.getLogger("mediapipeline.desktop.network.worker")


class WorkerHttpMixin:
    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }

    def _runtime_http_context(self) -> tuple[str, str]:
        snapshot = getattr(self, "_runtime_settings_snapshot", None)
        if callable(snapshot):
            base_url, auth_token, _mappings = snapshot()
            return base_url, auth_token
        return str(getattr(self, "_base_url", "") or ""), str(getattr(self, "_auth_token", "") or "")

    def _sign_request_with_token(
        self,
        method: str,
        path_with_query: str,
        body: bytes,
        auth_token: str,
    ) -> dict[str, str]:
        if not auth_token:
            return {}
        return _sign_request_headers(method, path_with_query, body, auth_token)

    def _sign_request(self, method: str, path_with_query: str, body: bytes) -> dict[str, str]:
        _base_url, auth_token = self._runtime_http_context()
        return self._sign_request_with_token(method, path_with_query, body, auth_token)

    def _http_get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        base_url, auth_token = self._runtime_http_context()
        return http_get_json(
            base_url,
            path,
            headers=self._headers(),
            params=params,
            sign_request=lambda method, path_with_query, body: self._sign_request_with_token(
                method,
                path_with_query,
                body,
                auth_token,
            ),
            timeout_seconds=_HTTP_TIMEOUT,
        )

    def _http_post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        base_url, auth_token = self._runtime_http_context()
        return http_post_json(
            base_url,
            path,
            data,
            headers=self._headers(),
            sign_request=lambda method, path_with_query, body: self._sign_request_with_token(
                method,
                path_with_query,
                body,
                auth_token,
            ),
            timeout_seconds=_HTTP_TIMEOUT,
        )
