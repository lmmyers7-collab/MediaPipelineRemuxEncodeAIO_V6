from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.queue.dry_run_runner import run_queue_dry_run_for_service
from mediapipeline.core.queue.snapshot import (
    queue_snapshot_write_path,
    read_queue_snapshot,
)
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult


class DummyQueueDryRunService:
    QUEUE_DRY_RUN_TIMEOUT_SECONDS = 120.0
    QUEUE_DRY_RUN_OUTPUT_TAIL_LINES = 3

    def __init__(self, root: Path) -> None:
        self.app_root = root / "DesktopApp"
        self.workspace_root = root
        self.app_root.mkdir()
        self._queue_completed_cache_status = ""

    def _queue_snapshot_write_path(self, resolved: ResolvedPaths) -> Path | None:
        return queue_snapshot_write_path(resolved)

    def _read_queue_snapshot(self, path: Path) -> dict | None:
        return read_queue_snapshot(path)

    def _queue_snapshot_is_current_for_request(self, _path: Path, _snapshot: dict, _started_at: float) -> bool:
        return True

    def _build_launch_environment(self) -> dict[str, str]:
        return {"PATH": "test-path"}

    def _subprocess_kwargs_hidden(self) -> dict[str, object]:
        return {"creationflags": 0}


def _resolved(root: Path) -> ResolvedPaths:
    local_base = root / "LocalBase"
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "config.psd1",
        audit_script_path=root / "Pipeline" / "audit.ps1",
        rerun_script_path=root / "Pipeline" / "rerun.ps1",
        powershell_host="pwsh",
        local_base=local_base,
        state_root=local_base / "State",
    )


def _snapshot_payload(produced_at: str, rows: list[dict] | None = None) -> dict:
    return {
        "schema_version": "queue_plan_snapshot.v1",
        "produced_at": produced_at,
        "config_path": "config.psd1",
        "local_base": "LocalBase",
        "source_movies": "Movies",
        "source_tv": "TV",
        "outsource": "Out",
        "movie_count_total": 0,
        "tv_count_total": 0,
        "priority_count": 0,
        "runnable_count": len(rows or []),
        "rows": rows or [],
    }


class QueueDryRunRunnerTests(unittest.TestCase):
    def test_run_queue_dry_run_writes_promoted_snapshot_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyQueueDryRunService(root)
            resolved = _resolved(root)
            captured: dict[str, object] = {}

            def fake_run_capture(args, **kwargs):
                captured["args"] = list(args)
                captured["kwargs"] = kwargs
                temp_path = Path(args[args.index("-QueuePlanOutPath") + 1])
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_text(
                    json.dumps(_snapshot_payload("2026-05-08T10:00:00")),
                    encoding="utf-8",
                )
                return CapturedCommandResult(args=args, returncode=0, stdout="", stderr="")

            with patch("mediapipeline.core.queue.dry_run_runner.run_capture", fake_run_capture):
                snapshot = run_queue_dry_run_for_service(service, resolved)

            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertTrue(snapshot["desktop_queue_preview_request_id"])
            final_path = queue_snapshot_write_path(resolved)
            self.assertIsNotNone(final_path)
            assert final_path is not None
            promoted = json.loads(final_path.read_text(encoding="utf-8"))
            self.assertEqual(promoted["desktop_queue_preview_request_id"], snapshot["desktop_queue_preview_request_id"])
            temp_path = Path(captured["args"][captured["args"].index("-QueuePlanOutPath") + 1])
            self.assertFalse(temp_path.exists())
            self.assertEqual(captured["kwargs"]["timeout_seconds"], service.QUEUE_DRY_RUN_TIMEOUT_SECONDS)
            self.assertEqual(captured["kwargs"]["cwd"], root)
            self.assertEqual(captured["kwargs"]["env"], {"PATH": "test-path"})
            self.assertEqual(captured["kwargs"]["extra_popen_kwargs"], {"creationflags": 0})

    def test_run_queue_dry_run_timeout_can_return_cached_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyQueueDryRunService(root)
            resolved = _resolved(root)
            final_path = queue_snapshot_write_path(resolved)
            assert final_path is not None
            final_path.parent.mkdir(parents=True, exist_ok=True)
            cached_payload = _snapshot_payload("cached")
            final_path.write_text(json.dumps(cached_payload), encoding="utf-8")

            def fake_run_capture(args, **_kwargs):
                temp_path = Path(args[args.index("-QueuePlanOutPath") + 1])
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_text("partial", encoding="utf-8")
                return CapturedCommandResult(
                    args=args,
                    returncode=None,
                    stdout="",
                    stderr="",
                    timed_out=True,
                    kill_message="process killed",
                )

            with patch("mediapipeline.core.queue.dry_run_runner.run_capture", fake_run_capture):
                snapshot = run_queue_dry_run_for_service(service, resolved, allow_cached_fallback=True)

            self.assertEqual(snapshot, cached_payload)
            self.assertIn("timed out", service._queue_completed_cache_status)
            self.assertIn("Showing last cached snapshot", service._queue_completed_cache_status)

    def test_run_queue_dry_run_without_local_base_sets_status_and_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyQueueDryRunService(root)
            resolved = ResolvedPaths(
                app_root=root / "DesktopApp",
                workspace_root=root,
                pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
                config_path=root / "Pipeline" / "config.psd1",
                audit_script_path=root / "Pipeline" / "audit.ps1",
                rerun_script_path=root / "Pipeline" / "rerun.ps1",
                powershell_host="pwsh",
            )

            snapshot = run_queue_dry_run_for_service(service, resolved)

            self.assertIsNone(snapshot)
            self.assertEqual(service._queue_completed_cache_status, "LocalBase not configured; cannot run queue dry-run.")


if __name__ == "__main__":
    unittest.main()
