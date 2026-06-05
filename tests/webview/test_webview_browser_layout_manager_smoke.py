from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

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
            localStorage.removeItem("mediapipeline-layout-v1");
            function text(node) { return node ? String(node.textContent || "").trim() : ""; }
            function headingText(panel) {
              return text(panel.querySelector(".panel-heading h2, .panel-heading h3")).replace(/\\s+/g, " ");
            }
            function click(id) {
              const node = document.getElementById(id);
              if (!node) throw new Error("missing button " + id);
              node.click();
            }
            function openDrawer() {
              if (!document.body.classList.contains("layout-editor-open")) click("customize-layout-btn");
              if (!document.body.classList.contains("layout-editor-open")) throw new Error("layout editor drawer did not activate");
              const drawer = document.getElementById("layout-editor-drawer");
              if (!drawer) throw new Error("missing layout editor drawer");
              if (drawer.getAttribute("aria-hidden") !== "false") throw new Error("layout editor drawer is still aria-hidden");
              if (document.body.classList.contains("layout-customize-mode")) throw new Error("legacy inline customize mode should not activate");
            }
            function drawerRows() {
              return Array.from(document.querySelectorAll("#layout-editor-tree .layout-editor-panel-row[data-layout-editor-panel-key]"));
            }
            function drawerRowText(row) {
              return text(row.querySelector(".layout-editor-panel-name")).replace(/\\s+/g, " ");
            }
            function panelForDrawerRow(row) {
              return document.querySelector('section.panel[data-panel-key="' + row.dataset.layoutEditorPanelKey + '"]');
            }
            function drawerRowByHeading(heading) {
              return drawerRows().find((row) => drawerRowText(row) === heading);
            }
            function drawerGroupLabels() {
              return Array.from(document.querySelectorAll("#layout-editor-tree .layout-editor-group-summary"))
                .map((summary) => text(summary.querySelector("span")).replace(/\\s+/g, " "))
                .filter(Boolean);
            }
            function requireDrawerGroups(page, labels) {
              window.showPage(page);
              openDrawer();
              const found = drawerGroupLabels();
              labels.forEach((label) => {
                if (!found.includes(label)) {
                  throw new Error("missing layout drawer group " + page + " / " + label + "\\nFound: " + found.join(" | "));
                }
              });
              const genericSummaryCount = found.filter((label) => label === "Summary").length;
              if (genericSummaryCount > 1) {
                throw new Error("layout drawer has duplicate generic Summary groups for " + page + ": " + found.join(" | "));
              }
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
              if (panel.getAttribute("draggable") === "true") throw new Error("real page panel should not be draggable while drawer is open: " + page + " / " + heading);
              if (!panel.querySelector(".pcb-btn-move-up")) throw new Error("missing move-up button for " + page + " / " + heading);
              if (!panel.querySelector(".pcb-btn-move-down")) throw new Error("missing move-down button for " + page + " / " + heading);
              return panel;
            }
            function requireDrawerPanel(page, heading) {
              window.showPage(page);
              openDrawer();
              const row = drawerRowByHeading(heading);
              if (!row) {
                throw new Error("missing drawer row " + page + " / " + heading + "\\nFound: " + drawerRows().map(drawerRowText).join(" | "));
              }
              if (row.getAttribute("draggable") !== "true") throw new Error("drawer row is not draggable: " + page + " / " + heading);
              if (!row.querySelector(".layout-editor-panel-grip")) throw new Error("missing drawer drag handle: " + page + " / " + heading);
              if (!row.querySelector(".layout-editor-move-button")) throw new Error("missing drawer move controls: " + page + " / " + heading);
              return row;
            }
            function panelOrder(page) {
              return Array.from(document.querySelectorAll('[data-page-panel="' + page + '"] > section.panel[data-panel-key]')).map((panel) => headingText(panel));
            }
            function panelOrderIn(container) {
              return Array.from(container.querySelectorAll(":scope > section.panel[data-panel-key]")).map((panel) => headingText(panel));
            }
            function dragDrawerRow(sourceRow, targetRow) {
              const grip = sourceRow.querySelector(".layout-editor-panel-grip");
              const targetRect = targetRow.getBoundingClientRect();
              const dataTransfer = new DataTransfer();
              grip.dispatchEvent(new DragEvent("dragstart", { bubbles: true, cancelable: true, dataTransfer }));
              targetRow.dispatchEvent(new DragEvent("dragover", {
                bubbles: true,
                cancelable: true,
                clientY: targetRect.top + 1,
                dataTransfer,
              }));
              if (!targetRow.classList.contains("is-drop-target")) throw new Error("drawer drop target did not highlight");
              targetRow.dispatchEvent(new DragEvent("drop", {
                bubbles: true,
                cancelable: true,
                clientY: targetRect.top + 1,
                dataTransfer,
              }));
            }
            openDrawer();
            const required = {
              queue: ["Readiness", "Queue Summary", "Run History", "Pre-Launch Checklist"],
              completed: ["Output Files", "Current Output Status", "Completed History Summary", "Size Evidence", "Proof Check", "Integrity Check", "Diagnostics Links"],
              settings: ["Staged Changes", "Active Policy", "Save Status", "Launch Impact", "Save Result"],
              diagnostics: ["Recovery Steps", "Read Order", "Impact Summary", "Related Evidence", "Contract Review"],
              launch: ["Readiness", "Settings Check", "Pipeline Controller", "Start Evidence", "Start Summary", "Command Review"],
              reports: ["Error Details", "Clear Errors", "Audit Entries"],
            };
            const keys = {};
            for (const [page, headings] of Object.entries(required)) {
              window.showPage(page);
              openDrawer();
              keys[page] = headings.map((heading) => {
                const panel = requireManagedPanel(page, heading);
                const row = requireDrawerPanel(page, heading);
                return {
                  panelKey: panel.dataset.panelKey || "",
                  drawerKey: row.dataset.layoutEditorPanelKey || "",
                };
              });
            }
            window.showPage("completed");
            openDrawer();
            const completedPanes = Array.from(document.querySelectorAll('[data-page-panel="completed"] .settings-tab-pane[data-completed-tab]'));
            const completedPaneKeys = completedPanes.map((pane) => pane.dataset.completedTab).sort().join("|");
            if (completedPaneKeys !== "advanced|history|overview") throw new Error("Completed tab panes were not merged to one container per tab: " + completedPaneKeys);
            if (document.querySelector('[data-page-panel="completed"] section.panel.settings-tab-pane')) throw new Error("Completed tab panes should be containers, not draggable panels");
            requireDrawerGroups("launch", ["Readiness", "Pipeline", "Audit", "CSV Rerun", "History"]);
            requireDrawerGroups("reports", ["Failures", "Audit", "Files"]);
            const nestedCompletedPanels = Array.from(document.querySelectorAll('[data-page-panel="completed"] section.panel[data-panel-key] section.panel[data-panel-key]'));
            if (nestedCompletedPanels.length) throw new Error("Completed layout still has nested managed panels: " + nestedCompletedPanels.map(headingText).join(" | "));
            const overviewPane = document.querySelector('[data-page-panel="completed"] .settings-tab-pane[data-completed-tab="overview"]');
            const overviewHeadings = panelOrderIn(overviewPane);
            ["Output Files", "Final Library Promotion", "Selected File", "Current Output Status"].forEach((heading) => {
              if (!overviewHeadings.includes(heading)) throw new Error("Completed Overview missing movable sibling panel " + heading + "; found " + overviewHeadings.join(" | "));
            });
            window.showPage("queue");
            openDrawer();
            const beforeQueueOrder = panelOrder("queue");
            let queueSummaryRow = requireDrawerPanel("queue", "Queue Summary");
            queueSummaryRow.querySelectorAll(".layout-editor-move-button")[0].click();
            const afterQueueOrder = panelOrder("queue");
            if (beforeQueueOrder.join("|") === afterQueueOrder.join("|")) throw new Error("drawer move-up button did not reorder Queue Summary");
            const queueSummary = requireManagedPanel("queue", "Queue Summary");
            if (!queueSummary.classList.contains("panel-layout-moved")) throw new Error("move-up button did not show moved-panel animation state");
            const beforeDragOrder = panelOrder("queue");
            dragDrawerRow(requireDrawerPanel("queue", "Pre-Launch Checklist"), requireDrawerPanel("queue", "Run History"));
            const afterDragOrder = panelOrder("queue");
            if (beforeDragOrder.join("|") === afterDragOrder.join("|")) throw new Error("drawer drag/drop did not reorder panels");
            queueSummaryRow = requireDrawerPanel("queue", "Queue Summary");
            const queueSummaryPanel = panelForDrawerRow(queueSummaryRow);
            queueSummaryRow.querySelectorAll(".layout-editor-toggle-button")[0].click();
            if (!queueSummaryPanel.hasAttribute("data-panel-hidden")) throw new Error("drawer Hidden toggle did not hide Queue Summary");
            if (!text(document.getElementById("layout-editor-status")).includes("hidden")) throw new Error("drawer status did not explain hidden panel");
            requireDrawerPanel("queue", "Queue Summary").querySelectorAll(".layout-editor-toggle-button")[0].click();
            if (queueSummaryPanel.hasAttribute("data-panel-hidden")) throw new Error("drawer Hidden toggle did not restore Queue Summary");
            requireDrawerPanel("queue", "Queue Summary").querySelectorAll(".layout-editor-toggle-button")[1].click();
            if (!queueSummaryPanel.hasAttribute("data-panel-advanced")) throw new Error("drawer Advanced toggle did not gate Queue Summary");
            requireDrawerPanel("queue", "Queue Summary").querySelectorAll(".layout-editor-toggle-button")[1].click();
            if (queueSummaryPanel.hasAttribute("data-panel-advanced")) throw new Error("drawer Advanced toggle did not restore Queue Summary");
            window.showPage("completed");
            openDrawer();
            const sizeEvidenceRow = requireDrawerPanel("completed", "Size Evidence");
            sizeEvidenceRow.click();
            const advancedSelected = document.querySelector('[data-page-panel="completed"] .settings-tab-btn[data-completed-tab="advanced"]').getAttribute("aria-selected") === "true";
            if (!advancedSelected) throw new Error("selecting Size Evidence did not switch to Completed Advanced");
            const sizeEvidencePanel = panelForDrawerRow(sizeEvidenceRow);
            if (!sizeEvidencePanel.classList.contains("layout-panel-preview")) throw new Error("selected drawer row did not highlight visible panel");
            window.showPage("completed");
            openDrawer();
            const overviewPaneForReset = document.querySelector('[data-page-panel="completed"] .settings-tab-pane[data-completed-tab="overview"]');
            const beforeOverviewResetOrder = panelOrderIn(overviewPaneForReset);
            const promotionRow = requireDrawerPanel("completed", "Final Library Promotion");
            promotionRow.click();
            promotionRow.querySelectorAll(".layout-editor-move-button")[1].click();
            const movedOverviewOrder = panelOrderIn(overviewPaneForReset);
            if (beforeOverviewResetOrder.join("|") === movedOverviewOrder.join("|")) throw new Error("drawer move did not change Completed Overview order before reset");
            click("layout-editor-reset-subtab");
            const afterOverviewResetOrder = panelOrderIn(overviewPaneForReset);
            if (beforeOverviewResetOrder.join("|") !== afterOverviewResetOrder.join("|")) throw new Error("Reset Current Subtab did not restore Completed Overview order");
            window.showPage("settings");
            openDrawer();
            const inactiveSettingsPanesHidden = Array.from(document.querySelectorAll('[data-page-panel="settings"] .settings-tab-pane'))
              .filter((pane) => !pane.classList.contains("is-active"))
              .every((pane) => getComputedStyle(pane).display === "none");
            if (!inactiveSettingsPanesHidden) throw new Error("inactive Settings subtab panes should remain hidden while drawer is open");
            const generatedCount = document.querySelectorAll("section.panel[data-layout-generated-panel='true'][data-panel-key]").length;
            if (generatedCount < 20) throw new Error("expected generated subsection panels, found " + generatedCount);
            return { generatedCount, keys, beforeQueueOrder, afterQueueOrder };
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
            let appReady = false;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.readyState !== "loading" && document.getElementById("customize-layout-btn") && typeof window.showPage === "function" && document.querySelectorAll("section.panel[data-panel-key]").length > 0)`,
                returnByValue: true,
              });
              if (ready.result?.value === true) {
                appReady = true;
                break;
              }
              await sleep(150);
            }
            if (!appReady) throw new Error("Timed out waiting for layout manager initialization");
            const startupErrorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || startupErrorEvents.length) {
              throw new Error(`Browser startup console/exception noise: ${client.exceptions.concat(startupErrorEvents).join("; ")}`);
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


class WebViewBrowserLayoutManagerSmoke(unittest.TestCase):
    def test_layout_editor_drawer_manages_tab_and_subsection_boxes(self) -> None:
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
