from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.files.open_plan import MKLINK_JUNCTION_TIMEOUT_SECONDS
from mediapipeline.core.files.opening import FileOpenServiceMixin


class DummyFileOpenService(FileOpenServiceMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_service_file_open")
        self._vlc_checked = False
        self._vlc_path = None


class FileOpenServiceTests(unittest.TestCase):
    def test_vlc_short_path_junction_creation_is_bounded(self) -> None:
        service = DummyFileOpenService()
        calls: list[dict[str, object]] = []

        def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args, returncode=0)

        with patch("mediapipeline.core.files.opening.vlc_needs_short_path", return_value=True):
            with patch("mediapipeline.core.files.opening.subprocess.run", side_effect=fake_run):
                launch_path, cleanup_root = service._vlc_launch_path_for_media(Path(r"C:\Media\Long\Movie.mkv"))

        self.assertEqual(cleanup_root, None)
        self.assertEqual(launch_path, r"C:\Media\Long\Movie.mkv")
        self.assertEqual(calls[0]["kwargs"]["timeout"], MKLINK_JUNCTION_TIMEOUT_SECONDS)
        self.assertTrue(calls[0]["kwargs"]["check"])

    def test_default_app_open_bypasses_vlc_media_opener(self) -> None:
        service = DummyFileOpenService()
        with tempfile.TemporaryDirectory() as raw_root:
            media = Path(raw_root) / "Movie.mkv"
            media.write_bytes(b"media")
            opened: list[Path] = []

            with patch("mediapipeline.core.files.opening.os.name", "nt"):
                with patch.object(service, "_open_media_with_vlc", side_effect=AssertionError("VLC should not be used")):
                    with patch.object(service, "_open_windows_path_with_shell", side_effect=lambda path: opened.append(path)):
                        service.open_path_with_default_app(media)

        self.assertEqual(opened, [media])

    def test_windows_folder_open_launches_explorer_and_requests_foreground(self) -> None:
        service = DummyFileOpenService()
        with tempfile.TemporaryDirectory() as raw_root:
            folder = Path(raw_root)
            with patch(
                "mediapipeline.core.files.opening._top_level_explorer_window_handles",
                side_effect=[[100], [100, 200]],
            ):
                with patch(
                    "mediapipeline.core.files.opening._bring_window_to_foreground",
                    return_value=True,
                ) as foreground:
                    with patch("mediapipeline.core.files.opening.subprocess.Popen") as popen:
                        service._open_windows_path_with_shell(folder)

        popen.assert_called_once_with(["explorer.exe", str(folder)], close_fds=True)
        foreground.assert_called_once_with(200)


if __name__ == "__main__":
    unittest.main()
