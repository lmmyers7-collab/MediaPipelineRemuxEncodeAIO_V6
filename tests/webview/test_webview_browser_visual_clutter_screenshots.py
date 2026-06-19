from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime
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


EXPECTED_DESKTOP_SCREENSHOT_COUNT = 39


def _browser_visual_clutter_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        const path = require("path");

        const CAPTURE_MATRIX = [
          { page: "home", label: "Home" },
          {
            page: "launch",
            label: "Launch",
            tabs: [
              ["pipeline", "Pipeline Processor"],
              ["audit", "Audit"],
              ["rerun", "CSV Rerun"],
              ["history", "History"],
              ["readiness", "Readiness"],
            ],
          },
          { page: "live", label: "Telemetry" },
          {
            page: "metrics",
            label: "Metrics",
            tabs: [
              ["overview", "Overview"],
              ["routes", "Remux vs Encode"],
              ["storage", "Storage"],
              ["production", "Production"],
              ["workers", "Workers"],
            ],
          },
          { page: "queue", label: "Queue" },
          {
            page: "completed",
            label: "Completed Output",
            tabs: [
              ["overview", "Overview"],
              ["history", "History"],
              ["evidence", "Evidence"],
            ],
          },
          { page: "pending", label: "Pending Publish" },
          { page: "rename", label: "Rename" },
          {
            page: "reports",
            label: "Reports",
            tabs: [
              ["failures", "Failures"],
              ["audit", "Audit"],
              ["files", "Locations"],
            ],
          },
          { page: "network", label: "Network Workers" },
          { page: "libraries", label: "Libraries" },
          { page: "schedule", label: "Schedule" },
          {
            page: "settings",
            label: "Settings",
            tabs: [
              ["status", "Status"],
              ["guided-setup", "Guided Setup"],
              ["paths-safety", "Paths & Safety"],
              ["routing-size", "Routing & Size"],
              ["media-output", "Media Output"],
              ["publish-recovery", "Publish & Recovery"],
              ["naming", "Naming"],
              ["queue-runtime", "Queue & Runtime"],
              ["advanced-evidence", "Evidence"],
            ],
          },
          {
            page: "diagnostics",
            label: "Diagnostics",
            tabs: [
              ["triage", "Overview"],
              ["investigation", "Investigation"],
              ["logs", "Logs"],
              ["progress", "State"],
              ["advanced", "Advanced"],
            ],
          },
          { page: "maintenance", label: "Maintenance" },
        ];

        const TAB_CONFIG = {
          launch: { button: "data-launch-tab", panel: "data-launch-tab-panel" },
          metrics: { button: "data-metrics-tab", panel: "data-metrics-tab-panel" },
          reports: { button: "data-reports-tab", panel: "data-reports-tab-panel" },
          completed: { button: "data-completed-tab", panel: "data-completed-tab" },
          settings: { button: "data-settings-tab", panel: "data-settings-tab", current: "aria-current" },
          diagnostics: { button: "data-diag-tab", panel: "data-diag-tab" },
        };

        function expectedStates() {
          return CAPTURE_MATRIX.flatMap((entry) => {
            if (!entry.tabs) return [{ page: entry.page, pageLabel: entry.label, subtab: "", subtabLabel: "" }];
            return entry.tabs.map(([subtab, subtabLabel]) => ({
              page: entry.page,
              pageLabel: entry.label,
              subtab,
              subtabLabel,
            }));
          });
        }

        function safeName(value) {
          return String(value || "default")
            .trim()
            .toLowerCase()
            .replace(/&/g, "and")
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
            || "default";
        }

        async function evaluateValue(client, expression, awaitPromise = false) {
          const result = await client.send("Runtime.evaluate", {
            expression,
            awaitPromise,
            returnByValue: true,
          });
          if (result.exceptionDetails) {
            const details = result.exceptionDetails;
            throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
          }
          return result.result?.value;
        }

        async function waitForExpression(client, expression, label, timeoutMs = 20000) {
          const deadline = Date.now() + timeoutMs;
          let lastValue = null;
          while (Date.now() < deadline) {
            lastValue = await evaluateValue(client, expression);
            if (lastValue === true) return;
            await sleep(150);
          }
          throw new Error(`Timed out waiting for ${label}; last value=${lastValue}`);
        }

        async function prepareUi(client) {
          await evaluateValue(client, `
            (() => {
              try {
                localStorage.setItem("mediapipeline-advanced-mode", "0");
                localStorage.setItem("mediapipeline-evidence-hidden", "0");
              } catch (_) {}
              if (typeof window.applyAdvancedModePreference === "function") window.applyAdvancedModePreference(false);
              else document.body.classList.remove("advanced-mode");
              if (typeof window.applyEvidenceHiddenPreference === "function") window.applyEvidenceHiddenPreference(false);
              else document.body.classList.remove("evidence-hidden");
              if (typeof window.renderCrossPageContext === "function" && window.mediaPipelineLastCrossPageContext) {
                window.renderCrossPageContext(window.mediaPipelineLastCrossPageContext);
              }
              return true;
            })()
          `);
        }

        async function activateState(client, state) {
          const activation = await evaluateValue(client, `
            (async () => {
              const state = ${JSON.stringify(state)};
              const tabConfig = ${JSON.stringify(TAB_CONFIG)};
              if (typeof window.showPage !== "function") throw new Error("showPage is not available");
              window.showPage(state.page);
              await new Promise((resolve) => setTimeout(resolve, 80));
              const page = document.querySelector('[data-page-panel="' + state.page + '"]');
              if (!page) throw new Error("missing page " + state.page);
              if (!page.classList.contains("is-visible")) throw new Error("page did not become visible: " + state.page);
              if (state.subtab) {
                const config = tabConfig[state.page];
                if (!config) throw new Error("missing tab config for " + state.page);
                const selector = '[' + config.button + '="' + state.subtab + '"]';
                const button = page.querySelector(selector);
                if (!button) {
                  return {
                    missingRequestedSubtab: true,
                    reason: "missing subtab button",
                    page: state.page,
                    subtab: state.subtab,
                  };
                }
                button.click();
                await new Promise((resolve) => setTimeout(resolve, 80));
                const panel = page.querySelector('.settings-tab-pane[' + config.panel + '="' + state.subtab + '"]');
                if (!panel) {
                  return {
                    missingRequestedSubtab: true,
                    reason: "missing subtab panel",
                    page: state.page,
                    subtab: state.subtab,
                  };
                }
                if (!panel.classList.contains("is-active")) {
                  return {
                    missingRequestedSubtab: true,
                    reason: "subtab did not become active",
                    page: state.page,
                    subtab: state.subtab,
                  };
                }
              }
              const scroller = document.scrollingElement || document.documentElement;
              scroller.scrollTo(0, 0);
              return { missingRequestedSubtab: false };
            })()
          `, true);
          await sleep(150);
          return activation;
        }

        async function auditVisibleState(client) {
          return await evaluateValue(client, `
            (() => {
              function visible(node) {
                if (!node || !node.getClientRects) return false;
                const style = getComputedStyle(node);
                if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
                return node.getClientRects().length > 0;
              }
              function text(node) {
                return String(node?.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 220);
              }
              const page = document.querySelector(".page.is-visible[data-page-panel]");
              if (!page) throw new Error("no visible page");
              const allowedReasons = new Set(["field-help", "table-legend", "operator-input", "copy-output", "advanced-detail", "log-output"]);
              function reasonFor(node) {
                const explicit = node.dataset?.visualKeep || node.closest("[data-visual-keep]")?.dataset?.visualKeep || "";
                if (allowedReasons.has(explicit)) return explicit;
                if (node.closest("details")) return "advanced-detail";
                if (node.closest(".table-legend")) return "table-legend";
                if (node.closest('[data-panel-type="interactive"]')) return "operator-input";
                const id = String(node.id || "");
                if (/(detail|result|history|markdown|tail|log|command|json|raw|copy|preview|editor|latest)/i.test(id)) return "copy-output";
                return "";
              }
              const candidates = Array.from(page.querySelectorAll(
                '.panel[data-panel-type="evidence"] > .prose-block,'
                + '.panel[data-panel-type="evidence"] > .diagnostic-callout,'
                + '.panel[data-panel-type="evidence"] .diagnostic-callout-brief'
              ));
              const offenders = candidates
                .filter(visible)
                .map((node) => ({ node, reason: reasonFor(node) }))
                .filter((entry) => !entry.reason)
                .map((entry) => ({
                  id: entry.node.id || "",
                  tag: entry.node.tagName.toLowerCase(),
                  classes: entry.node.className || "",
                  panel: entry.node.closest(".panel")?.querySelector(".panel-heading h2, .panel-heading h3")?.textContent?.trim() || "",
                  text: text(entry.node),
                }));
              const pageOverflow = document.documentElement.scrollWidth > window.innerWidth + 2;
              const overflowNodes = pageOverflow
                ? Array.from(document.body.querySelectorAll("*"))
                  .filter(visible)
                  .filter((node) => !node.closest(".table-wrap"))
                  .map((node) => ({ node, rect: node.getBoundingClientRect() }))
                  .filter((entry) => entry.rect.right > window.innerWidth + 2 || entry.rect.left < -2)
                  .slice(0, 8)
                  .map((entry) => ({
                    tag: entry.node.tagName.toLowerCase(),
                    id: entry.node.id || "",
                    classes: String(entry.node.className || "").slice(0, 160),
                    left: Math.round(entry.rect.left),
                    right: Math.round(entry.rect.right),
                    width: Math.round(entry.rect.width),
                    text: text(entry.node),
                  }))
                : [];
              return {
                page: page.dataset.pagePanel,
                offenders,
                horizontalOverflow: pageOverflow,
                scrollWidth: document.documentElement.scrollWidth,
                viewportWidth: window.innerWidth,
                overflowNodes,
              };
            })()
          `);
        }

        async function setViewport(client, width, height) {
          await client.send("Emulation.setDeviceMetricsOverride", {
            width,
            height,
            deviceScaleFactor: 1,
            mobile: width <= 430,
          });
          await sleep(120);
        }

        async function captureScreenshot(client, state, viewport) {
          const filename = `${safeName(state.pageLabel)}${state.subtabLabel ? "-" + safeName(state.subtabLabel) : ""}-${viewport.width}x${viewport.height}.png`;
          const screenshotPath = path.join(payload.screenshotDir, filename);
          const metrics = await client.send("Page.getLayoutMetrics");
          const contentSize = metrics.cssContentSize || metrics.contentSize || { width: viewport.width, height: viewport.height };
          const result = await client.send("Page.captureScreenshot", {
            format: "png",
            captureBeyondViewport: true,
            clip: {
              x: 0,
              y: 0,
              width: Math.max(viewport.width, Math.ceil(contentSize.width || viewport.width)),
              height: Math.max(viewport.height, Math.ceil(contentSize.height || viewport.height)),
              scale: 1,
            },
          });
          fs.writeFileSync(screenshotPath, Buffer.from(result.data, "base64"));
          return screenshotPath;
        }

        async function main() {
          fs.mkdirSync(payload.screenshotDir, { recursive: true });
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
            await client.send("Page.enable");
            await client.send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 25, g: 26, b: 33, a: 1 } });
            await waitForExpression(
              client,
              `Boolean(document.readyState !== "loading" && typeof window.showPage === "function" && window.mediaPipelineDom && typeof window.mediaPipelineDom.renderReviewTileBoard === "function" && document.querySelector('[data-page-panel="home"]'))`,
              "WebView app and review tile helper",
            );
            await prepareUi(client);
            const states = expectedStates();
            const manifest = {
              generated_at: payload.generatedAt,
              url: payload.url,
              screenshot_dir: payload.screenshotDir,
              entries: [],
              compact_checks: [],
            };
            const desktop = { width: 1366, height: 900 };
            await setViewport(client, desktop.width, desktop.height);
            for (const state of states) {
              const activation = await activateState(client, state);
              const audit = await auditVisibleState(client);
              const screenshotPath = await captureScreenshot(client, state, desktop);
              manifest.entries.push({
                page: state.pageLabel,
                subtab: state.subtabLabel || null,
                viewport: `${desktop.width}x${desktop.height}`,
                screenshot_path: screenshotPath,
                missing_requested_subtab: activation?.missingRequestedSubtab ? {
                  reason: activation.reason || "missing",
                  page: state.page,
                  subtab: state.subtab,
                } : null,
                visible_clutter_offenders: audit.offenders,
                horizontal_overflow: audit.horizontalOverflow,
                overflow_nodes: audit.overflowNodes,
              });
            }
            for (const compact of [{ width: 390, height: 844 }, { width: 768, height: 900 }]) {
              await setViewport(client, compact.width, compact.height);
              for (const state of states) {
                const activation = await activateState(client, state);
                const audit = await auditVisibleState(client);
                manifest.compact_checks.push({
                  page: state.pageLabel,
                  subtab: state.subtabLabel || null,
                  viewport: `${compact.width}x${compact.height}`,
                  missing_requested_subtab: activation?.missingRequestedSubtab ? {
                    reason: activation.reason || "missing",
                    page: state.page,
                    subtab: state.subtab,
                  } : null,
                  visible_clutter_offenders: audit.offenders,
                  horizontal_overflow: audit.horizontalOverflow,
                  overflow_nodes: audit.overflowNodes,
                });
              }
            }
            const manifestPath = path.join(payload.screenshotDir, "manifest.json");
            fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
            const allEntries = manifest.entries.concat(manifest.compact_checks);
            const offenderCount = allEntries.reduce((total, entry) => total + entry.visible_clutter_offenders.length, 0);
            const overflowCount = allEntries.reduce((total, entry) => total + (entry.horizontal_overflow ? 1 : 0), 0);
            const missingRequestedSubtabCount = allEntries.reduce((total, entry) => total + (entry.missing_requested_subtab ? 1 : 0), 0);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({
              ok: true,
              result: {
                screenshotDir: payload.screenshotDir,
                manifestPath,
                screenshotCount: manifest.entries.length,
                compactCheckCount: manifest.compact_checks.length,
                offenderCount,
                overflowCount,
                missingRequestedSubtabCount,
              },
            }));
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


def _run_browser_visual_clutter_smoke(*, browser_path: str, url: str, screenshot_dir: Path) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView screenshot smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-visual-clutter-payload.json"
        runner_path = tmp / "browser-visual-clutter-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "screenshotDir": str(screenshot_dir),
                    "generatedAt": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_visual_clutter_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView visual clutter screenshot smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=120,
        )


class WebViewBrowserVisualClutterScreenshots(unittest.TestCase):
    def test_all_pages_and_subtabs_have_screenshots_without_visible_evidence_prose_clutter(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView screenshot smoke.")

        repo_root = find_repo_root(Path(__file__))
        screenshot_dir = (
            repo_root
            / "LocalBase"
            / "UiScreenshots"
            / f"validation-clutter-cleanup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-visual-clutter-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_visual_clutter_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    screenshot_dir=screenshot_dir,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        manifest_path = Path(str(browser_result["manifestPath"]))
        self.assertTrue(manifest_path.exists(), f"Screenshot manifest was not written: {manifest_path}")
        self.assertEqual(EXPECTED_DESKTOP_SCREENSHOT_COUNT, browser_result["screenshotCount"])
        self.assertEqual(EXPECTED_DESKTOP_SCREENSHOT_COUNT * 2, browser_result["compactCheckCount"])
        self.assertEqual(0, browser_result["offenderCount"], f"Visible clutter offenders recorded in {manifest_path}")
        self.assertEqual(0, browser_result["overflowCount"], f"Horizontal overflow recorded in {manifest_path}")


if __name__ == "__main__":
    unittest.main()
