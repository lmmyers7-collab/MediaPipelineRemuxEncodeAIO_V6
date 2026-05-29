from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.processes.readiness import verify_spawn_readiness


class FakeReadinessProc:
    def __init__(self, returncode: int | None) -> None:
        self.returncode = returncode

    def poll(self) -> int | None:
        return self.returncode


class ProcessReadinessHelperTests(unittest.TestCase):
    def _verify(self, proc: FakeReadinessProc, *, stdout_tail: str = "", stderr_tail: str = "") -> list[dict[str, Any]]:
        updates: list[dict[str, Any]] = []

        def update(_proc: Any, **kwargs: Any) -> None:
            updates.append({"proc": _proc, **kwargs})

        verify_spawn_readiness(
            proc,
            "pwsh -File pipeline.ps1",
            ready_check_seconds=0,
            update_active_job_record=update,
            launch_log_summary=lambda: "stdout: a.log | stderr: b.log",
            spawn_log_tail=lambda path: stderr_tail if str(path).endswith("stderr.log") else stdout_tail,
            stdout_log=Path("stdout.log"),
            stderr_log=Path("stderr.log"),
            logger=logging.getLogger("test_service_process_readiness"),
        )
        return updates

    def test_running_process_marks_active(self) -> None:
        proc = FakeReadinessProc(None)

        updates = self._verify(proc)

        self.assertEqual(updates, [{"proc": proc, "status": "active", "return_code": None}])

    def test_immediate_zero_exit_marks_completed_without_raising(self) -> None:
        proc = FakeReadinessProc(0)

        updates = self._verify(proc)

        self.assertEqual(updates, [{"proc": proc, "status": "completed_immediate", "return_code": 0}])

    def test_immediate_nonzero_exit_marks_failed_and_includes_log_tails(self) -> None:
        proc = FakeReadinessProc(7)
        updates: list[dict[str, Any]] = []

        with self.assertRaisesRegex(RuntimeError, "stderr tail") as raised:
            verify_spawn_readiness(
                proc,
                "pwsh -File pipeline.ps1",
                ready_check_seconds=0,
                update_active_job_record=lambda _proc, **kwargs: updates.append({"proc": _proc, **kwargs}),
                launch_log_summary=lambda: "stdout: a.log | stderr: b.log",
                spawn_log_tail=lambda path: "bad stderr" if str(path).endswith("stderr.log") else "some stdout",
                stdout_log=Path("stdout.log"),
                stderr_log=Path("stderr.log"),
                logger=logging.getLogger("test_service_process_readiness"),
            )

        self.assertIn("bad stderr", str(raised.exception))
        self.assertIn("some stdout", str(raised.exception))
        self.assertEqual(updates, [{"proc": proc, "status": "failed_immediate", "return_code": 7}])


if __name__ == "__main__":
    unittest.main()
