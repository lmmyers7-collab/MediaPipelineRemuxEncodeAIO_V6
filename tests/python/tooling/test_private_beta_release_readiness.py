from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Test-PrivateBetaReleaseReadiness.ps1"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for release readiness tests.")
    return shell


class PrivateBetaReleaseReadinessTests(unittest.TestCase):
    def test_release_readiness_runs_local_static_gates_without_live_github(self) -> None:
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
        phase_names = {phase["name"] for phase in payload["phases"]}
        check_names = {check["name"] for check in payload["checks"]}

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "private_beta_release_readiness.v1")
        self.assertEqual(phase_names, {"workflow_dry_run", "github_setup_static", "workflow_dispatch_dry_run"})
        self.assertIn("readiness:read_only", check_names)
        self.assertNotIn("local-dry-run-placeholder-private-updater-key", result.stdout)
        self.assertNotIn("local-dry-run-placeholder-certificate-password", result.stdout)

    def test_release_readiness_script_uses_only_dry_run_static_child_modes(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Test-PrivateBetaWorkflowDryRun.ps1", text)
        self.assertIn("Test-PrivateBetaGitHubSetup.ps1", text)
        self.assertIn("Invoke-PrivateBetaWorkflowDispatch.ps1", text)
        self.assertIn("-StaticOnly", text)
        self.assertIn("-DryRun", text)
        self.assertNotIn("-PublishRelease", text)
        self.assertNotIn("gh release upload", text)
        self.assertNotIn("gh workflow run", text)


if __name__ == "__main__":
    unittest.main()
