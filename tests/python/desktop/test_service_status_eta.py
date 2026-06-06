from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.status.eta import ETA_SCHEMA_VERSION, eta_payload


class EtaPayloadTests(unittest.TestCase):
    def test_eta_payload_estimates_from_running_worker_percent_and_elapsed_time(self) -> None:
        payload = eta_payload(
            {
                "rows": [
                    {
                        "worker_id": "local",
                        "worker_label": "Local pipeline",
                        "job_id": "launch-1",
                        "stage": "encode",
                        "source": "Movie.mkv",
                        "status_state": "running",
                        "percent": 25.0,
                        "elapsed_seconds": 300,
                        "updated_at": "2026-05-08T12:05:00-04:00",
                    }
                ]
            }
        )

        self.assertEqual(payload["schema_version"], ETA_SCHEMA_VERSION)
        self.assertEqual(payload["status"], "loaded")
        self.assertEqual(payload["estimated_count"], 1)
        self.assertEqual(payload["unavailable_count"], 0)
        self.assertTrue(payload["read_only"])
        row = payload["rows"][0]
        self.assertEqual(row["job_id"], "launch-1")
        self.assertEqual(row["eta_seconds"], 900)
        self.assertEqual(row["confidence"], "medium")
        self.assertIn("desktop_worker_progress.v1", row["basis"])
        self.assertEqual(row["unavailable_reason"], "")
        self.assertIn("Mutation guardrail", "\n".join(payload["summary_lines"]))

    def test_eta_payload_reports_unavailable_for_active_worker_without_percent(self) -> None:
        payload = eta_payload(
            {
                "rows": [
                    {
                        "worker_id": "local",
                        "job_id": "launch-1",
                        "status_state": "running",
                        "elapsed_seconds": 120,
                    }
                ]
            }
        )

        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["estimated_count"], 0)
        self.assertEqual(payload["unavailable_count"], 1)
        self.assertIsNone(payload["rows"][0]["eta_seconds"])
        self.assertIn("usable percent", payload["rows"][0]["unavailable_reason"])

    def test_eta_payload_does_not_fake_rows_when_idle(self) -> None:
        payload = eta_payload({"rows": []})

        self.assertEqual(payload["schema_version"], ETA_SCHEMA_VERSION)
        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["rows"], [])
        self.assertEqual(payload["row_count"], 0)

    def test_eta_payload_estimates_publish_copy_from_progress_bytes(self) -> None:
        payload = eta_payload(
            {"rows": []},
            progress={
                "CurrentStage": "push",
                "CurrentFileDisplay": "Movie.mkv",
                "PushState": "copying",
                "CopyBytesCopied": 536870912,
                "CopyTotalBytes": 1073741824,
                "CopyStartedAt": "2026-06-04T12:00:00+00:00",
                "CopyUpdatedAt": "2026-06-04T12:01:00+00:00",
            },
            now=datetime(2026, 6, 4, 12, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(payload["status"], "loaded")
        self.assertEqual(payload["estimated_count"], 1)
        row = payload["rows"][0]
        self.assertEqual(row["worker_id"], "publish_copy")
        self.assertEqual(row["worker_label"], "Push file")
        self.assertEqual(row["eta_seconds"], 60)
        self.assertEqual(row["bytes_remaining"], 536870912)
        self.assertEqual(row["bytes_per_second"], 8947849)
        self.assertEqual(row["percent"], 50.0)
        self.assertIn("publish-copy bytes", row["basis"])

    def test_eta_payload_reports_publish_copy_unavailable_without_start_time(self) -> None:
        payload = eta_payload(
            {"rows": []},
            progress={
                "CurrentStage": "push",
                "PushState": "copying",
                "CopyBytesCopied": 1,
                "CopyTotalBytes": 100,
                "CopyUpdatedAt": "2026-06-04T12:01:00+00:00",
            },
        )

        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["estimated_count"], 0)
        row = payload["rows"][0]
        self.assertIsNone(row["eta_seconds"])
        self.assertIn("start and update timestamps", row["unavailable_reason"])

    def test_eta_payload_prefers_session_average_throughput_once_files_complete(self) -> None:
        payload = eta_payload(
            {"rows": []},
            progress={
                "CurrentStage": "push",
                "CurrentFileDisplay": "Movie.mkv",
                "PushState": "copying",
                "CopyBytesCopied": 536870912,
                "CopyTotalBytes": 1073741824,
                "CopyStartedAt": "2026-06-04T12:00:00+00:00",
                "CopyUpdatedAt": "2026-06-04T12:01:00+00:00",
                "CopySessionBytesPerSecond": 50000000,
                "CopySessionFilesCompleted": 3,
            },
            now=datetime(2026, 6, 4, 12, 1, tzinfo=timezone.utc),
        )

        row = payload["rows"][0]
        # Rate and ETA come from the learned session average (50 MB/s), not the
        # in-progress file's own partial bytes/elapsed (which would be ~8.9 MB/s).
        self.assertEqual(row["bytes_per_second"], 50000000)
        self.assertEqual(row["bytes_remaining"], 536870912)
        self.assertEqual(row["eta_seconds"], round(536870912 / 50000000))
        self.assertIn("average publish-copy throughput", row["basis"])
        self.assertIn("3 completed files", row["basis"])

    def test_eta_payload_session_average_estimates_before_current_file_has_elapsed(self) -> None:
        # A freshly started push (no usable start/update timestamps yet) still
        # gets a stable estimate from the learned session average.
        payload = eta_payload(
            {"rows": []},
            progress={
                "CurrentStage": "push",
                "CurrentFileDisplay": "Movie.mkv",
                "PushState": "copying",
                "CopyBytesCopied": 1048576,
                "CopyTotalBytes": 1073741824,
                "CopySessionBytesPerSecond": 50000000,
                "CopySessionFilesCompleted": 2,
            },
        )

        self.assertEqual(payload["status"], "loaded")
        row = payload["rows"][0]
        self.assertEqual(row["bytes_per_second"], 50000000)
        self.assertEqual(row["eta_seconds"], round((1073741824 - 1048576) / 50000000))
        self.assertEqual(row["unavailable_reason"], "")

    def test_eta_payload_ignores_session_average_for_first_file_of_run(self) -> None:
        # Guinea-pig file: no completed files yet, so the per-file partial
        # measurement is used unchanged.
        payload = eta_payload(
            {"rows": []},
            progress={
                "CurrentStage": "push",
                "CurrentFileDisplay": "Movie.mkv",
                "PushState": "copying",
                "CopyBytesCopied": 536870912,
                "CopyTotalBytes": 1073741824,
                "CopyStartedAt": "2026-06-04T12:00:00+00:00",
                "CopyUpdatedAt": "2026-06-04T12:01:00+00:00",
                "CopySessionBytesPerSecond": None,
                "CopySessionFilesCompleted": 0,
            },
            now=datetime(2026, 6, 4, 12, 1, tzinfo=timezone.utc),
        )

        row = payload["rows"][0]
        self.assertEqual(row["bytes_per_second"], 8947849)
        self.assertEqual(row["eta_seconds"], 60)
        self.assertIn("publish-copy bytes", row["basis"])


if __name__ == "__main__":
    unittest.main()
