from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api.static_files import render_index
from mediapipeline_desktop_app.api.static_files_policy import (
    STATIC_INDEX_BOOTSTRAP_PLACEHOLDER,
    local_api_bootstrap,
    missing_bootstrap_placeholder_response,
    missing_index_response,
    render_index_html,
    render_static_includes,
    static_error_response,
    static_not_found_response,
)


class LocalApiStaticFilesPolicyTests(unittest.TestCase):
    def test_local_api_bootstrap_includes_token_only_when_required(self) -> None:
        required = local_api_bootstrap(token="secret", require_token=True, app_version="v5-test")
        disabled = local_api_bootstrap(token="secret", require_token=False, app_version="v5-test", shell_surface="tauri")
        tauri = local_api_bootstrap(token="secret", require_token=True, app_version="v5-test", shell_surface="tauri")

        self.assertEqual(required, {"apiBase": "", "token": "secret", "appVersion": "v5-test", "shellSurface": "webview"})
        self.assertEqual(disabled, {"apiBase": "", "token": "", "appVersion": "v5-test", "shellSurface": "tauri"})
        self.assertEqual(
            tauri,
            {
                "apiBase": "",
                "token": "",
                "appVersion": "v5-test",
                "shellSurface": "tauri",
                "tokenSource": "tauri-initialization-script",
            },
        )

    def test_render_index_html_replaces_bootstrap_placeholder(self) -> None:
        body = render_index_html(
            f"window.MEDIA_PIPELINE_BOOTSTRAP = {STATIC_INDEX_BOOTSTRAP_PLACEHOLDER};",
            {"token": "secret", "appVersion": "v5-test"},
        ).decode("utf-8")

        self.assertIn('"token": "secret"', body)
        self.assertIn('"appVersion": "v5-test"', body)
        self.assertNotIn(STATIC_INDEX_BOOTSTRAP_PLACEHOLDER, body)

    def test_render_index_html_escapes_script_breakout_json(self) -> None:
        body = render_index_html(
            f"<script>window.MEDIA_PIPELINE_BOOTSTRAP = {STATIC_INDEX_BOOTSTRAP_PLACEHOLDER};</script>",
            {"token": "</script><img src=x onerror=alert(1)>", "line": "\u2028"},
        ).decode("utf-8")

        self.assertNotIn("</script><img", body)
        self.assertIn("\\u003c/script\\u003e", body)
        json_text = body.split(" = ", 1)[1].split(";</script>", 1)[0]
        parsed = json.loads(json_text)
        self.assertEqual(parsed["token"], "</script><img src=x onerror=alert(1)>")

    def test_render_index_rejects_missing_bootstrap_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "index.html").write_text("<html><body>missing bootstrap</body></html>", encoding="utf-8")

            response = render_index(root, {"token": "secret"})

        self.assertEqual(response.status, 500)
        self.assertIn(b"bootstrap placeholder", response.body)

    def test_render_index_expands_static_partials_before_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            partials = root / "partials"
            partials.mkdir()
            (partials / "shell.html").write_text(
                "<div id=\"app-version\">V6</div>\n"
                f"window.MEDIA_PIPELINE_BOOTSTRAP = {STATIC_INDEX_BOOTSTRAP_PLACEHOLDER};",
                encoding="utf-8",
            )
            (root / "index.html").write_text("<!-- mp-include: partials/shell.html -->", encoding="utf-8")

            response = render_index(root, {"token": "secret", "appVersion": "v5-test"})

        self.assertEqual(response.status, 200)
        body = response.body.decode("utf-8")
        self.assertIn('id="app-version"', body)
        self.assertIn('"token": "secret"', body)
        self.assertNotIn("mp-include", body)
        self.assertNotIn(STATIC_INDEX_BOOTSTRAP_PLACEHOLDER, body)

    def test_render_index_expands_webview_page_partials(self) -> None:
        static_root = Path(__file__).resolve().parents[1] / "mediapipeline_desktop_app" / "ui_web" / "static"

        response = render_index(static_root, {"token": "secret", "appVersion": "v5-test"})

        self.assertEqual(response.status, 200)
        body = response.body.decode("utf-8")
        self.assertIn('<div class="app-shell">', body)
        self.assertIn('data-page-panel="home"', body)
        self.assertIn('id="daily-driver-status"', body)
        self.assertIn('id="daily-driver-rows"', body)
        self.assertIn('id="home-active-work-status"', body)
        self.assertIn('id="sample-validation-status"', body)
        self.assertIn('id="sample-validation-worksheet-rows"', body)
        self.assertIn('id="sample-validation-preview-button"', body)
        self.assertIn('id="sample-validation-append-button"', body)
        self.assertIn('id="sample-validation-records"', body)
        self.assertIn('data-page-panel="live"', body)
        self.assertIn('id="telemetry-readiness-status"', body)
        self.assertIn('id="cpu-chart"', body)
        self.assertIn('id="gpu-rows"', body)
        self.assertIn('data-page-panel="queue"', body)
        self.assertIn('class="workflow-table queue-table"', body)
        self.assertIn('id="queue-rows"', body)
        self.assertIn('id="queue-backend-scope-rows"', body)
        self.assertIn('id="queue-launch-decision-rows"', body)
        self.assertIn('data-page-panel="reports"', body)
        self.assertIn('id="failure-rows"', body)
        self.assertIn('id="audit-preview-rows"', body)
        self.assertIn('id="report-open-history"', body)
        self.assertIn('data-page-panel="rename"', body)
        self.assertIn('id="rename-rows"', body)
        self.assertIn('id="rename-apply-readiness-rows"', body)
        self.assertIn('id="rename-apply-outcome-rows"', body)
        self.assertIn('data-page-panel="launch"', body)
        self.assertIn('id="launch-backend-preflight-rows"', body)
        self.assertIn('id="launch-start-decision-rows"', body)
        self.assertIn('id="launch-command-review-rows"', body)
        self.assertIn('data-page-panel="completed"', body)
        self.assertIn('class="workflow-table completed-table"', body)
        self.assertIn('id="completed-rows"', body)
        self.assertIn('id="completed-history-rows"', body)
        self.assertIn('id="completed-refresh-current-output-button"', body)
        self.assertIn('id="completed-history-filter"', body)
        self.assertIn('output-overview-section-current', body)
        self.assertIn('output-overview-section-history', body)
        self.assertIn('id="completed-real-media-proof-rows"', body)
        self.assertIn('id="completed-output-acceptance-rows"', body)
        self.assertIn('id="completed-copy-evidence-button"', body)
        self.assertIn('History</button>', body)
        self.assertIn('Advanced</button>', body)
        self.assertIn('id="completed-reconciliation-hint"', body)
        self.assertIn('data-page-panel="pending"', body)
        self.assertIn('class="workflow-table pending-table"', body)
        self.assertIn('id="pending-rows"', body)
        self.assertIn('id="pending-drain-button"', body)
        self.assertIn('id="pending-drain-decision-rows"', body)
        self.assertIn('id="pending-post-drain-trust-rows"', body)
        self.assertIn('data-page-panel="schedule"', body)
        self.assertIn('id="schedule-editor-preview-button"', body)
        self.assertIn('id="schedule-day-rows"', body)
        self.assertIn('data-page-panel="network"', body)
        self.assertIn('id="network-worker-status-filter"', body)
        self.assertIn('id="network-worker-rows"', body)
        self.assertIn('id="network-lifecycle-rows"', body)
        self.assertIn('data-page-panel="maintenance"', body)
        self.assertIn('id="maintenance-refresh-button"', body)
        self.assertIn('id="release-dry-run-button"', body)
        self.assertIn('id="release-build-button"', body)
        self.assertIn('id="backfill-dry-run-button"', body)
        self.assertIn('id="dependency-atlas-button"', body)
        self.assertIn('data-page-panel="diagnostics"', body)
        self.assertIn('id="diagnostics-triage-status"', body)
        self.assertIn('id="diagnostics-log-rows"', body)
        self.assertIn('id="diagnostics-command-drilldown-rows"', body)
        self.assertIn('id="backend-shutdown-button"', body)
        self.assertIn('id="api-contract-rows"', body)
        self.assertIn('data-page-panel="libraries"', body)
        self.assertIn('id="settings-library-profile-list"', body)
        self.assertIn('id="settings-library-save-button"', body)
        self.assertIn('data-page-panel="settings"', body)
        self.assertIn('id="settings-validate-button"', body)
        self.assertIn('id="settings-patch-json"', body)
        self.assertIn('id="settings-save-patch-button"', body)
        self.assertIn('id="settings-audio-builder-status"', body)
        self.assertIn("Stages audio builder values into Changes JSON", body)
        self.assertIn("Preview/Save still run backend validation", body)
        self.assertIn('id="settings-network-builder-status"', body)
        self.assertIn('id="settings-raw-triage-rows"', body)
        self.assertIn('"token": "secret"', body)
        self.assertNotIn("mp-include", body)

    def test_render_static_includes_rejects_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)

            with self.assertRaises(ValueError):
                render_static_includes("<!-- mp-include: ../outside.html -->", root)
            with self.assertRaises(ValueError):
                render_static_includes("<!-- mp-include: assets/app.html -->", root)

    def test_static_response_helpers_preserve_status_and_content_type(self) -> None:
        missing = missing_index_response()
        missing_placeholder = missing_bootstrap_placeholder_response()
        not_found = static_not_found_response()
        error = static_error_response(RuntimeError("failed"))

        self.assertEqual(missing.status, 404)
        self.assertIn(b"not installed", missing.body)
        self.assertEqual(missing_placeholder.status, 500)
        self.assertIn(b"bootstrap placeholder", missing_placeholder.body)
        self.assertEqual(not_found.status, 404)
        self.assertEqual(not_found.body, b"not found")
        self.assertEqual(error.status, 500)
        self.assertEqual(error.body, b"failed")
        self.assertEqual(error.content_type, "text/plain; charset=utf-8")
        long_error = static_error_response(RuntimeError("x" * 2500))
        self.assertEqual(long_error.body, (("x" * 1997) + "...").encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
