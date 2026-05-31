from __future__ import annotations

import unittest

from app.config.preset_policy import PRESET_POLICY_WRITE_FORMAT
from app.config.rollout import (
    planner_comparison_from_decision_snapshot,
    resolve_planner_rollout_config,
)


class RolloutPolicyTests(unittest.TestCase):
    def test_default_rollout_keeps_legacy_execution_authority(self) -> None:
        state = resolve_planner_rollout_config({})

        self.assertEqual(state.stage, "legacy")
        self.assertEqual(state.execution_authority, "legacy_powershell")
        self.assertFalse(state.new_planner_execution_enabled)
        self.assertFalse(state.comparison_logging_enabled)
        self.assertTrue(state.dry_run_only)
        self.assertEqual(state.preset_write_format, PRESET_POLICY_WRITE_FORMAT)

    def test_shadow_rollout_enables_comparison_but_not_execution(self) -> None:
        state = resolve_planner_rollout_config(
            {
                "PlannerRolloutStage": "stage1",
                "UsePythonPlanner": True,
                "PlannerComparisonLogging": True,
            }
        )

        self.assertEqual(state.stage, "shadow")
        self.assertEqual(state.execution_authority, "legacy_powershell_with_python_preview")
        self.assertTrue(state.new_planner_requested)
        self.assertTrue(state.comparison_logging_enabled)
        self.assertFalse(state.new_planner_execution_enabled)
        self.assertTrue(any("legacy PowerShell remains authoritative" in warning for warning in state.warnings))

    def test_default_cutover_requires_explicit_approval_key(self) -> None:
        state = resolve_planner_rollout_config(
            {
                "PlannerRolloutStage": "new_planner_default",
                "UsePythonPlanner": True,
            }
        )

        self.assertEqual(state.stage, "new_planner_default")
        self.assertFalse(state.new_planner_execution_enabled)
        self.assertEqual(state.execution_authority, "legacy_powershell_with_python_preview")
        self.assertTrue(any("without NewPlannerCutoverApproved" in warning for warning in state.warnings))

    def test_cutover_state_is_two_key_explicit_and_still_reports_validation_required(self) -> None:
        state = resolve_planner_rollout_config(
            {
                "PlannerRolloutStage": "cutover",
                "UsePythonPlanner": True,
                "NewPlannerCutoverApproved": True,
            }
        )

        self.assertTrue(state.new_planner_execution_enabled)
        self.assertEqual(state.execution_authority, "python_planner_cutover")
        self.assertFalse(state.dry_run_only)
        self.assertTrue(any("validated separately" in warning for warning in state.warnings))
        self.assertTrue(any("representative real-media validation" in action for action in state.operator_actions_required))

    def test_comparison_is_disabled_until_rollout_requests_logging(self) -> None:
        record = planner_comparison_from_decision_snapshot(
            {
                "routeSummary": "COPY",
                "legacyRoute": "remux",
                "legacyReasonCode": "plex_compatible_h264_remux",
                "routeReasons": [{"code": "SOURCE_CODEC_COMPATIBLE"}],
            }
        )

        self.assertFalse(record.enabled)
        self.assertEqual(record.status, "disabled")
        self.assertEqual(record.python_route, "COPY")
        self.assertEqual(record.legacy_route, "REMUX")

    def test_comparison_reports_dry_run_divergence(self) -> None:
        state = resolve_planner_rollout_config({"PlannerComparisonLogging": True})
        record = planner_comparison_from_decision_snapshot(
            {
                "routeSummary": "COPY",
                "legacyRoute": "remux",
                "legacyReasonCode": "plex_compatible_h264_remux",
                "routeReasons": [{"code": "SOURCE_CODEC_COMPATIBLE"}],
            },
            rollout_state=state,
        )

        self.assertTrue(record.enabled)
        self.assertEqual(record.status, "divergent")
        self.assertEqual(record.python_reason_codes, ["SOURCE_CODEC_COMPATIBLE"])
        self.assertTrue(any("dry-run evidence only" in note for note in record.notes))


if __name__ == "__main__":
    unittest.main()
