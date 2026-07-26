from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))


def _node() -> str:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is required for WebView tooling checks.")
    return node


def _require_webview_tooling_dependencies() -> None:
    if not (REPO_ROOT / "node_modules" / "@babel" / "parser").exists():
        raise unittest.SkipTest("WebView Node dev dependencies are omitted from release packages.")


class WebViewToolingCheckTests(unittest.TestCase):
    def _run_lint_budget_module(self, body: str) -> subprocess.CompletedProcess[str]:
        _require_webview_tooling_dependencies()
        module_uri = (
            REPO_ROOT / "ops" / "scripts" / "dev" / "check-webview-lint-budget.mjs"
        ).as_uri()
        script = f"import * as budget from {json.dumps(module_uri)};{body}"
        return subprocess.run(
            [_node(), "--input-type=module", "-e", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_webview_dependency_guard_skips_package_without_node_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(f"{__name__}.REPO_ROOT", Path(temp_dir)):
            with self.assertRaises(unittest.SkipTest):
                _require_webview_tooling_dependencies()

    def test_lint_budget_v2_tracks_no_undef_by_file_and_identifier(self) -> None:
        fixture_path = (REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "fixture.js").as_posix()
        result = self._run_lint_budget_module(
            f"""
            const summary = budget.summarize([{{
              filePath: {json.dumps(fixture_path)},
              warningCount: 3,
              errorCount: 0,
              messages: [
                {{ ruleId: "no-undef", severity: 1, message: "'missingThing' is not defined." }},
                {{ ruleId: "no-undef", severity: 1, message: "'missingThing' is not defined." }},
                {{ ruleId: "complexity", severity: 1, message: "too complex" }},
              ],
            }}]);
            console.log(JSON.stringify(summary));
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout.strip())
        self.assertEqual(summary["schema_version"], "webview_eslint_warning_budget.v2")
        self.assertEqual(summary["files"][0]["rules"], {"complexity": 1, "no-undef": 2})
        self.assertEqual(
            summary["no_undef_pairs"],
            [
                {
                    "path": "apps/desktop/webview/static/assets/fixture.js",
                    "identifier": "missingThing",
                    "warnings": 2,
                }
            ],
        )

    def test_lint_budget_rejects_malformed_no_undef_messages(self) -> None:
        fixture_path = (REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "fixture.js").as_posix()
        result = self._run_lint_budget_module(
            f"""
            budget.summarize([{{
              filePath: {json.dumps(fixture_path)},
              warningCount: 1,
              errorCount: 0,
              messages: [{{ ruleId: "no-undef", severity: 1, message: "unexpected formatter output" }}],
            }}]);
            """
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Malformed no-undef message", result.stderr)

    def test_lint_budget_detects_new_moved_swapped_and_repeated_no_undef_pairs(self) -> None:
        result = self._run_lint_budget_module(
            """
            const baseline = {
              schema_version: "webview_eslint_warning_budget.v2",
              no_undef_pairs: [
                { path: "a.js", identifier: "alpha", warnings: 1 },
                { path: "b.js", identifier: "beta", warnings: 1 },
              ],
            };
            const current = {
              schema_version: "webview_eslint_warning_budget.v2",
              no_undef_pairs: [
                { path: "a.js", identifier: "beta", warnings: 1 },
                { path: "b.js", identifier: "alpha", warnings: 1 },
                { path: "c.js", identifier: "gamma", warnings: 2 },
              ],
            };
            console.log(JSON.stringify(budget.compareNoUndefPairs(current, baseline)));
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        drift = json.loads(result.stdout.strip())
        self.assertEqual(
            {(entry["path"], entry["identifier"], entry["current"]) for entry in drift["increased"]},
            {("a.js", "beta", 1), ("b.js", "alpha", 1), ("c.js", "gamma", 2)},
        )
        self.assertEqual(
            {(entry["path"], entry["identifier"]) for entry in drift["decreased"]},
            {("a.js", "alpha"), ("b.js", "beta")},
        )

    def test_lint_budget_requires_dedicated_ratchet_and_never_blesses_increases(self) -> None:
        result = self._run_lint_budget_module(
            """
            const baseline = {
              schema_version: "webview_eslint_warning_budget.v2",
              no_undef_pairs: [{ path: "a.js", identifier: "alpha", warnings: 2 }],
            };
            const improved = {
              schema_version: "webview_eslint_warning_budget.v2",
              no_undef_pairs: [{ path: "a.js", identifier: "alpha", warnings: 1 }],
            };
            const increased = {
              schema_version: "webview_eslint_warning_budget.v2",
              no_undef_pairs: [{ path: "a.js", identifier: "alpha", warnings: 3 }],
            };
            const baselineBudget = {
              ...baseline,
              total_warnings: 2,
              total_errors: 0,
              by_rule: { "no-undef": { warnings: 2, errors: 0 } },
              files: [{ path: "a.js", warnings: 2, errors: 0, rules: { "no-undef": 2 } }],
            };
            const increasedBudget = {
              ...increased,
              total_warnings: 3,
              total_errors: 0,
              by_rule: { "no-undef": { warnings: 3, errors: 0 } },
              files: [{ path: "a.js", warnings: 3, errors: 0, rules: { "no-undef": 3 } }],
            };
            console.log(JSON.stringify({
              checkImproved: budget.noUndefRatchetFailures(improved, baseline, "check"),
              writeImproved: budget.noUndefRatchetFailures(improved, baseline, "write"),
              ratchetImproved: budget.noUndefRatchetFailures(improved, baseline, "ratchet"),
              writeIncreased: budget.noUndefRatchetFailures(increased, baseline, "write"),
              ratchetIncreased: budget.noUndefRatchetFailures(increased, baseline, "ratchet"),
              fullWriteIncreased: budget.budgetFailures(increasedBudget, baselineBudget, "write"),
            }));
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        outcomes = json.loads(result.stdout.strip())
        self.assertTrue(any("ratchet" in failure for failure in outcomes["checkImproved"]))
        self.assertTrue(any("ratchet" in failure for failure in outcomes["writeImproved"]))
        self.assertEqual(outcomes["ratchetImproved"], [])
        self.assertTrue(any("increased" in failure for failure in outcomes["writeIncreased"]))
        self.assertTrue(any("increased" in failure for failure in outcomes["ratchetIncreased"]))
        self.assertTrue(any("no-undef pair increased" in failure for failure in outcomes["fullWriteIncreased"]))

    def test_lint_budget_rejects_warning_moves_between_files(self) -> None:
        result = self._run_lint_budget_module(
            """
            const common = {
              schema_version: "webview_eslint_warning_budget.v2",
              total_warnings: 2,
              total_errors: 0,
              by_rule: { complexity: { warnings: 2, errors: 0 } },
              no_undef_pairs: [],
            };
            const baseline = {
              ...common,
              files: [{ path: "a.js", warnings: 2, errors: 0, rules: { complexity: 2 } }],
            };
            const current = {
              ...common,
              files: [
                { path: "a.js", warnings: 1, errors: 0, rules: { complexity: 1 } },
                { path: "b.js", warnings: 1, errors: 0, rules: { complexity: 1 } },
              ],
            };
            console.log(JSON.stringify(budget.budgetFailures(current, baseline, "check")));
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        failures = json.loads(result.stdout.strip())
        self.assertTrue(any("b.js complexity warnings increased: 1 > 0" in failure for failure in failures))

    def test_lint_budget_v1_migration_requires_the_dedicated_ratchet(self) -> None:
        result = self._run_lint_budget_module(
            """
            const baseline = {
              schema_version: "webview_eslint_warning_budget.v1",
              by_rule: { "no-undef": { warnings: 2, errors: 0 } },
            };
            const improved = {
              schema_version: "webview_eslint_warning_budget.v2",
              by_rule: { "no-undef": { warnings: 1, errors: 0 } },
              no_undef_pairs: [{ path: "a.js", identifier: "alpha", warnings: 1 }],
            };
            const increased = {
              ...improved,
              by_rule: { "no-undef": { warnings: 3, errors: 0 } },
              no_undef_pairs: [{ path: "a.js", identifier: "alpha", warnings: 3 }],
            };
            console.log(JSON.stringify({
              checkImproved: budget.noUndefRatchetFailures(improved, baseline, "check"),
              ratchetImproved: budget.noUndefRatchetFailures(improved, baseline, "ratchet"),
              ratchetIncreased: budget.noUndefRatchetFailures(increased, baseline, "ratchet"),
            }));
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        outcomes = json.loads(result.stdout.strip())
        self.assertTrue(any("migrate" in failure for failure in outcomes["checkImproved"]))
        self.assertEqual(outcomes["ratchetImproved"], [])
        self.assertTrue(any("increased" in failure for failure in outcomes["ratchetIncreased"]))

    def test_package_exposes_dedicated_no_undef_ratchet(self) -> None:
        package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(
            package["scripts"]["webview:lint:no-undef:ratchet"],
            "node ops/scripts/dev/check-webview-lint-budget.mjs --ratchet-no-undef",
        )

    def test_command_boundary_scans_split_command_contract_modules(self) -> None:
        source = (
            REPO_ROOT / "ops" / "scripts" / "dev" / "check-webview-command-boundary.mjs"
        ).read_text(encoding="utf-8")

        for module_name in (
            "contract_command_file.py",
            "contract_command_network.py",
            "contract_command_operations.py",
            "contract_command_process.py",
            "contract_command_settings_ui.py",
        ):
            self.assertIn(module_name, source)
        self.assertNotIn('"src/mediapipeline/desktop/api/contract_command.py"', source)

    def test_command_boundary_keeps_disabled_network_future_controls_unreachable(self) -> None:
        source = (
            REPO_ROOT / "ops" / "scripts" / "dev" / "check-webview-command-boundary.mjs"
        ).read_text(encoding="utf-8")

        future_guard = source.index('Object.hasOwn(control.attrs, "data-network-future-control")')
        route_matching = source.index("for (const rule of routeHintRules)", future_guard)
        self.assertLess(future_guard, route_matching)

    def test_route_ownership_recognizes_settings_split_directory(self) -> None:
        source = (
            REPO_ROOT / "ops" / "scripts" / "dev" / "check-webview-route-ownership.mjs"
        ).read_text(encoding="utf-8")

        self.assertIn('path.includes("/assets/settings/")', source)

    def test_godfile_analyzer_normalizes_source_and_report_line_endings(self) -> None:
        source = (
            REPO_ROOT / "ops" / "scripts" / "dev" / "analyze-webview-godfiles.mjs"
        ).read_text(encoding="utf-8")

        self.assertIn("function normalizeLineEndings(text)", source)
        self.assertIn(
            'const source = normalizeLineEndings(readFileSync(absolute, "utf-8"));',
            source,
        )
        self.assertIn(
            '? normalizeLineEndings(readFileSync(absolute, "utf-8"))',
            source,
        )

    def test_shared_generated_output_check_is_line_ending_stable(self) -> None:
        _require_webview_tooling_dependencies()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "generated.txt"
            output_path.write_bytes(b"one\r\ntwo\r\n")
            script = (
                "import { writeOrCheckText } from "
                "'./ops/scripts/dev/webview-tooling-common.mjs';"
                f"process.exitCode = writeOrCheckText({json.dumps(str(output_path))}, "
                "'one\\ntwo\\n', true);"
            )
            result = subprocess.run(
                [_node(), "--input-type=module", "-e", script],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("is current", result.stdout)

    def test_shared_parse_script_fails_on_recoverable_parser_error(self) -> None:
        _require_webview_tooling_dependencies()
        script = (
            "import { parseScript } from './ops/scripts/dev/webview-tooling-common.mjs';"
            "parseScript('let duplicate = 1; let duplicate = 2;', 'duplicate.js');"
        )

        result = subprocess.run(
            [_node(), "--input-type=module", "-e", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Recoverable parser error", result.stderr)
        self.assertIn("duplicate.js", result.stderr)

    def test_godfile_analyzer_fails_on_recoverable_parser_error(self) -> None:
        _require_webview_tooling_dependencies()
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_script = Path(temp_dir) / "duplicate.js"
            bad_script.write_text("let duplicate = 1;\nlet duplicate = 2;\n", encoding="utf-8")

            result = subprocess.run(
                [
                    _node(),
                    "ops/scripts/dev/analyze-webview-godfiles.mjs",
                    "--files",
                    str(bad_script),
                    "--json",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Recoverable parser error", result.stderr)
        self.assertIn("duplicate.js", result.stderr)


if __name__ == "__main__":
    unittest.main()
