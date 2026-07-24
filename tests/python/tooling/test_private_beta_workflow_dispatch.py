from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Invoke-PrivateBetaWorkflowDispatch.ps1"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for workflow dispatch tests.")
    return shell


class PrivateBetaWorkflowDispatchTests(unittest.TestCase):
    def test_dispatch_dry_run_builds_safe_default_gh_command(self) -> None:
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
                "-Ref",
                "main",
                "-DryRun",
                "-AsJson",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        args = payload["gh_args"]

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["publish_release"])
        self.assertEqual(payload["schema_version"], "private_beta_workflow_dispatch.v1")
        self.assertEqual(args[:3], ["workflow", "run", "private-beta-windows.yml"])
        self.assertIn("channel=beta", args)
        self.assertIn("version=2026.6.4+001", args)
        self.assertIn("release_tag=app-v2026.6.4+001", args)
        self.assertIn("publish_release=false", args)
        self.assertIn("allow_same_commit_rebuild=false", args)
        self.assertEqual(payload["commands"], [])

    def test_dispatch_dry_run_requires_explicit_publish_switch(self) -> None:
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
                "-PublishRelease",
                "-DryRun",
                "-AsJson",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)

        self.assertTrue(payload["publish_release"])
        self.assertIn("publish_release=true", payload["gh_args"])

    def test_dispatch_rejects_mismatched_version_and_tag(self) -> None:
        result = subprocess.run(
            [
                _powershell(),
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(SCRIPT),
                "-Repository",
                "owner/repo",
                "-Version",
                "2026.6.4+001",
                "-ReleaseTag",
                "app-v2026.6.5+001",
                "-DryRun",
                "-AsJson",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("release_tag:version_identity", failed)

    def test_dispatch_forwards_explicit_same_commit_rebuild_request(self) -> None:
        result = subprocess.run(
            [
                _powershell(),
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(SCRIPT),
                "-Repository",
                "owner/repo",
                "-Version",
                "2026.6.4+001",
                "-PublishRelease",
                "-AllowSameCommitRebuild",
                "-DryRun",
                "-AsJson",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["allow_same_commit_rebuild"])
        self.assertIn("allow_same_commit_rebuild=true", payload["gh_args"])

    def test_dispatch_script_invokes_setup_preflight_before_real_dispatch(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Test-PrivateBetaGitHubSetup.ps1", text)
        self.assertIn("setup_preflight:passed", text)
        self.assertIn("gh_workflow_dispatch", text)
        self.assertIn("gh_run_list_latest", text)
        self.assertIn("publish_release=false", text)
        self.assertIn("allow_same_commit_rebuild={0}", text)


if __name__ == "__main__":
    unittest.main()
