from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.processes.control_policy import (
    PIPELINE_CONTROL_ACTION_ERROR,
    is_supported_pipeline_control_action,
    normalize_pipeline_control_action,
    pipeline_control_command,
    pipeline_control_success_data,
)


class ProcessControlPolicyTests(unittest.TestCase):
    def test_action_normalization_matches_existing_api_behavior(self) -> None:
        self.assertEqual(normalize_pipeline_control_action(" Pause "), "pause")
        self.assertEqual(normalize_pipeline_control_action("stop-now"), "stop_now")
        self.assertEqual(normalize_pipeline_control_action(None), "")

    def test_action_allowlist_and_command_names_are_stable(self) -> None:
        self.assertTrue(is_supported_pipeline_control_action("pause"))
        self.assertTrue(is_supported_pipeline_control_action("stop"))
        self.assertTrue(is_supported_pipeline_control_action("rescan"))
        self.assertFalse(is_supported_pipeline_control_action("stop_now"))
        self.assertEqual(pipeline_control_command("pause"), "pipeline.control.pause")
        self.assertEqual(pipeline_control_command(""), "pipeline.control.unknown")
        self.assertIn("pause", PIPELINE_CONTROL_ACTION_ERROR)

    def test_success_payload_stringifies_flag_path(self) -> None:
        payload = pipeline_control_success_data("stop", Path("C:/state/pipeline_stop.flag"))
        kill_payload = pipeline_control_success_data("kill", None, {"kill_report": ["PID 1234"]})

        self.assertEqual(payload["action"], "stop")
        self.assertEqual(payload["flag_path"], str(Path("C:/state/pipeline_stop.flag")))
        self.assertEqual(pipeline_control_success_data("rescan", None)["flag_path"], "")
        self.assertEqual(kill_payload["force_stop_scope"]["job_kinds"], ["pipeline", "audit", "rerun_csv"])
        self.assertIn("pipeline, audit, and CSV rerun", kill_payload["force_stop_scope"]["scope_label"])
        self.assertEqual(kill_payload["kill_report"], ["PID 1234"])


if __name__ == "__main__":
    unittest.main()
