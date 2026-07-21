"""Generate a machine-readable smoke wrapper drift map.

The map ties each stable operator wrapper under ops/scripts/smoke/ to the
Python test/module it delegates to, the active smoke docs, and the release
layout gate. Use --check in release/tooling validation to catch drift without
rewriting the generated JSON.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
OUTPUT_PATH = REPO_ROOT / "docs" / "generated" / "SMOKE_WRAPPER_MAP.json"
RUN_COMMAND = (
    "apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py "
    "mediapipeline.tools.dev.generate_smoke_wrapper_map"
)

BROWSER_CATALOG_HEADING_RE = re.compile(
    r"^#{1,6}\s+`(?P<name>Test-WebViewBrowser[^`]+\.ps1)`\s*$",
    flags=re.MULTILINE,
)
BROWSER_WRAPPER_COUNT_RE = re.compile(
    r"\b(?P<count>\d+)\s+(?:canonical\s+)?browser(?:-backed)?(?:\s+smoke)?\s+wrappers?\b",
    flags=re.IGNORECASE,
)
BROWSER_MODULE_COUNT_RE = re.compile(
    r"\b(?P<count>\d+)\s+(?:browser(?:-backed)?\s+)?Python(?:\s+smoke)?\s+modules?\b",
    flags=re.IGNORECASE,
)
BROWSER_WRAPPER_BACKED_MODULE_COUNT_RE = re.compile(
    r"\b(?P<count>\d+)\s+wrapper-backed\s+browser(?:-backed)?(?:\s+Python)?\s+modules?\b",
    flags=re.IGNORECASE,
)
BROWSER_DIRECT_ONLY_MODULE_COUNT_RE = re.compile(
    r"\b(?P<count>\d+)\s+direct-only\s+browser(?:-backed)?(?:\s+Python)?\s+modules?\b",
    flags=re.IGNORECASE,
)
CANONICAL_WRAPPER_COUNT_RE = re.compile(
    r"\b(?P<count>\d+)\s+canonical\s+wrappers?\b",
    flags=re.IGNORECASE,
)
LOCAL_API_WRAPPER_COUNT_RE = re.compile(
    r"\b(?P<count>\d+)\s+Local API contract wrappers?\b",
    flags=re.IGNORECASE,
)
WEBVIEW_NON_BROWSER_WRAPPER_COUNT_RE = re.compile(
    r"\b(?P<count>\d+)\s+browser-free WebView wrappers?\b",
    flags=re.IGNORECASE,
)

REPORTED_COUNT_DOC_PATHS = (
    "docs/inventories/API_ROUTE_INVENTORY.md",
    "docs/inventories/PACKAGING_DEPENDENCY_INVENTORY.md",
    "docs/inventories/ROOT_SCRIPT_INVENTORY.md",
    "docs/inventories/SMOKE_TEST_INVENTORY.md",
    "docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md",
    "docs/operator/OPERATOR_GLOSSARY.md",
    "docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md",
    "docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md",
    "docs/testing/TEST_COVERAGE_MATRIX.md",
    "docs/testing/VALIDATION_LADDER_RUNBOOK.md",
    "docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md",
    "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md",
)


@dataclass(frozen=True)
class DriftFinding:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path}


def repo_rel(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def python_module_for(repo_root: Path, path: Path) -> str:
    return ".".join(path.relative_to(repo_root).with_suffix("").parts)


def extract_browser_catalog_headings(text: str) -> list[str]:
    return [match.group("name") for match in BROWSER_CATALOG_HEADING_RE.finditer(text)]


def extract_reported_browser_counts(repo_root: Path, paths: list[Path]) -> list[dict[str, Any]]:
    matches: list[tuple[str, int, int, dict[str, Any]]] = []
    patterns = (
        ("canonical_wrapper_count", CANONICAL_WRAPPER_COUNT_RE),
        ("local_api_wrapper_count", LOCAL_API_WRAPPER_COUNT_RE),
        ("webview_non_browser_wrapper_count", WEBVIEW_NON_BROWSER_WRAPPER_COUNT_RE),
        ("browser_wrapper_count", BROWSER_WRAPPER_COUNT_RE),
        ("browser_module_count", BROWSER_MODULE_COUNT_RE),
        ("browser_wrapper_backed_module_count", BROWSER_WRAPPER_BACKED_MODULE_COUNT_RE),
        ("browser_direct_only_module_count", BROWSER_DIRECT_ONLY_MODULE_COUNT_RE),
    )
    for path in paths:
        text = read_text(path)
        relative_path = repo_rel(repo_root, path)
        for kind, pattern in patterns:
            for match in pattern.finditer(text):
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                if line_end < 0:
                    line_end = len(text)
                line_text = text[line_start:line_end].strip()
                if kind == "browser_module_count" and "browser" not in line_text.lower():
                    continue
                line_number = text.count("\n", 0, match.start()) + 1
                record = {
                    "kind": kind,
                    "line": line_number,
                    "matched_text": match.group(0),
                    "path": relative_path,
                    "reported_count": int(match.group("count")),
                }
                matches.append((relative_path, line_number, match.start(), record))
    return [record for _path, _line, _offset, record in sorted(matches)]


def extract_write_host_literals(text: str) -> list[str]:
    literals: list[str] = []
    for line in text.splitlines():
        match = re.search(r"\bWrite-Host\s+(['\"])(.*?)\1", line)
        if match:
            literals.append(match.group(2))
    return literals


def extract_invocation(text: str) -> tuple[str, str, str, list[str]]:
    browser_match = re.search(
        r"Invoke-WebViewBrowserSmokeUnittest\b.*?-Module\s+['\"]([^'\"]+)['\"]",
        text,
        re.DOTALL,
    )
    if browser_match:
        selector = browser_match.group(1).strip()
        return "unittest", selector, selector, [selector]

    if "& $python -m pytest" in text:
        pytest_block = text.split("& $python -m pytest", 1)[1]
        pytest_block = pytest_block.split("if ($LASTEXITCODE", 1)[0]
        cleaned = pytest_block.replace("`", " ")
        selectors = [
            token.strip().replace("\\", "/")
            for token in cleaned.split()
            if token.strip().replace("\\", "/").endswith(".py")
        ]
        selector = ", ".join(selectors)
        return "pytest", "pytest", selector, selectors

    for line in text.splitlines():
        if "& $python -m unittest " in line:
            tail = line.split("& $python -m unittest ", 1)[1].strip()
            selector = tail.split(" -q", 1)[0].strip()
            module = selector.split(".", 3)
            python_module = selector
            if len(module) >= 3 and module[0] == "tests":
                python_module = ".".join(module[:3])
            return "unittest", python_module, selector, [selector]

        direct_match = re.search(r"&\s+\$python\s+-m\s+([A-Za-z_][A-Za-z0-9_.]*)", line)
        if direct_match and direct_match.group(1) != "unittest":
            python_module = direct_match.group(1)
            return "python_module", python_module, python_module, [python_module]

    return "unknown", "", "", []


def proof_tier_for(name: str) -> str:
    if name.startswith("Test-LocalApi"):
        return "local_api_contract_smoke"
    if name.startswith("Test-WebViewBrowser"):
        return "browser_smoke"
    if name.startswith("Test-WebView"):
        return "webview_non_browser_smoke"
    return "smoke_wrapper"


def parse_wrapper(repo_root: Path, path: Path) -> dict[str, Any]:
    text = read_text(path)
    name = path.name
    invocation_kind, python_module, test_selector, test_selectors = extract_invocation(text)
    host_literals = extract_write_host_literals(text)
    boundary_lines = [item for item in host_literals if item.startswith("Boundary:")]
    browser_backed = proof_tier_for(name) == "browser_smoke"
    return {
        "allows_skipped_tests": "[switch]$AllowSkippedTests" in text,
        "boundary_lines": boundary_lines,
        "browser_backed": browser_backed,
        "invocation_kind": invocation_kind,
        "name": name,
        "path": repo_rel(repo_root, path),
        "proof_tier": proof_tier_for(name),
        "python_module": python_module,
        "test_selector": test_selector,
        "test_selectors": test_selectors,
        "uses_shared_browser_support": "Invoke-WebViewBrowserSmokeUnittest" in text,
    }


def build_smoke_wrapper_map(repo_root: Path = REPO_ROOT) -> tuple[dict[str, Any], list[DriftFinding]]:
    smoke_root = repo_root / "ops" / "scripts" / "smoke"
    release_script = repo_root / "ops" / "scripts" / "release" / "test.ps1"
    smoke_inventory = repo_root / "docs" / "inventories" / "SMOKE_TEST_INVENTORY.md"
    webview_catalog = repo_root / "docs" / "testing" / "WEBVIEW_SMOKE_TEST_CATALOG.md"
    reported_count_documents = [repo_root / path for path in REPORTED_COUNT_DOC_PATHS]

    release_text = read_text(release_script)
    smoke_inventory_text = read_text(smoke_inventory)
    webview_catalog_text = read_text(webview_catalog)

    wrappers = [parse_wrapper(repo_root, path) for path in sorted(smoke_root.glob("Test-*.ps1"))]
    browser_wrappers = [wrapper for wrapper in wrappers if wrapper["browser_backed"]]
    browser_wrapper_names = [wrapper["name"] for wrapper in browser_wrappers]
    browser_catalog_headings = extract_browser_catalog_headings(webview_catalog_text)
    browser_catalog_heading_counts = Counter(browser_catalog_headings)
    browser_catalog_heading_names = set(browser_catalog_headings)
    browser_module_paths = sorted(
        (repo_root / "tests" / "webview").rglob("test_webview_browser*.py")
    )
    browser_modules = [python_module_for(repo_root, path) for path in browser_module_paths]
    wrappers_by_module: dict[str, list[str]] = {}
    for wrapper in browser_wrappers:
        module = wrapper["python_module"]
        if module:
            wrappers_by_module.setdefault(module, []).append(wrapper["name"])
    browser_module_records = [
        {
            "coverage_kind": "wrapper_backed" if module in wrappers_by_module else "direct_only",
            "path": repo_rel(repo_root, path),
            "python_module": module,
            "wrappers": sorted(wrappers_by_module.get(module, [])),
        }
        for path, module in zip(browser_module_paths, browser_modules, strict=True)
    ]
    wrapper_backed_modules = [
        record["python_module"]
        for record in browser_module_records
        if record["coverage_kind"] == "wrapper_backed"
    ]
    direct_only_modules = [
        record["python_module"]
        for record in browser_module_records
        if record["coverage_kind"] == "direct_only"
    ]
    reported_counts = extract_reported_browser_counts(
        repo_root,
        reported_count_documents,
    )
    disk_counts = {
        "canonical_wrapper_count": len(wrappers),
        "local_api_wrapper_count": sum(
            wrapper["proof_tier"] == "local_api_contract_smoke" for wrapper in wrappers
        ),
        "webview_non_browser_wrapper_count": sum(
            wrapper["proof_tier"] == "webview_non_browser_smoke" for wrapper in wrappers
        ),
        "browser_module_count": len(browser_modules),
        "browser_wrapper_backed_module_count": len(wrapper_backed_modules),
        "browser_direct_only_module_count": len(direct_only_modules),
        "browser_wrapper_count": len(browser_wrappers),
    }
    for record in reported_counts:
        record["disk_count"] = disk_counts[record["kind"]]
        record["matches_disk"] = record["reported_count"] == record["disk_count"]

    support_files = [
        repo_rel(repo_root, path)
        for path in sorted(smoke_root.glob("*.ps1"))
        if not path.name.startswith("Test-")
    ]
    findings: list[DriftFinding] = []

    for wrapper in wrappers:
        name = wrapper["name"]
        path = wrapper["path"]
        docs = {
            "listed_in_smoke_inventory": name in smoke_inventory_text,
            "listed_in_webview_catalog": (
                name in browser_catalog_heading_names
                if wrapper["browser_backed"]
                else name in webview_catalog_text
            ),
            "listed_in_webview_catalog_heading": (
                name in browser_catalog_heading_names if wrapper["browser_backed"] else None
            ),
            "webview_catalog_required": name.startswith("Test-WebView"),
        }
        release = {"listed_in_release_layout": name in release_text}
        wrapper["docs"] = docs
        wrapper["release"] = release

        if not wrapper["python_module"]:
            findings.append(
                DriftFinding(
                    code="UNPARSED_INVOCATION",
                    path=path,
                    message="wrapper does not expose a parseable Python module or unittest selector",
                )
            )
        if not docs["listed_in_smoke_inventory"]:
            findings.append(
                DriftFinding(
                    code="MISSING_SMOKE_INVENTORY",
                    path=path,
                    message="wrapper is not referenced by docs/inventories/SMOKE_TEST_INVENTORY.md",
                )
            )
        if (
            docs["webview_catalog_required"]
            and not wrapper["browser_backed"]
            and not docs["listed_in_webview_catalog"]
        ):
            findings.append(
                DriftFinding(
                    code="MISSING_WEBVIEW_CATALOG",
                    path=path,
                    message="WebView wrapper is not referenced by docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md",
                )
            )
        if not release["listed_in_release_layout"]:
            findings.append(
                DriftFinding(
                    code="MISSING_RELEASE_LAYOUT",
                    path=path,
                    message="wrapper is not listed in ops/scripts/release/test.ps1 layout checks",
                )
            )

    for name in sorted(browser_wrapper_names):
        heading_count = browser_catalog_heading_counts[name]
        if heading_count == 0:
            findings.append(
                DriftFinding(
                    code="MISSING_BROWSER_CATALOG_HEADING",
                    path=repo_rel(repo_root, webview_catalog),
                    message=f"browser wrapper has no exact catalog heading: {name}",
                )
            )
        elif heading_count > 1:
            findings.append(
                DriftFinding(
                    code="DUPLICATE_BROWSER_CATALOG_HEADING",
                    path=repo_rel(repo_root, webview_catalog),
                    message=f"browser wrapper has {heading_count} catalog headings: {name}",
                )
            )
    browser_wrapper_name_set = set(browser_wrapper_names)
    for name in sorted(browser_catalog_heading_names - browser_wrapper_name_set):
        findings.append(
            DriftFinding(
                code="STALE_BROWSER_CATALOG_HEADING",
                path=repo_rel(repo_root, webview_catalog),
                message=f"catalog heading has no browser wrapper on disk: {name}",
            )
        )

    count_labels = {
        "canonical_wrapper_count": "canonical wrapper count",
        "local_api_wrapper_count": "Local API contract wrapper count",
        "webview_non_browser_wrapper_count": "browser-free WebView wrapper count",
        "browser_module_count": "browser module count",
        "browser_wrapper_backed_module_count": "wrapper-backed browser module count",
        "browser_direct_only_module_count": "direct-only browser module count",
        "browser_wrapper_count": "browser wrapper count",
    }
    count_codes = {
        "canonical_wrapper_count": "CANONICAL_WRAPPER_COUNT_MISMATCH",
        "local_api_wrapper_count": "LOCAL_API_WRAPPER_COUNT_MISMATCH",
        "webview_non_browser_wrapper_count": "WEBVIEW_NON_BROWSER_WRAPPER_COUNT_MISMATCH",
        "browser_module_count": "BROWSER_MODULE_COUNT_MISMATCH",
        "browser_wrapper_backed_module_count": "BROWSER_WRAPPER_BACKED_MODULE_COUNT_MISMATCH",
        "browser_direct_only_module_count": "BROWSER_DIRECT_ONLY_MODULE_COUNT_MISMATCH",
        "browser_wrapper_count": "BROWSER_WRAPPER_COUNT_MISMATCH",
    }
    for record in reported_counts:
        if record["matches_disk"]:
            continue
        findings.append(
            DriftFinding(
                code=count_codes[record["kind"]],
                path=record["path"],
                message=(
                    f"{count_labels[record['kind']]} explicitly reported "
                    f"{record['reported_count']}; disk has {record['disk_count']}"
                ),
            )
        )

    findings.sort(key=lambda finding: (finding.code, finding.path, finding.message))
    tiers = Counter(wrapper["proof_tier"] for wrapper in wrappers)
    output = {
        "browser_suite": {
            "browser_module_count": len(browser_modules),
            "browser_modules": browser_module_records,
            "browser_wrapper_count": len(browser_wrappers),
            "browser_wrappers": browser_wrapper_names,
            "catalog_heading_count": len(browser_catalog_headings),
            "catalog_unique_heading_count": len(browser_catalog_heading_names),
            "catalog_wrapper_headings": browser_catalog_headings,
            "direct_only_module_count": len(direct_only_modules),
            "direct_only_modules": direct_only_modules,
            "reported_counts": reported_counts,
            "wrapper_backed_module_count": len(wrapper_backed_modules),
            "wrapper_backed_modules": wrapper_backed_modules,
        },
        "drift_findings": [finding.as_dict() for finding in findings],
        "generated_by": RUN_COMMAND,
        "schema_version": 2,
        "source_paths": {
            "release_script": repo_rel(repo_root, release_script),
            "reported_count_documents": [
                repo_rel(repo_root, path) for path in reported_count_documents
            ],
            "smoke_inventory": repo_rel(repo_root, smoke_inventory),
            "smoke_root": repo_rel(repo_root, smoke_root),
            "webview_catalog": repo_rel(repo_root, webview_catalog),
        },
        "summary": {
            "browser_catalog_heading_count": len(browser_catalog_headings),
            "browser_direct_only_module_count": len(direct_only_modules),
            "browser_module_count": len(browser_modules),
            "browser_wrapper_backed_module_count": len(wrapper_backed_modules),
            "browser_wrapper_count": len(browser_wrappers),
            "drift_finding_count": len(findings),
            "proof_tiers": dict(sorted(tiers.items())),
            "shared_support_files": support_files,
            "wrapper_count": len(wrappers),
        },
        "wrappers": wrappers,
    }
    return output, findings


def render_smoke_wrapper_map(repo_root: Path = REPO_ROOT) -> tuple[str, list[DriftFinding]]:
    output, findings = build_smoke_wrapper_map(repo_root)
    return json.dumps(output, indent=2, sort_keys=True) + "\n", findings


def write_if_changed(path: Path, text: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def check_current(path: Path, expected: str, findings: list[DriftFinding]) -> int:
    actual = path.read_text(encoding="utf-8") if path.exists() else ""
    ok = True
    if actual != expected:
        diff = difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            fromfile=str(path.relative_to(REPO_ROOT)),
            tofile=f"{path.relative_to(REPO_ROOT)} (generated)",
            lineterm="",
        )
        print("Smoke wrapper map drift detected. Regenerate with:")
        print(f"  {RUN_COMMAND}")
        print("\n".join(list(diff)[:160]))
        ok = False
    if findings:
        print("Smoke wrapper reference drift detected:")
        for finding in findings:
            print(f"  {finding.code}: {finding.path}: {finding.message}")
        ok = False
    if ok:
        print(f"OK: {path.relative_to(REPO_ROOT)} is current and wrapper references match.")
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify generated wrapper map and references.")
    args = parser.parse_args(argv)

    expected, findings = render_smoke_wrapper_map()
    if args.check:
        return check_current(OUTPUT_PATH, expected, findings)
    changed = write_if_changed(OUTPUT_PATH, expected)
    status = "updated" if changed else "current"
    print(f"{OUTPUT_PATH.relative_to(REPO_ROOT)} {status}")
    if findings:
        print(f"Warning: generated map contains {len(findings)} drift finding(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
