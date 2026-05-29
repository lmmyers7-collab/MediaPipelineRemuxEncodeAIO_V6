from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from app.queue.preview_builder import build_queue_preview_for_service


class DummyQueuePreviewService:
    QUEUE_SNAPSHOT_FRESH_SECONDS = 60.0

    def __init__(self, snapshot_path: Path | None) -> None:
        self.snapshot_path = snapshot_path
        self.snapshot_to_read: dict | None = None
        self.dry_run_snapshot: dict | None = None
        self.dry_run_calls: list[bool] = []
        self._queue_completed_excluded = 99
        self._queue_source_candidates = 99
        self._queue_completed_size_mismatches = 99
        self._queue_completed_identity_mismatches = 99
        self._queue_completed_unverified = 99
        self._queue_scan_limited = True
        self._queue_completed_cache_status = "stale"

    def _queue_snapshot_path(self, _resolved: ResolvedPaths) -> Path | None:
        return self.snapshot_path

    def _read_queue_snapshot(self, _path: Path) -> dict | None:
        return self.snapshot_to_read

    def _run_queue_dry_run(self, _resolved: ResolvedPaths, *, allow_cached_fallback: bool = False) -> dict | None:
        self.dry_run_calls.append(allow_cached_fallback)
        return self.dry_run_snapshot

    def _queue_record_from_snapshot_row(self, row: dict) -> str:
        return str(row.get("display_name") or "")


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "config.psd1",
        audit_script_path=root / "Pipeline" / "audit.ps1",
        rerun_script_path=root / "Pipeline" / "rerun.ps1",
        powershell_host=None,
    )


class QueuePreviewBuilderTests(unittest.TestCase):
    def test_fresh_snapshot_builds_records_without_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot_path = root / "queue_snapshot.json"
            snapshot_path.write_text("{}", encoding="utf-8")
            service = DummyQueuePreviewService(snapshot_path)
            service.snapshot_to_read = {
                "produced_at": "2026-05-08T10:00:00",
                "movie_count_total": 2,
                "tv_count_total": 1,
                "rows": [{"display_name": "A"}, {"display_name": "B"}],
            }

            records = build_queue_preview_for_service(service, _resolved(root))

        self.assertEqual(records, ["A", "B"])
        self.assertEqual(service.dry_run_calls, [])
        self.assertEqual(service._queue_source_candidates, 3)
        self.assertEqual(service._queue_completed_excluded, 1)
        self.assertFalse(service._queue_scan_limited)
        self.assertIn("Queue plan source: snapshot @ 2026-05-08T10:00:00", service._queue_completed_cache_status)

    def test_force_refresh_bypasses_fresh_snapshot_and_disables_cached_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot_path = root / "queue_snapshot.json"
            snapshot_path.write_text("{}", encoding="utf-8")
            service = DummyQueuePreviewService(snapshot_path)
            service.snapshot_to_read = {
                "produced_at": "stale",
                "movie_count_total": 1,
                "tv_count_total": 0,
                "rows": [{"display_name": "stale"}],
            }
            service.dry_run_snapshot = {
                "produced_at": "fresh",
                "desktop_queue_preview_request_id": "abcdef123456",
                "movie_count_total": 1,
                "tv_count_total": 0,
                "rows": [{"display_name": "fresh"}],
            }

            records = build_queue_preview_for_service(service, _resolved(root), force_refresh=True)

        self.assertEqual(records, ["fresh"])
        self.assertEqual(service.dry_run_calls, [False])
        self.assertIn("live (dry run abcdef12)", service._queue_completed_cache_status)

    def test_missing_snapshot_reports_empty_preview_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyQueuePreviewService(None)

            records = build_queue_preview_for_service(service, _resolved(root))

        self.assertEqual(records, [])
        self.assertEqual(service.dry_run_calls, [True])
        self.assertEqual(service._queue_completed_cache_status, "No queue snapshot available; run the pipeline once or refresh.")


if __name__ == "__main__":
    unittest.main()
