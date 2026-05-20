from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api.handler_policy import (
    OPTIONS_RESPONSE_HEADERS,
    bounded_error_text,
    not_found_payload,
    route_exception_payload,
    should_record_command_payload,
    unauthorized_payload,
)


class LocalApiHandlerPolicyTests(unittest.TestCase):
    def test_options_headers_preserve_cors_contract(self) -> None:
        headers = dict(OPTIONS_RESPONSE_HEADERS)

        self.assertEqual(headers["Allow"], "GET, POST, OPTIONS")
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://127.0.0.1")
        self.assertIn("X-MediaPipeline-Token", headers["Access-Control-Allow-Headers"])
        self.assertEqual(headers["Access-Control-Allow-Methods"], "GET, POST, OPTIONS")
        self.assertEqual(headers["Content-Length"], "0")

    def test_error_payload_helpers_preserve_handler_contract(self) -> None:
        self.assertEqual(unauthorized_payload(), {"error": "unauthorized"})
        self.assertEqual(not_found_payload("/api/missing"), {"error": "not found", "path": "/api/missing"})
        self.assertEqual(
            route_exception_payload("/api/snapshot", RuntimeError("failed")),
            {"error": "failed", "path": "/api/snapshot"},
        )
        self.assertEqual(bounded_error_text("abcdef", limit=4), "a...")
        self.assertEqual(
            route_exception_payload("/api/snapshot", RuntimeError("x" * 2500))["error"],
            ("x" * 1997) + "...",
        )

    def test_command_journal_recording_policy_is_success_status_only(self) -> None:
        self.assertTrue(should_record_command_payload(200))
        self.assertTrue(should_record_command_payload(399))
        self.assertFalse(should_record_command_payload(400))
        self.assertFalse(should_record_command_payload(500))


if __name__ == "__main__":
    unittest.main()
