from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
MODULE_PATH = REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "check_python_lint.py"
spec = importlib.util.spec_from_file_location("check_python_lint_for_tests", MODULE_PATH)
assert spec and spec.loader
check_python_lint = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_python_lint
spec.loader.exec_module(check_python_lint)


class PythonLintCheckTests(unittest.TestCase):
    def test_default_targets_construct_ruff_check_for_src_and_tests(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0)

        with (
            patch.object(check_python_lint.importlib.util, "find_spec", return_value=object()),
            patch.object(check_python_lint.subprocess, "run", side_effect=fake_run),
        ):
            result = check_python_lint.main([])

        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)
        command, kwargs = calls[0]
        self.assertEqual(
            command,
            [
                check_python_lint.sys.executable,
                "-m",
                "ruff",
                "check",
                "--config",
                "pyproject.toml",
                "src",
                "tests",
            ],
        )
        self.assertEqual(kwargs, {"cwd": check_python_lint.REPO_ROOT})
        self.assertNotIn("--fix", command)
        self.assertNotIn("format", command)

    def test_custom_targets_are_forwarded_after_ruff_check(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            calls.append(command)
            return SimpleNamespace(returncode=1)

        with (
            patch.object(check_python_lint.importlib.util, "find_spec", return_value=object()),
            patch.object(check_python_lint.subprocess, "run", side_effect=fake_run),
        ):
            result = check_python_lint.main(["src/mediapipeline/tools", "tests/python/tooling"])

        self.assertEqual(result, 1)
        self.assertEqual(
            calls[0],
            [
                check_python_lint.sys.executable,
                "-m",
                "ruff",
                "check",
                "--config",
                "pyproject.toml",
                "src/mediapipeline/tools",
                "tests/python/tooling",
            ],
        )

    def test_missing_ruff_returns_clear_tooling_error_without_running_subprocess(self) -> None:
        stderr = io.StringIO()

        with (
            patch.object(check_python_lint.importlib.util, "find_spec", return_value=None),
            patch.object(check_python_lint.subprocess, "run") as run_mock,
            contextlib.redirect_stderr(stderr),
        ):
            result = check_python_lint.main([])

        self.assertEqual(result, 2)
        run_mock.assert_not_called()
        self.assertIn("Ruff is not installed", stderr.getvalue())
        self.assertIn("requirements/dev.txt", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
