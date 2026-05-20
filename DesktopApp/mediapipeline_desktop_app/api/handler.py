from __future__ import annotations

import http.server
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .handler_policy import (
    OPTIONS_RESPONSE_HEADERS,
    not_found_payload,
    route_exception_payload,
    should_record_command_payload,
    unauthorized_payload,
)
from .http_helpers import discard_request_body, read_json_body, send_bytes
from .routes import GET_ROUTE_HANDLERS, POST_ROUTE_HANDLERS


def build_local_api_handler_class(owner: Any) -> type[http.server.BaseHTTPRequestHandler]:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            owner.logger.debug("local-api " + fmt, *args)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            for name, value in OPTIONS_RESPONSE_HEADERS:
                self.send_header(name, value)
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            route = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            if route in {"/", "/index.html"}:
                owner._send_index(self)
                return
            if route.startswith("/assets/"):
                owner._send_static(self, route)
                return
            if route == "/api/health":
                try:
                    self._send_json(owner._health_payload())
                except Exception as exc:
                    owner.logger.exception("local API route failed: %s", route)
                    self._send_json(route_exception_payload(route, exc), status=500)
                return
            if not owner._request_authorized(self.headers, query):
                self._send_json(unauthorized_payload(), status=401)
                return
            try:
                spec = GET_ROUTE_HANDLERS.get(route)
                if spec is None:
                    self._send_json(not_found_payload(route), status=404)
                    return
                handler = getattr(owner, spec.method_name)
                self._send_json(handler(query) if spec.needs_query else handler())
            except Exception as exc:
                owner.logger.exception("local API route failed: %s", route)
                self._send_json(route_exception_payload(route, exc), status=500)

        def do_POST(self) -> None:
            parsed = urlsplit(self.path)
            route = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            if not owner._request_authorized(self.headers, query):
                self._discard_request_body()
                self._send_json(unauthorized_payload(), status=401)
                return
            try:
                spec = POST_ROUTE_HANDLERS.get(route)
                if spec is None:
                    self._send_json(not_found_payload(route), status=404)
                    return
                body = self._read_json_body()
                if body is None:
                    return
                self._send_json(getattr(owner, spec.method_name)(body))
            except Exception as exc:
                owner.logger.exception("local API route failed: %s", route)
                self._send_json(route_exception_payload(route, exc), status=500)

        def _read_json_body(self) -> dict[str, Any] | None:
            return read_json_body(self, lambda payload, status: self._send_json(payload, status=status))

        def _discard_request_body(self) -> None:
            discard_request_body(self)

        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            try:
                body = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
            except (TypeError, ValueError) as exc:
                owner.logger.exception("local API attempted to send a non-strict JSON response.")
                status = 500
                payload = route_exception_payload("local-api response", exc)
                body = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
            if should_record_command_payload(status):
                owner.command_journal.record(payload)
            self._send_bytes(body, status=status, content_type="application/json; charset=utf-8")

        def _send_bytes(self, body: bytes, *, status: int = 200, content_type: str = "application/octet-stream") -> None:
            send_bytes(self, body, status=status, content_type=content_type)

    return _Handler
