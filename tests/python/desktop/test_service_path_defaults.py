from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from pathlib import Path

from mediapipeline.core.paths.defaults import (
    CONFIG_CANONICAL_NAME,
    PER_USER_APP_DIR_NAME,
    default_audit_script_path_for_roots,
    default_config_path_for_roots,
    default_pipeline_path_for_roots,
    default_rerun_script_path_for_roots,
)


class ServicePathDefaultsTests(unittest.TestCase):
    def test_default_pipeline_path_prefers_workspace_pipeline_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "apps" / "desktop"
            workspace_root = root
            preferred = workspace_root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1"
            fallback = app_root / "entrypoints" / "MediaPipeline.ps1"
            preferred.parent.mkdir(parents=True)
            app_root.mkdir(parents=True)
            fallback.parent.mkdir(parents=True)
            preferred.write_text("", encoding="utf-8")
            fallback.write_text("", encoding="utf-8")

            self.assertEqual(default_pipeline_path_for_roots(app_root, workspace_root), preferred)

    def test_default_config_path_falls_back_to_app_pipeline_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "apps" / "desktop"
            workspace_root = root
            fallback = app_root / "config" / "MediaPipeline_config_chatgpt.psd1"
            fallback.parent.mkdir(parents=True)
            fallback.write_text("", encoding="utf-8")

            with mock.patch.dict("os.environ", {"LOCALAPPDATA": str(root / "LocalAppData")}):
                self.assertEqual(default_config_path_for_roots(app_root, workspace_root), fallback)

    def test_default_config_path_prefers_existing_per_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "apps" / "desktop"
            workspace_root = root
            user_config = root / "LocalAppData" / PER_USER_APP_DIR_NAME / CONFIG_CANONICAL_NAME
            local_config = workspace_root / "ops" / "pipeline" / "config" / CONFIG_CANONICAL_NAME
            user_config.parent.mkdir(parents=True)
            local_config.parent.mkdir(parents=True)
            user_config.write_text("", encoding="utf-8")
            local_config.write_text("", encoding="utf-8")

            with mock.patch.dict("os.environ", {"LOCALAPPDATA": str(root / "LocalAppData")}):
                self.assertEqual(default_config_path_for_roots(app_root, workspace_root), user_config)

    def test_default_audit_script_path_falls_back_to_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "apps" / "desktop"
            workspace_root = root
            fallback = workspace_root / "ops" / "pipeline" / "entrypoints" / "Audit-MediaLibrary.ps1"
            app_root.mkdir(parents=True)
            fallback.parent.mkdir(parents=True)
            fallback.write_text("", encoding="utf-8")

            self.assertEqual(default_audit_script_path_for_roots(app_root, workspace_root), fallback)

    def test_default_rerun_script_path_returns_first_candidate_when_none_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "apps" / "desktop"
            workspace_root = root

            self.assertEqual(
                default_rerun_script_path_for_roots(app_root, workspace_root),
                workspace_root / "ops" / "pipeline" / "entrypoints" / "Invoke-RerunCsv.ps1",
            )


if __name__ == "__main__":
    unittest.main()
