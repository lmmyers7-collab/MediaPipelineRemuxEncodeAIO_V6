from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config.metadata_parts.field_definitions import CONFIG_FIELD_DEFINITIONS
from app.config.numeric_policy import validate_required_and_numeric_config


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
        "EncodeThresholdGB": 8,
        "TVEncodeThresholdGB": 4,
        "MovieRouteMaxVideoBitrateMbps": 35,
        "TVRouteMaxVideoBitrateMbps": 18,
        "Route1080pBucketMaxHeight": 1200,
        "Route1080pMaxVideoBitrateMbps": 20,
        "Route4KBucketMinHeight": 1800,
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
            "EncodeThresholdGB": {"min": 1, "max": None, "step": 1, "unit": "GB"},
            "TVEncodeThresholdGB": {"min": 1, "max": None, "step": 1, "unit": "GB"},
            "MovieRouteMaxVideoBitrateMbps": {"min": 1, "max": 500, "step": 1, "unit": "Mbps"},
            "TVRouteMaxVideoBitrateMbps": {"min": 1, "max": 500, "step": 1, "unit": "Mbps"},
            "Route1080pBucketMaxHeight": {"min": 1, "max": 4320, "step": 1, "unit": "pixels"},
            "Route1080pMaxVideoBitrateMbps": {"min": 1, "max": 500, "step": 1, "unit": "Mbps"},
            "Route4KBucketMinHeight": {"min": 1, "max": 4320, "step": 1, "unit": "pixels"},
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
                "MovieRouteMaxVideoBitrateMbps": 0,
                "TVRouteMaxVideoBitrateMbps": 501,
                "Route1080pBucketMaxHeight": 1800,
                "Route4KBucketMinHeight": 1800,
                "Route1080pMaxVideoBitrateMbps": 0,
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
        self.assertIn("MovieRouteMaxVideoBitrateMbps must be >= 1.", errors)
        self.assertIn("TVRouteMaxVideoBitrateMbps must be <= 500.", errors)
        self.assertIn("Route1080pBucketMaxHeight must be lower than Route4KBucketMinHeight.", errors)
        self.assertIn("Route1080pMaxVideoBitrateMbps must be >= 1.", errors)
        self.assertIn("Route4KMaxVideoBitrateMbps must be <= 500.", errors)

    def test_numeric_policy_rejects_boolean_values_as_numbers(self) -> None:
        values = _numeric_baseline()
        values["EncodeThresholdGB"] = True
        values["Route1080pBucketMaxHeight"] = True
        values["OutputSizeMultiplier"] = True
        errors: list[str] = []

        validate_required_and_numeric_config(values, errors)

        self.assertIn("EncodeThresholdGB must be an integer.", errors)
        self.assertIn("Route1080pBucketMaxHeight must be an integer.", errors)
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
