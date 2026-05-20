from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app import APP_VERSION


class VersioningTests(unittest.TestCase):
    def test_desktop_app_version_matches_pipeline_product_version(self) -> None:
        root = Path(__file__).resolve().parents[2]
        versioning = root / "Pipeline" / "Modules" / "Versioning.ps1"
        text = versioning.read_text(encoding="utf-8")
        match = re.search(
            r"function\s+Get-MediaPipelineProductVersion\s*\{[^{}]*return\s+['\"](?P<version>v\d+\.\d{3})['\"]",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        self.assertIsNotNone(match)
        self.assertEqual(APP_VERSION, match.group("version"))
        self.assertRegex(APP_VERSION, r"^v\d+\.\d{3}$")

    def test_operator_version_bump_rules_are_documented(self) -> None:
        root = Path(__file__).resolve().parents[2]
        text = (root / "Pipeline" / "Modules" / "Versioning.ps1").read_text(encoding="utf-8")

        self.assertIn("v6.001 = minor bug fix", text)
        self.assertIn("v6.010 = minor feature", text)
        self.assertIn("v6.100 = major feature within the V6 line", text)


if __name__ == "__main__":
    unittest.main()
