from __future__ import annotations

import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
