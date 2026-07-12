from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Test-PrivateBetaReleasePreflight.ps1"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for release preflight tests.")
    return shell


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GITHUB_REPOSITORY": "owner/repo",
            "MEDIAPIPELINE_RELEASE_CHANNEL": "beta",
            "MEDIAPIPELINE_SEMVER_VERSION": "2026.6.4+001",
            "TAURI_SIGNING_PRIVATE_KEY": "fake-private-updater-key",
            "TAURI_SIGNING_PRIVATE_KEY_PASSWORD": "fake-private-updater-key-password",
            "TAURI_UPDATER_PUBLIC_KEY": "fake-public-updater-key",
            "WINDOWS_CERTIFICATE_BASE64": "ZmFrZS1jZXJ0aWZpY2F0ZQ==",
            "WINDOWS_CERTIFICATE_PASSWORD": "fake-certificate-password",
            "WINDOWS_CERTIFICATE_THUMBPRINT": "0123456789ABCDEF0123456789ABCDEF01234567",
        }
    )
    return env


def _run_preflight(env: dict[str, str], config_path: Path) -> subprocess.CompletedProcess[str]:
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
            "-Version",
            "2026.6.4+001",
            "-ReleaseTag",
            "app-v2026.6.4+001",
            "-ConfigOutputPath",
            str(config_path),
            "-AsJson",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class PrivateBetaReleasePreflightTests(unittest.TestCase):
    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Private-beta GitHub workflow metadata is intentionally omitted from release packages.",
    )
    def test_preflight_passes_with_required_release_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "tauri.beta.preflight.conf.json"
            result = _run_preflight(_base_env(), config_path)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            generated = json.loads(config_path.read_text(encoding="utf-8-sig"))

        self.assertEqual(payload["schema_version"], "private_beta_release_preflight.v1")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["channel"], "beta")
        self.assertEqual(payload["generated_config"]["updater_endpoint"], "https://github.com/owner/repo/releases/latest/download/latest-beta.json")
        self.assertTrue(payload["generated_config"]["create_updater_artifacts"])
        self.assertTrue(payload["generated_config"]["nsis_only"])
        self.assertEqual(generated["bundle"]["targets"], ["nsis"])
        self.assertTrue(generated["bundle"]["createUpdaterArtifacts"])
        self.assertEqual(generated["plugins"]["updater"]["windows"]["installMode"], "passive")
        self.assertNotIn("fake-private-updater-key", result.stdout)
        self.assertNotIn("fake-certificate-password", result.stdout)

    def test_preflight_fails_without_required_release_secrets(self) -> None:
        env = _base_env()
        env.pop("TAURI_SIGNING_PRIVATE_KEY", None)
        env.pop("WINDOWS_CERTIFICATE_BASE64", None)
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "tauri.beta.preflight.conf.json"
            result = _run_preflight(env, config_path)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}

        self.assertFalse(payload["ok"])
        self.assertIn("secret:TAURI_SIGNING_PRIVATE_KEY", failed_names)
        self.assertIn("secret:WINDOWS_CERTIFICATE_BASE64", failed_names)
        self.assertNotIn("fake-public-updater-key", result.stdout)
        self.assertNotIn("fake-certificate-password", result.stdout)


if __name__ == "__main__":
    unittest.main()
