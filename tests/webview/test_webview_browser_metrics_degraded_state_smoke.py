from __future__ import annotations

import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )


def _runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function smokeScript() {
          return `
          (() => {
            const byId = (id) => document.getElementById(id);
            const text = (id) => byId(id)?.textContent || "";
            const page = document.querySelector('[data-page-panel="metrics"]');
            const payload = (generatedAt) => ({
              schema_version: "desktop_metrics.v1",
              read_only: true,
              generated_at: generatedAt,
              availability: "available",
              error: "",
              overview: {},
              route_mix: {},
              storage: {},
              production: {},
              workers: {},
              completeness: { complete: true, status: "complete" },
              history_authority: { authoritative_source: "completed_manifest" },
              sources: { rows: [] },
            });

            if (!window.mediaPipelineMetricsView.renderMetrics(payload("2026-07-09T12:00:00Z"))) {
              throw new Error("safe metrics payload was rejected");
            }
            if (page.dataset.availability !== "available" || byId("metrics-backfill-button").disabled) {
              throw new Error("safe metrics state did not enable current backend controls");
            }

            window.mediaPipelineMetricsView.renderMetricsUnavailable("fixture metrics route timeout");
            if (page.dataset.availability !== "unavailable" || !byId("metrics-backfill-button").disabled) {
              throw new Error("unavailable metrics state did not fail closed");
            }
            if (!text("metrics-summary").includes("Historical values remain visible from 2026-07-09T12:00:00Z")
                || text("metrics-overview-status") !== "Unavailable — historical only") {
              throw new Error("unavailable metrics did not retain timestamped historical-only evidence");
            }

            if (!window.mediaPipelineMetricsView.renderMetrics(payload("2026-07-09T12:01:00Z"))) {
              throw new Error("recovered metrics payload was rejected");
            }
            if (page.dataset.availability !== "available" || byId("metrics-backfill-button").disabled
                || text("metrics-overview-status") === "Unavailable — historical only") {
              throw new Error("metrics state did not recover after fresh backend evidence");
            }
            return { ok: true, summary: text("metrics-summary"), availability: page.dataset.availability };
          })()
          `;
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new", "--disable-gpu", "--disable-background-networking", "--disable-default-apps",
            "--disable-extensions", "--disable-sync", "--metrics-recording-only", "--no-first-run",
            "--no-default-browser-check", `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`, payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.getElementById("metrics-backfill-button") && typeof window.mediaPipelineMetricsView?.renderMetrics === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const result = await client.send("Runtime.evaluate", {
              expression: smokeScript(), awaitPromise: true, returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            const errors = client.consoleEvents.filter((entry) => entry.startsWith("error:"));
            if (client.exceptions.length || errors.length) throw new Error(client.exceptions.concat(errors).join("; "));
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }
        main().catch((error) => { console.error(error.stack || error.message || String(error)); process.exit(1); });
        """
    )


class WebViewBrowserMetricsDegradedStateSmoke(unittest.TestCase):
    def test_safe_unavailable_recovered_metrics_transition_fails_closed(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Metrics smoke.")
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the browser-backed Metrics smoke.")

        with tempfile.TemporaryDirectory() as raw_root, tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
            root = Path(raw_root)
            tmp = Path(raw_tmp)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            server = LocalApiServer(
                MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v5-test"),
                token="browser-metrics-degraded-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            payload_path = tmp / "metrics-degraded-payload.json"
            runner_path = tmp / "metrics-degraded-runner.cjs"
            try:
                server.start()
                payload_path.write_text(
                    json.dumps({"browserPath": browser_path, "port": free_port(), "tmpRoot": str(tmp), "url": f"{server.url}/"}),
                    encoding="utf-8",
                )
                runner_path.write_text(_runner_source(), encoding="utf-8")
                result = run_node_browser_smoke(
                    "Browser-backed Metrics degraded-state smoke",
                    node=node,
                    runner_path=runner_path,
                    payload_path=payload_path,
                    timeout_seconds=45,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["availability"], "available")


if __name__ == "__main__":
    unittest.main()
