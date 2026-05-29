from __future__ import annotations

import unittest

from app.status.events import (
    format_pipeline_event_summary,
    pipeline_event_stage_label,
    structured_status_from_pipeline_event,
)


class ServiceStatusEventsTests(unittest.TestCase):
    def test_structured_event_status_handles_publish_states(self) -> None:
        self.assertEqual(
            structured_status_from_pipeline_event({"event_type": "publish_parked", "status": "output-space-deferred"}),
            "parked until output space is available",
        )
        self.assertEqual(
            structured_status_from_pipeline_event({"event_type": "publish_drained", "status": "failed"}),
            "server push failed",
        )

    def test_tool_completed_uses_stage_label_and_status(self) -> None:
        event = {"event_type": "tool_completed", "stage": "encode", "status": "failed", "route": "encode"}

        self.assertEqual(structured_status_from_pipeline_event(event), "encode failed")

    def test_stage_label_keeps_pending_push_special_cases(self) -> None:
        self.assertEqual(
            pipeline_event_stage_label("pending-push-park", "", "output-space-deferred"),
            "parked until output space is available",
        )

    def test_event_summary_surfaces_denied_priority(self) -> None:
        rows = format_pipeline_event_summary(
            [
                {
                    "event_type": "tool_started",
                    "stage": "encode",
                    "source_path": r"C:\Media\Example.mkv",
                    "data": {
                        "tool_name": "ffmpeg",
                        "priority_requested": "high",
                        "priority_applied": False,
                        "priority_error": "privilege missing",
                    },
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertIn("Example.mkv", rows[0])
        self.assertIn("priority high requested but not applied: privilege missing", rows[0])


if __name__ == "__main__":
    unittest.main()
