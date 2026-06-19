from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.queue.service import QueueServiceMixin
from mediapipeline.core.queue.priority_markers import (
    apply_priority_marker,
    format_priority_leaf_name,
    get_source_priority_info,
    path_is_unc,
    priority_marker_destination,
    safe_mtime,
)
from mediapipeline.core.queue.priority_manifest import (
    PriorityManifestReadError,
    get_manifest_level,
    has_manifest_priority_entry,
    read_priority_manifest,
    set_manifest_entries_bulk,
    set_manifest_entry,
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

    def test_manifest_normal_can_override_parent_priority(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "priority_manifest.json"
            folder = root / "TV" / "Show"
            media = folder / "S01E01.mkv"
            sibling = folder / "S01E02.mkv"

            set_manifest_entry(manifest_path, folder, "low", "folder low")
            manifest = set_manifest_entry(manifest_path, media, "normal", "file normal")

            self.assertEqual(get_manifest_level(manifest, media), "normal")
            self.assertTrue(has_manifest_priority_entry(manifest, media))
            self.assertEqual(get_manifest_level(manifest, sibling), "low")
            self.assertTrue(has_manifest_priority_entry(manifest, sibling))
            entries = read_priority_manifest(manifest_path)["entries"]
            self.assertEqual(entries[str(media).replace("\\", "/").lower()]["level"], "normal")

    def test_manifest_normal_without_parent_removes_exact_entry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "priority_manifest.json"
            media = root / "Movies" / "Movie.mkv"

            set_manifest_entry(manifest_path, media, "high", "promote")
            manifest = set_manifest_entry(manifest_path, media, "normal", "clear")

            self.assertEqual(get_manifest_level(manifest, media), "normal")
            self.assertFalse(has_manifest_priority_entry(manifest, media))
            self.assertEqual(read_priority_manifest(manifest_path)["entries"], {})

    def test_manifest_new_priority_level_overwrites_exact_entry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "priority_manifest.json"
            media = root / "Movies" / "Movie.mkv"

            set_manifest_entry(manifest_path, media, "low", "demote")
            manifest = set_manifest_entry(manifest_path, media, "high", "promote")

            key = str(media).replace("\\", "/").lower()
            self.assertEqual(get_manifest_level(manifest, media), "high")
            self.assertEqual(read_priority_manifest(manifest_path)["entries"][key]["level"], "high")

    def test_manifest_normal_position_entry_is_preserved_for_manual_order(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "priority_manifest.json"
            media = root / "Movies" / "Movie.mkv"

            manifest = set_manifest_entry(manifest_path, media, "normal", position=3)

            key = str(media).replace("\\", "/").lower()
            entry = manifest["entries"][key]
            self.assertEqual(get_manifest_level(manifest, media), "normal")
            self.assertEqual(entry["level"], "normal")
            self.assertEqual(entry["position"], 3.0)

    def test_bulk_priority_update_preserves_existing_manual_position_and_reason_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "priority_manifest.json"
            media = root / "Movies" / "Movie.mkv"

            set_manifest_entry(manifest_path, media, "low", "keep reason", position=7)
            manifest = set_manifest_entries_bulk(manifest_path, [{"path": str(media), "level": "high"}])

            key = str(media).replace("\\", "/").lower()
            entry = manifest["entries"][key]
            self.assertEqual(entry["level"], "high")
            self.assertEqual(entry["reason"], "keep reason")
            self.assertEqual(entry["position"], 7.0)

    def test_malformed_manifest_legacy_read_falls_back_but_fail_closed_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "priority_manifest.json"
            manifest_path.write_text("{not-json", encoding="utf-8")

            self.assertEqual(read_priority_manifest(manifest_path)["entries"], {})
            with self.assertRaises(PriorityManifestReadError):
                read_priority_manifest(manifest_path, fail_closed=True)

    def test_malformed_manifest_blocks_normal_update_until_explicit_clear(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = root / "priority_manifest.json"
            media = root / "Movies" / "Movie.mkv"
            manifest_path.write_text("{not-json", encoding="utf-8")

            with self.assertRaises(PriorityManifestReadError):
                set_manifest_entry(manifest_path, media, "hold", "operator hold")

            self.assertEqual(manifest_path.read_text(encoding="utf-8"), "{not-json")

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
