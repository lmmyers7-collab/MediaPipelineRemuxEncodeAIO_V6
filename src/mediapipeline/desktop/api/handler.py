from __future__ import annotations

import http.server
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .handler_policy import (
    not_found_payload,
    options_response_headers,
    route_exception_payload,
    route_validation_error_payload,
    route_validation_journal_payload,
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
            if not self._request_host_authorized():
                self._send_json({"error": "invalid host"}, status=400)
                return
            if not self._request_origin_authorized():
                self._send_json({"error": "invalid origin"}, status=403)
                return
            self.send_response(204)
            for name, value in options_response_headers(self._cors_response_origin()):
                self.send_header(name, value)
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            route = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            if not self._request_host_authorized():
                self._send_json({"error": "invalid host"}, status=400)
                return
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
                    payload = route_exception_payload(route, exc)
                    owner.logger.exception("local API route failed: %s error_id=%s", route, payload.get("error_id"))
                    self._send_json(payload, status=500)
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
                payload = route_exception_payload(route, exc)
                owner.logger.exception("local API route failed: %s error_id=%s", route, payload.get("error_id"))
                self._send_json(payload, status=500)

        def do_POST(self) -> None:
            parsed = urlsplit(self.path)
            route = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            if not self._request_host_authorized():
                self._discard_request_body()
                self._send_json({"error": "invalid host"}, status=400)
                return
            if not self._request_origin_authorized():
                self._discard_request_body()
                self._send_json({"error": "invalid origin"}, status=403)
                return
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
                validate_payload = getattr(owner, "_validate_api_payload", None)
                if callable(validate_payload):
                    try:
                        body = validate_payload(route, body)
                    except Exception as exc:
                        try:
                            owner._record_command_journal(route_validation_journal_payload(route, exc), request=body)
                        except Exception as journal_exc:
                            owner.logger.warning("Could not record local API validation failure for %s: %s", route, journal_exc)
                        self._send_json(route_validation_error_payload(route, exc), status=400)
                        return
                self._send_json(getattr(owner, spec.method_name)(body), journal_request=body)
            except Exception as exc:
                payload = route_exception_payload(route, exc)
                owner.logger.exception("local API route failed: %s error_id=%s", route, payload.get("error_id"))
                self._send_json(payload, status=500)

        def _read_json_body(self) -> dict[str, Any] | None:
            return read_json_body(self, lambda payload, status: self._send_json(payload, status=status))

        def _discard_request_body(self) -> None:
            discard_request_body(self)

        def _request_host_authorized(self) -> bool:
            checker = getattr(owner, "_host_header_authorized", None)
            return bool(checker(self.headers)) if callable(checker) else True

        def _request_origin_authorized(self) -> bool:
            checker = getattr(owner, "_origin_header_authorized", None)
            return bool(checker(self.headers)) if callable(checker) else True

        def _cors_response_origin(self) -> str:
            resolver = getattr(owner, "_cors_response_origin", None)
            if callable(resolver):
                return str(resolver(self.headers))
            return str(self.headers.get("Origin") or "http://127.0.0.1")

        def _send_json(self, payload: dict[str, Any], status: int = 200, journal_request: dict[str, Any] | None = None) -> None:
            try:
                body = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
            except (TypeError, ValueError) as exc:
                owner.logger.exception("local API attempted to send a non-strict JSON response.")
                status = 500
                payload = route_exception_payload("local-api response", exc)
                body = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
            if should_record_command_payload(status):
                owner._record_command_journal(payload, request=journal_request)
            self._send_bytes(body, status=status, content_type="application/json; charset=utf-8")

        def _send_bytes(self, body: bytes, *, status: int = 200, content_type: str = "application/octet-stream") -> None:
            send_bytes(self, body, status=status, content_type=content_type)

    return _Handler
