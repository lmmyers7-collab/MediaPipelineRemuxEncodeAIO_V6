from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Test-PrivateBetaGitHubSetup.ps1"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for GitHub setup preflight tests.")
    return shell


def _repository_for_static_preflight() -> str:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return "owner/repo"
    remote_url = result.stdout.strip()
    match = re.search(r"github\.com[:/](?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?$", remote_url)
    if not match:
        return "owner/repo"
    return f"{match.group('owner')}/{match.group('repo')}"


class PrivateBetaGitHubSetupTests(unittest.TestCase):
    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Private-beta GitHub workflow metadata is intentionally omitted from release packages.",
    )
    def test_static_setup_preflight_validates_workflow_without_github_account(self) -> None:
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
                _repository_for_static_preflight(),
                "-StaticOnly",
                "-AsJson",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        checks = {check["name"]: check for check in payload["checks"]}

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "private_beta_github_setup_preflight.v1")
        self.assertTrue(payload["static_only"])
        self.assertTrue(checks["workflow:dispatch"]["ok"])
        self.assertTrue(checks["workflow:preflight"]["ok"])
        self.assertTrue(checks["workflow:artifact_verifier"]["ok"])
        self.assertTrue(checks["gh:static_only"]["ok"])

    def test_setup_preflight_static_contract_mentions_required_release_surfaces(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("beta-release", text)
        self.assertIn("stable-release", text)
        self.assertIn("private-beta-windows.yml", text)
        self.assertIn("TAURI_SIGNING_PRIVATE_KEY", text)
        self.assertIn("TAURI_UPDATER_PUBLIC_KEY", text)
        self.assertIn("WINDOWS_CERTIFICATE_BASE64", text)
        self.assertIn("WINDOWS_CERTIFICATE_PASSWORD", text)
        self.assertIn("Test-PrivateBetaReleasePreflight", text)
        self.assertIn("Test-PrivateBetaReleaseArtifact", text)


if __name__ == "__main__":
    unittest.main()
