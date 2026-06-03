"""HTTP helpers for :class:`WorkerDispatcher`."""
from __future__ import annotations

import logging
from typing import Any

from .auth import sign_request as _sign_request_headers
from .http_json import HTTP_TIMEOUT as _HTTP_TIMEOUT
from .http_json import http_get_json, http_post_json

_log = logging.getLogger("mediapipeline_desktop_app.network.worker")


class WorkerHttpMixin:
    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }

    def _sign_request(self, method: str, path_with_query: str, body: bytes) -> dict[str, str]:
        if not self._auth_token:
            return {}
        return _sign_request_headers(method, path_with_query, body, self._auth_token)

    def _http_get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        return http_get_json(
            self._base_url,
            path,
            headers=self._headers(),
            params=params,
            sign_request=self._sign_request,
            timeout_seconds=_HTTP_TIMEOUT,
        )

    def _http_post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        return http_post_json(
            self._base_url,
            path,
            data,
            headers=self._headers(),
            sign_request=self._sign_request,
            timeout_seconds=_HTTP_TIMEOUT,
        )
