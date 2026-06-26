from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.utils import (
    associated_sidecar_candidates,
    mediapipeline_sidecar_path,
    natural_sort_key,
    normalize_plex_filename_component,
    parse_rename_number,
    parse_rename_remove_terms,
    pipeline_sidecar_path,
    remove_default_priority_markers,
    rename_override_sidecar_path,
    strip_known_media_suffix,
)


class RenameServiceUtilsTests(unittest.TestCase):
    def test_parse_remove_terms_splits_and_deduplicates(self) -> None:
        self.assertEqual(
            parse_rename_remove_terms("sample, trailer\nSample;behind the scenes"),
            ["sample", "trailer", "behind the scenes"],
        )

    def test_parse_number_accepts_prefixed_tokens_and_bounds(self) -> None:
        self.assertEqual(parse_rename_number("S02", label="Season", prefix_pattern="S", minimum=0, maximum=99), 2)
        self.assertEqual(parse_rename_number("22", label="Episode", prefix_pattern="E", minimum=1, maximum=999), 22)
        with self.assertRaisesRegex(ValueError, "between 1 and 999"):
            parse_rename_number("E0000", label="Episode", prefix_pattern="E", minimum=1, maximum=999)

    def test_plex_component_normalization_removes_terms_and_invalid_chars(self) -> None:
        self.assertEqual(
            normalize_plex_filename_component('Show: Name | sample <test>', ["sample"]),
            "Show Name test",
        )

    def test_sidecar_candidates_preserve_pipeline_and_override_patterns(self) -> None:
        media = Path(r"C:\Media\Movie.mkv")
        candidates = associated_sidecar_candidates(media)

        self.assertEqual(candidates[0][0], mediapipeline_sidecar_path(media))
        self.assertEqual(candidates[1][0], pipeline_sidecar_path(media))
        self.assertEqual(candidates[2][0], Path(str(media) + ".pipeline.json"))
        self.assertEqual(candidates[3][0], rename_override_sidecar_path(media))
        self.assertEqual(candidates[0][1](Path(r"C:\Out\Movie Renamed.mkv")), Path(r"C:\Out\Movie Renamed.mediapipeline.json"))

    def test_sort_suffix_and_priority_helpers_match_rename_expectations(self) -> None:
        paths = [Path("Show.10.mkv"), Path("Show.2.mkv"), Path("Show.01.mkv")]

        self.assertEqual([path.name for path in sorted(paths, key=natural_sort_key)], ["Show.01.mkv", "Show.2.mkv", "Show.10.mkv"])
        self.assertEqual(strip_known_media_suffix("Movie.Title.mkv"), "Movie.Title")
        self.assertEqual(remove_default_priority_markers("[NOW] ! Movie.Title"), "Movie.Title")


if __name__ == "__main__":
    unittest.main()
