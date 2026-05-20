from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


DESKTOP_ROOT = Path(__file__).resolve().parents[1]


class NetworkCoordinatorSourcePolicyTests(unittest.TestCase):
    def test_done_report_queue_removal_scheduling_failure_is_logged(self) -> None:
        source = (DESKTOP_ROOT / "mediapipeline_desktop_app" / "network" / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("Failed to schedule queue removal after done report", source)
        self.assertIn("queue record may remain claimable until manually removed", source)
        self.assertIn("Retry policy: scheduled queue removal", source)
        self.assertNotIn("Retry policy: removed", source)

    def test_cluster_log_worker_timestamp_side_channel_failure_is_logged(self) -> None:
        source = (DESKTOP_ROOT / "mediapipeline_desktop_app" / "network" / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("Could not preserve worker timestamp for /api/log event %s", source)
        self.assertIn("using coordinator receive time only", source)
        self.assertNotIn("entry._worker_ts = entry.timestamp or \"\"    # type: ignore[attr-defined]\n        except Exception:\n            pass", source)

    def test_oversized_request_response_failure_is_warning_logged(self) -> None:
        source = (DESKTOP_ROOT / "mediapipeline_desktop_app" / "network" / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("Failed to send oversized coordinator request response", source)
        self.assertIn("client may not receive 413", source)
        self.assertNotIn('_log.debug("Failed to send oversized coordinator request response.', source)

    def test_malformed_content_length_response_failure_is_warning_logged(self) -> None:
        source = (DESKTOP_ROOT / "mediapipeline_desktop_app" / "network" / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("Failed to send malformed Content-Length coordinator request response", source)
        self.assertIn("client may not receive 400", source)

    def test_request_body_read_failure_is_warning_logged(self) -> None:
        source = (DESKTOP_ROOT / "mediapipeline_desktop_app" / "network" / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("Failed to read coordinator request body after Content-Length %d", source)
        self.assertIn("request handler will stop", source)

    def test_json_response_send_failure_is_warning_logged(self) -> None:
        source = (DESKTOP_ROOT / "mediapipeline_desktop_app" / "network" / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("Failed to send coordinator JSON response status=%s", source)
        self.assertIn("client may not receive response", source)

    def test_options_response_send_failure_is_warning_logged(self) -> None:
        source = (DESKTOP_ROOT / "mediapipeline_desktop_app" / "network" / "coordinator.py").read_text(encoding="utf-8")

        self.assertIn("Failed to send coordinator OPTIONS response", source)
        self.assertIn("client may not receive 204", source)


if __name__ == "__main__":
    unittest.main()
