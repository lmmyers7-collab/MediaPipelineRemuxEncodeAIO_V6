from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from mediapipeline.tools.dev import browser_smoke_inventory
from mediapipeline.tools.paths import find_repo_root


PROJECT_ROOT = find_repo_root(Path(__file__))
WORKFLOWS = (
    PROJECT_ROOT / ".github" / "workflows" / "phase1-drift.yml",
    PROJECT_ROOT / ".github" / "workflows" / "deep-audit.yml",
)


def _write_browser_test(path: Path, class_name: str, *method_names: str) -> None:
    methods = "\n".join(f"    def {name}(self):\n        pass" for name in method_names)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"import unittest\n\nclass {class_name}(unittest.TestCase):\n{methods}\n",
        encoding="utf-8",
    )


def _flatten_suite(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    cases: list[unittest.TestCase] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            cases.extend(_flatten_suite(item))
        else:
            cases.append(item)
    return cases


class BrowserSmokeInventoryTests(unittest.TestCase):
    def test_discovery_includes_every_matching_module_and_test_method(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_browser_test(
                root / "tests" / "webview" / "test_webview_browser_alpha_smoke.py",
                "AlphaSmoke",
                "test_first",
                "test_second",
            )
            _write_browser_test(
                root / "tests" / "webview" / "test_webview_browser_run_monitor_smoke.py",
                "RunMonitorSmoke",
                "test_monitor",
            )

            inventory = browser_smoke_inventory.discover_browser_smoke_inventory(root)

        self.assertEqual(
            inventory.modules,
            (
                "tests.webview.test_webview_browser_alpha_smoke",
                "tests.webview.test_webview_browser_run_monitor_smoke",
            ),
        )
        self.assertEqual(
            inventory.selectors,
            (
                "tests.webview.test_webview_browser_alpha_smoke.AlphaSmoke.test_first",
                "tests.webview.test_webview_browser_alpha_smoke.AlphaSmoke.test_second",
                "tests.webview.test_webview_browser_run_monitor_smoke.RunMonitorSmoke.test_monitor",
            ),
        )
        self.assertEqual(
            inventory.github_matrix(),
            {"include": [{"test_id": selector} for selector in inventory.selectors]},
        )

    def test_discovery_fails_when_matching_module_has_no_tests(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            path = root / "tests" / "webview" / "test_webview_browser_empty_smoke.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("import unittest\n", encoding="utf-8")

            with self.assertRaisesRegex(browser_smoke_inventory.BrowserSmokeInventoryError, "no unittest.TestCase test methods"):
                browser_smoke_inventory.discover_browser_smoke_inventory(root)

    def test_github_matrix_cli_is_compact_and_nonempty(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_browser_test(
                root / "tests" / "webview" / "test_webview_browser_direct_census.py",
                "DirectCensus",
                "test_controls",
            )
            output = StringIO()
            with redirect_stdout(output):
                exit_code = browser_smoke_inventory.main(
                    ["--repo-root", str(root), "--format", "github-matrix"]
                )

        self.assertEqual(exit_code, 0)
        self.assertNotIn("\n", output.getvalue().rstrip("\n"))
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "include": [
                    {
                        "test_id": "tests.webview.test_webview_browser_direct_census.DirectCensus.test_controls",
                    }
                ]
            },
        )

    def test_current_inventory_resolves_through_unittest_and_includes_required_direct_modules(self) -> None:
        inventory = browser_smoke_inventory.discover_browser_smoke_inventory(PROJECT_ROOT)
        required = {
            "tests.webview.test_webview_browser_evidence_control_census.WebViewBrowserEvidenceControlCensus.test_disposable_backend_rendered_control_census",
            "tests.webview.test_webview_browser_root_control_census.WebViewBrowserRootControlCensus.test_root_surface_controls_have_zero_unclassified_and_safe_local_controls_activate",
            "tests.webview.test_webview_browser_run_monitor_smoke.WebViewBrowserRunMonitorSmoke.test_backend_queue_run_monitor_states_focus_and_narrow_layout",
            "tests.webview.test_webview_browser_settings_generated_control_census.WebViewBrowserSettingsGeneratedControlCensus.test_generated_controls_are_fully_classified_and_safe_instances_activate",
            "tests.webview.test_webview_browser_shell_launch_queue_rename_control_census.WebViewBrowserShellLaunchQueueRenameControlCensus.test_backend_served_control_census_is_complete_and_non_mutating",
        }
        self.assertTrue(required.issubset(inventory.selectors), sorted(required - set(inventory.selectors)))

        loader = unittest.TestLoader()
        unresolved: list[str] = []
        for selector in inventory.selectors:
            cases = _flatten_suite(loader.loadTestsFromName(selector))
            if len(cases) != 1 or cases[0].id() != selector:
                unresolved.append(selector)
        self.assertEqual(unresolved, [])

    @unittest.skipUnless(
        all(path.is_file() for path in WORKFLOWS),
        "source CI workflows are unavailable in the release package",
    )
    def test_workflows_consume_the_complete_discovered_matrix_through_strict_wrapper(self) -> None:
        discovery_command = "python -m mediapipeline.tools.dev.browser_smoke_inventory --format github-matrix"
        dynamic_matrix = "matrix: ${{ fromJSON(needs.browser-test-inventory.outputs.matrix) }}"
        strict_invocation = "Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $PWD.Path -Module '${{ matrix.test_id }}'"
        literal_selector = "          - tests.webview.test_webview_browser"

        for path in WORKFLOWS:
            with self.subTest(workflow=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertEqual(source.count(discovery_command), 1)
                self.assertEqual(source.count(dynamic_matrix), 1)
                self.assertEqual(source.count(strict_invocation), 1)
                self.assertNotIn(literal_selector, source)
                self.assertNotIn('run: python -m unittest "${{ matrix.test_id }}" -q', source)
                self.assertNotIn("-AllowSkippedTests", source)


if __name__ == "__main__":
    unittest.main()
