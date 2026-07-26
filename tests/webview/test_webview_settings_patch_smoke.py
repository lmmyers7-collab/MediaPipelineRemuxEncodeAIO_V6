from __future__ import annotations

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.webview_settings_patch_smoke import run_smoke


PROJECT_ROOT = find_repo_root(Path(__file__))
APP_ROOT = PROJECT_ROOT / "src"
PIPELINE_PATH = PROJECT_ROOT / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1"


class WebViewSettingsPatchEvidenceSmoke(unittest.TestCase):
    def test_patch_evidence_smoke_uses_temp_config_and_backend_owned_commands(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            summary = run_smoke(app_root=APP_ROOT, pipeline_path=PIPELINE_PATH, work_root=root)
            config_path = Path(summary["config_path"])
            config_text = config_path.read_text(encoding="utf-8")

        self.assertEqual(summary["schema_version"], "webview_settings_patch_evidence_smoke.v1")
        self.assertEqual(summary["patch"], {"CompatibilityEncodeGrowthPercent": 16, "MaxEncodeGrowthPercent": 6})
        self.assertEqual(summary["before"], {"CompatibilityEncodeGrowthPercent": 15, "MaxEncodeGrowthPercent": 5})
        self.assertEqual(summary["after"], {"CompatibilityEncodeGrowthPercent": 16, "MaxEncodeGrowthPercent": 6})
        self.assertTrue(summary["preview"]["ok"])
        self.assertFalse(summary["preview"]["writes_config"])
        self.assertTrue(summary["preview"]["artifacts_unchanged"])
        self.assertGreaterEqual(summary["preview"]["artifact_count"], 6)
        self.assertEqual(summary["preview"]["review_entries_schema_version"], "desktop_settings_patch_review_entries.v1")
        self.assertTrue(summary["preview"]["review_confirmation_preview_id"])
        self.assertIn("MaxEncodeGrowthPercent", summary["preview"]["changed_keys"])
        self.assertFalse(summary["denied_save"]["ok"])
        self.assertIn("confirm_save must be true.", summary["denied_save"]["warnings"])
        self.assertEqual(summary["missing_confirmation"]["status"], 400)
        self.assertIn("confirm_save: Field required", summary["missing_confirmation"]["error"])
        self.assertTrue(summary["confirmed_save"]["ok"])
        self.assertTrue(summary["confirmed_save"]["writes_config"])
        self.assertTrue(summary["confirmed_save"]["reloaded"])
        self.assertTrue(summary["confirmed_save"]["reload_verified"])
        self.assertTrue(summary["confirmed_save"]["backup_exists"])
        self.assertIn("settings.preview_patch", summary["command_history"])
        self.assertGreaterEqual(summary["command_history"].count("settings.save_patch"), 2)
        self.assertIn("Temporary config only", summary["boundary"])
        self.assertIn("MaxEncodeGrowthPercent", config_text)
        self.assertIn("6", config_text)

    def test_productized_smoke_isolates_runtime_and_logger_before_service_startup(self) -> None:
        desktop_logger = logging.getLogger("mediapipeline.desktop")
        handlers_before = tuple(desktop_logger.handlers)
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            real_localappdata = root / "real-localappdata"
            work_root = root / "work"
            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(real_localappdata),
                    "MEDIAPIPELINE_PRODUCTIZED_APP": "1",
                },
            ):
                os.environ.pop("MEDIAPIPELINE_APPDATA_ROOT", None)
                summary = run_smoke(app_root=APP_ROOT, work_root=work_root)

            self.assertFalse(real_localappdata.exists())
            self.assertEqual(tuple(desktop_logger.handlers), handlers_before)
            self.assertEqual(Path(summary["pipeline_path"]), PIPELINE_PATH.resolve())
            for field in ("runtime_paths", "logger_paths"):
                paths = [Path(value).resolve() for value in summary[field]]
                self.assertTrue(paths, field)
                self.assertTrue(all(path.is_relative_to(work_root.resolve()) for path in paths), field)


if __name__ == "__main__":
    unittest.main()
