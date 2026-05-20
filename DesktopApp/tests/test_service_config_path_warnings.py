from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_config_path_warnings import (
    config_path_overlap_warning,
    config_root_path_warnings,
)


def _path_key(path: Path) -> str:
    return str(path).rstrip("\\/").casefold()


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


class ServiceConfigPathWarningTests(unittest.TestCase):
    def test_config_path_overlap_warning_reports_same_source_roots(self) -> None:
        warning = config_path_overlap_warning(
            "SourceMovies",
            "SourceTV",
            {"SourceMovies": r"C:\Media", "SourceTV": r"C:\Media"},
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(warning, "SourceMovies and SourceTV point to the same location.")

    def test_config_root_path_warnings_reports_relative_and_nested_paths(self) -> None:
        warnings = config_root_path_warnings(
            {
                "SourceMovies": "Movies",
                "SourceTV": r"C:\Media\TV",
                "Outsource": r"D:\Out",
                "LocalBase": r"C:\Media\TV\Scratch",
            },
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("SourceMovies should be an absolute path.", warnings)
        self.assertIn("LocalBase is inside SourceTV. Keep source, output, and scratch roots separated.", warnings)

    def test_config_root_path_warnings_deduplicates_equal_roots(self) -> None:
        warnings = config_root_path_warnings(
            {
                "SourceMovies": r"C:\Media",
                "SourceTV": r"C:\Media",
                "Outsource": r"C:\Media",
                "LocalBase": r"C:\Media",
            },
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(warnings.count("SourceMovies and SourceTV point to the same location."), 1)
        self.assertEqual(warnings.count("LocalBase and Outsource are identical. That defeats scratch-vs-library separation."), 1)


if __name__ == "__main__":
    unittest.main()
