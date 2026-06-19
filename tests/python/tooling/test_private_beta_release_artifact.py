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


def _run_verifier(bundle_root: Path) -> subprocess.CompletedProcess[str]:
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


if __name__ == "__main__":
    unittest.main()
