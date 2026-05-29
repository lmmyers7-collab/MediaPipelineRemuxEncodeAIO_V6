from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from DesktopApp.tests.test_application_facade import DummyFacadeService, _resolved


class ProfileSummaryService(DummyFacadeService):
    def __init__(self, root: Path, profile_config: dict[str, object]) -> None:
        super().__init__(root)
        self.profile_config = dict(profile_config)
        self.loaded_profile_path: Path | None = None

    def load_config_data(self, config_path: Path, powershell_host: str | None) -> dict[str, object]:
        _ = powershell_host
        self.loaded_profile_path = config_path
        return dict(self.profile_config)


class ApplicationFacadeSettingsWorkspaceTests(unittest.TestCase):
    def test_settings_workspace_redacts_tokens_and_reports_validation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.local_base = root / "Scratch"
            resolved.source_tv = root / "TV"
            resolved.failed_reports_path = root / "Logs" / "FailedReports"
            resolved.failed_markers_path = root / "State" / "FailedMarkers"
            resolved.audit_reports_path = root / "AuditReports"
            resolved.completed_manifest_path = root / "State" / "completed_jobs.jsonl"
            bdpgs_tool = root / "Tools" / "PgsToSrt" / "PgsToSrt.exe"
            bdpgs_tessdata = root / "Tools" / "PgsToSrt" / "tessdata"
            bdpgs_tool.parent.mkdir(parents=True)
            bdpgs_tool.write_text("fake", encoding="utf-8")
            bdpgs_tessdata.mkdir()
            resolved.config_data = {
                "LocalBase": str(root / "Scratch"),
                "SourceTV": str(root / "TV"),
                "RoutingProfile": "plex_direct_stream",
                "SkipStabilityCheck": True,
                "ConvertBdpgsToSrt": True,
                "BdpgsOcrToolPath": r"Tools\PgsToSrt\PgsToSrt.exe",
                "BdpgsOcrTessdataPath": r"Tools\PgsToSrt\tessdata",
                "WorkerAuthToken": "secret-value",
            }
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")

            settings = facade.get_settings_workspace(resolved).to_mapping()

        self.assertEqual(settings["schema_version"], "desktop_settings_workspace.v1")
        self.assertEqual(settings["config"]["WorkerAuthToken"], "<redacted>")
        self.assertEqual(settings["config"]["RoutingProfile"], "plex_direct_stream")
        self.assertEqual(settings["risk_summary"]["schema_version"], "settings_current_risk_summary.v1")
        self.assertTrue(any(item["code"] == "file_stability_check_disabled" for item in settings["risk_summary"]["items"]))
        self.assertEqual(settings["media_policy_readiness"]["schema_version"], "settings_media_policy_readiness.v1")
        self.assertTrue(settings["media_policy_readiness"]["read_only"])
        self.assertEqual(settings["tool_path_evidence"]["schema_version"], "settings_tool_path_evidence.v1")
        self.assertEqual(settings["tool_path_evidence"]["bdpgs_ocr"]["operator_status"], "Ready")
        self.assertTrue(settings["tool_path_evidence"]["bdpgs_ocr"]["read_only"])
        self.assertEqual(settings["profiles"], ["Default", "DirectPlay"])
        self.assertEqual(settings["profile_summary"]["schema_version"], "desktop_settings_profile_summary.v1")
        self.assertTrue(settings["profile_summary"]["read_only"])
        self.assertFalse(settings["profile_summary"]["webview_profile_operations"]["save_default_profile"])
        self.assertFalse(settings["profile_summary"]["webview_profile_operations"]["load_profile"])
        self.assertIn("LocalBase shares a volume", settings["warnings"][0])
        self.assertEqual(settings["paths"]["failed_reports"], str(root / "Logs" / "FailedReports"))
        self.assertEqual(settings["paths"]["audit_reports"], str(root / "AuditReports"))
        self.assertEqual(settings["paths"]["completed_manifest"], str(root / "State" / "completed_jobs.jsonl"))
        size_guard_field = next(field for field in settings["field_definitions"] if field["key"] == "SizeGuardMode")
        self.assertEqual(size_guard_field["choices"], ["advisory", "strict", "off"])
        self.assertIn("Reject oversized encodes", size_guard_field["choice_help"]["strict"])
        movie_bitrate_field = next(field for field in settings["field_definitions"] if field["key"] == "MovieRouteMaxVideoBitrateMbps")
        self.assertEqual(movie_bitrate_field["section"], "Routing")
        self.assertEqual(movie_bitrate_field["default"], 35)
        tv_bitrate_field = next(field for field in settings["field_definitions"] if field["key"] == "TVRouteMaxVideoBitrateMbps")
        self.assertEqual(tv_bitrate_field["section"], "Routing")
        self.assertEqual(tv_bitrate_field["default"], 18)
        subtitle_field = next(field for field in settings["field_definitions"] if field["key"] == "ConvertTx3gToSrt")
        self.assertEqual(subtitle_field["section"], "TX3G Subtitles")
        self.assertIn("mov_text", subtitle_field["help"])
        audio_field = next(field for field in settings["field_definitions"] if field["key"] == "AudioPassthroughProfile")
        self.assertEqual(audio_field["section"], "Audio")
        self.assertIn("plex_balanced", audio_field["choices"])
        self.assertIn("Plex-friendly audio", audio_field["choice_help"]["plex_balanced"])
        reprocess_field = next(field for field in settings["field_definitions"] if field["key"] == "ReprocessAll")
        self.assertEqual(reprocess_field["section"], "Queue")
        self.assertIn("one complete pass", reprocess_field["help"])
        cpu_threads_field = next(field for field in settings["field_definitions"] if field["key"] == "CpuEncodeMaxThreads")
        self.assertEqual(cpu_threads_field["section"], "Remux / Safety")
        self.assertIn("libx265 threads", cpu_threads_field["help"])

    def test_settings_workspace_reports_backend_media_policy_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "SizeGuardMode": "off",
                "OutputContainer": "mp4",
                "MaxEncodeGrowthPercent": 5,
                "CompatibilityEncodeGrowthPercent": 15,
                "SubKeepLanguages": [],
                "Tx3gExtractLanguages": ["eng"],
                "BdpgsExtractLanguages": ["eng"],
                "ConvertTx3gToSrt": False,
                "DropTx3gAfterConversion": True,
                "ConvertBdpgsToSrt": False,
                "DropBdpgsAfterConversion": True,
                "DropAssAfterConversion": False,
                "StripFormatting": True,
                "RemoveKaraoke": True,
                "KeepSignsAndSongs": True,
                "PreferredDefaultAudioLanguages": [],
                "AudioPassthroughProfile": "lossless_passthrough",
                "CompatibleAudioCodecs": ["aac", "ac3"],
                "AudioDownmixMode": "stereo",
                "AudioMaxChannels": 2,
                "AllowNoAudio": True,
                "DeferredPublish": True,
                "CleanupRemoteStaging": True,
                "SkipStabilityCheck": True,
                "EnableIntegrityCheck": False,
                "TransientFailureRetryLimit": 12,
                "RobocopyTimeoutSeconds": 120,
                "OutsourceMinFreeSpaceGB": 2,
                "OutputSizeMultiplier": 0.25,
                "DeleteSourceAfterProcessing": True,
            }
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")

            readiness = facade.get_settings_workspace(resolved).to_mapping()["media_policy_readiness"]

        self.assertEqual(readiness["schema_version"], "settings_media_policy_readiness.v1")
        self.assertEqual(readiness["operator_status"], "Blocked review")
        self.assertTrue(readiness["read_only"])
        self.assertGreaterEqual(readiness["counts"]["blocked"], 3)
        rows = {row["area"]: row for row in readiness["rows"]}
        self.assertEqual(rows["TX3G / mov_text SRT"]["posture"], "blocked")
        self.assertEqual(rows["BDPGS OCR to SRT"]["posture"], "blocked")
        self.assertEqual(rows["Audio passthrough / channels"]["posture"], "blocked")
        self.assertEqual(rows["Source preservation"]["posture"], "blocked")
        self.assertIn("DeleteSourceAfterProcessing", rows["Source preservation"]["keys"])
        self.assertIn("Backend media-policy readiness:", "\n".join(readiness["summary_lines"]))

    def test_settings_workspace_compares_default_profile_without_exposing_values(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            profile_dir = resolved.config_path.parent / "Profiles"
            profile_dir.mkdir()
            default_profile = profile_dir / "Default.psd1"
            default_profile.write_text("@{}", encoding="utf-8")
            resolved.config_data = {
                "LocalBase": str(root / "Scratch"),
                "DeferredPublish": False,
                "RemuxSafeVideoCodecs": ["hevc", "av1"],
                "WorkerAuthToken": "current-secret",
            }
            service = ProfileSummaryService(
                root,
                {
                    "LocalBase": str(root / "Scratch").replace("\\", "/"),
                    "DeferredPublish": True,
                    "RemuxSafeVideoCodecs": ["hevc"],
                    "WorkerAuthToken": "profile-secret",
                },
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            summary = facade.get_settings_workspace(resolved).to_mapping()["profile_summary"]

        self.assertEqual(service.loaded_profile_path, default_profile)
        self.assertEqual(summary["schema_version"], "desktop_settings_profile_summary.v1")
        self.assertEqual(summary["default_profile_status"], "differs_from_current")
        self.assertEqual(summary["default_profile_status_state"], "warning")
        self.assertEqual(summary["mismatch_count"], 3)
        self.assertEqual(summary["mismatch_keys"], ["DeferredPublish", "RemuxSafeVideoCodecs", "WorkerAuthToken"])
        self.assertIn("Default profile status: differs from current settings", "\n".join(summary["summary_lines"]))
        self.assertNotIn("current-secret", "\n".join(summary["summary_lines"]))
        self.assertNotIn("profile-secret", "\n".join(summary["summary_lines"]))
        self.assertFalse(summary["webview_profile_operations"]["save_default_profile"])

    def test_settings_validate_uses_command_result_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")

            result = facade.validate_settings_values(
                {"values": {"LocalBase": str(root / "Scratch"), "SourceTV": str(root / "TV")}}
            ).to_mapping()

        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "settings.validate")
        self.assertTrue(result["ok"])
        self.assertEqual(result["severity"], "warning")
        self.assertEqual(result["data"]["key_count"], 2)
