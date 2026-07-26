from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Test-PrivateBetaReleaseArtifact.ps1"

REQUIRED_INSTALLER_PATHS = (
    "release_manifest.json",
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
        raise unittest.SkipTest("PowerShell is required for release artifact verification tests.")
    return shell


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture_bundle(root: Path, *, bad_checksum: bool = False) -> Path:
    bundle_root = root / "bundle"
    nsis_root = bundle_root / "nsis"
    nsis_root.mkdir(parents=True)
    installer = nsis_root / "MediaPipelineRemuxEncodeAIO_2026.6.4+001_x64-setup.exe"
    signature = nsis_root / f"{installer.name}.sig"
    channel_json = bundle_root / "latest-beta.json"
    checksums = bundle_root / "SHA256SUMS.txt"

    installer.write_bytes(b"fake nsis installer bytes")
    signature.write_text("fake-updater-signature", encoding="utf-8")
    channel_json.write_text(
        json.dumps(
            {
                "version": "2026.6.4+001",
                "notes": "fixture",
                "pub_date": "2026-06-18T00:00:00Z",
                "platforms": {
                    "windows-x86_64": {
                        "signature": "fake-updater-signature",
                        "url": f"https://github.com/owner/repo/releases/download/app-v2026.6.4+001/{installer.name}",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    installer_hash = "0" * 64 if bad_checksum else _sha256(installer)
    checksums.write_text(
        "\n".join(
            [
                f"{installer_hash}  {installer.name}",
                f"{_sha256(signature)}  {signature.name}",
                f"{_sha256(channel_json)}  {channel_json.name}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return bundle_root


def _write_fake_seven_zip(root: Path, inventory_paths: tuple[str, ...]) -> Path:
    script = root / "fake-7z.cmd"
    lines = ["@echo off", *(f"echo Path = {path}" for path in inventory_paths), "exit /b 0"]
    script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return script


def _run_verifier(
    bundle_root: Path,
    *,
    inventory_paths: tuple[str, ...] = REQUIRED_INSTALLER_PATHS,
) -> subprocess.CompletedProcess[str]:
    seven_zip = _write_fake_seven_zip(bundle_root.parent, inventory_paths)
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
            "-BundleRoot",
            str(bundle_root),
            "-Repository",
            "owner/repo",
            "-ReleaseTag",
            "app-v2026.6.4+001",
            "-Version",
            "2026.6.4+001",
            "-SevenZipPath",
            str(seven_zip),
            "-SkipAuthenticode",
            "-AsJson",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class PrivateBetaReleaseArtifactTests(unittest.TestCase):
    def test_artifact_verifier_accepts_matching_bundle_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = _write_fixture_bundle(Path(temp_dir))
            result = _run_verifier(bundle_root)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "private_beta_release_artifact_verification.v1")
        self.assertEqual(payload["artifacts"]["msi_artifacts_found"], 0)
        self.assertEqual(payload["artifacts"]["installer_payload_inventory"]["required_path_count"], 11)
        self.assertEqual(payload["artifacts"]["installer_payload_inventory"]["forbidden_path_count"], 0)
        self.assertTrue(any(check["name"] == "authenticode:skipped" and check["ok"] for check in payload["checks"]))

    def test_artifact_verifier_rejects_checksum_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = _write_fixture_bundle(Path(temp_dir), bad_checksum=True)
            result = _run_verifier(bundle_root)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertFalse(payload["ok"])
        self.assertIn("checksums:installer", failed_names)

    def test_artifact_verifier_rejects_installer_missing_backend_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = _write_fixture_bundle(Path(temp_dir))
            result = _run_verifier(
                bundle_root,
                inventory_paths=("MediaPipelineRemuxEncodeAIO.exe", "release_manifest.json"),
            )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("installer_payload:required:apps_desktop_webview_static_index_html", failed_names)
        self.assertIn("installer_payload:required:src_mediapipeline_desktop_local_api_main_py", failed_names)

    def test_artifact_verifier_rejects_mutable_or_personal_installer_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_root = _write_fixture_bundle(Path(temp_dir))
            result = _run_verifier(
                bundle_root,
                inventory_paths=REQUIRED_INSTALLER_PATHS
                + ("LocalBase/State/operator.json", "ops/pipeline/config/MediaPipeline_config.psd1"),
            )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("installer_payload:no_mutable_or_personal_state", failed_names)


if __name__ == "__main__":
    unittest.main()
