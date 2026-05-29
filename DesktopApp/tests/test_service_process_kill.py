from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from app.processes.kill import (
    find_related_pipeline_processes,
    kill_process_tree,
    kill_related_pipeline_processes,
    process_text_contains_any,
    wait_for_process_exit,
)
from app.processes.lifecycle import ProcessLifecycleServiceMixin


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
            pipeline_path=root / "Pipeline" / "MediaPipeline_chatgpt.ps1",
            config_path=root / "Pipeline" / "MediaPipeline_config_chatgpt.psd1",
            audit_script_path=root / "Pipeline" / "Audit-MediaLibrary_chatgpt.ps1",
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
            cmdline=[r"C:\Tools\pwsh.exe", "-File", r"C:\Bundle\Pipeline\MediaPipeline_chatgpt.ps1"],
        )

        self.assertTrue(process_text_contains_any(proc, [r"c:\bundle\pipeline\mediapipeline_chatgpt.ps1"]))
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

            with patch("app.processes.lifecycle.psutil", FakePsutil):
                matches = service.find_related_pipeline_processes(resolved)

        self.assertEqual(matches, [matching])


if __name__ == "__main__":
    unittest.main()
