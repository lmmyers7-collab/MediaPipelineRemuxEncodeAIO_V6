from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_config import ConfigProfileServiceMixin
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


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

            with patch("mediapipeline_desktop_app.service_config.run_capture", fake_run):
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

            with patch("mediapipeline_desktop_app.service_config.run_capture", fake_run):
                data = self.service.load_config_data(config, "pwsh")

            self.assertEqual(data, {})


if __name__ == "__main__":
    unittest.main()
