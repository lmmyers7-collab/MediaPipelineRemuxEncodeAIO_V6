from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.service import RenameServiceMixin
from mediapipeline.core.rename.tv import (
    build_auto_tv_rename_name,
    clean_pipeline_tv_name_part,
    extract_confident_tv_episode_title,
    resolve_tv_folder_season_info,
    parse_tv_identity,
)


class DummyRenameTvService(RenameServiceMixin):
    pass


class RenameTvHelperTests(unittest.TestCase):
    def test_auto_tv_name_uses_season_from_parent_folder_when_file_has_only_episode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Serial Experiments Lain 1998 Season 02 1080p BluRay FLAC 2.0 x264-Chotab"
            folder.mkdir()
            source = folder / "Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv"

            self.assertEqual(
                build_auto_tv_rename_name(source, season_number=1, remove_terms=None),
                "Serial Experiments Lain - S02E01 - Weird.mkv",
            )

    def test_auto_tv_name_blocks_plus_special_and_ttga_folder_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Ascendance of a Bookworm S03+SP 1080p Dual Audio BD Remux FLAC-TTGA"
            folder.mkdir()
            source = folder / "S03E01-The Beginning of Winter.mkv"

            self.assertEqual(
                clean_pipeline_tv_name_part(folder.name),
                "Ascendance of a Bookworm",
            )
            self.assertEqual(
                build_auto_tv_rename_name(source, season_number=1, remove_terms=None),
                "Ascendance of a Bookworm - S03E01 - The Beginning of Winter.mkv",
            )

    def test_auto_tv_name_prefers_source_embedded_season_over_parent_folder(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Show Name Season 02"
            folder.mkdir()
            source = folder / "Show Name S03E04 The Title 1080p BluRay.mkv"

            self.assertEqual(
                build_auto_tv_rename_name(source, season_number=1, remove_terms=None),
                "Show Name - S03E04 - The Title.mkv",
            )

    def test_specials_folder_maps_episode_tokens_to_season_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Show Name" / "OVA"
            folder.mkdir(parents=True)
            source = folder / "Show Name E01 Bonus Story 1080p BluRay.mkv"

            info = resolve_tv_folder_season_info(source)

            self.assertEqual(info["season"], 0)
            self.assertEqual(build_auto_tv_rename_name(source, season_number=1, remove_terms=None), "Show Name - S00E01 - Bonus Story.mkv")

    def test_embedded_s_digits_in_parent_folder_do_not_become_season(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "scratchS08work"
            folder.mkdir()
            source = folder / "Serial Experiments Lain E01 Weird 1080p BluRay.mkv"

            self.assertIsNone(resolve_tv_folder_season_info(source))
            self.assertEqual(
                build_auto_tv_rename_name(source, season_number=1, remove_terms=None),
                "Serial Experiments Lain - S01E01 - Weird.mkv",
            )

    def test_auto_tv_name_accepts_episode_revision_suffixes(self) -> None:
        self.assertEqual(
            build_auto_tv_rename_name(Path("Example Show S01E12v2.mkv"), season_number=1, remove_terms=None),
            "Example Show - S01E12.mkv",
        )
        self.assertEqual(
            build_auto_tv_rename_name(Path("Example Show E12v3 - Revision Title.mkv"), season_number=1, remove_terms=None),
            "Example Show - S01E12 - Revision Title.mkv",
        )

    def test_canonical_multi_episode_forms_share_one_identity_and_output(self) -> None:
        for source_name in (
            "Example Show S01E01E02.mkv",
            "Example Show S01E01-E02.mkv",
            "Example Show S01E01_E02v3.mkv",
        ):
            with self.subTest(source_name=source_name):
                identity = parse_tv_identity(Path(source_name), season_number=1)
                self.assertTrue(identity["reliable"], identity)
                self.assertEqual(identity["season"], 1)
                self.assertEqual(identity["episode_start"], 1)
                self.assertEqual(identity["episode_end"], 2)
                self.assertEqual(identity["revision"], "v3" if "v3" in source_name else "")
                self.assertEqual(
                    build_auto_tv_rename_name(Path(source_name), season_number=1, remove_terms=None),
                    "Example Show - S01E01-E02.mkv",
                )

    def test_tv_identity_supports_three_digit_episode_and_rejects_out_of_range(self) -> None:
        identity = parse_tv_identity(Path("Example Show S01E100 - Century.mkv"), season_number=1)
        self.assertTrue(identity["reliable"], identity)
        self.assertEqual(identity["episode_start"], 100)
        self.assertEqual(
            build_auto_tv_rename_name(Path("Example Show S01E100 - Century.mkv"), season_number=1, remove_terms=None),
            "Example Show - S01E100 - Century.mkv",
        )

        for source_name in (
            "Example Show S01E1000.mkv",
            "Example Show S01E01-E01.mkv",
            "Example Show S01E02-E01.mkv",
            "Example Show S01E01-02.mkv",
            "Example Show Episode 1-2.mkv",
            "Example Show Ep 1-2.mkv",
            "Example Show - 01-02.mkv",
        ):
            with self.subTest(source_name=source_name):
                identity = parse_tv_identity(Path(source_name), season_number=1)
                self.assertFalse(identity["reliable"])
                self.assertIn("SxxEyy-Ezz", identity["parse_error"])
                with self.assertRaisesRegex(ValueError, "SxxEyy-Ezz"):
                    build_auto_tv_rename_name(Path(source_name), season_number=1, remove_terms=None)

    def test_filename_ordinal_seasons_are_used_without_stronger_folder_or_explicit_season(self) -> None:
        cases = {
            "Example Show 4th Season - 01.mkv": "Example Show - S04E01.mkv",
            "Example Show Third Season - 02.mkv": "Example Show - S03E02.mkv",
            "Example Show 3rd Cour E03.mkv": "Example Show - S03E03.mkv",
        }
        for source_name, expected in cases.items():
            with self.subTest(source_name=source_name):
                self.assertEqual(build_auto_tv_rename_name(Path(source_name), season_number=1, remove_terms=None), expected)

    def test_filename_special_markers_use_season_zero_only_without_stronger_season(self) -> None:
        cases = {
            "Example Show OVA - 01.mkv": "Example Show - S00E01.mkv",
            "Example Show OAV Episode 02.mkv": "Example Show - S00E02.mkv",
            "Example Show ONA E03.mkv": "Example Show - S00E03.mkv",
            "Example Show Special - 04.mkv": "Example Show - S00E04.mkv",
            "Example Show OVA S02E05.mkv": "Example Show - S02E05.mkv",
        }
        for source_name, expected in cases.items():
            with self.subTest(source_name=source_name):
                self.assertEqual(build_auto_tv_rename_name(Path(source_name), season_number=1, remove_terms=None), expected)

    def test_episode_titles_reject_only_pure_numbers(self) -> None:
        self.assertEqual(
            build_auto_tv_rename_name(Path("Example Show S01E01 - 12345.mkv"), season_number=1, remove_terms=None),
            "Example Show - S01E01.mkv",
        )
        self.assertEqual(
            build_auto_tv_rename_name(Path("Example Show S01E01 - 123 Reasons.mkv"), season_number=1, remove_terms=None),
            "Example Show - S01E01 - 123 Reasons.mkv",
        )

    def test_episode_title_metadata_words_are_only_cleaned_in_a_release_tail(self) -> None:
        cases = {
            "Example Show S01E01 - A Proper Introduction.mkv": "Example Show - S01E01 - A Proper Introduction.mkv",
            "Example Show S01E02 - The Repack Plan.mkv": "Example Show - S01E02 - The Repack Plan.mkv",
            "Example Show S01E03 - Rerip the Past.mkv": "Example Show - S01E03 - Rerip the Past.mkv",
            "Example Show S01E04 - The Web of Lies.mkv": "Example Show - S01E04 - The Web of Lies.mkv",
            "Example Show S01E05 - Finale PROPER.mkv": "Example Show - S01E05 - Finale.mkv",
        }
        for source_name, expected in cases.items():
            with self.subTest(source_name=source_name):
                self.assertEqual(build_auto_tv_rename_name(Path(source_name), season_number=1, remove_terms=None), expected)

    def test_canonical_identity_takes_precedence_over_numeric_ranges_in_title_text(self) -> None:
        cases = {
            "Show 1-2 S01E03.mkv": "Show 1-2 - S01E03.mkv",
            "Show S01E03 - Part 1-2.mkv": "Show - S01E03 - Part 1-2.mkv",
        }
        for source_name, expected in cases.items():
            with self.subTest(source_name=source_name):
                identity = parse_tv_identity(Path(source_name), season_number=1)
                self.assertTrue(identity["reliable"], identity)
                self.assertEqual(build_auto_tv_rename_name(Path(source_name), season_number=1, remove_terms=None), expected)

    def test_auto_tv_name_accepts_delimited_bare_anime_episode_numbers(self) -> None:
        self.assertEqual(
            build_auto_tv_rename_name(Path("Kanan-sama wa Akumade Choroi - 12 (1080p).mkv"), season_number=1, remove_terms=None),
            "Kanan-sama wa Akumade Choroi - S01E12.mkv",
        )
        self.assertEqual(
            build_auto_tv_rename_name(Path("Kanan-sama wa Akumade Choroi - 12v2 - Episode Title (1080p).mkv"), season_number=1, remove_terms=None),
            "Kanan-sama wa Akumade Choroi - S01E12 - Episode Title.mkv",
        )

    def test_auto_tv_name_rejects_non_episode_bare_numeric_tokens(self) -> None:
        for source_name in ("Example Show - 1080p.mkv", "Example Show - 2024.mkv", "Example Show - 12bit.mkv", "Example Show - v2.mkv"):
            with self.subTest(source_name=source_name):
                with self.assertRaisesRegex(ValueError, "TV auto preview needs"):
                    build_auto_tv_rename_name(Path(source_name), season_number=1, remove_terms=None)

    def test_service_wrappers_match_extracted_tv_helpers(self) -> None:
        service = DummyRenameTvService()
        source = Path("Serial Experiments Lain E01 Weird 1080p BluRay.mkv")

        self.assertEqual(service._clean_pipeline_tv_name_part("Serial Experiments Lain 1080p BluRay"), clean_pipeline_tv_name_part("Serial Experiments Lain 1080p BluRay"))
        self.assertEqual(service._extract_confident_tv_episode_title(source.stem), extract_confident_tv_episode_title(source.stem))
        self.assertEqual(service._build_auto_tv_rename_name(source, season_number=1, remove_terms=None), build_auto_tv_rename_name(source, season_number=1, remove_terms=None))


if __name__ == "__main__":
    unittest.main()
