from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.status.rerun_completion import csv_rerun_completion_summary  # noqa: E402
from mediapipeline.desktop.application import MediaPipelineApplicationFacade  # noqa: E402
from mediapipeline.desktop.models import Snapshot  # noqa: E402
from tests.python.desktop.application_facade_test_support import DummyFacadeService, _resolved  # noqa: E402


class CsvRerunCompletionSummaryTests(unittest.TestCase):
    def _resolved(self, root: Path):
        resolved = _resolved(root)
        resolved.local_base = root / "LocalBase"
        resolved.state_root = resolved.local_base / "State"
        return resolved

    def _write_manifest(self, resolved, *, status: str, rows: list[dict], csv_name: str = "current-rerun.csv") -> None:
        assert resolved.local_base is not None
        manifest_root = resolved.local_base / "RerunManifests"
        manifest_root.mkdir(parents=True)
        csv_path = resolved.workspace_root / csv_name
        csv_path.write_text("source_path\n", encoding="utf-8")
        (manifest_root / "current-rerun.json").write_text(
            json.dumps(
                {
                    "batch_id": "current-rerun",
                    "status": status,
                    "csv_path": str(csv_path),
                    "created_at": "2026-07-09T12:00:00Z",
                    "completed_at": "2026-07-09T12:10:00Z",
                    "rows": rows,
                }
            ),
            encoding="utf-8",
        )

    def test_completed_csv_has_definitive_success_summary(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            resolved = self._resolved(Path(raw_root))
            self._write_manifest(
                resolved,
                status="complete",
                rows=[{"status": "completed"}, {"status": "published_replace_final"}, {"status": "skipped"}],
            )

            summary = csv_rerun_completion_summary(resolved)

        self.assertEqual(summary["status"], "complete")
        self.assertTrue(summary["terminal"])
        self.assertEqual(summary["display_label"], "CSV rerun complete")
        self.assertEqual(summary["csv_name"], "current-rerun.csv")
        self.assertEqual(summary["totals"], {"total": 3, "processed": 3, "completed": 2, "failed": 0, "skipped": 1, "held": 0, "pending": 0, "pending_publish": 0})

    def test_terminal_csv_with_failures_is_not_reported_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            resolved = self._resolved(Path(raw_root))
            self._write_manifest(resolved, status="complete", rows=[{"status": "completed"}, {"status": "failed"}])

            summary = csv_rerun_completion_summary(resolved)

        self.assertEqual(summary["status"], "completed_with_failures")
        self.assertTrue(summary["terminal"])
        self.assertEqual(summary["display_label"], "CSV rerun complete with failures")
        self.assertTrue(summary["attention_required"])
        self.assertEqual(summary["totals"]["failed"], 1)

    def test_empty_csv_is_a_distinct_terminal_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            resolved = self._resolved(Path(raw_root))
            self._write_manifest(resolved, status="complete", rows=[])

            summary = csv_rerun_completion_summary(resolved)

        self.assertEqual(summary["status"], "empty")
        self.assertTrue(summary["terminal"])
        self.assertEqual(summary["display_label"], "CSV rerun complete — no rows")
        self.assertEqual(summary["totals"]["total"], 0)

    def test_pending_publish_is_terminal_but_requires_attention(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            resolved = self._resolved(Path(raw_root))
            self._write_manifest(resolved, status="complete", rows=[{"status": "completed"}, {"status": "pending_publish"}])

            summary = csv_rerun_completion_summary(resolved)

        self.assertEqual(summary["status"], "pending_publish")
        self.assertTrue(summary["terminal"])
        self.assertEqual(summary["display_label"], "CSV rerun complete — pending publish")
        self.assertTrue(summary["attention_required"])
        self.assertEqual(summary["totals"]["pending_publish"], 1)

    def test_active_csv_is_not_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            resolved = self._resolved(Path(raw_root))
            self._write_manifest(resolved, status="active", rows=[{"status": "completed"}, {"status": "pending"}])

            summary = csv_rerun_completion_summary(resolved)

        self.assertEqual(summary["status"], "active")
        self.assertFalse(summary["terminal"])
        self.assertEqual(summary["totals"]["pending"], 1)

    def test_cancelled_csv_is_terminal_attention_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            resolved = self._resolved(Path(raw_root))
            self._write_manifest(resolved, status="stopped_after_current", rows=[{"status": "completed"}, {"status": "pending"}])

            summary = csv_rerun_completion_summary(resolved)

        self.assertEqual(summary["status"], "cancelled")
        self.assertTrue(summary["terminal"])
        self.assertTrue(summary["attention_required"])
        self.assertEqual(summary["display_label"], "CSV rerun stopped")

    def test_snapshot_keeps_current_csv_completion_over_stale_progress_context(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = self._resolved(root)
            self._write_manifest(resolved, status="complete", rows=[{"status": "completed"}])
            service = DummyFacadeService(root)
            service.snapshot = Snapshot(
                resolved=resolved,
                current_activity="Stale progress from previous run; latest event: tool_started.",
                status_summary="Stale progress fixture.",
                log_tail="",
                progress={
                    "Status": "Processing",
                    "LastUpdate": (datetime.now() - timedelta(minutes=5)).isoformat(),
                    "CurrentStage": "csv_rerun",
                },
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            snapshot = MediaPipelineApplicationFacade(service, app_version="test").get_snapshot(resolved)

        self.assertEqual(snapshot.pipeline_state, "idle")
        self.assertEqual(snapshot.csv_rerun_summary["status"], "complete")
        self.assertTrue(snapshot.csv_rerun_summary["terminal"])


if __name__ == "__main__":
    unittest.main()
