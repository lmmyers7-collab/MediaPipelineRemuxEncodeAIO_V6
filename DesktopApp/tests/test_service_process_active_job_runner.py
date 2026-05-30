from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from app.processes.active_job_runner import (
    active_job_pid_is_alive_for_service,
    active_job_record_path_for_proc_for_service,
    active_jobs_dir_for_service,
    reconcile_active_job_records_for_service,
    update_active_job_record_for_service,
    write_active_job_launch_record_for_service,
    write_active_job_payload_for_service,
)


class FakeProc:
    def __init__(self, pid: int = 4321, returncode: int | None = None) -> None:
        self.pid = pid
        self.returncode = returncode

    def poll(self) -> int | None:
        return self.returncode


class DummyActiveJobRunnerService:
    def __init__(self, stdout_log: Path | None = None, stderr_log: Path | None = None) -> None:
        self._last_spawn_stdout_log = stdout_log
        self._last_spawn_stderr_log = stderr_log
        self.logger = logging.getLogger("test_service_process_active_job_runner")
        self.logger.addHandler(logging.NullHandler())


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "MediaPipeline_config_chatgpt.psd1",
        audit_script_path=root / "Pipeline" / "Audit-MediaLibrary.ps1",
        rerun_script_path=root / "Pipeline" / "Invoke-RerunCsv.ps1",
        powershell_host="pwsh",
        active_jobs_path=root / "ActiveJobs",
    )


class ProcessActiveJobRunnerTests(unittest.TestCase):
    def test_write_launch_record_uses_service_logs_and_sets_proc_record_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stdout = root / "stdout.log"
            stderr = root / "stderr.log"
            service = DummyActiveJobRunnerService(stdout, stderr)
            proc = FakeProc(pid=1234)
            resolved = _resolved(root)

            record_path = write_active_job_launch_record_for_service(
                service,
                proc,  # type: ignore[arg-type]
                resolved=resolved,
                job_kind="pipeline",
                mode="continuous",
                command_line="pwsh pipeline.ps1",
                args=["pwsh", "pipeline.ps1"],
                launch_cwd=root,
                show_console=False,
                metadata={"reason": "test"},
            )

            self.assertIsNotNone(record_path)
            assert record_path is not None
            payload = json.loads(record_path.read_text(encoding="utf-8"))

        self.assertEqual(active_jobs_dir_for_service(service, resolved), resolved.active_jobs_path)
        self.assertEqual(active_job_record_path_for_proc_for_service(service, proc), record_path)
        self.assertEqual(payload["stdout_log"], str(stdout))
        self.assertEqual(payload["stderr_log"], str(stderr))
        self.assertEqual(payload["metadata"], {"reason": "test"})
        self.assertIsInstance(payload["app_pid"], int)

    def test_update_active_job_record_for_service_writes_terminal_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyActiveJobRunnerService()
            proc = FakeProc(pid=2222, returncode=0)
            resolved = _resolved(root)
            record_path = write_active_job_launch_record_for_service(
                service,
                proc,  # type: ignore[arg-type]
                resolved=resolved,
                job_kind="audit",
                mode="scan",
                command_line="pwsh audit.ps1",
                args=["pwsh", "audit.ps1"],
                launch_cwd=root,
                show_console=False,
                metadata={},
            )

            update_active_job_record_for_service(service, proc, status=None, return_code=0)  # type: ignore[arg-type]

            payload = json.loads(record_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["return_code"], 0)
        self.assertTrue(payload["completed_at"])

    def test_reconcile_active_job_records_for_service_marks_missing_pid_orphaned(self) -> None:
        class FakeNoSuchProcess(Exception):
            pass

        class FakePsutil:
            NoSuchProcess = FakeNoSuchProcess
            STATUS_ZOMBIE = "zombie"

            @staticmethod
            def Process(_pid: int):
                raise FakeNoSuchProcess()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyActiveJobRunnerService()
            resolved = _resolved(root)
            active_jobs = resolved.active_jobs_path
            assert active_jobs is not None
            active_jobs.mkdir()
            record_path = active_jobs / "launch.json"
            write_active_job_payload_for_service(
                service,
                record_path,
                {
                    "schema_version": "desktop_active_job.v1",
                    "launch_id": "launch",
                    "job_kind": "pipeline",
                    "mode": "continuous",
                    "status": "active",
                    "pid": 99999,
                    "app_pid": 1,
                    "command_line": "pwsh",
                    "args": ["pwsh"],
                    "cwd": str(root),
                    "stdout_log": "",
                    "stderr_log": "",
                    "show_console": False,
                    "metadata": {},
                    "launched_at": "2026-05-06T12:00:00-04:00",
                    "last_update": "2026-05-06T12:00:01-04:00",
                    "return_code": None,
                },
            )

            messages = reconcile_active_job_records_for_service(
                service,
                resolved,
                max_items=24,
                psutil_module=FakePsutil,
            )

            updated = json.loads(record_path.read_text(encoding="utf-8"))

        self.assertEqual(len(messages), 1)
        self.assertEqual(updated["status"], "orphaned")
        self.assertEqual(updated["reconcile_reason"], "pid 99999 is no longer running")

    def test_active_job_pid_liveness_delegates_to_psutil_boundary(self) -> None:
        class FakeNoSuchProcess(Exception):
            pass

        class FakeProcess:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def is_running(self) -> bool:
                return self.pid == 1

            def status(self) -> str:
                return "running"

        class FakePsutil:
            NoSuchProcess = FakeNoSuchProcess
            STATUS_ZOMBIE = "zombie"

            @staticmethod
            def Process(pid: int):
                if pid == 2:
                    raise FakeNoSuchProcess()
                return FakeProcess(pid)

        service = DummyActiveJobRunnerService()

        self.assertTrue(active_job_pid_is_alive_for_service(service, 1, FakePsutil))
        self.assertFalse(active_job_pid_is_alive_for_service(service, 2, FakePsutil))


if __name__ == "__main__":
    unittest.main()
