from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev"))

import check_architecture_guardrails as guardrails  # noqa: E402


def _rule_ids(paths: list[str]) -> set[str]:
    return {finding.rule_id for finding in guardrails.findings_for_paths(paths)}


class ArchitectureGuardrailsTests(unittest.TestCase):
    def test_new_flat_python_layout_paths_are_blocked(self) -> None:
        paths = [
            "src/mediapipeline/desktop/application/facade_new_panel.py",
            "src/mediapipeline/desktop/service_new_worker.py",
            "src/mediapipeline/desktop/api/command_payloads_new_action.py",
        ]

        self.assertEqual(_rule_ids(paths), {"ARCH001", "ARCH002", "ARCH003"})

    def test_target_app_layout_is_allowed(self) -> None:
        self.assertEqual(
            guardrails.findings_for_paths(
                [
                    "src/mediapipeline/core/publish/drain.py",
                    "src/mediapipeline/core/config/profile.py",
                    "ops/pipeline/engine/publish/drain.ps1",
                ]
            ),
            [],
        )

    def test_new_dotted_pipeline_module_is_blocked(self) -> None:
        findings = guardrails.findings_for_paths(["Pipeline/Modules/Publish.Drain.ps1"])

        self.assertEqual([finding.rule_id for finding in findings], ["ARCH004"])

    def test_root_status_docs_are_blocked_except_open_work_checklist(self) -> None:
        self.assertEqual(_rule_ids(["NEW_FIXES.md", "DOCS_REPORT.md"]), {"ARCH005"})
        self.assertEqual(guardrails.findings_for_paths(["docs/OPEN_WORK_CHECKLIST.md"]), [])

    def test_root_callers_are_blocked_including_reintroduced_shim_names(self) -> None:
        self.assertEqual(
            _rule_ids(
                [
                    "Build-MediaPipelineRemuxEncodeAIO-Release.ps1",
                    "Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat",
                    "OPEN_API_AND_BROWSER.cmd",
                    "Start-NewTool.bat",
                    "Do-Thing.ps1",
                ]
            ),
            {"ARCH006"},
        )

    def test_active_config_metadata_does_not_embed_operator_unc_root(self) -> None:
        metadata = (REPO_ROOT / "src" / "mediapipeline" / "core" / "config" / "metadata.py").read_text(encoding="utf-8")

        self.assertNotIn("LAYNE-SERVER", metadata)

    def test_core_code_does_not_import_desktop_config_key_shim(self) -> None:
        offenders = []
        core_root = REPO_ROOT / "src" / "mediapipeline" / "core"
        for path in sorted(core_root.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "from mediapipeline.desktop.config_keys import" in source:
                offenders.append(path.relative_to(REPO_ROOT).as_posix())

        self.assertEqual(offenders, [])

    def test_working_tree_candidates_ignore_modified_existing_files(self) -> None:
        status = "\n".join(
            [
                " M src/mediapipeline/desktop/service_existing.py",
                "?? src/mediapipeline/desktop/service_new.py",
                "R  old/path.py -> src/mediapipeline/desktop/application/facade_new.py",
            ]
        )

        candidates = guardrails.creation_candidates_from_status(status)

        self.assertEqual(
            [candidate.path for candidate in candidates],
            [
                "src/mediapipeline/desktop/service_new.py",
                "src/mediapipeline/desktop/application/facade_new.py",
            ],
        )
        self.assertEqual(
            _rule_ids([candidate.path for candidate in candidates]),
            {"ARCH001", "ARCH002"},
        )

    def test_staged_rename_uses_destination_path(self) -> None:
        candidates = guardrails.staged_creation_candidates(
            "R100\told/facade_old.py\tsrc/mediapipeline/desktop/application/facade_new.py\n"
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0].path,
            "src/mediapipeline/desktop/application/facade_new.py",
        )
        self.assertEqual(candidates[0].source_path, "old/facade_old.py")

    def test_copy_statuses_are_creation_candidates(self) -> None:
        working_tree_candidates = guardrails.creation_candidates_from_status(
            "C  old/service_old.py -> src/mediapipeline/desktop/service_new.py\n"
        )
        staged_candidates = guardrails.staged_creation_candidates(
            "C100\told/service_old.py\tsrc/mediapipeline/desktop/service_new.py\n"
        )

        self.assertEqual(
            [candidate.path for candidate in working_tree_candidates],
            ["src/mediapipeline/desktop/service_new.py"],
        )
        self.assertEqual(
            [candidate.path for candidate in staged_candidates],
            ["src/mediapipeline/desktop/service_new.py"],
        )
        self.assertEqual(_rule_ids([working_tree_candidates[0].path]), {"ARCH002"})

    def test_failure_output_includes_rule_path_reason_and_fix(self) -> None:
        findings = guardrails.findings_for_paths(
            ["src/mediapipeline/desktop/application/facade_new.py"]
        )

        rendered = guardrails.render_findings(findings)

        self.assertIn("ARCH001", rendered)
        self.assertIn("src/mediapipeline/desktop/application/facade_new.py", rendered)
        self.assertIn("Reason:", rendered)
        self.assertIn("Fix:", rendered)
        self.assertIn("Do not weaken this guard", rendered)


if __name__ == "__main__":
    unittest.main()
