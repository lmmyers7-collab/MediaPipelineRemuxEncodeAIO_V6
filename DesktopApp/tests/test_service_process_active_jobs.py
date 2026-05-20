from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from mediapipeline_desktop_app.service_process_active_jobs import (
    active_job_close_block_messages,
    active_job_pid_is_alive,
    active_job_pid_matches_record,
    reconcile_active_job_records,
    update_active_job_record,
    write_active_job_launch_record,
    write_active_job_payload,
)
from mediapipeline_desktop_app.service_processes import ProcessLifecycleServiceMixin


class FakeProc:
    def __init__(self, pid: int = 4321, returncode: int | None = None) -> None:
        self.pid = pid
        self.returncode = returncode

    def poll(self) -> int | None:
        return self.returncode


class DummyActiveJobService(ProcessLifecycleServiceMixin):
    def __init__(self, stdout_log: Path | None = None, stderr_log: Path | None = None) -> None:
        self._last_spawn_stdout_log = stdout_log
        self._last_spawn_stderr_log = stderr_log
        self.logger = logging.getLogger("test_service_process_active_jobs")
        self.logger.addHandler(logging.NullHandler())


class ProcessActiveJobHelperTests(unittest.TestCase):
    def _resolved(self, root: Path) -> ResolvedPaths:
        return ResolvedPaths(
            app_root=root / "DesktopApp",
            workspace_root=root,
            pipeline_path=root / "Pipeline" / "MediaPipeline_chatgpt.ps1",
            config_path=root / "Pipeline" / "MediaPipeline_config_chatgpt.psd1",
            audit_script_path=root / "Pipeline" / "Audit-MediaLibrary_chatgpt.ps1",
            rerun_script_path=root / "Pipeline" / "Invoke-RerunCsv.ps1",
            powershell_host="pwsh",
            active_jobs_path=root / "ActiveJobs",
        )

    def test_write_launch_record_sets_proc_attribute_and_valid_contract_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stdout = root / "stdout.log"
            stderr = root / "stderr.log"
            resolved = self._resolved(root)
            proc = FakeProc(pid=1234)

            record_path = write_active_job_launch_record(
                proc,
                resolved=resolved,
                job_kind="pipeline",
                mode="once",
                command_line="pwsh -File pipeline.ps1",
                args=["pwsh", "-File", "pipeline.ps1"],
                launch_cwd=root,
                show_console=False,
                metadata={"source": "test"},
                stdout_log=stdout,
                stderr_log=stderr,
                app_pid=999,
            )

            self.assertIsNotNone(record_path)
            self.assertEqual(Path(getattr(proc, "_mediapipeline_active_job_record")), record_path)
            payload = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "desktop_active_job.v1")
            self.assertEqual(payload["job_kind"], "pipeline")
            self.assertEqual(payload["mode"], "once")
            self.assertEqual(payload["status"], "launching")
            self.assertEqual(payload["pid"], 1234)
            self.assertEqual(payload["app_pid"], 999)
            self.assertEqual(payload["stdout_log"], str(stdout))
            self.assertEqual(payload["stderr_log"], str(stderr))

    def test_update_active_job_record_preserves_contract_and_sets_terminal_time(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = FakeProc(pid=2222, returncode=0)
            resolved = self._resolved(root)
            record_path = write_active_job_launch_record(
                proc,
                resolved=resolved,
                job_kind="audit",
                mode="scan",
                command_line="pwsh audit.ps1",
                args=["pwsh", "audit.ps1"],
                launch_cwd=root,
                show_console=False,
                metadata={},
                stdout_log=None,
                stderr_log=None,
                app_pid=999,
            )

            update_active_job_record(proc, return_code=0, app_pid=999)

            payload = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["return_code"], 0)
            self.assertTrue(payload["completed_at"])

    def test_update_active_job_record_logs_corrupt_record_repair(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record_path = root / "ActiveJobs" / "launch.json"
            record_path.parent.mkdir()
            record_path.write_text("{not json", encoding="utf-8")
            proc = FakeProc(pid=2222, returncode=1)
            setattr(proc, "_mediapipeline_active_job_record", str(record_path))
            logger = logging.getLogger("test_service_process_active_jobs.update")

            with self.assertLogs(logger.name, level="WARNING") as logs:
                update_active_job_record(proc, return_code=1, app_pid=999, logger=logger)

            payload = json.loads(record_path.read_text(encoding="utf-8"))

        self.assertIn("could not be read during update; repairing with default fields", "\n".join(logs.output))
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["pid"], 2222)
        self.assertEqual(payload["return_code"], 1)

    def test_reconcile_marks_missing_pid_orphaned(self) -> None:
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
            active_jobs = root / "ActiveJobs"
            active_jobs.mkdir()
            record_path = active_jobs / "launch.json"
            write_active_job_payload(
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

            resolved = self._resolved(root)
            resolved.active_jobs_path = active_jobs
            messages = reconcile_active_job_records(resolved, psutil_module=FakePsutil)

            updated = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(len(messages), 1)
            self.assertEqual(updated["status"], "orphaned")
            self.assertEqual(updated["reconcile_reason"], "pid 99999 is no longer running")

    def test_reconcile_reports_malformed_active_job_record(self) -> None:
        class FakePsutil:
            NoSuchProcess = RuntimeError
            STATUS_ZOMBIE = "zombie"

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            active_jobs = root / "ActiveJobs"
            active_jobs.mkdir()
            (active_jobs / "broken.json").write_text("{not json", encoding="utf-8")

            resolved = self._resolved(root)
            resolved.active_jobs_path = active_jobs
            logger = logging.getLogger("test_service_process_active_jobs.reconcile")
            with self.assertLogs(logger.name, level="WARNING") as logs:
                messages = reconcile_active_job_records(resolved, psutil_module=FakePsutil, logger=logger)

        combined = "\n".join(messages + logs.output)
        self.assertIn("ActiveJobs record broken.json could not be reconciled", combined)
        self.assertIn("Expecting property name", combined)

    def test_active_job_close_blocks_live_missing_and_unverifiable_records(self) -> None:
        class FakeNoSuchProcess(Exception):
            pass

        class FakeProcess:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def is_running(self) -> bool:
                return True

            def status(self) -> str:
                return "running"

            def cmdline(self) -> list[str]:
                return ["pwsh", "-File", "pipeline.ps1"]

            def cwd(self) -> str:
                return str(root)

        class FakePsutil:
            NoSuchProcess = FakeNoSuchProcess
            STATUS_ZOMBIE = "zombie"

            @staticmethod
            def Process(pid: int):
                if pid == 200:
                    raise FakeNoSuchProcess()
                if pid == 300:
                    raise RuntimeError("access denied")
                return FakeProcess(pid)

        def payload(name: str, *, status: str, pid: int | None) -> dict[str, object]:
            return {
                "schema_version": "desktop_active_job.v1",
                "launch_id": name,
                "job_kind": "pipeline",
                "mode": "continuous",
                "status": status,
                "pid": pid,
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
            }

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            active_jobs = root / "ActiveJobs"
            active_jobs.mkdir()
            write_active_job_payload(active_jobs / "live.json", payload("live", status="active", pid=100))
            write_active_job_payload(active_jobs / "dead.json", payload("dead", status="active", pid=200))
            write_active_job_payload(active_jobs / "unknown.json", payload("unknown", status="active", pid=300))
            write_active_job_payload(active_jobs / "missing.json", payload("missing", status="launching", pid=None))
            write_active_job_payload(active_jobs / "done.json", payload("done", status="completed", pid=400))
            (active_jobs / "bad.json").write_text("{not json", encoding="utf-8")

            resolved = self._resolved(root)
            resolved.active_jobs_path = active_jobs
            messages = active_job_close_block_messages(resolved, psutil_module=FakePsutil)
            combined = "\n".join(messages)

        self.assertEqual(len(messages), 4)
        self.assertIn("live.json", combined)
        self.assertIn("PID 100 is still running", combined)
        self.assertIn("unknown.json", combined)
        self.assertIn("PID 300 identity could not be verified", combined)
        self.assertIn("missing.json", combined)
        self.assertIn("with no PID", combined)
        self.assertIn("bad.json", combined)
        self.assertIn("could not be verified", combined)
        self.assertNotIn("dead.json", combined)
        self.assertNotIn("done.json", combined)

    def test_active_job_close_blocks_when_psutil_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            active_jobs = root / "ActiveJobs"
            active_jobs.mkdir()
            write_active_job_payload(
                active_jobs / "active.json",
                {
                    "schema_version": "desktop_active_job.v1",
                    "launch_id": "active",
                    "job_kind": "pipeline",
                    "mode": "continuous",
                    "status": "active",
                    "pid": 54321,
                    "app_pid": 1,
                    "command_line": "pwsh",
                    "args": ["pwsh", "-File", "MediaPipeline_chatgpt.ps1"],
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

            resolved = self._resolved(root)
            resolved.active_jobs_path = active_jobs
            messages = active_job_close_block_messages(resolved, psutil_module=None)

        self.assertEqual(len(messages), 1)
        self.assertIn("active.json", messages[0])
        self.assertIn("PID 54321 identity could not be verified", messages[0])

    def test_active_job_close_does_not_block_reused_pid_with_mismatched_identity(self) -> None:
        class FakeNoSuchProcess(Exception):
            pass

        class FakeProcess:
            def is_running(self) -> bool:
                return True

            def status(self) -> str:
                return "running"

            def cmdline(self) -> list[str]:
                return ["notepad.exe", "unrelated.txt"]

            def cwd(self) -> str:
                return str(Path("C:/Other"))

        class FakePsutil:
            NoSuchProcess = FakeNoSuchProcess
            STATUS_ZOMBIE = "zombie"

            @staticmethod
            def Process(_pid: int):
                return FakeProcess()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            active_jobs = root / "ActiveJobs"
            active_jobs.mkdir()
            record_path = active_jobs / "reused.json"
            write_active_job_payload(
                record_path,
                {
                    "schema_version": "desktop_active_job.v1",
                    "launch_id": "reused",
                    "job_kind": "pipeline",
                    "mode": "continuous",
                    "status": "active",
                    "pid": 100,
                    "app_pid": 1,
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
                },
            )

            resolved = self._resolved(root)
            resolved.active_jobs_path = active_jobs
            messages = active_job_close_block_messages(resolved, psutil_module=FakePsutil)
            reconcile_messages = reconcile_active_job_records(resolved, psutil_module=FakePsutil)
            updated = json.loads(record_path.read_text(encoding="utf-8"))

        self.assertEqual(messages, [])
        self.assertEqual(updated["status"], "orphaned")
        self.assertIn("no longer matches the launch record", updated["reconcile_reason"])
        self.assertIn("Marked ActiveJobs record reused.json orphaned", "\n".join(reconcile_messages))

    def test_active_job_pid_identity_unknown_when_inspection_fails(self) -> None:
        class FakeNoSuchProcess(Exception):
            pass

        class FakeProcess:
            def is_running(self) -> bool:
                return True

            def status(self) -> str:
                return "running"

            def cmdline(self) -> list[str]:
                raise RuntimeError("cmdline denied")

            def cwd(self) -> str:
                raise RuntimeError("cwd denied")

        class FakePsutil:
            NoSuchProcess = FakeNoSuchProcess
            STATUS_ZOMBIE = "zombie"

            @staticmethod
            def Process(_pid: int):
                return FakeProcess()

        from mediapipeline_desktop_app.contracts import ActiveJobRecord

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            record = write_active_job_launch_record(
                FakeProc(pid=5555),
                resolved=self._resolved(root),
                job_kind="pipeline",
                mode="continuous",
                command_line="pwsh -File pipeline.ps1",
                args=["pwsh", "-File", "pipeline.ps1"],
                launch_cwd=root,
                show_console=False,
                metadata={},
                stdout_log=None,
                stderr_log=None,
                app_pid=999,
            )
            payload = json.loads(record.read_text(encoding="utf-8"))

        self.assertIsNone(active_job_pid_matches_record(ActiveJobRecord.from_mapping(payload), FakePsutil))

    def test_active_job_pid_alive_distinguishes_running_zombie_missing_and_unknown(self) -> None:
        class FakeNoSuchProcess(Exception):
            pass

        class FakeProcess:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def is_running(self) -> bool:
                return self.pid != 3

            def status(self) -> str:
                return "zombie" if self.pid == 2 else "running"

        class FakePsutil:
            NoSuchProcess = FakeNoSuchProcess
            STATUS_ZOMBIE = "zombie"

            @staticmethod
            def Process(pid: int):
                if pid == 4:
                    raise FakeNoSuchProcess()
                if pid == 5:
                    raise RuntimeError("denied")
                return FakeProcess(pid)

        self.assertTrue(active_job_pid_is_alive(1, FakePsutil))
        self.assertFalse(active_job_pid_is_alive(2, FakePsutil))
        self.assertFalse(active_job_pid_is_alive(3, FakePsutil))
        self.assertFalse(active_job_pid_is_alive(4, FakePsutil))
        self.assertIsNone(active_job_pid_is_alive(5, FakePsutil))

    def test_service_wrappers_match_extracted_active_job_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyActiveJobService()
            proc = FakeProc(pid=6789)
            resolved = self._resolved(root)

            record_path = service._write_active_job_launch_record(
                proc,
                resolved=resolved,
                job_kind="rerun_csv",
                mode="rerun_csv",
                command_line="pwsh rerun.ps1",
                args=["pwsh", "rerun.ps1"],
                launch_cwd=root,
                show_console=False,
                metadata={},
            )
            service.update_active_job_record(proc, status="active")

            payload = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(service._active_jobs_dir_for_resolved(resolved), resolved.active_jobs_path)
            self.assertEqual(service._active_job_record_path_for_proc(proc), record_path)
            self.assertEqual(payload["status"], "active")


if __name__ == "__main__":
    unittest.main()
