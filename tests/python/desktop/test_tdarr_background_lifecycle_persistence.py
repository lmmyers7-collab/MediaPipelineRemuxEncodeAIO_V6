from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.core.diagnostics.tdarr_matrix_audit import TdarrMatrixAuditServiceMixin
from mediapipeline.core.processes.tdarr_background import tdarr_matrix_background_close_evidence


class _FakeProcess:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self.returncode: int | None = None
        self.terminate_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = -15

    def wait(self, timeout: float | None = None) -> int:
        return 0 if self.returncode is None else self.returncode


class _Harness(TdarrMatrixAuditServiceMixin):
    def __init__(self) -> None:
        self.cleanup_calls: list[tuple[int, str]] = []

    def _tdarr_matrix_subprocess_kwargs(self) -> dict[str, object]:
        return {}

    def kill_process_tree(self, proc: _FakeProcess, label: str) -> str:
        self.cleanup_calls.append((proc.pid, label))
        proc.terminate()
        proc.wait(timeout=5)
        return f"Terminated {label} PID {proc.pid}."


def _launch(harness: _Harness, root: Path) -> dict[str, object]:
    runs_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrProofPack" / "runs"
    return harness._run_tdarr_matrix_audit_background(
        args=["fake-child"],
        command_line="fake-child",
        workspace_root=root,
        env={},
        preset={},
        library_root=root / "library",
        runs_root=runs_root,
        run_id="run-lifecycle-test",
        started=time.monotonic(),
    )


class TdarrBackgroundLifecyclePersistenceTests(unittest.TestCase):
    def test_reservation_failure_prevents_child_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            harness = _Harness()
            proc = _FakeProcess()
            with (
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.os.replace", side_effect=OSError("disk full")),
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.subprocess.Popen", return_value=proc) as popen,
            ):
                result = _launch(harness, root)

        self.assertFalse(result["success"])
        self.assertFalse(result["background_started"])
        self.assertFalse(result["partial_start"])
        popen.assert_not_called()

    def test_post_spawn_identity_failure_returns_failure_and_leaves_close_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            harness = _Harness()
            proc = _FakeProcess()
            replace_calls = 0
            real_replace = os.replace

            def fail_second_replace(source: str | bytes, destination: str | bytes) -> None:
                nonlocal replace_calls
                replace_calls += 1
                if replace_calls == 2:
                    raise OSError("forced active identity failure")
                real_replace(source, destination)

            with (
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.os.replace", side_effect=fail_second_replace),
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.subprocess.Popen", return_value=proc),
            ):
                result = _launch(harness, root)

            metadata_path = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrProofPack" / "runs" / "_background" / "run-lifecycle-test.process.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            close_evidence = tdarr_matrix_background_close_evidence(root)

        self.assertFalse(result["success"])
        self.assertFalse(result["background_started"])
        self.assertTrue(result["partial_start"])
        self.assertTrue(result["reconciliation_required"])
        self.assertEqual(metadata["lifecycle_status"], "launch_reserved")
        self.assertEqual(metadata["pid"], 0)
        self.assertEqual(harness.cleanup_calls, [(4242, "Tdarr Matrix background audit")])
        self.assertEqual(proc.terminate_calls, 1)
        self.assertEqual(close_evidence["status"], "unavailable")
        self.assertTrue(close_evidence["active_work"])

    def test_reused_pid_with_different_start_identity_is_not_active(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            metadata_root = root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrProofPack" / "runs" / "_background"
            metadata_root.mkdir(parents=True)
            (metadata_root / "run-stale.process.json").write_text(
                json.dumps(
                    {
                        "schema_version": "tdarr_matrix_background_process.v1",
                        "run_id": "run-stale",
                        "pid": 4242,
                        "process_start_time": "2026-01-01T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )

            class FakeProcess:
                is_running = staticmethod(lambda: True)
                status = staticmethod(lambda: "running")
                create_time = staticmethod(lambda: 1.0)

            class FakePsutil:
                STATUS_ZOMBIE = "zombie"
                NoSuchProcess = ProcessLookupError
                Process = staticmethod(lambda _pid: FakeProcess())

            evidence = tdarr_matrix_background_close_evidence(root, psutil_module=FakePsutil)

        self.assertEqual(evidence["status"], "inactive")
        self.assertFalse(evidence["active_work"])


if __name__ == "__main__":
    unittest.main()
