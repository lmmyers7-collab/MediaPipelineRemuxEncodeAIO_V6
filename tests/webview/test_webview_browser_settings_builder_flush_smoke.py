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
              window.apiPost = async (path, body) => {
                invalidBuilderPosts.push({ path: String(path || ""), body: JSON.parse(JSON.stringify(body || {})) });
                return { ok: true, command: "settings.mocked", message: name + " should not post" };
              };
              try {
                click("settings-save-header-save-button");
                await new Promise((resolve) => setTimeout(resolve, 250));
              } finally {
                window.apiPost = originalApiPost;
              }

              requireText("settings-patch-status", ["Builder invalid"]);
              requireText("settings-patch-detail", expectedDetailFragments);
              const settingsPosts = invalidBuilderPosts.filter((entry) => {
                return entry.path === "/api/settings/preview-patch" || entry.path === "/api/settings/save-patch";
              });
              if (settingsPosts.length) {
                throw new Error(name + " invalid dirty settings builder still posted Save: " + JSON.stringify(invalidBuilderPosts));
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
              ["runtime builder", "one or higher"]
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

        function settingsSaveScript() {
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
            function clickSettingsTab(tabId) {
              const button = document.querySelector('.settings-section-nav-btn[data-settings-tab="' + tabId + '"]');
              if (!button) throw new Error("missing settings section " + tabId);
              button.click();
            }
            async function waitFor(predicate, label, timeoutMs = 6000) {
              const deadline = Date.now() + timeoutMs;
              while (Date.now() < deadline) {
                if (predicate()) return;
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label);
            }

            window.showPage("settings");
            clickSettingsTab("queue-runtime");
            window.mediaPipelineSettingsView.syncNetworkSettingsBuilderFromConfig();
            window.mediaPipelineSettingsView.syncRuntimeSettingsBuilderFromConfig();
            setTextarea("settings-patch-json", JSON.stringify({
              RoutingProfile: "plex_direct_play",
              OutputContainer: "mkv",
            }, null, 2));

            const previewPosts = [];
            const savePosts = [];
            const originalApiPost = window.apiPost;
            const originalRenamePatch = window.mediaPipelineRenameView?.renameCleaningFilterConfigPatch;
            const originalAlert = window.alert;
            window.alert = () => {};
            if (window.mediaPipelineRenameView && typeof originalRenamePatch === "function") {
              window.mediaPipelineRenameView.renameCleaningFilterConfigPatch = () => ({});
            }
            let saveCompletionStatus = "";
            let saveCompletionDetail = "";
            let headerPatchAfterSave = "";
            window.apiPost = async (path, body, options) => {
              const clonedBody = JSON.parse(JSON.stringify(body || {}));
              if (String(path || "") === "/api/settings/preview-patch") {
                previewPosts.push({ path: String(path || ""), body: clonedBody });
              }
              if (String(path || "") === "/api/settings/save-patch") {
                savePosts.push({ path: String(path || ""), body: clonedBody });
              }
              return originalApiPost(path, body, options);
            };
            try {
              click("settings-save-header-save-button");
              await waitFor(() => {
                const dialog = byId("settings-save-review-dialog");
                return Boolean(dialog && (dialog.open || dialog.getAttribute("open") !== null));
              }, "settings save review dialog");
              if (previewPosts.length !== 1) throw new Error("Expected exactly one preview before review: " + JSON.stringify(previewPosts));
              if (savePosts.length !== 0) throw new Error("Save Settings posted before confirmation: " + JSON.stringify(savePosts));
              if (text("settings-save-review-dialog-changed") !== "1") {
                throw new Error("Review dialog did not use backend-confirmed changed count: " + text("settings-save-review-dialog-changed"));
              }
              if (text("settings-save-review-dialog-submitted") !== "2") {
                throw new Error("Review dialog did not show submitted count: " + text("settings-save-review-dialog-submitted"));
              }
              const reviewRowsBeforeConfirm = Array.from(document.querySelectorAll("#settings-save-review-dialog-rows tr"))
                .map((row) => row.textContent || "");
              if (reviewRowsBeforeConfirm.length !== 1 || !reviewRowsBeforeConfirm[0].includes("plex_direct_play")) {
                throw new Error("Review dialog did not show only the backend-confirmed RoutingProfile row: " + JSON.stringify(reviewRowsBeforeConfirm));
              }
              if (reviewRowsBeforeConfirm.join("\\n").includes("mkv")) {
                throw new Error("Review dialog still showed unchanged OutputContainer value: " + JSON.stringify(reviewRowsBeforeConfirm));
              }
              click("settings-save-review-confirm-button");
              await waitFor(() => text("settings-patch-status").includes("Saved"), "settings save completion");
              saveCompletionStatus = text("settings-patch-status");
              saveCompletionDetail = text("settings-patch-detail");
              if (!saveCompletionDetail.includes("Reloaded:")) {
                throw new Error("Save completion detail did not include reload evidence:\\n" + saveCompletionDetail);
              }
              if (!saveCompletionDetail.includes("Reload verified:")) {
                throw new Error("Save completion detail did not include reload verification evidence:\\n" + saveCompletionDetail);
              }

              await waitFor(() => (byId("settings-patch-json")?.value || "").trim() === "{}", "patch JSON cleared after save");
              await waitFor(() => text("settings-save-header-patch-status").includes("No changes"), "save header no changes");
              headerPatchAfterSave = text("settings-save-header-patch-status");

              click("settings-save-header-save-button");
              await new Promise((resolve) => setTimeout(resolve, 250));
              if ((byId("settings-save-review-dialog")?.open)) throw new Error("Second Save opened a review dialog after a successful save.");
              if (previewPosts.length !== 1) throw new Error("Second Save posted another preview with no staged changes: " + JSON.stringify(previewPosts));
              if (savePosts.length !== 1) throw new Error("Second Save posted another save with no staged changes: " + JSON.stringify(savePosts));
              const secondSaveStatus = text("settings-patch-status");
              if (!secondSaveStatus.includes("No changes")) {
                throw new Error("Second Save did not leave the status at No changes: " + secondSaveStatus);
              }

              setTextarea("settings-patch-json", JSON.stringify({
                RoutingProfile: "plex_direct_play",
                OutputContainer: "mkv",
              }, null, 2));
              click("settings-save-header-save-button");
              await waitFor(() => text("settings-patch-status").includes("No backend changes"), "same-value backend no-op");
              if ((byId("settings-save-review-dialog")?.open)) throw new Error("Same-value submitted JSON opened a review dialog.");
              if (previewPosts.length !== 2) throw new Error("Same-value Save did not post exactly one additional preview: " + JSON.stringify(previewPosts));
              if (savePosts.length !== 1) throw new Error("Same-value Save unexpectedly posted another save: " + JSON.stringify(savePosts));
              if ((byId("settings-patch-json")?.value || "").trim() !== "{}") {
                throw new Error("Same-value Save did not clear stale candidate JSON: " + (byId("settings-patch-json")?.value || ""));
              }
            } finally {
              window.apiPost = originalApiPost;
              window.alert = originalAlert;
              if (window.mediaPipelineRenameView && typeof originalRenamePatch === "function") {
                window.mediaPipelineRenameView.renameCleaningFilterConfigPatch = originalRenamePatch;
              }
            }

            if (previewPosts[0].body.confirm_save === true) throw new Error("Preview request included save confirmation: " + JSON.stringify(previewPosts[0]));
            if (!previewPosts[0].body.changes || previewPosts[0].body.changes.RoutingProfile !== "plex_direct_play") {
              throw new Error("Preview request did not include the expected RoutingProfile candidate: " + JSON.stringify(previewPosts[0]));
            }
            if (savePosts.length !== 1) throw new Error("Expected exactly one Save Settings post: " + JSON.stringify(savePosts));
            if (savePosts[0].body.confirm_save !== true) throw new Error("Save Settings post did not include confirm_save true: " + JSON.stringify(savePosts[0]));
            if (!savePosts[0].body.review_confirmation || !savePosts[0].body.review_confirmation.preview_id) {
              throw new Error("Save Settings post did not include backend review_confirmation: " + JSON.stringify(savePosts[0]));
            }
            if (!savePosts[0].body.changes || savePosts[0].body.changes.RoutingProfile !== "plex_direct_play") {
              throw new Error("Save Settings post did not include the expected RoutingProfile change: " + JSON.stringify(savePosts[0]));
            }

            const renderedText = [
              text("settings-patch-status"),
              text("settings-patch-detail"),
              text("settings-backend-result-status"),
              text("settings-backend-result-summary"),
              text("settings-backend-result-rows"),
              text("settings-save-header-reload-status"),
            ].join("\\n");
            if (renderedText.includes("Failed to fetch")) throw new Error("Settings save rendered Failed to fetch:\\n" + renderedText);
            requireText("settings-backend-result-summary", ["Save:", "Reload:"]);
            const resultRows = document.querySelectorAll("#settings-backend-result-rows tr");
            if (!resultRows.length) throw new Error("Settings backend-result rows did not render.");

            return {
              ok: true,
              patchStatus: text("settings-patch-status"),
              patchDetail: text("settings-patch-detail"),
              saveCompletionStatus,
              saveCompletionDetail,
              backendResultStatus: text("settings-backend-result-status"),
              backendResultSummary: text("settings-backend-result-summary"),
              headerReloadStatus: text("settings-save-header-reload-status"),
              headerPatchAfterSave,
              headerPatchStatus: text("settings-save-header-patch-status"),
              patchJson: byId("settings-patch-json")?.value || "",
              previewPosts,
              savePosts,
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
            "about:blank",
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, "about:blank");
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            await client.send("Page.addScriptToEvaluateOnNewDocument", {
              source: `window.MEDIA_PIPELINE_TAURI_BOOTSTRAP = {
                apiBase: "",
                token: ${JSON.stringify(payload.token)},
                tokenSource: "tauri-initialization-script",
                shellSurface: "tauri",
              };`,
            });
            await client.send("Page.navigate", { url: payload.url });
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.getElementById("settings-save-patch-button") && document.getElementById("settings-network-path-map") && document.getElementById("settings-runtime-ffmpeg-encode-timeout") && typeof window.showPage === "function" && typeof window.mediaPipelineSettingsView?.saveSettingsPatch === "function" && window.mediaPipelineApi?.tokenPresent === true && String(window.MEDIA_PIPELINE_BOOTSTRAP?.shellSurface || "").toLowerCase() === "tauri")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("settings-save-patch-button") && document.getElementById("settings-network-path-map") && document.getElementById("settings-runtime-ffmpeg-encode-timeout") && typeof window.showPage === "function" && typeof window.mediaPipelineSettingsView?.saveSettingsPatch === "function" && window.mediaPipelineApi?.tokenPresent === true && String(window.MEDIA_PIPELINE_BOOTSTRAP?.shellSurface || "").toLowerCase() === "tauri")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Settings builder WebView globals or DOM nodes did not become ready.");
            const invalidResult = await client.send("Runtime.evaluate", {
              expression: invalidBuilderScript(),
              awaitPromise: true,
              returnByValue: true,
            });
            if (invalidResult.exceptionDetails) {
              const details = invalidResult.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            const saveResult = await client.send("Runtime.evaluate", {
              expression: settingsSaveScript(),
              awaitPromise: true,
              returnByValue: true,
            });
            if (saveResult.exceptionDetails) {
              const details = saveResult.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            await sleep(500);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({
              ok: true,
              result: {
                invalidBuilder: invalidResult.result?.value || {},
                save: saveResult.result?.value || {},
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


def _run_browser_settings_builder_flush_smoke(*, browser_path: str, url: str, token: str) -> dict[str, object]:
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
                    "token": token,
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

            def resolved_reload() -> object:
                if service.saved_config_calls:
                    resolved.config_data = dict(service.saved_config_calls[-1]["config_values"])
                return resolved

            server = LocalApiServer(
                facade,
                token="browser-settings-builder-flush-token",
                shell_surface="tauri",
                resolved_provider=lambda: resolved,
                resolved_reload=resolved_reload,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_settings_builder_flush_smoke(
                    browser_path=browser_path,
                    token=server.token,
                    url=f"{server.url}/",
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        invalid_result = result["result"]["invalidBuilder"]
        self.assertEqual(invalid_result["patchStatus"], "Builder invalid")
        self.assertIn("runtime builder", invalid_result["patchDetail"])
        self.assertIn("one or higher", invalid_result["patchDetail"])
        self.assertEqual([case["name"] for case in invalid_result["cases"]], ["network-path-map-row", "runtime-positive-number"])
        for case in invalid_result["cases"]:
            self.assertEqual(case["patchStatus"], "Builder invalid")
            self.assertEqual(case["invalidBuilderPosts"], [])
        save_result = result["result"]["save"]
        self.assertEqual(save_result["saveCompletionStatus"], "Saved")
        self.assertIn("Reloaded:", save_result["saveCompletionDetail"])
        self.assertIn("Reload verified:", save_result["saveCompletionDetail"])
        self.assertEqual(save_result["patchStatus"], "No backend changes")
        self.assertIn("No backend settings differ", save_result["patchDetail"])
        self.assertIn("Save:", save_result["backendResultSummary"])
        self.assertIn("Reload:", save_result["backendResultSummary"])
        self.assertEqual(save_result["headerPatchAfterSave"], "No changes")
        self.assertEqual(save_result["headerPatchStatus"], "No backend changes")
        self.assertEqual(save_result["patchJson"].strip(), "{}")
        self.assertEqual(len(save_result["previewPosts"]), 2)
        self.assertEqual(save_result["previewPosts"][0]["path"], "/api/settings/preview-patch")
        self.assertNotIn("confirm_save", save_result["previewPosts"][0]["body"])
        self.assertEqual(save_result["previewPosts"][0]["body"]["changes"]["RoutingProfile"], "plex_direct_play")
        self.assertEqual(len(save_result["savePosts"]), 1)
        self.assertEqual(save_result["savePosts"][0]["path"], "/api/settings/save-patch")
        self.assertIs(save_result["savePosts"][0]["body"]["confirm_save"], True)
        self.assertTrue(save_result["savePosts"][0]["body"]["review_confirmation"]["preview_id"])
        self.assertEqual(save_result["savePosts"][0]["body"]["changes"]["RoutingProfile"], "plex_direct_play")


if __name__ == "__main__":
    unittest.main()
