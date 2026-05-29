from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.processes.logs import launch_log_summary, launch_log_tail_summary, spawn_log_tail
from app.processes.lifecycle import ProcessLifecycleServiceMixin


class DummyProcessLogService(ProcessLifecycleServiceMixin):
    def __init__(self, stdout_log: Path | None, stderr_log: Path | None) -> None:
        self._last_spawn_stdout_log = stdout_log
        self._last_spawn_stderr_log = stderr_log


class ProcessLogHelperTests(unittest.TestCase):
    def test_spawn_log_tail_returns_recent_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "stderr.log"
            path.write_text("one\ntwo\nthree\n", encoding="utf-8")

            self.assertEqual(spawn_log_tail(path, line_count=2), "two\nthree")

    def test_launch_log_summary_and_tail_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            stdout = Path(td) / "stdout.log"
            stderr = Path(td) / "stderr.log"
            stdout.write_text("out1\nout2\n", encoding="utf-8")
            stderr.write_text("err1\nerr2\nerr3\n", encoding="utf-8")

            self.assertEqual(launch_log_summary(stdout, stderr), f"stdout: {stdout} | stderr: {stderr}")
            self.assertEqual(
                launch_log_tail_summary(stdout, stderr, line_count=2),
                "stderr tail:\nerr2\nerr3\n\nstdout tail:\nout1\nout2",
            )

    def test_service_wrappers_match_extracted_log_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            stdout = Path(td) / "stdout.log"
            stdout.write_text("out\n", encoding="utf-8")
            service = DummyProcessLogService(stdout, None)

            self.assertEqual(service._spawn_log_tail(stdout), spawn_log_tail(stdout))
            self.assertEqual(service.launch_log_summary(), launch_log_summary(stdout, None))
            self.assertEqual(service.launch_log_tail_summary(), launch_log_tail_summary(stdout, None))


if __name__ == "__main__":
    unittest.main()
