from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediapipeline_desktop_app.service_path_layout import (
    first_existing,
    normalized_path_key,
    path_or_none,
    path_within_root,
    state_root_for_local_base,
    valid_extensions_from_config,
)


class ServicePathLayoutTests(unittest.TestCase):
    def test_first_existing_returns_first_existing_candidate_or_first_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing = root / "missing"
            existing = root / "existing"
            existing.write_text("", encoding="utf-8")

            self.assertEqual(first_existing(missing, existing), existing)
            self.assertEqual(first_existing(missing, root / "also-missing"), missing)

    def test_state_root_for_local_base_uses_versioned_state_folder(self) -> None:
        self.assertEqual(state_root_for_local_base(Path("D:/Scratch")), Path("D:/Scratch") / "State")

    def test_path_or_none_rejects_blank_values(self) -> None:
        self.assertIsNone(path_or_none(None))
        self.assertIsNone(path_or_none("   "))
        self.assertEqual(path_or_none("D:/Media"), Path("D:/Media"))

    def test_valid_extensions_from_config_uses_clean_lowercase_or_defaults(self) -> None:
        self.assertEqual(valid_extensions_from_config({"ValidExtensions": [".MKV", " ", ".MP4"]}), [".mkv", ".mp4"])
        self.assertIn(".m2ts", valid_extensions_from_config({"ValidExtensions": []}))

    def test_path_within_root_allows_nested_path_and_rejects_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            nested = root / "nested" / "file.txt"
            sibling = Path(temp_dir) / "root-other" / "file.txt"

            self.assertTrue(path_within_root(nested, root))
            self.assertFalse(path_within_root(sibling, root))

    def test_normalized_path_key_returns_absolute_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            key = normalized_path_key(Path(temp_dir) / ".." / Path(temp_dir).name)

        self.assertTrue(Path(key).is_absolute())


if __name__ == "__main__":
    unittest.main()
