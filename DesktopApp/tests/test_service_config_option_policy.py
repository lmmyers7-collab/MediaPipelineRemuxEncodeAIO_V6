from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.option_policy import validate_option_config


def _option_baseline() -> dict:
    return {
        "OutputContainer": "mkv",
        "EncodeTuningPreset": "balanced_nvenc",
        "EncodeLadder": "auto",
        "RoutingProfile": "plex_direct_stream",
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

    def test_option_policy_reports_enums_lists_and_audio_bitrate(self) -> None:
        values = _option_baseline()
        values.update(
            {
                "OutputContainer": "avi",
                "EncodeLadder": "bad",
                "AudioTranscodeBitrate": "640",
                "ConsoleLogLevel": "TRACE",
                "CompatibleAudioCodecs": [],
                "ValidExtensions": ["mkv"],
                "RobocopyFlags": ["R:3"],
            }
        )
        errors: list[str] = []
        warnings: list[str] = []

        validate_option_config(values, errors, warnings)

        self.assertIn("OutputContainer must be 'mkv' or 'mp4'.", errors)
        self.assertIn("EncodeLadder must be one of: auto, tv_balanced, tv_space_saver, movie_balanced, movie_archive, plex_compat.", errors)
        self.assertIn("AudioTranscodeBitrate must look like 640k.", errors)
        self.assertIn("ConsoleLogLevel must be one of: ERROR, WARN, INFO, DEBUG, or blank.", errors)
        self.assertIn("CompatibleAudioCodecs must contain at least one value.", errors)
        self.assertIn("ValidExtensions entries must start with a dot and contain only extension-safe characters.", errors)
        self.assertIn("RobocopyFlags entries must be non-empty robocopy switches beginning with '/'.", errors)
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
        self.assertIn("Archive Shrink with strict size guard can reject outputs that do not shrink enough; use advisory while tuning.", warnings)

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
