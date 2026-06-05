from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop import APP_VERSION


class VersioningTests(unittest.TestCase):
    def test_desktop_app_version_matches_release_metadata(self) -> None:
        root = find_repo_root(Path(__file__))
        version_file = root / "ops" / "release" / "metadata" / "VERSION"
        release_label = version_file.read_text(encoding="utf-8").strip()

        self.assertEqual(APP_VERSION, release_label)
        self.assertRegex(APP_VERSION, r"^\d{4}\.\d{2}\.\d{2}\.\d{3}$")

    def test_pipeline_product_version_reads_release_metadata(self) -> None:
        root = find_repo_root(Path(__file__))
        text = (root / "ops" / "pipeline" / "engine" / "shared" / "versioning.ps1").read_text(encoding="utf-8")

        self.assertIn("ops\\release\\metadata\\VERSION", text)
        self.assertIn("function Get-MediaPipelineReleaseLabel", text)
        self.assertNotRegex(text, re.compile(r"return\s+['\"]v\d+\.\d{3}['\"]", re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
