from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.webview_settings_live_smoke import run_smoke


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "DesktopApp"
PIPELINE_PATH = PROJECT_ROOT / "Pipeline" / "MediaPipeline_chatgpt.ps1"


def _ps_quote(path: Path) -> str:
    return str(path).replace("'", "''")


class WebViewSettingsLiveConfigSmokeTests(unittest.TestCase):
    def test_live_config_smoke_contract_runs_against_temp_config_without_mutation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "MediaPipeline_config_chatgpt.psd1"
            local_base = root / "Scratch"
            config_path.write_text(
                "\n".join(
                    [
                        "@{",
                        f"  LocalBase = '{_ps_quote(local_base)}'",
                        f"  SourceMovies = '{_ps_quote(root / 'Movies')}'",
                        f"  SourceTV = '{_ps_quote(root / 'TV')}'",
                        f"  Outsource = '{_ps_quote(root / 'Outsource')}'",
                        "  RoutingProfile = 'plex_direct_stream'",
                        "  SizeGuardMode = 'advisory'",
                        "  VideoCodec = 'hevc_nvenc'",
                        "  OutputContainer = 'mkv'",
                        "  AllowH264RemuxIfPlexCompatible = $true",
                        "  MaxEncodeGrowthPercent = 5",
                        "  CompatibilityEncodeGrowthPercent = 15",
                        "  SubKeepLanguages = @('eng', 'und')",
                        "  Tx3gExtractLanguages = @('eng', 'und')",
                        "  BdpgsExtractLanguages = @('eng', 'und')",
                        "  ConvertTx3gToSrt = $true",
                        "  DropTx3gAfterConversion = $false",
                        "  ConvertBdpgsToSrt = $true",
                        "  DropBdpgsAfterConversion = $false",
                        "  DropAssAfterConversion = $false",
                        "  StripFormatting = $true",
                        "  RemoveKaraoke = $true",
                        "  KeepSignsAndSongs = $true",
                        "  PreferredDefaultAudioLanguages = @('english')",
                        "  AudioPassthroughProfile = 'plex_balanced'",
                        "  CompatibleAudioCodecs = @('aac', 'ac3', 'eac3')",
                        "  AudioDownmixMode = 'max_channels'",
                        "  AudioMaxChannels = 6",
                        "  AllowNoAudio = $false",
                        "  DeferredPublish = $true",
                        "  CleanupRemoteStaging = $false",
                        "  SkipStabilityCheck = $false",
                        "  EnableIntegrityCheck = $true",
                        "  TransientFailureRetryLimit = 3",
                        "  RobocopyTimeoutSeconds = 14400",
                        "  OutsourceMinFreeSpaceGB = 20",
                        "  OutputSizeMultiplier = 1.15",
                        "  WorkerAuthToken = 'worker-secret'",
                        "  CoordinatorAuthToken = ''",
                        "}",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            summary = run_smoke(app_root=APP_ROOT, config_path=config_path, pipeline_path=PIPELINE_PATH)

        self.assertEqual(summary["schema_version"], "webview_settings_live_config_smoke.v1")
        self.assertEqual(summary["config_path"], str(config_path.resolve()))
        self.assertEqual(summary["operator_status"], "Ready")
        self.assertEqual(summary["counts"], {"blocked": 0, "coherent": 10, "review": 0})
        self.assertEqual(summary["review_rows"], [])


if __name__ == "__main__":
    unittest.main()
