from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.backend_bootstrap import BOOTSTRAP_SCHEMA_VERSION, backend_bootstrap_payload


class BackendBootstrapPayloadTests(unittest.TestCase):
    def test_backend_bootstrap_payload_includes_token_when_required(self) -> None:
        payload = backend_bootstrap_payload(
            url="http://127.0.0.1:8765",
            token="secret-token",
            host="127.0.0.1",
            port=8765,
            config_path=Path("C:/MediaPipeline/Pipeline/MediaPipeline_config.psd1"),
            pipeline_path=Path("C:/MediaPipeline/Pipeline/MediaPipeline_chatgpt.ps1"),
            include_token=True,
        )

        self.assertEqual(payload["schema_version"], BOOTSTRAP_SCHEMA_VERSION)
        self.assertEqual(payload["url"], "http://127.0.0.1:8765")
        self.assertEqual(payload["token"], "secret-token")
        self.assertEqual(payload["host"], "127.0.0.1")
        self.assertEqual(payload["port"], 8765)
        self.assertEqual(Path(str(payload["config_path"])).name, "MediaPipeline_config.psd1")
        self.assertEqual(Path(str(payload["pipeline_path"])).name, "MediaPipeline_chatgpt.ps1")
        self.assertEqual(payload["shell_surface"], "webview")

    def test_backend_bootstrap_payload_omits_token_when_not_required(self) -> None:
        payload = backend_bootstrap_payload(
            url="http://127.0.0.1:8765",
            token="secret-token",
            host="127.0.0.1",
            port=8765,
            config_path=Path("config.psd1"),
            pipeline_path=Path("pipeline.ps1"),
            include_token=False,
            shell_surface="tauri",
        )

        self.assertEqual(payload["token"], "")
        self.assertEqual(payload["shell_surface"], "tauri")


if __name__ == "__main__":
    unittest.main()
