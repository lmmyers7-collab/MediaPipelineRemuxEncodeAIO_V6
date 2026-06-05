from __future__ import annotations

import logging
import subprocess
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
