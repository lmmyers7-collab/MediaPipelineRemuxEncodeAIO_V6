from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application.settings_risk_policy import (
    build_launch_settings_risk_handoff,
    build_current_settings_risk_summary,
    build_settings_patch_risk_summary,
    build_settings_policy_impact,
)
from mediapipeline.desktop.application.settings_risk_policy_rules import (
    changed_key_risk_item,
    risk_warning_messages,
    source_mutation_setting,
    summarize_risk_items,
    truthy_setting,
)


class SettingsRiskPolicyRulesTests(unittest.TestCase):
    def test_config_template_keeps_source_mutation_and_unattended_risk_defaults_safe(self) -> None:
        template_path = find_repo_root(Path(__file__)) / "ops" / "pipeline" / "config" / "MediaPipeline_config_template.psd1"
        assignments: dict[str, object] = {}
        for line in template_path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s*(?P<key>[A-Za-z][A-Za-z0-9_]*)\s*=\s*(?P<value>.+?)\s*(?:#.*)?$", line)
            if not match:
                continue
            raw_value = match.group("value").strip()
            if raw_value == "$true":
                value: object = True
            elif raw_value == "$false":
                value = False
            elif raw_value.startswith("'") and raw_value.endswith("'"):
                value = raw_value[1:-1]
            else:
                value = raw_value
            assignments[match.group("key")] = value

        dangerous_source_defaults = {
            key: value
            for key, value in assignments.items()
            if source_mutation_setting(key, value)
        }
        self.assertEqual(dangerous_source_defaults, {})
        self.assertEqual(assignments.get("AllowSystemTools"), False)
        self.assertEqual(assignments.get("SkipStabilityCheck"), False)
        self.assertEqual(assignments.get("EnableIntegrityCheck"), True)
        self.assertEqual(assignments.get("CleanupRemoteStaging"), False)
        self.assertEqual(assignments.get("ReprocessAll"), False)

    def test_truthy_setting_accepts_operator_style_values(self) -> None:
        self.assertTrue(truthy_setting(True))
        self.assertTrue(truthy_setting("enabled"))
        self.assertTrue(truthy_setting(1))
        self.assertFalse(truthy_setting(False))
        self.assertFalse(truthy_setting("disabled"))
        self.assertFalse(truthy_setting(0))

    def test_source_mutation_setting_requires_matching_key_and_danger_value(self) -> None:
        self.assertTrue(source_mutation_setting("DeleteSourceAfterProcessing", True))
        self.assertTrue(source_mutation_setting("default_original_mode", "move"))
        self.assertFalse(source_mutation_setting("SourceMovies", "delete"))
        self.assertFalse(source_mutation_setting("DeleteSourceAfterProcessing", "keep"))

    def test_changed_key_risk_item_classifies_high_risk_settings(self) -> None:
        self.assertEqual(changed_key_risk_item("AllowNoAudio", "yes")["code"], "no_audio_allowed")
        self.assertEqual(changed_key_risk_item("AllowPSystemTools", "on")["code"], "system_tool_fallback")
        self.assertEqual(changed_key_risk_item("SizeGuardMode", "off")["code"], "size_guard_disabled")
        self.assertEqual(changed_key_risk_item("DeleteSourceAfterProcessing", True)["code"], "source_mutation_policy")
        self.assertEqual(changed_key_risk_item("SkipStabilityCheck", True)["code"], "file_stability_check_disabled")
        self.assertEqual(changed_key_risk_item("ValidExtensions", [".mkv", ".part"])["code"], "partial_download_extension_allowed")
        self.assertEqual(changed_key_risk_item("OutputContainer", "mp4")["code"], "mp4_container_limits")
        self.assertEqual(changed_key_risk_item("OutputContainer", "mp4")["severity"], "high")
        self.assertIsNone(changed_key_risk_item("AllowNoAudio", False))

    def test_changed_key_risk_item_classifies_medium_risk_settings(self) -> None:
        self.assertEqual(changed_key_risk_item("SizeGuardMode", "strict")["code"], "strict_size_guard")
        self.assertEqual(changed_key_risk_item("SizeGuardMode", "fallback_remux")["code"], "fallback_remux_size_guard")
        self.assertEqual(changed_key_risk_item("QualityFailAction", "block_review")["code"], "quality_block_review_enabled")
        self.assertEqual(changed_key_risk_item("DropAssAfterConversion", True)["code"], "drops_original_subtitle")
        self.assertEqual(changed_key_risk_item("LocalBase", r"D:\scratch")["code"], "path_root_changed")
        self.assertEqual(changed_key_risk_item("EnableIntegrityCheck", False)["code"], "integrity_check_disabled")
        self.assertEqual(changed_key_risk_item("RobocopyFlags", ["/J", "/MT:16"])["code"], "high_robocopy_thread_count")
        self.assertEqual(changed_key_risk_item("OutputSizeMultiplier", 0.4)["code"], "low_output_size_estimate")

    def test_summarize_risk_items_preserves_counts_highest_and_warning_text(self) -> None:
        items = [
            {"severity": "medium", "code": "path_root_changed", "key": "LocalBase", "message": "changed"},
            {"severity": "high", "code": "source_mutation_policy", "key": "DeleteSource", "message": "danger"},
        ]
        counts, highest = summarize_risk_items(items)
        self.assertEqual(highest, "high")
        self.assertEqual(counts["medium"], 1)
        self.assertEqual(counts["high"], 1)
        self.assertIn("Settings risk [high/source_mutation_policy/DeleteSource]: danger", risk_warning_messages(items))

    def test_build_settings_patch_risk_summary_uses_extracted_rules(self) -> None:
        summary = build_settings_patch_risk_summary(
            {},
            {
                "AllowNoAudio": True,
                "OutputContainer": "mp4",
                "UnknownExperimentalKey": "enabled",
            },
            ["AllowNoAudio", "OutputContainer", "UnknownExperimentalKey"],
            [],
        )
        self.assertEqual(summary["highest_severity"], "high")
        self.assertTrue(any(item["code"] == "unknown_key" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "no_audio_allowed" for item in summary["items"]))
        self.assertTrue(any(item["code"] == "mp4_container_limits" for item in summary["items"]))

    def test_build_current_settings_risk_summary_reports_active_risks_without_path_noise(self) -> None:
        summary = build_current_settings_risk_summary(
            {
                "LocalBase": r"D:\Scratch",
                "SourceTV": r"\\server\TV",
                "SkipStabilityCheck": True,
                "EnableIntegrityCheck": False,
                "ValidExtensions": [".mkv", ".part"],
                "RobocopyFlags": ["/J", "/MT:16"],
            }
        )

        codes = {item["code"] for item in summary["items"]}
        self.assertEqual(summary["schema_version"], "settings_current_risk_summary.v1")
        self.assertEqual(summary["highest_severity"], "high")
        self.assertIn("file_stability_check_disabled", codes)
        self.assertIn("integrity_check_disabled", codes)
        self.assertIn("partial_download_extension_allowed", codes)
        self.assertIn("high_robocopy_thread_count", codes)
        self.assertNotIn("path_root_changed", codes)

    def test_quality_metric_threshold_mismatch_is_high_risk(self) -> None:
        summary = build_current_settings_risk_summary(
            {
                "QualityMetric": "ssim",
                "QualityWarnThreshold": 90,
                "QualityFailThreshold": 75,
            }
        )

        codes = {item["code"] for item in summary["items"]}
        self.assertEqual(summary["highest_severity"], "high")
        self.assertIn("quality_threshold_metric_mismatch", codes)

    def test_build_launch_settings_risk_handoff_matches_existing_launch_rows(self) -> None:
        config = {
            "RoutingProfile": "plex_direct_stream",
            "RouteThresholdMode": "compatibility_advisory",
            "SizeGuardMode": "off",
            "MaxEncodeGrowthPercent": 5,
            "CompatibilityEncodeGrowthPercent": 15,
            "MovieRoute1080pTargetSizeGB": 8,
            "MovieRoute1440pTargetSizeGB": 8,
            "MovieRoute4KTargetSizeGB": 8,
            "TVRoute1080pTargetSizeGB": 3,
            "TVRoute1440pTargetSizeGB": 3,
            "TVRoute4KTargetSizeGB": 3,
            "Route1080pMaxVideoBitrateMbps": 20,
            "Route1440pMaxVideoBitrateMbps": 35,
            "Route4KMaxVideoBitrateMbps": 35,
            "VideoCodec": "hevc_nvenc",
            "EncodeTuningPreset": "balanced_nvenc",
            "EncodeLadder": "auto",
            "ExtraVideoFlags": ["-x-test"],
            "AllowH264RemuxIfPlexCompatible": False,
            "RemuxSafeVideoCodecs": ["hevc", "h265"],
            "OutputContainer": "mp4",
            "ConvertTx3gToSrt": False,
            "DropTx3gAfterConversion": True,
            "ConvertBdpgsToSrt": True,
            "DropBdpgsAfterConversion": False,
            "DropAssAfterConversion": False,
            "AllowNoAudio": True,
            "AudioPassthroughProfile": "plex_balanced",
            "AudioMaxChannels": 6,
            "DeferredPublish": True,
            "SkipStabilityCheck": True,
            "EnableIntegrityCheck": False,
            "AllowSystemTools": True,
            "SourceMovies": r"D:\Movies",
            "SourceTV": r"D:\TV",
            "LocalBase": r"D:\Scratch",
            "Outsource": r"D:\Output",
        }

        handoff = build_launch_settings_risk_handoff(
            config,
            risk_summary=build_current_settings_risk_summary(config),
            errors=["validation failed"],
            warnings=["warning"],
        )

        self.assertEqual(handoff["schema_version"], "settings_launch_risk_handoff.v1")
        self.assertEqual(handoff["evidence_authority"], "backend")
        self.assertTrue(handoff["read_only"])
        rows = {row["area"]: row for row in handoff["rows"]}
        self.assertEqual(rows["Backend settings risk"]["impact"], "blocked")
        self.assertEqual(rows["Publish / pending-drain posture"]["evidence"], "deferred publish=enabled; launch mode={launch_mode}")
        self.assertIn(
            "unknown-height uses 1080p targets movie=8GB, TV=3GB, cap=20Mbps",
            rows["Remux / encode size posture"]["evidence"],
        )
        self.assertIn("legacy flags=1", rows["Remux / encode size posture"]["evidence"])
        self.assertEqual(rows["Subtitle SRT routing"]["impact"], "blocked")
        self.assertEqual(rows["Audio predictability"]["impact"], "blocked")
        self.assertEqual(handoff["continuous_mode_row"]["area"], "Continuous-mode sensitivity")

    def test_build_settings_policy_impact_wraps_backend_readiness_and_launch_risk(self) -> None:
        impact = build_settings_policy_impact({"RoutingProfile": "plex_direct_stream"})

        self.assertEqual(impact["schema_version"], "settings_policy_impact.v1")
        self.assertEqual(impact["evidence_authority"], "backend")
        self.assertEqual(impact["source_route"], "/api/settings/workspace")
        self.assertTrue(impact["read_only"])
        self.assertEqual(impact["media_policy_readiness"]["schema_version"], "settings_media_policy_readiness.v1")
        self.assertEqual(impact["launch_risk_handoff"]["schema_version"], "settings_launch_risk_handoff.v1")


if __name__ == "__main__":
    unittest.main()
