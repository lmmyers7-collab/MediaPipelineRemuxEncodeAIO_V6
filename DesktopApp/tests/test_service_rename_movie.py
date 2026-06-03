from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rename.service import RenameServiceMixin
from app.rename.movie import (
    clean_pipeline_movie_name,
    movie_filter_options_are_default,
    rename_movie_filter_default_terms,
    normalize_movie_filter_options,
    normalize_movie_filter_terms,
    remove_movie_filter_terms,
    strip_movie_release_groups,
    title_case_movie_name,
)


class DummyRenameMovieService(RenameServiceMixin):
    pass


class RenameMovieHelperTests(unittest.TestCase):
    def test_movie_cleaner_matches_known_release_name_examples(self) -> None:
        examples = {
            "Devil Wears Prada (2006) (1080p BluRay x265 8bit AC 5.1) [Kris].mkv": "Devil Wears Prada (2006)",
            "Airplane 1980 REMASTERED 1080p BluRay HEVC x265 5.1 BONE.mkv": "Airplane (1980)",
            "Young Frankenstein 1974 1080p BluRay x265 5.1-RARBG.mkv": "Young Frankenstein (1974)",
            "The.Blues.Brothers.1980.EXTENDED.1080p.BluRay.x265.AAC5.1-RBG.mkv": "The Blues Brothers (1980)",
            "Team.America.World.Police.2004.1080p.BluRay.x264-[YTS.LT].mkv": "Team America World Police (2004)",
            "Monty.Pythons.The.Meaning.of.Life.1983.1080p.WEBRip.1400MB.DD5.1.x264-GalaxyRG.mkv": "Monty Pythons The Meaning of Life (1983)",
            "Annie.Hall.1977.1080p.BluRay.x264.YIFY.mkv": "Annie Hall (1977)",
        }

        for file_name, expected in examples.items():
            with self.subTest(file_name=file_name):
                self.assertEqual(clean_pipeline_movie_name(file_name), expected)

    def test_movie_filter_options_preserve_disabled_categories(self) -> None:
        options = normalize_movie_filter_options({"video_source": False, "unknown": False})

        self.assertFalse(options["video_source"])
        self.assertTrue(options["audio_channels"])
        self.assertFalse(movie_filter_options_are_default(options))
        self.assertEqual(
            clean_pipeline_movie_name("Movie.2001.1080p.BluRay.x265.mkv", movie_filter_options=options),
            "Movie 1080p BluRay X265 (2001)",
        )

    def test_movie_filter_terms_extend_enabled_category_defaults(self) -> None:
        self.assertEqual(
            clean_pipeline_movie_name(
                "Movie.CustomTag.1080p.BluRay.mkv",
                movie_filter_terms={"video_source": ["customtag"]},
            ),
            "Movie",
        )
        self.assertEqual(
            clean_pipeline_movie_name(
                "Movie.CustomTag.1080p.BluRay.mkv",
                movie_filter_options={"video_source": False},
                movie_filter_terms={"video_source": ["customtag"]},
            ),
            "Movie CustomTag 1080p BluRay",
        )
        self.assertEqual(normalize_movie_filter_terms({"video_source": ["Tag", "tag", ""]}), {"video_source": ["Tag"]})
        self.assertEqual(
            clean_pipeline_movie_name(
                "Together.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir.mkv",
                movie_filter_terms={"release_groups": ["neonoir"]},
            ),
            "Together (2025)",
        )

    def test_movie_filter_default_terms_include_backend_display_catalog(self) -> None:
        defaults = rename_movie_filter_default_terms()

        self.assertIn("video_source", defaults)
        self.assertIn("audio_channels", defaults)
        self.assertIn("release_groups", defaults)
        self.assertIn("1080p", defaults["video_source"])
        self.assertIn("ddp", defaults["audio_channels"])
        self.assertIn("cmrg", defaults["release_groups"])
        self.assertIn("neonoir", defaults["release_groups"])

    def test_service_wrappers_match_extracted_movie_helpers(self) -> None:
        service = DummyRenameMovieService()

        self.assertEqual(service._title_case_movie_name("history of the world part i"), title_case_movie_name("history of the world part i"))
        self.assertEqual(service._remove_movie_filter_terms("Movie sample trailer", ["sample"]), remove_movie_filter_terms("Movie sample trailer", ["sample"]))
        self.assertEqual(service._strip_movie_release_groups("Movie-GalaxyRG"), strip_movie_release_groups("Movie-GalaxyRG"))
        self.assertEqual(service._clean_pipeline_movie_name("Annie.Hall.1977.1080p.BluRay.x264.YIFY.mkv"), clean_pipeline_movie_name("Annie.Hall.1977.1080p.BluRay.x264.YIFY.mkv"))


if __name__ == "__main__":
    unittest.main()
