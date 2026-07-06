from __future__ import annotations

import json
import os
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

try:
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
except ImportError:  # pragma: no cover
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


EXPECTED_DESKTOP_SCREENSHOT_COUNT = 38


def _browser_prose_box_audit_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        const path = require("path");

        const CAPTURE_MATRIX = [
          { page: "home", label: "Home" },
          { page: "launch", label: "Launch", tabs: [["pipeline", "Pipeline Processor"], ["history", "History"]] },
          { page: "live", label: "Telemetry" },
          { page: "metrics", label: "Metrics", tabs: [["overview", "Overview"], ["routes", "Remux vs Encode"], ["storage", "Storage"], ["production", "Production"], ["workers", "Workers"]] },
          { page: "queue", label: "Queue", tabs: [["main", "Main Queue"], ["rerun", "CSV Rerun"]] },
          { page: "completed", label: "Completed Output", tabs: [["overview", "Overview"], ["history", "History"], ["evidence", "Evidence"]] },
          { page: "pending", label: "Pending Publish" },
          { page: "rename", label: "Rename" },
          { page: "reports", label: "Reports", tabs: [["failures", "Failures"], ["audit", "Audit"], ["files", "Locations"]] },
          { page: "network", label: "Network Workers" },
          { page: "libraries", label: "Libraries" },
          { page: "schedule", label: "Schedule" },
          { page: "settings", label: "Settings", tabs: [["status", "Status"], ["guided-setup", "Guided Setup"], ["paths-safety", "Paths & Safety"], ["routing-size", "Routing & Size"], ["media-output", "Media Output"], ["publish-recovery", "Publish & Recovery"], ["naming", "Naming"], ["queue-runtime", "Queue & Runtime"], ["advanced-evidence", "Evidence"]] },
          { page: "diagnostics", label: "Diagnostics", tabs: [["triage", "Overview"], ["readiness", "Readiness"], ["investigation", "Investigation"], ["logs", "Logs"], ["progress", "State"], ["advanced", "Advanced"]] },
          { page: "maintenance", label: "Maintenance" },
        ];

        const TAB_CONFIG = {
          launch: { button: "data-launch-tab", panel: "data-launch-tab-panel" },
          queue: { button: "data-queue-tab", panel: "data-queue-tab-panel" },
          metrics: { button: "data-metrics-tab", panel: "data-metrics-tab-panel" },
          reports: { button: "data-reports-tab", panel: "data-reports-tab-panel" },
          completed: { button: "data-completed-tab", panel: "data-completed-tab" },
          settings: { button: "data-settings-tab", panel: "data-settings-tab" },
          diagnostics: { button: "data-diag-tab", panel: "data-diag-tab" },
        };

        function expectedStates() {
          return CAPTURE_MATRIX.flatMap((entry) => {
            if (!entry.tabs) return [{ page: entry.page, pageLabel: entry.label, subtab: "", subtabLabel: "" }];
            return entry.tabs.map(([subtab, subtabLabel]) => ({ page: entry.page, pageLabel: entry.label, subtab, subtabLabel }));
          });
        }

        function safeName(value) {
          return String(value || "default").trim().toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "default";
        }

        async function evaluateValue(client, expression, awaitPromise = false) {
          const result = await client.send("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
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
              function restoreOriginalProseBoxes(root = document) {
                root.querySelectorAll(".prose-box-summary-strip").forEach((node) => node.remove());
                root.querySelectorAll(".prose-block, .status-block, .diagnostic-callout").forEach((node) => {
                  node.hidden = false;
                  delete node.dataset.proseBoxDisposition;
                  delete node.dataset.proseBoxDefense;
                });
              }
              try {
                localStorage.setItem("mediapipeline-advanced-mode", "0");
                localStorage.setItem("mediapipeline-evidence-hidden", "0");
              } catch (_) {}
              if (typeof window.applyAdvancedModePreference === "function") window.applyAdvancedModePreference(false);
              else document.body.classList.remove("advanced-mode");
              if (typeof window.applyEvidenceHiddenPreference === "function") window.applyEvidenceHiddenPreference(false);
              else document.body.classList.remove("evidence-hidden");
              if (${JSON.stringify(payload.auditMode)} === "after" && typeof window.applyProseBoxDispositions === "function") window.applyProseBoxDispositions(document);
              else restoreOriginalProseBoxes(document);
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
                const button = page.querySelector('[' + config.button + '="' + state.subtab + '"]');
                if (!button) return { missingRequestedSubtab: true, reason: "missing subtab button", page: state.page, subtab: state.subtab };
                button.click();
                await new Promise((resolve) => setTimeout(resolve, 80));
                const panel = page.querySelector('.settings-tab-pane[' + config.panel + '="' + state.subtab + '"]');
                if (!panel) return { missingRequestedSubtab: true, reason: "missing subtab panel", page: state.page, subtab: state.subtab };
                if (!panel.classList.contains("is-active")) return { missingRequestedSubtab: true, reason: "subtab did not become active", page: state.page, subtab: state.subtab };
              }
              if (${JSON.stringify(payload.auditMode)} === "after" && typeof window.applyProseBoxDispositions === "function") {
                window.applyProseBoxDispositions(page);
              } else {
                page.querySelectorAll(".prose-box-summary-strip").forEach((node) => node.remove());
                page.querySelectorAll(".prose-block, .status-block, .diagnostic-callout").forEach((node) => {
                  node.hidden = false;
                  delete node.dataset.proseBoxDisposition;
                  delete node.dataset.proseBoxDefense;
                });
              }
              const scroller = document.scrollingElement || document.documentElement;
              scroller.scrollTo(0, 0);
              return { missingRequestedSubtab: false };
            })()
          `, true);
          await sleep(150);
          return activation;
        }

        async function auditProseBoxes(client) {
          return await evaluateValue(client, `
            (() => {
              function visible(node) {
                if (!node || !node.getClientRects) return false;
                const style = getComputedStyle(node);
                if (node.hidden || style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
                return node.getClientRects().length > 0;
              }
              function text(node) {
                return String(node?.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 280);
              }
              const page = document.querySelector(".page.is-visible[data-page-panel]");
              if (!page) throw new Error("no visible page");
              const boxes = Array.from(page.querySelectorAll(".prose-block, .status-block, .diagnostic-callout"))
                .filter((node) => !node.classList.contains("log-block"))
                .filter((node) => node.dataset?.diagnosticCalloutBody !== "true")
                .filter((node) => !node.closest(".prose-box-summary-strip"))
                .map((node, index) => {
                  const panel = node.closest(".panel");
                  const heading = panel?.querySelector(".panel-heading h2, .panel-heading h3, h2, h3")?.textContent?.trim()
                    || node.id
                    || "Prose box";
                  const disposition = node.dataset.proseBoxDisposition || "";
                  const defense = node.dataset.proseBoxDefense || "";
                  const isVisible = visible(node);
                  return {
                    index,
                    id: node.id || "",
                    tag: node.tagName.toLowerCase(),
                    classes: String(node.className || "").slice(0, 180),
                    panel: heading,
                    text: text(node),
                    visible: isVisible,
                    disposition,
                    defense,
                    offender: isVisible && disposition !== "defended",
                  };
                });
              const logBoxes = Array.from(page.querySelectorAll(".log-block")).map((node) => ({
                id: node.id || "",
                panel: node.closest(".panel")?.querySelector(".panel-heading h2, .panel-heading h3, h2, h3")?.textContent?.trim() || node.id || "Log output",
                visible: visible(node),
                defense: "true log/output pane; kept because it is the inspectable payload, not explanatory prose",
              }));
              return {
                boxes,
                visibleBoxes: boxes.filter((box) => box.visible),
                offenders: boxes.filter((box) => box.offender),
                defended: boxes.filter((box) => box.visible && box.disposition === "defended"),
                logBoxes,
              };
            })()
          `);
        }

        async function setViewport(client, width, height) {
          await client.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
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
            clip: { x: 0, y: 0, width: Math.max(viewport.width, Math.ceil(contentSize.width || viewport.width)), height: Math.max(viewport.height, Math.ceil(contentSize.height || viewport.height)), scale: 1 },
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
            await waitForExpression(client, `Boolean(document.readyState !== "loading" && typeof window.showPage === "function" && document.querySelector('[data-page-panel="home"]'))`, "WebView app");
            await prepareUi(client);
            const manifest = { generated_at: payload.generatedAt, mode: payload.auditMode, url: payload.url, screenshot_dir: payload.screenshotDir, entries: [] };
            const desktop = { width: 1366, height: 900 };
            await setViewport(client, desktop.width, desktop.height);
            for (const state of expectedStates()) {
              const activation = await activateState(client, state);
              const audit = await auditProseBoxes(client);
              const screenshotPath = await captureScreenshot(client, state, desktop);
              manifest.entries.push({
                page: state.pageLabel,
                subtab: state.subtabLabel || null,
                viewport: `${desktop.width}x${desktop.height}`,
                screenshot_path: screenshotPath,
                missing_requested_subtab: activation?.missingRequestedSubtab ? { reason: activation.reason || "missing", page: state.page, subtab: state.subtab } : null,
                prose_boxes: audit.boxes,
                visible_prose_boxes: audit.visibleBoxes,
                prose_box_offenders: audit.offenders,
                defended_prose_boxes: audit.defended,
                log_boxes: audit.logBoxes,
              });
            }
            const manifestPath = path.join(payload.screenshotDir, "manifest.json");
            fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
            const allBoxes = manifest.entries.flatMap((entry) => entry.prose_boxes || []);
            const allOffenders = manifest.entries.flatMap((entry) => entry.prose_box_offenders || []);
            const visibleCount = allBoxes.filter((box) => box.visible).length;
            const defendedCount = allBoxes.filter((box) => box.visible && box.disposition === "defended").length;
            const missingRequestedSubtabCount = manifest.entries.reduce((total, entry) => total + (entry.missing_requested_subtab ? 1 : 0), 0);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            console.log(JSON.stringify({
              ok: true,
              result: {
                screenshotDir: payload.screenshotDir,
                manifestPath,
                mode: payload.auditMode,
                screenshotCount: manifest.entries.length,
                totalProseBoxCount: allBoxes.length,
                visibleProseBoxCount: visibleCount,
                defendedProseBoxCount: defendedCount,
                offenderCount: allOffenders.length,
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


def _run_browser_prose_box_audit(*, browser_path: str, url: str, screenshot_dir: Path, mode: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView prose-box audit.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-prose-box-payload.json"
        runner_path = tmp / "browser-prose-box-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "auditMode": mode,
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
        runner_path.write_text(_browser_prose_box_audit_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView prose-box audit",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=120,
        )


class WebViewBrowserProseBoxAudit(unittest.TestCase):
    def test_prose_boxes_are_inventoried_and_slimmed(self) -> None:
        mode = os.environ.get("MEDIA_PIPELINE_PROSE_BOX_AUDIT_MODE", "after").strip().lower() or "after"
        if mode not in {"before", "after"}:
            self.fail(f"Unsupported MEDIA_PIPELINE_PROSE_BOX_AUDIT_MODE={mode!r}; expected before or after.")

        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView prose-box audit.")

        repo_root = find_repo_root(Path(__file__))
        screenshot_dir = (
            repo_root
            / "LocalBase"
            / "UiScreenshots"
            / f"prose-box-cleanup-{mode}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-prose-box-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_prose_box_audit(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    screenshot_dir=screenshot_dir,
                    mode=mode,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        manifest_path = Path(str(browser_result["manifestPath"]))
        self.assertTrue(manifest_path.exists(), f"Prose-box manifest was not written: {manifest_path}")
        self.assertEqual(EXPECTED_DESKTOP_SCREENSHOT_COUNT, browser_result["screenshotCount"])
        self.assertGreater(browser_result["totalProseBoxCount"], 0, f"No prose boxes were inventoried in {manifest_path}")
        if mode == "before":
            self.assertGreater(browser_result["visibleProseBoxCount"], 0, f"Before audit did not capture visible prose boxes in {manifest_path}")
        else:
            self.assertEqual(0, browser_result["offenderCount"], f"Visible undefended prose boxes remain in {manifest_path}")


if __name__ == "__main__":
    unittest.main()
