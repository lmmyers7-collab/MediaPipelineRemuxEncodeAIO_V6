from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from mediapipeline.tools.dev.release_package_scope import release_package_omits_path
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Test-PrivateBetaWorkflowDryRun.ps1"
GITHUB_WORKFLOWS_OMITTED = release_package_omits_path(REPO_ROOT, ".github/workflows")


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for workflow dry-run tests.")
    return shell


class PrivateBetaWorkflowDryRunTests(unittest.TestCase):
    @unittest.skipIf(
        GITHUB_WORKFLOWS_OMITTED,
        "GitHub workflow metadata is intentionally omitted from release packages.",
    )
    def test_workflow_dry_run_exercises_preflight_without_secret_leakage(self) -> None:
        result = subprocess.run(
            [
                _powershell(),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-Channel",
                "beta",
                "-Repository",
                "owner/repo",
                "-Version",
                "2026.6.4+001",
                "-ReleaseTag",
                "app-v2026.6.4+001",
                "-SkipPythonTests",
                "-SkipTauriCheck",
                "-AsJson",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        command_names = {command["name"] for command in payload["commands"]}
        check_names = {check["name"] for check in payload["checks"]}

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "private_beta_workflow_dry_run.v1")
        self.assertIn("private_beta_preflight", command_names)
        self.assertIn("python_tests:skipped", check_names)
        self.assertIn("tauri_check:skipped", check_names)
        self.assertIn("TAURI_SIGNING_PRIVATE_KEY", payload["used_placeholder_secrets"])
        self.assertNotIn("local-dry-run-placeholder-private-updater-key", result.stdout)
        self.assertNotIn("local-dry-run-placeholder-certificate-password", result.stdout)

    def test_workflow_dry_run_static_command_scope(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Test-PrivateBetaReleasePreflight.ps1", text)
        self.assertIn("test_private_beta_release_artifact.py", text)
        self.assertIn("test_private_beta_release_preflight.py", text)
        self.assertIn("test_productization_support.py", text)
        self.assertIn("test_tauri_shell_scaffold.py", text)
        self.assertIn("npm", text)
        self.assertIn("run", text)
        self.assertIn("check", text)


if __name__ == "__main__":
    unittest.main()
