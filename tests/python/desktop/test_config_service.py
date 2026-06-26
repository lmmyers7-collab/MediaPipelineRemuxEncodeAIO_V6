from __future__ import annotations

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.config.service import ConfigProfileServiceMixin
from mediapipeline.core.config.settings_store import SettingsStoreError
from mediapipeline.core.kernel.config_locations import PER_USER_APP_DIR_NAME, SETTINGS_STORE_NAME
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult


class DummyConfigService(ConfigProfileServiceMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_config_service")
        self.logger.addHandler(logging.NullHandler())

    def _subprocess_kwargs_hidden(self) -> dict:
        return {}


class ConfigServiceRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DummyConfigService()

    def test_load_config_data_uses_runner_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "MediaPipeline_config.psd1"
            config.write_text("@{ VideoCodec = 'hevc_nvenc' }", encoding="utf-8")

            def fake_run(args, **kwargs):
                self.assertEqual(args[0], "pwsh")
                self.assertEqual(kwargs["timeout_seconds"], 30)
                self.assertEqual(kwargs["label"], "config import")
                return CapturedCommandResult(
                    args=args,
                    returncode=0,
                    stdout='{"VideoCodec":"hevc_nvenc"}',
                    stderr="",
                )

            with patch("mediapipeline.core.config.service.run_capture", fake_run):
                data = self.service.load_config_data(config, "pwsh")

            self.assertEqual(data["VideoCodec"], "hevc_nvenc")

    def test_load_config_data_returns_empty_on_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "MediaPipeline_config.psd1"
            config.write_text("@{}", encoding="utf-8")

            def fake_run(args, **_kwargs):
                return CapturedCommandResult(
                    args=args,
                    returncode=None,
                    stdout="",
                    stderr="",
                    timed_out=True,
                    kill_message="process killed",
                )

            with patch("mediapipeline.core.config.service.run_capture", fake_run):
                data = self.service.load_config_data(config, "pwsh")

            self.assertEqual(data, {})

    def test_load_settings_authority_rejects_timeout_without_promoting_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "MediaPipeline_config.psd1"
            config.write_text("@{}", encoding="utf-8")
            store_path = root / "LocalAppData" / PER_USER_APP_DIR_NAME / SETTINGS_STORE_NAME

            def fake_run(args, **_kwargs):
                return CapturedCommandResult(
                    args=args,
                    returncode=None,
                    stdout="",
                    stderr="",
                    timed_out=True,
                    kill_message="process killed",
                )

            with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}, clear=False):
                with patch("mediapipeline.core.config.service.run_capture", fake_run):
                    with self.assertRaisesRegex(SettingsStoreError, "process killed"):
                        self.service.load_settings_authority(config, "pwsh")

            self.assertFalse(store_path.exists())


if __name__ == "__main__":
    unittest.main()
