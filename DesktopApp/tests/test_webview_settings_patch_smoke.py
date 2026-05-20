from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.webview_settings_patch_smoke import run_smoke


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "DesktopApp"
PIPELINE_PATH = PROJECT_ROOT / "Pipeline" / "MediaPipeline_chatgpt.ps1"


class WebViewSettingsPatchEvidenceSmokeTests(unittest.TestCase):
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
        self.assertIn("MaxEncodeGrowthPercent", summary["preview"]["changed_keys"])
        self.assertFalse(summary["denied_save"]["ok"])
        self.assertIn("confirm_save must be true.", summary["denied_save"]["warnings"])
        self.assertTrue(summary["confirmed_save"]["ok"])
        self.assertTrue(summary["confirmed_save"]["writes_config"])
        self.assertTrue(summary["confirmed_save"]["reloaded"])
        self.assertTrue(summary["confirmed_save"]["backup_exists"])
        self.assertIn("settings.preview_patch", summary["command_history"])
        self.assertGreaterEqual(summary["command_history"].count("settings.save_patch"), 2)
        self.assertIn("Temporary config only", summary["boundary"])
        self.assertIn("MaxEncodeGrowthPercent", config_text)
        self.assertIn("6", config_text)


if __name__ == "__main__":
    unittest.main()
