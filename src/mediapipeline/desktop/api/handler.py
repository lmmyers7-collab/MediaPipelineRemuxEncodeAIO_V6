from __future__ import annotations

import http.server
import json
import uuid
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .handler_policy import (
    cors_response_headers,
    not_found_payload,
    route_exception_journal_payload,
    options_response_headers,
    route_exception_payload,
    route_exception_status,
    route_validation_error_payload,
    route_validation_journal_payload,
    requires_strict_durable_command_journal,
    should_record_command_payload,
    should_record_route_exception_journal,
    should_record_validation_failure_journal,
    unauthorized_payload,
)
from .http_helpers import QueryValidationError, discard_request_body, read_json_body, send_bytes
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
                    self._send_json(payload, status=route_exception_status(exc))
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
            except QueryValidationError as exc:
                self._send_json(route_validation_error_payload(route, exc), status=400)
            except Exception as exc:
                payload = route_exception_payload(route, exc)
                owner.logger.exception("local API route failed: %s error_id=%s", route, payload.get("error_id"))
                self._send_json(payload, status=route_exception_status(exc))

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
            body: dict[str, Any] | None = None
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
                        if should_record_validation_failure_journal(route):
                            try:
                                owner._record_command_journal(route_validation_journal_payload(route, exc), request=body)
                            except Exception as journal_exc:
                                owner.logger.warning("Could not record local API validation failure for %s: %s", route, journal_exc)
                        self._send_json(route_validation_error_payload(route, exc), status=400)
                        return
                strict_evidence = requires_strict_durable_command_journal(route)
                command_id = uuid.uuid4().hex if strict_evidence else ""
                if strict_evidence:
                    try:
                        owner._record_command_journal(
                            _strict_command_evidence_payload(
                                route,
                                command_id,
                                phase="accepted",
                                ok=True,
                                message="Critical command accepted by the backend before mutation.",
                            ),
                            request=body,
                            strict=True,
                        )
                    except Exception as journal_exc:
                        self._send_json(
                            _strict_command_evidence_payload(
                                route,
                                command_id,
                                phase="rejected",
                                ok=False,
                                message="Critical command was rejected before mutation because durable command evidence is unavailable.",
                                error=str(journal_exc),
                            ),
                            status=503,
                        )
                        return
                    body = {**body, "_command_id": command_id}
                result = getattr(owner, spec.method_name)(body)
                if strict_evidence:
                    result = _with_strict_command_evidence(result, command_id)
                    try:
                        owner._record_command_journal(result, request=body, strict=True)
                    except Exception as journal_exc:
                        marker = getattr(owner, "_mark_command_evidence_indeterminate", None)
                        if callable(marker):
                            marker(command_id=command_id, route=route, reason=str(journal_exc))
                        self._send_json(
                            _strict_command_evidence_payload(
                                route,
                                command_id,
                                phase="indeterminate",
                                ok=False,
                                message="The operation may have run, but its terminal evidence could not be persisted. Do not retry or close; reconcile backend state.",
                                error=str(journal_exc),
                            ),
                            status=503,
                        )
                        return
                self._send_json(result, journal_request=body)
            except Exception as exc:
                payload = route_exception_payload(route, exc)
                owner.logger.exception("local API route failed: %s error_id=%s", route, payload.get("error_id"))
                if should_record_route_exception_journal(route):
                    try:
                        owner._record_command_journal(route_exception_journal_payload(route, payload), request=body)
                    except Exception as journal_exc:
                        owner.logger.warning("Could not record local API route exception for %s: %s", route, journal_exc)
                self._send_json(payload, status=route_exception_status(exc))

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
            return "http://127.0.0.1"

        def _send_json(self, payload: dict[str, Any], status: int = 200, journal_request: dict[str, Any] | None = None) -> None:
            try:
                body = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
            except (TypeError, ValueError) as exc:
                owner.logger.exception("local API attempted to send a non-strict JSON response.")
                status = 500
                payload = route_exception_payload("local-api response", exc)
                body = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
            data = payload.get("data") if isinstance(payload, dict) else None
            suppress_journal = isinstance(data, dict) and (
                data.get("suppress_command_journal") is True
                or data.get("strict_command_journal_recorded") is True
            )
            if should_record_command_payload(status) and not suppress_journal:
                owner._record_command_journal(payload, request=journal_request)
            self._send_bytes(body, status=status, content_type="application/json; charset=utf-8")

        def _send_bytes(
            self,
            body: bytes,
            *,
            status: int = 200,
            content_type: str = "application/octet-stream",
            extra_headers: list[tuple[str, str]] | None = None,
        ) -> None:
            response_headers = [
                *cors_response_headers(self._cors_response_origin()),
                *(extra_headers or []),
            ]
            send_bytes(self, body, status=status, content_type=content_type, extra_headers=response_headers)

    return _Handler


def _strict_command_evidence_payload(
    route: str,
    command_id: str,
    *,
    phase: str,
    ok: bool,
    message: str,
    error: str = "",
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "command_id": command_id,
        "route": route,
        "evidence_phase": phase,
        "journal_durability": "strict",
        "suppress_command_journal": True,
    }
    if error:
        data["journal_error"] = error
    return {
        "schema_version": "desktop_command_result.v1",
        "command": route.removeprefix("/api/").replace("/", "."),
        "ok": ok,
        "severity": "info" if ok else "error",
        "message": message,
        "data": data,
    }


def _with_strict_command_evidence(payload: dict[str, Any], command_id: str) -> dict[str, Any]:
    result = dict(payload)
    data = dict(result.get("data") or {})
    data.update(
        {
            "command_id": command_id,
            "evidence_phase": "completed" if bool(result.get("ok")) else "rejected_or_failed",
            "journal_durability": "strict",
            "strict_command_journal_recorded": True,
        }
    )
    result["data"] = data
    return result
