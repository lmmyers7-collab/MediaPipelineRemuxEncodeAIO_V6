from __future__ import annotations

from datetime import datetime, UTC
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.block_curate = False
        self.curate_started = threading.Event()
        self.release_curate = threading.Event()
        self.scan_ids = iter(("scan-stable-a", "scan-stable-b", "scan-stable-c"))
        self.synchronize_start_status = False
        self.start_status_barrier = threading.Barrier(2)

    def _queue_scan_id(self) -> str:
        return next(self.scan_ids)

    def _write_queue_scan_status(self, resolved: ResolvedPaths, status: dict[str, object]) -> None:
        if self.synchronize_start_status and status.get("phase") == "starting":
            try:
                self.start_status_barrier.wait(timeout=0.5)
            except threading.BrokenBarrierError:
                pass
        super()._write_queue_scan_status(resolved, status)

    def build_queue_preview(self, _resolved: ResolvedPaths, force_refresh: bool = False) -> list[object]:
        self.curate_force_refresh.append(force_refresh)
        if self.block_curate:
            self.curate_started.set()
            self.release_curate.wait(timeout=5.0)
        return [object(), object()]


class QueueSourceScanTests(unittest.TestCase):
    def test_completed_scan_records_correlated_monotonic_anchor_and_next_scan_clears_it(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            fixed_now = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)

            class AnchoredQueueScanService(DummyQueueScanService):
                def queue_snapshot_freshness_wall_now(self) -> datetime:
                    return fixed_now

                def queue_snapshot_freshness_monotonic_now(self) -> float:
                    return 500.0

                def build_queue_preview(self, current: ResolvedPaths, force_refresh: bool = False) -> list[object]:
                    self.curate_force_refresh.append(force_refresh)
                    if self.block_curate:
                        self.curate_started.set()
                        self.release_curate.wait(timeout=3.0)
                    path = self._queue_snapshot_write_path(current)
                    assert path is not None
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        json.dumps(
                            {
                                "schema_version": "queue_plan_snapshot.v1",
                                "produced_at": fixed_now.isoformat(),
                                "runnable_count": 0,
                                "queue_snapshot_origin": "dry_run",
                                "desktop_queue_preview_request_id": "request-anchor-stable",
                                "queue_plan_fingerprint_schema": "queue_plan_fingerprint.v1",
                                "queue_plan_fingerprint": "plan-anchor-stable",
                                "accepted_run_rows": [],
                                "rows": [],
                            }
                        ),
                        encoding="utf-8",
                    )
                    os.utime(path, (fixed_now.timestamp(), fixed_now.timestamp()))
                    return []

            service = AnchoredQueueScanService(root)
            first = service.start_queue_source_scan(
                resolved,
                {"mode": "inventory_then_curate", "force": True, "scope": "all"},
            )
            for _ in range(100):
                if service.read_queue_scan_status(resolved).get("status") == "completed":
                    break
                time.sleep(0.02)
            anchor = service.queue_snapshot_freshness_anchor()

            self.assertTrue(first["ok"])
            self.assertIsNotNone(anchor)
            assert anchor is not None
            self.assertEqual(anchor.scan_id, "scan-stable-a")
            self.assertEqual(anchor.request_id, "request-anchor-stable")
            self.assertEqual(anchor.queue_plan_fingerprint, "plan-anchor-stable")
            self.assertEqual(anchor.monotonic_at, 500.0)

            service.block_curate = True
            second = service.start_queue_source_scan(
                resolved,
                {"mode": "inventory_then_curate", "force": True, "scope": "all"},
            )
            self.assertTrue(service.curate_started.wait(timeout=2.0))
            active = getattr(service, "_queue_source_scan_active", None)
            thread = active.get("thread") if isinstance(active, dict) else None
            try:
                self.assertTrue(second["ok"])
                self.assertFalse(second.get("duplicate"))
                self.assertIsNone(service.queue_snapshot_freshness_anchor())
            finally:
                service.release_curate.set()
                if isinstance(thread, threading.Thread):
                    thread.join(timeout=2.0)

    def test_two_simultaneous_scan_requests_share_one_lazily_created_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            service = DummyQueueScanService(root)
            service.block_curate = True
            service.synchronize_start_status = True
            callers_ready = threading.Barrier(3)
            constructor_barrier = threading.Barrier(2)
            results: list[dict[str, object]] = []
            results_lock = threading.Lock()
            real_lock_factory = threading.Lock
            factory_count = 0
            factory_count_lock = real_lock_factory()

            def racing_lock_factory():
                nonlocal factory_count
                with factory_count_lock:
                    factory_count += 1
                    call_number = factory_count
                if call_number <= 2:
                    try:
                        constructor_barrier.wait(timeout=0.5)
                    except threading.BrokenBarrierError:
                        pass
                return real_lock_factory()

            def request_scan() -> None:
                callers_ready.wait(timeout=2.0)
                result = service.start_queue_source_scan(
                    resolved,
                    {"mode": "inventory_then_curate", "force": True, "scope": "all"},
                )
                with results_lock:
                    results.append(result)

            callers = [threading.Thread(target=request_scan) for _ in range(2)]
            with patch("mediapipeline.core.queue.service.threading.Lock", side_effect=racing_lock_factory):
                for caller in callers:
                    caller.start()
                callers_ready.wait(timeout=2.0)
                for caller in callers:
                    caller.join(timeout=3.0)

            try:
                self.assertEqual(len(results), 2)
                self.assertEqual(sorted(bool(result.get("duplicate")) for result in results), [False, True])
                self.assertEqual(sum(1 for result in results if result.get("ok")), 2)
            finally:
                service.release_curate.set()
                for thread in list(threading.enumerate()):
                    if thread.name.startswith("queue-source-scan-scan-stable-"):
                        thread.join(timeout=2.0)

            self.assertEqual(service.curate_force_refresh, [True])

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
