from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev import generate_smoke_wrapper_map
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


class SmokeWrapperMapTests(unittest.TestCase):
    def test_browser_suite_inventory_derives_wrapper_backed_and_direct_only_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "ops/scripts/smoke/Test-WebViewBrowserThingSmoke.ps1",
                "Invoke-WebViewBrowserSmokeUnittest -Module "
                "'tests.webview.test_webview_browser_thing_smoke'\n",
            )
            _write(root / "tests/webview/test_webview_browser_thing_smoke.py", "")
            _write(root / "tests/webview/test_webview_browser_direct_only_smoke.py", "")
            _write(
                root / "docs/inventories/SMOKE_TEST_INVENTORY.md",
                "There are 1 browser-backed wrappers and 2 Python modules.\n"
                "Test-WebViewBrowserThingSmoke.ps1\n",
            )
            _write(
                root / "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md",
                "### `Test-WebViewBrowserThingSmoke.ps1`\n",
            )
            _write(
                root / "ops/scripts/release/test.ps1",
                "Test-WebViewBrowserThingSmoke.ps1\n",
            )

            mapping, findings = generate_smoke_wrapper_map.build_smoke_wrapper_map(root)

        self.assertEqual(findings, [])
        browser_suite = mapping["browser_suite"]
        self.assertEqual(browser_suite["browser_wrapper_count"], 1)
        self.assertEqual(browser_suite["browser_module_count"], 2)
        self.assertEqual(browser_suite["catalog_heading_count"], 1)
        self.assertEqual(
            browser_suite["catalog_wrapper_headings"],
            ["Test-WebViewBrowserThingSmoke.ps1"],
        )
        self.assertEqual(
            browser_suite["wrapper_backed_modules"],
            ["tests.webview.test_webview_browser_thing_smoke"],
        )
        self.assertEqual(
            browser_suite["direct_only_modules"],
            ["tests.webview.test_webview_browser_direct_only_smoke"],
        )
        self.assertEqual(
            [record["reported_count"] for record in browser_suite["reported_counts"]],
            [1, 2],
        )

    def test_browser_catalog_and_reported_count_drift_are_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "ops/scripts/smoke/Test-WebViewBrowserThingSmoke.ps1",
                "Invoke-WebViewBrowserSmokeUnittest -Module "
                "'tests.webview.test_webview_browser_thing_smoke'\n",
            )
            _write(root / "tests/webview/test_webview_browser_thing_smoke.py", "")
            _write(root / "tests/webview/test_webview_browser_direct_only_smoke.py", "")
            _write(
                root / "docs/inventories/SMOKE_TEST_INVENTORY.md",
                "There are 7 browser-backed wrappers. "
                "The browser suite has 8 Python modules.\n"
                "Test-WebViewBrowserThingSmoke.ps1\n",
            )
            _write(
                root / "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md",
                "### `Test-WebViewBrowserMissingSmoke.ps1`\n",
            )
            _write(
                root / "ops/scripts/release/test.ps1",
                "Test-WebViewBrowserThingSmoke.ps1\n",
            )

            _mapping, findings = generate_smoke_wrapper_map.build_smoke_wrapper_map(root)

        self.assertEqual(
            [finding.code for finding in findings],
            [
                "BROWSER_MODULE_COUNT_MISMATCH",
                "BROWSER_WRAPPER_COUNT_MISMATCH",
                "MISSING_BROWSER_CATALOG_HEADING",
                "STALE_BROWSER_CATALOG_HEADING",
            ],
        )
        self.assertIn("reported 8; disk has 2", findings[0].message)
        self.assertIn("reported 7; disk has 1", findings[1].message)

    def test_packaging_inventory_reported_counts_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "ops/scripts/smoke/Test-WebViewBrowserThingSmoke.ps1",
                "Invoke-WebViewBrowserSmokeUnittest -Module "
                "'tests.webview.test_webview_browser_thing_smoke'\n",
            )
            _write(root / "tests/webview/test_webview_browser_thing_smoke.py", "")
            _write(
                root / "docs/inventories/SMOKE_TEST_INVENTORY.md",
                "There are 1 browser-backed wrappers and 1 Python module.\n"
                "Test-WebViewBrowserThingSmoke.ps1\n",
            )
            _write(
                root / "docs/inventories/PACKAGING_DEPENDENCY_INVENTORY.md",
                "There are 2 canonical browser wrappers and 3 browser-backed Python modules.\n",
            )
            _write(
                root / "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md",
                "### `Test-WebViewBrowserThingSmoke.ps1`\n",
            )
            _write(
                root / "ops/scripts/release/test.ps1",
                "Test-WebViewBrowserThingSmoke.ps1\n",
            )

            _mapping, findings = generate_smoke_wrapper_map.build_smoke_wrapper_map(root)

        packaging_findings = [
            finding for finding in findings if finding.path.endswith("PACKAGING_DEPENDENCY_INVENTORY.md")
        ]
        self.assertEqual(
            [finding.code for finding in packaging_findings],
            ["BROWSER_MODULE_COUNT_MISMATCH", "BROWSER_WRAPPER_COUNT_MISMATCH"],
        )

    def test_active_route_operator_and_root_inventory_counts_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "ops/scripts/smoke/Test-WebViewBrowserThingSmoke.ps1",
                "Invoke-WebViewBrowserSmokeUnittest -Module "
                "'tests.webview.test_webview_browser_thing_smoke'\n",
            )
            _write(root / "tests/webview/test_webview_browser_thing_smoke.py", "")
            _write(
                root / "docs/inventories/SMOKE_TEST_INVENTORY.md",
                "There are 1 browser-backed wrappers and 1 browser Python module.\n"
                "Test-WebViewBrowserThingSmoke.ps1\n",
            )
            _write(
                root / "docs/inventories/API_ROUTE_INVENTORY.md",
                "There are 2 canonical browser wrappers.\n",
            )
            _write(
                root / "docs/inventories/ROOT_SCRIPT_INVENTORY.md",
                "There are 3 canonical wrappers.\n",
            )
            _write(
                root / "docs/operator/OPERATOR_GLOSSARY.md",
                "There are 4 direct-only browser Python modules.\n",
            )
            _write(
                root / "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md",
                "### `Test-WebViewBrowserThingSmoke.ps1`\n",
            )
            _write(
                root / "ops/scripts/release/test.ps1",
                "Test-WebViewBrowserThingSmoke.ps1\n",
            )

            mapping, findings = generate_smoke_wrapper_map.build_smoke_wrapper_map(root)

        finding_pairs = {(finding.code, finding.path) for finding in findings}
        self.assertIn(
            ("BROWSER_WRAPPER_COUNT_MISMATCH", "docs/inventories/API_ROUTE_INVENTORY.md"),
            finding_pairs,
        )
        self.assertIn(
            ("CANONICAL_WRAPPER_COUNT_MISMATCH", "docs/inventories/ROOT_SCRIPT_INVENTORY.md"),
            finding_pairs,
        )
        self.assertIn(
            ("BROWSER_DIRECT_ONLY_MODULE_COUNT_MISMATCH", "docs/operator/OPERATOR_GLOSSARY.md"),
            finding_pairs,
        )
        self.assertEqual(
            set(mapping["source_paths"]["reported_count_documents"]),
            set(generate_smoke_wrapper_map.REPORTED_COUNT_DOC_PATHS),
        )


    def test_browser_wrapper_records_module_boundaries_and_skip_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(root / "ops/scripts/smoke/webview_browser_smoke_common.ps1", "function Invoke-WebViewBrowserSmokeUnittest {}\n")
            _write(
                root / "ops/scripts/smoke/Test-WebViewBrowserThingSmoke.ps1",
                """
param(
    [switch]$AllowSkippedTests
)
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')
Write-Host 'WebView browser thing smoke'
Write-Host 'Boundary: starts a temporary local API.'
Write-Host 'Boundary: fails when browser prerequisites are missing unless -AllowSkippedTests is explicit.'
Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_thing_smoke' -AllowSkippedTests:$AllowSkippedTests
""".strip()
                + "\n",
            )
            _write(
                root / "docs/inventories/SMOKE_TEST_INVENTORY.md",
                "`ops/scripts/smoke/Test-WebViewBrowserThingSmoke.ps1`\n",
            )
            _write(
                root / "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md",
                "### `Test-WebViewBrowserThingSmoke.ps1`\n",
            )
            _write(
                root / "ops/scripts/release/test.ps1",
                "Join-Path $script:BundleRoot 'ops/scripts/smoke\\Test-WebViewBrowserThingSmoke.ps1'\n",
            )

            mapping, findings = generate_smoke_wrapper_map.build_smoke_wrapper_map(root)

        self.assertEqual(findings, [])
        self.assertEqual(mapping["summary"]["wrapper_count"], 1)
        self.assertEqual(
            mapping["summary"]["shared_support_files"],
            ["ops/scripts/smoke/webview_browser_smoke_common.ps1"],
        )
        wrapper = mapping["wrappers"][0]
        self.assertEqual(wrapper["proof_tier"], "browser_smoke")
        self.assertEqual(wrapper["python_module"], "tests.webview.test_webview_browser_thing_smoke")
        self.assertTrue(wrapper["allows_skipped_tests"])
        self.assertTrue(wrapper["uses_shared_browser_support"])
        self.assertIn("Boundary: starts a temporary local API.", wrapper["boundary_lines"])

    def test_missing_docs_and_release_references_are_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "ops/scripts/smoke/Test-WebViewRowSmoke.ps1",
                "& $python -m unittest tests.webview.test_webview_row_smoke -q\n",
            )
            _write(root / "docs/inventories/SMOKE_TEST_INVENTORY.md", "")
            _write(root / "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md", "")
            _write(root / "ops/scripts/release/test.ps1", "")

            _mapping, findings = generate_smoke_wrapper_map.build_smoke_wrapper_map(root)

        codes = {finding.code for finding in findings}
        self.assertEqual(
            codes,
            {"MISSING_RELEASE_LAYOUT", "MISSING_SMOKE_INVENTORY", "MISSING_WEBVIEW_CATALOG"},
        )

    def test_pytest_wrapper_records_all_test_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "ops/scripts/smoke/Test-LocalApiExampleContractSmoke.ps1",
                """
& $python -m pytest `
    tests\\python\\desktop\\test_one.py `
    tests\\webview\\test_two.py `
    -q
""".lstrip(),
            )
            _write(
                root / "docs/inventories/SMOKE_TEST_INVENTORY.md",
                "`ops/scripts/smoke/Test-LocalApiExampleContractSmoke.ps1`\n",
            )
            _write(root / "docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md", "")
            _write(
                root / "ops/scripts/release/test.ps1",
                "Test-LocalApiExampleContractSmoke.ps1\n",
            )

            mapping, findings = generate_smoke_wrapper_map.build_smoke_wrapper_map(root)

        self.assertEqual(findings, [])
        wrapper = mapping["wrappers"][0]
        self.assertEqual(wrapper["invocation_kind"], "pytest")
        self.assertEqual(
            wrapper["test_selectors"],
            ["tests/python/desktop/test_one.py", "tests/webview/test_two.py"],
        )

    def test_current_generated_map_matches_renderer(self) -> None:
        expected, _findings = generate_smoke_wrapper_map.render_smoke_wrapper_map(REPO_ROOT)
        actual = generate_smoke_wrapper_map.OUTPUT_PATH.read_text(encoding="utf-8")

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
