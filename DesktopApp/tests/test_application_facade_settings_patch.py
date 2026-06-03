from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from DesktopApp.tests.test_application_facade import DummyFacadeService, _resolved


class ApplicationFacadeSettingsPatchTests(unittest.TestCase):
    def test_settings_patch_preview_uses_backend_config_and_redacts_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "SizeGuardMode": "advisory",
                "ApiToken": "secret-token",
            }

            preview = facade.preview_settings_patch(resolved, {"changes": {"RoutingProfile": "plex_direct_play"}})
            rejected = facade.preview_settings_patch(resolved, {"changes": {"ApiToken": "<redacted>"}})

        self.assertTrue(preview.ok)
        self.assertEqual(preview.command, "settings.preview_patch")
        self.assertIn("RoutingProfile", preview.data["changed_keys"])
        self.assertFalse(preview.data["writes_config"])
        self.assertEqual(preview.data["settings_progress"]["schema_version"], "desktop_settings_save_reload_progress.v1")
        self.assertEqual(preview.data["progress_bars"][0]["id"], "settings_save_reload")
        self.assertEqual(preview.data["progress_bars"][0]["percent"], 20.0)
        diff_text = "\n".join(preview.data["redacted_diff_lines"])
        self.assertIn("plex_direct_play", diff_text)
        self.assertIn("<redacted>", diff_text)
        self.assertNotIn("secret-token", diff_text)
        self.assertEqual(preview.data["risk_summary"]["total_count"], 0)
        self.assertFalse(rejected.ok)
        self.assertIn("redacted display placeholder", "\n".join(rejected.errors))

    def test_settings_redacted_diff_logs_psd1_serialization_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)

            def fail_serialize(_values: dict) -> str:
                raise RuntimeError("serializer offline")

            service.serialize_psd1_document = fail_serialize  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            with self.assertLogs("test_application_facade", level="WARNING") as logs:
                text = facade._redacted_settings_text(facade._redacted_config({"Token": "secret", "A": 1}))

        self.assertIn('"A": 1', text)
        self.assertIn('"Token": "<redacted>"', text)
        self.assertIn("Settings PSD1 serialization failed for redacted diff", "\n".join(logs.output))
        self.assertIn("serializer offline", "\n".join(logs.output))

    def test_settings_patch_preview_reports_risky_settings(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "AllowNoAudio": False,
                "AllowSystemTools": False,
                "SizeGuardMode": "advisory",
                "DropBdpgsAfterConversion": False,
                "OutputContainer": "mkv",
                "ReprocessAll": False,
                "EncodeTuningPreset": "balanced_nvenc",
                "ExtraVideoFlags": [],
            }

            preview = facade.preview_settings_patch(
                resolved,
                {
                    "changes": {
                        "AllowNoAudio": True,
                        "AllowSystemTools": True,
                        "SizeGuardMode": "off",
                        "DropBdpgsAfterConversion": True,
                        "OutputContainer": "mp4",
                        "ReprocessAll": True,
                        "EncodeTuningPreset": "custom_legacy_flags",
                        "ExtraVideoFlags": ["-spatial-aq", "1"],
                        "UnknownExperimentalKey": "enabled",
                    }
                },
            )

        self.assertTrue(preview.ok)
        self.assertEqual(preview.severity, "warning")
        summary = preview.data["risk_summary"]
        self.assertEqual(summary["schema_version"], "settings_patch_risk_summary.v1")
        self.assertEqual(summary["highest_severity"], "high")
        self.assertGreaterEqual(summary["counts"]["high"], 3)
        self.assertTrue(any(item["code"] == "unknown_key" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "no_audio_allowed" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "system_tool_fallback" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "size_guard_disabled" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "full_reprocess_enabled" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "custom_video_flags_enabled" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "raw_video_flags_present" for item in summary["items"]))
        self.assertIn("Settings risk", "\n".join(preview.warnings))

    def test_settings_patch_preview_treats_queue_and_show_policy_keys_as_known_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {}

            preview = facade.preview_settings_patch(
                resolved,
                {
                    "changes": {
                        "MixPriorityPhase": True,
                        "QueueOrderingStrategy": "ManualOrder",
                        "ShowOverrides": {"Example Show": {"VideoCodec": "hevc_nvenc"}},
                    }
                },
            )

        self.assertTrue(preview.ok)
        self.assertEqual(
            sorted(preview.data["changed_keys"]),
            ["MixPriorityPhase", "QueueOrderingStrategy", "ShowOverrides"],
        )
        self.assertFalse(any(item["code"] == "unknown_key" for item in preview.data["risk_summary"]["items"]))

    def test_settings_patch_preview_reports_pending_publish_recovery_risks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "DeferredPublish": False,
                "CleanupRemoteStaging": False,
                "TransientFailureRetryLimit": 3,
                "RobocopyTimeoutSeconds": 14400,
            }

            preview = facade.preview_settings_patch(
                resolved,
                {
                    "changes": {
                        "DeferredPublish": True,
                        "CleanupRemoteStaging": True,
                        "TransientFailureRetryLimit": 12,
                        "RobocopyTimeoutSeconds": 120,
                    }
                },
            )

        self.assertTrue(preview.ok)
        summary = preview.data["risk_summary"]
        codes = {item["code"] for item in summary["items"]}
        self.assertIn("pending_publish_monitor_required", codes)
        self.assertIn("remote_staging_cleanup_enabled", codes)
        self.assertIn("high_transient_retry_limit", codes)
        self.assertIn("short_copy_timeout", codes)
        self.assertEqual(summary["highest_severity"], "medium")
        self.assertIn("remote_staging_cleanup_enabled", "\n".join(preview.warnings))

    def test_settings_patch_preview_reports_audio_subtitle_policy_risks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "PreferredDefaultAudioLanguages": ["english"],
                "CompatibleAudioCodecs": ["aac", "ac3", "eac3"],
                "AudioPassthroughProfile": "plex_balanced",
                "AudioDownmixMode": "max_channels",
                "AudioMaxChannels": 6,
                "SubKeepLanguages": ["eng", "und"],
                "ConvertTx3gToSrt": True,
                "ConvertBdpgsToSrt": True,
            }

            preview = facade.preview_settings_patch(
                resolved,
                {
                    "changes": {
                        "PreferredDefaultAudioLanguages": [],
                        "CompatibleAudioCodecs": [],
                        "AudioPassthroughProfile": "lossless_passthrough",
                        "AudioDownmixMode": "stereo",
                        "AudioMaxChannels": 2,
                        "SubKeepLanguages": [],
                        "ConvertTx3gToSrt": False,
                        "ConvertBdpgsToSrt": False,
                    }
                },
            )

        self.assertTrue(preview.ok)
        summary = preview.data["risk_summary"]
        codes = {item["code"] for item in summary["items"]}
        self.assertIn("empty_default_audio_languages", codes)
        self.assertIn("empty_audio_passthrough_codecs", codes)
        self.assertIn("lossless_audio_passthrough_profile", codes)
        self.assertIn("forced_stereo_downmix", codes)
        self.assertIn("low_audio_channel_cap", codes)
        self.assertIn("empty_subtitle_keep_languages", codes)
        self.assertIn("tx3g_srt_conversion_disabled", codes)
        self.assertIn("bdpgs_srt_conversion_disabled", codes)
        self.assertEqual(summary["highest_severity"], "medium")
        self.assertIn("PreferredDefaultAudioLanguages is empty", "\n".join(preview.warnings))

    def test_settings_save_patch_requires_confirmation_writes_backup_and_preserves_secret(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ RoutingProfile = 'old' }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "ApiToken": "secret-token",
            }

            rejected = facade.save_settings_patch(resolved, {"changes": {"RoutingProfile": "plex_direct_play"}})
            saved = facade.save_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}, "confirm_save": True},
            )
            secret_rejected = facade.save_settings_patch(
                resolved,
                {"changes": {"ApiToken": "<redacted>"}, "confirm_save": True},
            )

            self.assertFalse(rejected.ok)
            self.assertIn("confirmation", rejected.message)
            self.assertTrue(saved.ok)
            self.assertEqual(saved.command, "settings.save_patch")
            self.assertTrue(saved.data["writes_config"])
            self.assertIn("RoutingProfile", saved.data["changed_keys"])
            self.assertEqual(saved.data["risk_summary"]["total_count"], 0)
            self.assertTrue(saved.data["backup_path"])
            self.assertEqual(saved.data["settings_progress"]["schema_version"], "desktop_settings_save_reload_progress.v1")
            self.assertEqual(saved.data["progress_bars"][0]["id"], "settings_save_reload")
            self.assertEqual(saved.data["progress_bars"][0]["percent"], 60.0)
            self.assertEqual(service.saved_config_calls[-1]["config_values"]["ApiToken"], "secret-token")
            self.assertIn("plex_direct_play", config_path.read_text(encoding="utf-8"))
            self.assertFalse(secret_rejected.ok)
            self.assertIn("redacted display placeholder", "\n".join(secret_rejected.errors))

    def test_settings_save_patch_uses_backend_save_lock_before_candidate_build(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}

            self.assertTrue(facade._settings_save_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                result = facade.save_settings_patch(
                    resolved,
                    {"changes": {"RoutingProfile": "plex_direct_play"}, "confirm_save": True},
                )
            finally:
                facade._settings_save_lock.release()  # type: ignore[attr-defined]

        self.assertFalse(result.ok)
        self.assertEqual(result.command, "settings.save_patch")
        self.assertEqual(result.severity, "warning")
        self.assertIn("another settings save command is already in progress", result.message)
        self.assertEqual(service.saved_config_calls, [])

    def test_settings_save_patch_blocks_unverified_active_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}
            resolved.config_identity = {
                "schema_version": "desktop_config_identity.v1",
                "blocks_operations": True,
                "operator_status": "Config requires recovery",
                "reasons": ["Active config matches the deployment template/default paths."],
            }

            result = facade.save_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_play"}, "confirm_save": True},
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.command, "settings.save_patch")
        self.assertEqual(result.severity, "error")
        self.assertIn("not a verified operator config", result.message)
        self.assertFalse(result.data["writes_config"])
        self.assertEqual(service.saved_config_calls, [])

    def test_settings_patch_same_value_is_not_treated_as_changed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ RoutingProfile = 'plex_direct_stream' }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}

            preview = facade.preview_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_stream"}},
            )
            saved = facade.save_settings_patch(
                resolved,
                {"changes": {"RoutingProfile": "plex_direct_stream"}, "confirm_save": True},
            )

        self.assertTrue(preview.ok)
        self.assertEqual(preview.data["changed_keys"], [])
        self.assertEqual(preview.data["redacted_diff_lines"], [])
        self.assertIn("no changes", preview.message)
        self.assertFalse(saved.ok)
        self.assertIn("no changes", saved.message)
        self.assertEqual(service.saved_config_calls, [])

    def test_library_profile_resets_preview_and_save_remove_explicit_state_without_copying_globals(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ LibraryProfiles = @() }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {
                "SourceMovies": r"C:\Incoming\Movies",
                "SourceTV": r"C:\Incoming\TV",
                "Outsource": r"D:\Processed",
                "RoutingProfile": "plex_direct_stream",
                "VideoPreset": "p5",
                "ConvertVobSubToSrt": False,
                "LibraryProfiles": [
                    {
                        "id": "movies",
                        "designation": "movie",
                        "source_path": r"C:\Incoming\Movies",
                        "output_path": r"D:\Processed",
                        "overrides": {
                            "editor": {"RoutingProfile": "manual"},
                            "video": {"VideoPreset": "p5"},
                            "subtitles": {"ConvertVobSubToSrt": True},
                            "audio": {},
                        },
                    },
                    {
                        "id": "concerts",
                        "designation": "auto",
                        "source_path": r"F:\Concerts",
                        "output_path": r"G:\ConcertsProcessed",
                    },
                ],
            }
            request = {
                "changes": {},
                "library_profile_resets": [
                    {
                        "library_id": "movies",
                        "overrides": {
                            "editor": ["RoutingProfile"],
                            "video": ["VideoPreset"],
                            "subtitles": ["ConvertVobSubToSrt"],
                        },
                    },
                    {"library_id": "concerts", "path_fields": ["output_path"]},
                ],
            }

            preview = facade.preview_settings_patch(resolved, request)
            saved = facade.save_settings_patch(resolved, {**request, "confirm_save": True})

        self.assertTrue(preview.ok)
        self.assertIn("LibraryProfiles", preview.data["changed_keys"])
        state_by_id = {state["library_id"]: state for state in preview.data["library_profile_state"]}
        self.assertEqual(state_by_id["concerts"]["path_fields"]["output_path"]["state"], "inherited")
        self.assertTrue(saved.ok)
        profiles = {profile["id"]: profile for profile in service.saved_config_calls[-1]["config_values"]["LibraryProfiles"]}
        movie = profiles["movies"]
        concerts = profiles["concerts"]
        self.assertNotIn("RoutingProfile", movie["overrides"]["editor"])
        self.assertNotIn("VideoPreset", movie["overrides"]["video"])
        self.assertNotIn("ConvertVobSubToSrt", movie["overrides"]["subtitles"])
        self.assertEqual(concerts["output_path"], r"D:\Processed")
        self.assertIn("output_path", concerts["default_tracking"]["inherited_fields"])
        self.assertEqual(concerts["default_tracking"]["field_default_keys"]["output_path"], "Outsource")
