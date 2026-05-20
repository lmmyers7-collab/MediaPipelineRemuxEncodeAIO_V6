from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_config_numeric_policy import validate_required_and_numeric_config


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
        "MinFreeSpaceGB": 20,
        "OutsourceMinFreeSpaceGB": 20,
        "VideoQuality": 22,
        "MergeThresholdMs": 100,
        "FFmpegEncodeTimeoutSeconds": 3600,
        "FFmpegRemuxTimeoutSeconds": 1800,
        "SubtitleExtractTimeoutSeconds": 300,
        "SubtitleProbeTimeoutSeconds": 30,
        "BdpgsOcrTimeoutSeconds": 1800,
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

    def test_numeric_policy_reports_required_and_bounds_errors(self) -> None:
        values = _numeric_baseline()
        values.update(
            {
                "SourceMovies": "",
                "VideoQuality": 99,
                "IndexScanTimeoutSeconds": 10,
                "TransientFailureRetryLimit": 101,
                "OutputSizeMultiplier": 3.0,
            }
        )
        errors: list[str] = []

        validate_required_and_numeric_config(values, errors)

        self.assertIn("SourceMovies is required.", errors)
        self.assertIn("VideoQuality must be <= 51.", errors)
        self.assertIn("IndexScanTimeoutSeconds must be >= 30.", errors)
        self.assertIn("TransientFailureRetryLimit must be <= 100.", errors)
        self.assertIn("OutputSizeMultiplier must be <= 2.0.", errors)

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
