from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.paths.defaults import (
    default_audit_script_path_for_roots,
    default_config_path_for_roots,
    default_pipeline_path_for_roots,
    default_rerun_script_path_for_roots,
)


class ServicePathDefaultsTests(unittest.TestCase):
    def test_default_pipeline_path_prefers_workspace_pipeline_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            workspace_root = root
            preferred = workspace_root / "Pipeline" / "MediaPipeline_chatgpt.ps1"
            fallback = app_root / "MediaPipeline_chatgpt.ps1"
            preferred.parent.mkdir(parents=True)
            app_root.mkdir()
            preferred.write_text("", encoding="utf-8")
            fallback.write_text("", encoding="utf-8")

            self.assertEqual(default_pipeline_path_for_roots(app_root, workspace_root), preferred)

    def test_default_config_path_falls_back_to_app_pipeline_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            workspace_root = root
            fallback = app_root / "Pipeline" / "MediaPipeline_config_chatgpt.psd1"
            fallback.parent.mkdir(parents=True)
            fallback.write_text("", encoding="utf-8")

            self.assertEqual(default_config_path_for_roots(app_root, workspace_root), fallback)

    def test_default_audit_script_path_falls_back_to_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            workspace_root = root
            fallback = workspace_root / "Audit-MediaLibrary_chatgpt.ps1"
            app_root.mkdir()
            fallback.write_text("", encoding="utf-8")

            self.assertEqual(default_audit_script_path_for_roots(app_root, workspace_root), fallback)

    def test_default_rerun_script_path_returns_first_candidate_when_none_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            workspace_root = root

            self.assertEqual(
                default_rerun_script_path_for_roots(app_root, workspace_root),
                workspace_root / "Pipeline" / "Invoke-RerunCsv.ps1",
            )


if __name__ == "__main__":
    unittest.main()
