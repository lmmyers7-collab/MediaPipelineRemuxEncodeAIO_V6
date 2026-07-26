from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from mediapipeline.tools.paths import find_repo_root


DEFAULT_TEST_ROOTS = ("tests/python", "tests/webview")
BROWSER_TEST_PREFIX = "test_webview_browser"


class PytestStyleInventoryError(RuntimeError):
    """Raised when the canonical pytest-style inventory cannot be trusted."""


@dataclass(frozen=True)
class PytestStyleFile:
    path: str
    tests: tuple[str, ...]


def _module_level_test_names(path: Path) -> tuple[str, ...]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise PytestStyleInventoryError(f"cannot inventory {path}: {exc}") from exc

    return tuple(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )


def discover_pytest_style_files(
    repo_root: Path,
    *,
    test_roots: Sequence[str] = DEFAULT_TEST_ROOTS,
) -> tuple[PytestStyleFile, ...]:
    records: list[PytestStyleFile] = []
    for relative_root in test_roots:
        root = repo_root / relative_root
        if not root.is_dir():
            raise PytestStyleInventoryError(
                f"required test root is missing: {relative_root}"
            )
        for path in sorted(root.rglob("test_*.py")):
            relative_path = path.relative_to(repo_root).as_posix()
            if (
                relative_path.startswith("tests/webview/")
                and path.name.startswith(BROWSER_TEST_PREFIX)
            ):
                continue
            tests = _module_level_test_names(path)
            if tests:
                records.append(PytestStyleFile(path=relative_path, tests=tests))

    records.sort(key=lambda record: record.path)
    if not records:
        raise PytestStyleInventoryError(
            "no module-level pytest-style tests were discovered in the required roots"
        )
    return tuple(records)


def pytest_arguments(
    records: Sequence[PytestStyleFile], *, collect_only: bool = False
) -> list[str]:
    arguments = ["-q"]
    if collect_only:
        arguments.insert(0, "--collect-only")
    arguments.extend(record.path for record in records)
    return arguments


def run_pytest_style_files(
    repo_root: Path,
    records: Sequence[PytestStyleFile],
    *,
    collect_only: bool = False,
) -> int:
    command = [
        sys.executable,
        "-m",
        "pytest",
        *pytest_arguments(records, collect_only=collect_only),
    ]
    try:
        return subprocess.run(command, cwd=repo_root, check=False).returncode
    except OSError as exc:
        print(f"unable to start pytest: {exc}", file=sys.stderr)
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory module-level pytest-style tests and run exactly their files. "
            "Browser smoke modules remain owned by the isolated browser matrix."
        )
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="Print discovered paths.")
    action.add_argument(
        "--json", action="store_true", help="Print the discovered inventory as JSON."
    )
    action.add_argument(
        "--collect-only",
        action="store_true",
        help="Run pytest collection for every discovered file.",
    )
    action.add_argument(
        "--run", action="store_true", help="Run every discovered file with pytest."
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = find_repo_root(Path(__file__))
    try:
        records = discover_pytest_style_files(repo_root)
    except PytestStyleInventoryError as exc:
        print(f"pytest-style inventory failed: {exc}", file=sys.stderr)
        return 1

    function_count = sum(len(record.tests) for record in records)
    print(
        f"pytest-style inventory: {function_count} module-level test function(s) "
        f"across {len(records)} file(s)."
    )
    if args.list:
        for record in records:
            print(record.path)
        return 0
    if args.json:
        print(json.dumps([asdict(record) for record in records], indent=2))
        return 0
    return run_pytest_style_files(
        repo_root, records, collect_only=bool(args.collect_only)
    )


if __name__ == "__main__":
    raise SystemExit(main())
