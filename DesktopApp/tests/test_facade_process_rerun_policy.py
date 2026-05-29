from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.processes.rerun_policy import (
    CSV_RERUN_MODE_ERROR,
    CSV_RERUN_PATH_ERROR,
    normalize_rerun_csv_path,
    normalize_rerun_mode,
    rerun_csv_path_missing_result,
    rerun_mode_error_result,
    rerun_csv_path_from_request,
    rerun_modes_are_supported,
    rerun_modes_from_request,
    rerun_run_label,
    rerun_start_active_work_result,
    rerun_start_exception_result,
    rerun_start_success_data,
    rerun_start_success_message,
    rerun_start_success_result,
)


class RerunLaunchPolicyTests(unittest.TestCase):
    def test_csv_path_is_trimmed_and_missing_path_is_explicit(self) -> None:
        self.assertEqual(normalize_rerun_csv_path("  C:/queue/rerun.csv  "), "C:/queue/rerun.csv")
        self.assertEqual(normalize_rerun_csv_path(None), "")
        self.assertEqual(rerun_csv_path_from_request({"csv_path": "  C:/queue/rerun.csv  "}), Path("C:/queue/rerun.csv"))
        self.assertIsNone(rerun_csv_path_from_request({}))
        self.assertEqual(CSV_RERUN_PATH_ERROR, "CSV path is required.")

    def test_mode_normalization_preserves_copy_keep_park_contract(self) -> None:
        self.assertEqual(normalize_rerun_mode(" COPY ", "copy"), "copy")
        self.assertEqual(rerun_modes_from_request({}), ("copy", "keep", "park"))
        self.assertEqual(
            rerun_modes_from_request({"stage_mode": "Copy", "original_mode": "Keep", "return_mode": "Park"}),
            ("copy", "keep", "park"),
        )
        self.assertTrue(rerun_modes_are_supported("copy", "keep", "park"))
        self.assertFalse(rerun_modes_are_supported("move", "keep", "park"))
        self.assertFalse(rerun_modes_are_supported("copy", "delete", "park"))
        self.assertFalse(rerun_modes_are_supported("copy", "keep", "move"))
        self.assertIn("copy", CSV_RERUN_MODE_ERROR)

    def test_success_message_and_payload_are_stable(self) -> None:
        csv_path = Path("C:/queue/rerun.csv")
        payload = rerun_start_success_data(
            csv_path=csv_path,
            dry_run=True,
            stage_mode="copy",
            original_mode="keep",
            return_mode="park",
            pid=24682,
            launch_logs="stdout: rerun.stdout.log",
        )

        self.assertEqual(rerun_run_label(True), "dry run")
        self.assertEqual(rerun_run_label(False), "run")
        self.assertEqual(rerun_start_success_message(24682, True), "Started CSV rerun dry run via PID 24682.")
        self.assertEqual(rerun_start_success_message(24682, False), "Started CSV rerun run via PID 24682.")
        self.assertEqual(payload["csv_path"], str(csv_path))
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["stage_mode"], "copy")
        self.assertEqual(payload["original_mode"], "keep")
        self.assertEqual(payload["return_mode"], "park")
        self.assertEqual(payload["pid"], 24682)
        self.assertEqual(payload["logs"], "stdout: rerun.stdout.log")

    def test_command_result_helpers_preserve_rerun_start_contract(self) -> None:
        csv_path = Path("C:/queue/rerun.csv")
        missing = rerun_csv_path_missing_result()
        mode = rerun_mode_error_result()
        active = rerun_start_active_work_result("CSV rerun start blocked by active work.")
        failure = rerun_start_exception_result(RuntimeError("rerun spawn failed"))
        success = rerun_start_success_result(
            csv_path=csv_path,
            dry_run=False,
            stage_mode="copy",
            original_mode="keep",
            return_mode="park",
            pid=24682,
            launch_logs="stdout: rerun.stdout.log",
        )

        self.assertEqual(missing.command, "rerun.start")
        self.assertFalse(missing.ok)
        self.assertEqual(missing.errors, [CSV_RERUN_PATH_ERROR])
        self.assertEqual(mode.errors, [CSV_RERUN_MODE_ERROR])
        self.assertEqual(active.refresh_hint, "snapshot")
        self.assertEqual(failure.errors, ["rerun spawn failed"])
        self.assertTrue(success.ok)
        self.assertEqual(success.message, "Started CSV rerun run via PID 24682.")
        self.assertEqual(success.data["csv_path"], str(csv_path))


if __name__ == "__main__":
    unittest.main()
