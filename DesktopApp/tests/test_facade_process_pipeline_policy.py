from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application.facade_process_pipeline_policy import (
    PIPELINE_EXTRA_ARGS_ERROR,
    PIPELINE_SLEEP_SECONDS_ERROR,
    PIPELINE_START_MODE_ERROR,
    is_supported_pipeline_start_mode,
    normalize_pipeline_extra_args,
    normalize_pipeline_start_mode,
    parse_pipeline_sleep_seconds,
    pipeline_extra_args_error,
    pipeline_start_active_work_result,
    pipeline_start_exception_result,
    pipeline_start_extra_args_error_result,
    pipeline_start_schedule_gate_result,
    pipeline_start_sleep_error_result,
    pipeline_start_success_data,
    pipeline_start_success_message,
    pipeline_start_success_result,
    pipeline_start_unsupported_mode_result,
)


class PipelineLaunchPolicyTests(unittest.TestCase):
    def test_mode_normalization_and_allowlist_match_launch_contract(self) -> None:
        self.assertEqual(normalize_pipeline_start_mode(None), "once")
        self.assertEqual(normalize_pipeline_start_mode(" Validate "), "validate")
        self.assertTrue(is_supported_pipeline_start_mode("continuous"))
        self.assertTrue(is_supported_pipeline_start_mode("drain_pending_pushes"))
        self.assertFalse(is_supported_pipeline_start_mode("unsupported"))
        self.assertIn("drain_pending_pushes", PIPELINE_START_MODE_ERROR)

    def test_sleep_seconds_parser_preserves_default_and_minimum_behavior(self) -> None:
        self.assertEqual(parse_pipeline_sleep_seconds(None), (30, None))
        self.assertEqual(parse_pipeline_sleep_seconds(""), (30, None))
        self.assertEqual(parse_pipeline_sleep_seconds(0), (30, None))
        self.assertEqual(parse_pipeline_sleep_seconds("-5"), (1, None))
        self.assertEqual(parse_pipeline_sleep_seconds("12"), (12, None))
        self.assertEqual(parse_pipeline_sleep_seconds("bad"), (None, PIPELINE_SLEEP_SECONDS_ERROR))

    def test_extra_args_require_explicit_allowance(self) -> None:
        self.assertEqual(normalize_pipeline_extra_args("  -WhatIf  "), "-WhatIf")
        self.assertIsNone(pipeline_extra_args_error("", False))
        self.assertIsNone(pipeline_extra_args_error("-WhatIf", True))
        self.assertEqual(pipeline_extra_args_error("-WhatIf", False), PIPELINE_EXTRA_ARGS_ERROR)

    def test_success_message_and_payload_are_stable(self) -> None:
        schedule = {"mode": "validate"}
        payload = pipeline_start_success_data(
            actual_mode="validate",
            requested_mode="once",
            schedule_data=schedule,
            pid=24680,
            launch_prep_messages=["runtime ready"],
            launch_logs="stdout: run.stdout.log",
        )

        self.assertEqual(pipeline_start_success_message("validate", 24680), "Started pipeline (validate) via PID 24680.")
        self.assertEqual(payload["mode"], "validate")
        self.assertEqual(payload["requested_mode"], "once")
        self.assertIs(payload["schedule"], schedule)
        self.assertEqual(payload["pid"], 24680)
        self.assertEqual(payload["launch_prep"], ["runtime ready"])
        self.assertEqual(payload["logs"], "stdout: run.stdout.log")

    def test_command_result_helpers_preserve_pipeline_start_contract(self) -> None:
        unsupported = pipeline_start_unsupported_mode_result()
        sleep = pipeline_start_sleep_error_result()
        extra_args = pipeline_start_extra_args_error_result()
        schedule = pipeline_start_schedule_gate_result(
            {"ok": False, "message": "outside schedule", "severity": "warning", "data": {"mode": "once"}}
        )
        active = pipeline_start_active_work_result("Pipeline start blocked by active work.")
        failure = pipeline_start_exception_result(RuntimeError("spawn failed"))
        success = pipeline_start_success_result(
            actual_mode="continuous",
            requested_mode="once",
            schedule_data={"override": "run_once"},
            pid=24680,
            launch_prep_messages=["runtime ready"],
            launch_logs="stdout: run.stdout.log",
        )

        self.assertEqual(unsupported.command, "pipeline.start")
        self.assertFalse(unsupported.ok)
        self.assertEqual(unsupported.errors, [PIPELINE_START_MODE_ERROR])
        self.assertEqual(sleep.errors, [PIPELINE_SLEEP_SECONDS_ERROR])
        self.assertEqual(extra_args.errors, [PIPELINE_EXTRA_ARGS_ERROR])
        self.assertEqual(schedule.refresh_hint, "schedule")
        self.assertEqual(schedule.data["schedule"], {"mode": "once"})
        self.assertEqual(active.refresh_hint, "snapshot")
        self.assertEqual(failure.errors, ["spawn failed"])
        self.assertTrue(success.ok)
        self.assertEqual(success.message, "Started pipeline (continuous) via PID 24680.")
        self.assertEqual(success.data["requested_mode"], "once")


if __name__ == "__main__":
    unittest.main()
