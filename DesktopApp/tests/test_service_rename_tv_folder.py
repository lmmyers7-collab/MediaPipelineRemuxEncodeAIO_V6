from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.rename.tv_folder import resolve_tv_folder_season_info


def _clean_name(value: str, _remove_terms: list[str] | None = None) -> str:
    return " ".join(value.replace(".", " ").replace("_", " ").split()).strip()


class RenameTvFolderSeasonTests(unittest.TestCase):
    def test_season_folder_uses_parent_as_show_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "Show.Name" / "Season 02"
            folder.mkdir(parents=True)
            source = folder / "Show Name E01.mkv"

            info = resolve_tv_folder_season_info(source, clean_name=_clean_name)

            self.assertEqual(info, {"season": 2, "show": "Show Name", "source": "season-folder"})

    def test_show_season_folder_extracts_show_and_season(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "Serial Experiments Lain 1998 Season 02 1080p BluRay"
            folder.mkdir(parents=True)
            source = folder / "Serial Experiments Lain E01.mkv"

            info = resolve_tv_folder_season_info(source, clean_name=_clean_name)

            self.assertEqual(info["season"], 2)
            self.assertEqual(info["show"], "Serial Experiments Lain 1998")
            self.assertEqual(info["source"], "show-season-folder")

    def test_specials_folder_maps_to_season_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "Show Name" / "OVA"
            folder.mkdir(parents=True)
            source = folder / "Show Name E01.mkv"

            info = resolve_tv_folder_season_info(source, clean_name=_clean_name)

            self.assertEqual(info, {"season": 0, "show": "Show Name", "source": "specials-folder"})

    def test_embedded_s_digits_inside_word_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "scratchS08work"
            folder.mkdir(parents=True)
            source = folder / "Show Name E01.mkv"

            self.assertIsNone(resolve_tv_folder_season_info(source, clean_name=_clean_name))


if __name__ == "__main__":
    unittest.main()
