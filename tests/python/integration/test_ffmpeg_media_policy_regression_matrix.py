from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from mediapipeline.contracts.decision_policy import EffectiveDecisionPolicy
from mediapipeline.contracts.source_media import SourceMediaInfo, source_media_from_ffprobe
from mediapipeline.contracts.verification import evaluate_output_size_check, verification_result_from_size_check
from mediapipeline.core.decide.routing import build_processing_decision
from mediapipeline.core.orchestration.planner import build_pipeline_plan
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
MATRIX_PATH = REPO_ROOT / "tests" / "fixtures" / "media_policy" / "ffmpeg_media_policy_regression_matrix.json"
SOURCE_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "source_media"

REQUIRED_AXES = {
    "remux",
    "encode",
    "subtitles",
    "audio",
    "size_policy",
    "stream_mapping",
    "sidecars",
    "pending_publish",
    "failure_modes",
}
VALIDATION_RUNGS = {
    "python-planner-unit",
    "powershell-unit",
    "python-powershell-parity",
    "tdarr-smoke",
    "tdarr-proof",
    "real-media-gate",
    "release-gate",
}


def load_matrix() -> dict[str, Any]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def load_source_fixture(name: str) -> dict[str, Any]:
    return json.loads((SOURCE_FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def source_from_fixture(name: str, overrides: dict[str, Any] | None = None) -> SourceMediaInfo:
    raw = copy.deepcopy(load_source_fixture(name))
    overrides = overrides or {}
    raw.setdefault("source", {}).update(overrides.get("source", {}))
    raw.setdefault("format", {}).update(overrides.get("format", {}))
    if overrides.get("remove_subtitles"):
        raw["streams"] = [stream for stream in raw.get("streams", []) if stream.get("codec_type") != "subtitle"]
    return source_media_from_ffprobe(raw)


def reason_codes(decision: Any) -> set[str]:
    return {reason.code for reason in decision.route_reasons}


def advisory_codes(decision: Any) -> set[str]:
    return {reason.code for reason in decision.advisory_warnings}


def step_operations(plan: Any) -> set[str]:
    return {step.operation for command_plan in plan.command_plans for step in command_plan.steps}


class FFmpegMediaPolicyRegressionMatrixTests(unittest.TestCase):
    def test_matrix_rows_have_required_evidence_fields(self) -> None:
        matrix = load_matrix()
        rows = matrix.get("rows", [])

        self.assertEqual(matrix.get("schema_version"), "ffmpeg_media_policy_regression_matrix.v1")
        self.assertGreater(len(rows), 0)
        covered_axes: set[str] = set()

        for row in rows:
            with self.subTest(row=row.get("id")):
                self.assertRegex(row.get("id", ""), r"^FFMPOL-\d{3}$")
                self.assertTrue(row.get("title"))
                self.assertTrue(row.get("expected_outcome"), "row must describe expected behavior")
                self.assertTrue(row.get("owner_code_paths"), "row must identify owning code paths")
                self.assertTrue(row.get("automated_checks"), "row must have at least one automated check")
                self.assertIn(row.get("validation_rung"), VALIDATION_RUNGS)
                self.assertTrue(row.get("risk_boundary"))

                axes = set(row.get("axes", []))
                self.assertTrue(axes, "row must identify at least one matrix axis")
                covered_axes.update(axes)

                for code_path in row["owner_code_paths"]:
                    self.assertTrue((REPO_ROOT / code_path).exists(), code_path)
                for check in row["automated_checks"]:
                    self.assertTrue(check.get("command"), "automated check must name a command")
                    self.assertTrue(check.get("proves"), "automated check must say what it proves")
                    for check_path in check.get("paths", []):
                        self.assertTrue((REPO_ROOT / check_path).exists(), check_path)

        self.assertTrue(REQUIRED_AXES.issubset(covered_axes), sorted(REQUIRED_AXES - covered_axes))

    def test_python_decision_rows_match_expected_outcomes(self) -> None:
        matrix = load_matrix()

        for row in matrix["rows"]:
            check = row.get("python_decision_check")
            if not check:
                continue
            with self.subTest(row=row["id"]):
                source = source_from_fixture(check["source_fixture"], check.get("source_overrides"))
                policy = EffectiveDecisionPolicy(**check.get("policy", {}))
                expected = row["expected_outcome"]
                decision = build_processing_decision(source, policy)

                self.assertIn(decision.route_summary, expected["route_summaries"])
                self.assertEqual(decision.stream_actions.video.action, expected["video_action"])
                if "container_action" in expected:
                    self.assertEqual(decision.stream_actions.container, expected["container_action"])
                if "audio_actions" in expected:
                    self.assertEqual([stream.action for stream in decision.stream_actions.audio], expected["audio_actions"])
                if "subtitle_actions" in expected:
                    self.assertEqual(
                        [stream.action for stream in decision.stream_actions.subtitles],
                        expected["subtitle_actions"],
                    )
                self.assertTrue(set(expected.get("reason_codes", [])).issubset(reason_codes(decision)))
                self.assertTrue(set(expected.get("advisory_codes", [])).issubset(advisory_codes(decision)))

                if decision.route_summary != "REJECT":
                    plan = build_pipeline_plan(source, decision, plan_id=row["id"].lower())
                    operations = step_operations(plan)
                    self.assertTrue(set(expected.get("required_plan_operations", [])).issubset(operations))
                    self.assertFalse(set(expected.get("forbidden_plan_operations", [])).intersection(operations))

    def test_size_policy_rows_match_expected_outcomes(self) -> None:
        matrix = load_matrix()

        for row in matrix["rows"]:
            check = row.get("size_policy_check")
            if not check:
                continue
            with self.subTest(row=row["id"]):
                result = verification_result_from_size_check(
                    evaluate_output_size_check(
                        action=check["action"],
                        source_size_bytes=check["source_size_bytes"],
                        actual_output_size_bytes=check["actual_output_size_bytes"],
                        growth_tolerance_percent=check["growth_tolerance_percent"],
                    )
                )
                expected = row["expected_outcome"]

                self.assertEqual(result.output_size_check.status, expected["size_status"])
                self.assertEqual(result.output_size_check.on_fail, expected["on_fail"])
                self.assertEqual(len(result.advisory_warnings), expected["advisory_warning_count"])
                self.assertEqual(len(result.failures), expected["failure_count"])
                self.assertEqual(len(result.publish_blockers), expected["publish_blocker_count"])

    def test_testgap_006_cannot_close_without_parity_and_real_media_evidence(self) -> None:
        matrix = load_matrix()
        gap = matrix["testgap_006"]
        closure = gap["closure_requirements"]

        if gap["status"] == "closed":
            self.assertEqual(closure.get("python_powershell_parity_coverage"), "current")
            self.assertEqual(closure.get("real_media_evidence"), "current")
            self.assertTrue(closure.get("behavior_change_evidence_gate"))
        else:
            self.assertEqual(gap["status"], "open")
            self.assertIn("python-powershell-parity", gap["open_blockers"])
            self.assertIn("representative-real-media-evidence", gap["open_blockers"])


if __name__ == "__main__":
    unittest.main()
