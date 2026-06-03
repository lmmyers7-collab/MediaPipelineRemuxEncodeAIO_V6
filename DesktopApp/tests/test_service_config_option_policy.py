from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config.metadata_parts.field_definitions import CONFIG_FIELD_DEFINITIONS
from app.config.option_policy import validate_option_config
from app.config.constants import (
    AUDIO_PASSTHROUGH_PROFILE_NAMES,
    LOG_LEVEL_VALUES,
    ROUTE_THRESHOLD_MODE_NAMES,
    ROUTING_PROFILE_NAMES,
    SIZE_GUARD_MODE_NAMES,
)


def _metadata_by_key() -> dict[str, dict[str, object]]:
    return {str(field["key"]): field for field in CONFIG_FIELD_DEFINITIONS}


def _option_baseline() -> dict:
    return {
        "OutputContainer": "mkv",
        "EncodeTuningPreset": "balanced_nvenc",
        "EncodeLadder": "auto",
        "RoutingProfile": "plex_direct_stream",
        "RouteThresholdMode": "compatibility_advisory",
        "SizeGuardMode": "advisory",
        "AudioPassthroughProfile": "custom_codec_list",
        "AudioTranscodeCodec": "eac3",
        "AudioTranscodeBitrate": "640k",
        "AudioDownmixMode": "max_channels",
        "CompatibleAudioCodecs": ["aac", "ac3", "eac3"],
        "PriorityMarkers": ["[NOW]"],
        "RemuxSafeVideoCodecs": ["h264", "hevc"],
        "SubKeepLanguages": ["eng"],
        "ValidExtensions": [".mkv", ".mp4", ".m2ts"],
        "RobocopyFlags": ["/J", "/R:3", "/W:15", "/NP"],
        "ConsoleLogLevel": "INFO",
        "FileLogLevel": "DEBUG",
    }


class ServiceConfigOptionPolicyTests(unittest.TestCase):
    def test_option_policy_accepts_baseline(self) -> None:
        errors: list[str] = []
        warnings: list[str] = []

        validate_option_config(_option_baseline(), errors, warnings)

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_backend_metadata_allowed_values_match_option_policy_enums(self) -> None:
        metadata = _metadata_by_key()
        expected_allowed_values = {
            "OutputContainer": ("mkv", "mp4"),
            "EncodeTuningPreset": (
                "balanced_nvenc",
                "quality_nvenc",
                "fast_nvenc",
                "compatibility",
                "custom_legacy_flags",
            ),
            "EncodeLadder": (
                "auto",
                "tv_balanced",
                "tv_space_saver",
                "movie_balanced",
                "movie_archive",
                "plex_compat",
            ),
            "RoutingProfile": ROUTING_PROFILE_NAMES,
            "RouteThresholdMode": ROUTE_THRESHOLD_MODE_NAMES,
            "SizeGuardMode": SIZE_GUARD_MODE_NAMES,
            "VideoCodec": ("hevc_nvenc", "libx265", "h264_nvenc", "libx264", "av1_nvenc"),
            "VideoPreset": ("p1", "p2", "p3", "p4", "p5", "p6", "p7"),
            "FinalLibraryPromotionVerificationMode": ("cautious", "fast"),
            "AudioPassthroughProfile": AUDIO_PASSTHROUGH_PROFILE_NAMES,
            "AudioTranscodeCodec": ("eac3", "ac3", "aac"),
            "AudioTranscodeBitrate": ("384k", "448k", "640k", "768k"),
            "AudioDownmixMode": ("max_channels", "preserve", "stereo"),
            "ConsoleLogLevel": LOG_LEVEL_VALUES,
            "FileLogLevel": LOG_LEVEL_VALUES,
        }

        for key, expected in expected_allowed_values.items():
            with self.subTest(key=key):
                self.assertEqual(tuple(metadata[key]["allowed_values"]), tuple(expected))

    def test_option_policy_reports_enums_lists_and_audio_bitrate(self) -> None:
        values = _option_baseline()
        values.update(
            {
                "OutputContainer": "avi",
                "EncodeLadder": "bad",
                "RouteThresholdMode": "all",
                "AudioTranscodeBitrate": "640",
                "ConsoleLogLevel": "TRACE",
                "CompatibleAudioCodecs": [],
                "ValidExtensions": ["mkv"],
                "RobocopyFlags": ["R:3"],
                "VideoCodec": "vp9",
                "VideoPreset": "p9",
            }
        )
        errors: list[str] = []
        warnings: list[str] = []

        validate_option_config(values, errors, warnings)

        self.assertIn("OutputContainer must be 'mkv' or 'mp4'.", errors)
        self.assertIn("EncodeLadder must be one of: auto, tv_balanced, tv_space_saver, movie_balanced, movie_archive, plex_compat.", errors)
        self.assertIn("RouteThresholdMode must be one of: compatibility_advisory, size, bitrate, size_or_bitrate.", errors)
        self.assertIn("AudioTranscodeBitrate must be a positive ffmpeg bitrate like 640k.", errors)
        self.assertIn("ConsoleLogLevel must be one of: ERROR, WARN, INFO, DEBUG, or blank.", errors)
        self.assertIn("CompatibleAudioCodecs must contain at least one value.", errors)
        self.assertIn("ValidExtensions entries must start with a dot and contain only extension-safe characters.", errors)
        self.assertIn("RobocopyFlags entries must be non-empty robocopy switches beginning with '/'.", errors)
        self.assertIn("VideoCodec must be one of: av1_nvenc, h264_nvenc, hevc_nvenc, libx264, libx265.", errors)
        self.assertIn("VideoPreset must be one of: p1, p2, p3, p4, p5, p6, p7.", errors)
        self.assertEqual(warnings, [])

    def test_option_policy_rejects_zero_audio_transcode_bitrate(self) -> None:
        values = _option_baseline()
        values["AudioTranscodeBitrate"] = "0k"
        errors: list[str] = []
        warnings: list[str] = []

        validate_option_config(values, errors, warnings)

        self.assertIn("AudioTranscodeBitrate must be a positive ffmpeg bitrate like 640k.", errors)
        self.assertEqual(warnings, [])

    def test_option_policy_warns_on_ignored_custom_flags_and_strict_archive(self) -> None:
        values = _option_baseline()
        values.update(
            {
                "ExtraVideoFlags": ["-cq", "19"],
                "RoutingProfile": "archive_shrink",
                "SizeGuardMode": "strict",
            }
        )
        errors: list[str] = []
        warnings: list[str] = []

        validate_option_config(values, errors, warnings)

        self.assertEqual(errors, [])
        self.assertIn("ExtraVideoFlags are ignored unless EncodeTuningPreset is custom_legacy_flags; Save In Place will write an empty ExtraVideoFlags list.", warnings)
        self.assertIn("Archive Shrink with strict Output Size Check can reject outputs that do not shrink enough; use advisory while tuning.", warnings)

    def test_option_policy_warns_when_structured_audio_profile_reconciles_custom_codecs(self) -> None:
        values = _option_baseline()
        values.update(
            {
                "AudioPassthroughProfile": "compatibility",
                "CompatibleAudioCodecs": ["flac", "dts"],
            }
        )
        errors: list[str] = []
        warnings: list[str] = []

        validate_option_config(values, errors, warnings)

        self.assertEqual(errors, [])
        self.assertIn("CompatibleAudioCodecs are controlled by AudioPassthroughProfile unless it is custom_codec_list; Save In Place will write the selected profile codec list.", warnings)


if __name__ == "__main__":
    unittest.main()
