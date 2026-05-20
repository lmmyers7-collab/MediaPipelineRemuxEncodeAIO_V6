from __future__ import annotations

import unittest

from mediapipeline_desktop_app.service_config_preview import build_config_preview


class ServiceConfigPreviewTests(unittest.TestCase):
    def test_preview_preserves_unknown_keys_and_removes_blank_optional_keys(self) -> None:
        preview = build_config_preview(
            {"UnknownKey": "keep", "ConsoleLogLevel": "Info"},
            {"ConsoleLogLevel": "", "VideoCodec": "hevc_nvenc"},
            ["ConsoleLogLevel", "VideoCodec"],
            validate_values=lambda _values: ([], ["warning"]),
            serialize_document=lambda data: f"keys={','.join(sorted(data))}",
        )

        self.assertEqual(preview.errors, [])
        self.assertEqual(preview.warnings, ["warning"])
        self.assertIn("UnknownKey", preview.preserved_keys)
        self.assertNotIn("ConsoleLogLevel", preview.merged_config)
        self.assertEqual(preview.merged_config["VideoCodec"], "hevc_nvenc")
        self.assertIn("ConfigSchemaVersion", preview.merged_config)

    def test_preview_clears_legacy_flags_unless_custom_tuning_is_selected(self) -> None:
        preview = build_config_preview(
            {"ExtraVideoFlags": ["-rc", "vbr"]},
            {"EncodeTuningPreset": "balanced_nvenc"},
            ["ExtraVideoFlags", "EncodeTuningPreset"],
            validate_values=lambda _values: ([], []),
            serialize_document=lambda _data: "preview",
        )

        self.assertEqual(preview.merged_config["ExtraVideoFlags"], [])

    def test_preview_preserves_legacy_flags_when_custom_tuning_is_selected(self) -> None:
        preview = build_config_preview(
            {"ExtraVideoFlags": []},
            {"EncodeTuningPreset": "custom_legacy_flags", "ExtraVideoFlags": ["-cq", "19"]},
            ["ExtraVideoFlags", "EncodeTuningPreset"],
            validate_values=lambda _values: ([], []),
            serialize_document=lambda _data: "preview",
        )

        self.assertEqual(preview.merged_config["ExtraVideoFlags"], ["-cq", "19"])

    def test_preview_expands_managed_audio_passthrough_profile_codecs(self) -> None:
        preview = build_config_preview(
            {"CompatibleAudioCodecs": ["aac"]},
            {"AudioPassthroughProfile": "plex_balanced"},
            ["AudioPassthroughProfile", "CompatibleAudioCodecs"],
            validate_values=lambda _values: ([], []),
            serialize_document=lambda _data: "preview",
        )

        self.assertGreater(len(preview.merged_config["CompatibleAudioCodecs"]), 1)
        self.assertIn("aac", preview.merged_config["CompatibleAudioCodecs"])

    def test_preview_preserves_custom_audio_passthrough_codecs(self) -> None:
        preview = build_config_preview(
            {"CompatibleAudioCodecs": ["aac"]},
            {"AudioPassthroughProfile": "custom_codec_list", "CompatibleAudioCodecs": ["flac", "dts"]},
            ["AudioPassthroughProfile", "CompatibleAudioCodecs"],
            validate_values=lambda _values: ([], []),
            serialize_document=lambda _data: "preview",
        )

        self.assertEqual(preview.merged_config["CompatibleAudioCodecs"], ["flac", "dts"])


if __name__ == "__main__":
    unittest.main()
