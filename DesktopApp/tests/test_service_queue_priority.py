from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.queue.service import QueueServiceMixin
from app.queue.priority_markers import (
    apply_priority_marker,
    format_priority_leaf_name,
    get_source_priority_info,
    path_is_unc,
    priority_marker_destination,
    safe_mtime,
)


class QueuePriorityHelperTests(unittest.TestCase):
    def test_format_priority_leaf_name_removes_existing_markers(self) -> None:
        self.assertEqual(format_priority_leaf_name("[NOW]", "! Movie", ["!", "[NOW]"]), "[NOW] Movie")
        self.assertEqual(format_priority_leaf_name("!", "", ["!"]), "")

    def test_priority_marker_destination_handles_files_and_folders(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            media = root / "Movie.mkv"
            folder = root / "Season 01"
            media.write_text("x", encoding="utf-8")
            folder.mkdir()

            self.assertEqual(priority_marker_destination(media, ["!"], "!!").name, "!! Movie.mkv")
            self.assertEqual(priority_marker_destination(root / "! Movie.mkv", ["!"], "!", remove_only=True).name, "Movie.mkv")
            self.assertEqual(priority_marker_destination(folder, ["!"], "!").name, "! Season 01")

    def test_apply_priority_marker_renames_file_and_remove_only_restores_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            media = Path(td) / "Movie.mkv"
            media.write_text("x", encoding="utf-8")
            before = media.stat().st_mtime
            time.sleep(0.01)

            renamed = apply_priority_marker(media, ["!"], "!")
            restored = apply_priority_marker(renamed, ["!"], "!", remove_only=True)

            self.assertEqual(renamed.name, "! Movie.mkv")
            self.assertEqual(restored.name, "Movie.mkv")
            self.assertTrue(restored.exists())
            self.assertGreaterEqual(renamed.stat().st_mtime if renamed.exists() else restored.stat().st_mtime, before)

    def test_apply_priority_marker_rejects_collision(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            media = root / "Movie.mkv"
            collision = root / "! Movie.mkv"
            media.write_text("x", encoding="utf-8")
            collision.write_text("existing", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                apply_priority_marker(media, ["!"], "!")

    def test_get_source_priority_info_collects_file_and_folder_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "! Season 01"
            folder.mkdir()
            media = folder / "! Episode.mkv"
            media.write_text("x", encoding="utf-8")
            stat_cache = {media: 100.0, folder: 200.0}

            is_priority, reasons, rank = get_source_priority_info(media, ["!"], stat_cache)

            self.assertTrue(is_priority)
            self.assertEqual(reasons, ["file", "folder:! Season 01"])
            self.assertEqual(rank, 200.0)

    def test_path_and_mtime_wrappers_remain_available_on_queue_service(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            media = Path(td) / "Movie.mkv"
            media.write_text("x", encoding="utf-8")
            service = QueueServiceMixin()

            self.assertFalse(path_is_unc(media))
            self.assertFalse(service._path_is_unc(media))
            self.assertGreater(safe_mtime(media), 0.0)
            self.assertGreater(service._safe_mtime(media), 0.0)


if __name__ == "__main__":
    unittest.main()
