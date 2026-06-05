from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.queue.service import QueueServiceMixin
from mediapipeline.core.queue.snapshot import (
    queue_dry_run_tail,
    queue_record_from_snapshot_row,
    queue_snapshot_is_current_for_request,
    queue_snapshot_path,
    queue_snapshot_write_path,
    read_queue_snapshot,
)


def _snapshot_payload(root: Path, rows: list[dict] | None = None) -> dict:
    return {
        "schema_version": "queue_plan_snapshot.v1",
        "produced_at": datetime.now().isoformat(),
        "config_path": str(root / "config.psd1"),
        "local_base": str(root),
        "source_movies": str(root / "Movies"),
        "source_tv": str(root / "TV"),
        "outsource": str(root / "Outsource"),
        "movie_count_total": 1,
        "tv_count_total": 0,
        "priority_count": 0,
        "runnable_count": len(rows or []),
        "rows": rows or [],
    }


def _queue_row(root: Path, **overrides) -> dict:
    source = root / "Movies" / "Movie.mkv"
    row = {
        "global_order": 1,
        "phase": "movie",
        "media_kind": "movie",
        "queue_index": 1,
        "queue_total": 1,
        "is_priority": False,
        "source_path": str(source),
        "root_path": str(root / "Movies"),
        "relative_path": "Movie.mkv",
        "display_name": "Movie.mkv",
        "size_gb": 1.5,
        "route": "remux",
        "route_reason_code": "copy_compatible",
        "route_reason": "already compatible",
        "blocked_reason": "",
        "last_write_utc": "2026-05-08T12:00:00Z",
    }
    row.update(overrides)
    return row


def _parse_datetime(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


class _QueueSnapshotWrapperService(QueueServiceMixin):
    def _parse_progress_datetime(self, raw: str) -> datetime | None:
        return _parse_datetime(raw)


class ServiceQueueSnapshotTests(unittest.TestCase):
    def test_queue_snapshot_paths_prefer_state_progress_write_location(self) -> None:
        root = Path(r"C:\MediaPipeline")
        resolved = ResolvedPaths(
            app_root=root,
            workspace_root=root,
            pipeline_path=root / "pipeline.ps1",
            config_path=root / "config.psd1",
            audit_script_path=root / "audit.ps1",
            rerun_script_path=root / "rerun.ps1",
            powershell_host=None,
        )
        resolved.state_root = root / "State"
        resolved.queue_snapshot_path = root / "legacy_queue_snapshot.json"

        self.assertEqual(queue_snapshot_path(resolved), root / "legacy_queue_snapshot.json")
        self.assertEqual(queue_snapshot_write_path(resolved), root / "State" / "Progress" / "queue_snapshot.json")

    def test_read_queue_snapshot_accepts_bom_and_rejects_invalid_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            valid_path = root / "queue_snapshot.json"
            valid_path.write_text("\ufeff" + json.dumps(_snapshot_payload(root, [_queue_row(root)])), encoding="utf-8")
            invalid_path = root / "invalid.json"
            invalid_path.write_text(json.dumps({"schema_version": "queue_plan_snapshot.v1"}), encoding="utf-8")

            valid = read_queue_snapshot(valid_path)
            invalid = read_queue_snapshot(invalid_path)

        self.assertIsNotNone(valid)
        assert valid is not None
        self.assertEqual(valid["runnable_count"], 1)
        self.assertIsNone(invalid)

    def test_queue_snapshot_is_current_for_request_checks_file_and_produced_times(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot_path = root / "queue_snapshot.json"
            snapshot_path.write_text(json.dumps(_snapshot_payload(root)), encoding="utf-8")
            started_at = time.time() - 0.1
            current_snapshot = _snapshot_payload(root)
            stale_snapshot = dict(current_snapshot)
            stale_snapshot["produced_at"] = "2000-01-01T00:00:00"

            self.assertTrue(
                queue_snapshot_is_current_for_request(
                    snapshot_path,
                    current_snapshot,
                    started_at,
                    parse_progress_datetime=_parse_datetime,
                )
            )
            self.assertFalse(
                queue_snapshot_is_current_for_request(
                    snapshot_path,
                    stale_snapshot,
                    started_at,
                    parse_progress_datetime=_parse_datetime,
                )
            )

    def test_queue_dry_run_tail_prefers_stderr_and_bounds_lines(self) -> None:
        self.assertEqual(queue_dry_run_tail("out1\nout2", "err1\nerr2\nerr3", max_lines=2), "err2 | err3")
        self.assertEqual(queue_dry_run_tail("", "", max_lines=2), "no output")

    def test_queue_record_from_snapshot_row_maps_tv_priority_fields(self) -> None:
        root = Path(r"C:\Media")
        row = _queue_row(
            root,
            phase="priority",
            media_kind="tv",
            is_priority=True,
            priority_reasons=["file"],
            priority_rank=10,
            source_path=str(root / "TV" / "Show" / "S01E01.mkv"),
            root_path=str(root / "TV"),
            relative_path=r"Show\S01E01.mkv",
            display_name="Show - S01E01.mkv",
            season_number=1,
            episode_number=1,
            route="encode",
        )

        record = queue_record_from_snapshot_row(row)

        self.assertEqual(record.media_type, "TV")
        self.assertEqual(record.phase, "PRIORITY")
        self.assertTrue(record.is_priority)
        self.assertEqual(record.priority_reasons, ["file"])
        self.assertEqual(record.route_name, "encode")
        self.assertEqual(record.season_number, 1)
        self.assertEqual(record.episode_number, 1)

    def test_queue_record_from_snapshot_row_maps_backend_phase_labels(self) -> None:
        root = Path(r"C:\Media")
        cases = [
            ("movie", "MOVIE", "normal"),
            ("tv", "TV", "normal"),
            ("priority", "PRIORITY", "high"),
            ("priority_movie", "PRIORITY", "high"),
            ("priority_tv", "PRIORITY", "high"),
            ("low", "LOW", "low"),
            ("hold", "HOLD", "hold"),
        ]

        for phase, expected_label, manifest_level in cases:
            with self.subTest(phase=phase):
                media_kind = "tv" if phase in {"tv", "priority_tv"} else "movie"
                record = queue_record_from_snapshot_row(
                    _queue_row(
                        root,
                        phase=phase,
                        media_kind=media_kind,
                        manifest_priority_level=manifest_level,
                    )
                )

                self.assertEqual(record.phase, expected_label)
                self.assertEqual(record.manifest_priority_level, manifest_level)

    def test_service_mixin_preserves_queue_snapshot_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot_path = root / "queue_snapshot.json"
            snapshot_path.write_text(json.dumps(_snapshot_payload(root, [_queue_row(root)])), encoding="utf-8")
            service = _QueueSnapshotWrapperService()

            snapshot = service._read_queue_snapshot(snapshot_path)
            tail = service._queue_dry_run_tail("a\nb\nc", None)
            record = service._queue_record_from_snapshot_row(_queue_row(root))

        self.assertIsNotNone(snapshot)
        self.assertEqual(tail, "a | b | c")
        self.assertEqual(record.display_name, "Movie.mkv")


if __name__ == "__main__":
    unittest.main()
