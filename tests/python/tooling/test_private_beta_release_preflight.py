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
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "private-beta-windows.yml"

REQUIRED_RESOURCES = (
    "pyproject.toml",
    "apps/desktop/webview/static/index.html",
    "apps/desktop/runtime/Python/python.exe",
    "src/mediapipeline/desktop/local_api_main.py",
    "ops/pipeline/entrypoints/MediaPipeline.ps1",
    "ops/pipeline/runtime/PowerShell-7.6.0-win-x64/pwsh.exe",
    "ops/pipeline/tools/ffmpeg/bin/ffmpeg.exe",
    "ops/pipeline/tools/ffmpeg/bin/ffprobe.exe",
    "ops/pipeline/tools/MKVToolNix/mkvmerge.exe",
    "ops/pipeline/tools/PgsToSrt/PgsToSrt.exe",
)


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


def _write_resource_fixture(root: Path) -> Path:
    resource_root = root / "sanitized-release"
    for relative in REQUIRED_RESOURCES:
        path = resource_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"fixture:{relative}".encode())
    for relative in ("ops/scripts/dev/setup.bat", "ops/release/metadata/VERSION"):
        path = resource_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture:{relative}", encoding="utf-8")
    (resource_root / "release_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "mediapipeline_release_manifest.v1",
                "integrity": {
                    "algorithm": "sha256",
                    "files": [{"path": relative} for relative in REQUIRED_RESOURCES],
                },
            }
        ),
        encoding="utf-8",
    )
    return resource_root


def _run_preflight(
    env: dict[str, str],
    config_path: Path,
    resource_root: Path,
    *,
    release_tag: str = "app-v2026.6.4+001",
    skip_secret_presence: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = [
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
            release_tag,
            "-ConfigOutputPath",
            str(config_path),
            "-ResourceRoot",
            str(resource_root),
            "-AsJson",
        ]
    if skip_secret_presence:
        args.append("-SkipSecretPresence")
    return subprocess.run(
        args,
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
            temp_root = Path(temp_dir)
            config_path = temp_root / "tauri.beta.preflight.conf.json"
            resource_root = _write_resource_fixture(temp_root)
            result = _run_preflight(_base_env(), config_path, resource_root)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            generated = json.loads(config_path.read_text(encoding="utf-8-sig"))

        self.assertEqual(payload["schema_version"], "private_beta_release_preflight.v1")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["channel"], "beta")
        self.assertEqual(
            payload["generated_config"]["updater_endpoint"],
            "https://github.com/owner/repo/releases/download/updater-beta/latest-beta.json",
        )
        self.assertTrue(payload["generated_config"]["create_updater_artifacts"])
        self.assertTrue(payload["generated_config"]["nsis_only"])
        self.assertEqual(generated["bundle"]["targets"], ["nsis"])
        self.assertTrue(generated["bundle"]["createUpdaterArtifacts"])
        expected_resources = {
            str(resource_root / "release_manifest.json"): "release_manifest.json",
            str(resource_root / "pyproject.toml"): "pyproject.toml",
            f"{resource_root / 'apps/desktop/webview'}\\": "apps/desktop/webview/",
            f"{resource_root / 'apps/desktop/runtime'}\\": "apps/desktop/runtime/",
            f"{resource_root / 'src/mediapipeline'}\\": "src/mediapipeline/",
            f"{resource_root / 'ops/pipeline'}\\": "ops/pipeline/",
            f"{resource_root / 'ops/scripts'}\\": "ops/scripts/",
            f"{resource_root / 'ops/release/metadata'}\\": "ops/release/metadata/",
        }
        self.assertEqual(generated["bundle"]["resources"], expected_resources)
        self.assertEqual(payload["generated_config"]["resource_map_count"], 8)
        self.assertEqual(generated["plugins"]["updater"]["windows"]["installMode"], "passive")
        self.assertNotIn("fake-private-updater-key", result.stdout)
        self.assertNotIn("fake-certificate-password", result.stdout)

    def test_preflight_fails_without_required_release_secrets(self) -> None:
        env = _base_env()
        env.pop("TAURI_SIGNING_PRIVATE_KEY", None)
        env.pop("WINDOWS_CERTIFICATE_BASE64", None)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config_path = temp_root / "tauri.beta.preflight.conf.json"
            resource_root = _write_resource_fixture(temp_root)
            result = _run_preflight(env, config_path, resource_root)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}

        self.assertFalse(payload["ok"])
        self.assertIn("secret:TAURI_SIGNING_PRIVATE_KEY", failed_names)
        self.assertIn("secret:WINDOWS_CERTIFICATE_BASE64", failed_names)
        self.assertNotIn("fake-public-updater-key", result.stdout)
        self.assertNotIn("fake-certificate-password", result.stdout)

    def test_preflight_rejects_mismatched_version_and_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config_path = temp_root / "tauri.beta.preflight.conf.json"
            resource_root = _write_resource_fixture(temp_root)
            result = _run_preflight(
                _base_env(),
                config_path,
                resource_root,
                release_tag="app-v2026.6.5+001",
            )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("release_tag:version_identity", failed_names)

    @unittest.skipUnless(
        WORKFLOW.is_file(),
        "Private-beta GitHub workflow metadata is intentionally omitted from release packages.",
    )
    def test_preflight_can_defer_private_secret_presence_to_consuming_step(self) -> None:
        env = _base_env()
        for name in (
            "TAURI_SIGNING_PRIVATE_KEY",
            "TAURI_SIGNING_PRIVATE_KEY_PASSWORD",
            "WINDOWS_CERTIFICATE_BASE64",
            "WINDOWS_CERTIFICATE_PASSWORD",
        ):
            env.pop(name, None)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config_path = temp_root / "tauri.beta.preflight.conf.json"
            resource_root = _write_resource_fixture(temp_root)
            result = _run_preflight(
                env,
                config_path,
                resource_root,
                skip_secret_presence=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        checks = {check["name"]: check for check in payload["checks"]}
        self.assertTrue(checks["secret_scope:deferred_to_consuming_step"]["ok"])
        self.assertNotIn("secret:TAURI_SIGNING_PRIVATE_KEY", checks)

    def test_preflight_rejects_incomplete_resource_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config_path = temp_root / "tauri.beta.preflight.conf.json"
            resource_root = _write_resource_fixture(temp_root)
            (resource_root / "apps/desktop/webview/static/index.html").unlink()
            result = _run_preflight(_base_env(), config_path, resource_root)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("generated_config:writable", failed_names)

    def test_preflight_rejects_mutable_or_personal_resource_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config_path = temp_root / "tauri.beta.preflight.conf.json"
            resource_root = _write_resource_fixture(temp_root)
            personal_config = resource_root / "ops/pipeline/config/MediaPipeline_config.psd1"
            personal_config.parent.mkdir(parents=True)
            personal_config.write_text("@{}", encoding="utf-8")
            result = _run_preflight(_base_env(), config_path, resource_root)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("generated_config:writable", failed_names)

    @unittest.skipUnless(
        WORKFLOW.is_file(),
        "Private-beta GitHub workflow metadata is intentionally omitted from release packages.",
    )
    def test_workflow_stages_and_verifies_installer_resources_in_order(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertLess(text.index("Full release self-test"), text.index("Stage sanitized installer resources"))
        self.assertLess(
            text.index("Stage sanitized installer resources"),
            text.index("Create SHA-256-bound nonsecret validation handoff"),
        )
        self.assertLess(
            text.index("Verify validation handoff before secret access"),
            text.index("Build signed NSIS updater bundle with step-scoped credentials"),
        )
        self.assertIn("-Verify -IncludeTests", text)
        self.assertIn("New-TauriProductizationConfig.ps1", text)
        self.assertIn("-ResourceRoot $resourceRoot", text)
        self.assertIn("Publish-PrivateBetaGitHubRelease.ps1", text)
        self.assertIn("Publish-TauriUpdaterChannelPointer.ps1", text)
        self.assertIn("Advance and verify updater channel pointer", text)
        self.assertIn('group: private-beta-windows-${{ github.repository }}-${{ inputs.channel }}', text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertLess(
            text.index("Publish GitHub Release assets"),
            text.index("Advance and verify updater channel pointer"),
        )
        self.assertIn("MEDIAPIPELINE_ALLOW_SAME_COMMIT_REBUILD", text)
        self.assertNotIn("--clobber", text)
        self.assertNotIn("Release package dry run", text)


if __name__ == "__main__":
    unittest.main()
