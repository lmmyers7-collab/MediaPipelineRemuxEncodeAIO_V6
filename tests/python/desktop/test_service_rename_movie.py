from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.service import RenameServiceMixin
from mediapipeline.core.rename.movie import (
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

    def test_movie_cleaner_uses_rightmost_plausible_release_year(self) -> None:
        examples = {
            "2001.A.Space.Odyssey.1968.1080p.BluRay.x265.mkv": "2001 A Space Odyssey (1968)",
            "Blade.Runner.2049.2017.1080p.BluRay.x265.mkv": "Blade Runner 2049 (2017)",
            "1917.2019.1080p.BluRay.x265.mkv": "1917 (2019)",
            "1984.1984.1080p.BluRay.x265.mkv": "1984 (1984)",
        }

        for file_name, expected in examples.items():
            with self.subTest(file_name=file_name):
                self.assertEqual(clean_pipeline_movie_name(file_name), expected)

    def test_movie_year_candidates_use_plausible_bounds_and_bracket_precedence(self) -> None:
        next_year = date.today().year + 1
        too_future = next_year + 1
        examples = {
            "Roundhay.Garden.Scene.1888.mkv": "Roundhay Garden Scene (1888)",
            "Pre-Cinema.1887.mkv": "Pre-Cinema 1887",
            f"Near.Future.{next_year}.mkv": f"Near Future ({next_year})",
            f"Far.Future.{too_future}.mkv": f"Far Future {too_future}",
            f"{date.today().year}.mkv": str(date.today().year),
            "Movie.(2020).2021.mkv": "Movie 2021 (2020)",
        }

        for file_name, expected in examples.items():
            with self.subTest(file_name=file_name):
                self.assertEqual(clean_pipeline_movie_name(file_name), expected)

    def test_movie_cleaner_preserves_title_words_that_resemble_metadata(self) -> None:
        examples = {
            "12.Angry.Men.1957.mkv": "12 Angry Men (1957)",
            "10.Cloverfield.Lane.2016.mkv": "10 Cloverfield Lane (2016)",
            "DC.League.of.Super-Pets.2022.mkv": "DC League of Super-Pets (2022)",
            "Ma.2019.mkv": "Ma (2019)",
            "Cam.2018.mkv": "Cam (2018)",
            "The.Web.2013.mkv": "The Web (2013)",
            "Audio.Drama.2024.mkv": "Audio Drama (2024)",
        }

        for file_name, expected in examples.items():
            with self.subTest(file_name=file_name):
                self.assertEqual(clean_pipeline_movie_name(file_name), expected)

    def test_movie_cleaner_removes_revision_and_ambiguous_terms_only_in_verified_metadata_tails(self) -> None:
        for revision in ("PROPER", "REPACK", "RERIP"):
            with self.subTest(revision=revision):
                self.assertEqual(clean_pipeline_movie_name(f"Movie.{revision}.2024.mkv"), "Movie (2024)")

        self.assertEqual(clean_pipeline_movie_name("A.Proper.Man.2024.mkv"), "A Proper Man (2024)")
        self.assertEqual(
            clean_pipeline_movie_name(
                "Hoppers.2160p.MA.WEB-DL.DDP5.1.Atmos.DV.HDR.H.265-BYNDR.2026.mkv",
                movie_filter_terms={"services_containers": ["MA"], "release_groups": ["BYNDR"]},
            ),
            "Hoppers (2026)",
        )
        self.assertEqual(clean_pipeline_movie_name("Movie.1080p.CAM.2024.mkv"), "Movie (2024)")

    def test_explicit_movie_remove_terms_remain_global_and_token_bounded(self) -> None:
        self.assertEqual(
            clean_pipeline_movie_name("The.Web.Story.2024.mkv", remove_terms=["web"]),
            "The Story (2024)",
        )
        self.assertEqual(
            clean_pipeline_movie_name("Webster.2024.mkv", remove_terms=["web"]),
            "Webster (2024)",
        )

    def test_movie_cleaner_does_not_fall_back_to_metadata_when_title_is_empty(self) -> None:
        self.assertEqual(clean_pipeline_movie_name("1080p.WEB-DL.x265.2024.mkv"), "")

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

    def test_saved_policy_terms_clean_reported_movie_examples(self) -> None:
        saved_terms = {
            "release_groups": ["SupaCvnt", "BYNDR"],
            "services_containers": ["MA"],
        }

        self.assertEqual(
            clean_pipeline_movie_name(
                "Iron.Lung.2026.1080p.WEBRip.x265.6CH-SupaCvnt.mkv",
                movie_filter_terms=saved_terms,
            ),
            "Iron Lung (2026)",
        )
        self.assertEqual(
            clean_pipeline_movie_name(
                "Hoppers.2026.2160p.MA.WEB-DL.DDP5.1.Atmos.DV.HDR.H.265-BYNDR.mkv",
                movie_filter_terms=saved_terms,
            ),
            "Hoppers (2026)",
        )

    def test_language_sub_dub_filter_terms_clean_release_tags(self) -> None:
        file_name = "Cinema.Paradiso.1988.Ita.Eng.Sub.Dub.1080p.BluRay.x264.mkv"

        self.assertEqual(clean_pipeline_movie_name(file_name), "Cinema Paradiso (1988)")
        self.assertEqual(
            clean_pipeline_movie_name(
                file_name,
                movie_filter_options={"languages_subs_dubs": False},
            ),
            "Cinema Paradiso Ita Eng Sub Dub (1988)",
        )

    def test_symbol_only_custom_remove_terms_strip_plus_inside_title_token(self) -> None:
        self.assertEqual(remove_movie_filter_terms("S03+SP", ["+"]), "S03 SP")
        self.assertEqual(
            clean_pipeline_movie_name(
                "Ascendance.of.a.Bookworm.S03+SP.1080p.BluRay.x265.mkv",
                remove_terms=["sp", "+"],
            ),
            "Ascendance of a Bookworm S03",
        )

    def test_movie_filter_default_terms_include_backend_display_catalog(self) -> None:
        defaults = rename_movie_filter_default_terms()

        self.assertIn("video_source", defaults)
        self.assertIn("audio_channels", defaults)
        self.assertIn("languages_subs_dubs", defaults)
        self.assertIn("release_groups", defaults)
        self.assertIn("1080p", defaults["video_source"])
        self.assertIn("ddp", defaults["audio_channels"])
        self.assertIn("eng", defaults["languages_subs_dubs"])
        self.assertIn("ita", defaults["languages_subs_dubs"])
        self.assertIn("sub", defaults["languages_subs_dubs"])
        self.assertIn("dub", defaults["languages_subs_dubs"])
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
