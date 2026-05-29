from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "lint-naming.py"
spec = importlib.util.spec_from_file_location("lint_naming", MODULE_PATH)
assert spec and spec.loader
lint_naming = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lint_naming
spec.loader.exec_module(lint_naming)


def _rule_ids(paths: list[str]) -> set[str]:
    return {finding.rule_id for finding in lint_naming.findings_for_paths(paths)}


class NamingLintTests(unittest.TestCase):
    def test_new_flat_layout_paths_are_blocked(self) -> None:
        paths = [
            "DesktopApp/mediapipeline_desktop_app/application/facade_new_panel.py",
            "DesktopApp/mediapipeline_desktop_app/service_new_worker.py",
            "DesktopApp/mediapipeline_desktop_app/api/command_payloads_new_action.py",
        ]

        self.assertEqual(_rule_ids(paths), {"NAME001", "NAME002", "NAME003"})

    def test_target_layout_is_allowed(self) -> None:
        self.assertEqual(
            lint_naming.findings_for_paths(
                [
                    "app/publish/drain.py",
                    "app/settings/profile.py",
                    "engine/publish/drain.ps1",
                ]
            ),
            [],
        )

    def test_new_dotted_pipeline_module_and_suffixes_are_blocked(self) -> None:
        self.assertEqual(_rule_ids(["Pipeline/Modules/Publish.Drain.ps1"]), {"NAME004"})
        self.assertEqual(
            _rule_ids(
                [
                    "Pipeline/MediaPipeline_chatgpt.ps1",
                    "app/config/load_old.py",
                    "engine/probe/runner_new.ps1",
                ]
            ),
            {"NAME007"},
        )

    def test_root_status_docs_and_callers_are_blocked(self) -> None:
        self.assertEqual(_rule_ids(["NEW_REPORT.md", "DOCS_CHECKLIST.md"]), {"NAME005"})
        self.assertEqual(lint_naming.findings_for_paths(["OPEN_WORK_CHECKLIST.md"]), [])
        self.assertEqual(
            _rule_ids(["Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat", "Start-NewTool.bat", "Do-Thing.ps1"]),
            {"NAME006"},
        )

    def test_existing_legacy_paths_can_be_grandfathered_when_not_new(self) -> None:
        self.assertEqual(
            lint_naming.findings_for_paths(
                [
                    "DesktopApp/mediapipeline_desktop_app/service_queue.py",
                    "Pipeline/MediaPipeline_chatgpt.ps1",
                    "Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat",
                ],
                is_new=False,
            ),
            [],
        )

    def test_git_status_parsers_use_created_destination_paths(self) -> None:
        working = lint_naming.creation_candidates_from_status(
            "\n".join(
                [
                    " M DesktopApp/mediapipeline_desktop_app/service_existing.py",
                    "?? DesktopApp/mediapipeline_desktop_app/service_new.py",
                    "R  old/path.py -> DesktopApp/mediapipeline_desktop_app/application/facade_new.py",
                ]
            )
        )
        staged = lint_naming.creation_candidates_from_name_status(
            "R100\told/facade_old.py\tDesktopApp/mediapipeline_desktop_app/application/facade_new.py\n"
        )

        self.assertEqual(
            [candidate.path for candidate in working],
            [
                "DesktopApp/mediapipeline_desktop_app/service_new.py",
                "DesktopApp/mediapipeline_desktop_app/application/facade_new.py",
            ],
        )
        self.assertEqual(staged[0].path, "DesktopApp/mediapipeline_desktop_app/application/facade_new.py")


if __name__ == "__main__":
    unittest.main()
