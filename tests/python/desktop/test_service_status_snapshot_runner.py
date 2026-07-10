from __future__ import annotations

import logging
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.status.snapshot_runner import build_snapshot_for_service


def _resolved(root: Path) -> ResolvedPaths:
    local_base = root / "LocalBase"
    state_root = local_base / "State"
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
        local_base=local_base,
        state_root=state_root,
        active_jobs_path=state_root / "ActiveJobs",
        progress_file=state_root / "Progress" / "pipeline_progress.json",
        event_file=state_root / "Progress" / "pipeline_events.jsonl",
        log_file=local_base / "pipeline_debug.log",
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
        self.log_tail = "log tail"
        self.summary_kwargs = {}
        self.activity_progress = None

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
        return self.log_tail

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
        if progress and progress.get("CurrentFile"):
            return f"{progress.get('CurrentStage')} {progress.get('CurrentFile')}"
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

    def test_build_snapshot_uses_active_csv_rerun_child_progress_for_current_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolved = _resolved(root)
            resolved.active_jobs_path.mkdir(parents=True)
            child_root = root / "LocalBase_RerunWorkspace" / "RuntimeState" / "rerun_20260704_220624_609aad0f"
            child_progress_dir = child_root / "State" / "Progress"
            child_progress_dir.mkdir(parents=True)
            child_progress = {
                "ProgressVersion": 2,
                "LastUpdate": datetime.now().isoformat(timespec="seconds"),
                "Status": "Encoding Movie",
                "CurrentFile": "[Movie 1/1] Cars (2006).mkv",
                "CurrentFilePath": str(child_root / "RerunQueue" / "Movies" / "Cars (2006)" / "Cars (2006).mkv"),
                "CurrentMediaType": "movie",
                "CurrentRoute": "encode",
                "CurrentStage": "encode",
                "CurrentStagePercent": 30,
                "TotalProcessed": 0,
                "Encoded": 0,
                "Remuxed": 0,
                "Failed": 0,
                "Movies": 1,
                "TVEpisodes": 0,
            }
            (child_progress_dir / "pipeline_progress.json").write_text(json.dumps(child_progress), encoding="utf-8")
            (child_progress_dir / "pipeline_events.jsonl").write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_event.v1",
                        "event_id": "event-1",
                        "event_type": "tool_started",
                        "timestamp": "2026-07-04T22:24:42",
                        "created_at": "2026-07-04T22:24:42",
                        "run_id": "run-1",
                        "correlation_id": "corr-1",
                        "job_id": "job-1",
                        "product_version": "v6",
                        "pipeline_version": "v6",
                        "stage": "encode",
                        "route": "encode",
                        "status": "started",
                        "source_path": str(child_root / "Incoming" / "Cars (2006).mkv"),
                        "data": {},
                    }
                ),
                encoding="utf-8",
            )
            (resolved.active_jobs_path / "rerun.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "20260704_220624_184605_rerun_csv_22844_4ea5fba2",
                        "job_kind": "rerun_csv",
                        "mode": "process",
                        "status": "active",
                        "pid": 22844,
                        "app_pid": 26588,
                        "command_line": "pwsh -File Invoke-RerunCsv.ps1",
                        "args": ["pwsh", "-File", "Invoke-RerunCsv.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(root / "rerun.stdout.log"),
                        "stderr_log": str(root / "rerun.stderr.log"),
                        "show_console": False,
                        "metadata": {"route": "rerun_csv"},
                        "launched_at": "2026-07-04T22:06:24",
                        "last_update": datetime.now().isoformat(timespec="seconds"),
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )
            service = _DummyStatusSnapshotService(activity="No active work reported.")
            service.progress = {
                "ProgressVersion": 2,
                "LastUpdate": "2026-07-02T00:00:00",
                "Status": "Idle",
                "CurrentStage": "idle",
                "CurrentFile": "None",
            }

            snapshot = build_snapshot_for_service(service, resolved, "AuditRoot")

        self.assertEqual(snapshot.progress["CurrentStage"], "encode")
        self.assertEqual(snapshot.progress["CurrentFile"], "[Movie 1/1] Cars (2006).mkv")
        self.assertEqual(snapshot.progress["ActiveJobKind"], "rerun_csv")
        self.assertEqual(snapshot.progress["RerunParentLaunchId"], "20260704_220624_184605_rerun_csv_22844_4ea5fba2")
        self.assertEqual(snapshot.pipeline_events[0]["event_type"], "tool_started")
        self.assertIn("Cars (2006).mkv", snapshot.current_activity)
        self.assertEqual(service.activity_progress["CurrentStage"], "encode")
        self.assertEqual(service.summary_kwargs["progress"]["CurrentFile"], "[Movie 1/1] Cars (2006).mkv")

    def test_build_snapshot_uses_csv_rerun_process_tail_when_child_log_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resolved = _resolved(root)
            resolved.active_jobs_path.mkdir(parents=True)
            child_root = root / "LocalBase_RerunWorkspace" / "RuntimeState" / "rerun_20260704_220624_609aad0f"
            child_progress_dir = child_root / "State" / "Progress"
            child_progress_dir.mkdir(parents=True)
            (child_progress_dir / "pipeline_progress.json").write_text(
                json.dumps(
                    {
                        "ProgressVersion": 2,
                        "LastUpdate": datetime.now().isoformat(timespec="seconds"),
                        "Status": "Encoding Movie",
                        "CurrentFile": "[Movie 1/1] Cars (2006).mkv",
                        "CurrentFilePath": str(child_root / "RerunQueue" / "Movies" / "Cars (2006)" / "Cars (2006).mkv"),
                        "CurrentMediaType": "movie",
                        "CurrentRoute": "encode",
                        "CurrentStage": "encode",
                        "CurrentStagePercent": 30,
                        "TotalProcessed": 0,
                        "Encoded": 0,
                        "Remuxed": 0,
                        "Failed": 0,
                        "Movies": 1,
                        "TVEpisodes": 0,
                    }
                ),
                encoding="utf-8",
            )
            rerun_stdout = root / "rerun.stdout.log"
            rerun_line = "2026-07-04 22:24:42 [INFO] STAGE COPY attempt 1/3: Cars (2006).mkv"
            rerun_stdout.write_text(
                "2026-07-04 22:06:24 [INFO] CSV rerun selected path: rerun.csv\n" + rerun_line + "\n",
                encoding="utf-8",
            )
            (resolved.active_jobs_path / "rerun.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "20260704_220624_184605_rerun_csv_22844_4ea5fba2",
                        "job_kind": "rerun_csv",
                        "mode": "process",
                        "status": "active",
                        "pid": 22844,
                        "app_pid": 26588,
                        "command_line": "pwsh -File Invoke-RerunCsv.ps1",
                        "args": ["pwsh", "-File", "Invoke-RerunCsv.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(rerun_stdout),
                        "stderr_log": str(root / "rerun.stderr.log"),
                        "show_console": False,
                        "metadata": {"route": "rerun_csv"},
                        "launched_at": "2026-07-04T22:06:24",
                        "last_update": datetime.now().isoformat(timespec="seconds"),
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )
            service = _DummyStatusSnapshotService(activity="No active work reported.")
            service.log_tail = "2026-07-04 22:10:00 [INFO] SKIP (already in outsource): unrelated library item"
            service.progress = {
                "ProgressVersion": 2,
                "LastUpdate": "2026-07-02T00:00:00",
                "Status": "Idle",
                "CurrentStage": "idle",
                "CurrentFile": "None",
            }

            snapshot = build_snapshot_for_service(service, resolved, "AuditRoot")

        self.assertIn(rerun_line, snapshot.log_tail)
        self.assertIn("CSV rerun selected path", snapshot.log_tail)
        self.assertNotIn("SKIP (already in outsource)", snapshot.log_tail)
        self.assertEqual(snapshot.progress["ActiveJobKind"], "rerun_csv")

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
