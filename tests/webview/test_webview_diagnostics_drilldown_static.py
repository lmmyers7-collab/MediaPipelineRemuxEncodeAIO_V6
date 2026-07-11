from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


class WebViewDiagnosticsDrilldownStaticTests(unittest.TestCase):
    def _static_root(self) -> Path:
        return find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static" / "assets"

    def _diagnostics_partial(self) -> Path:
        return self._static_root().parent / "partials" / "page-diagnostics.html"

    def test_diagnostics_subtabs_are_overview_first(self) -> None:
        html = self._diagnostics_partial().read_text(encoding="utf-8")
        tabs = re.findall(
            r'<button type="button" class="settings-tab-btn" role="tab" data-diag-tab="([^"]+)" aria-selected="([^"]+)">([^<]+)</button>',
            html,
        )

        self.assertEqual(
            [(tab_id, label) for tab_id, _selected, label in tabs],
            [
                ("triage", "Overview"),
                ("readiness", "Readiness"),
                ("investigation", "Investigation"),
                ("logs", "Logs"),
                ("progress", "State"),
                ("advanced", "Advanced"),
            ],
        )
        self.assertEqual(tabs[0][1], "true")
        self.assertTrue(any(tab_id == "logs" and selected == "false" for tab_id, selected, _label in tabs))
        self.assertTrue(any(tab_id == "readiness" and selected == "false" for tab_id, selected, _label in tabs))
        self.assertIn('<div class="settings-tab-pane is-active" data-diag-tab="triage">', html)
        self.assertIn('<div class="settings-tab-pane" data-diag-tab="readiness">', html)
        self.assertNotIn('<div class="settings-tab-pane is-active" data-diag-tab="logs">', html)

    def test_diagnostics_overview_starts_with_first_response(self) -> None:
        html = self._diagnostics_partial().read_text(encoding="utf-8")
        expected_order = [
            "First Response",
            "Shutdown Readiness",
            "Diagnostics Overview",
            "Errors",
            "Events",
            "Active Jobs",
        ]
        positions = [html.index(f"<h2>{heading}</h2>") for heading in expected_order]

        self.assertEqual(positions, sorted(positions))
        self.assertLess(html.index("<h2>First Response</h2>"), html.index("<!-- TAB: STATE -->"))
        self.assertEqual(html.count('id="diagnostics-close-status"'), 1)
        self.assertIn(
            "Diagnostics first-response rows are read-only and do not launch, drain, save, rename, repair, delete, publish, clear state, or touch files.",
            html,
        )

    def test_diagnostics_owner_handoff_is_in_investigation_before_logs(self) -> None:
        html = self._diagnostics_partial().read_text(encoding="utf-8")

        self.assertLess(html.index("<h2>Investigation Path</h2>"), html.index("<h2>Page Handoff</h2>"))
        self.assertLess(html.index("<h2>Page Handoff</h2>"), html.index("<h2>Log Access</h2>"))
        self.assertLess(html.index("<h2>Page Handoff</h2>"), html.index("<!-- TAB: LOGS -->"))
        self.assertEqual(html.count('id="diagnostics-owner-handoff-status"'), 1)
        self.assertIn(
            "Owner-row navigation is local UI selection only and sends no backend command.",
            html,
        )

    def test_diagnostics_logs_and_advanced_panels_are_labeled_by_source_and_group(self) -> None:
        html = self._diagnostics_partial().read_text(encoding="utf-8")
        for fragment in [
            "Source: backend diagnostics pipeline log tail",
            "Target Key",
            "Byte Limit",
            "resolved label, read window, and truncation state",
            "Source: backend launch log summary from diagnostics.",
            "Lifecycle - Backend State",
            "Allowlisted File Access - Open Files",
            "Developer / Contract Evidence - API Contract",
        ]:
            self.assertIn(fragment, html)

    def test_targetless_artifact_hints_do_not_post_empty_diagnostics_open(self) -> None:
        static_root = self._static_root()
        diagnostics_view_js = "\n".join(
            (static_root / name).read_text(encoding="utf-8")
            for name in ("diagnostics/triage.js", "diagnosticsView.js")
        )

        self.assertIn('target: ""', diagnostics_view_js)
        self.assertIn(
            'const openTarget = String(artifact.target || "").trim();',
            diagnostics_view_js,
        )
        self.assertIn("if (openTarget) {", diagnostics_view_js)
        self.assertIn("requestDiagnosticsOpen(openTarget, button)", diagnostics_view_js)
        self.assertNotIn("requestDiagnosticsOpen(artifact.target)", diagnostics_view_js)
        self.assertIn(
            'artifact.target || "none; use row guidance"',
            diagnostics_view_js,
        )

    def test_diagnostics_tail_fallback_ignores_negated_error_phrases(self) -> None:
        diagnostics_tail_js = self._static_root() / "diagnosticsTailView.js"
        source = diagnostics_tail_js.read_text(encoding="utf-8")

        self.assertIn("diagnosticsTailLineHasNegatedError", source)
        self.assertIn("diagnosticsTailLineContainsTerm", source)
        self.assertIn("error[_ -]?count", source)

        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available for WebView diagnostics tail fallback smoke")
        script = f"""
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
const source = fs.readFileSync({json.dumps(str(diagnostics_tail_js))}, "utf8");
const context = {{ window: {{}} }};
vm.createContext(context);
vm.runInContext(source, context);
const evidence = context.window.mediaPipelineDiagnosticsTailView.diagnosticsTailEvidence({{
  ok: true,
  exists: true,
  is_file: true,
  text: "completed without errors\\nNo recent pipeline errors found.\\nerror_count=0\\n"
}});
assert.strictEqual(evidence.operator_status, "ready");
assert.strictEqual(evidence.error_count, 0);
const blocked = context.window.mediaPipelineDiagnosticsTailView.diagnosticsTailEvidence({{
  ok: true,
  exists: true,
  is_file: true,
  text: "completed without errors\\nfatal mux failure\\n"
}});
assert.strictEqual(blocked.operator_status, "blocked");
assert.ok(blocked.error_count > 0);
"""
        subprocess.run([node, "-e", script], check=True, text=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
