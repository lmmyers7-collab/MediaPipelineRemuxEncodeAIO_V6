from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.status.eta import ETA_SCHEMA_VERSION, eta_payload


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


if __name__ == "__main__":
    unittest.main()
