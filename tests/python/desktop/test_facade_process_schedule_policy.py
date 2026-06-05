from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.processes.schedule_policy import (
    SCHEDULE_CONTINUOUS_BLOCK_MESSAGE,
    SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY,
    SCHEDULE_MODE_NOT_SCHEDULED_REASON,
    SCHEDULE_OUTSIDE_WINDOW_MESSAGE,
    continuous_schedule_stop_watcher_preflight_check,
    normalize_schedule_override,
    resolve_pipeline_start_schedule_gate,
    schedule_gate_data,
)


class ProcessSchedulePolicyTests(unittest.TestCase):
    def test_validate_and_pending_drain_skip_schedule_check(self) -> None:
        for mode in ("validate", "drain_pending_pushes"):
            gate = resolve_pipeline_start_schedule_gate(
                mode=mode,
                request={},
                enabled=True,
                evaluation={"allowed_now": False},
            )
            self.assertTrue(gate["ok"])
            self.assertEqual(gate["mode"], mode)
            self.assertEqual(gate["data"]["checked"], False)
            self.assertEqual(gate["data"]["reason"], SCHEDULE_MODE_NOT_SCHEDULED_REASON)

    def test_disabled_schedule_allows_current_mode_with_status_data(self) -> None:
        gate = resolve_pipeline_start_schedule_gate(
            mode="continuous",
            request={},
            enabled=False,
            evaluation={"allowed_now": False, "status_text": "outside"},
        )

        self.assertTrue(gate["ok"])
        self.assertEqual(gate["mode"], "continuous")
        self.assertEqual(gate["data"], {"checked": True, "enabled": False, "allowed_now": False, "status_text": "outside"})
        self.assertEqual(schedule_gate_data(True, {"allowed_now": True, "status_text": "inside"})["status_text"], "inside")

    def test_continuous_is_blocked_when_schedule_allowed_without_ignore_override(self) -> None:
        gate = resolve_pipeline_start_schedule_gate(
            mode="continuous",
            request={},
            enabled=True,
            evaluation={"allowed_now": True, "status_text": "inside"},
        )

        self.assertFalse(gate["ok"])
        self.assertEqual(gate["message"], SCHEDULE_CONTINUOUS_BLOCK_MESSAGE)
        self.assertEqual(gate["severity"], "warning")

    def test_continuous_is_allowed_when_backend_stop_watcher_is_available(self) -> None:
        gate = resolve_pipeline_start_schedule_gate(
            mode="continuous",
            request={},
            enabled=True,
            evaluation={
                "allowed_now": True,
                "status_text": "inside",
                "current_window_end": "2026-05-14T23:30:00",
            },
            backend_stop_watcher_available=True,
        )

        self.assertTrue(gate["ok"])
        self.assertEqual(gate["mode"], "continuous")
        self.assertTrue(gate["data"]["backend_stop_watcher_available"])
        self.assertEqual(gate["data"]["current_window_end"], "2026-05-14T23:30:00")

    def test_allowed_schedule_and_overrides_preserve_existing_behavior(self) -> None:
        once = resolve_pipeline_start_schedule_gate(
            mode="once",
            request={},
            enabled=True,
            evaluation={"allowed_now": True},
        )
        continuous_ignored = resolve_pipeline_start_schedule_gate(
            mode="continuous",
            request={"schedule_override": "ignore"},
            enabled=True,
            evaluation={"allowed_now": True},
        )
        outside_run_once = resolve_pipeline_start_schedule_gate(
            mode="continuous",
            request={"schedule_override": "run-once"},
            enabled=True,
            evaluation={"allowed_now": False},
        )
        outside_ignored = resolve_pipeline_start_schedule_gate(
            mode="continuous",
            request={"schedule_override": " ignore "},
            enabled=True,
            evaluation={"allowed_now": False},
        )

        self.assertEqual(normalize_schedule_override("run-once"), "run_once")
        self.assertTrue(once["ok"])
        self.assertEqual(once["mode"], "once")
        self.assertTrue(continuous_ignored["ok"])
        self.assertEqual(continuous_ignored["mode"], "continuous")
        self.assertTrue(outside_run_once["ok"])
        self.assertEqual(outside_run_once["mode"], "once")
        self.assertEqual(outside_run_once["data"]["override"], "run_once")
        self.assertTrue(outside_ignored["ok"])
        self.assertEqual(outside_ignored["mode"], "continuous")

    def test_outside_schedule_without_override_is_blocked(self) -> None:
        gate = resolve_pipeline_start_schedule_gate(
            mode="once",
            request={},
            enabled=True,
            evaluation={"allowed_now": False},
        )

        self.assertFalse(gate["ok"])
        self.assertEqual(gate["message"], SCHEDULE_OUTSIDE_WINDOW_MESSAGE)
        self.assertEqual(gate["severity"], "warning")

    def test_schedule_gate_data_carries_window_timing_when_available(self) -> None:
        data = schedule_gate_data(
            True,
            {
                "allowed_now": True,
                "status_text": "inside",
                "current_window_end": "2026-05-14T23:30:00",
                "next_allowed_start": "2026-05-14T21:00:00",
            },
        )

        self.assertEqual(data["current_window_end"], "2026-05-14T23:30:00")
        self.assertEqual(data["next_allowed_start"], "2026-05-14T21:00:00")

    def test_continuous_schedule_stop_watcher_preflight_explains_block_and_bypass(self) -> None:
        gate = {
            "ok": False,
            "mode": "continuous",
            "data": {
                "enabled": True,
                "allowed_now": True,
                "status_text": "Schedule: Allowed now until Thursday 11:30 PM",
                "current_window_end": "2026-05-14T23:30:00",
            },
        }
        blocked = continuous_schedule_stop_watcher_preflight_check(
            requested_mode="continuous",
            actual_mode="continuous",
            request={},
            schedule_gate=gate,
        )
        ignored = continuous_schedule_stop_watcher_preflight_check(
            requested_mode="continuous",
            actual_mode="continuous",
            request={"schedule_override": "ignore"},
            schedule_gate=gate,
            backend_watcher_available=True,
        )
        ready = continuous_schedule_stop_watcher_preflight_check(
            requested_mode="continuous",
            actual_mode="continuous",
            request={},
            schedule_gate=gate,
            backend_watcher_available=True,
        )
        once = continuous_schedule_stop_watcher_preflight_check(
            requested_mode="continuous",
            actual_mode="once",
            request={"schedule_override": "run_once"},
            schedule_gate=gate,
        )

        self.assertEqual(blocked["key"], SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("2026-05-14T23:30:00", blocked["evidence"])
        self.assertIn("backend watcher unavailable", blocked["evidence"])
        self.assertEqual(ignored["status"], "high review")
        self.assertIn("bypassing", ignored["action"])
        self.assertIn("backend watcher bypassed", ignored["evidence"])
        self.assertEqual(ready["status"], "ready")
        self.assertIn("backend watcher available", ready["evidence"])
        self.assertEqual(once["status"], "ready")
        self.assertIn("actual_mode=once", once["evidence"])
        trust_text = "\n".join(
            str(item)
            for result in (blocked, ignored, ready, once)
            for item in (result["evidence"], result["action"], *result["detail"])
        )
        self.assertNotIn("V" + "5", trust_text)
        self.assertNotIn("not owned", trust_text)
        self.assertNotIn("does not yet own", trust_text)


if __name__ == "__main__":
    unittest.main()
