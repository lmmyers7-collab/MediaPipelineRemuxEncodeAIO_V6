from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))
sys.path.insert(0, str(find_repo_root(Path(__file__))))

from mediapipeline.core.config.load import (
    config_to_flat_dict,
    config_to_psd1,
    load_psd1_mapping,
    order_top_level_config,
)
from mediapipeline.contracts.config import (
    CONFIG_KEY_ORDER,
    DESKTOP_SCHEMA_CONFIG_KEYS,
    NETWORK_CONFIG_KEYS,
    PS_CONFIG_KEY_ORDER,
    Config,
)
from mediapipeline.core.config.metadata import CONFIG_FIELD_DEFINITIONS
from mediapipeline.core.config.metadata_network import NETWORK_CONFIG_DEFAULTS


class DummyCaptureResult:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.args: list[str] = []
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = False
        self.kill_message = ""


class AppConfigContractTests(unittest.TestCase):
    def test_contract_key_order_covers_powershell_order_plus_network_keys(self) -> None:
        engine_config = find_repo_root(Path(__file__)) / "ops" / "pipeline" / "engine" / "config"
        module_text = "\n".join(
            (engine_config / path).read_text(encoding="utf-8")
            for path in ("config_schema.ps1", "schema_keys.ps1")
        )
        match = re.search(
            r"function Get-MediaPipelineConfigOrderedKeys \{\s*return @\((?P<body>.*?)\)\s*\}",
            module_text,
            re.S,
        )
        self.assertIsNotNone(match)
        ps_order = tuple(re.findall(r"'([^']+)'", match.group("body") if match else ""))

        self.assertEqual(PS_CONFIG_KEY_ORDER, ps_order)
        self.assertEqual(CONFIG_KEY_ORDER, ps_order + NETWORK_CONFIG_KEYS)

    def test_contract_covers_desktop_settings_schema_and_network_defaults(self) -> None:
        schema_keys = tuple(str(field["key"]) for field in CONFIG_FIELD_DEFINITIONS)

        self.assertEqual(DESKTOP_SCHEMA_CONFIG_KEYS, schema_keys)
        self.assertEqual(NETWORK_CONFIG_KEYS, tuple(NETWORK_CONFIG_DEFAULTS))
        self.assertLessEqual(set(schema_keys), set(CONFIG_KEY_ORDER))

    def test_model_defaults_validate_and_preserve_unknown_keys(self) -> None:
        config = Config.model_validate(
            {
                "SourceMovies": r"C:\Movies",
                "SourceTV": r"C:\TV",
                "Outsource": r"D:\Out",
                "LocalBase": r"E:\Scratch",
                "RoutingProfile": "PLEX_DIRECT_STREAM",
                "ConsoleLogLevel": "debug",
                "UnknownOperatorKey": "preserve",
            }
        )

        data = config_to_flat_dict(config)

        self.assertEqual(config.RoutingProfile, "plex_direct_stream")
        self.assertEqual(config.RouteThresholdMode, "compatibility_advisory")
        self.assertEqual(config.MovieRoute1080pTargetSizeGB, config.EncodeThresholdGB)
        self.assertEqual(config.MovieRoute1440pTargetSizeGB, config.EncodeThresholdGB)
        self.assertEqual(config.MovieRoute4KTargetSizeGB, config.EncodeThresholdGB)
        self.assertEqual(config.TVRoute1080pTargetSizeGB, config.TVEncodeThresholdGB)
        self.assertEqual(config.TVRoute1440pTargetSizeGB, config.TVEncodeThresholdGB)
        self.assertEqual(config.TVRoute4KTargetSizeGB, config.TVEncodeThresholdGB)
        self.assertEqual(config.MovieRouteMaxVideoBitrateMbps, 35)
        self.assertEqual(config.TVRouteMaxVideoBitrateMbps, 18)
        self.assertEqual(config.Route1080pBucketMaxHeight, 1200)
        self.assertAlmostEqual(config.Route1080pUpperHeightTolerancePercent, 11.111111, places=6)
        self.assertEqual(config.Route1080pMaxVideoBitrateMbps, 20)
        self.assertAlmostEqual(config.Route1440pLowerHeightTolerancePercent, 16.597222, places=6)
        self.assertAlmostEqual(config.Route1440pUpperHeightTolerancePercent, 24.930556, places=6)
        self.assertEqual(config.Route1440pMaxVideoBitrateMbps, 35)
        self.assertAlmostEqual(config.Route4KLowerHeightTolerancePercent, 16.666667, places=6)
        self.assertEqual(config.Route4KBucketMinHeight, 1800)
        self.assertEqual(config.Route4KMaxVideoBitrateMbps, 35)
        self.assertEqual(config.ConsoleLogLevel, "DEBUG")
        self.assertEqual(data["UnknownOperatorKey"], "preserve")
        self.assertEqual(list(order_top_level_config({"zz": 1, "SourceMovies": 2, "aa": 3})), ["SourceMovies", "aa", "zz"])

    def test_psd1_loader_uses_single_import_command_and_builds_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "MediaPipeline_config.psd1"
            config_path.write_text("@{ VideoCodec = 'hevc_nvenc' }", encoding="utf-8")

            def fake_run(args, **kwargs):
                self.assertEqual(args[0], "pwsh")
                self.assertIn("Import-PowerShellDataFile", args[-1])
                self.assertIn(str(config_path).replace("'", "''"), args[-1])
                self.assertEqual(kwargs["label"], "config import")
                return DummyCaptureResult(json.dumps({"VideoCodec": "hevc_nvenc"}))

            result = load_psd1_mapping(config_path, "pwsh", run_capture_func=fake_run)
            config = Config.model_validate(result.data)

        self.assertTrue(result.ok)
        self.assertEqual(config.VideoCodec, "hevc_nvenc")

    def test_config_to_psd1_serializes_known_and_unknown_keys(self) -> None:
        text = config_to_psd1({"SourceMovies": r"C:\Movies", "Custom Key": "Layne's value"})

        self.assertIn("SourceMovies = 'C:\\Movies'", text)
        self.assertIn("'Custom Key' = 'Layne''s value'", text)

    def test_desktop_working_directory_can_import_canonical_app_contract(self) -> None:
        project_root = find_repo_root(Path(__file__))
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        src_root = project_root / "src"
        env["PYTHONPATH"] = (
            str(src_root)
            if not existing_pythonpath
            else str(src_root) + os.pathsep + existing_pythonpath
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import mediapipeline.core.shared.constants; "
                "import mediapipeline.contracts.config; "
                "print('ok')",
            ],
            cwd=project_root / "apps" / "desktop",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=15,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ok")


if __name__ == "__main__":
    unittest.main()

