"""Discover the authoritative browser-smoke selector inventory for CI."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Sequence

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
BROWSER_TEST_GLOB = "test_webview_browser*.py"
_SAFE_SELECTOR = re.compile(r"^tests\.webview\.test_webview_browser[A-Za-z0-9_.]+$")


class BrowserSmokeInventoryError(RuntimeError):
    """Raised when browser-smoke source cannot produce a safe complete inventory."""


@dataclass(frozen=True)
class BrowserSmokeInventory:
    modules: tuple[str, ...]
    selectors: tuple[str, ...]

    def github_matrix(self) -> dict[str, list[dict[str, str]]]:
        return {"include": [{"test_id": selector} for selector in self.selectors]}

    def to_dict(self) -> dict[str, object]:
        return {
            "module_count": len(self.modules),
            "selector_count": len(self.selectors),
            "modules": list(self.modules),
            "selectors": list(self.selectors),
        }


def _is_unittest_test_case(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "TestCase":
            return True
        if (
            isinstance(base, ast.Attribute)
            and base.attr == "TestCase"
            and isinstance(base.value, ast.Name)
            and base.value.id == "unittest"
        ):
            return True
    return False


def _module_selectors(path: Path) -> tuple[str, tuple[str, ...]]:
    module = f"tests.webview.{path.stem}"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as error:
        raise BrowserSmokeInventoryError(f"Could not inspect browser smoke module {path}: {error}") from error

    selectors: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not _is_unittest_test_case(node):
            continue
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name.startswith("test"):
                selectors.append(f"{module}.{node.name}.{member.name}")

    if not selectors:
        raise BrowserSmokeInventoryError(f"Browser smoke module has no unittest.TestCase test methods: {path}")
    unsafe = [selector for selector in selectors if not _SAFE_SELECTOR.fullmatch(selector)]
    if unsafe:
        raise BrowserSmokeInventoryError(f"Browser smoke module produced unsafe selectors: {unsafe}")
    return module, tuple(sorted(selectors))


def discover_browser_smoke_inventory(repo_root: Path = REPO_ROOT) -> BrowserSmokeInventory:
    tests_root = Path(repo_root) / "tests" / "webview"
    paths = sorted(tests_root.glob(BROWSER_TEST_GLOB), key=lambda path: path.name.casefold())
    if not paths:
        raise BrowserSmokeInventoryError(f"No browser smoke modules matched {tests_root / BROWSER_TEST_GLOB}")

    modules: list[str] = []
    selectors: list[str] = []
    for path in paths:
        module, module_selectors = _module_selectors(path)
        modules.append(module)
        selectors.extend(module_selectors)

    if len(selectors) != len(set(selectors)):
        raise BrowserSmokeInventoryError("Browser smoke discovery produced duplicate selectors.")
    return BrowserSmokeInventory(modules=tuple(modules), selectors=tuple(sorted(selectors)))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--format",
        choices=("github-matrix", "json", "selectors"),
        default="json",
        dest="output_format",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        inventory = discover_browser_smoke_inventory(args.repo_root)
    except BrowserSmokeInventoryError as error:
        print(f"Browser smoke inventory failed: {error}")
        return 1

    if args.output_format == "github-matrix":
        print(json.dumps(inventory.github_matrix(), separators=(",", ":")))
    elif args.output_format == "selectors":
        print("\n".join(inventory.selectors))
    else:
        print(json.dumps(inventory.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
