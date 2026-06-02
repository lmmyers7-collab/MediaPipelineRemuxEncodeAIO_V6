from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.service import ConfigProfileServiceMixin
from app.config.validation import (
    config_path_overlap_warning,
    split_list_input,
    validate_config_values,
)


def _path_key(path: Path) -> str:
    return str(path).rstrip("\\/").casefold()


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _valid_config_values() -> dict:
    return {
        "SourceMovies": r"C:\Media\Movies",
        "SourceTV": r"C:\Media\TV",
        "Outsource": r"D:\MediaOut",
        "LocalBase": r"E:\MediaScratch",
        "VideoCodec": "hevc_nvenc",
        "VideoPreset": "p5",
        "OutputContainer": "mkv",
        "EncodeThresholdGB": 8,
        "TVEncodeThresholdGB": 4,
        "MinFreeSpaceGB": 20,
        "OutsourceMinFreeSpaceGB": 20,
        "VideoQuality": 22,
        "MergeThresholdMs": 100,
        "FFmpegEncodeTimeoutSeconds": 3600,
        "FFmpegRemuxTimeoutSeconds": 1800,
        "SubtitleExtractTimeoutSeconds": 300,
        "SubtitleProbeTimeoutSeconds": 30,
        "BdpgsOcrTimeoutSeconds": 1800,
        "VobSubOcrTimeoutSeconds": 1800,
        "TransientFailureRetryLimit": 3,
        "SourceScanIntervalSeconds": 60,
        "ProcessedIndexRefreshSeconds": 120,
        "RobocopyTimeoutSeconds": 3600,
        "SourceScanTimeoutSeconds": 300,
        "IndexScanTimeoutSeconds": 300,
        "CleanupScanTimeoutSeconds": 300,
        "CleanupStaleAgeHours": 24,
        "CompatibleAudioCodecs": ["aac", "ac3", "eac3"],
        "PriorityMarkers": ["[NOW]"],
        "RemuxSafeVideoCodecs": ["h264", "hevc"],
        "SubKeepLanguages": ["eng"],
        "ValidExtensions": [".mkv", ".mp4"],
        "RobocopyFlags": ["/J", "/R:3", "/W:15", "/NP"],
        "EncodeTuningPreset": "balanced_nvenc",
        "EncodeLadder": "auto",
        "RoutingProfile": "plex_direct_stream",
        "SizeGuardMode": "advisory",
        "AudioPassthroughProfile": "custom_codec_list",
        "AudioTranscodeCodec": "eac3",
        "AudioTranscodeBitrate": "640k",
        "AudioDownmixMode": "max_channels",
        "ConsoleLogLevel": "INFO",
        "FileLogLevel": "DEBUG",
    }


class _ConfigValidationWrapperService(ConfigProfileServiceMixin):
    logger = logging.getLogger("test_service_config_validation")

    def _subprocess_kwargs_hidden(self) -> dict:
        return {}

    def resolve_powershell_host(self) -> str:
        return "powershell"

    def _normalized_path_key(self, path: Path) -> str:
        return _path_key(path)

    def _path_within_root(self, path: Path, root: Path) -> bool:
        return _path_within_root(path, root)


class ServiceConfigValidationTests(unittest.TestCase):
    def test_split_list_input_splits_commas_and_newlines(self) -> None:
        self.assertEqual(split_list_input("aac, ac3\r\neac3,, "), ["aac", "ac3", "eac3"])

    def test_validate_config_values_accepts_valid_baseline(self) -> None:
        errors, warnings = validate_config_values(
            _valid_config_values(),
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_validate_config_values_allows_custom_blank_output_but_requires_source(self) -> None:
        values = _valid_config_values()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "name": "Concerts",
                "designation": "auto",
                "enabled": True,
                "source_path": r"C:\Media\Concerts",
                "output_path": "",
            }
        ]

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])
        self.assertTrue(any("mirrors its primary Movie/TV paths" in warning for warning in warnings))

        values["LibraryProfiles"][0]["source_path"] = ""
        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("Library profile Concerts source_path is required.", errors)
        self.assertFalse(any("output_path is required" in error for error in errors))

    def test_validate_config_values_reports_ranges_enums_and_lists(self) -> None:
        values = _valid_config_values()
        values.update(
            {
                "VideoQuality": 99,
                "OutputContainer": "avi",
                "AudioTranscodeBitrate": "640",
                "ConsoleLogLevel": "TRACE",
                "CompatibleAudioCodecs": [],
                "RoutingProfile": "unknown",
                "VideoCodec": "vp9",
                "VideoPreset": "p9",
            }
        )

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("VideoQuality must be <= 51.", errors)
        self.assertIn("OutputContainer must be 'mkv' or 'mp4'.", errors)
        self.assertIn("AudioTranscodeBitrate must look like 640k.", errors)
        self.assertIn("ConsoleLogLevel must be one of: ERROR, WARN, INFO, DEBUG, or blank.", errors)
        self.assertIn("CompatibleAudioCodecs must contain at least one value.", errors)
        self.assertTrue(any(error.startswith("RoutingProfile must be one of:") for error in errors))
        self.assertIn("VideoCodec must be one of: av1_nvenc, h264_nvenc, hevc_nvenc, libx264, libx265.", errors)
        self.assertIn("VideoPreset must be one of: p1, p2, p3, p4, p5, p6, p7.", errors)
        self.assertEqual(warnings, [])

    def test_validate_config_values_rejects_friendly_display_labels_as_persisted_keys(self) -> None:
        values = _valid_config_values()
        values.update(
            {
                "ProcessingStrategy": "manual",
                "OutputSizeCheck": "strict",
                "EnforcementMode": "bitrate",
                "EncoderSpeedPreset": "p6",
            }
        )

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("ProcessingStrategy is a display label only; use persisted key RoutingProfile.", errors)
        self.assertIn("OutputSizeCheck is a display label only; use persisted key SizeGuardMode.", errors)
        self.assertIn("EnforcementMode is a display label only; use persisted key RouteThresholdMode.", errors)
        self.assertIn("EncoderSpeedPreset is a display label only; use persisted key VideoPreset.", errors)

    def test_validate_config_values_rejects_runtime_evidence_as_persisted_keys(self) -> None:
        values = _valid_config_values()
        values.update(
            {
                "library_effective_settings": {"video": {"VideoPreset": "p5"}},
                "runtime_effective_settings": {"folder": {"VideoPreset": "p5"}},
            }
        )

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("library_effective_settings is diagnostic evidence only; it is not a persisted config key.", errors)
        self.assertIn("runtime_effective_settings is diagnostic evidence only; it is not a persisted config key.", errors)

    def test_validate_config_values_accepts_stable_persisted_key_names(self) -> None:
        values = _valid_config_values()
        values.update(
            {
                "RoutingProfile": "manual",
                "RouteThresholdMode": "bitrate",
                "SizeGuardMode": "strict",
            }
        )

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])

    def test_config_path_overlap_warning_reports_same_source_roots(self) -> None:
        warning = config_path_overlap_warning(
            "SourceMovies",
            "SourceTV",
            {"SourceMovies": r"C:\Media", "SourceTV": r"C:\Media"},
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(warning, "SourceMovies and SourceTV point to the same location.")

    def test_validate_config_values_warns_when_scratch_inside_source(self) -> None:
        values = _valid_config_values()
        values["SourceTV"] = r"C:\Media\TV"
        values["LocalBase"] = r"C:\Media\TV\Scratch"

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])
        self.assertIn("LocalBase is inside SourceTV. Keep source, output, and scratch roots separated.", warnings)

    def test_validate_config_values_warns_when_bdpgs_ocr_enabled_without_tool_path(self) -> None:
        values = _valid_config_values()
        values["ConvertBdpgsToSrt"] = True
        values["BdpgsOcrToolPath"] = " "

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])
        self.assertIn(
            "BdpgsOcrToolPath is blank while ConvertBdpgsToSrt is enabled; BDPGS OCR will be blocked until a bundled or configured OCR tool path is saved.",
            warnings,
        )

    def test_validate_config_values_warns_when_vobsub_ocr_enabled_without_tool_path(self) -> None:
        values = _valid_config_values()
        values["ConvertVobSubToSrt"] = True
        values["VobSubOcrToolPath"] = " "

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])
        self.assertIn(
            "VobSubOcrToolPath is blank while ConvertVobSubToSrt is enabled; VobSub OCR will be blocked until Subtitle Edit 4.x SubtitleEdit.exe is configured.",
            warnings,
        )

    def test_service_mixin_preserves_validation_wrapper_methods(self) -> None:
        service = _ConfigValidationWrapperService()

        self.assertEqual(service.split_list_input("eng, spa\njpn"), ["eng", "spa", "jpn"])
        errors, warnings = service.validate_config_values(_valid_config_values())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_save_config_document_rejects_invalid_values_before_write(self) -> None:
        service = _ConfigValidationWrapperService()
        values = _valid_config_values()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Media\Movies",
                "output_path": r"D:\MediaOut",
                "overrides": {"editor": {"ProcessingStrategy": "manual"}},
            },
        ]
        document_text = service.serialize_psd1_document(values)

        with tempfile.TemporaryDirectory() as raw_root:
            config_path = Path(raw_root) / "MediaPipelineConfig.psd1"
            original_text = "@{ RoutingProfile = 'plex_direct_stream' }\n"
            config_path.write_text(original_text, encoding="utf-8")

            with self.assertRaises(ValueError) as raised:
                service.save_config_document(
                    config_path,
                    document_text,
                    True,
                    config_values=values,
                    powershell_host="powershell",
                )

            self.assertEqual(config_path.read_text(encoding="utf-8"), original_text)

        self.assertIn("Config document failed validation before save", str(raised.exception))
        self.assertIn(
            "Library profile Movies override editor.ProcessingStrategy is not a supported library override key.",
            str(raised.exception),
        )


if __name__ == "__main__":
    unittest.main()
