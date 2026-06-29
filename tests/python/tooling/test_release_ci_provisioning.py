from __future__ import annotations

import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))


class ReleaseCiProvisioningTests(unittest.TestCase):
    def test_pysubs2_declared_for_project_and_dev_runtime(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        dev_requirements = (REPO_ROOT / "requirements" / "dev.txt").read_text(encoding="utf-8")

        self.assertIn('"pysubs2>=1.7,<2"', pyproject)
        self.assertIn("pysubs2>=1.7,<2", dev_requirements)

    def test_python_runtime_provisioner_installs_dependencies_into_bundled_roots(self) -> None:
        script = (REPO_ROOT / "ops" / "scripts" / "release" / "Initialize-CiPythonRuntime.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("[switch] $InstallDependencies", script)
        self.assertIn("requirements\\dev.txt", script)
        self.assertIn("'-e', $RepoRootPath", script)
        self.assertIn("import pydantic, psutil, pysubs2, zeroconf", script)
        self.assertIn("apps\\desktop\\runtime\\Python", script)
        self.assertIn("ops\\pipeline\\runtime\\Python", script)

    def test_media_tool_provisioner_targets_release_expected_layout(self) -> None:
        script = (REPO_ROOT / "ops" / "scripts" / "release" / "Initialize-CiMediaTools.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("ops\\pipeline\\runtime\\PowerShell-7.6.0-win-x64", script)
        self.assertIn("ops\\pipeline\\tools\\ffmpeg\\bin", script)
        self.assertIn("ops\\pipeline\\tools\\MKVToolNix", script)
        self.assertIn("ffprobe.exe", script)
        self.assertIn("mkvmerge.exe", script)
        self.assertIn("'ffmpeg', 'mkvtoolnix'", script)

    def test_deep_audit_provisions_bundled_runtime_tools_and_stable_temp_paths(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "deep-audit.yml").read_text(encoding="utf-8")

        self.assertIn("TMP: ${{ runner.temp }}", workflow)
        self.assertIn("TEMP: ${{ runner.temp }}", workflow)
        self.assertIn("Initialize-CiPythonRuntime.ps1 -InstallDependencies", workflow)
        self.assertIn("Initialize-CiMediaTools.ps1 -InstallMissing", workflow)


if __name__ == "__main__":
    unittest.main()
