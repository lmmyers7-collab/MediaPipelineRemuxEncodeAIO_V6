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

    def test_current_generated_map_is_current_and_drift_free(self) -> None:
        expected, findings = generate_smoke_wrapper_map.render_smoke_wrapper_map(REPO_ROOT)
        actual = generate_smoke_wrapper_map.OUTPUT_PATH.read_text(encoding="utf-8")

        self.assertEqual(findings, [])
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
