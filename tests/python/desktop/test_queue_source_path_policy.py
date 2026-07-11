from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.queue_source_path_policy import (
    queue_source_file_validation,
    validate_queue_source_file_path,
    validate_queue_source_path,
)


def _resolved(root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        source_movies=root / "Movies",
        source_tv=root / "TV",
        config_data={},
    )


class QueueSourcePathPolicyTests(unittest.TestCase):
    def test_validate_queue_source_path_rejects_dotdot_escape_from_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.source_movies.mkdir()
            resolved.source_tv.mkdir()
            traversal = resolved.source_movies / ".." / "Other" / "Outside.mkv"

            source_path, error = validate_queue_source_path(resolved, traversal)

        self.assertIsNone(source_path)
        self.assertIn("outside configured source roots", error or "")

    def test_validate_queue_source_path_accepts_dotdot_that_stays_inside_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = resolved.source_movies / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            expected_source_path = str(source.resolve(strict=False))
            traversal = resolved.source_movies / "Season 01" / ".." / "Movie.mkv"

            source_path, error = validate_queue_source_path(resolved, traversal)

        self.assertIsNone(error)
        self.assertEqual(source_path, expected_source_path)

    def test_validate_queue_source_path_uses_route_specific_field_label(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.source_movies.mkdir()
            resolved.source_tv.mkdir()

            source_path, error = validate_queue_source_path(
                resolved,
                "relative-folder",
                field_name="folder_path",
            )

        self.assertIsNone(source_path)
        self.assertEqual(
            error,
            "'folder_path' must be an absolute path under configured source roots (SourceMovies, SourceTV, or enabled LibraryProfiles source roots).",
        )

    def test_validate_queue_source_file_path_accepts_configured_source_movies_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movies = root / "ConfiguredMovies"
            source_movies.mkdir()
            source = source_movies / "Movie.mkv"
            source.write_bytes(b"media")
            expected_source_path = str(source.resolve(strict=False))
            resolved = _resolved(root)
            resolved.source_movies = None
            resolved.source_tv = None
            resolved.config_data = {"SourceMovies": str(source_movies)}

            source_path, error = validate_queue_source_file_path(resolved, source, field_name="single_file")
            validation = queue_source_file_validation(resolved, source, field_name="single_file")

        self.assertIsNone(error)
        self.assertEqual(source_path, expected_source_path)
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["normalized_path"], expected_source_path)
        self.assertTrue(validation["under_source_root"])


if __name__ == "__main__":
    unittest.main()
