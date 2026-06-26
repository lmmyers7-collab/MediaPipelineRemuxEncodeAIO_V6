from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.processes.guard_policy import (
    NO_ACTIVE_WORK_REASON,
    SNAPSHOT_UNAVAILABLE_WARNING,
    UNKNOWN_CLOSE_READINESS_REASON,
    audit_progress_indicates_active_work,
    close_readiness_fields,
    pipeline_progress_indicates_active_work,
)


class ProcessGuardPolicyTests(unittest.TestCase):
    def test_close_readiness_allows_known_idle_terminal_states(self) -> None:
        for state in ("idle", "completed", "failed"):
            fields = close_readiness_fields(state=state, snapshot_available=True, block_message="")
            self.assertTrue(fields["safe_to_close"])
            self.assertFalse(fields["active_work"])
            self.assertEqual(fields["reason"], NO_ACTIVE_WORK_REASON)
            self.assertEqual(fields["continuous_watcher"], {})
            self.assertEqual(fields["warnings"], [])

    def test_close_readiness_preserves_watcher_state_for_ui_contract(self) -> None:
        fields = close_readiness_fields(
            state="completed",
            snapshot_available=True,
            block_message="Schedule watcher armed.",
            continuous_watcher={"status": "armed", "pid": 24680},
        )

        self.assertFalse(fields["safe_to_close"])
        self.assertEqual(fields["continuous_watcher"]["status"], "armed")
        self.assertEqual(fields["continuous_watcher"]["pid"], 24680)

    def test_close_readiness_blocks_active_unknown_and_block_messages(self) -> None:
        active = close_readiness_fields(state="processing", snapshot_available=True, block_message="")
        unknown = close_readiness_fields(state="unknown", snapshot_available=False, block_message="")
        custom = close_readiness_fields(state="completed", snapshot_available=True, block_message="PID 123 is still running.")
        unexpected = close_readiness_fields(state="publishing", snapshot_available=True, block_message="")
        unknown_with_snapshot = close_readiness_fields(state="unknown", snapshot_available=True, block_message="")

        self.assertFalse(active["safe_to_close"])
        self.assertIn("processing", active["reason"])
        self.assertFalse(unknown["safe_to_close"])
        self.assertEqual(unknown["warnings"], [SNAPSHOT_UNAVAILABLE_WARNING])
        self.assertIn("unknown", unknown["reason"])
        self.assertFalse(custom["safe_to_close"])
        self.assertEqual(custom["reason"], "PID 123 is still running.")
        self.assertFalse(unexpected["safe_to_close"])
        self.assertIn("publishing", unexpected["reason"])
        self.assertTrue(unknown_with_snapshot["safe_to_close"])
        self.assertEqual(unknown_with_snapshot["reason"], UNKNOWN_CLOSE_READINESS_REASON)

    def test_pipeline_progress_active_policy_preserves_current_stage_behavior(self) -> None:
        for stage in ("", "idle", "sleeping", "stopped", "completed"):
            self.assertFalse(pipeline_progress_indicates_active_work({"CurrentStage": stage}))
        self.assertTrue(pipeline_progress_indicates_active_work({"CurrentStage": " encode "}))
        self.assertTrue(pipeline_progress_indicates_active_work({"CurrentStage": "encode", "StopRequested": True}))
        self.assertTrue(pipeline_progress_indicates_active_work({"CurrentStage": "encode", "StopRequested": "false"}))

    def test_audit_progress_active_policy_preserves_status_behavior(self) -> None:
        for status in ("", "idle", "completed", "failed", "stopped"):
            self.assertFalse(audit_progress_indicates_active_work({"status": status}))
        self.assertTrue(audit_progress_indicates_active_work({"status": " running "}))
        self.assertFalse(audit_progress_indicates_active_work({"status": "running", "completed": True}))
        self.assertFalse(audit_progress_indicates_active_work({"status": "running", "failed": True}))
        self.assertFalse(audit_progress_indicates_active_work({"status": "running", "completed": "false"}))


if __name__ == "__main__":
    unittest.main()
