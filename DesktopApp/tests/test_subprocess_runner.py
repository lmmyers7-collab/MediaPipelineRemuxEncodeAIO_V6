from __future__ import annotations

import sys
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.subprocess_runner import run_capture


class SubprocessRunnerTests(unittest.TestCase):
    def test_run_capture_returns_stdout_and_exit_code(self) -> None:
        result = run_capture(
            [sys.executable, "-c", "print('ok')"],
            timeout_seconds=5,
            hidden=True,
            label="unit test",
        )

        self.assertFalse(result.timed_out)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_run_capture_marks_timeout_and_kills_process(self) -> None:
        result = run_capture(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout_seconds=0.2,
            hidden=True,
            label="timeout unit test",
        )

        self.assertTrue(result.timed_out)
        self.assertIn("kill", result.kill_message.lower())

    def test_run_capture_falls_back_to_direct_kill_when_tree_cleanup_fails(self) -> None:
        class FakeTimedOutProcess:
            returncode: int | None = None

            def __init__(self) -> None:
                self.kill_calls = 0

            def communicate(self, timeout: float | None = None):
                if self.returncode is None:
                    raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
                return "", ""

            def poll(self) -> int | None:
                return self.returncode

            def kill(self) -> None:
                self.kill_calls += 1
                self.returncode = -9

            def terminate(self) -> None:
                self.returncode = -15

        fake_proc = FakeTimedOutProcess()

        def failing_kill_tree(_proc, _label: str) -> str:
            raise RuntimeError("tree cleanup failed")

        with patch("mediapipeline_desktop_app.subprocess_runner.subprocess.Popen", lambda *_args, **_kwargs: fake_proc):
            result = run_capture(
                ["fake"],
                timeout_seconds=0.1,
                label="timeout unit test",
                kill_tree=failing_kill_tree,
            )

        self.assertTrue(result.timed_out)
        self.assertEqual(result.returncode, -9)
        self.assertEqual(fake_proc.kill_calls, 1)
        self.assertIn("process tree kill failed", result.kill_message)
        self.assertIn("process killed", result.kill_message)


if __name__ == "__main__":
    unittest.main()
