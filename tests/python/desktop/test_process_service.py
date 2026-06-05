from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.paths.service import PathResolutionServiceMixin
from mediapipeline.core.processes.lifecycle import ProcessLifecycleServiceMixin
from mediapipeline.core.status.service import StatusServiceMixin


class DummyProcessService(PathResolutionServiceMixin, ProcessLifecycleServiceMixin, StatusServiceMixin):
    def __init__(self, root: Path) -> None:
        self.app_root = root
        self.workspace_root = root
        self.logger = logging.getLogger("test_process_service")


class ProcessServiceControlFlagTests(unittest.TestCase):
    def _resolved(self, root: Path) -> ResolvedPaths:
        state = root / "State" / "Pipeline"
        return ResolvedPaths(
            app_root=root,
            workspace_root=root,
            pipeline_path=root / "pipeline.ps1",
            config_path=root / "config.psd1",
            audit_script_path=root / "audit.ps1",
            rerun_script_path=root / "rerun.ps1",
            powershell_host=None,
            pause_flag=state / "pipeline_pause.flag",
            stop_flag=state / "pipeline_stop.flag",
            rescan_flag=state / "pipeline_rescan.flag",
        )

    def _runtime_resolved(self, root: Path) -> ResolvedPaths:
        local_base = root / "LocalBase"
        state_root = local_base / "State"
        pipeline_state = state_root / "Pipeline"
        return ResolvedPaths(
            app_root=root,
            workspace_root=root,
            pipeline_path=root / "pipeline.ps1",
            config_path=root / "config.psd1",
            audit_script_path=root / "audit.ps1",
            rerun_script_path=root / "rerun.ps1",
            powershell_host=None,
            local_base=local_base,
            state_root=state_root,
            progress_file=state_root / "Progress" / "pipeline_progress.json",
            pause_flag=pipeline_state / "pipeline_pause.flag",
            stop_flag=pipeline_state / "pipeline_stop.flag",
            rescan_flag=pipeline_state / "pipeline_rescan.flag",
            audit_reports_path=local_base / "AuditReports",
        )

    def _progress_payload(self, last_update: str) -> dict[str, object]:
        return {
            "ProgressVersion": 2,
            "LastUpdate": last_update,
            "CurrentQueueIndex": 1,
            "CurrentQueueTotal": 2,
            "CurrentStagePercent": 10,
            "PauseRequested": False,
            "StopRequested": False,
            "ControlRequests": {},
            "Status": "Processing",
            "CurrentStage": "encoding",
            "TotalProcessed": 0,
            "Encoded": 0,
            "Remuxed": 0,
            "Failed": 0,
            "Movies": 0,
            "TVEpisodes": 0,
        }

    def _audit_progress_payload(self, last_update: str) -> dict[str, object]:
        return {
            "last_update": last_update,
            "status": "scanning",
            "completed": False,
            "failed": False,
            "processed_files": 1,
            "total_files": 2,
            "percent_complete": 50,
        }

    def test_write_flag_persists_current_control_flag_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._resolved(root)

            message = service.write_flag(resolved.stop_flag, "Stop")

            payload = json.loads(resolved.stop_flag.read_text(encoding="utf-8"))
        self.assertEqual(message, "Stop requested.")
        self.assertEqual(payload["schema_version"], "pipeline_control_flag.v1")
        self.assertEqual(payload["action"], "stop")
        self.assertEqual(payload["label"], "Stop")
        self.assertTrue(payload["request_id"])
        self.assertTrue(payload["created_at"])
        self.assertIsInstance(payload["app_pid"], int)

    def test_toggle_pause_flag_writes_and_removes_contract_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._resolved(root)

            first = service.toggle_pause_flag(resolved)
            payload = json.loads(resolved.pause_flag.read_text(encoding="utf-8"))
            second = service.toggle_pause_flag(resolved)

            self.assertEqual(first, "Pause requested.")
            self.assertEqual(payload["action"], "pause")
            self.assertEqual(second, "Pause flag cleared.")
            self.assertFalse(resolved.pause_flag.exists())

    def test_prepare_launch_uses_contract_timestamp_for_stale_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._resolved(root)
            resolved.pause_flag.parent.mkdir(parents=True, exist_ok=True)
            resolved.pause_flag.write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_control_flag.v1",
                        "action": "pause",
                        "label": "Pause",
                        "request_id": "pause-old",
                        "created_at": "2000-01-01T00:00:00-04:00",
                    }
                ),
                encoding="utf-8",
            )

            messages = service.prepare_pipeline_control_flags_for_launch(resolved, stale_after_seconds=3600)

            self.assertFalse(resolved.pause_flag.exists())
            self.assertTrue(any("stale pause" in message for message in messages))

    def test_read_control_flag_payload_preserves_invalid_current_file_for_legacy_existence_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._resolved(root)
            resolved.rescan_flag.parent.mkdir(parents=True, exist_ok=True)
            resolved.rescan_flag.write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_control_flag.v1",
                        "action": "invalid",
                        "label": "Rescan",
                        "request_id": "rescan-1",
                        "created_at": "2026-05-06T12:00:00-04:00",
                    }
                ),
                encoding="utf-8",
            )

            payload = service._read_control_flag_payload(resolved.rescan_flag)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["action"], "invalid")

    def test_read_control_flag_payload_logs_unreadable_flag(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._resolved(root)
            resolved.rescan_flag.parent.mkdir(parents=True, exist_ok=True)
            resolved.rescan_flag.write_text("{not json", encoding="utf-8")

            with self.assertLogs("test_process_service", level="WARNING") as logs:
                payload = service._read_control_flag_payload(resolved.rescan_flag)

        self.assertIsNone(payload)
        self.assertIn("Control flag unreadable", "\n".join(logs.output))

    def test_prepare_pipeline_runtime_for_launch_clears_only_stale_progress_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._runtime_resolved(root)
            resolved.progress_file.parent.mkdir(parents=True, exist_ok=True)
            resolved.pause_flag.parent.mkdir(parents=True, exist_ok=True)
            resolved.progress_file.write_text(json.dumps(self._progress_payload("2000-01-01T00:00:00-04:00")), encoding="utf-8")
            legacy_progress = resolved.local_base / "pipeline_progress.json"
            legacy_progress.parent.mkdir(parents=True, exist_ok=True)
            legacy_progress.write_text(json.dumps(self._progress_payload("2000-01-01T00:00:00-04:00")), encoding="utf-8")
            resolved.pause_flag.write_text("pause", encoding="utf-8")

            messages = service.prepare_pipeline_runtime_for_launch(resolved, stale_after_seconds=1)

            self.assertFalse(resolved.progress_file.exists())
            self.assertFalse(legacy_progress.exists())
            self.assertTrue(resolved.pause_flag.exists())
            self.assertEqual(len(messages), 1)
            self.assertIn("Cleared stale pipeline progress before launch", messages[0])

    def test_prepare_pipeline_runtime_for_launch_does_not_clear_when_related_process_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._runtime_resolved(root)
            resolved.progress_file.parent.mkdir(parents=True, exist_ok=True)
            resolved.progress_file.write_text(json.dumps(self._progress_payload("2000-01-01T00:00:00-04:00")), encoding="utf-8")
            service.find_related_pipeline_processes = lambda _resolved: [type("Proc", (), {"pid": 4321})()]

            messages = service.prepare_pipeline_runtime_for_launch(resolved, stale_after_seconds=1)

            self.assertTrue(resolved.progress_file.exists())
            self.assertEqual(len(messages), 1)
            self.assertIn("PID(s) 4321", messages[0])

    def test_prepare_audit_runtime_for_launch_clears_only_stale_audit_progress(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._runtime_resolved(root)
            assert resolved.audit_reports_path is not None
            resolved.audit_reports_path.mkdir(parents=True, exist_ok=True)
            audit_progress = resolved.audit_reports_path / "audit_progress.json"
            audit_progress.write_text(json.dumps(self._audit_progress_payload("2000-01-01T00:00:00-04:00")), encoding="utf-8")
            resolved.progress_file.parent.mkdir(parents=True, exist_ok=True)
            resolved.progress_file.write_text(json.dumps(self._progress_payload("2000-01-01T00:00:00-04:00")), encoding="utf-8")

            messages = service.prepare_audit_runtime_for_launch(resolved, stale_after_seconds=1)

            self.assertFalse(audit_progress.exists())
            self.assertTrue(resolved.progress_file.exists())
            self.assertEqual(len(messages), 1)
            self.assertIn("Cleared stale audit progress before launch", messages[0])

    def test_prepare_audit_runtime_for_launch_does_not_clear_when_related_process_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._runtime_resolved(root)
            assert resolved.audit_reports_path is not None
            resolved.audit_reports_path.mkdir(parents=True, exist_ok=True)
            audit_progress = resolved.audit_reports_path / "audit_progress.json"
            audit_progress.write_text(json.dumps(self._audit_progress_payload("2000-01-01T00:00:00-04:00")), encoding="utf-8")
            service.find_related_pipeline_processes = lambda _resolved: [type("Proc", (), {"pid": 5432})()]

            messages = service.prepare_audit_runtime_for_launch(resolved, stale_after_seconds=1)

            self.assertTrue(audit_progress.exists())
            self.assertEqual(len(messages), 1)
            self.assertIn("PID(s) 5432", messages[0])

    def test_reconcile_active_job_records_marks_missing_running_pid_orphaned(self) -> None:
        class FakeNoSuchProcess(Exception):
            pass

        class FakePsutil:
            NoSuchProcess = FakeNoSuchProcess
            STATUS_ZOMBIE = "zombie"

            @staticmethod
            def Process(_pid: int):
                raise FakeNoSuchProcess()

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._resolved(root)
            active_jobs = root / "ActiveJobs"
            active_jobs.mkdir()
            resolved.active_jobs_path = active_jobs
            record_path = active_jobs / "launch.json"
            record_path.write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch",
                        "job_kind": "pipeline",
                        "mode": "continuous",
                        "status": "active",
                        "pid": 99999,
                        "app_pid": 123,
                        "command_line": "pwsh -File pipeline.ps1",
                        "args": ["pwsh", "-File", "pipeline.ps1"],
                        "cwd": str(root),
                        "stdout_log": "",
                        "stderr_log": "",
                        "show_console": False,
                        "metadata": {},
                        "launched_at": "2026-05-06T12:00:00-04:00",
                        "last_update": "2026-05-06T12:00:01-04:00",
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )

            with patch("mediapipeline.core.processes.lifecycle.psutil", FakePsutil):
                messages = service.reconcile_active_job_records(resolved)

            updated = json.loads(record_path.read_text(encoding="utf-8"))

        self.assertEqual(len(messages), 1)
        self.assertEqual(updated["status"], "orphaned")
        self.assertEqual(updated["return_code"], None)
        self.assertTrue(updated["completed_at"])
        self.assertEqual(updated["reconcile_reason"], "pid 99999 is no longer running")

    def test_reconcile_active_job_records_leaves_terminal_records_unchanged(self) -> None:
        class FakePsutil:
            NoSuchProcess = RuntimeError
            STATUS_ZOMBIE = "zombie"

            @staticmethod
            def Process(_pid: int):
                raise AssertionError("terminal records should not inspect process state")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyProcessService(root)
            resolved = self._resolved(root)
            active_jobs = root / "ActiveJobs"
            active_jobs.mkdir()
            resolved.active_jobs_path = active_jobs
            record_path = active_jobs / "done.json"
            record_path.write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "done",
                        "job_kind": "pipeline",
                        "status": "completed",
                        "pid": 99999,
                        "args": [],
                        "metadata": {},
                    }
                ),
                encoding="utf-8",
            )

            with patch("mediapipeline.core.processes.lifecycle.psutil", FakePsutil):
                messages = service.reconcile_active_job_records(resolved)

            updated = json.loads(record_path.read_text(encoding="utf-8"))

        self.assertEqual(messages, [])
        self.assertEqual(updated["status"], "completed")


if __name__ == "__main__":
    unittest.main()
