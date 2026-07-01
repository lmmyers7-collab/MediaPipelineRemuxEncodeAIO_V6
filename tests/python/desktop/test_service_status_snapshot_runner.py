from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.status.snapshot_runner import build_snapshot_for_service


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
        failed_reports_path=root / "Failures",
        audit_reports_path=root / "Audit",
        progress_file=root / "progress.json",
        event_file=root / "events.jsonl",
        log_file=root / "pipeline.log",
    )


class _DummyStatusSnapshotService:
    def __init__(
        self,
        *,
        stale: bool = False,
        activity: str = "Encoding Movie.mkv",
        fail_reconcile: bool = False,
    ) -> None:
        self.logger = logging.getLogger("test_service_status_snapshot_runner")
        self.stale = stale
        self.activity = activity
        self.fail_reconcile = fail_reconcile
        self.calls: list[str] = []
        self.progress = {"Status": "Processing"}
        self.audit_progress = {"Status": "Audit"}
        self.events = [{"event_type": "job_started"}]

    def reconcile_active_job_records(self, resolved: ResolvedPaths) -> None:
        _ = resolved
        self.calls.append("reconcile")
        if self.fail_reconcile:
            raise RuntimeError("offline")

    def read_progress(self, resolved: ResolvedPaths):
        _ = resolved
        self.calls.append("progress")
        return self.progress

    def read_audit_progress(self, resolved: ResolvedPaths):
        _ = resolved
        self.calls.append("audit_progress")
        return self.audit_progress

    def latest_matching_file(self, folder: Path | None, pattern: str) -> Path:
        _ = folder, pattern
        self.calls.append("failure_report")
        return Path("round_failures_1.txt")

    def latest_failure_json(self, resolved: ResolvedPaths) -> Path:
        _ = resolved
        self.calls.append("failure_json")
        return Path("failure.json")

    def latest_audit_csv(self, resolved: ResolvedPaths, priority_only: bool) -> Path:
        _ = resolved
        self.calls.append("priority_csv" if priority_only else "audit_csv")
        return Path("priority.csv" if priority_only else "audit.csv")

    def read_log_tail(self, resolved: ResolvedPaths) -> str:
        _ = resolved
        self.calls.append("log_tail")
        return "log tail"

    def read_pipeline_events_tail(self, resolved: ResolvedPaths):
        _ = resolved
        self.calls.append("events")
        return self.events

    def _build_status_summary(self, **kwargs) -> str:
        self.calls.append("summary")
        self.summary_kwargs = kwargs
        return "status summary"

    def is_progress_stale(self, progress) -> bool:
        _ = progress
        self.calls.append("stale")
        return self.stale

    def _build_current_activity(self, resolved: ResolvedPaths, progress, log_tail: str, pipeline_events):
        _ = resolved, progress, log_tail, pipeline_events
        self.calls.append("activity")
        self.activity_progress = progress
        return self.activity


class ServiceStatusSnapshotRunnerTests(unittest.TestCase):
    def test_build_snapshot_collects_readers_and_returns_snapshot_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = _resolved(Path(temp_dir))
            service = _DummyStatusSnapshotService()

            snapshot = build_snapshot_for_service(service, resolved, "AuditRoot")

        self.assertEqual(snapshot.resolved, resolved)
        self.assertEqual(snapshot.current_activity, "Encoding Movie.mkv")
        self.assertEqual(snapshot.status_summary, "status summary")
        self.assertEqual(snapshot.log_tail, "log tail")
        self.assertEqual(snapshot.pipeline_events, [{"event_type": "job_started"}])
        self.assertEqual(snapshot.progress, {"Status": "Processing"})
        self.assertEqual(snapshot.audit_progress, {"Status": "Audit"})
        self.assertIn("summary", service.calls)
        self.assertEqual(service.summary_kwargs["audit_root"], "AuditRoot")

    def test_build_snapshot_marks_stale_progress_without_active_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = _resolved(Path(temp_dir))
            service = _DummyStatusSnapshotService(stale=True, activity="No active work reported.")

            snapshot = build_snapshot_for_service(service, resolved, "AuditRoot")

        self.assertEqual(snapshot.current_activity, "Stale progress from previous run; no active pipeline process reported.")
        self.assertIsNone(service.activity_progress)

    def test_build_snapshot_preserves_latest_event_when_progress_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = _resolved(Path(temp_dir))
            service = _DummyStatusSnapshotService(stale=True, activity="Queued Movie.mkv")

            snapshot = build_snapshot_for_service(service, resolved, "AuditRoot")

        self.assertEqual(snapshot.current_activity, "Stale progress from previous run; latest event: Queued Movie.mkv")
        self.assertIsNone(service.activity_progress)

    def test_build_snapshot_keeps_stale_progress_inactive_without_active_jobs_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = _resolved(Path(temp_dir))
            service = _DummyStatusSnapshotService(
                stale=True,
                activity="Scanning sources.",
            )
            service.progress = {
                "ProgressVersion": 2,
                "Status": "Scanning sources",
                "CurrentStage": "scanning",
            }

            snapshot = build_snapshot_for_service(service, resolved, "AuditRoot")

        self.assertEqual(snapshot.current_activity, "Stale progress from previous run; latest event: Scanning sources.")
        self.assertIsNone(service.activity_progress)
        self.assertNotIn("active_jobs", service.calls)

    def test_build_snapshot_logs_reconcile_failure_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = _resolved(Path(temp_dir))
            service = _DummyStatusSnapshotService(fail_reconcile=True)

            with self.assertLogs("test_service_status_snapshot_runner", level="WARNING") as logs:
                snapshot = build_snapshot_for_service(service, resolved, "AuditRoot")

        self.assertEqual(snapshot.status_summary, "status summary")
        self.assertIn("ActiveJobs reconciliation failed: offline", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
