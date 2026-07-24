from __future__ import annotations

import http.server
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .handler_policy import (
    OperatorRouteError,
    cors_response_headers,
    not_found_payload,
    route_exception_journal_payload,
    options_response_headers,
    route_exception_payload,
    route_exception_status,
    route_validation_error_payload,
    route_validation_journal_payload,
    STRICT_COMMAND_ID_HEADER,
    requires_strict_durable_command_journal,
    should_record_command_payload,
    should_record_route_exception_journal,
    should_record_validation_failure_journal,
    strict_command_fingerprint,
    unauthorized_payload,
    validated_strict_command_id,
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
                command_id = ""
                request_fingerprint = ""
                if strict_evidence:
                    try:
                        command_id = validated_strict_command_id(self.headers.get(STRICT_COMMAND_ID_HEADER))
                        request_fingerprint = strict_command_fingerprint(route, body)
                    except (TypeError, ValueError) as identity_exc:
                        self._send_json(
                            _strict_command_identity_error_payload(route, str(identity_exc)),
                            status=400,
                        )
                        return
                    try:
                        reservation = owner._reserve_strict_command(
                            command_id=command_id,
                            route=route,
                            request_fingerprint=request_fingerprint,
                            request=body,
                            accepted_payload=_strict_command_evidence_payload(
                                route,
                                command_id,
                                phase="accepted",
                                ok=True,
                                message="Critical command accepted by the backend before mutation.",
                            ),
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
                    reservation_action = str(reservation.get("action") or "")
                    if reservation_action == "replay":
                        replay_payload = reservation.get("response_payload")
                        if not isinstance(replay_payload, dict):
                            self._send_json(
                                _strict_command_state_payload(
                                    route,
                                    command_id,
                                    code="command_outcome_indeterminate",
                                    message="The prior command outcome cannot be replayed safely. Reconcile backend evidence before retrying.",
                                    phase="indeterminate",
                                    retry_with_same_command_id=True,
                                ),
                                status=503,
                            )
                            return
                        self._send_json(
                            _replayed_strict_command_payload(replay_payload, command_id),
                            status=int(reservation.get("response_status") or 200),
                        )
                        return
                    if reservation_action != "execute":
                        code = str(reservation.get("code") or "command_outcome_indeterminate")
                        is_conflict = code == "command_id_payload_conflict"
                        is_indeterminate = code == "command_outcome_indeterminate"
                        self._send_json(
                            _strict_command_state_payload(
                                route,
                                command_id,
                                code=code,
                                message=(
                                    "This command ID is already reserved for a different route or payload. Submit a new intent with a new command ID."
                                    if is_conflict
                                    else "The matching command is still active or its outcome is unresolved. Do not submit a new command; reconcile or retry with the same command ID."
                                ),
                                phase="indeterminate" if is_indeterminate else "accepted",
                                retry_with_same_command_id=not is_conflict,
                            ),
                            status=503 if is_indeterminate else 409,
                        )
                        return
                    body = {**body, "_command_id": command_id}
                try:
                    result = getattr(owner, spec.method_name)(body)
                except Exception as dispatch_exc:
                    if not strict_evidence:
                        raise
                    route_payload = route_exception_payload(route, dispatch_exc)
                    owner.logger.exception(
                        "local API strict command dispatch failed: %s error_id=%s",
                        route,
                        route_payload.get("error_id"),
                    )
                    proven_pre_mutation = (
                        isinstance(dispatch_exc, OperatorRouteError)
                        and dispatch_exc.mutation_performed is False
                    )
                    response_status = route_exception_status(dispatch_exc) if proven_pre_mutation else 503
                    terminal_payload = _strict_dispatch_exception_payload(
                        route,
                        command_id,
                        route_payload,
                        proven_pre_mutation=proven_pre_mutation,
                    )
                    try:
                        owner._complete_strict_command(
                            command_id=command_id,
                            route=route,
                            request_fingerprint=request_fingerprint,
                            response_payload=terminal_payload,
                            response_status=response_status,
                            request=body,
                        )
                    except Exception as journal_exc:
                        marker_proof = _mark_indeterminate_evidence(
                            owner,
                            command_id=command_id,
                            route=route,
                            reason=str(journal_exc),
                        )
                        self._send_json(
                            _strict_terminal_persistence_failure_payload(
                                route,
                                command_id,
                                error_id=str(route_payload.get("error_id") or ""),
                                marker_proof=marker_proof,
                            ),
                            status=503,
                        )
                        return
                    self._send_json(terminal_payload, status=response_status)
                    return
                if strict_evidence:
                    result = _with_strict_command_evidence(result, command_id)
                    try:
                        owner._complete_strict_command(
                            command_id=command_id,
                            route=route,
                            request_fingerprint=request_fingerprint,
                            response_payload=result,
                            response_status=200,
                            request=body,
                        )
                    except Exception as journal_exc:
                        marker_proof = _mark_indeterminate_evidence(
                            owner,
                            command_id=command_id,
                            route=route,
                            reason=str(journal_exc),
                        )
                        self._send_json(
                            _strict_terminal_persistence_failure_payload(
                                route,
                                command_id,
                                marker_proof=marker_proof,
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
            return str(self.headers.get("Origin") or "http://127.0.0.1")

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
    result = {
        "schema_version": "desktop_command_result.v1",
        "command": route.removeprefix("/api/").replace("/", "."),
        "ok": ok,
        "severity": "info" if ok else "error",
        "message": message,
        "data": data,
    }
    if phase == "rejected" and error:
        result["code"] = "command_journal_unavailable"
    elif phase == "indeterminate":
        result["code"] = "command_outcome_indeterminate"
    return result


def _strict_command_identity_error_payload(route: str, error: str) -> dict[str, Any]:
    code = "command_id_required" if " is required " in f" {error} " else "command_id_invalid"
    return {
        "schema_version": "desktop_command_result.v1",
        "command": route.removeprefix("/api/").replace("/", "."),
        "ok": False,
        "severity": "error",
        "message": error,
        "code": code,
        "retryable": False,
        "data": {
            "route": route,
            "evidence_phase": "rejected",
            "mutation_performed": False,
            "suppress_command_journal": True,
        },
    }


def _strict_dispatch_exception_payload(
    route: str,
    command_id: str,
    route_payload: dict[str, Any],
    *,
    proven_pre_mutation: bool,
) -> dict[str, Any]:
    error_id = str(route_payload.get("error_id") or "")
    if proven_pre_mutation:
        code = str(route_payload.get("code") or "command_failed_before_mutation")
        message = str(route_payload.get("error") or "The command was rejected before mutation.")
        phase = "failed"
        mutation_performed: bool | None = False
        current_state_unverified = False
        retry_with_same_command_id = False
    else:
        code = "command_outcome_indeterminate"
        message = (
            "The command raised after durable acceptance, so its outcome is unknown. "
            "Do not submit a new command; reconcile backend state or retry with the same command ID."
        )
        phase = "indeterminate"
        mutation_performed = None
        current_state_unverified = True
        retry_with_same_command_id = True
    return {
        "schema_version": "desktop_command_result.v1",
        "command": route.removeprefix("/api/").replace("/", "."),
        "ok": False,
        "severity": "error",
        "message": message,
        "code": code,
        "retryable": False,
        "retry_with_same_command_id": retry_with_same_command_id,
        "data": {
            "command_id": command_id,
            "route": route,
            "error_id": error_id,
            "evidence_phase": phase,
            "mutation_performed": mutation_performed,
            "current_state_unverified": current_state_unverified,
            "journal_durability": "strict",
            "strict_command_journal_recorded": True,
            "suppress_command_journal": True,
        },
    }


def _mark_indeterminate_evidence(
    owner: Any,
    *,
    command_id: str,
    route: str,
    reason: str,
) -> dict[str, Any]:
    marker = getattr(owner, "_mark_command_evidence_indeterminate", None)
    if not callable(marker):
        return {"persisted": False, "status": "marker_unavailable"}
    try:
        proof = marker(command_id=command_id, route=route, reason=reason)
    except Exception as exc:
        owner.logger.exception("Could not persist critical command indeterminate marker: %s", exc)
        return {"persisted": False, "status": "marker_failed"}
    if not isinstance(proof, dict) or proof.get("persisted") is not True:
        return {"persisted": False, "status": "marker_unverified"}
    return {"persisted": True, "status": "marker_persisted"}


def _strict_terminal_persistence_failure_payload(
    route: str,
    command_id: str,
    *,
    marker_proof: dict[str, Any],
    error_id: str = "",
) -> dict[str, Any]:
    marker_persisted = marker_proof.get("persisted") is True
    phase = "indeterminate" if marker_persisted else "unresolved"
    code = "command_outcome_indeterminate" if marker_persisted else "command_evidence_unresolved"
    message = (
        "The operation may have run and its terminal journal evidence could not be persisted. "
        "A durable lifecycle marker blocks unsafe recovery; reconcile backend state before retrying or closing."
        if marker_persisted
        else "The operation may have run, but neither terminal journal evidence nor a fallback lifecycle marker could be proven. The durable accepted reservation remains unresolved; do not retry or close."
    )
    return {
        "schema_version": "desktop_command_result.v1",
        "command": route.removeprefix("/api/").replace("/", "."),
        "ok": False,
        "severity": "error",
        "message": message,
        "code": code,
        "retryable": False,
        "retry_with_same_command_id": True,
        "data": {
            "command_id": command_id,
            "route": route,
            "error_id": error_id,
            "evidence_phase": phase,
            "mutation_performed": None,
            "current_state_unverified": True,
            "accepted_reservation_durable": True,
            "lifecycle_marker_persisted": marker_persisted,
            "journal_durability": "fallback_marker" if marker_persisted else "unresolved",
            "suppress_command_journal": True,
        },
    }


def _strict_command_state_payload(
    route: str,
    command_id: str,
    *,
    code: str,
    message: str,
    phase: str,
    retry_with_same_command_id: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "desktop_command_result.v1",
        "command": route.removeprefix("/api/").replace("/", "."),
        "ok": False,
        "severity": "warning" if code == "command_in_progress" else "error",
        "message": message,
        "code": code,
        "retryable": False,
        "retry_with_same_command_id": retry_with_same_command_id,
        "data": {
            "command_id": command_id,
            "route": route,
            "evidence_phase": phase,
            "mutation_performed": False,
            "suppress_command_journal": True,
        },
    }


def _replayed_strict_command_payload(payload: dict[str, Any], command_id: str) -> dict[str, Any]:
    result = dict(payload)
    data = dict(result.get("data") or {})
    original_evidence_phase = str(data.get("evidence_phase") or "completed")
    data.update(
        {
            "command_id": command_id,
            "idempotent_replay": True,
            "mutation_performed": False,
            "evidence_phase": "replayed",
            "original_evidence_phase": original_evidence_phase,
            "current_state_unverified": True,
            "journal_durability": "strict",
            "strict_command_journal_recorded": True,
        }
    )
    result["data"] = data
    return result


def _with_strict_command_evidence(payload: dict[str, Any], command_id: str) -> dict[str, Any]:
    result = dict(payload)
    data = dict(result.get("data") or {})
    evidence_phase = str(data.get("evidence_phase") or "").strip()
    if not evidence_phase:
        if str(result.get("command") or "") == "pipeline.start":
            evidence_phase = "running" if bool(result.get("ok")) else "rejected"
        else:
            evidence_phase = "completed" if bool(result.get("ok")) else "rejected_or_failed"
    data.update(
        {
            "command_id": command_id,
            "evidence_phase": evidence_phase,
            "journal_durability": "strict",
            "strict_command_journal_recorded": True,
            "idempotent_replay": False,
            "mutation_performed": True,
        }
    )
    result["data"] = data
    return result
