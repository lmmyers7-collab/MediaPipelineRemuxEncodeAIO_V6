from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Test-PrivateBetaPublishedRelease.ps1"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for published release verification tests.")
    return shell


def _release_payload(*, prerelease: bool = True, include_signature: bool = True) -> dict[str, object]:
    installer = "MediaPipelineRemuxEncodeAIO_2026.6.4+001_x64-setup.exe"
    assets: list[dict[str, object]] = [
        {
            "name": installer,
            "browser_download_url": f"https://github.com/owner/repo/releases/download/app-v2026.6.4+001/{installer}",
            "size": 123456,
        },
        {
            "name": "latest-beta.json",
            "browser_download_url": "https://github.com/owner/repo/releases/download/app-v2026.6.4+001/latest-beta.json",
            "size": 512,
        },
        {
            "name": "SHA256SUMS.txt",
            "browser_download_url": "https://github.com/owner/repo/releases/download/app-v2026.6.4+001/SHA256SUMS.txt",
            "size": 256,
        },
    ]
    if include_signature:
        assets.append(
            {
                "name": f"{installer}.sig",
                "browser_download_url": f"https://github.com/owner/repo/releases/download/app-v2026.6.4+001/{installer}.sig",
                "size": 128,
            }
        )
    return {
        "tag_name": "app-v2026.6.4+001",
        "name": "MediaPipelineRemuxEncodeAIO 2026.6.4+001 (beta)",
        "body": "Signed NSIS beta release.",
        "draft": False,
        "prerelease": prerelease,
        "assets": assets,
    }


def _run_verifier(release_json: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
            "-ReleaseTag",
            "app-v2026.6.4+001",
            "-Version",
            "2026.6.4+001",
            "-ReleaseJsonPath",
            str(release_json),
            "-AsJson",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class PrivateBetaPublishedReleaseTests(unittest.TestCase):
    def test_published_release_verifier_accepts_required_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release_json = Path(temp_dir) / "release.json"
            release_json.write_text(json.dumps(_release_payload()), encoding="utf-8")
            result = _run_verifier(release_json)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "private_beta_published_release_verification.v1")
        self.assertIn("latest-beta.json", payload["asset_names"])
        self.assertTrue(any(check["name"] == "assets:no_msi" and check["ok"] for check in payload["checks"]))

    def test_published_release_verifier_rejects_missing_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release_json = Path(temp_dir) / "release.json"
            release_json.write_text(json.dumps(_release_payload(include_signature=False)), encoding="utf-8")
            result = _run_verifier(release_json)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertFalse(payload["ok"])
        self.assertIn("assets:updater_signature", failed_names)

    def test_published_release_verifier_rejects_beta_without_prerelease_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release_json = Path(temp_dir) / "release.json"
            release_json.write_text(json.dumps(_release_payload(prerelease=False)), encoding="utf-8")
            result = _run_verifier(release_json)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("release:beta_prerelease", failed_names)

    def test_script_does_not_mutate_github_release_assets(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("gh_release_by_tag", text)
        self.assertIn("repos/$Repository/releases/tags/$ReleaseTag", text)
        self.assertNotIn("release upload", text)
        self.assertNotIn("release create", text)


if __name__ == "__main__":
    unittest.main()
