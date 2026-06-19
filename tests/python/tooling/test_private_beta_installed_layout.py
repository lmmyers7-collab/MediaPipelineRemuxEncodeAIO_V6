from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Test-PrivateBetaInstalledLayout.ps1"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for installed layout verification tests.")
    return shell


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_fixture_layout(
    root: Path,
    *,
    install_localbase: bool = False,
    migration_writes_media: bool = False,
) -> tuple[Path, Path, Path]:
    install_root = root / "install"
    appdata_root = root / "appdata" / "MediaPipelineRemuxEncodeAIO"
    install_root.mkdir(parents=True)
    appdata_root.mkdir(parents=True)
    (install_root / "release_manifest.json").write_text(
        json.dumps({"schema_version": "release_manifest.v1", "version": "2026.06.04.001", "files": []}),
        encoding="utf-8",
    )
    if install_localbase:
        (install_root / "LocalBase").mkdir()

    for relative in (
        "State",
        "Logs",
        "RunLogs",
        "DiagnosticsExports",
        "UpdateState",
        "Backups",
        "State/Migration",
    ):
        (appdata_root / relative).mkdir(parents=True, exist_ok=True)

    _write_json(
        appdata_root / "State" / "Migration" / "localbase_import.json",
        {
            "schema_version": "desktop_appdata_migration.v1",
            "status": "complete",
            "appdata_available": True,
            "writes_media": migration_writes_media,
            "deletes_media": False,
            "protected_boundaries": {
                "moved_source_media": False,
                "deleted_source_media": False,
                "copied_scratch_payloads": False,
                "copied_output_payloads": False,
                "copied_pending_publish_payloads": False,
                "copied_completed_media": False,
            },
        },
    )

    runtime_roots = {
        "appdata_root": appdata_root,
        "config_root": appdata_root / "Config",
        "state_root": appdata_root / "State",
        "logs_root": appdata_root / "Logs",
        "run_logs_root": appdata_root / "RunLogs",
        "diagnostics_exports_root": appdata_root / "DiagnosticsExports",
        "update_state_root": appdata_root / "UpdateState",
        "backups_root": appdata_root / "Backups",
        "migration_root": appdata_root / "State" / "Migration",
    }
    for path in runtime_roots.values():
        path.mkdir(parents=True, exist_ok=True)
    productization_json = root / "productization.json"
    _write_json(
        productization_json,
        {
            "schema_version": "desktop_productization_status.v1",
            "app_version": "2026.06.04.001",
            "release_channel": "beta",
            "installer": {"target": "nsis", "msi_enabled": False, "windows_arch": "x64"},
            "updater": {
                "mode": "prompted",
                "channels": ["beta", "stable"],
                "active_channel": "beta",
                "close_readiness_required": True,
            },
            "runtime_roots": {
                "appdata_available": True,
                "roots": {
                    name: {"path": f"<APPDATA>/{name}", "exists": True}
                    for name in runtime_roots
                },
            },
            "migration": {
                "guarded_import_runs_in_productized_mode": True,
                "writes_media": False,
                "deletes_media": False,
            },
            "release_manifest": {"found": True},
        },
    )
    return install_root, appdata_root, productization_json


def _run_verifier(
    install_root: Path,
    appdata_root: Path,
    productization_json: Path,
) -> subprocess.CompletedProcess[str]:
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
            "-Version",
            "2026.06.04.001",
            "-InstallRoot",
            str(install_root),
            "-AppDataRoot",
            str(appdata_root),
            "-ProductizationJsonPath",
            str(productization_json),
            "-AsJson",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class PrivateBetaInstalledLayoutTests(unittest.TestCase):
    def test_installed_layout_verifier_accepts_productized_appdata_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root, appdata_root, productization_json = _write_fixture_layout(Path(temp_dir))
            result = _run_verifier(install_root, appdata_root, productization_json)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "private_beta_installed_layout_verification.v1")
        self.assertEqual(payload["channel"], "beta")
        self.assertTrue(any(check["name"] == "productization:installer_target" and check["ok"] for check in payload["checks"]))
        self.assertTrue(any(check["name"] == "migration:writes_media" and check["ok"] for check in payload["checks"]))

    def test_installed_layout_verifier_rejects_mutable_localbase_under_install_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root, appdata_root, productization_json = _write_fixture_layout(Path(temp_dir), install_localbase=True)
            result = _run_verifier(install_root, appdata_root, productization_json)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertFalse(payload["ok"])
        self.assertIn("install_root:no_mutable_LocalBase", failed_names)

    def test_installed_layout_verifier_rejects_migration_evidence_that_writes_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_root, appdata_root, productization_json = _write_fixture_layout(
                Path(temp_dir),
                migration_writes_media=True,
            )
            result = _run_verifier(install_root, appdata_root, productization_json)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertFalse(payload["ok"])
        self.assertIn("migration:writes_media", failed_names)

    def test_installed_layout_verifier_does_not_install_download_or_mutate_files(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        forbidden_commands = (
            "Start-Process",
            "Invoke-WebRequest",
            "gh ",
            "msiexec",
            "Remove-Item",
            "Move-Item",
            "Copy-Item",
        )
        for command in forbidden_commands:
            self.assertNotIn(command, text)


if __name__ == "__main__":
    unittest.main()
