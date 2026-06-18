from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))
sys.path.insert(0, str(find_repo_root(Path(__file__))))

from mediapipeline.core.config.metadata_parts.field_definitions import CONFIG_FIELD_DEFINITIONS
from mediapipeline.core.config.numeric_policy import validate_required_and_numeric_config


def _metadata_by_key() -> dict[str, dict[str, object]]:
    return {str(field["key"]): field for field in CONFIG_FIELD_DEFINITIONS}


def _numeric_baseline() -> dict:
    return {
        "SourceMovies": r"C:\Media\Movies",
        "SourceTV": r"C:\Media\TV",
        "Outsource": r"D:\MediaOut",
        "LocalBase": r"E:\Scratch",
        "VideoCodec": "hevc_nvenc",
        "VideoPreset": "p5",
        "OutputContainer": "mkv",
        "MovieRoute1080pTargetSizeGB": 8,
        "MovieRoute1440pTargetSizeGB": 10,
        "MovieRoute4KTargetSizeGB": 12,
        "TVRoute1080pTargetSizeGB": 4,
        "TVRoute1440pTargetSizeGB": 6,
        "TVRoute4KTargetSizeGB": 8,
        "Route1080pUpperHeightTolerancePercent": 11.111111,
        "Route1080pMaxVideoBitrateMbps": 20,
        "Route1440pLowerHeightTolerancePercent": 16.597222,
        "Route1440pUpperHeightTolerancePercent": 24.930556,
        "Route1440pMaxVideoBitrateMbps": 35,
        "Route4KLowerHeightTolerancePercent": 16.666667,
        "Route4KMaxVideoBitrateMbps": 35,
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
    }


class ServiceConfigNumericPolicyTests(unittest.TestCase):
    def test_numeric_policy_accepts_baseline(self) -> None:
        errors: list[str] = []

        validate_required_and_numeric_config(_numeric_baseline(), errors)

        self.assertEqual(errors, [])

    def test_backend_metadata_numeric_limits_match_numeric_policy_representatives(self) -> None:
        metadata = _metadata_by_key()
        expected_limits = {
            "MovieRoute1080pTargetSizeGB": {"min": 1, "max": None, "step": 1, "unit": "GB"},
            "MovieRoute1440pTargetSizeGB": {"min": 1, "max": None, "step": 1, "unit": "GB"},
            "MovieRoute4KTargetSizeGB": {"min": 1, "max": None, "step": 1, "unit": "GB"},
            "TVRoute1080pTargetSizeGB": {"min": 1, "max": None, "step": 1, "unit": "GB"},
            "TVRoute1440pTargetSizeGB": {"min": 1, "max": None, "step": 1, "unit": "GB"},
            "TVRoute4KTargetSizeGB": {"min": 1, "max": None, "step": 1, "unit": "GB"},
            "Route1080pUpperHeightTolerancePercent": {"min": 0, "max": 100, "step": 0.000001, "unit": "percent"},
            "Route1080pMaxVideoBitrateMbps": {"min": 1, "max": 500, "step": 1, "unit": "Mbps"},
            "Route1440pLowerHeightTolerancePercent": {"min": 0, "max": 100, "step": 0.000001, "unit": "percent"},
            "Route1440pUpperHeightTolerancePercent": {"min": 0, "max": 100, "step": 0.000001, "unit": "percent"},
            "Route1440pMaxVideoBitrateMbps": {"min": 1, "max": 500, "step": 1, "unit": "Mbps"},
            "Route4KLowerHeightTolerancePercent": {"min": 0, "max": 100, "step": 0.000001, "unit": "percent"},
            "Route4KMaxVideoBitrateMbps": {"min": 1, "max": 500, "step": 1, "unit": "Mbps"},
            "VideoQuality": {"min": 1, "max": 51, "step": 1, "unit": None},
            "AudioMaxChannels": {"min": 1, "max": 16, "step": 1, "unit": "channels"},
            "SubtitleExtractTimeoutSeconds": {"min": 30, "max": 3600, "step": 1, "unit": "seconds"},
            "SubtitleProbeTimeoutSeconds": {"min": 5, "max": 600, "step": 1, "unit": "seconds"},
            "BdpgsOcrTimeoutSeconds": {"min": 60, "max": 14400, "step": 1, "unit": "seconds"},
            "VobSubOcrTimeoutSeconds": {"min": 60, "max": 14400, "step": 1, "unit": "seconds"},
            "OutputSizeMultiplier": {"min": 0.1, "max": 2.0, "step": "any", "unit": None},
            "CpuEncodeMaxThreads": {"min": 0, "max": 256, "step": 1, "unit": "threads"},
        }

        for key, expected in expected_limits.items():
            with self.subTest(key=key):
                self.assertEqual(
                    {name: metadata[key].get(name) for name in ("min", "max", "step", "unit")},
                    expected,
                )

    def test_numeric_choice_metadata_stays_inside_numeric_policy_bounds(self) -> None:
        metadata = _metadata_by_key()

        for key in ("AudioMaxChannels", "H264RemuxMaxHeight", "VideoQuality"):
            field = metadata[key]
            minimum = field.get("min")
            maximum = field.get("max")
            choices = field.get("allowed_values") or ()
            for choice in choices:
                value = int(str(choice))
                with self.subTest(key=key, choice=choice):
                    if minimum is not None:
                        self.assertGreaterEqual(value, minimum)
                    if maximum is not None:
                        self.assertLessEqual(value, maximum)

    def test_numeric_policy_reports_required_and_bounds_errors(self) -> None:
        values = _numeric_baseline()
        values.update(
            {
                "SourceMovies": "",
                "VideoQuality": 99,
                "IndexScanTimeoutSeconds": 10,
                "TransientFailureRetryLimit": 101,
                "VobSubOcrTimeoutSeconds": 59,
                "OutputSizeMultiplier": 3.0,
                "MovieRoute1080pTargetSizeGB": 0,
                "TVRoute1440pTargetSizeGB": 0,
                "Route1080pUpperHeightTolerancePercent": 101,
                "Route1080pMaxVideoBitrateMbps": 0,
                "Route1440pMaxVideoBitrateMbps": 501,
                "Route4KMaxVideoBitrateMbps": 501,
            }
        )
        errors: list[str] = []

        validate_required_and_numeric_config(values, errors)

        self.assertIn("SourceMovies is required.", errors)
        self.assertIn("VideoQuality must be <= 51.", errors)
        self.assertIn("IndexScanTimeoutSeconds must be >= 30.", errors)
        self.assertIn("TransientFailureRetryLimit must be <= 100.", errors)
        self.assertIn("VobSubOcrTimeoutSeconds must be >= 60.", errors)
        self.assertIn("OutputSizeMultiplier must be <= 2.0.", errors)
        self.assertIn("MovieRoute1080pTargetSizeGB must be >= 1.", errors)
        self.assertIn("TVRoute1440pTargetSizeGB must be >= 1.", errors)
        self.assertIn("Route1080pUpperHeightTolerancePercent must be <= 100.", errors)
        self.assertIn("Route1080pMaxVideoBitrateMbps must be >= 1.", errors)
        self.assertIn("Route1440pMaxVideoBitrateMbps must be <= 500.", errors)
        self.assertIn("Route4KMaxVideoBitrateMbps must be <= 500.", errors)

    def test_numeric_policy_rejects_noncontiguous_height_tolerance_percent_keys(self) -> None:
        values = _numeric_baseline()
        values["Route1080pUpperHeightTolerancePercent"] = 0
        values["Route1440pLowerHeightTolerancePercent"] = 0
        errors: list[str] = []

        validate_required_and_numeric_config(values, errors)

        self.assertIn(
            "Height tolerance must make 1440p start exactly one pixel above the 1080p upper boundary.",
            errors,
        )

    def test_numeric_policy_rejects_boolean_values_as_numbers(self) -> None:
        values = _numeric_baseline()
        values["MovieRoute1080pTargetSizeGB"] = True
        values["Route1080pUpperHeightTolerancePercent"] = True
        values["OutputSizeMultiplier"] = True
        errors: list[str] = []

        validate_required_and_numeric_config(values, errors)

        self.assertIn("MovieRoute1080pTargetSizeGB must be an integer.", errors)
        self.assertIn("Route1080pUpperHeightTolerancePercent must be numeric.", errors)
        self.assertIn("OutputSizeMultiplier must be numeric.", errors)

    def test_numeric_policy_bounds_optional_cpu_fields_when_present(self) -> None:
        values = _numeric_baseline()
        values["CpuEncodeMaxThreads"] = 300
        values["FallbackCpuQuality"] = 0
        errors: list[str] = []

        validate_required_and_numeric_config(values, errors)

        self.assertIn("CpuEncodeMaxThreads must be <= 256.", errors)
        self.assertIn("FallbackCpuQuality must be >= 1.", errors)


if __name__ == "__main__":
    unittest.main()
