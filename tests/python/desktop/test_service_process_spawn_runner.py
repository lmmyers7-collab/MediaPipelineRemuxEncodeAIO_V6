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

from mediapipeline.core.processes.spawn_runner import (
    _finalize_process_ownership_after_tree_proof,
    _launch_cleanup_reconciliation_required,
    _start_active_job_completion_watcher,
    spawn_process_for_service,
)
from mediapipeline.core.processes.kill import (
    _clear_process_tree_cleanup_reconciliation_required,
    _mark_process_tree_cleanup_reconciliation_required,
    _process_tree_cleanup_reconciliation_required,
)
from mediapipeline.core.processes.guard_facade import ProcessGuardFacadeMixin
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
        self.killed_labels.append(label)
        proc.kill()
        self.update_active_job_record(proc, status="killed", return_code=proc.returncode)
        return f"killed {label}"

    def update_active_job_record(self, proc, *, status=None, return_code=None) -> None:
        self.active_job_updates.append((proc, status, return_code))


class IntegratedProcessLifecycleService(ProcessLifecycleServiceMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_service_process_spawn_runner.integrated")
        self._active_spawned_processes_lock = threading.Lock()
        self._active_spawned_processes: dict[int, tuple[object, str]] = {}
        self.active_job_updates: list[tuple[object, str | None, int | None]] = []

    def update_active_job_record(self, proc, *, status=None, return_code=None) -> None:
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

    def test_spawn_runner_releases_lease_after_successful_tree_cleanup(self) -> None:
        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def activate(self, child_pid: int) -> None:
                _ = child_pid

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        with tempfile.TemporaryDirectory() as td:
            lease = FakeLifecycleLease()
            service = DummySpawnRunnerService(Path(td))
            service.readiness_exception = RuntimeError("readiness update failed")
            service._consume_pending_lifecycle_lease = lambda: lease  # type: ignore[attr-defined]
            fake_proc = FakeSpawnProcess()

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ):
                with self.assertRaisesRegex(RuntimeError, "readiness update failed"):
                    spawn_process_for_service(
                        service,
                        ["pwsh", "-File", "Pipeline.ps1"],
                        False,
                        job_kind="pipeline",
                    )

            self.assertEqual(service.killed_labels, ["pipeline launch failure"])
            self.assertEqual(fake_proc.kill_calls, 1)
            self.assertEqual(lease.release_outcomes, ["launch_failed"])

    def test_spawn_runner_preserves_lease_when_launch_failure_child_exit_is_unverified(self) -> None:
        class FakeLifecycleLease:
            __slots__ = ("activated_pids", "release_outcomes")

            def __init__(self) -> None:
                self.activated_pids: list[int] = []
                self.release_outcomes: list[str] = []

            def activate(self, child_pid: int) -> None:
                self.activated_pids.append(child_pid)

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class UnstoppableFakeSpawnProcess(FakeSpawnProcess):
            def poll(self) -> int | None:
                return None

            def kill(self) -> None:
                self.kill_calls += 1

            def wait(self, timeout: float | None = None) -> int | None:
                self.wait_calls.append(timeout)
                raise subprocess.TimeoutExpired(["pwsh"], timeout)

        class FakeMemoryLock:
            def __init__(self) -> None:
                self.released = False

            def release(self) -> None:
                self.released = True

        with tempfile.TemporaryDirectory() as td:
            lease = FakeLifecycleLease()
            service = DummySpawnRunnerService(Path(td))
            service.readiness_exception = RuntimeError("readiness update failed")
            service._consume_pending_lifecycle_lease = lambda: lease  # type: ignore[attr-defined]
            service.kill_process_tree = (  # type: ignore[method-assign]
                lambda proc, label: (
                    service.killed_labels.append(label)
                    or "Kill requested, but taskkill timed out and exit could not be verified."
                )
            )
            fake_proc = UnstoppableFakeSpawnProcess()

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ):
                with self.assertLogs(service.logger, level="WARNING") as captured_logs:
                    with self.assertRaisesRegex(RuntimeError, "readiness update failed") as captured_error:
                        spawn_process_for_service(
                            service,
                            ["pwsh", "-File", "Pipeline.ps1"],
                            False,
                            job_kind="rerun_csv",
                        )

            memory_lock = FakeMemoryLock()
            guard = ProcessGuardFacadeMixin()
            guard.service = service
            guard._release_process_launch_lock(
                {"memory_lock": memory_lock, "lease": lease, "transferred": False}
            )

            self.assertEqual(lease.activated_pids, [fake_proc.pid])
            self.assertEqual(service.killed_labels, ["rerun_csv launch failure"])
            self.assertEqual(fake_proc.kill_calls, 1)
            self.assertEqual(fake_proc.wait_calls, [5.0])
            self.assertEqual(lease.release_outcomes, [])
            self.assertTrue(memory_lock.released)
            self.assertTrue(
                any("could not verify" in note.lower() for note in getattr(captured_error.exception, "__notes__", []))
            )
            self.assertTrue(any("could not verify" in message.lower() for message in captured_logs.output))

    def test_spawn_runner_preserves_lease_when_tree_kill_is_degraded_after_root_exit(self) -> None:
        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def activate(self, child_pid: int) -> None:
                _ = child_pid

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class FakeMemoryLock:
            def release(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as td:
            lease = FakeLifecycleLease()
            service = DummySpawnRunnerService(Path(td))
            service.readiness_exception = RuntimeError("readiness update failed")
            service._consume_pending_lifecycle_lease = lambda: lease  # type: ignore[attr-defined]
            fake_proc = FakeSpawnProcess()

            def degraded_tree_kill(proc, label: str) -> str:
                service.killed_labels.append(label)
                proc.returncode = -9
                return (
                    "Kill requested for process tree, but taskkill timed out and descendant exit "
                    "could not be verified."
                )

            service.kill_process_tree = degraded_tree_kill  # type: ignore[method-assign]

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ):
                with self.assertLogs(service.logger, level="WARNING") as captured_logs:
                    with self.assertRaisesRegex(RuntimeError, "readiness update failed") as captured_error:
                        spawn_process_for_service(
                            service,
                            ["pwsh", "-File", "Pipeline.ps1"],
                            False,
                            job_kind="rerun_csv",
                        )

            self.assertTrue(_launch_cleanup_reconciliation_required(lease))
            self.assertTrue(_launch_cleanup_reconciliation_required(lease))
            guard = ProcessGuardFacadeMixin()
            guard.service = service
            guard._release_process_launch_lock(
                {"memory_lock": FakeMemoryLock(), "lease": lease, "transferred": False}
            )

            self.assertEqual(service.killed_labels, ["rerun_csv launch failure"])
            self.assertEqual(fake_proc.kill_calls, 0)
            self.assertEqual(lease.release_outcomes, [])
            self.assertFalse(_launch_cleanup_reconciliation_required(lease))
            self.assertTrue(service._active_spawned_process_is_registered(fake_proc))
            _clear_process_tree_cleanup_reconciliation_required(fake_proc)
            self.assertTrue(_finalize_process_ownership_after_tree_proof(fake_proc, -9))
            self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
            self.assertEqual(lease.release_outcomes, ["launch_failed"])
            self.assertTrue(
                any("process tree" in note.lower() for note in getattr(captured_error.exception, "__notes__", []))
            )
            self.assertTrue(any("could not be verified" in message.lower() for message in captured_logs.output))

    def test_spawn_runner_preserves_lease_when_tree_kill_reports_already_exited_after_alive_poll(self) -> None:
        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def activate(self, child_pid: int) -> None:
                _ = child_pid

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class FakeMemoryLock:
            def release(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as td:
            lease = FakeLifecycleLease()
            service = DummySpawnRunnerService(Path(td))
            service.readiness_exception = RuntimeError("readiness update failed")
            service._consume_pending_lifecycle_lease = lambda: lease  # type: ignore[attr-defined]
            fake_proc = FakeSpawnProcess()

            def already_exited_tree_kill(proc, label: str) -> str:
                service.killed_labels.append(label)
                proc.returncode = 0
                return f"App-owned {label} process already exited."

            service.kill_process_tree = already_exited_tree_kill  # type: ignore[method-assign]

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ):
                with self.assertLogs(service.logger, level="WARNING") as captured_logs:
                    with self.assertRaisesRegex(RuntimeError, "readiness update failed"):
                        spawn_process_for_service(
                            service,
                            ["pwsh", "-File", "Pipeline.ps1"],
                            False,
                            job_kind="rerun_csv",
                        )

            guard = ProcessGuardFacadeMixin()
            guard.service = service
            guard._release_process_launch_lock(
                {"memory_lock": FakeMemoryLock(), "lease": lease, "transferred": False}
            )

            self.assertEqual(service.killed_labels, ["rerun_csv launch failure"])
            self.assertEqual(lease.release_outcomes, [])
            self.assertTrue(any("process tree" in message.lower() for message in captured_logs.output))

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

    def test_completion_watcher_preserves_registration_and_lease_when_wait_cannot_verify_exit(self) -> None:
        class WaitFailureProcess(FakeSpawnProcess):
            def poll(self) -> int | None:
                return None

            def wait(self, timeout: float | None = None) -> int | None:
                self.wait_calls.append(timeout)
                raise OSError("process wait failed")

        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class ImmediateThread:
            def __init__(self, *, target, **kwargs) -> None:
                _ = kwargs
                self.target = target

            def start(self) -> None:
                self.target()

        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            fake_proc = WaitFailureProcess()
            lease = FakeLifecycleLease()
            fake_proc._mediapipeline_lifecycle_lease = lease  # type: ignore[attr-defined]
            service._register_active_spawned_process(fake_proc, "rerun_csv")

            with patch("mediapipeline.core.processes.spawn_runner.threading.Thread", ImmediateThread):
                with self.assertLogs(service.logger, level="WARNING") as captured_logs:
                    started = _start_active_job_completion_watcher(
                        service,
                        fake_proc,  # type: ignore[arg-type]
                        "rerun_csv",
                        metadata={"enrollment_path": "C:/state/enrollment.json"},
                    )

            self.assertTrue(started)
            self.assertTrue(service._active_spawned_process_is_registered(fake_proc))
            self.assertEqual(service.unregistered_processes, [])
            self.assertEqual(lease.release_outcomes, [])
            self.assertTrue(any("reconciliation" in message.lower() for message in captured_logs.output))

    def test_completion_watcher_runs_terminalization_when_wait_raises_but_poll_proves_exit(self) -> None:
        class WaitFailureAfterExitProcess(FakeSpawnProcess):
            def __init__(self) -> None:
                super().__init__(returncode=7)

            def wait(self, timeout: float | None = None) -> int | None:
                self.wait_calls.append(timeout)
                raise OSError("wait handle failed after exit")

        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class ImmediateThread:
            def __init__(self, *, target, **kwargs) -> None:
                _ = kwargs
                self.target = target

            def start(self) -> None:
                self.target()

        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            fake_proc = WaitFailureAfterExitProcess()
            lease = FakeLifecycleLease()
            fake_proc._mediapipeline_lifecycle_lease = lease  # type: ignore[attr-defined]
            service._register_active_spawned_process(fake_proc, "rerun_csv")
            sync_calls: list[dict[str, object]] = []
            service.sync_audit_sources_after_process_exit = (  # type: ignore[method-assign]
                lambda proc, **kwargs: sync_calls.append({"proc": proc, **kwargs})
            )
            finalized: list[tuple[dict[str, object], int | None]] = []

            with patch("mediapipeline.core.processes.spawn_runner.threading.Thread", ImmediateThread), patch(
                "mediapipeline.core.processes.spawn_runner.finalize_rerun_enrollment_after_exit",
                side_effect=lambda metadata, return_code: finalized.append((metadata, return_code)),
            ):
                with self.assertLogs(service.logger, level="WARNING") as captured_logs:
                    started = _start_active_job_completion_watcher(
                        service,
                        fake_proc,  # type: ignore[arg-type]
                        "rerun_csv",
                        resolved=object(),  # type: ignore[arg-type]
                        metadata={"enrollment_path": "C:/state/enrollment.json"},
                    )

            self.assertTrue(started)
            self.assertEqual(service.active_job_updates, [(fake_proc, 7)])
            self.assertEqual(finalized, [({"enrollment_path": "C:/state/enrollment.json"}, 7)])
            self.assertEqual(len(sync_calls), 1)
            self.assertIs(sync_calls[0]["proc"], fake_proc)
            self.assertEqual(sync_calls[0]["job_kind"], "rerun_csv")
            self.assertEqual(sync_calls[0]["return_code"], 7)
            self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
            self.assertEqual(service.unregistered_processes, [fake_proc.pid])
            self.assertEqual(lease.release_outcomes, ["failed"])
            self.assertTrue(any("poll verified" in message.lower() for message in captured_logs.output))

    def test_completion_watcher_preserves_degraded_tree_cleanup_evidence(self) -> None:
        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class ImmediateThread:
            def __init__(self, *, target, **kwargs) -> None:
                _ = kwargs
                self.target = target

            def start(self) -> None:
                self.target()

        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            fake_proc = FakeSpawnProcess(returncode=-9)
            lease = FakeLifecycleLease()
            fake_proc._mediapipeline_lifecycle_lease = lease  # type: ignore[attr-defined]
            service._register_active_spawned_process(fake_proc, "rerun_csv")
            _mark_process_tree_cleanup_reconciliation_required(fake_proc)
            finalized: list[tuple[dict[str, object], int | None]] = []

            with patch("mediapipeline.core.processes.spawn_runner.threading.Thread", ImmediateThread), patch(
                "mediapipeline.core.processes.spawn_runner.finalize_rerun_enrollment_after_exit",
                side_effect=lambda metadata, return_code: finalized.append((metadata, return_code)),
            ):
                with self.assertLogs(service.logger, level="WARNING") as captured_logs:
                    started = _start_active_job_completion_watcher(
                        service,
                        fake_proc,  # type: ignore[arg-type]
                        "rerun_csv",
                        metadata={"enrollment_path": "C:/state/enrollment.json"},
                    )

            self.assertTrue(started)
            self.assertEqual(service.active_job_updates, [])
            self.assertEqual(finalized, [])
            self.assertTrue(service._active_spawned_process_is_registered(fake_proc))
            self.assertEqual(service.unregistered_processes, [])
            self.assertEqual(lease.release_outcomes, [])
            self.assertTrue(any("tree cleanup" in message.lower() for message in captured_logs.output))

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

    def test_rerun_completion_finalizes_enrollment_when_process_was_already_unregistered(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            fake_proc = FakeSpawnProcess(returncode=7)
            finalized = threading.Event()
            calls: list[tuple[dict[str, object], int | None]] = []

            def finalize(metadata: dict[str, object], return_code: int | None) -> None:
                calls.append((metadata, return_code))
                finalized.set()

            with patch("mediapipeline.core.processes.spawn_runner.finalize_rerun_enrollment_after_exit", finalize):
                started = _start_active_job_completion_watcher(
                    service,
                    fake_proc,  # type: ignore[arg-type]
                    "rerun_csv",
                    metadata={"enrollment_path": "C:/state/enrollment.json"},
                )
                self.assertTrue(started)
                self.assertTrue(finalized.wait(timeout=2))

            self.assertEqual(service.active_job_updates, [])
            self.assertEqual(calls, [({"enrollment_path": "C:/state/enrollment.json"}, 7)])

    def test_rerun_completion_finalizes_enrollment_when_active_job_update_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            fake_proc = FakeSpawnProcess(returncode=9)
            service._register_active_spawned_process(fake_proc, "rerun_csv")
            finalized = threading.Event()

            def update_raises(proc, return_code=None, status=None) -> None:
                _ = (proc, return_code, status)
                raise OSError("ActiveJobs unavailable")

            service.update_active_job_record = update_raises  # type: ignore[method-assign]

            with patch(
                "mediapipeline.core.processes.spawn_runner.finalize_rerun_enrollment_after_exit",
                side_effect=lambda metadata, return_code: finalized.set(),
            ):
                started = _start_active_job_completion_watcher(
                    service,
                    fake_proc,  # type: ignore[arg-type]
                    "rerun_csv",
                    metadata={"enrollment_path": "C:/state/enrollment.json"},
                )
                self.assertTrue(started)
                self.assertTrue(finalized.wait(timeout=2))

            self.assertEqual(service.registered_processes, {})

    def test_force_cleanup_finalizes_exact_owner_after_tree_proof(self) -> None:
        service = DummyProcessLifecycleService()
        fake_proc = FakeSpawnProcess()
        service._register_active_spawned_process(fake_proc, "pipeline")

        messages = service.kill_active_spawned_processes()

        self.assertEqual(messages, ["killed pipeline"])
        self.assertEqual(service.killed_labels, ["pipeline"])
        self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
        self.assertEqual(service.active_job_updates, [(fake_proc, "killed", -9)])

    def test_spawned_process_registry_requires_exact_identity_for_same_pid(self) -> None:
        service = IntegratedProcessLifecycleService()
        original = FakeSpawnProcess()
        reused = FakeSpawnProcess()

        service._register_active_spawned_process(original, "pipeline")

        with self.assertRaisesRegex(RuntimeError, "already owned"):
            service._register_active_spawned_process(reused, "rerun_csv")

        self.assertTrue(service._active_spawned_process_is_registered(original))
        self.assertFalse(service._active_spawned_process_is_registered(reused))
        self.assertFalse(service._unregister_active_spawned_process(reused))
        self.assertTrue(service._active_spawned_process_is_registered(original))

    def test_delayed_old_watcher_cannot_unregister_reused_pid_owner(self) -> None:
        class ImmediateThread:
            def __init__(self, *, target, **kwargs) -> None:
                _ = kwargs
                self.target = target

            def start(self) -> None:
                self.target()

        service = IntegratedProcessLifecycleService()
        old_proc = FakeSpawnProcess(returncode=0)
        new_proc = FakeSpawnProcess()
        service._register_active_spawned_process(old_proc, "pipeline")
        self.assertTrue(service._unregister_active_spawned_process(old_proc))
        service._register_active_spawned_process(new_proc, "rerun_csv")

        with patch("mediapipeline.core.processes.spawn_runner.threading.Thread", ImmediateThread):
            self.assertTrue(_start_active_job_completion_watcher(service, old_proc, "pipeline"))

        self.assertFalse(service._active_spawned_process_is_registered(old_proc))
        self.assertTrue(service._active_spawned_process_is_registered(new_proc))

    def test_degraded_force_cleanup_preserves_registry_lease_and_rerun_enrollment(self) -> None:
        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class DeferredThread:
            targets: list[object] = []

            def __init__(self, *, target, **kwargs) -> None:
                _ = kwargs
                self.target = target

            def start(self) -> None:
                self.targets.append(self.target)

        service = IntegratedProcessLifecycleService()
        fake_proc = FakeSpawnProcess()
        lease = FakeLifecycleLease()
        fake_proc._mediapipeline_lifecycle_lease = lease  # type: ignore[attr-defined]
        service._register_active_spawned_process(fake_proc, "rerun_csv")
        finalized: list[tuple[dict[str, object], int | None]] = []

        with patch("mediapipeline.core.processes.spawn_runner.threading.Thread", DeferredThread), patch(
            "mediapipeline.core.processes.spawn_runner.finalize_rerun_enrollment_after_exit",
            side_effect=lambda metadata, return_code: finalized.append((metadata, return_code)),
        ), patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["taskkill"], 10),
        ):
            self.assertTrue(
                _start_active_job_completion_watcher(
                    service,
                    fake_proc,  # type: ignore[arg-type]
                    "rerun_csv",
                    metadata={"enrollment_path": "C:/state/enrollment.json"},
                )
            )
            messages = service.kill_active_spawned_processes()
            self.assertEqual(len(DeferredThread.targets), 1)
            DeferredThread.targets[0]()  # type: ignore[operator]

            retry_messages = service.kill_active_spawned_processes()
            self.assertTrue(_process_tree_cleanup_reconciliation_required(fake_proc))
            self.assertTrue(service._active_spawned_process_is_registered(fake_proc))
            self.assertEqual(lease.release_outcomes, [])
            self.assertEqual(finalized, [])
            self.assertEqual(service.active_job_updates, [(fake_proc, "kill_degraded", -9)])

            _clear_process_tree_cleanup_reconciliation_required(fake_proc)
            self.assertTrue(_finalize_process_ownership_after_tree_proof(fake_proc, -9))
            self.assertFalse(_finalize_process_ownership_after_tree_proof(fake_proc, -9))

        self.assertIn("taskkill timed out", messages[0])
        self.assertEqual(
            service.active_job_updates,
            [
                (fake_proc, "kill_degraded", -9),
                (fake_proc, "killed", -9),
            ],
        )
        self.assertEqual(
            finalized,
            [({"enrollment_path": "C:/state/enrollment.json"}, -9)],
        )
        self.assertFalse(_process_tree_cleanup_reconciliation_required(fake_proc))
        self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
        self.assertEqual(lease.release_outcomes, ["failed"])
        self.assertEqual(len(retry_messages), 1)
        self.assertIn("descendant cleanup still requires reconciliation", retry_messages[0])

    def test_verified_force_cleanup_releases_lease_without_overwriting_killed_status(self) -> None:
        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class DeferredThread:
            targets: list[object] = []

            def __init__(self, *, target, **kwargs) -> None:
                _ = kwargs
                self.target = target

            def start(self) -> None:
                self.targets.append(self.target)

        service = IntegratedProcessLifecycleService()
        fake_proc = FakeSpawnProcess()
        lease = FakeLifecycleLease()
        fake_proc._mediapipeline_lifecycle_lease = lease  # type: ignore[attr-defined]
        service._register_active_spawned_process(fake_proc, "pipeline")

        def successful_taskkill(*args, **kwargs):
            _ = (args, kwargs)
            fake_proc.returncode = -9
            return subprocess.CompletedProcess(["taskkill"], 0, stdout="SUCCESS", stderr="")

        with patch("mediapipeline.core.processes.spawn_runner.threading.Thread", DeferredThread), patch(
            "mediapipeline.core.processes.kill.os.name", "nt"
        ), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=successful_taskkill,
        ):
            self.assertTrue(
                _start_active_job_completion_watcher(
                    service,
                    fake_proc,  # type: ignore[arg-type]
                    "pipeline",
                )
            )
            messages = service.kill_active_spawned_processes()
            DeferredThread.targets[0]()  # type: ignore[operator]

        self.assertEqual(messages, ["Force-killed pipeline process tree (PID 1234)."])
        self.assertEqual(service.active_job_updates, [(fake_proc, "killed", -9)])
        self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
        self.assertEqual(lease.release_outcomes, ["failed"])

    def test_tree_proof_finalizes_ownership_even_when_active_job_write_fails(self) -> None:
        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class DeferredThread:
            def __init__(self, *, target, **kwargs) -> None:
                _ = (target, kwargs)

            def start(self) -> None:
                return None

        service = IntegratedProcessLifecycleService()
        fake_proc = FakeSpawnProcess()
        lease = FakeLifecycleLease()
        fake_proc._mediapipeline_lifecycle_lease = lease  # type: ignore[attr-defined]
        service._register_active_spawned_process(fake_proc, "pipeline")
        with patch("mediapipeline.core.processes.spawn_runner.threading.Thread", DeferredThread):
            _start_active_job_completion_watcher(service, fake_proc, "pipeline")

        def update_raises(proc, *, status=None, return_code=None) -> None:
            _ = (proc, status, return_code)
            raise OSError("ActiveJobs unavailable")

        service.update_active_job_record = update_raises  # type: ignore[method-assign]

        def successful_taskkill(*args, **kwargs):
            _ = (args, kwargs)
            fake_proc.returncode = -9
            return subprocess.CompletedProcess(["taskkill"], 0, stdout="SUCCESS", stderr="")

        with patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=successful_taskkill,
        ):
            messages = service.kill_active_spawned_processes()

        self.assertEqual(messages, ["Force-killed pipeline process tree (PID 1234)."])
        self.assertFalse(_process_tree_cleanup_reconciliation_required(fake_proc))
        self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
        self.assertEqual(lease.release_outcomes, ["failed"])

    def test_verified_retry_after_degraded_kill_clears_marker_and_releases_ownership(self) -> None:
        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class DeferredThread:
            targets: list[object] = []

            def __init__(self, *, target, **kwargs) -> None:
                _ = kwargs
                self.target = target

            def start(self) -> None:
                self.targets.append(self.target)

        class WaitObservedProcess(FakeSpawnProcess):
            def __init__(self) -> None:
                super().__init__()
                self.wait_observed = threading.Event()

            def wait(self, timeout: float | None = None) -> int | None:
                self.wait_observed.set()
                return super().wait(timeout)

        service = IntegratedProcessLifecycleService()
        fake_proc = WaitObservedProcess()
        lease = FakeLifecycleLease()
        fake_proc._mediapipeline_lifecycle_lease = lease  # type: ignore[attr-defined]
        service._register_active_spawned_process(fake_proc, "rerun_csv")
        finalized: list[tuple[dict[str, object], int | None]] = []
        attempts = 0
        real_thread = threading.Thread
        completion_thread: threading.Thread | None = None

        def taskkill_result(*args, **kwargs):
            nonlocal attempts, completion_thread
            _ = (args, kwargs)
            attempts += 1
            if attempts == 1:
                raise subprocess.TimeoutExpired(["taskkill"], 10)
            fake_proc.returncode = -9
            completion_thread = real_thread(target=DeferredThread.targets[0])  # type: ignore[arg-type]
            completion_thread.start()
            self.assertTrue(fake_proc.wait_observed.wait(timeout=1.0))
            return subprocess.CompletedProcess(["taskkill"], 0, stdout="SUCCESS", stderr="")

        with patch("mediapipeline.core.processes.spawn_runner.threading.Thread", DeferredThread), patch(
            "mediapipeline.core.processes.spawn_runner.finalize_rerun_enrollment_after_exit",
            side_effect=lambda metadata, return_code: finalized.append((metadata, return_code)),
        ), patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=taskkill_result,
        ), patch("mediapipeline.core.processes.kill.fallback_kill_process_handle"):
            self.assertTrue(
                _start_active_job_completion_watcher(
                    service,
                    fake_proc,  # type: ignore[arg-type]
                    "rerun_csv",
                    metadata={"enrollment_path": "C:/state/enrollment.json"},
                )
            )
            first_messages = service.kill_active_spawned_processes()
            self.assertTrue(_process_tree_cleanup_reconciliation_required(fake_proc))
            self.assertTrue(service._active_spawned_process_is_registered(fake_proc))
            fake_proc.wait_observed.clear()

            second_messages = service.kill_active_spawned_processes()
            self.assertEqual(len(DeferredThread.targets), 1)
            self.assertIsNotNone(completion_thread)
            completion_thread.join(timeout=1.0)  # type: ignore[union-attr]
            self.assertFalse(completion_thread.is_alive())  # type: ignore[union-attr]

        self.assertIn("taskkill timed out", first_messages[0])
        self.assertEqual(second_messages, ["Force-killed rerun_csv process tree (PID 1234)."])
        self.assertFalse(_process_tree_cleanup_reconciliation_required(fake_proc))
        self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
        self.assertEqual(
            service.active_job_updates,
            [
                (fake_proc, "kill_degraded", None),
                (fake_proc, "killed", -9),
            ],
        )
        self.assertEqual(
            finalized,
            [({"enrollment_path": "C:/state/enrollment.json"}, -9)],
        )
        self.assertEqual(lease.release_outcomes, ["failed"])

    def test_heartbeat_thread_start_failure_unregisters_after_verified_cleanup(self) -> None:
        self._assert_watcher_start_failure_cleanup("heartbeat", degraded=False)

    def test_completion_thread_start_failure_unregisters_after_verified_cleanup(self) -> None:
        self._assert_watcher_start_failure_cleanup("completion", degraded=False)

    def test_heartbeat_thread_start_failure_preserves_ambiguous_cleanup(self) -> None:
        self._assert_watcher_start_failure_cleanup("heartbeat", degraded=True)

    def test_completion_thread_start_failure_preserves_ambiguous_cleanup(self) -> None:
        self._assert_watcher_start_failure_cleanup("completion", degraded=True)

    def _assert_watcher_start_failure_cleanup(self, watcher_kind: str, *, degraded: bool) -> None:
        class FakeLifecycleLease:
            def __init__(self) -> None:
                self.release_outcomes: list[str] = []

            def activate(self, child_pid: int) -> None:
                _ = child_pid

            def release(self, *, outcome: str) -> None:
                self.release_outcomes.append(outcome)

        class SelectiveStartFailureThread:
            def __init__(self, *, target, name: str, **kwargs) -> None:
                _ = (target, kwargs)
                self.name = name

            def start(self) -> None:
                if watcher_kind in self.name:
                    raise RuntimeError(f"{watcher_kind} thread start failed")

        class InitiallyUnstoppableProcess(FakeSpawnProcess):
            def kill(self) -> None:
                self.kill_calls += 1

            def wait(self, timeout: float | None = None) -> int | None:
                self.wait_calls.append(timeout)
                if self.returncode is None:
                    raise subprocess.TimeoutExpired(["pwsh"], timeout)
                return self.returncode

        with tempfile.TemporaryDirectory() as td:
            service = DummySpawnRunnerService(Path(td))
            lease = FakeLifecycleLease()
            service._consume_pending_lifecycle_lease = lambda: lease  # type: ignore[attr-defined]
            fake_proc = InitiallyUnstoppableProcess() if degraded else FakeSpawnProcess()

            if degraded:
                def degraded_tree_kill(proc, label: str) -> str:
                    service.killed_labels.append(label)
                    return "Kill requested, but descendant cleanup could not be verified."

                service.kill_process_tree = degraded_tree_kill  # type: ignore[method-assign]

            with patch(
                "mediapipeline.core.processes.spawn_runner.subprocess.Popen",
                lambda *args, **kwargs: fake_proc,
            ), patch(
                "mediapipeline.core.processes.spawn_runner.threading.Thread",
                SelectiveStartFailureThread,
            ):
                with self.assertRaisesRegex(RuntimeError, f"{watcher_kind} thread start failed"):
                    spawn_process_for_service(
                        service,
                        ["pwsh", "-File", "Pipeline.ps1"],
                        False,
                        job_kind="rerun_csv",
                    )

            if degraded:
                self.assertTrue(service._active_spawned_process_is_registered(fake_proc))
                self.assertTrue(_process_tree_cleanup_reconciliation_required(fake_proc))
                self.assertEqual(lease.release_outcomes, [])
                self.assertTrue(_launch_cleanup_reconciliation_required(lease))

                def proven_tree_kill(proc, label: str) -> str:
                    service.killed_labels.append(label)
                    proc.returncode = -9
                    _clear_process_tree_cleanup_reconciliation_required(proc)
                    return f"Force-killed {label} process tree (PID {proc.pid})."

                service.kill_process_tree = proven_tree_kill  # type: ignore[method-assign]
                messages = [service.kill_process_tree(fake_proc, "rerun_csv")]
                self.assertTrue(_finalize_process_ownership_after_tree_proof(fake_proc, -9))
                self.assertEqual(messages, [f"Force-killed rerun_csv process tree (PID {fake_proc.pid})."])
                self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
                self.assertFalse(_process_tree_cleanup_reconciliation_required(fake_proc))
                self.assertEqual(lease.release_outcomes, ["launch_failed"])
                self.assertFalse(_finalize_process_ownership_after_tree_proof(fake_proc, -9))
                self.assertEqual(lease.release_outcomes, ["launch_failed"])
            else:
                self.assertFalse(service._active_spawned_process_is_registered(fake_proc))
                self.assertEqual(service.unregistered_processes, [fake_proc.pid])
                self.assertEqual(lease.release_outcomes, ["launch_failed"])

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
