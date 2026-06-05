from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.handler_policy import (
    OPTIONS_RESPONSE_HEADERS,
    bounded_error_text,
    not_found_payload,
    options_response_headers,
    route_exception_payload,
    route_validation_error_payload,
    should_record_command_payload,
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

    def test_error_payload_helpers_preserve_handler_contract(self) -> None:
        self.assertEqual(unauthorized_payload(), {"error": "unauthorized"})
        self.assertEqual(not_found_payload("/api/missing"), {"error": "not found", "path": "/api/missing"})
        error_payload = route_exception_payload("/api/snapshot", RuntimeError("failed"))
        self.assertEqual(error_payload["error"], "internal route error")
        self.assertEqual(error_payload["path"], "/api/snapshot")
        self.assertRegex(error_payload["error_id"], r"^[0-9a-f]{12}$")
        self.assertEqual(
            route_validation_error_payload("/api/snapshot", RuntimeError("failed")),
            {"error": "failed", "path": "/api/snapshot"},
        )
        self.assertEqual(bounded_error_text("abcdef", limit=4), "a...")
        self.assertEqual(
            route_validation_error_payload("/api/snapshot", RuntimeError("x" * 2500))["error"],
            ("x" * 1997) + "...",
        )

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
