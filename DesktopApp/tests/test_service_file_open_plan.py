from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from mediapipeline_desktop_app.service_file_open_plan import (
    build_vlc_launch_args,
    explorer_select_args,
    vlc_candidate_paths,
    vlc_creation_flags,
    vlc_needs_short_path,
)


class FileOpenPlanTests(unittest.TestCase):
    def test_vlc_candidate_paths_include_path_and_program_files_locations(self) -> None:
        candidates = vlc_candidate_paths(
            which_vlc=r"C:\Tools\VLC\vlc.exe",
            environ={
                "ProgramFiles": r"C:\Program Files",
                "ProgramFiles(x86)": r"C:\Program Files (x86)",
            },
        )

        self.assertEqual(candidates[0], Path(r"C:\Tools\VLC\vlc.exe"))
        self.assertIn(Path(r"C:\Program Files\VideoLAN\VLC\vlc.exe"), candidates)
        self.assertIn(Path(r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"), candidates)

    def test_vlc_short_path_is_windows_local_long_path_only(self) -> None:
        long_local = "C:\\" + ("a" * 280) + "\\movie.mkv"
        long_unc = "\\\\server\\share\\" + ("a" * 280) + "\\movie.mkv"

        self.assertTrue(vlc_needs_short_path(long_local, is_windows=True, threshold=260))
        self.assertFalse(vlc_needs_short_path(long_unc, is_windows=True, threshold=260))
        self.assertFalse(vlc_needs_short_path(long_local, is_windows=False, threshold=260))
        self.assertFalse(vlc_needs_short_path(r"C:\short\movie.mkv", is_windows=True, threshold=260))

    def test_vlc_creation_flags_and_args_are_stable(self) -> None:
        self.assertEqual(vlc_creation_flags(is_windows=False), 0)
        expected_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        self.assertEqual(vlc_creation_flags(is_windows=True), expected_flags)
        self.assertEqual(
            build_vlc_launch_args(Path(r"C:\VLC\vlc.exe"), r"C:\Media\Movie.mkv"),
            [
                str(Path(r"C:\VLC\vlc.exe")),
                "--no-one-instance",
                "--no-one-instance-when-started-from-file",
                "--no-playlist-enqueue",
                r"C:\Media\Movie.mkv",
            ],
        )

    def test_explorer_select_args_preserve_native_path_literal(self) -> None:
        self.assertEqual(
            explorer_select_args(r"\\?\C:\Media\Movie.mkv"),
            ["explorer.exe", r"/select,\\?\C:\Media\Movie.mkv"],
        )


if __name__ == "__main__":
    unittest.main()
