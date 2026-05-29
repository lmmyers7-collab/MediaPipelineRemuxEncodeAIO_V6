from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rename.service import RenameServiceMixin
from app.rename.tv import (
    build_auto_tv_rename_name,
    clean_pipeline_tv_name_part,
    extract_confident_tv_episode_title,
    resolve_tv_folder_season_info,
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

    def test_service_wrappers_match_extracted_tv_helpers(self) -> None:
        service = DummyRenameTvService()
        source = Path("Serial Experiments Lain E01 Weird 1080p BluRay.mkv")

        self.assertEqual(service._clean_pipeline_tv_name_part("Serial Experiments Lain 1080p BluRay"), clean_pipeline_tv_name_part("Serial Experiments Lain 1080p BluRay"))
        self.assertEqual(service._extract_confident_tv_episode_title(source.stem), extract_confident_tv_episode_title(source.stem))
        self.assertEqual(service._build_auto_tv_rename_name(source, season_number=1, remove_terms=None), build_auto_tv_rename_name(source, season_number=1, remove_terms=None))


if __name__ == "__main__":
    unittest.main()
