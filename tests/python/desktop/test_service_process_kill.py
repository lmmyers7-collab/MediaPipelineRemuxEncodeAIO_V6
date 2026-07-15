from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.processes.kill import (
    _mark_process_tree_cleanup_reconciliation_required,
    _process_tree_cleanup_reconciliation_required,
    find_related_pipeline_processes,
    kill_process_tree,
    kill_related_pipeline_processes,
    process_text_contains_any,
    wait_for_process_exit,
)
from mediapipeline.core.processes.lifecycle import ProcessLifecycleServiceMixin


class FakePopen:
    def __init__(self, *, pid: int = 4321, returncode: int | None = 0) -> None:
        self.pid = pid
        self.returncode = returncode
        self.wait_calls: list[float | None] = []

    def wait(self, timeout: float | None = None) -> int | None:
        self.wait_calls.append(timeout)
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode


class FakePsutilProc:
    def __init__(
        self,
        *,
        pid: int,
        name: str,
        exe: str = "",
        cmdline: list[str] | None = None,
        running: bool = True,
    ) -> None:
        self.pid = pid
        self.info = {"pid": pid, "name": name}
        self._exe = exe
        self._cmdline = cmdline or []
        self._running = running
        self.killed = False

    def exe(self) -> str:
        return self._exe

    def cmdline(self) -> list[str]:
        return self._cmdline

    def is_running(self) -> bool:
        return self._running

    def children(self, recursive: bool = False) -> list[Any]:
        return []

    def kill(self) -> None:
        self.killed = True
        self._running = False

    def terminate(self) -> None:
        self._running = False

    def status(self) -> str:
        return "stopped" if not self._running else "running"


class FakePsutil:
    STATUS_ZOMBIE = "zombie"
    processes: list[FakePsutilProc] = []

    @classmethod
    def process_iter(cls, _attrs: list[str]) -> list[FakePsutilProc]:
        return list(cls.processes)

    @staticmethod
    def wait_procs(targets: list[Any], timeout: float):
        return targets, []


class DummyKillService(ProcessLifecycleServiceMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_service_process_kill")
        self.logger.addHandler(logging.NullHandler())
        self.updated: list[dict[str, Any]] = []

    def update_active_job_record(self, proc: Any | None, *, status: str | None = None, return_code: int | None = None) -> None:
        self.updated.append({"proc": proc, "status": status, "return_code": return_code})


class ProcessKillHelperTests(unittest.TestCase):
    def _resolved(self, root: Path) -> ResolvedPaths:
        return ResolvedPaths(
            app_root=root / "DesktopApp",
            workspace_root=root,
            pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
            config_path=root / "Pipeline" / "MediaPipeline_config_chatgpt.psd1",
            audit_script_path=root / "Pipeline" / "Audit-MediaLibrary.ps1",
            rerun_script_path=root / "Pipeline" / "Invoke-RerunCsv.ps1",
            powershell_host="pwsh",
        )

    def test_wait_for_process_exit_returns_true_when_poll_is_terminal(self) -> None:
        proc = FakePopen(returncode=0)

        exited = wait_for_process_exit(proc, timeout_seconds=1.5)

        self.assertTrue(exited)
        self.assertEqual(proc.wait_calls, [1.5])

    def test_process_text_contains_any_matches_executable_or_command_line(self) -> None:
        proc = FakePsutilProc(
            pid=1,
            name="pwsh.exe",
            exe=r"C:\Tools\pwsh.exe",
            cmdline=[r"C:\Tools\pwsh.exe", "-File", r"C:\Bundle\ops\pipeline\entrypoints\MediaPipeline.ps1"],
        )

        self.assertTrue(process_text_contains_any(proc, [r"c:\bundle\ops\pipeline\entrypoints\mediapipeline.ps1"]))
        self.assertFalse(process_text_contains_any(proc, [r"c:\other\script.ps1"]))

    def test_find_related_pipeline_processes_filters_to_matching_powershell_processes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            matching = FakePsutilProc(
                pid=100,
                name="pwsh.exe",
                cmdline=["pwsh", "-File", str(resolved.pipeline_path)],
            )
            wrong_name = FakePsutilProc(
                pid=101,
                name="python.exe",
                cmdline=["python", str(resolved.pipeline_path)],
            )
            wrong_script = FakePsutilProc(
                pid=102,
                name="pwsh.exe",
                cmdline=["pwsh", "-File", str(root / "Other.ps1")],
            )
            FakePsutil.processes = [matching, wrong_name, wrong_script]

            matches = find_related_pipeline_processes(resolved, psutil_module=FakePsutil, current_pid=999)

        self.assertEqual(matches, [matching])

    def test_find_related_pipeline_processes_can_filter_by_job_kind(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            pipeline = FakePsutilProc(
                pid=100,
                name="pwsh.exe",
                cmdline=["pwsh", "-File", str(resolved.pipeline_path)],
            )
            audit = FakePsutilProc(
                pid=101,
                name="pwsh.exe",
                cmdline=["pwsh", "-File", str(resolved.audit_script_path)],
            )
            rerun = FakePsutilProc(
                pid=102,
                name="pwsh.exe",
                cmdline=["pwsh", "-File", str(resolved.rerun_script_path)],
            )
            FakePsutil.processes = [pipeline, audit, rerun]

            audit_matches = find_related_pipeline_processes(
                resolved,
                psutil_module=FakePsutil,
                current_pid=999,
                job_kinds={"audit"},
            )
            pipeline_matches = find_related_pipeline_processes(
                resolved,
                psutil_module=FakePsutil,
                current_pid=999,
                job_kinds={"pipeline"},
            )

        self.assertEqual(audit_matches, [audit])
        self.assertEqual(pipeline_matches, [pipeline])

    def test_find_related_pipeline_processes_fails_closed_without_psutil(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            resolved = self._resolved(Path(td))

            with self.assertRaisesRegex(RuntimeError, "psutil unavailable"):
                find_related_pipeline_processes(resolved, psutil_module=None)

    def test_kill_related_pipeline_processes_uses_psutil_tree_and_reports_message(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            matching = FakePsutilProc(
                pid=100,
                name="powershell.exe",
                cmdline=["powershell", "-File", str(resolved.audit_script_path)],
            )
            FakePsutil.processes = [matching]

            messages = kill_related_pipeline_processes(
                resolved,
                psutil_module=FakePsutil,
                logger=logging.getLogger("test_service_process_kill"),
            )

        self.assertTrue(matching.killed)
        self.assertEqual(messages, ["Force-killed related MediaPipeline process tree (PID 100)."])

    def test_kill_related_pipeline_processes_can_scope_to_audit_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            pipeline = FakePsutilProc(
                pid=100,
                name="pwsh.exe",
                cmdline=["pwsh", "-File", str(resolved.pipeline_path)],
            )
            audit = FakePsutilProc(
                pid=101,
                name="pwsh.exe",
                cmdline=["pwsh", "-File", str(resolved.audit_script_path)],
            )
            rerun = FakePsutilProc(
                pid=102,
                name="pwsh.exe",
                cmdline=["pwsh", "-File", str(resolved.rerun_script_path)],
            )
            FakePsutil.processes = [pipeline, audit, rerun]

            messages = kill_related_pipeline_processes(
                resolved,
                psutil_module=FakePsutil,
                logger=logging.getLogger("test_service_process_kill"),
                job_kinds={"audit"},
            )

        self.assertFalse(pipeline.killed)
        self.assertTrue(audit.killed)
        self.assertFalse(rerun.killed)
        self.assertEqual(messages, ["Force-killed related MediaPipeline audit process tree (PID 101)."])

    def test_kill_process_tree_already_exited_updates_active_job_without_taskkill(self) -> None:
        proc = FakePopen(pid=1234, returncode=0)
        updates: list[dict[str, Any]] = []

        message = kill_process_tree(
            proc,
            "pipeline",
            psutil_module=None,
            logger=logging.getLogger("test_service_process_kill"),
            update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
        )

        self.assertEqual(message, "App-owned pipeline process already exited.")
        self.assertEqual(updates, [{"proc": proc, "return_code": 0}])

    def test_kill_process_tree_returns_degraded_when_windows_taskkill_times_out(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []

        with patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["taskkill"], 10),
        ) as run:
            message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )

        self.assertIn("taskkill timed out", message)
        self.assertIn("without blocking the control path", message)
        self.assertEqual(updates, [{"proc": proc, "status": "kill_degraded", "return_code": None}])
        self.assertEqual(run.call_args.kwargs["timeout"], 10)

    def test_kill_process_tree_remains_degraded_when_timeout_fallback_exits_root(self) -> None:
        class FallbackExitPopen(FakePopen):
            def kill(self) -> None:
                self.returncode = -9

            def terminate(self) -> None:
                self.returncode = -15

        proc = FallbackExitPopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []

        with patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["taskkill"], 10),
        ):
            message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )

        self.assertIn("taskkill timed out", message)
        self.assertIn("could not be verified", message)
        self.assertEqual(updates, [{"proc": proc, "status": "kill_degraded", "return_code": -9}])

    def test_kill_process_tree_marks_degraded_evidence_before_fallback_can_exit_root(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []
        fallback_observations: list[tuple[bool, list[dict[str, Any]]]] = []

        def fallback_after_observing_marker(proc_arg, label: str, *, logger) -> None:
            _ = (label, logger)
            fallback_observations.append(
                (_process_tree_cleanup_reconciliation_required(proc_arg), list(updates))
            )
            proc_arg.returncode = -9

        with patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["taskkill"], 10),
        ), patch(
            "mediapipeline.core.processes.kill.wait_for_process_exit",
            return_value=False,
        ), patch(
            "mediapipeline.core.processes.kill.fallback_kill_process_handle",
            side_effect=fallback_after_observing_marker,
        ):
            message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )

        self.assertIn("taskkill timed out", message)
        self.assertEqual(
            fallback_observations,
            [(True, [])],
        )
        self.assertTrue(_process_tree_cleanup_reconciliation_required(proc))
        self.assertEqual(updates, [{"proc": proc, "status": "kill_degraded", "return_code": -9}])

    def test_kill_process_tree_is_degraded_when_nonzero_taskkill_result_coincides_with_root_exit(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []

        def failed_taskkill(*args, **kwargs):
            _ = (args, kwargs)
            proc.returncode = -9
            return subprocess.CompletedProcess(["taskkill"], 1, stdout="", stderr="Access denied")

        with patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=failed_taskkill,
        ):
            message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )

        self.assertIn("taskkill reported a failure", message)
        self.assertIn("could not be verified", message)
        self.assertEqual(updates, [{"proc": proc, "status": "kill_degraded", "return_code": -9}])

    def test_kill_process_tree_reports_success_when_taskkill_zero_exits_root(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []

        def successful_taskkill(*args, **kwargs):
            _ = (args, kwargs)
            proc.returncode = -9
            return subprocess.CompletedProcess(["taskkill"], 0, stdout="SUCCESS", stderr="")

        with patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=successful_taskkill,
        ):
            message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )

        self.assertEqual(message, "Force-killed pipeline process tree (PID 1234).")
        self.assertEqual(updates, [{"proc": proc, "status": "killed", "return_code": -9}])

    def test_successful_windows_tree_kill_retry_clears_prior_degraded_evidence(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []
        attempts = 0

        def taskkill_result(*args, **kwargs):
            nonlocal attempts
            _ = (args, kwargs)
            attempts += 1
            if attempts == 1:
                raise subprocess.TimeoutExpired(["taskkill"], 10)
            proc.returncode = -9
            return subprocess.CompletedProcess(["taskkill"], 0, stdout="SUCCESS", stderr="")

        with patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=taskkill_result,
        ), patch("mediapipeline.core.processes.kill.fallback_kill_process_handle"):
            first_message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )
            self.assertTrue(_process_tree_cleanup_reconciliation_required(proc))

            second_message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )

        self.assertIn("taskkill timed out", first_message)
        self.assertEqual(second_message, "Force-killed pipeline process tree (PID 1234).")
        self.assertFalse(_process_tree_cleanup_reconciliation_required(proc))
        self.assertEqual(
            updates,
            [
                {"proc": proc, "status": "kill_degraded", "return_code": None},
                {"proc": proc, "status": "killed", "return_code": -9},
            ],
        )

    def test_successful_non_windows_process_group_kill_clears_prior_degraded_evidence(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []
        _mark_process_tree_cleanup_reconciliation_required(proc)

        def successful_group_kill(process_group_id: int, kill_signal: int) -> None:
            _ = (process_group_id, kill_signal)
            if kill_signal == 0:
                raise ProcessLookupError
            proc.returncode = -9

        with patch("mediapipeline.core.processes.kill.os.name", "posix"), patch(
            "mediapipeline.core.processes.kill.os.getpgid",
            return_value=1234,
            create=True,
        ), patch(
            "mediapipeline.core.processes.kill.os.killpg",
            side_effect=successful_group_kill,
            create=True,
        ), patch(
            "mediapipeline.core.processes.kill.signal.SIGKILL",
            9,
            create=True,
        ):
            message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )

        self.assertEqual(message, "Force-killed pipeline process (PID 1234).")
        self.assertFalse(_process_tree_cleanup_reconciliation_required(proc))
        self.assertEqual(updates, [{"proc": proc, "status": "killed", "return_code": -9}])

    def test_non_windows_root_only_fallback_does_not_clear_tree_reconciliation(self) -> None:
        class FallbackExitPopen(FakePopen):
            def kill(self) -> None:
                self.returncode = -9

            def terminate(self) -> None:
                self.returncode = -15

        proc = FallbackExitPopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []
        _mark_process_tree_cleanup_reconciliation_required(proc)

        with patch("mediapipeline.core.processes.kill.os.name", "posix"), patch(
            "mediapipeline.core.processes.kill.os.getpgid",
            return_value=1234,
            create=True,
        ), patch(
            "mediapipeline.core.processes.kill.os.killpg",
            side_effect=ProcessLookupError,
            create=True,
        ), patch(
            "mediapipeline.core.processes.kill.signal.SIGKILL",
            9,
            create=True,
        ):
            message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )

        self.assertIn("process group exit could not be verified", message)
        self.assertTrue(_process_tree_cleanup_reconciliation_required(proc))
        self.assertEqual(updates, [{"proc": proc, "status": "kill_degraded", "return_code": -9}])

    def test_already_exited_root_does_not_clear_prior_tree_reconciliation(self) -> None:
        proc = FakePopen(pid=1234, returncode=-9)
        updates: list[dict[str, Any]] = []
        _mark_process_tree_cleanup_reconciliation_required(proc)

        message = kill_process_tree(
            proc,
            "pipeline",
            psutil_module=None,
            logger=logging.getLogger("test_service_process_kill"),
            update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
        )

        self.assertIn("descendant cleanup still requires reconciliation", message)
        self.assertTrue(_process_tree_cleanup_reconciliation_required(proc))
        self.assertEqual(updates, [])

    def test_non_windows_group_signal_does_not_prove_descendant_exit_while_group_remains(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []

        def group_kill_leaves_group_present(process_group_id: int, kill_signal: int) -> None:
            _ = process_group_id
            if kill_signal != 0:
                proc.returncode = -9

        with patch("mediapipeline.core.processes.kill.os.name", "posix"), patch(
            "mediapipeline.core.processes.kill.os.getpgid",
            return_value=1234,
            create=True,
        ), patch(
            "mediapipeline.core.processes.kill.os.killpg",
            side_effect=group_kill_leaves_group_present,
            create=True,
        ), patch(
            "mediapipeline.core.processes.kill.signal.SIGKILL",
            9,
            create=True,
        ):
            message = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
            )

        self.assertIn("process group exit could not be verified", message)
        self.assertTrue(_process_tree_cleanup_reconciliation_required(proc))
        self.assertEqual(updates, [{"proc": proc, "status": "kill_degraded", "return_code": -9}])

    def test_unexpected_windows_termination_error_marks_reconciliation_before_raising(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []

        with patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=OSError("taskkill unavailable"),
        ):
            with self.assertRaisesRegex(OSError, "taskkill unavailable"):
                kill_process_tree(
                    proc,
                    "pipeline",
                    psutil_module=None,
                    logger=logging.getLogger("test_service_process_kill"),
                    update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
                )

        self.assertTrue(_process_tree_cleanup_reconciliation_required(proc))
        self.assertEqual(updates, [{"proc": proc, "status": "kill_degraded", "return_code": None}])

    def test_unexpected_posix_termination_error_marks_reconciliation_before_raising(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        updates: list[dict[str, Any]] = []

        with patch("mediapipeline.core.processes.kill.os.name", "posix"), patch(
            "mediapipeline.core.processes.kill.os.getpgid",
            side_effect=PermissionError("group access denied"),
            create=True,
        ), patch(
            "mediapipeline.core.processes.kill.os.killpg",
            create=True,
        ):
            with self.assertRaisesRegex(PermissionError, "group access denied"):
                kill_process_tree(
                    proc,
                    "pipeline",
                    psutil_module=None,
                    logger=logging.getLogger("test_service_process_kill"),
                    update_active_job_record=lambda proc, **kwargs: updates.append({"proc": proc, **kwargs}),
                )

        self.assertTrue(_process_tree_cleanup_reconciliation_required(proc))
        self.assertEqual(updates, [{"proc": proc, "status": "kill_degraded", "return_code": None}])

    def test_concurrent_cleanup_callers_join_one_exact_process_attempt(self) -> None:
        proc = FakePopen(pid=1234, returncode=None)
        entered = threading.Event()
        release = threading.Event()
        calls = 0
        calls_lock = threading.Lock()
        first_results: list[str] = []

        def taskkill_result(*args, **kwargs):
            nonlocal calls
            _ = (args, kwargs)
            with calls_lock:
                calls += 1
            entered.set()
            self.assertTrue(release.wait(timeout=1.0))
            proc.returncode = -9
            return subprocess.CompletedProcess(["taskkill"], 0, stdout="SUCCESS", stderr="")

        def first_cleanup() -> None:
            first_results.append(
                kill_process_tree(
                    proc,
                    "pipeline",
                    psutil_module=None,
                    logger=logging.getLogger("test_service_process_kill"),
                    update_active_job_record=lambda proc, **kwargs: None,
                )
            )

        with patch("mediapipeline.core.processes.kill.os.name", "nt"), patch(
            "mediapipeline.core.processes.kill.subprocess.run",
            side_effect=taskkill_result,
        ):
            first_thread = threading.Thread(target=first_cleanup)
            first_thread.start()
            self.assertTrue(entered.wait(timeout=1.0))
            timer = threading.Timer(0.05, release.set)
            timer.start()
            second_result = kill_process_tree(
                proc,
                "pipeline",
                psutil_module=None,
                logger=logging.getLogger("test_service_process_kill"),
                update_active_job_record=lambda proc, **kwargs: None,
            )
            first_thread.join(timeout=1.0)
            timer.join(timeout=1.0)

        self.assertFalse(first_thread.is_alive())
        self.assertEqual(calls, 1)
        self.assertEqual(first_results, ["Force-killed pipeline process tree (PID 1234)."])
        self.assertEqual(second_result, first_results[0])

    def test_process_service_wrappers_route_to_extracted_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            matching = FakePsutilProc(
                pid=100,
                name="pwsh.exe",
                cmdline=["pwsh", "-File", str(resolved.rerun_script_path)],
            )
            FakePsutil.processes = [matching]
            service = DummyKillService()

            with patch("mediapipeline.core.processes.lifecycle.psutil", FakePsutil):
                matches = service.find_related_pipeline_processes(resolved)

        self.assertEqual(matches, [matching])


if __name__ == "__main__":
    unittest.main()
