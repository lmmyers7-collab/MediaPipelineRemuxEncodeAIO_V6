from __future__ import annotations

import io
import json
import logging
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.network.auth import AUTH_VERSION
from mediapipeline_desktop_app.network.cluster_log import format_cluster_log_line
from mediapipeline_desktop_app.network.coordinator import (
    CoordinatorDispatcher,
    _CoordHandler,
    _coordinator_health_heartbeat_timeout_mins,
)
from mediapipeline_desktop_app.network.diagnostics import diagnostic_preview
from mediapipeline_desktop_app.network.firewall import (
    add_firewall_rule,
    build_add_firewall_rule_command,
    check_firewall_port,
    parse_matching_firewall_rule_names,
)
from mediapipeline_desktop_app.network.http_json import http_get_json, http_post_json
from mediapipeline_desktop_app.network.identity import (
    LOG_MESSAGE_TRUNCATION_SUFFIX,
    coerce_worker_name,
    is_valid_worker_id,
    sanitize_log_entry_fields,
)
from mediapipeline_desktop_app.network.coordinator_http import (
    MAX_COORDINATOR_BODY_BYTES,
    parse_query_params,
    validate_content_length,
)
from mediapipeline_desktop_app.network.coordinator_policy import (
    RETRY_AFTER_ACTIVE_SECONDS,
    RETRY_AFTER_IDLE_SECONDS,
    compute_retry_after_seconds,
    coordinator_bind_address,
    coordinator_port,
    heartbeat_timeout_mins,
)
from mediapipeline_desktop_app.network.coordinator_url import validate_coordinator_url
from mediapipeline_desktop_app.network.encode_config_snapshot import snapshot_encode_config
from mediapipeline_desktop_app.network.failure_policy import source_has_prior_failure
from mediapipeline_desktop_app.network.path_map import apply_source_path_map, parse_source_path_map
from mediapipeline_desktop_app.network.poll_policy import resolve_worker_poll_interval, resolve_worker_wait_seconds
from mediapipeline_desktop_app.network.probe import probe_coordinator_health, probe_worker_auth
from mediapipeline_desktop_app.network.protocol import ClaimResponse, DoneRequest, HeartbeatRequest, LogEntryRequest
from mediapipeline_desktop_app.network.registry import InFlightRegistry
from mediapipeline_desktop_app.network.share_block import (
    coerce_coordinator_port,
    format_coordinator_share_block,
    select_coordinator_share_ip,
)
from mediapipeline_desktop_app.network.threading_helpers import start_daemon_thread
from mediapipeline_desktop_app.network.worker_state import atomic_write_text, load_worker_state, save_worker_state
from mediapipeline_desktop_app.network.worker import (
    WorkerDispatcher,
    _atomic_write_text,
    _http_read_capped,
    _make_queue_record,
    _safe_hostname,
    _validate_coordinator_url,
)
from mediapipeline_desktop_app.network.worker_done import (
    build_completion_done_request,
    build_crash_recovery_done_request,
    build_release_done_request,
)
from mediapipeline_desktop_app.network.worker_record import make_queue_record


class NetworkCoordinatorHttpTests(unittest.TestCase):
    def test_http_json_get_posts_bounded_authenticated_requests(self) -> None:
        class FakeResponse:
            def __init__(self, body: bytes) -> None:
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> bool:
                return False

            def read(self, _limit: int) -> bytes:
                return self.body

        requests: list[object] = []
        signer_calls: list[tuple[str, str, bytes]] = []

        def fake_urlopen(request, timeout: int):
            requests.append((request, timeout))
            return FakeResponse(b'{"ok": true}')

        def signer(method: str, path_with_query: str, body: bytes) -> dict[str, str]:
            signer_calls.append((method, path_with_query, body))
            return {
                "X-MediaPipeline-Auth-Version": AUTH_VERSION,
                "X-MediaPipeline-Timestamp": "1700000000",
                "X-MediaPipeline-Nonce": f"nonce-{len(signer_calls)}",
                "X-MediaPipeline-Signature": "signature",
            }

        with patch("mediapipeline_desktop_app.network.http_json.urllib.request.urlopen", side_effect=fake_urlopen):
            get_result = http_get_json(
                "http://coordinator:7830",
                "/api/claim",
                headers={"Accept": "application/json"},
                params={"worker_id": "worker 1"},
                sign_request=signer,
                timeout_seconds=7,
            )
            post_result = http_post_json(
                "http://coordinator:7830",
                "/api/done",
                {"job_id": "job-1", "success": True},
                headers={"Accept": "application/json"},
                sign_request=signer,
                timeout_seconds=8,
            )

        get_request, get_timeout = requests[0]
        post_request, post_timeout = requests[1]
        self.assertEqual(get_result, {"ok": True})
        self.assertEqual(post_result, {"ok": True})
        self.assertEqual(get_timeout, 7)
        self.assertEqual(post_timeout, 8)
        self.assertEqual(get_request.get_method(), "GET")
        self.assertIn("worker_id=worker+1", get_request.full_url)
        get_headers = {key.casefold(): value for key, value in get_request.header_items()}
        post_headers = {key.casefold(): value for key, value in post_request.header_items()}
        self.assertNotIn("authorization", get_headers)
        self.assertNotIn("authorization", post_headers)
        self.assertEqual(get_headers["x-mediapipeline-auth-version"], AUTH_VERSION)
        self.assertEqual(post_headers["x-mediapipeline-auth-version"], AUTH_VERSION)
        self.assertEqual(post_request.get_method(), "POST")
        self.assertEqual(json.loads(post_request.data.decode("utf-8")), {"job_id": "job-1", "success": True})
        self.assertEqual(signer_calls[0], ("GET", "/api/claim?worker_id=worker+1", b""))
        self.assertEqual(signer_calls[1][0:2], ("POST", "/api/done"))
        self.assertEqual(json.loads(signer_calls[1][2].decode("utf-8")), {"job_id": "job-1", "success": True})

    def test_http_json_post_rejects_nonfinite_payload_before_request(self) -> None:
        with patch("mediapipeline_desktop_app.network.http_json.urllib.request.urlopen") as urlopen:
            with self.assertRaises(ValueError):
                http_post_json(
                    "http://coordinator:7830",
                    "/api/heartbeat",
                    {"job_id": "job-1", "progress_percent": float("nan")},
                    headers={"Authorization": "Bearer token"},
                )

        urlopen.assert_not_called()

    def test_http_json_response_rejects_nonfinite_payload(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args) -> bool:
                return False

            def read(self, _limit: int) -> bytes:
                return b'{"progress": NaN}'

        with patch("mediapipeline_desktop_app.network.http_json.urllib.request.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(RuntimeError, "Invalid JSON from http://coordinator:7830/api/workers"):
                http_get_json(
                    "http://coordinator:7830",
                    "/api/workers",
                    headers={"Authorization": "Bearer token"},
                )

    def test_coordinator_send_json_rejects_nonfinite_response_payload(self) -> None:
        class FakeHandler:
            def __init__(self) -> None:
                self.status: int | None = None
                self.headers: dict[str, str] = {}
                self.wfile = io.BytesIO()

            def send_response(self, status: int) -> None:
                self.status = status

            def send_header(self, key: str, value: str) -> None:
                self.headers[key] = value

            def end_headers(self) -> None:
                return None

        handler = FakeHandler()

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="ERROR") as logs:
            _CoordHandler._send_json(handler, {"progress": float("nan")})  # type: ignore[arg-type]

        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler.status, 500)
        self.assertEqual(body, {"error": "internal non-strict JSON response"})
        self.assertIn("Coordinator attempted to send a non-strict JSON response", "\n".join(logs.output))

    def test_coordinator_send_json_write_failure_is_logged(self) -> None:
        class BrokenWriter:
            def write(self, _body: bytes) -> None:
                raise OSError("socket closed")

        class FakeHandler:
            def __init__(self) -> None:
                self.status: int | None = None
                self.headers: dict[str, str] = {}
                self.wfile = BrokenWriter()

            def send_response(self, status: int) -> None:
                self.status = status

            def send_header(self, key: str, value: str) -> None:
                self.headers[key] = value

            def end_headers(self) -> None:
                return None

        handler = FakeHandler()

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            with self.assertRaisesRegex(OSError, "socket closed"):
                _CoordHandler._send_json(handler, {"status": "ok"})  # type: ignore[arg-type]

        self.assertEqual(handler.status, 200)
        self.assertIn("Failed to send coordinator JSON response status=200", "\n".join(logs.output))
        self.assertIn("client may not receive response", "\n".join(logs.output))

    def test_coordinator_options_response_failure_is_logged(self) -> None:
        class FakeHandler:
            def __init__(self) -> None:
                self.status: int | None = None
                self.headers: dict[str, str] = {}

            def send_response(self, status: int) -> None:
                self.status = status

            def send_header(self, key: str, value: str) -> None:
                self.headers[key] = value

            def end_headers(self) -> None:
                raise OSError("socket closed")

        handler = FakeHandler()

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            with self.assertRaisesRegex(OSError, "socket closed"):
                _CoordHandler.do_OPTIONS(handler)  # type: ignore[arg-type]

        self.assertEqual(handler.status, 204)
        self.assertEqual(handler.headers["Allow"], "GET, POST, OPTIONS")
        self.assertIn("Failed to send coordinator OPTIONS response", "\n".join(logs.output))
        self.assertIn("client may not receive 204", "\n".join(logs.output))

    def test_coordinator_rejects_nonfinite_json_request_body(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._http_heartbeat(
                dispatcher,
                handler,
                b'{"job_id":"job-1","worker_id":"worker-1","progress_percent": NaN}',
            )

        self.assertEqual(sent, [({"error": "Invalid JSON body"}, 400)])
        self.assertIn("Rejected /api/heartbeat with invalid JSON body", "\n".join(logs.output))

    def test_coordinator_logs_invalid_done_and_cluster_log_request_bodies(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)

        for endpoint, method in (
            ("/api/done", CoordinatorDispatcher._http_done),
            ("/api/log", CoordinatorDispatcher._http_log),
        ):
            sent: list[tuple[dict[str, object], int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

            with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
                method(dispatcher, handler, b'{"job_id": NaN}')  # type: ignore[misc]

            self.assertEqual(sent, [({"error": "Invalid JSON body"}, 400)])
            self.assertIn(f"Rejected {endpoint} with invalid JSON body", "\n".join(logs.output))

    def test_coordinator_logs_invalid_done_and_heartbeat_identifiers(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)

        cases = (
            (
                "/api/done",
                CoordinatorDispatcher._http_done,
                {"job_id": "job-1", "worker_id": "worker bad", "success": True},
                {"error": "invalid worker_id"},
                "invalid worker_id",
            ),
            (
                "/api/heartbeat",
                CoordinatorDispatcher._http_heartbeat,
                {"job_id": "job bad", "worker_id": "worker-1"},
                {"error": "invalid job_id"},
                "invalid job_id",
            ),
        )

        for endpoint, method, payload, expected_error, expected_log in cases:
            sent: list[tuple[dict[str, object], int]] = []
            handler = SimpleNamespace(_send_json=lambda response, status=200: sent.append((response, status)))

            with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
                method(dispatcher, handler, json.dumps(payload).encode("utf-8"))  # type: ignore[misc]

            self.assertEqual(sent, [(expected_error, 400)])
            output = "\n".join(logs.output)
            self.assertIn(f"Rejected {endpoint}", output)
            self.assertIn(expected_log, output)

    def test_coordinator_heartbeat_registry_failure_returns_logged_500(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = SimpleNamespace(
            heartbeat=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("registry locked"))
        )
        handler = SimpleNamespace(_send_json=lambda response, status=200: sent.append((response, status)))
        payload = {"job_id": "job-1", "worker_id": "worker-1", "progress_percent": 25.0}

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="ERROR") as logs:
            CoordinatorDispatcher._http_heartbeat(
                dispatcher,
                handler,
                json.dumps(payload).encode("utf-8"),
            )

        self.assertEqual(sent, [({"error": "heartbeat unavailable"}, 500)])
        output = "\n".join(logs.output)
        self.assertIn("Failed to process /api/heartbeat for job job-1 from worker worker-1", output)
        self.assertIn("registry locked", output)

    def test_coordinator_reclaimed_heartbeat_cluster_log_failure_does_not_block_response(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = SimpleNamespace(
            heartbeat=lambda *_args, **_kwargs: "reclaimed"
        )
        dispatcher.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster blocked"))  # type: ignore[assignment]
        handler = SimpleNamespace(_send_json=lambda response, status=200: sent.append((response, status)))
        payload = {
            "job_id": "job-1",
            "worker_id": "worker-1",
            "progress_percent": 25.0,
            "current_stage": "Encoding",
        }

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._http_heartbeat(
                dispatcher,
                handler,
                json.dumps(payload).encode("utf-8"),
            )

        self.assertEqual(sent, [({"status": "reclaimed"}, 200)])
        output = "\n".join(logs.output)
        self.assertIn("Failed to emit heartbeat-reclaimed cluster event for job job-1", output)
        self.assertIn("cluster blocked", output)

    def test_coordinator_done_registry_completion_failure_returns_logged_500(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = SimpleNamespace(
            _lock=threading.Lock(),
            _jobs={"job-1": SimpleNamespace(worker_id="worker-1")},
            complete=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("complete exploded")),
        )
        handler = SimpleNamespace(_send_json=lambda response, status=200: sent.append((response, status)))
        payload = {"job_id": "job-1", "worker_id": "worker-1", "success": True}

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="ERROR") as logs:
            CoordinatorDispatcher._http_done(
                dispatcher,
                handler,
                json.dumps(payload).encode("utf-8"),
            )

        self.assertEqual(sent, [({"error": "done state unavailable"}, 500)])
        output = "\n".join(logs.output)
        self.assertIn("Failed to process /api/done completion for job job-1 from worker worker-1", output)
        self.assertIn("complete exploded", output)

    def test_coordinator_done_registry_release_failure_returns_logged_500(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = SimpleNamespace(
            _lock=threading.Lock(),
            _jobs={"job-1": SimpleNamespace(worker_id="worker-1")},
            unclaim=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("release exploded")),
        )
        handler = SimpleNamespace(_send_json=lambda response, status=200: sent.append((response, status)))
        payload = {"job_id": "job-1", "worker_id": "worker-1", "released": True}

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="ERROR") as logs:
            CoordinatorDispatcher._http_done(
                dispatcher,
                handler,
                json.dumps(payload).encode("utf-8"),
            )

        self.assertEqual(sent, [({"error": "done state unavailable"}, 500)])
        output = "\n".join(logs.output)
        self.assertIn("Failed to process /api/done release for job job-1 from worker worker-1", output)
        self.assertIn("release exploded", output)

    def test_coordinator_logs_cluster_log_missing_event_rejection(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        handler = SimpleNamespace(_send_json=lambda response, status=200: sent.append((response, status)))
        payload = {"worker_id": "worker-1", "message": "missing event"}

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._http_log(dispatcher, handler, json.dumps(payload).encode("utf-8"))  # type: ignore[arg-type]

        self.assertEqual(sent, [({"error": "event field is required"}, 400)])
        self.assertIn("Rejected /api/log without required event field", "\n".join(logs.output))

    def test_coordinator_logs_cluster_log_field_sanitization(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        appended: list[LogEntryRequest] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._append_cluster_log = lambda entry: appended.append(entry)  # type: ignore[method-assign]
        handler = SimpleNamespace(_send_json=lambda response, status=200: sent.append((response, status)))
        payload = {
            "worker_id": "worker bad",
            "worker_name": "Worker",
            "job_id": "job bad",
            "event": "x" * 70,
            "message": "m" * 5000,
        }

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._http_log(dispatcher, handler, json.dumps(payload).encode("utf-8"))  # type: ignore[arg-type]

        self.assertEqual(sent, [({"status": "ok"}, 200)])
        self.assertEqual(len(appended), 1)
        self.assertEqual(appended[0].worker_id, "")
        self.assertEqual(appended[0].job_id, "")
        output = "\n".join(logs.output)
        self.assertIn("Sanitized /api/log invalid worker_id", output)
        self.assertIn("Sanitized /api/log invalid job_id", output)
        self.assertIn("Truncated /api/log event field", output)
        self.assertIn("Truncated /api/log message field", output)

    def test_coordinator_http_log_worker_timestamp_side_channel_failure_warns(self) -> None:
        class NoWorkerTimestampEntry(LogEntryRequest):
            def __setattr__(self, name: str, value: object) -> None:
                if name == "_worker_ts":
                    raise RuntimeError("side-channel blocked")
                super().__setattr__(name, value)

        sent: list[tuple[dict[str, object], int]] = []
        appended: list[LogEntryRequest] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._append_cluster_log = lambda entry: appended.append(entry)  # type: ignore[method-assign]
        handler = SimpleNamespace(_send_json=lambda response, status=200: sent.append((response, status)))
        entry = NoWorkerTimestampEntry(
            timestamp="2026-05-08T11:50:00-04:00",
            worker_id="worker-1",
            event="heartbeat",
            message="still alive",
        )

        with (
            patch(
                "mediapipeline_desktop_app.network.coordinator_http_handlers.LogEntryRequest.from_dict",
                return_value=entry,
            ),
            self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs,
        ):
            CoordinatorDispatcher._http_log(dispatcher, handler, b"{}")  # type: ignore[arg-type]

        self.assertEqual(sent, [({"status": "ok"}, 200)])
        self.assertEqual(appended, [entry])
        self.assertNotEqual(entry.timestamp, "2026-05-08T11:50:00-04:00")
        output = "\n".join(logs.output)
        self.assertIn("Could not preserve worker timestamp for /api/log event heartbeat", output)
        self.assertIn("side-channel blocked", output)

    def test_coordinator_http_log_append_failure_still_returns_ok(self) -> None:
        sent: list[tuple[dict[str, object], int]] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._append_cluster_log = lambda _entry: (_ for _ in ()).throw(RuntimeError("append blocked"))  # type: ignore[method-assign]
        handler = SimpleNamespace(_send_json=lambda response, status=200: sent.append((response, status)))
        payload = {"worker_id": "worker-1", "event": "heartbeat", "message": "still alive"}

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._http_log(dispatcher, handler, json.dumps(payload).encode("utf-8"))  # type: ignore[arg-type]

        self.assertEqual(sent, [({"status": "ok"}, 200)])
        output = "\n".join(logs.output)
        self.assertIn("Unexpected cluster log append failure for event heartbeat", output)
        self.assertIn("append blocked", output)

    def test_http_json_error_reports_unreadable_error_body(self) -> None:
        class BadHttpError(urllib.error.HTTPError):
            def read(self, _limit: int = -1) -> bytes:
                raise OSError("body offline")

        def fake_urlopen(_request: object, timeout: int):
            raise BadHttpError("http://coordinator:7830/api/done", 500, "failed", hdrs=None, fp=None)

        with patch("mediapipeline_desktop_app.network.http_json.urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaisesRegex(RuntimeError, "failed to read error body: body offline"):
                http_post_json(
                    "http://coordinator:7830",
                    "/api/done",
                    {"job_id": "job-1"},
                    headers={"Authorization": "Bearer token"},
                    timeout_seconds=8,
                )

    def test_http_json_error_body_preview_is_bounded(self) -> None:
        class BodyHttpError(urllib.error.HTTPError):
            def read(self, _limit: int = -1) -> bytes:
                return b"<html>" + (b"x" * 900) + b"tail-marker"

        def fake_urlopen(_request: object, timeout: int):
            raise BodyHttpError("http://coordinator:7830/api/done", 500, "failed", hdrs=None, fp=None)

        with patch("mediapipeline_desktop_app.network.http_json.urllib.request.urlopen", side_effect=fake_urlopen):
            try:
                http_post_json(
                    "http://coordinator:7830",
                    "/api/done",
                    {"job_id": "job-1"},
                    headers={"Authorization": "Bearer token"},
                    timeout_seconds=8,
                )
            except RuntimeError as exc:
                message = str(exc)
            else:
                self.fail("Expected HTTP error to raise RuntimeError")

        self.assertIn("HTTP 500 from http://coordinator:7830/api/done: <html>", message)
        self.assertLess(len(message), 650)
        self.assertNotIn("tail-marker", message)

    def test_http_json_invalid_success_body_reports_url_and_bounded_preview(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args) -> bool:
                return False

            def read(self, _limit: int) -> bytes:
                return b"<html>" + (b"x" * 1000)

        with patch("mediapipeline_desktop_app.network.http_json.urllib.request.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(RuntimeError, "Invalid JSON from http://coordinator:7830/api/claim"):
                http_get_json(
                    "http://coordinator:7830",
                    "/api/claim",
                    headers={"Authorization": "Bearer token"},
                )

        try:
            with patch("mediapipeline_desktop_app.network.http_json.urllib.request.urlopen", return_value=FakeResponse()):
                http_get_json(
                    "http://coordinator:7830",
                    "/api/claim",
                    headers={"Authorization": "Bearer token"},
                )
        except RuntimeError as exc:
            self.assertLess(len(str(exc)), 650)
            self.assertIn("<html>", str(exc))



if __name__ == "__main__":
    unittest.main()
