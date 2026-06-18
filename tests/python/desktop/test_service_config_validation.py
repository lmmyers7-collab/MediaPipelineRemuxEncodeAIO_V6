from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.contracts.config import Config
from mediapipeline.core.config.service import ConfigProfileServiceMixin
from mediapipeline.core.config.validation import (
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
        "MovieRoute1080pTargetSizeGB": 8,
        "MovieRoute1440pTargetSizeGB": 10,
        "MovieRoute4KTargetSizeGB": 12,
        "TVRoute1080pTargetSizeGB": 4,
        "TVRoute1440pTargetSizeGB": 6,
        "TVRoute4KTargetSizeGB": 8,
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
        "CoordinatorMaxJobRetries": 3,
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

    def test_validate_config_values_rejects_case_variant_canonical_keys(self) -> None:
        values = _valid_config_values()
        values["routingprofile"] = "not-a-real-choice"

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("Invalid settings key: 'routingprofile'; use canonical key RoutingProfile.", errors)
        self.assertIn(
            "Config contains duplicate keys for RoutingProfile: 'RoutingProfile' and 'routingprofile'; use only canonical key RoutingProfile.",
            errors,
        )
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
                "AudioTranscodeBitrate": "0k",
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
        self.assertIn("AudioTranscodeBitrate must be a positive ffmpeg bitrate like 640k.", errors)
        self.assertIn("ConsoleLogLevel must be one of: ERROR, WARN, INFO, DEBUG, or blank.", errors)
        self.assertIn("CompatibleAudioCodecs must contain at least one value.", errors)
        self.assertTrue(any(error.startswith("RoutingProfile must be one of:") for error in errors))
        self.assertIn(
            "VideoCodec must be one of: av1_amf, av1_nvenc, av1_qsv, h264_amf, "
            "h264_nvenc, h264_qsv, hevc_amf, hevc_nvenc, hevc_qsv, libaom-av1, "
            "libx264, libx265.",
            errors,
        )
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

    def test_validate_config_values_materializes_defaulted_network_numeric_keys(self) -> None:
        values = _valid_config_values()
        values.pop("CoordinatorMaxJobRetries")

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_validate_config_values_rejects_explicit_invalid_network_retry_count(self) -> None:
        values = _valid_config_values()
        values["CoordinatorMaxJobRetries"] = 0

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("CoordinatorMaxJobRetries must be >= 1.", errors)

    def test_config_contract_rejects_strict_rename_filter_json_text(self) -> None:
        cases = [
            (
                "RenameMovieFilterOptions",
                '{"sample": true, "sample": false}',
                "duplicate JSON object key: sample",
            ),
            (
                "RenameMovieFilterOptions",
                '{"sample": NaN}',
                "non-finite JSON value is not allowed: NaN",
            ),
            (
                "RenameMovieFilterTerms",
                '{"sample": ["alpha"], "sample": ["beta"]}',
                "duplicate JSON object key: sample",
            ),
        ]
        for key, raw, expected in cases:
            with self.subTest(key=key, raw=raw):
                with self.assertRaises(ValidationError) as raised:
                    Config.model_validate({**_valid_config_values(), key: raw})
                self.assertIn(expected, str(raised.exception))

    def test_validate_config_values_rejects_strict_promotion_rule_json_text(self) -> None:
        cases = [
            (
                '[{"id": "first", "id": "second"}]',
                "duplicate JSON object key: id",
            ),
            (
                '[{"id": "rule-a", "enabled": Infinity}]',
                "non-finite JSON value is not allowed: Infinity",
            ),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                values = _valid_config_values()
                values["FinalLibraryPromotionRules"] = raw

                errors, _warnings = validate_config_values(
                    values,
                    normalized_path_key=_path_key,
                    path_within_root=_path_within_root,
                )

                self.assertTrue(any(expected in error for error in errors), errors)

    def test_config_path_overlap_warning_reports_same_source_roots(self) -> None:
        warning = config_path_overlap_warning(
            "SourceMovies",
            "SourceTV",
            {"SourceMovies": r"C:\Media", "SourceTV": r"C:\Media"},
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(warning, "SourceMovies and SourceTV point to the same location.")

    def test_validate_config_values_rejects_runtime_schema_root_overlap(self) -> None:
        cases = [
            (
                {"SourceMovies": r"C:\Media", "Outsource": r"C:\Media\Processed"},
                "Outsource and SourceMovies must not be nested inside each other.",
                "Outsource is inside SourceMovies. Keep source, output, and scratch roots separated.",
            ),
            (
                {"SourceTV": r"C:\Media\TV", "Outsource": r"C:\Media\TV"},
                "Outsource and SourceTV must not point to the same path.",
                "SourceTV and Outsource point to the same location.",
            ),
            (
                {"SourceMovies": r"C:\Media\Movies", "LocalBase": r"C:\Media\Movies\Scratch"},
                "LocalBase and SourceMovies must not be nested inside each other.",
                "LocalBase is inside SourceMovies. Keep source, output, and scratch roots separated.",
            ),
            (
                {"SourceTV": r"C:\Media\TV", "LocalBase": r"C:\Media\TV\Scratch"},
                "LocalBase and SourceTV must not be nested inside each other.",
                "LocalBase is inside SourceTV. Keep source, output, and scratch roots separated.",
            ),
            (
                {"Outsource": r"D:\MediaOut", "LocalBase": r"D:\MediaOut"},
                "LocalBase and Outsource must not point to the same path.",
                "LocalBase and Outsource are identical. That defeats scratch-vs-library separation.",
            ),
        ]
        for overrides, expected_error, promoted_warning in cases:
            with self.subTest(expected_error=expected_error):
                values = _valid_config_values()
                values.update(overrides)

                errors, warnings = validate_config_values(
                    values,
                    normalized_path_key=_path_key,
                    path_within_root=_path_within_root,
                )

                self.assertIn(expected_error, errors)
                self.assertNotIn(promoted_warning, warnings)

    def test_validate_config_values_rejects_relative_roots_as_errors(self) -> None:
        values = _valid_config_values()
        values.update(
            {
                "SourceMovies": "Movies",
                "SourceTV": "TV",
                "Outsource": "Out",
                "LocalBase": "Scratch",
            }
        )

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("SourceMovies must be an absolute path.", errors)
        self.assertIn("SourceTV must be an absolute path.", errors)
        self.assertIn("Outsource must be an absolute path.", errors)
        self.assertIn("LocalBase must be an absolute path.", errors)
        self.assertFalse(any("should be an absolute path" in warning for warning in warnings))

    def test_validate_config_values_keeps_source_movie_tv_overlap_as_warning_evidence(self) -> None:
        values = _valid_config_values()
        values["SourceTV"] = values["SourceMovies"]

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertNotIn("SourceMovies and SourceTV must not point to the same path.", errors)
        self.assertIn("SourceMovies and SourceTV point to the same location.", warnings)

    def test_validate_config_values_rejects_bdpgs_ocr_enabled_without_tool_path(self) -> None:
        values = _valid_config_values()
        values["ConvertBdpgsToSrt"] = True
        values["BdpgsOcrToolPath"] = " "

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("ConvertBdpgsToSrt requires BdpgsOcrToolPath.", errors)
        self.assertEqual(warnings, [])

    def test_validate_config_values_rejects_subtitle_drop_without_conversion(self) -> None:
        cases = [
            ("ConvertTx3gToSrt", False, "DropTx3gAfterConversion", True, "DropTx3gAfterConversion requires ConvertTx3gToSrt."),
            (
                "ConvertTx3gToSrt",
                False,
                "CreateExternalTx3gSrtSidecars",
                True,
                "CreateExternalTx3gSrtSidecars requires ConvertTx3gToSrt.",
            ),
            ("ConvertBdpgsToSrt", False, "DropBdpgsAfterConversion", True, "DropBdpgsAfterConversion requires ConvertBdpgsToSrt."),
            ("ConvertVobSubToSrt", False, "DropVobSubAfterConversion", True, "DropVobSubAfterConversion requires ConvertVobSubToSrt."),
        ]

        for conversion_key, conversion_value, dependent_key, dependent_value, expected_error in cases:
            with self.subTest(dependent_key=dependent_key):
                values = _valid_config_values()
                values[conversion_key] = conversion_value
                values[dependent_key] = dependent_value

                errors, warnings = validate_config_values(
                    values,
                    normalized_path_key=_path_key,
                    path_within_root=_path_within_root,
                )

                self.assertIn(expected_error, errors)
                self.assertEqual(warnings, [])

    def test_validate_config_values_rejects_vobsub_ocr_enabled_without_tool_path(self) -> None:
        values = _valid_config_values()
        values["ConvertVobSubToSrt"] = True
        values["VobSubOcrToolPath"] = " "

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("ConvertVobSubToSrt requires VobSubOcrToolPath.", errors)
        self.assertEqual(warnings, [])

    def test_service_mixin_preserves_validation_wrapper_methods(self) -> None:
        service = _ConfigValidationWrapperService()

        self.assertEqual(service.split_list_input("eng, spa\njpn"), ["eng", "spa", "jpn"])
        errors, warnings = service.validate_config_values(_valid_config_values())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_service_mixin_validation_does_not_resolve_config_warning_paths(self) -> None:
        class NoFilesystemPathResolutionService(_ConfigValidationWrapperService):
            def _normalized_path_key(self, path: Path) -> str:
                raise AssertionError(f"validation should not resolve {path}")

            def _path_within_root(self, path: Path, root: Path) -> bool:
                raise AssertionError(f"validation should not resolve {path} under {root}")

        values = _valid_config_values()
        values.update(
            {
                "SourceMovies": r"\\LAYNE-SERVER\Users\Layne\Videos\Encode\Movies",
                "SourceTV": r"\\LAYNE-SERVER\Users\Layne\Videos\Encode\TV",
                "Outsource": r"\\LAYNE-SERVER\Users\Layne\Videos\outsource\Movies",
                "LocalBase": r"E:\Videos\Scratch",
            }
        )

        errors, warnings = NoFilesystemPathResolutionService().validate_config_values(values)

        self.assertEqual(errors, [])
        self.assertIsInstance(warnings, list)

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

    def test_save_config_document_rejects_contract_invalid_subtitle_policy_before_write(self) -> None:
        service = _ConfigValidationWrapperService()
        values = _valid_config_values()
        values["ConvertTx3gToSrt"] = False
        values["DropTx3gAfterConversion"] = True
        document_text = service.serialize_psd1_document(values)

        with tempfile.TemporaryDirectory() as raw_root:
            config_path = Path(raw_root) / "MediaPipelineConfig.psd1"
            original_text = "@{ ConvertTx3gToSrt = $true }\n"
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
        self.assertIn("DropTx3gAfterConversion requires ConvertTx3gToSrt.", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
