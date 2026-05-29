from __future__ import annotations

from datetime import datetime, timedelta
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from mediapipeline_desktop_app.models import ResolvedPaths, Snapshot
from DesktopApp.tests.test_application_facade import DummyFacadeService, DummyProc, DummyWorkflowFacadeService, _resolved


class ApplicationFacadeCloseReadinessTests(unittest.TestCase):
    def test_close_readiness_blocks_active_and_unknown_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )
            active_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Encoding.",
                status_summary="Processing",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Processing", "CurrentStage": "encode"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )
            audit_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Auditing.",
                status_summary="Audit running",
                log_tail="",
                progress={},
                audit_progress={"status": "running", "completed": False, "failed": False},
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            idle = facade.get_close_readiness(resolved, idle_snapshot)
            active = facade.get_close_readiness(resolved, active_snapshot)
            audit = facade.get_close_readiness(resolved, audit_snapshot)
            unknown = facade.get_close_readiness(resolved, None)

        self.assertTrue(idle.safe_to_close)
        self.assertFalse(idle.active_work)
        self.assertEqual(idle.state, "completed")
        self.assertFalse(active.safe_to_close)
        self.assertTrue(active.active_work)
        self.assertEqual(active.state, "processing")
        self.assertIn("processing", active.reason)
        self.assertFalse(audit.safe_to_close)
        self.assertEqual(audit.state, "audit")
        self.assertFalse(unknown.safe_to_close)
        self.assertEqual(unknown.state, "unknown")
        self.assertTrue(unknown.warnings)

    def test_close_readiness_blocks_fresh_progress_even_when_snapshot_is_idle(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            service.read_progress = lambda _resolved: {"ProgressVersion": 2, "Status": "Running", "CurrentStage": "encode"}
            service.is_progress_stale = lambda _progress: False
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            readiness = facade.get_close_readiness(resolved, idle_snapshot)

        self.assertFalse(readiness.safe_to_close)
        self.assertTrue(readiness.active_work)
        self.assertIn("fresh pipeline progress", readiness.reason)

    def test_close_readiness_blocks_when_pipeline_progress_verification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)

            def fail_progress(_resolved: ResolvedPaths) -> dict[str, object]:
                raise RuntimeError("progress locked")

            service.read_progress = fail_progress
            service.is_progress_stale = lambda _progress: False
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            with self.assertLogs("test_application_facade", level="WARNING") as logs:
                readiness = facade.get_close_readiness(resolved, idle_snapshot)

        self.assertFalse(readiness.safe_to_close)
        self.assertTrue(readiness.active_work)
        self.assertIn("pipeline progress could not be verified", readiness.reason)
        self.assertIn("progress locked", readiness.reason)
        self.assertIn("Pipeline progress close-readiness verification failed", "\n".join(logs.output))

    def test_close_readiness_blocks_when_audit_progress_verification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            service.read_progress = lambda _resolved: {}
            service.is_progress_stale = lambda _progress: True

            def fail_audit_progress(_resolved: ResolvedPaths) -> dict[str, object]:
                raise RuntimeError("audit progress locked")

            service.read_audit_progress = fail_audit_progress
            service.is_audit_progress_stale = lambda _progress: False
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            with self.assertLogs("test_application_facade", level="WARNING") as logs:
                readiness = facade.get_close_readiness(resolved, idle_snapshot)

        self.assertFalse(readiness.safe_to_close)
        self.assertTrue(readiness.active_work)
        self.assertIn("audit progress could not be verified", readiness.reason)
        self.assertIn("audit progress locked", readiness.reason)
        self.assertIn("Audit progress close-readiness verification failed", "\n".join(logs.output))

    def test_close_readiness_blocks_active_job_record_even_when_snapshot_is_idle(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            service.active_job_close_block_messages = lambda _resolved: [
                "ActiveJobs record launch.json reports pipeline continuous as active; PID 9999 could not be verified."
            ]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            readiness = facade.get_close_readiness(resolved, idle_snapshot)

        self.assertFalse(readiness.safe_to_close)
        self.assertTrue(readiness.active_work)
        self.assertIn("ActiveJobs still reports active work", readiness.reason)
        self.assertIn("launch.json", readiness.reason)

    def test_close_readiness_blocks_while_schedule_stop_watcher_is_armed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            service.read_progress = lambda _resolved: {}
            service.is_progress_stale = lambda _progress: True
            service.read_audit_progress = lambda _resolved: {}
            service.is_audit_progress_stale = lambda _progress: True
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            deadline = (datetime.now() + timedelta(seconds=30)).replace(microsecond=0)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            facade._schedule_stop_watcher.arm(  # type: ignore[attr-defined]
                service=service,
                resolved=resolved,
                proc=DummyProc(5555),
                deadline=deadline,
            )
            try:
                readiness = facade.get_close_readiness(resolved, idle_snapshot)
            finally:
                facade._schedule_stop_watcher.cancel("test cleanup")  # type: ignore[attr-defined]

        self.assertFalse(readiness.safe_to_close)
        self.assertTrue(readiness.active_work)
        self.assertIn("schedule-stop watcher is armed", readiness.reason)
        self.assertIn("PID 5555", readiness.reason)
        self.assertIn(deadline.isoformat(), readiness.reason)
        self.assertEqual(readiness.continuous_watcher["status"], "armed")
        self.assertEqual(readiness.continuous_watcher["pid"], 5555)
        self.assertGreater(readiness.continuous_watcher["generation"], 0)

    def test_close_readiness_blocks_and_logs_when_active_jobs_verification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)

            def fail_active_jobs(_resolved: ResolvedPaths) -> list[str]:
                raise RuntimeError("active jobs locked")

            service.active_job_close_block_messages = fail_active_jobs
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            with self.assertLogs("test_application_facade", level="WARNING") as logs:
                readiness = facade.get_close_readiness(resolved, idle_snapshot)

        self.assertFalse(readiness.safe_to_close)
        self.assertTrue(readiness.active_work)
        self.assertIn("ActiveJobs still reports active work", readiness.reason)
        self.assertIn("ActiveJobs state could not be verified", readiness.reason)
        self.assertIn("ActiveJobs close-readiness verification failed", "\n".join(logs.output))

    def test_close_readiness_blocks_when_related_process_inspection_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)

            def fail_related_processes(_resolved: ResolvedPaths) -> list[object]:
                raise RuntimeError("process table unavailable")

            service.find_related_pipeline_processes = fail_related_processes
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            with self.assertLogs("test_application_facade", level="WARNING") as logs:
                readiness = facade.get_close_readiness(resolved, idle_snapshot)

        self.assertFalse(readiness.safe_to_close)
        self.assertTrue(readiness.active_work)
        self.assertIn("related MediaPipeline processes could not be verified", readiness.reason)
        self.assertIn("process table unavailable", readiness.reason)
        self.assertIn("Related process close-readiness verification failed", "\n".join(logs.output))

    def test_close_readiness_blocks_when_related_process_detection_dependency_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            with patch("app.processes.lifecycle.psutil", None):
                with self.assertLogs("test_application_facade", level="WARNING") as logs:
                    readiness = facade.get_close_readiness(resolved, idle_snapshot)

        self.assertFalse(readiness.safe_to_close)
        self.assertTrue(readiness.active_work)
        self.assertIn("related MediaPipeline processes could not be verified", readiness.reason)
        self.assertIn("psutil unavailable", readiness.reason)
        self.assertIn("Related process close-readiness verification failed", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
