from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from mediapipeline_desktop_app.service_status_errors import format_recent_error_summary


class ServiceStatusErrorSummaryTests(unittest.TestCase):
    def test_pipeline_event_errors_take_priority(self) -> None:
        rows = format_recent_error_summary(
            resolved=SimpleNamespace(),
            pipeline_events=[
                {"event_type": "tool_completed", "status": "succeeded", "stage": "push"},
                {
                    "event_type": "tool_completed",
                    "status": "failed",
                    "stage": "encode",
                    "source_path": r"C:\Media\movie.mkv",
                    "data": {"error_code": "FFMPEG_FAILED", "error": "encoder failed"},
                },
            ],
            log_tail="ERROR older log line",
            latest_failure_json=None,
            max_items=1,
        )

        self.assertEqual(rows, ["tool_completed | failed | encode | FFMPEG_FAILED | movie.mkv | encoder failed"])

    def test_failure_json_is_used_when_events_do_not_have_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            failure_path = Path(temp_dir) / "round_failures.json"
            failure_path.write_text(
                json.dumps(
                    [
                        {
                            "ErrorCode": "PUBLISH_FAILED",
                            "Stage": "push",
                            "SourcePath": r"C:\Media\show.mkv",
                            "Reason": "network down",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            rows = format_recent_error_summary(
                resolved=SimpleNamespace(),
                pipeline_events=[],
                log_tail="",
                latest_failure_json=failure_path,
            )

        self.assertEqual(rows, ["PUBLISH_FAILED | push | show.mkv | network down"])

    def test_log_tail_is_used_as_last_fallback(self) -> None:
        rows = format_recent_error_summary(
            resolved=SimpleNamespace(),
            pipeline_events=[],
            log_tail="INFO ok\nFATAL last failure\nERROR older failure",
            latest_failure_json=None,
            max_items=1,
        )

        self.assertEqual(rows, ["ERROR older failure"])


if __name__ == "__main__":
    unittest.main()
