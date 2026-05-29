from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.status.service import StatusServiceMixin
from app.status.progress import (
    datetime_is_stale,
    format_audit_progress,
    is_audit_progress_stale,
    is_progress_stale,
    parse_progress_datetime,
)


class StatusProgressHelperTests(unittest.TestCase):
    def test_parse_progress_datetime_accepts_iso_z_space_and_t_formats(self) -> None:
        self.assertIsNotNone(parse_progress_datetime("2026-05-08T12:00:00Z"))
        self.assertIsNotNone(parse_progress_datetime("2026-05-08 12:00:00"))
        self.assertIsNotNone(parse_progress_datetime("2026-05-08T12:00:00"))
        self.assertIsNone(parse_progress_datetime("not a date"))

    def test_datetime_is_stale_uses_timestamp_age(self) -> None:
        old = (datetime.now() - timedelta(seconds=30)).isoformat(timespec="seconds")
        fresh = datetime.now().isoformat(timespec="seconds")

        self.assertTrue(datetime_is_stale(old, stale_after_seconds=5))
        self.assertFalse(datetime_is_stale(fresh, stale_after_seconds=5))
        self.assertFalse(datetime_is_stale("not a date", stale_after_seconds=5))

    def test_is_progress_stale_ignores_idle_and_detects_active_stale(self) -> None:
        old = (datetime.now() - timedelta(seconds=30)).isoformat(timespec="seconds")

        self.assertFalse(is_progress_stale({"CurrentStage": "idle", "LastUpdate": old}))
        self.assertTrue(is_progress_stale({"CurrentStage": "encode", "LastUpdate": old}, stale_after_seconds=5))

    def test_is_audit_progress_stale_ignores_completed_and_detects_scanning_stale(self) -> None:
        old = (datetime.now() - timedelta(seconds=30)).isoformat(timespec="seconds")
        fresh = datetime.now().isoformat(timespec="seconds")

        self.assertFalse(is_audit_progress_stale({"status": "completed", "completed": True, "last_update": old}))
        self.assertFalse(is_audit_progress_stale({"status": "scanning", "completed": False, "failed": False, "last_update": fresh}))
        self.assertTrue(is_audit_progress_stale({"status": "scanning", "completed": False, "failed": False, "last_update": old}, stale_after_seconds=5))

    def test_format_audit_progress_reports_file_percent_stale_and_write_failures(self) -> None:
        old = (datetime.now() - timedelta(seconds=30)).isoformat(timespec="seconds")

        text = format_audit_progress(
            {
                "status": "scanning",
                "completed": False,
                "failed": False,
                "last_update": old,
                "processed_files": 2,
                "total_files": 4,
                "percent_complete": 50,
                "current_file": r"C:\Media\Movie.mkv",
                "progress_persistence_healthy": False,
                "progress_write_failures": 3,
            }
        )

        self.assertEqual(text, "Audit progress: STALE scanning | 2 / 4 | 50% | Movie.mkv | progress writes failing (3)")

    def test_format_audit_progress_reports_completed_and_empty_states(self) -> None:
        self.assertEqual(format_audit_progress(None), "Audit progress: No audit progress file found.")
        self.assertEqual(
            format_audit_progress({"status": "scanning", "completed": True, "failed": False}),
            "Audit progress: completed",
        )

    def test_service_mixin_preserves_progress_wrapper_methods(self) -> None:
        service = StatusServiceMixin()
        old = (datetime.now() - timedelta(seconds=30)).isoformat(timespec="seconds")

        self.assertIsNotNone(service._parse_progress_datetime("2026-05-08T12:00:00Z"))
        self.assertTrue(service._datetime_is_stale(old, 5))
        self.assertTrue(service.is_progress_stale({"CurrentStage": "encode", "LastUpdate": old}, stale_after_seconds=5))
        self.assertTrue(service.is_audit_progress_stale({"status": "scanning", "last_update": old}, stale_after_seconds=5))


if __name__ == "__main__":
    unittest.main()
