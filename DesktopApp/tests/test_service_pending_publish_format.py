from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_pending_publish import PendingPublishServiceMixin
from mediapipeline_desktop_app.service_pending_publish_format import (
    format_bytes_compact,
    format_pending_datetime_text,
    format_pending_timestamp,
    int_or_none,
    parse_pending_datetime,
    pending_age_text,
)


class PendingPublishFormatTests(unittest.TestCase):
    def test_format_bytes_compact_uses_existing_units(self) -> None:
        self.assertEqual(format_bytes_compact(0), "0 B")
        self.assertEqual(format_bytes_compact(1536), "1.5 KB")
        self.assertEqual(format_bytes_compact(2 * 1024**2), "2.0 MB")
        self.assertEqual(format_bytes_compact(3 * 1024**3), "3.00 GB")

    def test_format_pending_timestamp_handles_zero_and_epoch(self) -> None:
        self.assertEqual(format_pending_timestamp(0), "")
        self.assertEqual(format_pending_timestamp(1), time.strftime("%Y-%m-%d %H:%M", time.localtime(1)))

    def test_parse_pending_datetime_accepts_iso_and_legacy_formats(self) -> None:
        self.assertIsNotNone(parse_pending_datetime("2026-05-08T12:30:00-04:00"))
        self.assertIsNotNone(parse_pending_datetime("05/08/2026 12:30:00"))
        self.assertIsNotNone(parse_pending_datetime("05/08/2026 12:30:00 PM"))
        self.assertIsNone(parse_pending_datetime("not a date"))

    def test_datetime_text_and_age_text_preserve_existing_fallbacks(self) -> None:
        self.assertEqual(format_pending_datetime_text("2026-05-08T12:30:00-04:00"), "2026-05-08 12:30")
        self.assertEqual(format_pending_datetime_text("2026-05-08T12:30:00Z-extra"), "2026-05-08 12:30")
        self.assertEqual(pending_age_text("not a date"), "")

    def test_service_wrapper_methods_delegate_to_format_helper(self) -> None:
        service = PendingPublishServiceMixin()

        self.assertEqual(service._int_or_none("12"), 12)
        self.assertIsNone(service._int_or_none("bad"))
        self.assertEqual(service._format_bytes_compact(1024), "1.0 KB")
        self.assertEqual(service._format_pending_datetime_text("2026-05-08T12:30:00"), "2026-05-08 12:30")
        self.assertIsNotNone(service._parse_pending_datetime("2026-05-08T12:30:00"))


if __name__ == "__main__":
    unittest.main()
