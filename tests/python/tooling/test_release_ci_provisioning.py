from __future__ import annotations

import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))


class ReleaseCiProvisioningTests(unittest.TestCase):
    def test_pysubs2_declared_for_project_and_dev_runtime(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        dev_requirements = (REPO_ROOT / "requirements" / "dev.txt").read_text(encoding="utf-8")

        self.assertIn('"pysubs2>=1.8.1,<2"', pyproject)
        self.assertIn("pysubs2>=1.8.1,<2", dev_requirements)

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
        self.assertIn("Tentacule/PgsToSrt/releases/download/v1.4.8/PgsToStr-1.4.8.zip", script)
        self.assertIn("27c3e637fe777cabe55b063a5a454e124c395e727d6a270899be3b5a7b2a9c7a", script)
        self.assertIn("tesseract-ocr/tessdata/ced78752cc61322fb554c280d13360b35b8684e4/eng.traineddata", script)
        self.assertIn("daa0c97d651c19fba3b25e81317cd697e9908c8208090c94c3905381c23fc047", script)
        self.assertIn("function Invoke-VerifiedDownload", script)
        self.assertIn("[int] $MaximumAttempts = 3", script)
        self.assertEqual(script.count("Invoke-VerifiedDownload -Uri $pgs"), 2)

    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Source-checkout CI workflow metadata is intentionally omitted from release packages.",
    )
    def test_deep_audit_provisions_bundled_runtime_tools_and_stable_temp_paths(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "deep-audit.yml").read_text(encoding="utf-8")

        self.assertNotIn("${{ runner.temp }}", workflow)
        self.assertEqual(workflow.count("Initialize isolated CI environment"), 7)
        self.assertEqual(workflow.count('"mediapipeline-$env:GITHUB_JOB"'), 7)
        self.assertEqual(workflow.count("$env:GITHUB_ENV"), 7)
        self.assertIn("Deep Audit browser smoke (${{ matrix.test_id }})", workflow)
        self.assertIn("Initialize-CiPythonRuntime.ps1 -InstallDependencies", workflow)
        self.assertIn("Initialize-CiMediaTools.ps1 -InstallMissing", workflow)

    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Source-checkout CI workflow metadata is intentionally omitted from release packages.",
    )
    def test_generated_drift_release_jobs_provision_the_same_required_runtime(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "phase1-drift.yml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("${{ runner.temp }}", workflow)
        self.assertEqual(workflow.count("Initialize isolated CI environment"), 4)
        self.assertEqual(workflow.count('"mediapipeline-$env:GITHUB_JOB"'), 4)
        self.assertEqual(workflow.count("$env:GITHUB_ENV"), 4)
        self.assertEqual(workflow.count("Initialize-CiPythonRuntime.ps1 -InstallDependencies"), 4)
        self.assertEqual(workflow.count("Initialize-CiMediaTools.ps1 -InstallMissing"), 4)
        self.assertIn("Browser smoke (${{ matrix.test_id }})", workflow)

    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Source-checkout CI workflow metadata is intentionally omitted from release packages.",
    )
    def test_generated_drift_has_case_sensitive_generated_context_job(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "phase1-drift.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("generated-context-linux:", workflow)
        self.assertIn("name: Generated context drift (Linux)", workflow)
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertIn("Run generated context checks on a case-sensitive filesystem", workflow)
        self.assertIn("npm run webview:contract:check", workflow)

    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Source-checkout CI workflow metadata is intentionally omitted from release packages.",
    )
    def test_deep_audit_python_and_release_jobs_share_complete_runtime_provisioning(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "deep-audit.yml").read_text(encoding="utf-8")

        self.assertNotIn("${{ runner.temp }}", workflow)
        self.assertEqual(workflow.count("Initialize isolated CI environment"), 7)
        self.assertEqual(workflow.count("Initialize-CiPythonRuntime.ps1 -InstallDependencies"), 4)
        self.assertEqual(workflow.count("Initialize-CiMediaTools.ps1 -InstallMissing"), 4)


if __name__ == "__main__":
    unittest.main()
