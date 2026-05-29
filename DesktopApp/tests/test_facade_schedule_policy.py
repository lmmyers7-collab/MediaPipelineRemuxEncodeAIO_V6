from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schedule.policy import (
    schedule_block_label,
    schedule_bool_values,
    schedule_day_summaries,
    schedule_day_windows,
    schedule_grid_rows,
)


class ScheduleFacadePolicyTests(unittest.TestCase):
    def test_schedule_bool_values_and_grid_rows_preserve_day_order_and_bound_blocks(self) -> None:
        values = [1, "", "yes", None] + [True] * 60
        grid = {"Monday": values, 5: (False, True)}

        self.assertEqual(schedule_bool_values(values[:4]), [True, False, True, False])
        rows = schedule_grid_rows(grid)

        self.assertEqual(list(rows.keys()), ["Monday", "5"])
        self.assertEqual(len(rows["Monday"]), 48)
        self.assertEqual(rows["Monday"][:4], [True, False, True, False])
        self.assertEqual(rows["5"], [False, True])

    def test_schedule_block_label_uses_formatter_with_existing_fallbacks(self) -> None:
        self.assertEqual(schedule_block_label(18, lambda index: f"block-{index}"), "block-18")
        self.assertEqual(schedule_block_label(48, lambda index: f"block-{index}"), "12:00 AM")
        self.assertEqual(schedule_block_label(19, lambda _index: (_ for _ in ()).throw(ValueError("bad"))), "09:30")

    def test_schedule_day_windows_group_contiguous_allowed_blocks(self) -> None:
        values = [False] * 48
        values[18:20] = [True, True]
        values[22] = True

        windows = schedule_day_windows(values, formatter=lambda index: f"B{index}")

        self.assertEqual(windows, ["B18 - B20", "B22 - B23"])

    def test_schedule_day_summaries_match_workspace_contract(self) -> None:
        all_day = [True] * 48
        empty = [False] * 48
        split = [False] * 48
        split[18:20] = [True, True]

        summaries = schedule_day_summaries(
            {"Monday": all_day, "Tuesday": empty, "Wednesday": split},
            formatter=lambda index: "12:00 AM" if index == 48 else f"B{index}",
        )

        self.assertEqual(summaries[0]["allowed_blocks"], 48)
        self.assertEqual(summaries[0]["allowed_hours"], 24)
        self.assertEqual(summaries[0]["windows_text"], "All day")
        self.assertEqual(summaries[1]["windows"], [])
        self.assertEqual(summaries[1]["windows_text"], "None")
        self.assertEqual(summaries[2]["windows_text"], "B18 - B20")


if __name__ == "__main__":
    unittest.main()
