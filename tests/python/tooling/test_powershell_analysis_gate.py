from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
CHECKER = REPO_ROOT / "ops" / "scripts" / "dev" / "check_powershell_analysis.ps1"
INSTALLER = REPO_ROOT / "ops" / "scripts" / "dev" / "install_powershell_analysis.ps1"
REQUIREMENTS = REPO_ROOT / "requirements" / "powershell-modules.psd1"
WORKFLOWS = (
    REPO_ROOT / ".github" / "workflows" / "deep-audit.yml",
    REPO_ROOT / ".github" / "workflows" / "phase1-drift.yml",
)


class PowerShellAnalysisGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bundled = (
            REPO_ROOT
            / "ops"
            / "pipeline"
            / "runtime"
            / "PowerShell-7.6.0-win-x64"
            / "pwsh.exe"
        )
        cls.powershell = (
            str(bundled)
            if bundled.is_file()
            else shutil.which("pwsh") or shutil.which("powershell")
        )
        if not cls.powershell:
            raise unittest.SkipTest("PowerShell is required for analyzer gate tests.")

    def _run_checker(
        self,
        *,
        module_path: Path,
        analysis_root: Path,
        target_path: Path,
        preload_manifest: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        escaped_module_path = str(module_path).replace("'", "''")
        escaped_analysis_root = str(analysis_root).replace("'", "''")
        escaped_checker = str(CHECKER).replace("'", "''")
        escaped_target = str(target_path).replace("'", "''")
        commands = [
            f"$env:PSModulePath = '{escaped_module_path}'",
            f"$env:MP_POWERSHELL_ANALYSIS_MODULE_ROOT = '{escaped_analysis_root}'",
        ]
        if preload_manifest is not None:
            escaped_preload_manifest = str(preload_manifest).replace("'", "''")
            commands.append(f"Import-Module -Name '{escaped_preload_manifest}' -Force")
        commands.append(f"& '{escaped_checker}' -Path '{escaped_target}'")
        command = "; ".join(commands)
        return subprocess.run(
            [
                self.powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=REPO_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )

    def test_dependency_manifest_selects_one_approved_version(self) -> None:
        requirements = REQUIREMENTS.read_text(encoding="utf-8")

        self.assertIn("PSScriptAnalyzer", requirements)
        self.assertIn("RequiredVersion = '1.25.0'", requirements)
        self.assertIn("Guid            = 'd6245802-193d-4068-a631-8863a4342a18'", requirements)
        self.assertIn("Repository      = 'PSGallery'", requirements)

    def test_workflows_use_repository_owned_exact_version_installer(self) -> None:
        for workflow_path in WORKFLOWS:
            with self.subTest(workflow=workflow_path.name):
                workflow = workflow_path.read_text(encoding="utf-8")
                self.assertIn(
                    r".\ops\scripts\dev\install_powershell_analysis.ps1",
                    workflow,
                )
                self.assertNotIn("Install-Module PSScriptAnalyzer", workflow)
                self.assertLess(
                    workflow.index("install_powershell_analysis.ps1"),
                    workflow.index("check_powershell_analysis.ps1"),
                )

    def test_installer_and_checker_consume_the_same_requirement(self) -> None:
        installer = INSTALLER.read_text(encoding="utf-8")
        checker = CHECKER.read_text(encoding="utf-8")

        for script in (installer, checker):
            with self.subTest(script=script[:40]):
                self.assertIn(r"requirements\powershell-modules.psd1", script)
                self.assertIn("RequiredVersion", script)
                self.assertIn("PSScriptAnalyzer.psd1", script)
                self.assertIn("Test-ModuleManifest", script)
        self.assertIn("Save-Module", installer)
        self.assertIn("-RequiredVersion $RequiredVersionText", installer)
        self.assertIn("-Repository $Repository", installer)
        self.assertIn(
            "Required isolated PSScriptAnalyzer $RequiredVersionText is not installed",
            checker,
        )
        self.assertIn("Remove-Module -Name PSScriptAnalyzer", checker)
        self.assertIn("Resolve-Path -LiteralPath $_.Module.Path", checker)
        self.assertIn("$LoadedModulePath", checker)
        self.assertIn("$Findings = & $AnalyzerCommand", checker)

    def test_missing_required_analyzer_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target"
            target.mkdir()
            (target / "clean.ps1").write_text("Write-Output 'clean'\n", encoding="utf-8")
            result = self._run_checker(
                module_path=root / "empty-modules",
                analysis_root=root / "isolated-modules",
                target_path=target,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "Required isolated PSScriptAnalyzer 1.25.0 is not installed",
            result.stdout + result.stderr,
        )
        self.assertNotIn("skipping PowerShell analysis", result.stdout + result.stderr)

    def test_wrong_analyzer_version_does_not_satisfy_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target"
            target.mkdir()
            (target / "clean.ps1").write_text("Write-Output 'clean'\n", encoding="utf-8")
            module_root = root / "modules" / "PSScriptAnalyzer" / "9.9.9"
            module_root.mkdir(parents=True)
            (module_root / "PSScriptAnalyzer.psd1").write_text(
                "@{ RootModule='PSScriptAnalyzer.psm1'; ModuleVersion='9.9.9'; "
                "GUID='665ee81b-3564-4e11-857d-93d5b8d6e00c' }\n",
                encoding="utf-8",
            )
            (module_root / "PSScriptAnalyzer.psm1").write_text(
                "function Invoke-ScriptAnalyzer { param([string] $Path) @() }\n"
                "Export-ModuleMember -Function Invoke-ScriptAnalyzer\n",
                encoding="utf-8",
            )
            result = self._run_checker(
                module_path=root / "modules",
                analysis_root=root / "isolated-modules",
                target_path=target,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "Required isolated PSScriptAnalyzer 1.25.0 is not installed",
            result.stdout + result.stderr,
        )

    def test_same_version_module_path_shadow_cannot_satisfy_isolated_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target"
            target.mkdir()
            (target / "clean.ps1").write_text("Write-Output 'clean'\n", encoding="utf-8")
            shadow_root = root / "modules" / "PSScriptAnalyzer" / "1.25.0"
            shadow_root.mkdir(parents=True)
            (shadow_root / "PSScriptAnalyzer.psd1").write_text(
                "@{ RootModule='PSScriptAnalyzer.psm1'; ModuleVersion='1.25.0'; "
                "GUID='d6245802-193d-4068-a631-8863a4342a18' }\n",
                encoding="utf-8",
            )
            (shadow_root / "PSScriptAnalyzer.psm1").write_text(
                "function Invoke-ScriptAnalyzer { param([string] $Path) @() }\n"
                "Export-ModuleMember -Function Invoke-ScriptAnalyzer\n",
                encoding="utf-8",
            )
            result = self._run_checker(
                module_path=root / "modules",
                analysis_root=root / "isolated-modules",
                target_path=target,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "Required isolated PSScriptAnalyzer 1.25.0 is not installed",
            result.stdout + result.stderr,
        )

    def test_preloaded_namesake_cannot_shadow_isolated_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target"
            target.mkdir()
            (target / "clean.ps1").write_text("Write-Output 'clean'\n", encoding="utf-8")
            marker = root / "analyzer-marker.txt"
            trusted_root = root / "isolated-modules" / "PSScriptAnalyzer" / "1.25.0"
            trusted_root.mkdir(parents=True)
            trusted_manifest = trusted_root / "PSScriptAnalyzer.psd1"
            trusted_manifest.write_text(
                "@{ RootModule='PSScriptAnalyzer.psm1'; ModuleVersion='1.25.0'; "
                "GUID='d6245802-193d-4068-a631-8863a4342a18' }\n",
                encoding="utf-8",
            )
            trusted_marker = str(marker).replace("'", "''")
            (trusted_root / "PSScriptAnalyzer.psm1").write_text(
                "function Invoke-ScriptAnalyzer { "
                "param([string] $Path, [switch] $Recurse, [string] $Severity) "
                f"Set-Content -LiteralPath '{trusted_marker}' -Value 'trusted'; @() }}\n"
                "Export-ModuleMember -Function Invoke-ScriptAnalyzer\n",
                encoding="utf-8",
            )
            shadow_root = root / "modules" / "PSScriptAnalyzer" / "9.9.9"
            shadow_root.mkdir(parents=True)
            shadow_manifest = shadow_root / "PSScriptAnalyzer.psd1"
            shadow_manifest.write_text(
                "@{ RootModule='PSScriptAnalyzer.psm1'; ModuleVersion='9.9.9'; "
                "GUID='665ee81b-3564-4e11-857d-93d5b8d6e00c' }\n",
                encoding="utf-8",
            )
            shadow_marker = str(marker).replace("'", "''")
            (shadow_root / "PSScriptAnalyzer.psm1").write_text(
                "function Invoke-ScriptAnalyzer { "
                "param([string] $Path, [switch] $Recurse, [string] $Severity) "
                f"Set-Content -LiteralPath '{shadow_marker}' -Value 'shadow'; @() }}\n"
                "Export-ModuleMember -Function Invoke-ScriptAnalyzer\n",
                encoding="utf-8",
            )
            result = self._run_checker(
                module_path=root / "modules",
                analysis_root=root / "isolated-modules",
                target_path=target,
                preload_manifest=shadow_manifest,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8").strip(), "trusted")


if __name__ == "__main__":
    unittest.main()
