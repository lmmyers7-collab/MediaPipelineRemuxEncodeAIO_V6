from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.completed.validation_state import validation_state_for_completed_row, validation_state_payload


class CompletedValidationStateTests(unittest.TestCase):
    def test_existing_output_without_probe_hash_or_playback_is_validation_needed(self) -> None:
        row = {
            "row_key": "row-1",
            "source_path": "C:/Source/Movie.mkv",
            "output_path": "C:/Out/Movie.mkv",
            "output_exists": True,
            "output_health": "ok",
            "output_size_bytes": 2048,
            "output_size_text": "2 KB",
        }

        validation = validation_state_for_completed_row(row)

        self.assertEqual(validation["schema_version"], "desktop_validation_state.v1")
        self.assertEqual(validation["validation_status_state"], "validation-needed")
        self.assertIsNone(validation["probe_ok"])
        self.assertIsNone(validation["hash_ok"])
        self.assertTrue(validation["playback_required"])
        self.assertIn("ffprobe output proof not reported", validation["unavailable_reasons"])
        self.assertIn("output hash proof not reported", validation["unavailable_reasons"])

    def test_missing_or_failed_output_is_blocked(self) -> None:
        row = {
            "row_key": "row-2",
            "output_path": "C:/Out/Missing.mkv",
            "output_exists": False,
            "output_health": "completed metadata without media",
        }

        validation = validation_state_for_completed_row(row)

        self.assertEqual(validation["validation_status_state"], "blocked")
        self.assertEqual(validation["failure_reason"], "Completed row points at a missing output.")
        self.assertFalse(validation["playback_required"])

    def test_future_backend_probe_hash_success_can_complete_contract(self) -> None:
        row = {
            "row_key": "row-3",
            "output_path": "C:/Out/Movie.mkv",
            "output_exists": True,
            "output_health": "ok",
            "output_size_bytes": 4096,
            "validation_probe_ok": True,
            "validation_hash_ok": True,
            "validation_playback_required": False,
        }

        validation = validation_state_for_completed_row(row)

        self.assertEqual(validation["validation_status_state"], "completed")
        self.assertTrue(validation["probe_ok"])
        self.assertTrue(validation["hash_ok"])
        self.assertFalse(validation["playback_required"])
        self.assertEqual(validation["unavailable_reasons"], [])

    def test_payload_summarizes_blocked_and_validation_needed_rows(self) -> None:
        payload = validation_state_payload(
            [
                {
                    "output_path": "C:/Out/NeedsValidation.mkv",
                    "output_exists": True,
                    "output_health": "ok",
                    "output_size_bytes": 2048,
                },
                {
                    "output_path": "C:/Out/Missing.mkv",
                    "output_exists": False,
                    "output_health": "completed metadata without media",
                },
            ],
            source="completed_manifest",
        )

        self.assertEqual(payload["schema_version"], "desktop_validation_state.v1")
        self.assertEqual(payload["status_state"], "blocked")
        self.assertEqual(payload["row_count"], 2)
        self.assertEqual(payload["blocked_count"], 1)
        self.assertEqual(payload["validation_needed_count"], 1)
        self.assertEqual(payload["playback_required_count"], 1)
        self.assertTrue(payload["read_only"])


if __name__ == "__main__":
    unittest.main()
