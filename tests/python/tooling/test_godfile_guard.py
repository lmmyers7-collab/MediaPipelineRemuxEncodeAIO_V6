from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
MODULE_PATH = REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "check_godfiles.py"
spec = importlib.util.spec_from_file_location("check_godfiles_for_tests", MODULE_PATH)
assert spec and spec.loader
godfiles = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = godfiles
spec.loader.exec_module(godfiles)


def _policy() -> dict[str, object]:
    return {
        "schema_version": "god_file_guardrail.v1",
        "defaults": {
            "include_globs": ["src/*.py"],
            "exclude_globs": [],
            "warn_lines": 3,
            "max_lines": 5,
            "new_file_max_lines": 4,
            "growth_warn_lines": 2,
            "report_limit": 10,
        },
        "patterns": [],
        "allowlist": [
            {
                "id": "generated-builder",
                "path_globs": ["src/generated_builder.py"],
                "warn_lines": 10,
                "max_lines": 12,
                "new_file_max_lines": 12,
                "growth_warn_lines": 2,
                "feature": "generated_builder",
                "reason": "Generated builder is intentionally consolidated.",
            }
        ],
    }


def _write_lines(root: Path, rel: str, count: int) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"line_{index}" for index in range(count)), encoding="utf-8")


class GodFileGuardTests(unittest.TestCase):
    def test_policy_validation_accepts_repo_policy(self) -> None:
        policy = godfiles.load_policy()

        self.assertEqual(godfiles.validate_policy(policy), [])

    def test_repo_policy_includes_root_webview_assets(self) -> None:
        policy = godfiles.load_policy()
        path = "apps/desktop/webview/static/assets/app.js"

        self.assertTrue(godfiles.is_included(path, policy))
        thresholds = godfiles.thresholds_for_path(path, policy)
        self.assertTrue(thresholds.allowlisted)
        self.assertEqual(thresholds.warn_lines, 1500)

    def test_repo_policy_covers_promoted_source_roots(self) -> None:
        policy = godfiles.load_policy()

        self.assertTrue(godfiles.is_included("src/mediapipeline/core/config/validation.py", policy))
        self.assertTrue(godfiles.is_included("ops/pipeline/entrypoints/Setup-MediaPipeline.ps1", policy))
        self.assertTrue(godfiles.is_included("ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1", policy))

    def test_repo_policy_does_not_reintroduce_removed_roots(self) -> None:
        policy = godfiles.load_policy()
        default_globs = set(policy["defaults"]["include_globs"])
        pattern_globs = {
            glob
            for entry in policy["patterns"]
            for glob in entry.get("path_globs", [])
        }
        all_globs = default_globs | pattern_globs

        self.assertNotIn("app/**/*.py", all_globs)
        self.assertNotIn("DesktopApp/**/*.py", all_globs)
        self.assertNotIn("Pipeline/**/*.ps1", all_globs)

    def test_new_oversized_file_warns_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_lines(root, "src/new_feature.py", 6)

            findings = godfiles.analyze_candidates(
                [godfiles.CandidatePath("src/new_feature.py", is_new=True)],
                _policy(),
                root=root,
            )

        self.assertIn("GOD003", {finding.rule_id for finding in findings})
        self.assertIn("warning", {finding.severity for finding in findings})

    def test_new_oversized_file_can_be_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_lines(root, "src/new_feature.py", 6)

            findings = godfiles.analyze_candidates(
                [godfiles.CandidatePath("src/new_feature.py", is_new=True)],
                _policy(),
                root=root,
                enforce_new=True,
            )

        self.assertIn("GOD003", {finding.rule_id for finding in findings})
        self.assertIn("error", {finding.severity for finding in findings})

    def test_existing_oversized_file_warns_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_lines(root, "src/existing.py", 6)

            findings = godfiles.analyze_candidates(
                [godfiles.CandidatePath("src/existing.py", is_new=False)],
                _policy(),
                root=root,
            )

        self.assertEqual([(finding.rule_id, finding.severity) for finding in findings], [("GOD002", "warning")])

    def test_allowlist_raises_threshold_for_named_feature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_lines(root, "src/generated_builder.py", 6)

            findings = godfiles.analyze_candidates(
                [godfiles.CandidatePath("src/generated_builder.py", is_new=True)],
                _policy(),
                root=root,
            )

        self.assertEqual(findings, [])

    def test_growth_warning_reports_previous_line_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_lines(root, "src/existing.py", 5)

            findings = godfiles.analyze_candidate(
                godfiles.CandidatePath("src/existing.py", is_new=False),
                _policy(),
                root=root,
                previous_lines=3,
            )

        growth = [finding for finding in findings if finding.rule_id == "GOD004"]
        self.assertEqual(len(growth), 1)
        self.assertEqual(growth[0].previous_line_count, 3)

    def test_git_status_parser_marks_created_destinations(self) -> None:
        candidates = godfiles.changed_candidates_from_status(
            "\n".join(
                [
                    " M src/existing.py",
                    "?? src/new.py",
                    "R  old/name.py -> src/renamed.py",
                ]
            )
        )

        self.assertEqual(
            [(candidate.path, candidate.is_new) for candidate in candidates],
            [
                ("src/existing.py", False),
                ("src/new.py", True),
                ("src/renamed.py", True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
