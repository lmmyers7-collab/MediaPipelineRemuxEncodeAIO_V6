from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
POWERSHELL = REPO_ROOT / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
HELPER = REPO_ROOT / "ops" / "scripts" / "dev" / "tauri-prerequisite-tools.ps1"
PREREQ = REPO_ROOT / "apps" / "desktop" / "tauri" / "Test-TauriShell-Prereqs.ps1"


class TauriPrerequisiteToolsTests(unittest.TestCase):
    def _probe_fixture(
        self,
        *,
        include_vsdevcmd: bool = True,
        company_name: str = "Microsoft Corporation",
        product_name: str = "Microsoft Visual Studio",
        file_description: str = "Microsoft Incremental Linker",
        file_version: str = "14.44.35226.0",
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory(prefix="tauri-msvc-probe-") as temp_dir:
            fixture_root = Path(temp_dir)
            install_root = fixture_root / "VisualStudio" / "BuildTools"
            vswhere = fixture_root / "vswhere.exe"
            linker = install_root / "VC" / "Tools" / "MSVC" / "14.44.35207" / "bin" / "Hostx64" / "x64" / "link.exe"
            vswhere.write_bytes(b"fixture")
            linker.parent.mkdir(parents=True)
            linker.write_bytes(b"fixture")
            if include_vsdevcmd:
                vsdevcmd = install_root / "Common7" / "Tools" / "VsDevCmd.bat"
                vsdevcmd.parent.mkdir(parents=True)
                vsdevcmd.write_text("@echo off\n", encoding="utf-8")

            command = """
. $env:TAURI_PREREQ_HELPER
$result = Resolve-MsvcBuildTools `
    -VsWherePath $env:TAURI_FIXTURE_VSWHERE `
    -VsWhereRunner { param($Path) [pscustomobject]@{ ExitCode = 0; InstallationPath = $env:TAURI_FIXTURE_INSTALL } } `
    -VersionInfoReader { param($Path) [pscustomobject]@{
        CompanyName = $env:TAURI_FIXTURE_COMPANY
        ProductName = $env:TAURI_FIXTURE_PRODUCT
        FileDescription = $env:TAURI_FIXTURE_DESCRIPTION
        FileVersion = $env:TAURI_FIXTURE_VERSION
    } }
$result | ConvertTo-Json -Compress
"""
            env = os.environ.copy()
            env.update(
                {
                    "TAURI_PREREQ_HELPER": str(HELPER),
                    "TAURI_FIXTURE_VSWHERE": str(vswhere),
                    "TAURI_FIXTURE_INSTALL": str(install_root),
                    "TAURI_FIXTURE_COMPANY": company_name,
                    "TAURI_FIXTURE_PRODUCT": product_name,
                    "TAURI_FIXTURE_DESCRIPTION": file_description,
                    "TAURI_FIXTURE_VERSION": file_version,
                }
            )
            completed = subprocess.run(
                [str(POWERSHELL), "-NoProfile", "-Command", command],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            return json.loads(completed.stdout.strip())

    def test_valid_vswhere_workload_vsdevcmd_x64_linker_and_metadata_pass(self) -> None:
        result = self._probe_fixture()

        self.assertTrue(result["Valid"])
        self.assertTrue(result["WorkloadFound"])
        self.assertTrue(result["VsDevCmdFound"])
        self.assertTrue(result["LinkerFound"])
        self.assertTrue(result["MetadataValid"])
        self.assertTrue(str(result["LinkerPath"]).endswith(r"bin\Hostx64\x64\link.exe"))

    def test_non_microsoft_linker_metadata_fails_closed(self) -> None:
        result = self._probe_fixture(
            company_name="Example Tools",
            product_name="Example link utility",
            file_description="Filesystem link helper",
        )

        self.assertFalse(result["Valid"])
        self.assertTrue(result["LinkerFound"])
        self.assertFalse(result["MetadataValid"])

    def test_missing_vsdevcmd_fails_closed_before_linker_acceptance(self) -> None:
        result = self._probe_fixture(include_vsdevcmd=False)

        self.assertFalse(result["Valid"])
        self.assertTrue(result["WorkloadFound"])
        self.assertFalse(result["VsDevCmdFound"])
        self.assertFalse(result["LinkerFound"])

    def test_require_build_tools_ignores_hostile_path_link_command(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tauri-hostile-link-") as temp_dir:
            fixture_root = Path(temp_dir)
            hostile = fixture_root / "link.cmd"
            hostile.write_text("@echo hostile-link\n", encoding="utf-8")
            env = os.environ.copy()
            env["ProgramFiles(x86)"] = str(fixture_root / "no-visual-studio")
            env["PATH"] = f"{fixture_root}{os.pathsep}{env.get('PATH', '')}"
            completed = subprocess.run(
                [
                    str(POWERSHELL),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(PREREQ),
                    "-CheckOnly",
                    "-RequireBuildTools",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )

        output = completed.stdout + completed.stderr
        self.assertNotEqual(completed.returncode, 0, output)
        self.assertIn("[WARN] MSVC x64 linker provenance", output)
        self.assertIn("vswhere.exe was not found", output)
        self.assertNotIn(str(hostile), output)


if __name__ == "__main__":
    unittest.main()
