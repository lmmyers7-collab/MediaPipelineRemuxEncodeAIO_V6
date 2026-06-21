from __future__ import annotations

import json
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

from pydantic import ValidationError

import mediapipeline.core.config.preset_migration as preset_migration
from mediapipeline.core.config.preset_migration import (
    BLOCKED_FUTURE_PERSISTED_KEYS,
    FRIENDLY_LABEL_PERSISTED_KEY_ALIASES,
    LABEL_ONLY_RENAMES,
    LABEL_ONLY_RENAME_POLICIES,
    LEGACY_COMPATIBILITY_KEY_STATUSES,
    MIGRATION_STATUS_VALUES,
    PERSISTED_KEY_MIGRATION_STATUS,
    effective_decision_policy_from_legacy_or_preset,
    effective_decision_policy_from_preset_v2,
    legacy_config_patch_from_preset_v2,
    preset_v2_from_legacy_config,
)
from mediapipeline.core.config.encoding_capabilities import (
    EncodingCapabilityFacts,
    encoding_capability_facts_from_encoder_rows,
    validate_encoding_capabilities,
)
from mediapipeline.core.config.preset_policy import (
    PRESET_POLICY_WRITE_FORMAT,
    PRESET_POLICY_SCHEMA_VERSION,
    PresetV2,
    preset_v2_validation_issues,
)
from mediapipeline.contracts.source_media import SourceMediaInfo, source_media_from_ffprobe
from mediapipeline.core.decide.processing_decision import decision_policy_from_mapping
from mediapipeline.core.decide.routing import build_processing_decision


REPO_ROOT = find_repo_root(Path(__file__))
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "source_media"


def load_source(name: str) -> SourceMediaInfo:
    raw = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    return source_media_from_ffprobe(raw)


class PresetPolicyContractTests(unittest.TestCase):
    def test_preset_audio_transcode_bitrate_rejects_zero_value(self) -> None:
        with self.assertRaises(ValidationError):
            PresetV2.model_validate({"audio": {"transcodeBitrate": "0k"}})

    def test_migration_policy_declares_label_only_and_legacy_statuses(self) -> None:
        expected_statuses = {
            "stable_persisted_key",
            "label_only_rename",
            "legacy_alias_accepted",
            "deprecated_warn_only",
            "accepted_one_release",
            "accepted_forever",
            "blocked_future_key",
            "migration_deferred",
        }

        self.assertEqual(set(MIGRATION_STATUS_VALUES), expected_statuses)
        for key, label in {
            "RoutingProfile": "Library goal",
            "RouteThresholdMode": "What forces an encode?",
            "SizeGuardMode": "If encoded output is too large",
            "EncodeTuningPreset": "NVENC tuning bundle",
            "EncodeLadder": "How encode targets are calculated",
            "MaxEncodeGrowthPercent": "Quality-encode size tolerance",
            "CompatibilityEncodeGrowthPercent": "Compatibility-encode size tolerance",
            "MovieRoute1080pTargetSizeGB": "Movie 1080p target output size",
            "MovieRoute1440pTargetSizeGB": "Movie 1440p target output size",
            "MovieRoute4KTargetSizeGB": "Movie 4K target output size",
            "TVRoute1080pTargetSizeGB": "TV 1080p target output size",
            "TVRoute1440pTargetSizeGB": "TV 1440p target output size",
            "TVRoute4KTargetSizeGB": "TV 4K target output size",
            "Route1080pUpperHeightTolerancePercent": "1080p upper height tolerance",
            "Route1080pMaxVideoBitrateMbps": "1080p max bitrate for direct copy",
            "Route1440pLowerHeightTolerancePercent": "1440p lower height tolerance",
            "Route1440pUpperHeightTolerancePercent": "1440p upper height tolerance",
            "Route1440pMaxVideoBitrateMbps": "1440p max bitrate for direct copy",
            "Route4KLowerHeightTolerancePercent": "4K lower height tolerance",
            "Route4KMaxVideoBitrateMbps": "4K max bitrate for direct copy",
            "VideoPreset": "Encoder Speed Preset",
            "ExtraVideoFlags": "Advanced Encoder Flags",
            "RemuxSafeVideoCodecs": "Direct Copy Video Codec Allowlist",
        }.items():
            with self.subTest(key=key):
                self.assertEqual(LABEL_ONLY_RENAMES[key], label)
                self.assertEqual(PERSISTED_KEY_MIGRATION_STATUS[key], "stable_persisted_key")

        policies = {str(policy["persisted_key"]): policy for policy in LABEL_ONLY_RENAME_POLICIES}
        self.assertEqual(set(policies), set(LABEL_ONLY_RENAMES))
        for key, policy in policies.items():
            with self.subTest(policy=key):
                self.assertEqual(policy["status"], "label_only_rename")
                self.assertFalse(policy["accepted_as_persisted_key"])

        self.assertEqual(FRIENDLY_LABEL_PERSISTED_KEY_ALIASES["ProcessingStrategy"], "RoutingProfile")
        self.assertEqual(FRIENDLY_LABEL_PERSISTED_KEY_ALIASES["OutputSizeCheck"], "SizeGuardMode")
        self.assertEqual(BLOCKED_FUTURE_PERSISTED_KEYS["ProcessingStrategy"], "blocked_future_key")
        self.assertEqual(LEGACY_COMPATIBILITY_KEY_STATUSES["editor_overrides"], "legacy_alias_accepted")
        self.assertEqual(LEGACY_COMPATIBILITY_KEY_STATUSES["media_overrides"], "legacy_alias_accepted")
        self.assertEqual(LEGACY_COMPATIBILITY_KEY_STATUSES["SourceMovies"], "accepted_forever")

    def test_removed_temporary_helpers_are_not_public_migration_surface(self) -> None:
        self.assertNotIn("blocked_friendly_label_aliases", preset_migration.__all__)
        self.assertNotIn("migration_status_for_persisted_key", preset_migration.__all__)

    def test_legacy_config_migrates_to_preset_v2_and_matching_effective_policy(self) -> None:
        legacy = {
            "RoutingProfile": "plex_direct_play",
            "RouteThresholdMode": "bitrate",
            "MovieRoute1080pTargetSizeGB": 7,
            "MovieRoute1440pTargetSizeGB": 10,
            "MovieRoute4KTargetSizeGB": 14,
            "TVRoute1080pTargetSizeGB": 2,
            "TVRoute1440pTargetSizeGB": 5,
            "TVRoute4KTargetSizeGB": 8,
            "Route1080pUpperHeightTolerancePercent": 9.259259,
            "Route1080pMaxVideoBitrateMbps": 22,
            "Route1440pLowerHeightTolerancePercent": 17.986111,
            "Route1440pUpperHeightTolerancePercent": 23.541667,
            "Route4KLowerHeightTolerancePercent": 17.592593,
            "Route4KMaxVideoBitrateMbps": 36,
            "AllowH264RemuxIfPlexCompatible": True,
            "H264RemuxMaxBitrateMbps": 30,
            "H264RemuxMaxHeight": 720,
            "SizeGuardMode": "strict",
            "OutputContainer": "mp4",
            "RemuxSafeVideoCodecs": ["hevc", "h264"],
            "VideoCodec": "hevc_nvenc",
            "EncodeLadder": "plex_compat",
            "FutureLegacyKey": {"preserve": True},
        }

        preset = preset_v2_from_legacy_config(legacy, name="Legacy compatibility view")
        effective = effective_decision_policy_from_preset_v2(preset)
        direct_effective = decision_policy_from_mapping(
            {
                key: legacy[key]
                for key in (
                    "RoutingProfile",
                    "RouteThresholdMode",
                    "MovieRoute1080pTargetSizeGB",
                    "MovieRoute1440pTargetSizeGB",
                    "MovieRoute4KTargetSizeGB",
                    "TVRoute1080pTargetSizeGB",
                    "TVRoute1440pTargetSizeGB",
                    "TVRoute4KTargetSizeGB",
                    "Route1080pUpperHeightTolerancePercent",
                    "Route1080pMaxVideoBitrateMbps",
                    "Route1440pLowerHeightTolerancePercent",
                    "Route1440pUpperHeightTolerancePercent",
                    "Route4KLowerHeightTolerancePercent",
                    "Route4KMaxVideoBitrateMbps",
                    "AllowH264RemuxIfPlexCompatible",
                    "H264RemuxMaxBitrateMbps",
                    "H264RemuxMaxHeight",
                    "SizeGuardMode",
                    "OutputContainer",
                    "RemuxSafeVideoCodecs",
                )
            }
        )

        self.assertEqual(preset.version, PRESET_POLICY_SCHEMA_VERSION)
        self.assertEqual(preset.name, "Legacy compatibility view")
        self.assertEqual(preset.processing_strategy, "plex_direct_play")
        self.assertEqual(preset.routing.enforcement_mode, "bitrate")
        self.assertEqual(preset.routing.resolution_aware_bitrate.bucket_1080p_max_height, 1180)
        self.assertEqual(preset.routing.resolution_aware_bitrate.bucket_1080p_max_bitrate_mbps, 22)
        self.assertEqual(preset.routing.resolution_aware_bitrate.bucket_4k_min_height, 1780)
        self.assertEqual(preset.routing.resolution_aware_bitrate.bucket_4k_max_bitrate_mbps, 36)
        self.assertEqual(preset.guards.size.movie_route_1080p_size_limit_gb, 7)
        self.assertEqual(preset.guards.size.movie_route_1440p_size_limit_gb, 10)
        self.assertEqual(preset.guards.size.movie_route_4k_size_limit_gb, 14)
        self.assertEqual(preset.guards.size.tv_route_1080p_size_limit_gb, 2)
        self.assertEqual(preset.guards.size.tv_route_1440p_size_limit_gb, 5)
        self.assertEqual(preset.guards.size.tv_route_4k_size_limit_gb, 8)
        self.assertEqual(preset.guards.size.mode, "strict")
        self.assertEqual(preset.guards.size.on_exceeded, "fail_job")
        self.assertEqual(preset.container.format, "mp4")
        self.assertEqual(preset.video.target_selection, "plex_compat")
        self.assertEqual(preset.advanced.legacy_passthrough["FutureLegacyKey"], {"preserve": True})
        self.assertEqual(effective.preferred_default_audio_languages, ["eng"])
        self.assertEqual(effective, direct_effective)

    def test_v2_config_validates_and_feeds_decision_engine(self) -> None:
        preset = PresetV2.model_validate(
            {
                "version": 2,
                "name": "Plex MP4 compatibility",
                "processingStrategy": "plex_direct_stream",
                "routing": {
                    "enforcementMode": "compatibility_advisory",
                    "directCopyMaxBitrate": {"movieMbps": 35, "tvMbps": 18},
                    "directCopyVideoCodecAllowlist": ["hevc", "h265", "h.265"],
                },
                "video": {"codec": "hevc_nvenc", "encoderQualityPreset": "balanced_nvenc"},
                "audio": {"mp4CopyCodecs": ["aac", "ac3", "eac3", "mp3", "alac"]},
                "subtitles": {"mp4CopyCodecs": ["mov_text", "tx3g"]},
                "container": {"format": "mp4", "forceRemux": True},
                "guards": {"size": {"mode": "advisory", "movieRouteSizeLimitGb": 8, "tvRouteSizeLimitGb": 3}},
            }
        )

        effective = effective_decision_policy_from_preset_v2(preset)
        decision = build_processing_decision(load_source("multi_audio_tracks.json"), effective)

        self.assertEqual(effective.output_container, "mp4")
        self.assertEqual(effective.mp4_audio_copy_codecs, ["eac3"])
        self.assertEqual(effective.mp4_subtitle_copy_codecs, [])
        self.assertEqual(decision.effective_settings.output_container, "mp4")
        self.assertEqual(
            {item.stream_index: item.action for item in decision.stream_actions.audio},
            {1: "drop", 2: "copy", 3: "drop"},
        )
        self.assertEqual(decision.route_summary, "REMUX")

    def test_v2_output_size_check_can_request_block_publish(self) -> None:
        preset = PresetV2.model_validate(
            {
                "version": 2,
                "name": "Block publish on oversized output",
                "guards": {"size": {"mode": "advisory", "onExceeded": "block_publish"}},
            }
        )
        effective = effective_decision_policy_from_preset_v2(preset)

        self.assertEqual(preset.guards.size.on_exceeded, "block_publish")
        self.assertEqual(effective.output_size_check_action, "block_publish")

    def test_handbrake_style_encoding_sections_validate(self) -> None:
        preset = PresetV2.model_validate(
            {
                "version": 2,
                "name": "HandBrake style model",
                "dimensions": {
                    "resolutionLimit": "720p",
                    "scalingPolicy": "never_upscale",
                    "aspectPolicy": "preserve_display_aspect",
                    "cropMode": "custom",
                    "pixelAspectMode": "source",
                },
                "filters": {
                    "detelecine": "auto",
                    "deinterlace": "decomb",
                    "denoise": "medium",
                    "sharpen": "low",
                    "deblock": "off",
                    "chromaSmooth": "off",
                    "colorspace": "source",
                },
                "video": {
                    "codec": "hevc_nvenc",
                    "codecFamily": "hevc",
                    "encoderBackend": "nvenc",
                    "targetMode": "constant_quality",
                    "qualityTarget": 23,
                    "framerateMode": "same_as_source",
                    "tune": "film",
                },
                "audio": {"passthroughDefault": True, "forceTranscode": False},
                "subtitles": {"mode": "convert_preferred", "generatePreferredSrt": True},
                "container": {"format": "mkv", "remuxWhenPossible": True},
            }
        )

        self.assertEqual(preset.dimensions.resolution_limit, "720p")
        self.assertEqual(preset.filters.deinterlace, "decomb")
        self.assertEqual(preset.video.target_mode, "constant_quality")
        self.assertEqual(preset.subtitles.mode, "convert_preferred")

    def test_encoding_capability_validation_uses_supplied_facts(self) -> None:
        preset = PresetV2.model_validate(
            {
                "version": 2,
                "name": "Unsupported request",
                "filters": {"denoise": "high"},
                "video": {"codec": "av1_nvenc", "codecFamily": "av1", "encoderBackend": "nvenc"},
            }
        )
        issues = validate_encoding_capabilities(
            preset,
            EncodingCapabilityFacts(
                supported_video_codecs=["h264", "hevc"],
                supported_encoder_backends=["x265"],
                supported_video_filters=["deinterlace"],
            ),
        )
        issue_paths = {issue.path for issue in issues}

        self.assertIn("video.codecFamily", issue_paths)
        self.assertIn("video.encoderBackend", issue_paths)
        self.assertIn("filters.denoise", issue_paths)

    def test_encoding_capability_facts_can_be_derived_from_descriptor_rows(self) -> None:
        facts = encoding_capability_facts_from_encoder_rows(
            [
                {
                    "encoder_name": "hevc_nvenc",
                    "family": "hevc",
                    "backend": "nvenc",
                    "available": True,
                },
                {
                    "encoder_name": "libx265",
                    "family": "hevc",
                    "backend": "cpu",
                    "available": True,
                },
                {
                    "encoder_name": "libaom-av1",
                    "family": "av1",
                    "backend": "cpu",
                    "available": True,
                },
                {
                    "encoder_name": "h264_qsv",
                    "family": "h264",
                    "backend": "qsv",
                    "available": False,
                },
            ]
        )

        self.assertEqual(facts.supported_video_codecs, ["av1", "h265", "hevc"])
        self.assertEqual(facts.supported_encoder_backends, ["copy", "cpu", "libaom", "nvenc", "x265"])

        issues = validate_encoding_capabilities(
            {
                "version": 2,
                "name": "QSV request",
                "video": {"codec": "h264_qsv", "codecFamily": "h264", "encoderBackend": "qsv"},
            },
            facts,
        )

        self.assertEqual([issue.path for issue in issues], ["video.codecFamily", "video.encoderBackend"])

    def test_legacy_or_preset_adapter_reads_both_shapes(self) -> None:
        legacy_effective = effective_decision_policy_from_legacy_or_preset({"OutputContainer": "mp4"})
        preset_effective = effective_decision_policy_from_legacy_or_preset(
            {
                "version": 2,
                "name": "V2",
                "container": {"format": "mp4"},
            }
        )

        self.assertEqual(legacy_effective.output_container, "mp4")
        self.assertEqual(preset_effective.output_container, "mp4")

    def test_validation_issues_use_user_facing_sections(self) -> None:
        issues = preset_v2_validation_issues(
            {
                "version": 2,
                "name": "Invalid",
                "routing": {"enforcementMode": "definitely-not-valid"},
                "video": {"codec": ""},
                "container": {"format": "avi"},
            }
        )
        sections = {issue.section for issue in issues}
        paths = {issue.path for issue in issues}

        self.assertIn("Routing", sections)
        self.assertIn("Video", sections)
        self.assertIn("Container", sections)
        self.assertIn("routing.enforcementMode", paths)
        self.assertIn("video.codec", paths)
        self.assertIn("container.format", paths)

    def test_source_facts_are_rejected_from_persisted_presets(self) -> None:
        issues = preset_v2_validation_issues(
            {
                "version": 2,
                "name": "Invalid source facts",
                "sourceFacts": {"codec": "h264"},
            }
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].section, "Preset")
        self.assertIn("source facts are read-only", issues[0].message)

    def test_unknown_future_fields_round_trip(self) -> None:
        preset = PresetV2.model_validate(
            {
                "version": 2,
                "name": "Future tolerant",
                "futureTopLevel": {"keep": True},
                "routing": {
                    "futureRoutingField": "preserved",
                },
            }
        )
        dumped = preset.model_dump(by_alias=True)

        self.assertEqual(dumped["futureTopLevel"], {"keep": True})
        self.assertEqual(dumped["routing"]["futureRoutingField"], "preserved")

    def test_rollout_write_target_remains_legacy_until_cutover(self) -> None:
        self.assertEqual(PRESET_POLICY_WRITE_FORMAT, "legacy")

    def test_preset_v2_adapter_emits_stable_legacy_keys_not_display_aliases(self) -> None:
        patch = legacy_config_patch_from_preset_v2(
            {
                "version": 2,
                "name": "Legacy writer",
                "processingStrategy": "plex_direct_play",
                "routing": {
                    "enforcementMode": "bitrate",
                    "directCopyMaxBitrate": {"movieMbps": 40, "tvMbps": 20},
                    "resolutionAwareBitrate": {
                        "bucket1080pUpperHeightTolerancePct": 9.259259,
                        "bucket1080pMaxBitrateMbps": 22,
                        "bucket1440pLowerHeightTolerancePct": 17.986111,
                        "bucket1440pUpperHeightTolerancePct": 23.541667,
                        "bucket4kLowerHeightTolerancePct": 17.592593,
                        "bucket4kMaxBitrateMbps": 36,
                    },
                    "directCopyVideoCodecAllowlist": ["hevc", "h264"],
                },
                "guards": {
                    "size": {
                        "mode": "strict",
                        "qualityEncodeGrowthTolerancePct": 7,
                        "compatibilityEncodeGrowthTolerancePct": 12,
                        "movieRouteSizeLimitGb": 9,
                        "tvRouteSizeLimitGb": 4,
                    }
                },
                "video": {
                    "codec": "hevc_nvenc",
                    "encoderSpeedPreset": "p6",
                    "encoderQualityPreset": "quality_nvenc",
                    "targetSelection": "plex_compat",
                },
                "container": {"format": "mp4"},
                "advanced": {"extraVideoFlags": ["-spatial-aq", "1"]},
            }
        )

        self.assertEqual(patch["RoutingProfile"], "plex_direct_play")
        self.assertEqual(patch["RouteThresholdMode"], "bitrate")
        self.assertEqual(patch["SizeGuardMode"], "strict")
        self.assertEqual(patch["EncodeTuningPreset"], "quality_nvenc")
        self.assertEqual(patch["EncodeLadder"], "plex_compat")
        self.assertEqual(patch["MaxEncodeGrowthPercent"], 7)
        self.assertEqual(patch["CompatibilityEncodeGrowthPercent"], 12)
        self.assertEqual(patch["MovieRoute1080pTargetSizeGB"], 9)
        self.assertEqual(patch["MovieRoute1440pTargetSizeGB"], 9)
        self.assertEqual(patch["MovieRoute4KTargetSizeGB"], 9)
        self.assertEqual(patch["TVRoute1080pTargetSizeGB"], 4)
        self.assertEqual(patch["TVRoute1440pTargetSizeGB"], 4)
        self.assertEqual(patch["TVRoute4KTargetSizeGB"], 4)
        self.assertAlmostEqual(patch["Route1080pUpperHeightTolerancePercent"], 9.259259)
        self.assertEqual(patch["Route1080pMaxVideoBitrateMbps"], 22)
        self.assertAlmostEqual(patch["Route1440pLowerHeightTolerancePercent"], 17.986111)
        self.assertAlmostEqual(patch["Route1440pUpperHeightTolerancePercent"], 23.541667)
        self.assertAlmostEqual(patch["Route4KLowerHeightTolerancePercent"], 17.592593)
        self.assertEqual(patch["Route4KMaxVideoBitrateMbps"], 36)
        self.assertEqual(patch["VideoPreset"], "p6")
        self.assertEqual(patch["OutputContainer"], "mp4")
        self.assertEqual(patch["RemuxSafeVideoCodecs"], ["hevc", "h264"])
        for alias in (
            "ProcessingStrategy",
            "EnforcementMode",
            "OutputSizeCheck",
            "EncoderQualityPreset",
            "EncodeTargetMode",
            "EncoderSpeedPreset",
            "DirectCopyVideoCodecAllowlist",
        ):
            self.assertNotIn(alias, patch)

    def test_preset_v2_legacy_patch_validation_uses_current_config_contract(self) -> None:
        with self.assertRaises(Exception):
            legacy_config_patch_from_preset_v2(
                {
                    "version": 2,
                    "name": "Invalid legacy patch",
                    "routing": {"resolutionAwareBitrate": {"bucket1080pMaxBitrateMbps": 0}},
                }
            )


if __name__ == "__main__":
    unittest.main()
