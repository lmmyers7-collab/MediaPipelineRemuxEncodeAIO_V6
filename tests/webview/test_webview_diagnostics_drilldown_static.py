from __future__ import annotations

import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


class WebViewDiagnosticsDrilldownStaticTests(unittest.TestCase):
    def test_targetless_artifact_hints_do_not_post_empty_diagnostics_open(self) -> None:
        static_root = (
            find_repo_root(Path(__file__))
            / "apps"
            / "desktop"
            / "webview"
            / "static"
            / "assets"
        )
        diagnostics_view_js = (static_root / "diagnosticsView.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('target: ""', diagnostics_view_js)
        self.assertIn(
            'const openTarget = String(artifact.target || "").trim();',
            diagnostics_view_js,
        )
        self.assertIn("if (openTarget) {", diagnostics_view_js)
        self.assertIn("requestDiagnosticsOpen(openTarget)", diagnostics_view_js)
        self.assertNotIn("requestDiagnosticsOpen(artifact.target)", diagnostics_view_js)
        self.assertIn(
            'artifact.target || "none; use row guidance"',
            diagnostics_view_js,
        )


if __name__ == "__main__":
    unittest.main()
