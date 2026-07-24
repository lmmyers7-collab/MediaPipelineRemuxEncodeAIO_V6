from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
MODULE_PATH = REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "check_tracked_office_documents.py"
spec = importlib.util.spec_from_file_location("check_tracked_office_documents_for_tests", MODULE_PATH)
assert spec and spec.loader
office_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = office_check
spec.loader.exec_module(office_check)


class TrackedOfficeDocumentTests(unittest.TestCase):
    def test_enumerates_present_office_documents_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tracked = root / "docs" / "design.DOCX"
            tracked.parent.mkdir(parents=True)
            tracked.write_bytes(b"test")
            completed = subprocess.CompletedProcess(
                args=["git", "ls-files"],
                returncode=0,
                stdout="docs/design.DOCX\0docs/notes.md\0docs/deleted.pptx\0",
                stderr="",
            )

            with mock.patch.object(office_check.subprocess, "run", return_value=completed):
                findings = office_check.tracked_office_documents(root)

        self.assertEqual(findings, ["docs/design.DOCX"])

    def test_git_failures_are_fail_closed(self) -> None:
        command = ["git", "ls-files", "-z", "--", "docs"]
        failures = (
            FileNotFoundError("git missing"),
            subprocess.TimeoutExpired(command, office_check.GIT_ENUMERATION_TIMEOUT_SECONDS),
            subprocess.CalledProcessError(128, command, stderr="not a repository"),
            PermissionError("access denied"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with mock.patch.object(office_check.subprocess, "run", side_effect=failure):
                    with self.assertRaises(office_check.GitEnumerationError):
                        office_check.tracked_office_documents(REPO_ROOT)

    def test_cli_reports_findings_and_enumeration_errors(self) -> None:
        stdout = io.StringIO()
        with (
            mock.patch.object(office_check, "tracked_office_documents", return_value=["docs/reference.docx"]),
            redirect_stdout(stdout),
        ):
            exit_code = office_check.main(["--json"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["findings"], ["docs/reference.docx"])

        stderr = io.StringIO()
        with (
            mock.patch.object(
                office_check,
                "tracked_office_documents",
                side_effect=office_check.GitEnumerationError("Git unavailable"),
            ),
            redirect_stderr(stderr),
        ):
            exit_code = office_check.main([])
        self.assertEqual(exit_code, 2)
        self.assertIn("Git unavailable", stderr.getvalue())

    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Source-control provenance checks require a Git checkout.",
    )
    def test_current_repository_has_no_tracked_office_documents_under_docs(self) -> None:
        self.assertEqual(office_check.tracked_office_documents(REPO_ROOT), [])


if __name__ == "__main__":
    unittest.main()
