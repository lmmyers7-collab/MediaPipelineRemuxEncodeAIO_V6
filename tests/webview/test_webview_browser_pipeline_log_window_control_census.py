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
            await client.send("Page.enable");
            await client.send("Page.addScriptToEvaluateOnNewDocument", {
              source: "window.MEDIA_PIPELINE_TAURI_BOOTSTRAP=Object.freeze({token:"
                + JSON.stringify(payload.token)
                + ",tokenSource:'test-tauri-initialization-script',startupWarnings:[]});",
            });
            await client.send("Page.navigate", { url: payload.pageUrl });
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(
                  document.getElementById("pipeline-log-window-follow")
                  && document.getElementById("pipeline-log-window-mode")
                  && document.getElementById("pipeline-log-window-refresh-button")
                  && typeof window.mediaPipelinePipelineLogWindow?.refreshPipelineLogWindow === "function"
                  && window.mediaPipelineApi?.apiGet
                )`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(100);
            }

            const evaluated = await client.send("Runtime.evaluate", {
              expression: `(async () => {
                const byId = (id) => document.getElementById(id);
                const follow = byId("pipeline-log-window-follow");
                const mode = byId("pipeline-log-window-mode");
                const refresh = byId("pipeline-log-window-refresh-button");
                const status = byId("pipeline-log-window-status");
                const updated = byId("pipeline-log-window-updated");
                const required = [follow, mode, refresh];
                if (required.some((node) => !node || node.hidden || node.disabled)) {
                  throw new Error("Pipeline Log controls were not visible and enabled.");
                }

                const events = [];
                for (const node of required) {
                  for (const type of ["click", "input", "change"]) {
                    node.addEventListener(type, (event) => events.push({ id: event.currentTarget.id, type }), { capture: true });
                  }
                }
                const apiCalls = [];
                const originalApiGet = window.mediaPipelineApi.apiGet;
                window.mediaPipelineApi.apiGet = async (...args) => {
                  const path = String(args[0] || "");
                  apiCalls.push(path);
                  if (path.startsWith("/api/diagnostics/tail?target=pipeline_log")) {
                    return { ok: true, text: "fixture raw pipeline log" };
                  }
                  if (path === "/api/diagnostics") {
                    return { log_tail: "fixture activity pipeline log", active_job_rows: [], active_jobs: [], worker_progress: { rows: [] } };
                  }
                  if (path === "/api/backend/close-readiness") {
                    return { safe_to_close: true, active_work: false, state: "idle" };
                  }
                  return originalApiGet(...args);
                };
                const waitFor = async (predicate, label, timeoutMs = 5000) => {
                  const stop = Date.now() + timeoutMs;
                  while (Date.now() < stop) {
                    if (predicate()) return;
                    await new Promise((resolve) => setTimeout(resolve, 25));
                  }
                  throw new Error("Timed out waiting for " + label);
                };

                follow.click();
                if (follow.checked) throw new Error("Follow did not toggle off through a physical click.");
                follow.click();
                if (!follow.checked) throw new Error("Follow did not toggle back on through a physical click.");

                mode.value = "raw";
                mode.dispatchEvent(new Event("input", { bubbles: true }));
                mode.dispatchEvent(new Event("change", { bubbles: true }));
                await waitFor(
                  () => apiCalls.some((path) => path.startsWith("/api/diagnostics/tail?target=pipeline_log")),
                  "raw-tail request",
                );
                mode.value = "activity";
                mode.dispatchEvent(new Event("input", { bubbles: true }));
                mode.dispatchEvent(new Event("change", { bubbles: true }));
                await waitFor(() => apiCalls.includes("/api/diagnostics"), "activity diagnostics request");

                const callsBeforeRefresh = apiCalls.length;
                refresh.click();
                if (!refresh.disabled) throw new Error("Refresh did not expose its in-flight disabled state.");
                await waitFor(() => !refresh.disabled && apiCalls.length > callsBeforeRefresh, "refresh completion");
                if (!updated.textContent.includes("Last refresh:")) throw new Error("Refresh did not update stable UI evidence.");

                const originalTrackedApiGet = window.mediaPipelineApi.apiGet;
                window.mediaPipelineApi.apiGet = async () => { throw new Error("injected read failure"); };
                refresh.click();
                await waitFor(() => !refresh.disabled && ["Stale", "Read failed"].includes(status.textContent), "read failure state");
                window.mediaPipelineApi.apiGet = originalTrackedApiGet;
                refresh.click();
                await waitFor(() => !refresh.disabled && !["Stale", "Read failed", "Refreshing"].includes(status.textContent), "retry recovery");

                const requiredEvents = [
                  ["pipeline-log-window-follow", "click"],
                  ["pipeline-log-window-mode", "input"],
                  ["pipeline-log-window-mode", "change"],
                  ["pipeline-log-window-refresh-button", "click"],
                ];
                for (const [id, type] of requiredEvents) {
                  if (!events.some((event) => event.id === id && event.type === type)) {
                    throw new Error("Missing physical " + type + " evidence for " + id + ".");
                  }
                }
                if (mode.value !== "activity" || follow.checked !== true) {
                  throw new Error("Pipeline Log controls did not end in the restored modeled state.");
                }
                return {
                  ok: true,
                  discovered: 3,
                  activated: 3,
                  finiteValues: { follow: [false, true], mode: ["activity", "raw"] },
                  events,
                  apiCalls,
                  finalStatus: status.textContent,
                };
              })()`,
              awaitPromise: true,
              returnByValue: true,
            });
            if (evaluated.exceptionDetails) {
              const details = evaluated.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            const errors = client.consoleEvents.filter((entry) => entry.startsWith("error:"));
            if (client.exceptions.length || errors.length) throw new Error(client.exceptions.concat(errors).join("; "));
            console.log(JSON.stringify({ ok: true, result: evaluated.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }
        main().catch((error) => { console.error(error.stack || error.message || String(error)); process.exit(1); });
        """
    )


class WebViewBrowserPipelineLogWindowControlCensus(unittest.TestCase):
    def test_read_only_auxiliary_window_controls_and_retry(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the Pipeline Log control census.")
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the Pipeline Log control census.")

        with tempfile.TemporaryDirectory() as raw_root, tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
            root = Path(raw_root)
            tmp = Path(raw_tmp)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            server = LocalApiServer(
                MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v5-test"),
                token="browser-pipeline-log-control-census-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            payload_path = tmp / "pipeline-log-control-census-payload.json"
            runner_path = tmp / "pipeline-log-control-census-runner.cjs"
            try:
                server.start()
                payload_path.write_text(
                    json.dumps(
                        {
                            "browserPath": browser_path,
                            "port": free_port(),
                            "tmpRoot": str(tmp),
                            "url": f"{server.url}/",
                            "pageUrl": f"{server.url}/assets/pipelineLogWindow.html?surface=pipeline-log",
                            "token": "browser-pipeline-log-control-census-token",
                        }
                    ),
                    encoding="utf-8",
                )
                runner_path.write_text(_runner_source(), encoding="utf-8")
                result = run_node_browser_smoke(
                    "Browser-backed Pipeline Log window control census",
                    node=node,
                    runner_path=runner_path,
                    payload_path=payload_path,
                    timeout_seconds=45,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["discovered"], 3)
        self.assertEqual(result["result"]["activated"], 3)
        self.assertEqual(result["result"]["finiteValues"]["follow"], [False, True])
        self.assertEqual(result["result"]["finiteValues"]["mode"], ["activity", "raw"])


if __name__ == "__main__":
    unittest.main()
