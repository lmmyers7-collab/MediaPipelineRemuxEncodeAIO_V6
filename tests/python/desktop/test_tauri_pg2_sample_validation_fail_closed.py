from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "apps" / "desktop" / "tauri" / "Test-TauriShell-PG2SampleValidationAppend.ps1"
PWSH = REPO_ROOT / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
DEBUG_WEBVIEW = REPO_ROOT / "apps" / "desktop" / "tauri" / "src-tauri" / "src" / "debug_webview.rs"


class TauriPg2SampleValidationFailClosedTests(unittest.TestCase):
    def test_obsolete_harness_refuses_before_creating_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / "sample_validation_log.jsonl"
            result = subprocess.run(
                [
                    str(PWSH),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SCRIPT),
                    "-SourceFile",
                    str(root / "missing-source.mkv"),
                    "-OutputFile",
                    str(root / "missing-output.mkv"),
                    "-SampleValidationLog",
                    str(log_path),
                    "-Decision",
                    "accepted",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            detail = result.stdout + result.stderr
            self.assertIn("automatic sample-validation append is disabled", detail)
            self.assertIn("No Tauri shell, backend, pipeline command", detail)
            self.assertFalse(log_path.exists())

    def test_debug_shell_has_no_sample_attestation_generator(self) -> None:
        source = DEBUG_WEBVIEW.read_text(encoding="utf-8")
        for forbidden in (
            "pg2-sample-validation-append",
            "debug_sample_validation_append_script",
            "sample_validation_record.v1",
            'apiPost(\"/api/sample-validation/append\"',
            "ffmpeg_log_checked: true",
            "proof_strength: \"exact-path\"",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
