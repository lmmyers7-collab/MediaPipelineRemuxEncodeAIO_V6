from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_rename_plan_policy import (
    build_movie_rename_name,
    casefold_bool_override_map,
    casefold_override_map,
    normalise_manual_final_name,
    rename_row_status,
)
from mediapipeline_desktop_app.service_rename_utils import normalize_plex_filename_component


def _clean_movie_name(
    file_name: str,
    remove_terms: list[str] | None,
    movie_filter_options: dict[str, bool] | None,
    movie_filter_terms: dict[str, list[str]] | None = None,
) -> str:
    if movie_filter_terms:
        return "Editable Filter Movie (1999)"
    return "Fallback Movie (1999)"


class RenamePlanPolicyTests(unittest.TestCase):
    def test_casefold_override_maps_normalize_keys(self) -> None:
        self.assertEqual(casefold_override_map({"C:/Media/Movie.MKV": "Clean.mkv"}), {"c:/media/movie.mkv": "Clean.mkv"})
        self.assertEqual(casefold_bool_override_map({"C:/Media/Movie.MKV": 1}), {"c:/media/movie.mkv": True})
        self.assertEqual(casefold_override_map(None), {})
        self.assertEqual(casefold_bool_override_map(None), {})

    def test_rename_row_status_priority(self) -> None:
        self.assertEqual(rename_row_status(errors=["bad"], warnings=["warn"], matches_target=True), "blocked")
        self.assertEqual(rename_row_status(errors=[], warnings=["warn"], matches_target=True), "warning")
        self.assertEqual(rename_row_status(errors=[], warnings=[], matches_target=True), "match")
        self.assertEqual(rename_row_status(errors=[], warnings=[], matches_target=False), "ready")

    def test_manual_final_name_adds_source_suffix(self) -> None:
        source = Path("Example.Source.MKV")

        final_name = normalise_manual_final_name(
            source,
            "Clean Name",
            normalize_component=normalize_plex_filename_component,
        )

        self.assertEqual(final_name, "Clean Name.mkv")

    def test_manual_final_name_rejects_paths_and_empty_values(self) -> None:
        source = Path("Example.mkv")

        with self.assertRaisesRegex(ValueError, "filenames"):
            normalise_manual_final_name(
                source,
                "Nested/Name",
                normalize_component=normalize_plex_filename_component,
            )
        with self.assertRaisesRegex(ValueError, "empty"):
            normalise_manual_final_name(
                source,
                "<>",
                normalize_component=normalize_plex_filename_component,
            )

    def test_movie_name_uses_manual_title_and_year(self) -> None:
        final_name = build_movie_rename_name(
            Path("Noisy.Release.MKV"),
            movie_title="The Matrix",
            movie_year="1999",
            remove_terms=None,
            normalize_component=normalize_plex_filename_component,
            clean_movie_name=_clean_movie_name,
        )

        self.assertEqual(final_name, "The Matrix (1999).mkv")

    def test_movie_name_replaces_existing_year_when_manual_year_differs(self) -> None:
        final_name = build_movie_rename_name(
            Path("Noisy.Release.mkv"),
            movie_title="Movie (2000)",
            movie_year="2001",
            remove_terms=None,
            normalize_component=normalize_plex_filename_component,
            clean_movie_name=_clean_movie_name,
        )

        self.assertEqual(final_name, "Movie (2001).mkv")

    def test_movie_name_rejects_invalid_manual_year(self) -> None:
        with self.assertRaisesRegex(ValueError, "four digit"):
            build_movie_rename_name(
                Path("Noisy.Release.mkv"),
                movie_title="Movie",
                movie_year="20XX",
                remove_terms=None,
                normalize_component=normalize_plex_filename_component,
                clean_movie_name=_clean_movie_name,
            )

    def test_movie_name_uses_cleaner_when_manual_title_is_blank(self) -> None:
        final_name = build_movie_rename_name(
            Path("Noisy.Release.mkv"),
            movie_title="",
            movie_year="",
            remove_terms=["sample"],
            movie_filter_options={"release_groups": False},
            normalize_component=normalize_plex_filename_component,
            clean_movie_name=_clean_movie_name,
        )

        self.assertEqual(final_name, "Fallback Movie (1999).mkv")

    def test_movie_name_passes_editable_filter_terms_to_cleaner(self) -> None:
        final_name = build_movie_rename_name(
            Path("Noisy.Release.mkv"),
            movie_title="",
            movie_year="",
            remove_terms=None,
            movie_filter_options={"video_source": True},
            movie_filter_terms={"video_source": ["noisy"]},
            normalize_component=normalize_plex_filename_component,
            clean_movie_name=_clean_movie_name,
        )

        self.assertEqual(final_name, "Editable Filter Movie (1999).mkv")


if __name__ == "__main__":
    unittest.main()
