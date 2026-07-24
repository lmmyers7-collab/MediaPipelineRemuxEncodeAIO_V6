from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev.pytest_style_tests import (
    PytestStyleInventoryError,
    discover_pytest_style_files,
    pytest_arguments,
)
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))


class PytestStyleTestInventoryTests(unittest.TestCase):
    def test_discovers_only_module_level_non_browser_tests_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            python_tests = root / "tests" / "python"
            webview_tests = root / "tests" / "webview"
            python_tests.mkdir(parents=True)
            webview_tests.mkdir(parents=True)
            (python_tests / "test_mixed.py").write_text(
                """
def test_sync():
    pass

async def test_async():
    pass

class ExistingUnittest:
    def test_method(self):
        pass
""",
                encoding="utf-8",
            )
            (webview_tests / "test_plain.py").write_text(
                "def test_webview():\n    pass\n", encoding="utf-8"
            )
            (webview_tests / "test_webview_browser_ignored.py").write_text(
                "def test_browser():\n    pass\n", encoding="utf-8"
            )

            records = discover_pytest_style_files(root)

        self.assertEqual(
            [(record.path, record.tests) for record in records],
            [
                ("tests/python/test_mixed.py", ("test_sync", "test_async")),
                ("tests/webview/test_plain.py", ("test_webview",)),
            ],
        )
        self.assertEqual(
            pytest_arguments(records, collect_only=True),
            [
                "--collect-only",
                "-q",
                "tests/python/test_mixed.py",
                "tests/webview/test_plain.py",
            ],
        )

    def test_inventory_fails_closed_for_missing_root_and_parse_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "tests" / "python").mkdir(parents=True)
            with self.assertRaisesRegex(
                PytestStyleInventoryError, "required test root is missing"
            ):
                discover_pytest_style_files(root)

            webview_root = root / "tests" / "webview"
            webview_root.mkdir(parents=True)
            (root / "tests" / "python" / "test_bad.py").write_text(
                "def test_bad(:\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                PytestStyleInventoryError, "cannot inventory"
            ):
                discover_pytest_style_files(root)

    def test_current_inventory_covers_every_known_pytest_style_file(self) -> None:
        records = discover_pytest_style_files(REPO_ROOT)
        self.assertEqual(
            {record.path for record in records},
            {
                "tests/python/core/subtitles/test_ass_to_srt_helpers.py",
                "tests/python/desktop/test_marketecture_guard.py",
                "tests/python/tooling/test_dependency_atlas.py",
                "tests/webview/test_webview_touchpoint_ledger.py",
            },
        )
        self.assertEqual(sum(len(record.tests) for record in records), 34)

    def test_dependency_and_canonical_gates_invoke_inventory_runner(self) -> None:
        requirements = (REPO_ROOT / "requirements" / "dev.txt").read_text(
            encoding="utf-8"
        )
        self.assertRegex(requirements, r"(?m)^pytest[^\r\n]*$")

        module_command = (
            "python -m mediapipeline.tools.dev.pytest_style_tests --run"
        )
        for workflow_path in (
            REPO_ROOT / ".github" / "workflows" / "deep-audit.yml",
            REPO_ROOT / ".github" / "workflows" / "phase1-drift.yml",
        ):
            workflow = workflow_path.read_text(encoding="utf-8")
            self.assertEqual(workflow.count(module_command), 2)
            self.assertIn("runs-on: ubuntu-latest", workflow)
            self.assertIn("$pytestStyleExitCode = $LASTEXITCODE", workflow)
            self.assertIn("if ($pytestStyleExitCode -ne 0) { exit 1 }", workflow)

        release_test = (REPO_ROOT / "ops" / "scripts" / "release" / "test.ps1").read_text(
            encoding="utf-8"
        )
        release_support = (
            REPO_ROOT / "ops" / "scripts" / "release" / "test_support.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("Invoke-PythonPytestStyleTests", release_test)
        self.assertIn(
            "function Invoke-PythonPytestStyleTests", release_support
        )
        self.assertIn(
            "mediapipeline.tools.dev.pytest_style_tests", release_support
        )


if __name__ == "__main__":
    unittest.main()
