"""
Coordinator HTTP server and request handler implementation.

This module owns the HTTP connection/session handling for the coordinator
facade. Keep log records on the historical ``network.coordinator`` logger so
existing operator diagnostics and tests continue to observe the same source.
"""
from __future__ import annotations

import http.server
import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol

from ..auth import AUTH_FAILURE_CLOCK_SKEW
from ..coordinator_http import MAX_COORDINATOR_BODY_BYTES, parse_query_params, validate_content_length

_log = logging.getLogger("mediapipeline.desktop.network.coordinator")

# W3 - protocol version advertised in /api/health so workers can detect
# coordinator/worker version skew before attempting incompatible RPCs.
# Bump on any wire-format change (new required fields, renamed endpoints,
# changed response shapes). Workers may treat a missing field as 0.
_COORDINATOR_PROTOCOL_VERSION = 2


@dataclass
class _ActiveRequest:
    thread: threading.Thread | None = None
    authenticated: bool = False


class _CoordinatorDispatcherProtocol(Protocol):
    _accepting_claims: bool

    def _heartbeat_timeout_mins(self) -> float: ...

    def _request_auth_result(
        self,
        headers: dict[str, str],
        *,
        method: str,
        path_with_query: str,
        body: bytes,
    ) -> object: ...

    def _validate_request_auth(
        self,
        headers: dict[str, str],
        *,
        method: str,
        path_with_query: str,
        body: bytes,
    ) -> bool: ...

    def _http_claim(self, handler: _CoordHandler, params: dict[str, str]) -> None: ...

    def _http_libraries(self, handler: _CoordHandler, params: dict[str, str]) -> None: ...

    def _http_ping(self, handler: _CoordHandler) -> None: ...

    def _http_workers(self, handler: _CoordHandler, params: dict[str, str]) -> None: ...

    def _http_done(self, handler: _CoordHandler, body: bytes) -> None: ...

    def _http_heartbeat(self, handler: _CoordHandler, body: bytes) -> None: ...

    def _http_log(self, handler: _CoordHandler, body: bytes) -> None: ...


def _coordinator_health_heartbeat_timeout_mins(disp: _CoordinatorDispatcherProtocol) -> float:
    try:
        return disp._heartbeat_timeout_mins()
    except Exception as exc:
        _log.warning("Coordinator health heartbeat timeout lookup failed; using 5.0 minutes: %s", exc)
        return 5.0


class _CoordServer(http.server.ThreadingHTTPServer):
    """Coordinator-specific HTTP server.

    Attributes set after construction by ``CoordinatorDispatcher.__init__``:
    - ``dispatcher``: back-reference to the owning dispatcher.
    """

    # Pre-authentication readers must never keep process shutdown alive. The
    # server explicitly joins authenticated handlers for a bounded interval.
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True
    MAX_CONCURRENT_HANDLERS = 32
    AUTHENTICATED_CLEANUP_TIMEOUT_SECONDS = 5.0

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[http.server.BaseHTTPRequestHandler],
        bind_and_activate: bool = True,
    ) -> None:
        self._handler_slots = threading.BoundedSemaphore(self.MAX_CONCURRENT_HANDLERS)
        self._active_requests: dict[socket.socket, _ActiveRequest] = {}
        self._active_requests_lock = threading.Lock()
        self._closing = False
        self._capacity_warning_logged = False
        super().__init__(server_address, request_handler_class, bind_and_activate)

    def process_request(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        """Start one bounded handler thread or close an excess connection."""
        if not self._handler_slots.acquire(blocking=False):
            with self._active_requests_lock:
                if not self._capacity_warning_logged:
                    _log.warning(
                        "Coordinator HTTP handler capacity reached (%d); rejecting excess connections.",
                        self.MAX_CONCURRENT_HANDLERS,
                    )
                    self._capacity_warning_logged = True
            self._close_rejected_request(request)
            return

        with self._active_requests_lock:
            if self._closing:
                self._handler_slots.release()
                self._close_rejected_request(request)
                return
            state = _ActiveRequest()
            self._active_requests[request] = state

        try:
            thread = threading.Thread(
                target=self.process_request_thread,
                args=(request, client_address),
                daemon=True,
            )
            with self._active_requests_lock:
                state.thread = thread
            thread.start()
        except BaseException:
            self._finish_active_request(request)
            self._close_rejected_request(request)
            raise

    def process_request_thread(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._finish_active_request(request)

    def server_close(self) -> None:
        """Abandon pre-auth reads and boundedly join authenticated cleanup."""
        with self._active_requests_lock:
            self._closing = True
            active_requests = tuple(self._active_requests.items())
        authenticated_threads: list[threading.Thread] = []
        for request, state in active_requests:
            if state.authenticated:
                if state.thread is not None and state.thread is not threading.current_thread():
                    authenticated_threads.append(state.thread)
                continue
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        super().server_close()

        deadline = time.monotonic() + self.AUTHENTICATED_CLEANUP_TIMEOUT_SECONDS
        for thread in authenticated_threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        unfinished = [thread.name for thread in authenticated_threads if thread.is_alive()]
        if unfinished:
            _log.warning(
                "Coordinator HTTP shutdown left %d authenticated handler(s) running after %.1f seconds: %s",
                len(unfinished),
                self.AUTHENTICATED_CLEANUP_TIMEOUT_SECONDS,
                ", ".join(unfinished),
            )

    def _mark_request_authenticated(self, request: socket.socket) -> bool:
        with self._active_requests_lock:
            state = self._active_requests.get(request)
            if self._closing or state is None:
                return False
            state.authenticated = True
            return True

    def _finish_active_request(self, request: socket.socket) -> None:
        with self._active_requests_lock:
            if self._active_requests.pop(request, None) is None:
                return
            self._capacity_warning_logged = False
        self._handler_slots.release()

    def _close_rejected_request(self, request: socket.socket) -> None:
        try:
            request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.shutdown_request(request)

    def _active_request_count(self) -> int:
        with self._active_requests_lock:
            return len(self._active_requests)

    # Set by the dispatcher after server creation.
    dispatcher: _CoordinatorDispatcherProtocol


class _CoordHandler(http.server.BaseHTTPRequestHandler):
    """Per-request handler for the coordinator HTTP API."""

    server: _CoordServer  # type: ignore[assignment]

    # N4 - request bodies on this API are tiny JSON envelopes (claim
    # responses, heartbeat payloads, log entries). 1 MB is generous
    # cover for cluster log entries with embedded stack traces; reject
    # anything larger with 413 instead of allocating arbitrary RAM.
    MAX_BODY_BYTES = MAX_COORDINATOR_BODY_BYTES
    REQUEST_IO_TIMEOUT_SECONDS = 15.0

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(self.REQUEST_IO_TIMEOUT_SECONDS)

    # Silence the default access log - coordinator handles its own logging.
    def log_message(self, fmt, *args) -> None:  # noqa: ANN001
        pass

    @property
    def _disp(self) -> _CoordinatorDispatcherProtocol:
        return self.server.dispatcher

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        try:
            body = json.dumps(data, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            _log.exception("Coordinator attempted to send a non-strict JSON response.")
            status = 500
            body = json.dumps({"error": "internal non-strict JSON response"}, allow_nan=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type",   "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control",  "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            _log.warning(
                "Failed to send coordinator JSON response status=%s; client may not receive response: %s",
                status,
                exc,
            )
            raise

    def _check_auth(self, *, method: str, path_with_query: str, body: bytes = b"") -> bool:
        auth_result = getattr(self._disp, "_request_auth_result", None)
        if callable(auth_result):
            result = auth_result(
                dict(self.headers),
                method=method,
                path_with_query=path_with_query,
                body=body,
            )
            ok = bool(getattr(result, "ok", False))
            reason = str(getattr(result, "reason", "") or "auth_failed")
            self._auth_failure_reason = "" if ok else reason  # type: ignore[attr-defined]
        else:
            ok = self._disp._validate_request_auth(
                dict(self.headers),
                method=method,
                path_with_query=path_with_query,
                body=body,
            )
            self._auth_failure_reason = "" if ok else "auth_failed"  # type: ignore[attr-defined]
        if ok and not self.server._mark_request_authenticated(self.connection):
            self._auth_failure_reason = "server_shutting_down"
            self.close_connection = True
            return False
        return ok

    def _unauthorized_payload(self) -> dict[str, Any]:
        reason = str(getattr(self, "_auth_failure_reason", "") or "auth_failed")
        if reason == "server_shutting_down":
            return {"error": reason, "safe_next_action": "Retry after the coordinator restarts."}
        payload: dict[str, Any] = {"error": "unauthorized", "reason": reason}
        if reason == AUTH_FAILURE_CLOCK_SKEW:
            payload["safe_next_action"] = "Synchronize coordinator and worker clocks, then retry."
        return payload

    def _parse_query_params(self) -> dict[str, str]:
        return parse_query_params(self.path)

    def _read_body(self) -> bytes | None:
        """Read the request body, enforcing the configured size cap.

        Returns ``None`` after sending an HTTP error response when the
        Content-Length is malformed (N5) or exceeds ``MAX_BODY_BYTES``
        (N4). Callers must short-circuit on ``None``.
        """
        decision = validate_content_length(self.headers.get("Content-Length", "0"), self.MAX_BODY_BYTES)
        if not decision.ok and decision.status == 400:
            # N5 - malformed Content-Length used to crash the request
            # thread with ValueError. Reject with 400 cleanly instead.
            try:
                self._send_json(dict(decision.payload or {"error": "Invalid Content-Length header"}), 400)
            except Exception as exc:
                _log.warning(
                    "Failed to send malformed Content-Length coordinator request response; client may not receive 400: %s",
                    exc,
                )
            return None
        if not decision.ok and decision.status == 413:
            # N4 - refuse oversized bodies before allocating any buffer.
            # Send 413 with Connection: close so the offending client
            # has to reconnect, preventing a streaming-amplification
            # follow-up on the same socket.
            try:
                body = json.dumps(decision.payload or {}, allow_nan=False).encode("utf-8")
                self.send_response(413)
                self.send_header("Content-Type",   "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection",     "close")
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                _log.warning(
                    "Failed to send oversized coordinator request response; client may not receive 413: %s",
                    exc,
                )
            return None
        if decision.length <= 0:
            return b""
        try:
            body = self.rfile.read(decision.length)
        except Exception as exc:
            _log.warning(
                "Failed to read coordinator request body after Content-Length %d; request handler will stop: %s",
                decision.length,
                exc,
            )
            return None
        if len(body) != decision.length:
            _log.warning(
                "Incomplete coordinator request body: expected %d bytes but received %d; request handler will stop.",
                decision.length,
                len(body),
            )
            return None
        return body

    def _reject_unsupported_transfer_encoding(self) -> bool:
        raw_value = str(self.headers.get("Transfer-Encoding", "") or "").strip()
        if not raw_value:
            return False
        self.close_connection = True
        try:
            body = json.dumps(
                {"error": "unsupported Transfer-Encoding", "supported": "Content-Length"},
                allow_nan=False,
            ).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            _log.warning(
                "Failed to send unsupported Transfer-Encoding coordinator response; client may not receive 400: %s",
                exc,
            )
        return True

    def do_OPTIONS(self) -> None:
        try:
            self.send_response(204)
            self.send_header("Allow", "GET, POST, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()
        except Exception as exc:
            _log.warning(
                "Failed to send coordinator OPTIONS response; client may not receive 204: %s",
                exc,
            )
            raise

    def do_GET(self) -> None:
        path_with_query = self.path or "/"
        path   = path_with_query.split("?")[0].rstrip("/") or "/"
        params = self._parse_query_params()

        # /api/health is auth-free so workers and the UI can probe reachability
        # without needing the token. It returns nothing sensitive.
        #
        # W3 - payload is enriched with protocol_version, heartbeat_timeout_mins,
        # and accepting_claims so workers can self-tune their poll cadence and
        # detect a coordinator drain without needing to actually call /api/claim.
        # Old workers that ignore these extra fields still see {"status": "ok"}.
        if path == "/api/health":
            disp = self._disp
            hb_timeout = _coordinator_health_heartbeat_timeout_mins(disp)
            self._send_json({
                "status":                 "ok",
                "service":                "mediapipeline-coordinator",
                "protocol_version":       _COORDINATOR_PROTOCOL_VERSION,
                "heartbeat_timeout_mins": hb_timeout,
                "accepting_claims":       bool(disp._accepting_claims),
            })
            return

        if not self._check_auth(method="GET", path_with_query=path_with_query):
            status = 503 if self._auth_failure_reason == "server_shutting_down" else 401
            self._send_json(self._unauthorized_payload(), status)
            return

        if path == "/api/claim":
            self._disp._http_claim(self, params)
        elif path == "/api/libraries":
            self._disp._http_libraries(self, params)
        elif path == "/api/ping":
            self._disp._http_ping(self)
        elif path == "/api/workers":
            self._disp._http_workers(self, params)
        else:
            self._send_json({"error": "not found", "path": path}, 404)

    def do_POST(self) -> None:
        path_with_query = self.path or "/"
        path = path_with_query.split("?")[0].rstrip("/") or "/"
        if self._reject_unsupported_transfer_encoding():
            return
        body = self._read_body()
        # _read_body returns None after it has already sent 400/413 for
        # malformed or oversized requests (N4/N5). Short-circuit so we
        # don't double-respond on the same socket.
        if body is None:
            return
        if not self._check_auth(method="POST", path_with_query=path_with_query, body=body):
            status = 503 if self._auth_failure_reason == "server_shutting_down" else 401
            self._send_json(self._unauthorized_payload(), status)
            return
        if path == "/api/done":
            self._disp._http_done(self, body)
        elif path == "/api/heartbeat":
            self._disp._http_heartbeat(self, body)
        elif path == "/api/log":
            self._disp._http_log(self, body)
        else:
            self._send_json({"error": "not found", "path": path}, 404)
