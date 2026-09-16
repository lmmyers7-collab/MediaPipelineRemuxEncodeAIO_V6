from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.queue.service import QueueServiceMixin
from mediapipeline.core.queue.discovery_artifact import (
    validate_queue_discovery_artifact,
    write_queue_discovery_artifact,
)
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
        self.block_curate = False
        self.curate_started = threading.Event()
        self.release_curate = threading.Event()

    def build_queue_preview(self, _resolved: ResolvedPaths, force_refresh: bool = False) -> list[object]:
        self.curate_force_refresh.append(force_refresh)
        if self.block_curate:
            self.curate_started.set()
            self.release_curate.wait(timeout=5.0)
        return [object(), object()]


class QueueSourceScanTests(unittest.TestCase):
    def test_discovery_artifact_is_complete_uncapped_and_checksum_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            for index in range(7):
                source = root / "Movies" / f"Movie {index}.mkv"
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(b"media")
            inventory = build_queue_source_inventory(resolved, scan_id="scan-artifact", row_limit=None)
            manifest_path = write_queue_discovery_artifact(resolved, scan_id="scan-artifact", inventory=inventory)
            assert manifest_path is not None

            valid, reason, manifest = validate_queue_discovery_artifact(resolved, manifest_path)
            self.assertTrue(valid, reason)
            assert manifest is not None
            self.assertEqual(manifest["schema_version"], "queue_discovery_manifest.v1")
            self.assertEqual(manifest["candidate_count"], 7)
            candidates_path = Path(manifest["candidates_path"])
            rows = [json.loads(line) for line in candidates_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 7)
            self.assertTrue(all("mtime_ns" in row and "priority_reasons" in row for row in rows))

            candidates_path.write_text(candidates_path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
            valid, reason, _manifest = validate_queue_discovery_artifact(resolved, manifest_path)
            self.assertFalse(valid)
            self.assertEqual(reason, "candidate_checksum_mismatch")

    def test_source_inventory_lists_media_candidates_without_launch_authority(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            tv_file = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            tv_sidecar = root / "TV" / "Show" / "Season 01" / "Show - S01E01.srt"
            movie_file = root / "Movies" / "Movie.mkv"
            anime_file = root / "Anime" / "New Show" / "New Show - S01E01.mp4"
            anime_sidecar = root / "Anime" / "New Show" / "New Show - S01E01.ass"
            ignored_file = root / "TV" / "Show" / "notes.txt"
            for path in (tv_file, tv_sidecar, movie_file, anime_file, anime_sidecar, ignored_file):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")

            inventory = build_queue_source_inventory(resolved, scan_id="scan-1")

        self.assertEqual(inventory["schema_version"], "desktop_queue_source_inventory.v1")
        self.assertEqual(inventory["row_count"], 3)
        self.assertFalse(inventory["launchable"])
        self.assertIn("SourceTV", inventory["source_key_counts"])
        self.assertIn("SourceMovies", inventory["source_key_counts"])
        self.assertIn("LibraryProfiles:anime", inventory["source_key_counts"])
        self.assertEqual(inventory["sidecar_count"], 2)
        self.assertEqual(inventory["sidecar_source_key_counts"], {"LibraryProfiles:anime": 1, "SourceTV": 1})
        self.assertEqual(inventory["sidecar_media_kind_counts"], {"tv": 2})
        self.assertEqual(inventory["sidecar_extension_counts"], {".ass": 1, ".srt": 1})
        self.assertFalse(inventory["sidecar_counts_truncated"])
        self.assertEqual(inventory["candidate_count"], 3)
        self.assertGreaterEqual(inventory["directory_count"], 3)
        self.assertEqual(sum(inventory["phase_timings_ms"].values()), inventory["total_elapsed_ms"])
        self.assertTrue(all(row["launchable"] is False for row in inventory["rows"]))
        self.assertTrue(all(row["route"] == "pending_backend_curation" for row in inventory["rows"]))
        self.assertFalse(any("notes.txt" in row["source_path"] for row in inventory["rows"]))
        self.assertFalse(any(row["source_path"].endswith((".ass", ".srt")) for row in inventory["rows"]))

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
            self.assertEqual(status["candidate_count"], 1)
            self.assertGreaterEqual(status["directory_count"], 1)
            self.assertTrue(status["phase_timings_reconcile"])
            self.assertEqual(sum(status["phase_timings_ms"].values()), status["total_elapsed_ms"])
            self.assertIn("launch_acceptance", status["phase_timings_ms"])
            self.assertEqual(status["cache_decisions"]["source_inventory"], "full_scan")
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

            reuse = service.start_queue_source_scan(
                resolved,
                {"mode": "curate_only", "force": True, "scope": "all"},
            )
            for _ in range(100):
                reused_status = service.read_queue_scan_status(resolved)
                if reused_status.get("status") == "completed" and reused_status.get("scan_id") != status.get("scan_id"):
                    break
                time.sleep(0.05)
            self.assertTrue(reuse["ok"])
            self.assertEqual(reused_status["cache_decisions"]["source_discovery"], "valid_artifact_reuse")

    def test_source_scan_thread_is_not_daemonized_and_blocks_close_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            service = DummyQueueScanService(root)
            service.block_curate = True

            result = service.start_queue_source_scan(
                resolved,
                {"mode": "inventory_then_curate", "force": True, "scope": "all"},
            )
            self.assertTrue(service.curate_started.wait(timeout=2.0))
            active = getattr(service, "_queue_source_scan_active", None)
            thread = active.get("thread") if isinstance(active, dict) else None
            try:
                self.assertTrue(result["ok"])
                self.assertIsInstance(thread, threading.Thread)
                assert isinstance(thread, threading.Thread)
                self.assertFalse(thread.daemon)
                self.assertIn("queue source scan", service.queue_source_scan_active_block_message("Shell close"))
            finally:
                service.release_curate.set()
                if isinstance(thread, threading.Thread):
                    thread.join(timeout=2.0)

            self.assertEqual(service.queue_source_scan_active_block_message("Shell close"), "")


if __name__ == "__main__":
    unittest.main()
