from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.handler_policy import (
    OPTIONS_RESPONSE_HEADERS,
    OperatorRouteError,
    bounded_error_text,
    cors_response_headers,
    not_found_payload,
    options_response_headers,
    route_exception_journal_payload,
    route_exception_payload,
    route_exception_status,
    route_validation_error_payload,
    route_validation_journal_payload,
    should_record_command_payload,
    should_record_route_exception_journal,
    should_record_validation_failure_journal,
    unauthorized_payload,
)
from mediapipeline.desktop.api.http_helpers import is_client_disconnect_error, send_bytes


class LocalApiHandlerPolicyTests(unittest.TestCase):
    def test_options_headers_preserve_cors_contract(self) -> None:
        headers = dict(OPTIONS_RESPONSE_HEADERS)

        self.assertEqual(headers["Allow"], "GET, POST, OPTIONS")
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://127.0.0.1")
        self.assertIn("X-MediaPipeline-Token", headers["Access-Control-Allow-Headers"])
        self.assertEqual(headers["Access-Control-Allow-Methods"], "GET, POST, OPTIONS")
        self.assertEqual(headers["Content-Length"], "0")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")

    def test_options_headers_reflect_authorized_origin(self) -> None:
        headers = dict(options_response_headers("http://localhost:8765"))

        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:8765")
        self.assertEqual(headers["Vary"], "Origin")

    def test_cors_response_headers_reflect_authorized_origin(self) -> None:
        headers = dict(cors_response_headers("tauri://localhost"))

        self.assertEqual(headers["Access-Control-Allow-Origin"], "tauri://localhost")
        self.assertEqual(headers["Vary"], "Origin")

    def test_error_payload_helpers_preserve_handler_contract(self) -> None:
        self.assertEqual(unauthorized_payload(), {"error": "unauthorized"})
        self.assertEqual(not_found_payload("/api/missing"), {"error": "not found", "path": "/api/missing"})
        error_payload = route_exception_payload("/api/snapshot", RuntimeError("failed"))
        self.assertEqual(error_payload["error"], "internal route error")
        self.assertEqual(error_payload["path"], "/api/snapshot")
        self.assertRegex(error_payload["error_id"], r"^[0-9a-f]{12}$")
        retryable_error = OperatorRouteError(
            code="snapshot_busy",
            operator_message="Dashboard status is still loading. Wait a moment and refresh.",
            status=503,
        )
        retryable_payload = route_exception_payload("/api/snapshot", retryable_error)
        self.assertEqual(retryable_payload["error"], "Dashboard status is still loading. Wait a moment and refresh.")
        self.assertEqual(retryable_payload["code"], "snapshot_busy")
        self.assertTrue(retryable_payload["retryable"])
        self.assertEqual(retryable_payload["status"], 503)
        self.assertEqual(route_exception_status(retryable_error), 503)
        self.assertEqual(route_exception_status(RuntimeError("failed")), 500)
        self.assertEqual(
            route_validation_error_payload("/api/snapshot", RuntimeError("failed")),
            {"error": "failed", "path": "/api/snapshot"},
        )
        self.assertEqual(bounded_error_text("abcdef", limit=4), "a...")
        self.assertEqual(
            route_validation_error_payload("/api/snapshot", RuntimeError("x" * 2500))["error"],
            ("x" * 1997) + "...",
        )

    def test_route_validation_journal_payload_is_sanitized_command_result(self) -> None:
        payload = route_validation_journal_payload("/api/pipeline/start", RuntimeError("x" * 2500))

        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "local_api.validation_failed")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["errors"], [("x" * 1997) + "..."])
        self.assertEqual(payload["data"]["path"], "/api/pipeline/start")
        self.assertEqual(payload["data"]["status"], 400)

    def test_route_exception_journal_payload_is_sanitized_command_result(self) -> None:
        response = {"error": "internal route error", "path": "/api/pipeline/start", "error_id": "abc123def456"}

        payload = route_exception_journal_payload("/api/pipeline/start", response)

        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "local_api.route_exception")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["errors"], ["Internal route error."])
        self.assertEqual(payload["refresh_hint"], "diagnostics")
        self.assertEqual(payload["data"]["path"], "/api/pipeline/start")
        self.assertEqual(payload["data"]["status"], 500)
        self.assertEqual(payload["data"]["error_id"], "abc123def456")
        self.assertNotIn("RuntimeError", str(payload))

    def test_route_failure_journaling_policy_suppresses_secret_transfer_routes(self) -> None:
        self.assertFalse(should_record_validation_failure_journal("/api/network/coordinator/join-blob"))
        self.assertFalse(should_record_validation_failure_journal("/api/network/worker/join-cluster"))
        self.assertFalse(should_record_route_exception_journal("/api/network/coordinator/join-blob"))
        self.assertTrue(should_record_route_exception_journal("/api/pipeline/start"))

    def test_command_journal_recording_policy_is_success_status_only(self) -> None:
        self.assertTrue(should_record_command_payload(200))
        self.assertTrue(should_record_command_payload(399))
        self.assertFalse(should_record_command_payload(400))
        self.assertFalse(should_record_command_payload(500))

    def test_send_bytes_treats_client_disconnect_as_non_route_failure(self) -> None:
        class AbortWriter:
            def write(self, body: bytes) -> None:
                _ = body
                raise ConnectionAbortedError(10053, "client aborted")

        class Handler:
            wfile = AbortWriter()

            def __init__(self) -> None:
                self.responses: list[int] = []
                self.headers: list[tuple[str, str]] = []
                self.ended = False

            def send_response(self, status: int) -> None:
                self.responses.append(status)

            def send_header(self, name: str, value: str) -> None:
                self.headers.append((name, value))

            def end_headers(self) -> None:
                self.ended = True

        handler = Handler()

        self.assertTrue(is_client_disconnect_error(ConnectionAbortedError()))
        send_bytes(handler, b'{"ok": true}', content_type="application/json; charset=utf-8")

        self.assertEqual(handler.responses, [200])
        self.assertTrue(handler.ended)
        self.assertIn(("Content-Type", "application/json; charset=utf-8"), handler.headers)


if __name__ == "__main__":
    unittest.main()
