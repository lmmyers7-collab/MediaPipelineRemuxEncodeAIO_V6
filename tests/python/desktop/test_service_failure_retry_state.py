from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.failures.retry_state import retry_state_for_failure_row, retry_state_payload


class FailureRetryStateTests(unittest.TestCase):
    def test_transient_failure_before_limit_is_backend_retryable(self) -> None:
        row = {
            "job_id": "job-1",
            "source_path": "C:/Source/Movie.mkv",
            "stage": "scratch-copy",
            "error_code": "SOURCE_LOCKED",
            "classification": "transient",
            "reason": "File is locked.",
            "retry_count": 1,
            "retry_limit": 3,
        }

        retry = retry_state_for_failure_row(row)

        self.assertEqual(retry["schema_version"], "desktop_retry_state.v1")
        self.assertEqual(retry["job_id"], "job-1")
        self.assertEqual(retry["attempt"], 1)
        self.assertEqual(retry["max_attempts"], 3)
        self.assertTrue(retry["retry_allowed"])
        self.assertEqual(retry["retry_route_or_command"], "automatic_next_queue_pass")
        self.assertEqual(retry["status_state"], "retrying")

    def test_operator_required_or_exhausted_failure_is_blocked(self) -> None:
        row = {
            "source_path": "C:/Source/Movie.mkv",
            "stage": "encode",
            "error_code": "ENCODE_FAILED",
            "classification": "operator_required",
            "reason": "Retry limit reached.",
            "retry_count": 3,
            "retry_limit": 3,
            "suggested_action": "Inspect logs before clearing the marker.",
        }

        retry = retry_state_for_failure_row(row)

        self.assertFalse(retry["retry_allowed"])
        self.assertEqual(retry["retry_route_or_command"], "none_exposed")
        self.assertEqual(retry["status_state"], "blocked")
        self.assertIn("Inspect logs", retry["safe_next_action"])

    def test_payload_summarizes_retryable_and_blocked_rows(self) -> None:
        payload = retry_state_payload(
            [
                {"classification": "transient", "retry_count": 1, "retry_limit": 3},
                {"classification": "permanent", "retry_count": 0, "retry_limit": 3},
            ],
            source="markers",
            source_kind="markers",
        )

        self.assertEqual(payload["schema_version"], "desktop_retry_state.v1")
        self.assertEqual(payload["status_state"], "retrying")
        self.assertEqual(payload["row_count"], 2)
        self.assertEqual(payload["retryable_count"], 1)
        self.assertEqual(payload["blocked_count"], 1)
        self.assertTrue(payload["read_only"])


if __name__ == "__main__":
    unittest.main()
