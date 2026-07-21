from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyProc, DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _get_json, _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyProc, DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _get_json, _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_lifecycle_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function lifecycleScript(scenario) {
          return `
          (async () => {
            const scenario = ${JSON.stringify(scenario)};
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 15000;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : "") + "\\nLifecycle state:\\n" + [
                "closeReadiness=" + text("diagnostics-close-readiness"),
                "lifecycleStatus=" + text("backend-lifecycle-status"),
                "lifecycleSummary=" + text("backend-lifecycle-summary"),
                "shutdownStatus=" + text("backend-shutdown-status"),
                "history=" + text("backend-lifecycle-history"),
              ].join("\\n"));
            }
            function shutdownButton() {
              const node = byId("backend-shutdown-button");
              if (!node) throw new Error("missing backend shutdown button");
              return node;
            }
            function lifecycleHistory() {
              const entries = typeof window.getCommandHistory === "function" ? window.getCommandHistory() : [];
              return entries.filter((entry) => {
                const raw = entry.raw || {};
                return String(entry.command || raw.command || "") === "backend.shutdown";
              });
            }
            function requireHistoryFragment(fragment) {
              const lines = lifecycleHistory().map((entry) => JSON.stringify(entry));
              if (!lines.some((line) => line.includes(fragment))) {
                throw new Error("backend.shutdown history missing " + fragment + "\\nHistory:\\n" + lines.join("\\n"));
              }
            }
            function installApiPostRecorder() {
              const originalApiPost = window.apiPost;
              if (typeof originalApiPost !== "function") throw new Error("missing global function apiPost");
              const posts = [];
              window.apiPost = async (path, payload, options) => {
                posts.push({ path, payload: payload || {}, options: options || {} });
                return originalApiPost(path, payload, options);
              };
              return {
                posts,
                restore() {
                  window.apiPost = originalApiPost;
                },
              };
            }
            function activePageName() {
              const active = document.querySelector("[data-page-panel].is-visible");
              return active ? active.getAttribute("data-page-panel") || "" : "";
            }
            async function requireTopbarDiagnosticsButton(id) {
              const button = byId(id);
              if (!button) throw new Error("missing topbar diagnostics button " + id);
              if (button.tagName !== "BUTTON") throw new Error(id + " is not a semantic button");
              button.focus({ preventScroll: true });
              if (document.activeElement !== button) throw new Error(id + " is not keyboard focusable");
              const deadline = Date.now() + 5000;
              while (Date.now() < deadline) {
                window.showPage("home");
                button.focus({ preventScroll: true });
                button.click();
                if (activePageName() === "diagnostics") return;
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error(id + " did not navigate to Diagnostics");
            }
            [
              "showPage",
              "requestBackendShutdown",
              "getCommandHistory",
              "renderBackendLifecycle",
            ].forEach(requireFunction);

            window.showPage("home");
            await requireTopbarDiagnosticsButton("refresh-health");
            window.showPage("home");
            await requireTopbarDiagnosticsButton("close-readiness");
            window.showPage("diagnostics");

            if (scenario === "blocked") {
              await waitFor(
                () => text("backend-lifecycle-summary").includes("Continuous watcher: armed") && shutdownButton().disabled === true,
                "blocked lifecycle summary",
              );
              requireText("diagnostics-close-readiness", [
                "Safe to close: no",
                "Continuous watcher: armed",
                "Watcher stop requested: no",
              ]);
              requireText("backend-lifecycle-summary", [
                "Backend lifecycle handoff:",
                "Request status: Watcher armed",
                "Close-readiness: blocked",
                "Guardrail: WebView exposes backend shutdown only when the loaded close-readiness payload reports safe.",
                "Watcher note: keep the backend alive until the schedule boundary requests Stop",
              ]);
              const originalConfirm = window.confirm;
              let confirmCount = 0;
              window.confirm = () => {
                confirmCount += 1;
                return true;
              };
              try {
                await window.requestBackendShutdown();
              } finally {
                window.confirm = originalConfirm;
              }
              await waitFor(
                () => lifecycleHistory().some((entry) => entry.local === true && entry.ok === false && String(entry.message || "").includes("disabled in WebView")),
                "local blocked shutdown rejection",
              );
              requireHistoryFragment("disabled in WebView");
              requireText("backend-shutdown-status", ["Backend shutdown is disabled in WebView until close-readiness reports safe"]);
              if (confirmCount !== 0) throw new Error("blocked shutdown should not ask for confirmation; got " + confirmCount);
              if (shutdownButton().disabled !== true) throw new Error("blocked shutdown button became enabled");
              return {
                ok: true,
                scenario,
                confirmCount,
                shutdownDisabled: shutdownButton().disabled,
                lifecycleSummary: text("backend-lifecycle-summary"),
                closeReadiness: text("diagnostics-close-readiness"),
                shutdownStatus: text("backend-shutdown-status"),
                shutdownHistoryCount: lifecycleHistory().length,
              };
            }

            await waitFor(
              () => text("backend-lifecycle-summary").includes("Close-readiness: safe") && shutdownButton().disabled === false,
              "safe lifecycle summary",
            );
            requireText("diagnostics-close-readiness", [
              "Safe to close: yes",
              "Continuous watcher:",
            ]);
            if (scenario === "stop_requested") {
              requireText("diagnostics-close-readiness", [
                "Continuous watcher: stop_requested",
                "Watcher stop requested: yes",
              ]);
              requireText("backend-lifecycle-summary", [
                "Continuous watcher: stop_requested",
                "Watcher stop requested: yes",
              ]);
            }
            requireText("backend-lifecycle-summary", [
              "Backend lifecycle handoff:",
              "Request status: Safe to request",
              "Close-readiness: safe",
              "Backend authority: /api/backend/shutdown remains token-protected",
              "Next step: use this only when you are done with the WebView/local backend session.",
            ]);
            const originalConfirm = window.confirm;
            let confirmCount = 0;
            let confirmMessage = "";
            window.confirm = (message) => {
              confirmCount += 1;
              confirmMessage = String(message || "");
              return true;
            };
            const apiRecorder = installApiPostRecorder();
            try {
              await window.requestBackendShutdown();
            } finally {
              apiRecorder.restore();
              window.confirm = originalConfirm;
            }
            await waitFor(
              () => lifecycleHistory().some((entry) => entry.ok === true && String(entry.message || "").includes("Backend shutdown requested")),
              "backend-owned shutdown result",
            );
            const shutdownPost = apiRecorder.posts.find((entry) => entry.path === "/api/backend/shutdown");
            if (!shutdownPost) throw new Error("safe shutdown did not post /api/backend/shutdown");
            if (shutdownPost.payload.reason !== "webview-safe-close-request") {
              throw new Error("safe shutdown posted unexpected payload: " + JSON.stringify(shutdownPost));
            }
            requireText("backend-shutdown-status", ["Backend shutdown requested"]);
            if (confirmCount !== 1) throw new Error("safe shutdown should ask for one confirmation; got " + confirmCount);
            if (!confirmMessage.includes("Close the local WebView backend now")) {
              throw new Error("safe shutdown confirmation did not describe local backend close. Actual:\\n" + confirmMessage);
            }
            return {
              ok: true,
              scenario,
              confirmCount,
              confirmMessage,
              shutdownPosts: apiRecorder.posts,
              shutdownDisabled: shutdownButton().disabled,
              lifecycleSummary: text("backend-lifecycle-summary"),
              closeReadiness: text("diagnostics-close-readiness"),
              shutdownStatus: text("backend-shutdown-status"),
              shutdownHistoryCount: lifecycleHistory().length,
            };
          })()
          `;
        }

        async function runtimeValue(client, expression) {
          const result = await client.send("Runtime.evaluate", {
            expression,
            awaitPromise: true,
            returnByValue: true,
          });
          if (result.exceptionDetails) {
            const details = result.exceptionDetails;
            throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
          }
          return result.result?.value;
        }

        async function dispatchNavigationKey(client, keyName, autoRepeat = false) {
          const isEnter = keyName === "Enter";
          const key = isEnter ? "Enter" : " ";
          const code = isEnter ? "Enter" : "Space";
          const keyCode = isEnter ? 13 : 32;
          await client.send("Input.dispatchKeyEvent", {
            type: "keyDown",
            key,
            code,
            text: isEnter ? "\r" : " ",
            unmodifiedText: isEnter ? "\r" : " ",
            windowsVirtualKeyCode: keyCode,
            nativeVirtualKeyCode: keyCode,
            autoRepeat,
          });
          await client.send("Input.dispatchKeyEvent", {
            type: "keyUp",
            key,
            code,
            windowsVirtualKeyCode: keyCode,
            nativeVirtualKeyCode: keyCode,
          });
          await sleep(100);
        }

        async function runPrimaryNavigationKeyboardProbe(client) {
          const pages = await runtimeValue(client, `
            (() => {
              const buttons = Array.from(document.querySelectorAll(".nav-button[data-page]"));
              return buttons.map((button) => button.dataset.page || "");
            })()
          `);
          if (!Array.isArray(pages) || pages.length < 2) {
            throw new Error("Primary navigation buttons were not available for keyboard testing.");
          }
          const navigationReadyDeadline = Date.now() + 10000;
          let navigationReady = false;
          while (Date.now() < navigationReadyDeadline) {
            navigationReady = await runtimeValue(client, `
              (() => {
                const sentinel = ${JSON.stringify(pages[0])};
                const target = ${JSON.stringify(pages[1])};
                window.showPage(sentinel);
                document.querySelector('.nav-button[data-page="' + CSS.escape(target) + '"]')?.click();
                const active = document.querySelector("[data-page-panel].is-visible")?.dataset.pagePanel || "";
                window.showPage(sentinel);
                return active === target;
              })()
            `);
            if (navigationReady) break;
            await sleep(100);
          }
          if (!navigationReady) throw new Error("Primary navigation click handlers did not become ready.");
          await runtimeValue(client, `
            (() => {
              const buttons = Array.from(document.querySelectorAll(".nav-button[data-page]"));
              window.__primaryNavKeyboardProbe = { clicks: [] };
              buttons.forEach((button) => {
                button.addEventListener("click", () => {
                  window.__primaryNavKeyboardProbe.clicks.push(button.dataset.page || "");
                }, true);
              });
            })()
          `);

          const results = [];
          for (const keyName of ["Enter", "Space"]) {
            for (let index = 0; index < pages.length; index += 1) {
              const target = pages[index];
              const sentinel = pages[(index + 1) % pages.length];
              const prepared = await runtimeValue(client, `
                (() => {
                  const target = ${JSON.stringify(target)};
                  const sentinel = ${JSON.stringify(sentinel)};
                  window.showPage(sentinel);
                  const button = document.querySelector('.nav-button[data-page="' + CSS.escape(target) + '"]');
                  if (!button) throw new Error("missing primary nav button " + target);
                  button.focus({ preventScroll: true });
                  window.__primaryNavKeyboardProbe.clicks.length = 0;
                  return {
                    activePage: document.querySelector("[data-page-panel].is-visible")?.dataset.pagePanel || "",
                    focusedPage: document.activeElement?.dataset?.page || "",
                  };
                })()
              `);
              if (prepared.activePage !== sentinel || prepared.focusedPage !== target) {
                throw new Error(`Could not prepare ${keyName} navigation ${sentinel} -> ${target}: ${JSON.stringify(prepared)}`);
              }

              await dispatchNavigationKey(client, keyName);
              const observed = await runtimeValue(client, `
                (() => ({
                  activePages: Array.from(document.querySelectorAll("[data-page-panel].is-visible")).map((node) => node.dataset.pagePanel || ""),
                  ariaPages: Array.from(document.querySelectorAll('.nav-button[aria-current="page"]')).map((node) => node.dataset.page || ""),
                  focusedPage: document.activeElement?.closest?.("[data-page-panel]")?.dataset?.pagePanel || "",
                  focusedTag: document.activeElement?.tagName || "",
                  focusedText: document.activeElement?.textContent?.trim() || "",
                  clicks: window.__primaryNavKeyboardProbe.clicks.slice(),
                }))()
              `);
              const expectedClicks = keyName === "Enter" ? [] : [target];
              if (JSON.stringify(observed.activePages) !== JSON.stringify([target])) {
                throw new Error(`${keyName} did not activate only ${target}: ${JSON.stringify(observed)}`);
              }
              if (JSON.stringify(observed.ariaPages) !== JSON.stringify([target])) {
                throw new Error(`${keyName} did not set aria-current only on ${target}: ${JSON.stringify(observed)}`);
              }
              if (observed.focusedPage !== target) {
                throw new Error(`${keyName} did not move focus into destination ${target}: ${JSON.stringify(observed)}`);
              }
              if (observed.focusedTag !== "H1") {
                throw new Error(`${keyName} did not land focus on the destination heading for ${target}: ${JSON.stringify(observed)}`);
              }
              if (JSON.stringify(observed.clicks) !== JSON.stringify(expectedClicks)) {
                throw new Error(`${keyName} produced unexpected click activation for ${target}: ${JSON.stringify(observed)}`);
              }
              results.push({ keyName, target, sentinel, ...observed });
            }
          }

          const repeatTarget = pages[0];
          const repeatSentinel = pages[1];
          await runtimeValue(client, `
            (() => {
              window.showPage(${JSON.stringify(repeatSentinel)});
              const button = document.querySelector('.nav-button[data-page="' + CSS.escape(${JSON.stringify(repeatTarget)}) + '"]');
              button.focus({ preventScroll: true });
              window.__primaryNavKeyboardProbe.clicks.length = 0;
            })()
          `);
          await dispatchNavigationKey(client, "Enter", true);
          const repeatObserved = await runtimeValue(client, `
            (() => ({
              activePage: document.querySelector("[data-page-panel].is-visible")?.dataset.pagePanel || "",
              ariaPage: document.querySelector('.nav-button[aria-current="page"]')?.dataset.page || "",
              focusedPage: document.activeElement?.dataset?.page || "",
              clicks: window.__primaryNavKeyboardProbe.clicks.slice(),
            }))()
          `);
          if (repeatObserved.activePage !== repeatSentinel || repeatObserved.ariaPage !== repeatSentinel) {
            throw new Error(`Repeated Enter unexpectedly activated ${repeatTarget}: ${JSON.stringify(repeatObserved)}`);
          }
          if (repeatObserved.focusedPage !== repeatTarget || repeatObserved.clicks.length !== 0) {
            throw new Error(`Repeated Enter changed focus or dispatched a click: ${JSON.stringify(repeatObserved)}`);
          }
          return { ok: true, cases: results, repeatObserved };
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`,
            payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.getElementById("backend-shutdown-button") && document.getElementById("backend-lifecycle-summary") && document.getElementById("diagnostics-close-readiness") && typeof window.requestBackendShutdown === "function" && typeof window.getCommandHistory === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("backend-shutdown-button") && document.getElementById("backend-lifecycle-summary") && document.getElementById("diagnostics-close-readiness") && typeof window.requestBackendShutdown === "function" && typeof window.getCommandHistory === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Backend lifecycle WebView globals or DOM nodes did not become ready.");
            const resultValue = payload.scenario === "navigation"
              ? await runPrimaryNavigationKeyboardProbe(client)
              : await runtimeValue(client, lifecycleScript(payload.scenario));
            await sleep(750);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: resultValue || {} }));
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


def _run_browser_lifecycle_smoke(*, browser_path: str, url: str, scenario: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView lifecycle smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-lifecycle-payload.json"
        runner_path = tmp / "browser-lifecycle-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "scenario": scenario,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_lifecycle_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            f"Browser-backed WebView lifecycle smoke ({scenario})",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserLifecycleSmoke(unittest.TestCase):
    def _service_with_fixture(self, root: Path) -> tuple[object, DummyWorkflowFacadeService]:
        resolved, _source, _output = _write_fixture_state(root)
        service = DummyWorkflowFacadeService(root)
        snapshot = service.build_snapshot(resolved, str(root))
        if snapshot.progress is None:
            snapshot.progress = {}
        snapshot.progress["Status"] = "Completed"
        service.snapshot = snapshot
        service.find_related_pipeline_processes = lambda _resolved: []
        service.read_progress = lambda _resolved: {}
        service.is_progress_stale = lambda _progress: True
        service.read_audit_progress = lambda _resolved: {}
        service.is_audit_progress_stale = lambda _progress: True
        return resolved, service

    def test_real_browser_blocks_shutdown_while_schedule_stop_watcher_is_armed(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView lifecycle smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, service = self._service_with_fixture(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            deadline = datetime.now() + timedelta(minutes=10)
            facade._schedule_stop_watcher.arm(
                service=service,
                resolved=resolved,
                proc=DummyProc(24680),
                deadline=deadline,
            )
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="browser-lifecycle-blocked-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                status, readiness = _get_json(f"{server.url}/api/backend/close-readiness", token=server.token)
                self.assertEqual(status, 200)
                self.assertFalse(readiness["safe_to_close"])
                self.assertEqual(readiness["continuous_watcher"]["status"], "armed")
                result = _run_browser_lifecycle_smoke(browser_path=browser_path, url=f"{server.url}/", scenario="blocked")
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

            browser_result = result["result"]
            self.assertEqual(browser_result["confirmCount"], 0)
            self.assertTrue(browser_result["shutdownDisabled"])
            self.assertIn("Watcher armed", browser_result["lifecycleSummary"])
            self.assertIn("disabled in WebView", browser_result["shutdownStatus"])
            self.assertFalse(shutdown_event.is_set())

    def test_real_browser_primary_nav_keyboard_activation_is_explicit_and_single(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView lifecycle smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, service = self._service_with_fixture(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-navigation-keyboard-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_lifecycle_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    scenario="navigation",
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

            browser_result = result["result"]
            cases = browser_result["cases"]
            expected_nav_pages = {
                "home", "launch", "live", "metrics", "queue", "completed", "pending", "rename",
                "reports", "network", "libraries", "schedule", "settings", "diagnostics", "maintenance",
            }
            self.assertEqual(len(cases), len(expected_nav_pages) * 2)
            self.assertEqual({case["target"] for case in cases}, expected_nav_pages)
            self.assertEqual({case["keyName"] for case in cases}, {"Enter", "Space"})

    def test_real_browser_requests_backend_shutdown_only_when_close_readiness_is_safe(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView lifecycle smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, service = self._service_with_fixture(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="browser-lifecycle-safe-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                status, readiness = _get_json(f"{server.url}/api/backend/close-readiness", token=server.token)
                self.assertEqual(status, 200)
                self.assertTrue(readiness["safe_to_close"])
                result = _run_browser_lifecycle_smoke(browser_path=browser_path, url=f"{server.url}/", scenario="safe")
                self.assertTrue(shutdown_event.wait(2.0))
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

            browser_result = result["result"]
            self.assertEqual(browser_result["confirmCount"], 1)
            self.assertIn("Close the local WebView backend now", browser_result["confirmMessage"])
            self.assertIn("Safe to request", browser_result["lifecycleSummary"])
            self.assertIn("Backend shutdown requested", browser_result["shutdownStatus"])

    def test_real_browser_treats_stop_requested_watcher_as_safe_shutdown_evidence(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView lifecycle smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, service = self._service_with_fixture(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            proc = DummyProc(24680)
            proc._mediapipeline_launch_id = "browser-lifecycle-stop-requested-launch"
            facade._schedule_stop_watcher.arm(
                service=service,
                resolved=resolved,
                proc=proc,
                deadline=datetime.now() - timedelta(seconds=1),
            )
            watcher_deadline = time.monotonic() + 2.0
            while time.monotonic() < watcher_deadline:
                if facade._schedule_stop_watcher.state().status == "stop_requested":
                    break
                time.sleep(0.02)
            self.assertEqual(facade._schedule_stop_watcher.state().status, "stop_requested")
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="browser-lifecycle-stop-requested-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                status, readiness = _get_json(f"{server.url}/api/backend/close-readiness", token=server.token)
                self.assertEqual(status, 200)
                self.assertTrue(readiness["safe_to_close"])
                self.assertEqual(readiness["continuous_watcher"]["status"], "stop_requested")
                self.assertTrue(readiness["continuous_watcher"]["stop_requested"])
                result = _run_browser_lifecycle_smoke(browser_path=browser_path, url=f"{server.url}/", scenario="stop_requested")
                self.assertTrue(shutdown_event.wait(2.0))
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

            browser_result = result["result"]
            self.assertEqual(browser_result["confirmCount"], 1)
            self.assertIn("stop_requested", browser_result["lifecycleSummary"])
            self.assertIn("Backend shutdown requested", browser_result["shutdownStatus"])


if __name__ == "__main__":
    unittest.main()
