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
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Test-PrivateBetaDownloadedAssets.ps1"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for downloaded asset verification tests.")
    return shell


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture_download(root: Path, *, missing_signature: bool = False, bad_checksum: bool = False) -> Path:
    download_root = root / "downloads"
    download_root.mkdir(parents=True)
    installer = download_root / "MediaPipelineRemuxEncodeAIO_2026.6.4+001_x64-setup.exe"
    signature = download_root / f"{installer.name}.sig"
    channel_json = download_root / "latest-beta.json"
    checksums = download_root / "SHA256SUMS.txt"

    installer.write_bytes(b"fake downloaded nsis installer bytes")
    if not missing_signature:
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
    checksum_lines = [
        f"{installer_hash}  {installer.name}",
        f"{_sha256(channel_json)}  {channel_json.name}",
    ]
    if not missing_signature:
        checksum_lines.append(f"{_sha256(signature)}  {signature.name}")
    checksums.write_text("\n".join(checksum_lines + [""]), encoding="utf-8")
    return download_root


def _run_verifier(download_root: Path) -> subprocess.CompletedProcess[str]:
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
            "-DownloadRoot",
            str(download_root),
            "-Repository",
            "owner/repo",
            "-ReleaseTag",
            "app-v2026.6.4+001",
            "-Version",
            "2026.6.4+001",
            "-SkipAuthenticode",
            "-AsJson",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class PrivateBetaDownloadedAssetTests(unittest.TestCase):
    def test_downloaded_asset_verifier_accepts_flat_release_download_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            download_root = _write_fixture_download(Path(temp_dir))
            result = _run_verifier(download_root)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "private_beta_downloaded_asset_verification.v1")
        self.assertEqual(payload["artifacts"]["msi_artifacts_found"], 0)
        self.assertIn("MediaPipelineRemuxEncodeAIO_2026.6.4+001_x64-setup.exe", payload["artifacts"]["installer_candidates"])
        self.assertTrue(any(check["name"] == "authenticode:skipped" and check["ok"] for check in payload["checks"]))

    def test_downloaded_asset_verifier_rejects_missing_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            download_root = _write_fixture_download(Path(temp_dir), missing_signature=True)
            result = _run_verifier(download_root)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertFalse(payload["ok"])
        self.assertIn("updater_signature:file", failed_names)

    def test_downloaded_asset_verifier_rejects_checksum_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            download_root = _write_fixture_download(Path(temp_dir), bad_checksum=True)
            result = _run_verifier(download_root)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertFalse(payload["ok"])
        self.assertIn("checksums:installer", failed_names)

    def test_downloaded_asset_verifier_does_not_install_or_download(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("Start-Process", text)
        self.assertNotIn("Invoke-WebRequest", text)
        self.assertNotIn("gh release download", text)
        self.assertNotIn("msiexec", text.lower())


if __name__ == "__main__":
    unittest.main()
