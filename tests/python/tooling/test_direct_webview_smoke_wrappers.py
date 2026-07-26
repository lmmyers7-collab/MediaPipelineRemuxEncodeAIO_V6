from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


PROJECT_ROOT = find_repo_root(Path(__file__))
WRAPPERS = (
    "Test-WebViewCommandEvidenceSmoke.ps1",
    "Test-WebViewRenameReadinessSmoke.ps1",
    "Test-WebViewRowDetailSmoke.ps1",
    "Test-WebViewScheduleSmoke.ps1",
)


class DirectWebViewSmokeWrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bundled = PROJECT_ROOT / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
        cls.powershell = str(bundled) if bundled.is_file() else shutil.which("pwsh") or shutil.which("powershell")
        if not cls.powershell:
            raise unittest.SkipTest("PowerShell is required for direct WebView smoke wrapper tests.")

    def _run_wrapper(self, name: str, *, hide_node: bool) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        environment = os.environ.copy()
        if hide_node:
            system_root = Path(environment.get("SystemRoot", r"C:\Windows"))
            environment["PATH"] = str(system_root / "System32") if os.name == "nt" else ""
        result = subprocess.run(
            [
                self.powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(PROJECT_ROOT / "ops" / "scripts" / "smoke" / name),
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        payloads: list[dict[str, object]] = []
        for line in result.stdout.splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("kind") == "webview_smoke":
                payloads.append(payload)
        self.assertEqual(len(payloads), 1, result.stdout + result.stderr)
        return result, payloads[0]

    def test_wrappers_reject_missing_node_with_structured_results(self) -> None:
        for name in WRAPPERS:
            with self.subTest(wrapper=name):
                result, payload = self._run_wrapper(name, hide_node=True)

                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(payload["outcome"], "skipped_disallowed")
                self.assertEqual(payload["wrapper_exit_code"], 1)
                self.assertEqual(payload["test_exit_code"], 0)
                self.assertGreater(int(payload["tests_run"]), 0)
                self.assertGreater(int(payload["skipped_count"]), 0)
                self.assertLessEqual(int(payload["skipped_count"]), int(payload["tests_run"]))
                self.assertIn("node", payload["missing_prerequisites"])
                self.assertNotIn("browser", payload["prerequisites"])

    def test_wrappers_execute_tests_with_zero_skips_in_normal_environment(self) -> None:
        for name in WRAPPERS:
            with self.subTest(wrapper=name):
                result, payload = self._run_wrapper(name, hide_node=False)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(payload["outcome"], "passed")
                self.assertGreater(int(payload["tests_run"]), 0)
                self.assertEqual(payload["skipped_count"], 0)
                self.assertTrue(payload["prerequisites"]["node"]["available"])


if __name__ == "__main__":
    unittest.main()
