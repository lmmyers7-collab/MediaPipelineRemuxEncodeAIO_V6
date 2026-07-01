from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.processes.rerun_policy import (
    CSV_RERUN_MODE_ERROR,
    CSV_RERUN_PATH_ERROR,
    CSV_RERUN_PLAN_MODE_ERROR,
    normalize_rerun_csv_path,
    normalize_rerun_mode,
    rerun_lifecycle_errors,
    rerun_lifecycle_from_request,
    rerun_bool_from_request,
    rerun_csv_path_missing_result,
    rerun_csv_path_from_request,
    rerun_dry_run_from_request,
    rerun_mode_error_result,
    rerun_modes_are_supported,
    rerun_modes_from_request,
    rerun_plan_flags_are_supported,
    rerun_plan_mode_error_result,
    rerun_plan_only_from_request,
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
        self.assertIn("lifecycle", CSV_RERUN_MODE_ERROR)

    def test_lifecycle_defaults_aliases_and_confirmations_are_explicit(self) -> None:
        lifecycle = rerun_lifecycle_from_request({})
        self.assertEqual(lifecycle.execution_mode, "one_at_a_time")
        self.assertEqual(lifecycle.destination_mode, "review_workspace")
        self.assertEqual(lifecycle.original_policy, "keep")
        self.assertEqual(lifecycle.window_size, 1)
        self.assertEqual(rerun_lifecycle_errors(lifecycle), [])

        alias = rerun_lifecycle_from_request({"return_mode": "replace_original"})
        self.assertEqual(alias.destination_mode, "publish_replace_final")
        self.assertIn("confirm_replace_final=true", "\n".join(rerun_lifecycle_errors(alias)))

        confirmed = rerun_lifecycle_from_request({
            "destination_mode": "publish_replace_final",
            "confirm_replace_final": True,
            "original_policy": "hold_then_delete_after_publish",
            "confirm_original_policy": True,
            "confirm_delete_original": True,
        })
        self.assertEqual(rerun_lifecycle_errors(confirmed), [])

    def test_success_message_and_payload_are_stable(self) -> None:
        csv_path = Path("C:/queue/rerun.csv")
        payload = rerun_start_success_data(
            csv_path=csv_path,
            dry_run=True,
            plan_only=False,
            stage_mode="copy",
            original_mode="keep",
            return_mode="park",
            pid=24682,
            launch_logs="stdout: rerun.stdout.log",
        )

        self.assertEqual(rerun_run_label(True), "dry run")
        self.assertEqual(rerun_run_label(False), "run")
        self.assertEqual(rerun_run_label(False, True), "plan-only check")
        self.assertEqual(rerun_start_success_message(24682, True), "Started CSV rerun dry run via PID 24682.")
        self.assertEqual(rerun_start_success_message(24682, False), "Started CSV rerun run via PID 24682.")
        self.assertEqual(
            rerun_start_success_message(24682, False, True),
            "Started CSV rerun plan-only check via PID 24682.",
        )
        self.assertEqual(payload["csv_path"], str(csv_path))
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["plan_only"])
        self.assertEqual(payload["stage_mode"], "copy")
        self.assertEqual(payload["original_mode"], "keep")
        self.assertEqual(payload["return_mode"], "park")
        self.assertEqual(payload["execution_mode"], "one_at_a_time")
        self.assertEqual(payload["destination_mode"], "review_workspace")
        self.assertEqual(payload["original_policy"], "keep")
        self.assertEqual(payload["pid"], 24682)
        self.assertEqual(payload["logs"], "stdout: rerun.stdout.log")

    def test_command_result_helpers_preserve_rerun_start_contract(self) -> None:
        csv_path = Path("C:/queue/rerun.csv")
        missing = rerun_csv_path_missing_result()
        mode = rerun_mode_error_result()
        plan_mode = rerun_plan_mode_error_result()
        active = rerun_start_active_work_result("CSV rerun start blocked by active work.")
        failure = rerun_start_exception_result(RuntimeError("rerun spawn failed"))
        success = rerun_start_success_result(
            csv_path=csv_path,
            dry_run=False,
            plan_only=True,
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
        self.assertEqual(plan_mode.errors, [CSV_RERUN_PLAN_MODE_ERROR])
        self.assertEqual(active.refresh_hint, "snapshot")
        self.assertEqual(failure.errors, ["rerun spawn failed"])
        self.assertTrue(success.ok)
        self.assertEqual(success.message, "Started CSV rerun plan-only check via PID 24682.")
        self.assertEqual(success.data["csv_path"], str(csv_path))
        self.assertTrue(success.data["plan_only"])

    def test_plan_flags_are_strict_booleans_and_mutually_exclusive(self) -> None:
        self.assertTrue(rerun_bool_from_request({"plan_only": True}, "plan_only"))
        self.assertFalse(rerun_bool_from_request({"plan_only": "true"}, "plan_only"))
        self.assertTrue(rerun_dry_run_from_request({"dry_run": True}))
        self.assertTrue(rerun_plan_only_from_request({"plan_only": True}))
        self.assertTrue(rerun_plan_flags_are_supported(False, False))
        self.assertTrue(rerun_plan_flags_are_supported(True, False))
        self.assertTrue(rerun_plan_flags_are_supported(False, True))
        self.assertFalse(rerun_plan_flags_are_supported(True, True))


if __name__ == "__main__":
    unittest.main()
