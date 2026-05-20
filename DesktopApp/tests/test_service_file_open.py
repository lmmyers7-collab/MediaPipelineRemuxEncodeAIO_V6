from __future__ import annotations

import logging
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_file_open import FileOpenServiceMixin
from mediapipeline_desktop_app.service_file_open_plan import MKLINK_JUNCTION_TIMEOUT_SECONDS


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

        with patch("mediapipeline_desktop_app.service_file_open.vlc_needs_short_path", return_value=True):
            with patch("mediapipeline_desktop_app.service_file_open.subprocess.run", side_effect=fake_run):
                launch_path, cleanup_root = service._vlc_launch_path_for_media(Path(r"C:\Media\Long\Movie.mkv"))

        self.assertEqual(cleanup_root, None)
        self.assertEqual(launch_path, r"C:\Media\Long\Movie.mkv")
        self.assertEqual(calls[0]["kwargs"]["timeout"], MKLINK_JUNCTION_TIMEOUT_SECONDS)
        self.assertTrue(calls[0]["kwargs"]["check"])


if __name__ == "__main__":
    unittest.main()
