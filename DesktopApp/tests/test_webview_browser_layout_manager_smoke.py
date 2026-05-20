from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer
from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_layout_manager_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function layoutManagerScript() {
          return `
          (async () => {
            function text(node) { return node ? String(node.textContent || "").trim() : ""; }
            function headingText(panel) {
              return text(panel.querySelector(".panel-heading h2, .panel-heading h3")).replace(/\\s+/g, " ");
            }
            function requireManagedPanel(page, heading) {
              const root = document.querySelector('[data-page-panel="' + page + '"]');
              if (!root) throw new Error("missing page " + page);
              const panels = Array.from(root.querySelectorAll("section.panel[data-panel-key]"));
              const panel = panels.find((candidate) => headingText(candidate) === heading);
              if (!panel) {
                throw new Error("missing managed panel " + page + " / " + heading + "\\nFound: " + panels.map(headingText).join(" | "));
              }
              if (!panel.querySelector(".panel-customize-bar")) throw new Error("missing customize bar for " + page + " / " + heading);
              if (panel.getAttribute("draggable") !== "true") throw new Error("panel is not draggable in customize mode: " + page + " / " + heading);
              return panel.dataset.panelKey || "";
            }
            function click(id) {
              const node = document.getElementById(id);
              if (!node) throw new Error("missing button " + id);
              node.click();
            }
            if (!document.body.classList.contains("layout-customize-mode")) click("customize-layout-btn");
            if (!document.body.classList.contains("layout-customize-mode")) throw new Error("customize mode did not activate");
            const required = {
              queue: ["Readiness", "Queue Summary", "Run History", "Pre-Launch Checklist"],
              completed: ["Flagged Items", "Size Evidence", "Proof Check", "Integrity Check", "Diagnostics Links"],
              settings: ["Staged Changes", "Active Policy", "Save Status", "Launch Impact", "Save Result"],
              diagnostics: ["Recovery Steps", "Read Order", "Impact Summary", "Related Evidence", "Contract Review"],
              launch: ["Risk Summary", "Policy Boundaries", "Start Summary", "Control Running Pipeline", "Command Review"],
              reports: ["Failure Details", "Clear Retry Blockers", "Audit Entries"],
            };
            const keys = {};
            for (const [page, headings] of Object.entries(required)) {
              window.showPage(page);
              keys[page] = headings.map((heading) => requireManagedPanel(page, heading));
            }
            const inactiveSettingsPanesVisible = Array.from(document.querySelectorAll('[data-page-panel="settings"] .settings-tab-pane'))
              .filter((pane) => !pane.classList.contains("is-active"))
              .every((pane) => getComputedStyle(pane).display !== "none");
            if (!inactiveSettingsPanesVisible) throw new Error("customize mode should expose inactive Settings subtab panes");
            const generatedCount = document.querySelectorAll("section.panel[data-layout-generated-panel='true'][data-panel-key]").length;
            if (generatedCount < 20) throw new Error("expected generated subsection panels, found " + generatedCount);
            return { generatedCount, keys };
          })();
          `;
        }

        async function main() {
          const browser = launchBrowser([
            `--remote-debugging-port=${payload.port}`,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-popup-blocking",
            "--disable-background-networking",
            "--user-data-dir=" + payload.tmpRoot + "/browser-profile",
            payload.url,
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
                expression: `Boolean(document.getElementById("customize-layout-btn") && typeof window.showPage === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const result = await client.send("Runtime.evaluate", {
              expression: layoutManagerScript(),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            await sleep(500);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }

        main().catch((error) => {
          console.error(error.stack || error.message || String(error));
          process.exit(1);
        });
        """
    )


def _run_browser_layout_manager_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView layout-manager smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-layout-manager-payload.json"
        runner_path = tmp / "browser-layout-manager-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_layout_manager_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView layout-manager smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserLayoutManagerSmokeTests(unittest.TestCase):
    def test_customize_mode_exposes_tab_and_subsection_boxes_as_draggable_panels(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView layout-manager smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-layout-manager-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_layout_manager_smoke(browser_path=browser_path, url=f"{server.url}/")
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        self.assertGreaterEqual(browser_result["generatedCount"], 20)
        self.assertIn("settings", browser_result["keys"])
        self.assertIn("completed", browser_result["keys"])


if __name__ == "__main__":
    unittest.main()
