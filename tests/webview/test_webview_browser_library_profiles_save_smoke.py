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


def _browser_library_profiles_save_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function libraryProfilesSaveScript() {
          return `
          (async () => {
            const stages = [];
            function stage(name) {
              stages.push(name);
              window.__libraryProfilesSaveSmokeStages = stages.slice();
            }
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function click(id) {
              const node = byId(id);
              if (!node) throw new Error("missing control " + id);
              node.click();
            }
            function setValue(control, value) {
              if (!control) throw new Error("missing control for value " + value);
              control.value = value;
              control.dispatchEvent(new Event("input", { bubbles: true }));
              control.dispatchEvent(new Event("change", { bubbles: true }));
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 15000;
              while (Date.now() < deadline) {
                if (predicate()) return;
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label);
            }

            async function run() {
              stage("show libraries");
              window.showPage("libraries");
              await waitFor(() => document.querySelectorAll("#settings-library-profile-list .settings-library-card").length >= 2, "library profile cards");
              await waitFor(() => Boolean(byId("settings-library-summary-rows") && byId("settings-library-scan-sources-button")), "library summary tiles");
              stage("cards loaded");
              const summaryTilesBefore = document.querySelectorAll("#settings-library-summary-rows [data-library-summary-row]").length;
              const initialProfiles = window.mediaPipelineSettingsView.getLastSettings()?.config?.LibraryProfiles || [];
              const posts = [];
              const originalApiPost = window.mediaPipelineApi.apiPost;
              const originalAlert = window.alert;
              window.alert = () => {};
              window.mediaPipelineApi.apiPost = async (path, body, options) => {
                if (String(path || "") === "/api/settings/preview-patch" || String(path || "") === "/api/settings/save-patch") {
                  posts.push({ path: String(path || ""), body: JSON.parse(JSON.stringify(body || {})) });
                }
                return originalApiPost(path, body, options);
              };
              try {
              click("settings-library-add-button");
              await waitFor(() => {
                const card = document.querySelector("#settings-library-profile-list .settings-library-profile-pane.is-active .settings-library-card");
                return Boolean(card && !["movies", "tv"].includes(card.dataset.libraryId || ""));
              }, "custom library profile card");
              stage("custom card added");
              const card = document.querySelector("#settings-library-profile-list .settings-library-profile-pane.is-active .settings-library-card");
              const profileId = card?.dataset.libraryId || "";
              const identity = card?.querySelector("[data-library-identity]");
              if (!profileId || !identity || identity.value !== profileId || identity.readOnly !== true) {
                throw new Error("Library identity field did not expose the immutable card identity.");
              }
              setValue(card.querySelector('[data-library-field="name"]'), "Browser Concerts");
              setValue(card.querySelector('[data-library-field="designation"]'), "movie");
              setValue(card.querySelector('[data-library-field="source_path"]'), "E:\\\\BrowserConcerts");
              stage("fields edited");
              click("settings-library-save-button");
              await waitFor(() => {
                const dialog = byId("settings-save-review-dialog");
                return Boolean(dialog && (dialog.open || dialog.getAttribute("open") !== null));
              }, "settings save review dialog");
              stage("review dialog open");
              const previewPosts = posts.filter((entry) => entry.path === "/api/settings/preview-patch");
              const savePostsBeforeConfirm = posts.filter((entry) => entry.path === "/api/settings/save-patch");
              if (previewPosts.length !== 1 || savePostsBeforeConfirm.length !== 0) {
                throw new Error("Library save did not preview exactly once before confirmation: " + JSON.stringify(posts));
              }
              if (!text("settings-save-review-dialog-detail").includes("LibraryProfiles change detail:")) {
                throw new Error("Library save review did not show LibraryProfiles detail.");
              }
              click("settings-save-review-confirm-button");
              stage("review confirmed");
              await waitFor(() => text("settings-libraries-status").includes("saved"), "library profile saved status");
              stage("save status reported");
              await waitFor(() => text("settings-patch-detail").includes("Reload verified: yes"), "reload verification detail");
              stage("reload verified");
              await waitFor(() => {
                const profiles = window.mediaPipelineSettingsView.getLastSettings()?.config?.LibraryProfiles || [];
                return profiles.some((profile) => String(profile?.name || "") === "Browser Concerts");
              }, "reloaded settings include custom library profile");
              stage("settings reloaded");
              const savePosts = posts.filter((entry) => entry.path === "/api/settings/save-patch");
              if (savePosts.length !== 1) throw new Error("Library save did not issue exactly one save post: " + JSON.stringify(posts));
              const saveBody = savePosts[0].body || {};
              if (saveBody.confirm_save !== true || !saveBody.review_confirmation?.preview_id) {
                throw new Error("Library save did not include review_confirmation and confirm_save: " + JSON.stringify(saveBody));
              }
              const savedProfiles = saveBody.changes?.LibraryProfiles || [];
              if (!savedProfiles.some((profile) => profile.id === profileId && profile.name === "Browser Concerts")) {
                throw new Error("Library save payload did not preserve custom profile id/name: " + JSON.stringify(savedProfiles));
              }
              return {
                ok: true,
                profileId,
                initialProfileCount: initialProfiles.length,
                savedProfileCount: savedProfiles.length,
                summaryTilesBefore,
                previewPostCount: previewPosts.length,
                savePostCount: savePosts.length,
                patchDetail: text("settings-patch-detail"),
              };
              } finally {
                window.mediaPipelineApi.apiPost = originalApiPost;
                window.alert = originalAlert;
              }
            }
            return Promise.race([
              run(),
              new Promise((_, reject) => setTimeout(() => reject(new Error("LibraryProfiles page script stalled after: " + stages.join(" > "))), 30000)),
            ]);
          })()
          `;
        }

        async function main() {
          async function withTimeout(promise, label, timeoutMs = 45000) {
            let timer = null;
            try {
              return await Promise.race([
                promise,
                new Promise((_, reject) => {
                  timer = setTimeout(() => reject(new Error(label + " timed out")), timeoutMs);
                }),
              ]);
            } finally {
              if (timer) clearTimeout(timer);
            }
          }
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
                expression: `Boolean(document.getElementById("settings-library-profile-list") && document.getElementById("settings-library-summary-rows") && document.getElementById("settings-library-save-button") && typeof window.showPage === "function" && typeof window.mediaPipelineSettingsLibraries?.saveLibraryProfiles === "function" && typeof window.mediaPipelineSettingsLibraries?.renderLibrarySummary === "function" && window.mediaPipelineApi?.tokenPresent === true)`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const result = await withTimeout(
              client.send("Runtime.evaluate", {
                expression: libraryProfilesSaveScript(),
                awaitPromise: true,
                returnByValue: true,
              }),
              "LibraryProfiles browser evaluation"
            );
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


def _run_browser_library_profiles_save_smoke(*, browser_path: str, url: str, token: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed LibraryProfiles save smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-library-profiles-save-payload.json"
        runner_path = tmp / "browser-library-profiles-save-runner.cjs"
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
        runner_path.write_text(_browser_library_profiles_save_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView LibraryProfiles save smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserLibraryProfilesSaveSmoke(unittest.TestCase):
    def test_real_browser_saves_library_profile_with_review_confirmation_and_reload(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed LibraryProfiles save smoke.")

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
                token="browser-library-profiles-save-token",
                shell_surface="tauri",
                resolved_provider=lambda: resolved,
                resolved_reload=resolved_reload,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_library_profiles_save_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    token=server.token,
                )
            finally:
                server.stop()

            self.assertTrue(result["ok"])
            summary = result["result"]
            self.assertTrue(summary["profileId"].startswith("library-"))
            self.assertEqual(summary["previewPostCount"], 1)
            self.assertEqual(summary["savePostCount"], 1)
            self.assertGreater(summary["savedProfileCount"], summary["initialProfileCount"])
            self.assertIn("Reload verified: yes", summary["patchDetail"])
            assert_media_no_mutation(self, media_snapshot)


if __name__ == "__main__":
    unittest.main()
