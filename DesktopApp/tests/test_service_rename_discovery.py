from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rename.discovery import discover_rename_media_files


class RenameServiceDiscoveryTests(unittest.TestCase):
    def test_discovers_top_level_media_files_only_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Show.E02.mkv").write_text("", encoding="utf-8")
            (root / "Show.E10.mp4").write_text("", encoding="utf-8")
            (root / "notes.txt").write_text("", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "Show.E03.mkv").write_text("", encoding="utf-8")

            discovered = discover_rename_media_files(root)

        self.assertEqual([path.name for path in discovered], ["Show.E02.mkv", "Show.E10.mp4"])

    def test_recursive_discovery_includes_nested_media_and_natural_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Show.E10.mkv").write_text("", encoding="utf-8")
            nested = root / "Season 01"
            nested.mkdir()
            (nested / "Show.E2.mkv").write_text("", encoding="utf-8")
            (nested / "Show.E01.mkv").write_text("", encoding="utf-8")
            (nested / "cover.jpg").write_text("", encoding="utf-8")

            discovered = discover_rename_media_files(root, recursive=True)

        self.assertEqual([path.name for path in discovered], ["Show.E01.mkv", "Show.E2.mkv", "Show.E10.mkv"])

    def test_missing_folder_and_file_path_raise_clear_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "Movie.mkv"
            file_path.write_text("", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                discover_rename_media_files(root / "missing")
            with self.assertRaises(NotADirectoryError):
                discover_rename_media_files(file_path)


if __name__ == "__main__":
    unittest.main()
