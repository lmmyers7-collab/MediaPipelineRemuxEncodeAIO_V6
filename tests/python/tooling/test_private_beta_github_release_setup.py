from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Initialize-PrivateBetaGitHubReleaseSetup.ps1"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for GitHub release setup tests.")
    return shell


class PrivateBetaGitHubReleaseSetupTests(unittest.TestCase):
    def test_initializer_dry_run_plans_environment_and_secret_commands(self) -> None:
        result = subprocess.run(
            [
                _powershell(),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-Repository",
                "owner/repo",
                "-AsJson",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        planned = {command["name"]: command for command in payload["planned_commands"]}

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["apply"])
        self.assertEqual(payload["schema_version"], "private_beta_github_release_setup.v1")
        self.assertEqual(payload["environments"], ["beta-release", "stable-release"])
        self.assertIn("TAURI_SIGNING_PRIVATE_KEY", payload["required_secrets"])
        self.assertIn("TAURI_SIGNING_PRIVATE_KEY_PASSWORD", payload["optional_secrets"])
        self.assertIn("create_environment:beta-release", planned)
        self.assertIn("create_environment:stable-release", planned)
        self.assertIn("list_environment_secrets:beta-release", planned)
        self.assertIn("set_secret_hint:beta-release:TAURI_SIGNING_PRIVATE_KEY", planned)
        self.assertTrue(planned["create_environment:beta-release"]["would_mutate"])
        self.assertFalse(planned["list_environment_secrets:beta-release"]["would_mutate"])
        self.assertEqual(payload["commands"], [])

    def test_initializer_static_contract_mentions_required_surfaces(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("beta-release", text)
        self.assertIn("stable-release", text)
        self.assertIn("TAURI_SIGNING_PRIVATE_KEY", text)
        self.assertIn("TAURI_UPDATER_PUBLIC_KEY", text)
        self.assertIn("WINDOWS_CERTIFICATE_BASE64", text)
        self.assertIn("WINDOWS_CERTIFICATE_PASSWORD", text)
        self.assertIn("TAURI_SIGNING_PRIVATE_KEY_PASSWORD", text)
        self.assertIn("'api', '--method', 'PUT'", text)
        self.assertIn("'secret', 'list'", text)
        self.assertIn("'secret', 'set'", text)
        self.assertIn("-not $Apply", text)


if __name__ == "__main__":
    unittest.main()
