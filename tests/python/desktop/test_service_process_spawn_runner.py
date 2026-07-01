from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.processes.spawn_runner import spawn_process_for_service
from mediapipeline.core.processes.lifecycle import ProcessLifecycleServiceMixin


class DummySpawnRunnerService:
    def __init__(self, root: Path) -> None:
        self.app_root = root / "DesktopApp"
        self.workspace_root = root / "Workspace"
        self.app_root.mkdir()
        self.workspace_root.mkdir()
        self.logger = logging.getLogger("test_service_process_spawn_runner")
        self.launch_records: list[dict] = []
        self.readiness_checks: list[tuple[object, str]] = []
        self.killed_labels: list[str] = []
        self.active_job_updates: list[tuple[object, int | None]] = []
        self.active_job_update_event = threading.Event()
        self.audit_sync_calls: list[dict[str, object]] = []
        self.audit_sync_event = threading.Event()
        self.registered_processes: dict[int, tuple[object, str]] = {}
        self.unregistered_processes: list[int] = []
        self.write_exception: Exception | None = None
        self.readiness_exception: Exception | None = None
        self._last_spawn_stdout_log: Path | None = None
        self._last_spawn_stderr_log: Path | None = None

    def _build_launch_environment(self) -> dict[str, str]:
        return {"PATH": "test-path"}

    def _write_active_job_launch_record(self, proc, **kwargs):
        if self.write_exception is not None:
            raise self.write_exception
        self.launch_records.append({"proc": proc, **kwargs})

    def _verify_spawn_readiness(self, proc, command_line: str) -> None:
        if self.readiness_exception is not None:
            raise self.readiness_exception
        self.readiness_checks.append((proc, command_line))

    def kill_process_tree(self, proc, label: str) -> str:
        self.killed_labels.append(label)
        proc.kill()
        return f"killed {label}"

    def update_active_job_record(self, proc, return_code=None, status=None) -> None:
        _ = status
        self.active_job_updates.append((proc, return_code))
        self.active_job_update_event.set()

    def sync_audit_sources_after_process_exit(self, proc, *, resolved, job_kind, return_code, metadata) -> None:
        if job_kind != "audit":
            return
        self.audit_sync_calls.append(
            {
                "proc": proc,
                "resolved": resolved,
                "job_kind": job_kind,
                "return_code": return_code,
                "metadata": metadata,
            }
        )
        self.audit_sync_event.set()

    def _register_active_spawned_process(self, proc, job_kind: str) -> None:
        self.registered_processes[int(proc.pid)] = (proc, job_kind)

    def _unregister_active_spawned_process(self, proc) -> None:
        self.unregistered_processes.append(int(proc.pid))
        self.registered_processes.pop(int(proc.pid), None)

    def _active_spawned_process_is_registered(self, proc) -> bool:
        return int(proc.pid) in self.registered_processes


class FakeSpawnProcess:
    def __init__(self, returncode: int | None = None) -> None:
        self.pid = 1234
        self.returncode = returncode
        self.kill_calls = 0
        self.wait_calls: list[float | None] = []

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int | None:
        self.wait_calls.append(timeout)
        return self.returncode


class DummyProcessLifecycleService(ProcessLifecycleServiceMixin):
    def __init__(self) -> None:
        self._active_spawned_processes_lock = threading.Lock()
        self._active_spawned_processes: dict[int, tuple[object, str]] = {}
        self.killed_labels: list[str] = []
        self.active_job_updates: list[tuple[object, str | None, int | None]] = []

    def kill_process_tree(self, proc, label: str) -> str:
        if self._active_spawned_process_is_registered(proc):
            raise AssertionError("process should be unregistered before force kill")
        self.killed_labels.append(label)
        proc.kill()
        self.update_active_job_record(proc, status="killed", return_code=proc.returncode)
        return f"killed {label}"

    def update_active_job_record(self, proc, status=None, return_code=None) -> None:
        self.active_job_updates.append((proc, status, return_code))


class SpawnRunnerTests(unittest.TestCase):
    def test_spawn_runner_launches_with_logs_active_record_and_closed_handles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            captured: dict[str, object] = {}
            fake_proc = FakeSpawnProcess()

            def fake_popen(args, stdin=None, **kwargs):
                captured["args"] = args
                captured["stdin"] = stdin
                captured["kwargs"] = kwargs
                return fake_proc

            with patch("mediapipeline.core.processes.spawn_runner.subprocess.Popen", fake_popen):
                result = spawn_process_for_service(
                    service,
                    ["pwsh", "-File", "Pipeline.ps1"],
                    False,
                    job_kind="pipeline",
                    mode="continuous",
                    metadata={"source": "test"},
                )

            self.assertIs(result, fake_proc)
            self.assertEqual(captured["args"], ["pwsh", "-File", "Pipeline.ps1"])
            self.assertEqual(captured["stdin"], subprocess.DEVNULL)
            kwargs = captured["kwargs"]
            self.assertIsInstance(kwargs, dict)
            self.assertEqual(kwargs["env"], {"PATH": "test-path"})
            self.assertEqual(kwargs["cwd"], str(service.workspace_root))
            self.assertTrue(kwargs["stdout"].closed)
            self.assertTrue(kwargs["stderr"].closed)
            self.assertEqual(len(service.launch_records), 1)
            self.assertEqual(service.launch_records[0]["job_kind"], "pipeline")
            self.assertEqual(service.launch_records[0]["mode"], "continuous")
            self.assertEqual(service.launch_records[0]["metadata"], {"source": "test"})
            self.assertEqual(len(service.readiness_checks), 1)
            self.assertTrue(service._last_spawn_stdout_log and service._last_spawn_stdout_log.exists())
            self.assertTrue(service._last_spawn_stderr_log and service._last_spawn_stderr_log.exists())

    def test_spawn_runner_kills_started_process_when_active_job_record_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            service.write_exception = RuntimeError("active job write failed")
            fake_proc = FakeSpawnProcess()

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ):
                with self.assertRaisesRegex(RuntimeError, "active job write failed"):
                    spawn_process_for_service(service, ["pwsh", "-File", "Pipeline.ps1"], False, job_kind="pipeline")

            self.assertEqual(service.killed_labels, ["pipeline launch failure"])
            self.assertEqual(fake_proc.kill_calls, 1)
            self.assertEqual(service.launch_records, [])

    def test_spawn_runner_kills_started_process_when_readiness_fails_while_running(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            service.readiness_exception = RuntimeError("readiness update failed")
            fake_proc = FakeSpawnProcess()

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ):
                with self.assertRaisesRegex(RuntimeError, "readiness update failed"):
                    spawn_process_for_service(service, ["pwsh", "-File", "Pipeline.ps1"], False, job_kind="pipeline")

            self.assertEqual(service.killed_labels, ["pipeline launch failure"])
            self.assertEqual(fake_proc.kill_calls, 1)
            self.assertEqual(len(service.launch_records), 1)

    def test_spawn_runner_does_not_kill_process_that_already_exited_during_readiness_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            service.readiness_exception = RuntimeError("immediate failure")
            fake_proc = FakeSpawnProcess(returncode=2)

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ):
                with self.assertRaisesRegex(RuntimeError, "immediate failure"):
                    spawn_process_for_service(service, ["pwsh", "-File", "Pipeline.ps1"], False, job_kind="pipeline")

            self.assertEqual(service.killed_labels, [])
            self.assertEqual(fake_proc.kill_calls, 0)
            self.assertEqual(len(service.launch_records), 1)

    def test_spawn_runner_updates_active_job_when_background_process_exits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            fake_proc = FakeSpawnProcess(returncode=0)

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ):
                result = spawn_process_for_service(service, ["pwsh", "-File", "Pipeline.ps1"], False, job_kind="pipeline")

            self.assertIs(result, fake_proc)
            self.assertTrue(service.active_job_update_event.wait(timeout=2.0))
            self.assertEqual(service.active_job_updates, [(fake_proc, 0)])
            self.assertEqual(service.audit_sync_calls, [])
            self.assertEqual(service.registered_processes, {})
            self.assertEqual(service.unregistered_processes, [fake_proc.pid])

    def test_spawn_runner_invokes_audit_sync_hook_after_successful_audit_exit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            fake_proc = FakeSpawnProcess(returncode=0)
            resolved = object()
            metadata = {"library_roots": ["C:/Media"]}

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ):
                result = spawn_process_for_service(
                    service,
                    ["pwsh", "-File", "Audit-MediaLibrary.ps1"],
                    False,
                    resolved=resolved,  # type: ignore[arg-type]
                    job_kind="audit",
                    metadata=metadata,
                )

            self.assertIs(result, fake_proc)
            self.assertTrue(service.active_job_update_event.wait(timeout=2.0))
            self.assertTrue(service.audit_sync_event.wait(timeout=2.0))
            self.assertEqual(service.active_job_updates, [(fake_proc, 0)])
            self.assertEqual(len(service.audit_sync_calls), 1)
            call = service.audit_sync_calls[0]
            self.assertIs(call["proc"], fake_proc)
            self.assertIs(call["resolved"], resolved)
            self.assertEqual(call["job_kind"], "audit")
            self.assertEqual(call["return_code"], 0)
            self.assertEqual(call["metadata"], metadata)
            self.assertEqual(service.registered_processes, {})

    def test_force_cleanup_unregisters_before_kill_so_watcher_cannot_overwrite_killed_status(self) -> None:
        service = DummyProcessLifecycleService()
        fake_proc = FakeSpawnProcess()
        service._register_active_spawned_process(fake_proc, "pipeline")

        messages = service.kill_active_spawned_processes()

        self.assertEqual(messages, ["killed pipeline"])
        self.assertEqual(service.killed_labels, ["pipeline"])
        self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
        self.assertEqual(service.active_job_updates, [(fake_proc, "killed", -9)])

    def test_force_cleanup_can_scope_to_audit_processes(self) -> None:
        service = DummyProcessLifecycleService()
        pipeline_proc = FakeSpawnProcess()
        pipeline_proc.pid = 1234
        audit_proc = FakeSpawnProcess()
        audit_proc.pid = 1235
        service._register_active_spawned_process(pipeline_proc, "pipeline")
        service._register_active_spawned_process(audit_proc, "audit")

        messages = service.kill_active_spawned_processes(job_kinds={"audit"})

        self.assertEqual(messages, ["killed audit"])
        self.assertEqual(service.killed_labels, ["audit"])
        self.assertTrue(service._active_spawned_process_is_registered(pipeline_proc))
        self.assertFalse(service._active_spawned_process_is_registered(audit_proc))
        self.assertEqual(pipeline_proc.kill_calls, 0)
        self.assertEqual(audit_proc.kill_calls, 1)


if __name__ == "__main__":
    unittest.main()
