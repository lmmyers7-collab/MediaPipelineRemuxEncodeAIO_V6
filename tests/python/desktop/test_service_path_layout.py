from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.paths.layout import (
    first_existing,
    normalized_path_key,
    path_or_none,
    path_boundary_check,
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

    def test_path_boundary_rejects_parent_traversal_and_root_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            root.mkdir()

            outside = root / ".." / "outside.txt"
            root_target = root

            self.assertEqual(path_boundary_check(outside, root).reason_code, "OUTSIDE_ALLOWED_ROOT")
            self.assertEqual(path_boundary_check(root_target, root).reason_code, "ROOT_MUTATION_TARGET")

    def test_path_boundary_allows_missing_leaf_after_existing_parent_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            parent = root / "parent"
            parent.mkdir(parents=True)

            target = parent / "new-file.txt"

            self.assertTrue(path_boundary_check(target, root, allow_missing_leaf=True).ok)
            self.assertEqual(path_boundary_check(target, root, allow_missing_leaf=False).reason_code, "PATH_MISSING")

    def test_path_boundary_rejects_symlink_component_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            outside = Path(temp_dir) / "outside"
            root.mkdir()
            outside.mkdir()
            link = root / "link"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            result = path_boundary_check(link / "file.txt", root, allow_missing_leaf=True)

            self.assertEqual(result.reason_code, "REPARSE_POINT_COMPONENT")
            self.assertIn("link", result.reparse_path)

    @unittest.skipUnless(os.name == "nt", "junction checks are Windows-only")
    def test_path_boundary_rejects_junction_component_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            outside = Path(temp_dir) / "outside"
            junction = root / "junction"
            root.mkdir()
            outside.mkdir()
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                text=True,
                capture_output=True,
            )
            if result.returncode != 0:
                self.skipTest(f"junction creation unavailable: {result.stdout} {result.stderr}")

            boundary = path_boundary_check(junction / "file.txt", root, allow_missing_leaf=True)

            self.assertEqual(boundary.reason_code, "REPARSE_POINT_COMPONENT")

    @unittest.skipUnless(os.name == "nt", "case-insensitive keys are Windows-specific")
    def test_normalized_path_key_handles_case_insensitive_collisions_on_windows(self) -> None:
        self.assertEqual(normalized_path_key(Path("C:/Media/Movie.mkv")), normalized_path_key(Path("c:/media/movie.mkv")))


if __name__ == "__main__":
    unittest.main()
