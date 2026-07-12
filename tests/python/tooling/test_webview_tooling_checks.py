from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

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
