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


def _browser_settings_builder_flush_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function invalidBuilderScript() {
          return `
          (async () => {
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function click(id) {
              const node = byId(id);
              if (!node) throw new Error("missing control " + id);
              node.click();
            }
            function setTextarea(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing textarea " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function setInput(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing input " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function setInputSelector(selector, value) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing input selector " + selector);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function clickSettingsTab(tabId) {
              const button = document.querySelector('.settings-section-nav-btn[data-settings-tab="' + tabId + '"]');
              if (!button) throw new Error("missing settings section " + tabId);
              button.click();
            }

            window.showPage("settings");
            clickSettingsTab("queue-runtime");

            async function runInvalidBuilderCase(name, arrangeInvalidBuilder, expectedDetailFragments) {
              setTextarea("settings-patch-json", JSON.stringify({ RoutingProfile: "plex_direct_play" }, null, 2));
              arrangeInvalidBuilder();

              const invalidBuilderPosts = [];
              const originalApiPost = window.apiPost;
              const originalConfirm = window.confirm;
              window.apiPost = async (path, body) => {
                invalidBuilderPosts.push({ path: String(path || ""), body: JSON.parse(JSON.stringify(body || {})) });
                return { ok: true, command: "settings.mocked", message: name + " should not post" };
              };
              window.confirm = () => true;
              try {
                click("settings-preview-patch-button");
                await new Promise((resolve) => setTimeout(resolve, 250));
                click("settings-save-patch-button");
                await new Promise((resolve) => setTimeout(resolve, 250));
              } finally {
                window.apiPost = originalApiPost;
                window.confirm = originalConfirm;
              }

              requireText("settings-patch-status", ["Builder invalid"]);
              requireText("settings-patch-detail", expectedDetailFragments);
              const settingsPosts = invalidBuilderPosts.filter((entry) => {
                return entry.path === "/api/settings/preview-patch" || entry.path === "/api/settings/save-patch";
              });
              if (settingsPosts.length) {
                throw new Error(name + " invalid dirty settings builder still posted Preview/Save: " + JSON.stringify(invalidBuilderPosts));
              }
              return {
                name,
                patchStatus: text("settings-patch-status"),
                patchDetail: text("settings-patch-detail"),
                invalidBuilderPosts: settingsPosts,
              };
            }

            const pathMapRowCase = await runInvalidBuilderCase(
              "network-path-map-row",
              () => {
                window.mediaPipelineSettingsView.syncRuntimeSettingsBuilderFromConfig();
                window.mediaPipelineSettingsView.syncNetworkSettingsBuilderFromConfig();
                setInput("settings-network-role", "worker");
                setInput("settings-network-worker-url", "http://10.0.0.20:7830");
                const row = "#settings-network-path-map-rows tr[data-path-map-row]";
                setInputSelector(row + ' [data-path-map-field="from"]', "D:/Source");
                setInputSelector(row + ' [data-path-map-field="to"]', "");
                window.mediaPipelineSettingsView.markNetworkSettingsBuilderDirty();
              },
              ["Source Path Map row", "both From prefix and To prefix"]
            );
            const numericCase = await runInvalidBuilderCase(
              "runtime-positive-number",
              () => {
                window.mediaPipelineSettingsView.syncNetworkSettingsBuilderFromConfig();
                window.mediaPipelineSettingsView.syncRuntimeSettingsBuilderFromConfig();
                setInput("settings-runtime-ffmpeg-encode-timeout", "0");
                window.mediaPipelineSettingsView.markRuntimeSettingsBuilderDirty();
              },
              ["Encode Timeout", "one or higher"]
            );

            return {
              ok: true,
              patchStatus: text("settings-patch-status"),
              patchDetail: text("settings-patch-detail"),
              cases: [pathMapRowCase, numericCase],
            };
          })()
          `;
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
                expression: `Boolean(document.getElementById("settings-preview-patch-button") && document.getElementById("settings-save-patch-button") && document.getElementById("settings-network-path-map") && document.getElementById("settings-runtime-ffmpeg-encode-timeout") && typeof window.showPage === "function" && typeof window.mediaPipelineSettingsView?.previewSettingsPatch === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("settings-preview-patch-button") && document.getElementById("settings-save-patch-button") && document.getElementById("settings-network-path-map") && document.getElementById("settings-runtime-ffmpeg-encode-timeout") && typeof window.showPage === "function" && typeof window.mediaPipelineSettingsView?.previewSettingsPatch === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Settings builder WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: invalidBuilderScript(),
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


def _run_browser_settings_builder_flush_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed Settings builder flush smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-settings-builder-flush-payload.json"
        runner_path = tmp / "browser-settings-builder-flush-runner.cjs"
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
        runner_path.write_text(_browser_settings_builder_flush_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Settings builder flush smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserSettingsBuilderFlushSmoke(unittest.TestCase):
    def test_invalid_dirty_builder_blocks_preview_and_save_posts(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Settings builder flush smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-settings-builder-flush-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_settings_builder_flush_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        self.assertEqual(browser_result["patchStatus"], "Builder invalid")
        self.assertIn("Encode Timeout", browser_result["patchDetail"])
        self.assertEqual([case["name"] for case in browser_result["cases"]], ["network-path-map-row", "runtime-positive-number"])
        for case in browser_result["cases"]:
            self.assertEqual(case["patchStatus"], "Builder invalid")
            self.assertEqual(case["invalidBuilderPosts"], [])


if __name__ == "__main__":
    unittest.main()
