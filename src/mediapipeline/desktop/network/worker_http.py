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

    def _register_claim_http_context(self, job_id: str, context: tuple[str, str]) -> None:
        """Bind one claim to the exact coordinator URL/token that issued it."""
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            contexts = getattr(self, "_claim_http_contexts", None)
            if not isinstance(contexts, dict):
                contexts = {}
                self._claim_http_contexts = contexts
            contexts[str(job_id)] = (str(context[0]), str(context[1]))
            return
        with lock:
            contexts = getattr(self, "_claim_http_contexts", None)
            if not isinstance(contexts, dict):
                contexts = {}
                self._claim_http_contexts = contexts
            contexts[str(job_id)] = (str(context[0]), str(context[1]))

    def _claim_http_context(self, job_id: str) -> tuple[str, str] | None:
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            contexts = getattr(self, "_claim_http_contexts", {})
            context = contexts.get(str(job_id)) if isinstance(contexts, dict) else None
        else:
            with lock:
                contexts = getattr(self, "_claim_http_contexts", {})
                context = contexts.get(str(job_id)) if isinstance(contexts, dict) else None
        if not isinstance(context, tuple) or len(context) != 2:
            return None
        return str(context[0]), str(context[1])

    def _forget_claim_http_context(self, job_id: str) -> None:
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            contexts = getattr(self, "_claim_http_contexts", None)
            if isinstance(contexts, dict):
                contexts.pop(str(job_id), None)
            return
        with lock:
            contexts = getattr(self, "_claim_http_contexts", None)
            if isinstance(contexts, dict):
                contexts.pop(str(job_id), None)

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
        response, _context = self._http_get_with_context(path, params)
        return response

    def _http_get_with_context(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], tuple[str, str]]:
        base_url, auth_token = self._runtime_http_context()
        response = http_get_json(
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
        return response, (base_url, auth_token)

    def _http_get_for_claim(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], tuple[str, str]]:
        """Issue a claim request and return the exact routing context used."""
        instance_get = vars(self).get("_http_get")
        if callable(instance_get):
            context = self._runtime_http_context()
            return instance_get(path, params), context
        return self._http_get_with_context(path, params)

    def _http_post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._http_post_with_context(path, data, self._runtime_http_context())

    def _http_post_with_context(
        self,
        path: str,
        data: dict[str, Any],
        context: tuple[str, str],
    ) -> dict[str, Any]:
        base_url, auth_token = context
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

    def _http_post_for_claim(self, job_id: str, path: str, data: dict[str, Any]) -> dict[str, Any]:
        instance_post = vars(self).get("_http_post")
        if callable(instance_post):
            return instance_post(path, data)
        context = self._claim_http_context(job_id)
        if context is None:
            return self._http_post(path, data)
        return self._http_post_with_context(path, data, context)
