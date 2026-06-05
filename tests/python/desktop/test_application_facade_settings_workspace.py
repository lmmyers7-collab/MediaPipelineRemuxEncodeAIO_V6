from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.test_application_facade import DummyFacadeService, _resolved


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
        self.assertEqual(settings["policy_impact"]["schema_version"], "settings_policy_impact.v1")
        self.assertEqual(settings["policy_impact"]["evidence_authority"], "backend")
        self.assertEqual(settings["policy_impact"]["launch_risk_handoff"]["schema_version"], "settings_launch_risk_handoff.v1")
        self.assertTrue(settings["policy_impact"]["launch_risk_handoff"]["read_only"])
        self.assertEqual(settings["tool_path_evidence"]["schema_version"], "settings_tool_path_evidence.v1")
        self.assertEqual(settings["tool_path_evidence"]["bdpgs_ocr"]["operator_status"], "Ready")
        self.assertTrue(settings["tool_path_evidence"]["bdpgs_ocr"]["read_only"])
        self.assertEqual(settings["path_health"]["schema_version"], "desktop_configured_path_health.v1")
        self.assertTrue(settings["path_health"]["read_only"])
        self.assertGreaterEqual(settings["path_health"]["row_count"], 1)
        self.assertTrue(any("path health" in warning for warning in settings["warnings"]))
        self.assertEqual(settings["profiles"], ["Default", "DirectPlay"])
        self.assertEqual(settings["profile_summary"]["schema_version"], "desktop_settings_profile_summary.v1")
        self.assertTrue(settings["profile_summary"]["read_only"])
        self.assertFalse(settings["profile_summary"]["webview_profile_operations"]["save_default_profile"])
        self.assertFalse(settings["profile_summary"]["webview_profile_operations"]["load_profile"])
        profile_state_by_id = {state["library_id"]: state for state in settings["library_profile_state"]}
        self.assertGreaterEqual(set(profile_state_by_id), {"movies", "tv"})
        self.assertEqual(profile_state_by_id["movies"]["schema_version"], "library_profile_state.v1")
        self.assertEqual(profile_state_by_id["movies"]["path_fields"]["source_path"]["source_key"], "SourceMovies")
        self.assertEqual(profile_state_by_id["movies"]["path_fields"]["output_path"]["source_key"], "Outsource")
        self.assertIn("RoutingProfile", profile_state_by_id["movies"]["setting_overrides"]["editor"])
        self.assertIn("LocalBase shares a volume", settings["warnings"][0])
        self.assertEqual(settings["paths"]["failed_reports"], str(root / "Logs" / "FailedReports"))
        self.assertEqual(settings["paths"]["audit_reports"], str(root / "AuditReports"))
        self.assertEqual(settings["paths"]["completed_manifest"], str(root / "State" / "completed_jobs.jsonl"))
        size_guard_field = next(field for field in settings["field_definitions"] if field["key"] == "SizeGuardMode")
        self.assertEqual(size_guard_field["choices"], ["advisory", "strict", "off"])
        self.assertEqual(size_guard_field["allowed_values"], ["advisory", "strict", "off"])
        self.assertIn("Blocks publish", size_guard_field["choice_help"]["strict"])
        self.assertEqual(size_guard_field["persisted_key"], "SizeGuardMode")
        self.assertEqual(size_guard_field["override_group"], "editor")
        self.assertEqual(size_guard_field["scope"], "library_overridable")
        self.assertEqual(size_guard_field["value_type"], "string")
        self.assertTrue(size_guard_field["library_override_allowed"])
        self.assertEqual(size_guard_field["default_source"], "field_definition")
        self.assertEqual(size_guard_field["default_value"], "advisory")
        self.assertEqual(size_guard_field["advanced_visibility"], "standard")
        self.assertEqual(size_guard_field["label"], "If encoded output is too large")
        self.assertEqual(size_guard_field["short_label"], "Oversize Action")
        self.assertEqual(size_guard_field["section"], "Size / Bitrate Guards")
        self.assertEqual(size_guard_field["rule_taxonomy"], ["size", "verification"])
        self.assertEqual(size_guard_field["strictness"], "hard")
        self.assertEqual(
            size_guard_field["help_text"],
            "Checked after encode. Warns but does not block in warn-only mode. Blocks publish when configured to block if output exceeds the configured size budget.",
        )
        self.assertEqual(size_guard_field["validation_owner"], "backend")
        self.assertEqual(size_guard_field["runtime_consumer"], "deferred")
        self.assertEqual(size_guard_field["migration_status"], "stable_persisted_key")
        threshold_mode_field = next(field for field in settings["field_definitions"] if field["key"] == "RouteThresholdMode")
        self.assertEqual(threshold_mode_field["section"], "Routing")
        self.assertEqual(threshold_mode_field["label"], "What forces an encode?")
        self.assertEqual(threshold_mode_field["short_label"], "Encode Trigger")
        self.assertEqual(threshold_mode_field["default"], "compatibility_advisory")
        self.assertIn("size_or_bitrate", threshold_mode_field["choices"])
        self.assertEqual(threshold_mode_field["override_group"], "editor")
        movie_bitrate_field = next(field for field in settings["field_definitions"] if field["key"] == "MovieRouteMaxVideoBitrateMbps")
        self.assertEqual(movie_bitrate_field["section"], "Size / Bitrate Guards")
        self.assertEqual(movie_bitrate_field["label"], "Movie fallback max bitrate")
        self.assertEqual(movie_bitrate_field["default"], 35)
        self.assertEqual(movie_bitrate_field["min"], 1)
        self.assertEqual(movie_bitrate_field["max"], 500)
        self.assertEqual(movie_bitrate_field["unit"], "Mbps")
        self.assertEqual(movie_bitrate_field["library_profile_designations"], ["movie", "auto"])
        tv_bitrate_field = next(field for field in settings["field_definitions"] if field["key"] == "TVRouteMaxVideoBitrateMbps")
        self.assertEqual(tv_bitrate_field["section"], "Size / Bitrate Guards")
        self.assertEqual(tv_bitrate_field["label"], "TV fallback max bitrate")
        self.assertEqual(tv_bitrate_field["default"], 18)
        self.assertEqual(tv_bitrate_field["library_profile_designations"], ["tv", "auto"])
        route_1080p_field = next(field for field in settings["field_definitions"] if field["key"] == "Route1080pBucketMaxHeight")
        self.assertEqual(route_1080p_field["section"], "Size / Bitrate Guards")
        self.assertEqual(route_1080p_field["default"], 1200)
        self.assertEqual(route_1080p_field["unit"], "pixels")
        self.assertIn("Compatibility pixel height derived", route_1080p_field["help_text"])
        self.assertNotIn("library_profile_designations", route_1080p_field)
        route_4k_field = next(field for field in settings["field_definitions"] if field["key"] == "Route4KMaxVideoBitrateMbps")
        self.assertEqual(route_4k_field["default"], 35)
        self.assertEqual(route_4k_field["unit"], "Mbps")
        subtitle_field = next(field for field in settings["field_definitions"] if field["key"] == "ConvertTx3gToSrt")
        self.assertEqual(subtitle_field["section"], "Subtitles")
        self.assertIn("mov_text", subtitle_field["help"])
        self.assertIn("TX3G/mov_text", subtitle_field["help_text"])
        self.assertEqual(subtitle_field["override_group"], "subtitles")
        self.assertEqual(subtitle_field["value_type"], "boolean")
        audio_field = next(field for field in settings["field_definitions"] if field["key"] == "AudioPassthroughProfile")
        self.assertEqual(audio_field["section"], "Audio")
        self.assertIn("plex_balanced", audio_field["choices"])
        self.assertIn("plex_balanced", audio_field["allowed_values"])
        self.assertEqual(audio_field["override_group"], "audio")
        self.assertTrue(audio_field["library_override_allowed"])
        self.assertIn("Plex-friendly audio", audio_field["choice_help"]["plex_balanced"])
        video_field = next(field for field in settings["field_definitions"] if field["key"] == "VideoPreset")
        self.assertEqual(video_field["override_group"], "video")
        self.assertEqual(video_field["scope"], "library_overridable")
        self.assertIn("p7", video_field["allowed_values"])
        vobsub_field = next(field for field in settings["field_definitions"] if field["key"] == "ConvertVobSubToSrt")
        self.assertEqual(vobsub_field["persisted_key"], "ConvertVobSubToSrt")
        self.assertEqual(vobsub_field["override_group"], "subtitles")
        self.assertEqual(vobsub_field["scope"], "library_overridable")
        self.assertEqual(vobsub_field["value_type"], "boolean")
        self.assertTrue(vobsub_field["library_override_allowed"])
        self.assertEqual(vobsub_field["short_label"], "VobSub OCR")
        self.assertEqual(vobsub_field["section"], "Subtitles")
        self.assertEqual(vobsub_field["rule_taxonomy"], ["compatibility", "output"])
        vobsub_timeout_field = next(field for field in settings["field_definitions"] if field["key"] == "VobSubOcrTimeoutSeconds")
        self.assertEqual(vobsub_timeout_field["min"], 60)
        self.assertEqual(vobsub_timeout_field["max"], 14400)
        self.assertEqual(vobsub_timeout_field["unit"], "seconds")
        self.assertEqual(vobsub_timeout_field["advanced_visibility"], "advanced")
        self.assertEqual(vobsub_timeout_field["section"], "Advanced")
        self.assertEqual(vobsub_timeout_field["strictness"], "advanced")
        reprocess_field = next(field for field in settings["field_definitions"] if field["key"] == "ReprocessAll")
        self.assertEqual(reprocess_field["section"], "Advanced")
        self.assertIn("one complete pass", reprocess_field["help"])
        self.assertFalse(reprocess_field["library_override_allowed"])
        self.assertIsNone(reprocess_field["override_group"])
        cpu_threads_field = next(field for field in settings["field_definitions"] if field["key"] == "CpuEncodeMaxThreads")
        self.assertEqual(cpu_threads_field["section"], "Advanced")
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

    def test_settings_workspace_reports_backend_policy_impact_launch_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "SizeGuardMode": "off",
                "MaxEncodeGrowthPercent": 5,
                "CompatibilityEncodeGrowthPercent": 15,
                "EncodeThresholdGB": 8,
                "TVEncodeThresholdGB": 3,
                "MovieRouteMaxVideoBitrateMbps": 35,
                "TVRouteMaxVideoBitrateMbps": 18,
                "VideoCodec": "hevc_nvenc",
                "EncodeTuningPreset": "balanced_nvenc",
                "EncodeLadder": "auto",
                "ExtraVideoFlags": ["-legacy"],
                "AllowH264RemuxIfPlexCompatible": False,
                "RemuxSafeVideoCodecs": ["hevc", "h265"],
                "OutputContainer": "mp4",
                "ConvertTx3gToSrt": False,
                "DropTx3gAfterConversion": True,
                "ConvertBdpgsToSrt": True,
                "DropBdpgsAfterConversion": False,
                "DropAssAfterConversion": False,
                "AllowNoAudio": True,
                "DeferredPublish": True,
                "SkipStabilityCheck": True,
                "EnableIntegrityCheck": False,
                "AllowSystemTools": True,
                "SourceMovies": str(root / "Movies"),
                "SourceTV": str(root / "TV"),
                "LocalBase": str(root / "Scratch"),
                "Outsource": str(root / "Output"),
            }
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")

            impact = facade.get_settings_workspace(resolved).to_mapping()["policy_impact"]

        self.assertEqual(impact["schema_version"], "settings_policy_impact.v1")
        launch_risk = impact["launch_risk_handoff"]
        self.assertEqual(launch_risk["schema_version"], "settings_launch_risk_handoff.v1")
        rows = {row["area"]: row for row in launch_risk["rows"]}
        self.assertEqual(rows["Remux / encode size posture"]["impact"], "review")
        self.assertIn("legacy flags=1", rows["Remux / encode size posture"]["evidence"])
        self.assertEqual(rows["Subtitle SRT routing"]["impact"], "blocked")
        self.assertEqual(rows["Audio predictability"]["impact"], "blocked")
        self.assertIn("Backend-authored saved-policy readiness", "\n".join(impact["summary_lines"]))

    def test_settings_workspace_exposes_blocked_config_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.config_identity = {
                "schema_version": "desktop_config_identity.v1",
                "config_path": str(resolved.config_path),
                "blocks_operations": True,
                "status_state": "blocked",
                "operator_status": "Config unavailable",
                "reasons": ["Config file is missing: config.psd1"],
            }
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")

            settings = facade.get_settings_workspace(resolved).to_mapping()

        self.assertEqual(settings["config_identity"]["status_state"], "blocked")
        self.assertTrue(settings["config_identity"]["blocks_operations"])
        self.assertIn("Active config is not a verified operator config.", settings["errors"])
        self.assertIn("Config file is missing", "\n".join(settings["errors"]))

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
