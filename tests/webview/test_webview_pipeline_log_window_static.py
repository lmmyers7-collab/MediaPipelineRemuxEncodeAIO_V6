from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))


PROJECT_ROOT = find_repo_root(Path(__file__))
WEBVIEW_ROOT = PROJECT_ROOT / "apps" / "desktop" / "webview" / "static"
ASSETS_ROOT = WEBVIEW_ROOT / "assets"
TAURI_ROOT = PROJECT_ROOT / "apps" / "desktop" / "tauri" / "src-tauri"


class WebViewPipelineLogWindowStaticTests(unittest.TestCase):
    def test_remote_tauri_webview_has_explicit_pipeline_log_command_permission(self) -> None:
        build_script = (TAURI_ROOT / "build.rs").read_text(encoding="utf-8")
        capability = json.loads(
            (TAURI_ROOT / "capabilities" / "default.json").read_text(encoding="utf-8")
        )

        self.assertIn("AppManifest::new().commands", build_script)
        self.assertIn('"open_pipeline_log_window"', build_script)
        self.assertIn("allow-open-pipeline-log-window", capability["permissions"])
        self.assertEqual(
            capability["remote"]["urls"],
            ["http://127.0.0.1:*", "http://localhost:*"],
        )

    def test_main_shell_exposes_pipeline_log_window_entry_points(self) -> None:
        index = (WEBVIEW_ROOT / "index.html").read_text(encoding="utf-8")
        shell = (WEBVIEW_ROOT / "partials" / "app-shell-start.html").read_text(encoding="utf-8")
        launch = (WEBVIEW_ROOT / "partials" / "page-launch.html").read_text(encoding="utf-8")
        app_js = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ASSETS_ROOT / "app" / "lifecycleOrchestration.js",
                ASSETS_ROOT / "app" / "refreshCoordinator.js",
                ASSETS_ROOT / "app.js",
            )
        )

        self.assertIn('/assets/floatingPipelineLog.js', index)
        self.assertIn('/assets/pipelineLogWindowBridge.js', index)
        self.assertLess(index.index('/assets/tauriLifecycleBridge.js'), index.index('/assets/pipelineLogWindowBridge.js'))
        self.assertLess(index.index('/assets/floatingPipelineLog.js'), index.index('/assets/app.js'))
        self.assertLess(index.index('/assets/pipelineLogWindowBridge.js'), index.index('/assets/app.js'))
        self.assertIn('id="pipeline-log-window-button"', shell)
        self.assertIn('aria-pressed="false"', shell)
        self.assertIn('id="launch-open-pipeline-log-window-button"', launch)
        self.assertIn("window.mediaPipelineFloatingPipelineLog?.initFloatingPipelineLogEvents?.();", app_js)
        self.assertIn("window.mediaPipelinePipelineLogWindowBridge?.initPipelineLogWindowBridgeEvents?.();", app_js)
        self.assertIn("renderFloatingPipelineLog?.(values.diagnostics)", app_js)

        for fragment in (
            'id="floating-pipeline-log-panel"',
            'id="floating-pipeline-log-title"',
            'id="floating-pipeline-log-status"',
            'id="floating-pipeline-log-follow"',
            'id="floating-pipeline-log-mode"',
            'id="floating-pipeline-log-refresh-button"',
            'id="floating-pipeline-log-close-button"',
            'id="floating-pipeline-log-updated"',
            'id="floating-pipeline-log-text"',
        ):
            self.assertIn(fragment, shell)

    def test_floating_pipeline_log_overlay_refreshes_diagnostics_read_only(self) -> None:
        script = (ASSETS_ROOT / "floatingPipelineLog.js").read_text(encoding="utf-8")

        for fragment in (
            "const REFRESH_INTERVAL_MS = 2000",
            'apiClient.apiGet("/api/diagnostics"',
            'apiClient.apiGet("/api/backend/close-readiness"',
            "function initFloatingPipelineLogEvents",
            "function toggleFloatingPipelineLog",
            "function openFloatingPipelineLog",
            "function closeFloatingPipelineLog",
            "function refreshFloatingPipelineLog",
            "function renderFloatingPipelineLog",
            "function renderRawFloatingPipelineLog",
            "function compactRepeatedProgressLines",
            "/api/diagnostics/tail?target=pipeline_log&max_bytes=262144",
            "function activeWorkLogLines",
            "function activeProcessLogLines",
            "ACTIVE WORK DETECTED",
            "Active process log:",
            "CSV rerun process",
            "--- current activity ---",
            "shown once;",
            "function initFloatingPipelineLogDragEvents",
            "header.addEventListener(\"pointerdown\", startPanelDrag)",
            "window.addEventListener(\"resize\", keepPanelInsideViewport)",
            "pipeline-log-window-button",
            "floating-pipeline-log-panel",
            "floating-pipeline-log-mode",
            "window.mediaPipelineFloatingPipelineLog",
        ):
            self.assertIn(fragment, script)
        self.assertNotIn("apiPost", script)
        self.assertNotIn("window.__TAURI__", script)
        self.assertNotIn("open_pipeline_log_window", script)
        self.assertNotIn('window.showPage("diagnostics")', script)
        self.assertNotIn('data-diag-tab="logs"', script)
        self.assertNotIn("fetch(", script)

    def test_pipeline_log_window_page_loads_api_client_before_window_script(self) -> None:
        html = (ASSETS_ROOT / "pipelineLogWindow.html").read_text(encoding="utf-8")

        for fragment in (
            'id="pipeline-log-window-status"',
            'id="pipeline-log-window-follow"',
            'id="pipeline-log-window-mode"',
            'id="pipeline-log-window-refresh-button"',
            'id="pipeline-log-window-updated"',
            'id="pipeline-log-window-text"',
            'id="pipeline-log-window-detail"',
        ):
            self.assertIn(fragment, html)
        self.assertLess(html.index('/assets/apiClient.js'), html.index('/assets/pipelineLogWindow.js'))

    def test_launch_pipeline_log_bridge_opens_read_only_window_and_falls_back_to_diagnostics_logs(self) -> None:
        bridge = (ASSETS_ROOT / "pipelineLogWindowBridge.js").read_text(encoding="utf-8")

        self.assertIn("window.open", bridge)
        self.assertIn("/assets/pipelineLogWindow.html?surface=pipeline-log", bridge)
        self.assertIn("mediapipeline-pipeline-log", bridge)
        self.assertIn("launch-open-pipeline-log-window-button", bridge)
        self.assertNotIn('bindOpenButton("pipeline-log-window-button")', bridge)
        self.assertIn("function showDiagnosticsLogsFallback", bridge)
        self.assertIn('window.showPage("diagnostics")', bridge)
        self.assertIn('data-diag-tab="logs"', bridge)
        self.assertIn("diagnostics-pipeline-log-status", bridge)
        self.assertIn("window.mediaPipelinePipelineLogWindowBridge", bridge)
        self.assertIn("window.__TAURI__", bridge)
        self.assertIn('await invoke("open_pipeline_log_window")', bridge)
        self.assertIn("function openNativeLogWindow", bridge)
        self.assertNotIn("apiPost", bridge)

    def test_launch_pipeline_log_bridge_prefers_native_tauri_window_and_keeps_browser_fallback(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the Pipeline Log bridge smoke.")
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(
              "apps/desktop/webview/static/assets/pipelineLogWindowBridge.js",
              "utf8"
            );

            function makeContext(withTauri) {
              const status = { textContent: "", dataset: {} };
              let browserOpenCount = 0;
              const invoked = [];
              const context = {
                console,
                document: {
                  getElementById(id) {
                    return id === "pipeline-launch-status" ? status : null;
                  },
                  querySelector() { return null; },
                },
                window: {
                  open() {
                    browserOpenCount += 1;
                    return { focus() {} };
                  },
                },
              };
              if (withTauri) {
                context.window.__TAURI__ = {
                  core: {
                    async invoke(command) { invoked.push(command); },
                  },
                };
              }
              context.window.window = context.window;
              vm.createContext(context);
              vm.runInContext(source, context, { filename: "pipelineLogWindowBridge.js" });
              return {
                bridge: context.window.mediaPipelinePipelineLogWindowBridge,
                invoked,
                status,
                browserOpenCount: () => browserOpenCount,
              };
            }

            (async () => {
              const nativeContext = makeContext(true);
              const nativeResult = await nativeContext.bridge.openPipelineLogWindow(null);
              if (JSON.stringify(nativeContext.invoked) !== JSON.stringify(["open_pipeline_log_window"])) {
                throw new Error("native command was not invoked exactly once");
              }
              if (!nativeResult.opened || !nativeResult.native || nativeResult.fallback) {
                throw new Error("native result did not report the native window");
              }
              if (nativeContext.browserOpenCount() !== 0) {
                throw new Error("browser popup opened despite an available Tauri bridge");
              }

              const browserContext = makeContext(false);
              const browserResult = await browserContext.bridge.openPipelineLogWindow(null);
              if (!browserResult.opened || browserResult.native || browserResult.fallback) {
                throw new Error("browser fallback did not report an opened window");
              }
              if (browserContext.browserOpenCount() !== 1) {
                throw new Error("browser fallback did not open exactly once");
              }
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_pipeline_log_window_refreshes_diagnostics_read_only(self) -> None:
        script = (ASSETS_ROOT / "pipelineLogWindow.js").read_text(encoding="utf-8")

        self.assertIn("const REFRESH_INTERVAL_MS = 2000", script)
        self.assertIn('apiClient.apiGet("/api/diagnostics"', script)
        self.assertIn('apiClient.apiGet("/api/backend/close-readiness"', script)
        self.assertIn("function renderPipelineLogWindow", script)
        self.assertIn("function renderRawPipelineLogWindow", script)
        self.assertIn("function renderRefreshError", script)
        self.assertIn("function compactRepeatedProgressLines", script)
        self.assertIn("/api/diagnostics/tail?target=pipeline_log&max_bytes=262144", script)
        self.assertIn("function activeWorkLogLines", script)
        self.assertIn("function activeProcessLogLines", script)
        self.assertIn("ACTIVE WORK DETECTED", script)
        self.assertIn("Active process log:", script)
        self.assertIn("CSV rerun process", script)
        self.assertIn("--- current activity ---", script)
        self.assertIn("shown once;", script)
        self.assertIn("isNearBottom", script)
        self.assertIn("pipeline-log-window-follow", script)
        self.assertIn("pipeline-log-window-mode", script)
        self.assertIn("window.mediaPipelinePipelineLogWindow", script)
        self.assertNotIn("apiPost", script)
        self.assertNotIn("fetch(", script)
        for route in (
            "/api/pipeline/start",
            "/api/pipeline/control",
            "/api/settings/save-patch",
            "/api/pending-publish/drain",
            "/api/rename/apply",
            "/api/queue",
            "/api/completed/final-library",
            "/api/backend/shutdown",
        ):
            self.assertNotIn(route, script)

    def test_diagnostics_pipeline_log_compacts_repeated_progress_lines(self) -> None:
        script = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ASSETS_ROOT / "diagnostics" / "triage.js",
                ASSETS_ROOT / "diagnosticsView.js",
            )
        )

        self.assertIn("function compactRepeatedProgressLines", script)
        self.assertIn("function compactedDiagnosticsTextLines", script)
        self.assertIn('source === "Pipeline log tail" ? compactedDiagnosticsTextLines(value)', script)
        self.assertIn('setTextIfChanged("log-tail", compactRepeatedProgressLines(pipelineLog) || pipelineStatus.fallback)', script)
        self.assertIn("shown once;", script)

    def test_floating_pipeline_log_topbar_smoke_keeps_panel_visible_across_tab_switch(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the floating Pipeline Log smoke.")
        script = textwrap.dedent(
            r"""
            (async () => {
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");
            const source = fs.readFileSync(
              path.join(process.cwd(), "apps/desktop/webview/static/assets/floatingPipelineLog.js"),
              "utf8"
            );

            function makeElement(id) {
              const classes = new Set();
              return {
                id,
                hidden: false,
                checked: id === "floating-pipeline-log-follow",
                value: id === "floating-pipeline-log-mode" ? "activity" : "",
                disabled: false,
                dataset: {},
                attributes: {},
                style: {},
                classList: {
                  add(name) { classes.add(name); },
                  remove(name) { classes.delete(name); },
                  contains(name) { return classes.has(name); },
                },
                listeners: {},
                offsetWidth: id === "floating-pipeline-log-panel" ? 420 : 100,
                offsetHeight: id === "floating-pipeline-log-panel" ? 260 : 40,
                scrollTop: 0,
                clientHeight: 100,
                scrollHeight: 100,
                title: "",
                _textContent: "",
                set textContent(value) { this._textContent = String(value ?? ""); },
                get textContent() { return this._textContent; },
                setAttribute(name, value) { this.attributes[name] = String(value); },
                getAttribute(name) { return this.attributes[name]; },
                getBoundingClientRect() {
                  return {
                    left: Number.parseInt(this.style.left || "100", 10),
                    top: Number.parseInt(this.style.top || "80", 10),
                    width: this.offsetWidth,
                    height: this.offsetHeight,
                    right: Number.parseInt(this.style.left || "100", 10) + this.offsetWidth,
                    bottom: Number.parseInt(this.style.top || "80", 10) + this.offsetHeight,
                  };
                },
                querySelector(selector) {
                  if (selector === ".floating-pipeline-log-header") return nodes["floating-pipeline-log-header"];
                  return null;
                },
                closest() { return null; },
                addEventListener(type, handler) {
                  this.listeners[type] = this.listeners[type] || [];
                  this.listeners[type].push(handler);
                },
                setPointerCapture() {},
                releasePointerCapture() {},
                contains(node) { return node === this; },
                click() {
                  for (const handler of this.listeners.click || []) {
                    handler({ preventDefault() {} });
                  }
                },
              };
            }

            const nodes = {};
            for (const id of [
              "pipeline-log-window-button",
              "floating-pipeline-log-panel",
              "floating-pipeline-log-header",
              "floating-pipeline-log-status",
              "floating-pipeline-log-follow",
              "floating-pipeline-log-mode",
              "floating-pipeline-log-refresh-button",
              "floating-pipeline-log-close-button",
              "floating-pipeline-log-updated",
              "floating-pipeline-log-text",
            ]) {
              nodes[id] = makeElement(id);
            }

            let diagnosticsNavigationAttempted = false;
            let apiCalls = 0;
            let diagnosticsTail = [
              "2026-06-25 20:03:00 [INFO] ENCODE : 65%",
              "2026-06-25 20:03:00 [INFO] ENCODE : 65%",
              "2026-06-25 20:03:01 [INFO] ENCODE : 65%",
              "2026-06-25 20:03:02 [INFO] smoke log line",
            ].join("\n");
            const rawTail = [
              "2026-06-25 20:04:00 [INFO] ENCODE : 65%",
              "2026-06-25 20:04:00 [INFO] ENCODE : 65%",
              "2026-06-25 20:04:01 [INFO] raw tail line",
            ].join("\n");
            const windowListeners = {};
            const context = {
              window: {},
              document: {
                activeElement: nodes["floating-pipeline-log-panel"],
                getElementById(id) { return nodes[id] || null; },
                addEventListener() {},
              },
              Date,
              setTimeout,
              clearTimeout,
              console,
            };
            context.window = context;
            context.innerWidth = 1200;
            context.innerHeight = 800;
            context.matchMedia = () => ({ matches: false });
            context.window.requestAnimationFrame = (handler) => handler();
            context.window.setInterval = () => 1;
            context.window.clearInterval = () => {};
            context.window.addEventListener = (type, handler) => {
              windowListeners[type] = windowListeners[type] || [];
              windowListeners[type].push(handler);
            };
            context.window.showPage = () => { diagnosticsNavigationAttempted = true; };
            context.window.mediaPipelineApi = {
              async apiGet(path) {
                apiCalls += 1;
                if (path === "/api/backend/close-readiness") {
                  return {
                    safe_to_close: false,
                    active_work: true,
                    state: "running",
                    reason: "Shell close blocked because CSV rerun is active.",
                  };
                }
                if (path === "/api/diagnostics") {
                  return {
                    log_tail: diagnosticsTail,
                    active_jobs: ["csv rerun: active (pid 56492) launched 2026-06-29T21:36:12"],
                    active_job_rows: [{
                      launch_id: "csv-rerun-smoke",
                      job_kind: "csv_rerun",
                      mode: "copy",
                      status: "active",
                      status_state: "running",
                      pid: 56492,
                    }],
                    worker_progress: {
                      rows: [{
                        job_kind: "rerun_csv",
                        worker_label: "Local rerun_csv",
                        status_state: "running",
                        stage: "active",
                        last_log_line: "2026-06-25 20:03:02 [INFO] [Movie 1/1] SIZE: 5.45 GB | Route: ENCODE",
                      }],
                    },
                  };
                }
                if (path === "/api/diagnostics/tail?target=pipeline_log&max_bytes=262144") {
                  return {
                    ok: true,
                    target: "pipeline_log",
                    text: rawTail,
                    truncated: false,
                    warnings: [],
                    errors: [],
                  };
                }
                throw new Error(`Unexpected path ${path}`);
              },
            };

            vm.createContext(context);
            vm.runInContext(source, context, { filename: "floatingPipelineLog.js" });
            const overlay = context.window.mediaPipelineFloatingPipelineLog;
            if (!overlay?.initFloatingPipelineLogEvents) throw new Error("overlay namespace missing");
            overlay.initFloatingPipelineLogEvents();

            nodes["pipeline-log-window-button"].click();
            await new Promise((resolve) => setImmediate(resolve));
            if (nodes["floating-pipeline-log-panel"].hidden) throw new Error("floating panel did not open");
            if (nodes["pipeline-log-window-button"].attributes["aria-pressed"] !== "true") throw new Error("button pressed state not set");
            if (apiCalls !== 2) throw new Error(`expected diagnostics and close-readiness calls, got ${apiCalls}`);
            if (!nodes["floating-pipeline-log-text"].textContent.includes("ACTIVE WORK DETECTED")) throw new Error("active work banner did not render");
            if (!nodes["floating-pipeline-log-text"].textContent.includes("Shell close blocked because CSV rerun is active.")) throw new Error("close-readiness reason did not render");
            if (!nodes["floating-pipeline-log-text"].textContent.includes("smoke log line")) throw new Error("log text did not render");
            if (!nodes["floating-pipeline-log-text"].textContent.includes("CSV rerun process (active)")) throw new Error("active rerun process log label did not render");
            if (!nodes["floating-pipeline-log-text"].textContent.includes("Route: ENCODE")) throw new Error("active rerun encode log line did not render");
            if (!nodes["floating-pipeline-log-text"].textContent.includes("3 repeated progress updates collapsed")) throw new Error("progress repeats were not compacted");
            const initialText = nodes["floating-pipeline-log-text"].textContent;
            if (initialText.indexOf("smoke log line") >= initialText.indexOf("ACTIVE WORK DETECTED")) {
              throw new Error("active work evidence should render after the tail so follow-tail keeps it visible");
            }

            diagnosticsTail = [
              "2026-06-25 20:03:03 [INFO] COPY : 80%",
              "2026-06-25 20:03:04 [INFO] proof refreshed tail line",
            ].join("\n");
            await overlay.refreshFloatingPipelineLog();
            const refreshedText = nodes["floating-pipeline-log-text"].textContent;
            if (apiCalls !== 4) throw new Error(`expected two diagnostics refresh cycles, got ${apiCalls} API calls`);
            if (!refreshedText.includes("proof refreshed tail line")) throw new Error("manual refresh did not render the updated diagnostics log tail");
            if (refreshedText.includes("smoke log line")) throw new Error("manual refresh kept stale log text after diagnostics changed");
            if (refreshedText.indexOf("proof refreshed tail line") >= refreshedText.indexOf("ACTIVE WORK DETECTED")) {
              throw new Error("active work evidence should remain visible at the bottom after refresh");
            }

            nodes["floating-pipeline-log-mode"].value = "raw";
            await overlay.refreshFloatingPipelineLog();
            const rawText = nodes["floating-pipeline-log-text"].textContent;
            if (apiCalls !== 5) throw new Error(`expected raw mode to add one tail call, got ${apiCalls} API calls`);
            if (rawText !== rawTail) throw new Error("raw mode did not render the unmodified backend tail");
            if (rawText.includes("ACTIVE WORK DETECTED")) throw new Error("raw mode kept synthetic active-work evidence");
            if (!rawText.includes("ENCODE : 65%\n2026-06-25 20:04:00 [INFO] ENCODE : 65%")) {
              throw new Error("raw mode compacted repeated progress lines");
            }

            const header = nodes["floating-pipeline-log-header"];
            const panel = nodes["floating-pipeline-log-panel"];
            header.listeners.pointerdown[0]({
              button: 0,
              pointerId: 7,
              clientX: 120,
              clientY: 100,
              target: header,
              preventDefault() {},
            });
            panel.listeners.pointermove[0]({
              pointerId: 7,
              clientX: 300,
              clientY: 240,
              preventDefault() {},
            });
            if (panel.style.left !== "280px" || panel.style.top !== "220px") {
              throw new Error(`panel was not dragged to the expected location: ${panel.style.left}, ${panel.style.top}`);
            }
            if (!panel.classList.contains("floating-pipeline-log--dragging")) throw new Error("dragging class not set");
            panel.listeners.pointerup[0]({ pointerId: 7 });
            if (panel.classList.contains("floating-pipeline-log--dragging")) throw new Error("dragging class not cleared");

            const switchedPage = { name: "queue", visible: true };
            if (!switchedPage.visible || nodes["floating-pipeline-log-panel"].hidden) throw new Error("panel did not survive local tab switch");
            if (diagnosticsNavigationAttempted) throw new Error("topbar overlay attempted Diagnostics navigation");

            nodes["floating-pipeline-log-close-button"].click();
            if (!nodes["floating-pipeline-log-panel"].hidden) throw new Error("floating panel did not close");
            if (nodes["pipeline-log-window-button"].attributes["aria-pressed"] !== "false") throw new Error("button pressed state not cleared");
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
