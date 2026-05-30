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
from typing import TYPE_CHECKING, Any

from ..coordinator_http import MAX_COORDINATOR_BODY_BYTES, parse_query_params, validate_content_length

if TYPE_CHECKING:
    from ..coordinator import CoordinatorDispatcher

_log = logging.getLogger("mediapipeline_desktop_app.network.coordinator")

# W3 - protocol version advertised in /api/health so workers can detect
# coordinator/worker version skew before attempting incompatible RPCs.
# Bump on any wire-format change (new required fields, renamed endpoints,
# changed response shapes). Workers may treat a missing field as 0.
_COORDINATOR_PROTOCOL_VERSION = 1


def _coordinator_health_heartbeat_timeout_mins(disp: "CoordinatorDispatcher") -> float:
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

    # Claim/done/log handlers update coordinator state; let shutdown wait for their cleanup.
    daemon_threads = False
    allow_reuse_address = True

    # Set by the dispatcher after server creation.
    dispatcher: "CoordinatorDispatcher"


class _CoordHandler(http.server.BaseHTTPRequestHandler):
    """Per-request handler for the coordinator HTTP API."""

    server: _CoordServer  # type: ignore[assignment]

    # N4 - request bodies on this API are tiny JSON envelopes (claim
    # responses, heartbeat payloads, log entries). 1 MB is generous
    # cover for cluster log entries with embedded stack traces; reject
    # anything larger with 413 instead of allocating arbitrary RAM.
    MAX_BODY_BYTES = MAX_COORDINATOR_BODY_BYTES

    # Silence the default access log - coordinator handles its own logging.
    def log_message(self, fmt, *args) -> None:  # noqa: ANN001
        pass

    @property
    def _disp(self) -> "CoordinatorDispatcher":
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
        return self._disp._validate_request_auth(
            dict(self.headers),
            method=method,
            path_with_query=path_with_query,
            body=body,
        )

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
            return self.rfile.read(decision.length)
        except Exception as exc:
            _log.warning(
                "Failed to read coordinator request body after Content-Length %d; request handler will stop: %s",
                decision.length,
                exc,
            )
            return None

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
            self._send_json({"error": "unauthorized"}, 401)
            return

        if path == "/api/claim":
            self._disp._http_claim(self, params)
        elif path == "/api/workers":
            self._disp._http_workers(self, params)
        else:
            self._send_json({"error": "not found", "path": path}, 404)

    def do_POST(self) -> None:
        path_with_query = self.path or "/"
        path = path_with_query.split("?")[0].rstrip("/") or "/"
        body = self._read_body()
        # _read_body returns None after it has already sent 400/413 for
        # malformed or oversized requests (N4/N5). Short-circuit so we
        # don't double-respond on the same socket.
        if body is None:
            return
        if not self._check_auth(method="POST", path_with_query=path_with_query, body=body):
            self._send_json({"error": "unauthorized"}, 401)
            return
        if path == "/api/done":
            self._disp._http_done(self, body)
        elif path == "/api/heartbeat":
            self._disp._http_heartbeat(self, body)
        elif path == "/api/log":
            self._disp._http_log(self, body)
        else:
            self._send_json({"error": "not found", "path": path}, 404)
