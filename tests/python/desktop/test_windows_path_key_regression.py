from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root


sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))


from mediapipeline.core.config import library_profile_state
from mediapipeline.core.observability import status_files
from mediapipeline.core.paths import layout as path_layout
from mediapipeline.core.queue import priority_manifest
from mediapipeline.core.queue.file_overrides import normalize_file_override_path


@unittest.skipUnless(os.name == "nt", "Windows 8.3 aliases are Windows-specific")
class WindowsPathKeyRegressionTests(unittest.TestCase):
    short_root = Path(r"C:\Users\RUNNER~1\AppData\Local\Temp\path-key-regression")
    long_root = Path(r"C:\Users\runneradmin\AppData\Local\Temp\path-key-regression")
    short_source = short_root / "Movies" / "Movie.mkv"
    long_source = long_root / "Movies" / "Movie.mkv"

    @staticmethod
    def _expand_short_name_alias(path: Path, *, strict: bool = False) -> Path:
        del strict
        return Path(str(path).replace("RUNNER~1", "runneradmin"))

    def _with_expanded_short_name(self):
        return patch.object(
            path_layout.Path,
            "resolve",
            autospec=True,
            side_effect=self._expand_short_name_alias,
        )

    def test_file_override_keys_expand_windows_short_name_aliases(self) -> None:
        expected = str(self.long_source).replace("\\", "/").lower()

        with self._with_expanded_short_name():
            self.assertEqual(normalize_file_override_path(self.short_source), expected)

    def test_priority_manifest_keys_expand_windows_short_name_aliases(self) -> None:
        expected = str(self.long_source).replace("\\", "/").lower()

        with self._with_expanded_short_name():
            self.assertEqual(priority_manifest._normalise(self.short_source), expected)

    def test_library_profile_match_keys_expand_windows_short_name_aliases(self) -> None:
        expected = os.path.normcase(str(self.long_source)).rstrip("\\/")

        with self._with_expanded_short_name():
            self.assertEqual(library_profile_state._resolved_match_key(self.short_source), expected)

    def test_audit_pointer_boundary_accepts_equivalent_short_name_parent(self) -> None:
        with self._with_expanded_short_name():
            self.assertTrue(status_files._path_is_inside(self.long_source, self.short_root))

    def test_audit_pointer_boundary_still_rejects_a_sibling(self) -> None:
        sibling = self.long_root.parent / "path-key-regression-other" / "audit_summary_20260710.csv"

        with self._with_expanded_short_name():
            self.assertFalse(status_files._path_is_inside(sibling, self.short_root))

    def test_audit_pointer_boundary_fails_closed_when_path_resolution_errors(self) -> None:
        with patch.object(status_files, "path_within_root", side_effect=ValueError("invalid path")):
            self.assertFalse(status_files._path_is_inside(self.long_source, self.short_root))


if __name__ == "__main__":
    unittest.main()
