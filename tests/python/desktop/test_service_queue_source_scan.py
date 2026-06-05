from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.queue.service import QueueServiceMixin
from mediapipeline.core.queue.source_inventory import build_queue_source_inventory, queue_scan_status_path, queue_source_inventory_path
from mediapipeline.desktop.models import ResolvedPaths


def _resolved(root: Path) -> ResolvedPaths:
    local_base = root / "LocalBase"
    state_root = local_base / "State"
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "config.psd1",
        audit_script_path=root / "Pipeline" / "audit.ps1",
        rerun_script_path=root / "Pipeline" / "rerun.ps1",
        powershell_host="pwsh",
        local_base=local_base,
        state_root=state_root,
        source_movies=root / "Movies",
        source_tv=root / "TV",
        queue_snapshot_path=state_root / "Progress" / "queue_snapshot.json",
        config_data={
            "SourceMovies": str(root / "Movies"),
            "SourceTV": str(root / "TV"),
            "LibraryProfiles": [
                {
                    "id": "anime",
                    "name": "Anime",
                    "enabled": True,
                    "designation": "tv",
                    "source_path": str(root / "Anime"),
                    "output_path": str(root / "Out"),
                }
            ],
        },
    )


class DummyQueueScanService(QueueServiceMixin):
    def __init__(self, root: Path) -> None:
        self.app_root = root / "DesktopApp"
        self.workspace_root = root
        self.curate_force_refresh: list[bool] = []

    def build_queue_preview(self, _resolved: ResolvedPaths, force_refresh: bool = False) -> list[object]:
        self.curate_force_refresh.append(force_refresh)
        return [object(), object()]


class QueueSourceScanTests(unittest.TestCase):
    def test_source_inventory_lists_media_candidates_without_launch_authority(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_file = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            movie_file = root / "Movies" / "Movie.mkv"
            anime_file = root / "Anime" / "New Show" / "New Show - S01E01.mp4"
            ignored_file = root / "TV" / "Show" / "notes.txt"
            for path in (tv_file, movie_file, anime_file, ignored_file):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")

            inventory = build_queue_source_inventory(resolved, scan_id="scan-1")

        self.assertEqual(inventory["schema_version"], "desktop_queue_source_inventory.v1")
        self.assertEqual(inventory["row_count"], 3)
        self.assertFalse(inventory["launchable"])
        self.assertIn("SourceTV", inventory["source_key_counts"])
        self.assertIn("SourceMovies", inventory["source_key_counts"])
        self.assertIn("LibraryProfiles:anime", inventory["source_key_counts"])
        self.assertTrue(all(row["launchable"] is False for row in inventory["rows"]))
        self.assertTrue(all(row["route"] == "pending_backend_curation" for row in inventory["rows"]))
        self.assertFalse(any("notes.txt" in row["source_path"] for row in inventory["rows"]))

    def test_start_queue_source_scan_writes_inventory_then_curation_status(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            service = DummyQueueScanService(root)

            result = service.start_queue_source_scan(
                resolved,
                {"mode": "inventory_then_curate", "force": True, "scope": "all"},
            )
            for _ in range(100):
                status = service.read_queue_scan_status(resolved)
                if status.get("status") == "completed":
                    break
                time.sleep(0.05)

            status_path = queue_scan_status_path(resolved)
            inventory_path = queue_source_inventory_path(resolved)
            inventory = service.read_queue_source_inventory(resolved)

            self.assertTrue(result["ok"])
            self.assertEqual(status["status"], "completed")
            self.assertEqual(status["phase"], "complete")
            self.assertEqual(status["inventory_count"], 1)
            self.assertEqual(status["curated_row_count"], 2)
            self.assertEqual(service.curate_force_refresh, [True])
            self.assertIsNotNone(status_path)
            self.assertIsNotNone(inventory_path)
            assert status_path is not None
            assert inventory_path is not None
            self.assertTrue(status_path.exists())
            self.assertTrue(inventory_path.exists())
            self.assertEqual(inventory["row_count"], 1)
            self.assertFalse(inventory["launchable"])
            self.assertEqual(inventory["rows"][0]["curation_state"], "uncurated")


if __name__ == "__main__":
    unittest.main()
