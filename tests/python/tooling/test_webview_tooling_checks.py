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
