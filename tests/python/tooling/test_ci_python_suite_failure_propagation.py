from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


ROOT = find_repo_root(Path(__file__))
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "deep-audit.yml",
    ROOT / ".github" / "workflows" / "phase1-drift.yml",
)
FIRST_COMMAND = "python -m unittest discover -s tests/python -q"
SECOND_COMMAND = "python -m unittest @nonBrowserModules -q"
FIRST_CAPTURE = "$pythonTestsExitCode = $LASTEXITCODE"
SECOND_CAPTURE = "$nonBrowserExitCode = $LASTEXITCODE"
FAIL_CONDITION = (
    "if (($pythonTestsExitCode -ne 0) -or "
    "($nonBrowserExitCode -ne 0)) { exit 1 }"
)


def _python_step(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index("      - name: Run Python and non-browser WebView tests")
    end = text.index("\n  browser-tests:", start)
    return text[start:end]


class CiPythonSuiteFailurePropagationTests(unittest.TestCase):
    def test_each_native_exit_is_captured_before_another_process_can_overwrite_it(self) -> None:
        for path in WORKFLOWS:
            with self.subTest(workflow=path.name):
                step = _python_step(path)
                positions = [
                    step.index(FIRST_COMMAND),
                    step.index(FIRST_CAPTURE),
                    step.index(SECOND_COMMAND),
                    step.index(SECOND_CAPTURE),
                    step.index(FAIL_CONDITION),
                ]
                self.assertEqual(positions, sorted(positions))
                self.assertNotIn("if ($LASTEXITCODE -ne 0)", step)

    def test_aggregate_condition_fails_for_either_native_suite(self) -> None:
        pwsh = shutil.which("pwsh") or shutil.which("pwsh.exe")
        if not pwsh:
            self.skipTest("PowerShell 7 is unavailable")
        condition = re.search(r"if \(\(\$pythonTestsExitCode.*?\{ exit 1 \}", _python_step(WORKFLOWS[0]))
        self.assertIsNotNone(condition)
        for first, second, expected in ((1, 0, 1), (0, 1, 1), (0, 0, 0)):
            with self.subTest(first=first, second=second):
                script = (
                    f"$pythonTestsExitCode={first}; "
                    f"$nonBrowserExitCode={second}; {condition.group(0)}"
                )
                completed = subprocess.run(
                    [pwsh, "-NoProfile", "-Command", script],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, expected, completed.stderr)


if __name__ == "__main__":
    unittest.main()
