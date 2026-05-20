from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_app_schedule import (
    block_label,
    default_schedule_grid,
    evaluate_schedule,
    format_schedule_datetime,
    next_scheduled_stop,
    normalize_schedule_grid,
)


class AppScheduleHelperTests(unittest.TestCase):
    def test_normalize_schedule_grid_accepts_case_insensitive_days_and_pads(self) -> None:
        grid = normalize_schedule_grid({"monday": [1, 0, "yes"], "Friday": [True] * 55})

        self.assertEqual(len(grid["Monday"]), 48)
        self.assertEqual(grid["Monday"][:4], [True, False, True, False])
        self.assertEqual(len(grid["Friday"]), 48)
        self.assertTrue(all(grid["Friday"]))
        self.assertFalse(any(grid["Tuesday"]))

    def test_block_label_and_schedule_datetime_formatting(self) -> None:
        self.assertEqual(block_label(0), "12:00 AM")
        self.assertEqual(block_label(25), "12:30 PM")
        self.assertEqual(format_schedule_datetime(datetime(2026, 5, 4, 10, 30)), "Monday 10:30 AM")
        self.assertEqual(format_schedule_datetime(None), "")

    def test_evaluate_schedule_disabled_allows_now(self) -> None:
        result = evaluate_schedule(False, default_schedule_grid(), now=datetime(2026, 5, 4, 10, 15))

        self.assertFalse(result["enabled"])
        self.assertTrue(result["allowed_now"])
        self.assertEqual(result["status_text"], "Schedule: Off")

    def test_evaluate_schedule_allowed_window_finds_current_end(self) -> None:
        grid = default_schedule_grid()
        grid["Monday"][20] = True  # 10:00
        grid["Monday"][21] = True  # 10:30

        result = evaluate_schedule(True, grid, now=datetime(2026, 5, 4, 10, 15))

        self.assertTrue(result["allowed_now"])
        self.assertEqual(result["current_window_end"], datetime(2026, 5, 4, 11, 0))
        self.assertEqual(result["next_allowed_start"], datetime(2026, 5, 4, 10, 0))
        self.assertIn("Monday 11:00 AM", result["status_text"])
        self.assertEqual(next_scheduled_stop(True, grid, now=datetime(2026, 5, 4, 10, 15)), datetime(2026, 5, 4, 11, 0))

    def test_evaluate_schedule_waiting_finds_next_allowed_window(self) -> None:
        grid = default_schedule_grid()
        grid["Monday"][22] = True  # 11:00
        grid["Monday"][23] = True  # 11:30

        result = evaluate_schedule(True, grid, now=datetime(2026, 5, 4, 10, 15))

        self.assertFalse(result["allowed_now"])
        self.assertEqual(result["next_allowed_start"], datetime(2026, 5, 4, 11, 0))
        self.assertEqual(result["next_allowed_end"], datetime(2026, 5, 4, 12, 0))
        self.assertIn("next allowed Monday 11:00 AM", result["status_text"])
        self.assertEqual(next_scheduled_stop(True, grid, now=datetime(2026, 5, 4, 10, 15)), datetime(2026, 5, 4, 12, 0))


if __name__ == "__main__":
    unittest.main()
