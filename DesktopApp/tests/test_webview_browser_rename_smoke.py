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


def _browser_rename_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function browserRenameScript() {
          return `
          (async () => {
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function setValue(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing input " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
            }
            function setChecked(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing checkbox " + id);
              node.checked = Boolean(value);
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function click(selector, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.click();
            }
            function readinessCells() {
              return Array.from(document.querySelectorAll("#rename-apply-readiness-rows td")).map((cell) => cell.textContent || "").join("\\n");
            }
            function outcomeCells() {
              return Array.from(document.querySelectorAll("#rename-apply-outcome-rows td")).map((cell) => cell.textContent || "").join("\\n");
            }
            function requireReadiness(fragments) {
              const actual = readinessCells();
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error("readiness table missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            [
              "showPage",
              "renderRenamePreview",
              "selectRenameRow",
              "checkApplicableRenameRows",
              "applySelectedRename",
              "renameApplyReadinessRows",
              "renameApplyScopeBlockers",
              "renderRenamePipelineHandoff",
              "renderRenameApplyResult",
              "renameApplyOutcomeRows",
              "renameApplyProgressBars",
            ].forEach(requireFunction);
            window.getLastSettings = () => ({
              config: {
                RoutingProfile: "plex_direct_stream",
                SizeGuardMode: "advisory",
                OutputContainer: "mkv",
                ConvertTx3gToSrt: true,
                DropTx3gAfterConversion: false,
                ConvertBdpgsToSrt: true,
                DropBdpgsAfterConversion: false,
                DropAssAfterConversion: false,
                DeferredPublish: true,
              },
            });

            window.showPage("rename");
            const originalApiPost = window.apiPost;
            const browsePosts = [];
            window.apiPost = async (url, body) => {
              if (String(url || "") === "/api/rename/browse") {
                browsePosts.push({ url: String(url || ""), body: body || {} });
                return {
                  command: "rename.browse",
                  ok: true,
                  message: "Windows file browser selected 2 files.",
                  data: {
                    paths: ["C:/Browse/Selected Rename A.mkv", "C:/Browse/Selected Rename B.mkv"],
                    selection_mode: "files",
                    canceled: false,
                    path_count: 2,
                  },
                };
              }
              return originalApiPost(url, body);
            };
            click("#rename-browse-files-button", "browse rename files");
            await new Promise((resolve) => setTimeout(resolve, 100));
            requireText("rename-file-source-summary", ["Windows file browser added 2 paths", "Source paths staged: 2", "C:/Browse/Selected Rename A.mkv"]);
            if (browsePosts.length !== 1 || browsePosts[0].body.selection_mode !== "files") {
              throw new Error("rename browse did not submit expected file-browser request: " + JSON.stringify(browsePosts));
            }
            window.apiPost = originalApiPost;
            click("#rename-clear-paths-button", "clear browsed rename paths");
            setValue("rename-add-path-input", "C:/Manual/Typed Rename Source.mkv");
            click("#rename-add-path-button", "add typed rename path");
            requireText("rename-file-source-summary", ["Manual path added 1 path", "Source paths staged: 1"]);
            click("#rename-clear-paths-button", "clear typed rename paths");
            requireText("rename-file-source-summary", ["Cleared staged rename paths.", "No source paths staged."]);
            setValue("rename-mode", "tv");
            setValue("rename-show", "Serial Experiments Lain");
            setValue("rename-season", "S02");
            setValue("rename-start", "E01");
            setValue("rename-paths", "C:/TV/Season 02/Serial Experiments Lain E01 Weird.mkv");
            setChecked("rename-sidecars", true);
            setChecked("rename-force-pipeline", false);
            setChecked("rename-pipeline-preview", true);

            const first = {
              source: "C:/TV/Season 02/Serial Experiments Lain E01 Weird.mkv",
              source_name: "Serial Experiments Lain E01 Weird.mkv",
              source_parent: "C:/TV/Season 02",
              destination: "C:/TV/Season 02/Serial Experiments Lain - S02E01 - Weird.mkv",
              destination_parent: "C:/TV/Season 02",
              target_name: "Serial Experiments Lain - S02E01 - Weird.mkv",
              pipeline_guess: "Serial Experiments Lain - S02E01 - Weird.mkv",
              status: "ready",
              confidence: "high",
              preview_source: "auto_tv_heuristic",
              confidence_reasons: ["folder season 02", "episode token E01"],
              change_kind: "rename",
              sidecar_count: 0,
              destination_exists: false,
              matches_target: false,
              warnings: [],
              errors: [],
            };
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [first], counts: { total: 1, ready: 1 }, confidence_counts: { high: 1 }, preview_source_counts: { auto_tv_heuristic: 1 }, change_kind_counts: { rename: 1 } });
            click('#rename-rows tr[data-selectable-row="true"]', "rename preview row");
            requireText("rename-detail", ["Serial Experiments Lain - S02E01 - Weird.mkv", "Confidence reason(s): folder season 02 | episode token E01"]);
            requireText("rename-apply-readiness-status", ["Ready"]);
            requireReadiness(["Apply scope", "all applicable preview rows", "Mutation boundary", "/api/rename/apply"]);
            requireText("rename-pipeline-handoff-status", ["Ready"]);
            requireText("rename-pipeline-handoff", ["Rename-to-pipeline handoff", "Saved routing profile: plex_direct_stream", "output container: mkv", "renaming changes filenames only"]);
            window.mediaPipelineRenameView.renderRenameApplyResult({
              command: "rename.apply",
              ok: true,
              message: "Applied selected rename.",
              data: {
                selected: 1,
                applied_count: 1,
                renamed: 1,
                unchanged: 0,
                sidecars: 1,
                media_operations: 1,
                sidecar_operations: 1,
                undo_manifest: "C:/State/Rename/undo.json",
                rename_progress: {
                  schema_version: "desktop_rename_apply_progress.v1",
                  status: "complete",
                  selected: 1,
                  renamed: 1,
                  unchanged: 0,
                  sidecars: 1,
                  media_operations: 1,
                  sidecar_operations: 1,
                  updated_at: "2026-05-17T12:00:00",
                  progress_bars: [{
                    id: "rename_apply",
                    label: "Rename apply",
                    mode: "determinate",
                    percent: 100,
                    status: "complete",
                    detail: "1 renamed / 1 planned; unchanged 0; media ops 1; sidecar ops 1; sidecars 1",
                    source: "rename.apply",
                    updated_at: "2026-05-17T12:00:00",
                    stale: false,
                  }],
                },
                rows: [{ source: first.source, destination: first.destination, status: "renamed", sidecar_count: 1 }],
              },
              request: { mode: "tv", confirm_apply: true, selected_sources: [first.source] },
            });
            requireText("rename-apply-outcome-status", ["Applied"]);
            requireText("rename-apply-outcome-summary", ["Backend rename apply outcome review", "selected=1", "Undo manifest: C:/State/Rename/undo.json", "read-only"]);
            requireText("rename-apply-progress-bars", ["Rename apply", "complete", "100%", "1 renamed / 1 planned", "source: rename.apply"]);
            for (const fragment of ["Backend result", "Selected scope", "Sidecar operations", "Undo / rollback evidence", "Mutation boundary"]) {
              if (!outcomeCells().includes(fragment)) throw new Error("outcome table missing " + fragment + "\\nActual:\\n" + outcomeCells());
            }
            const appliedOutcomeStatus = text("rename-apply-outcome-status");

            const posted = [];
            window.apiPost = async (url) => {
              posted.push(String(url || ""));
              return { ok: false, message: "browser smoke should not post rename apply" };
            };

            const largeRows = Array.from({ length: 260 }, (_value, index) => {
              const episode = String(index + 1).padStart(2, "0");
              return {
                ...first,
                source: \`C:/TV/S02/Serial Experiments Lain E\${episode}.mkv\`,
                source_name: \`Serial Experiments Lain E\${episode}.mkv\`,
                destination: \`C:/TV/S02/Serial Experiments Lain - S02E\${episode}.mkv\`,
                target_name: \`Serial Experiments Lain - S02E\${episode}.mkv\`,
                pipeline_guess: \`Serial Experiments Lain - S02E\${episode}.mkv\`,
              };
            });
            setValue("rename-paths", largeRows.map((row) => row.source).join("\\n"));
            window.mediaPipelineRenameView.renderRenamePreview({ rows: largeRows, counts: { total: 260, ready: 260 }, confidence_counts: { high: 260 }, preview_source_counts: { auto_tv_heuristic: 260 }, change_kind_counts: { rename: 260 } });
            requireText("rename-status", ["260 ready", "250 shown / 260 preview rows"]);
            requireText("rename-table-legend", ["Display cap: 250 shown / 260 preview rows rendered", "not visible in the table"]);
            click("#rename-check-applicable-button", "check all applicable large rename rows");
            requireText("rename-selected-count", ["260 checked"]);
            requireText("rename-selection-audit", ["Rows in scope: 260", "Rendered rows: 250 of 260", "checked scope may include rows not currently rendered"]);
            requireReadiness(["Render cap visibility", "250 of 260 preview row(s) are rendered", "unrendered backend preview rows"]);

            const duplicateA = { ...first, source: "C:/TV/S02/E01.mkv", source_name: "E01.mkv" };
            const duplicateB = { ...first, source: "C:/TV/S02/E02.mkv", source_name: "E02.mkv" };
            setValue("rename-paths", "C:/TV/S02/E01.mkv\\nC:/TV/S02/E02.mkv");
            window.mediaPipelineRenameView.renderRenamePreview({ rows: [duplicateA, duplicateB], counts: { total: 2, ready: 2 }, confidence_counts: { high: 2 }, preview_source_counts: { auto_tv_heuristic: 2 }, change_kind_counts: { rename: 2 } });
            click("#rename-check-applicable-button", "check applicable rename rows");
            requireText("rename-selected-count", ["2 checked"]);
            requireText("rename-apply-readiness-status", ["Blocked"]);
            requireReadiness(["Duplicate destinations", "duplicate target", "selected_sources"]);
            click("#rename-apply-button", "apply rename");
            await new Promise((resolve) => setTimeout(resolve, 100));
            requireText("rename-detail", ["blocked by apply readiness", "duplicate destination target"]);
            if (posted.some((url) => url.includes("rename") && url.includes("apply"))) {
              throw new Error("blocked duplicate-target scope still posted a rename apply request");
            }
            return {
              ok: true,
              readyStatus: "Ready",
              duplicateStatus: text("rename-apply-readiness-status"),
              appliedOutcomeStatus,
              outcomeStatus: text("rename-apply-outcome-status"),
              detail: text("rename-detail"),
              browsePosts,
              posted,
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
                expression: `Boolean(document.getElementById("rename-apply-readiness-rows") && typeof window.showPage === "function" && typeof window.mediaPipelineRenameView.renderRenamePreview === "function" && typeof window.mediaPipelineRenameView.applySelectedRename === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("rename-apply-readiness-rows") && typeof window.showPage === "function" && typeof window.mediaPipelineRenameView.renderRenamePreview === "function" && typeof window.mediaPipelineRenameView.applySelectedRename === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Rename WebView globals or readiness DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: browserRenameScript(),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              const exception = details.exception || {};
              throw new Error(exception.description || exception.value || details.text || "browser evaluation failed");
            }
            await sleep(750);
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


def _run_browser_rename_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView rename smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-rename-payload.json"
        runner_path = tmp / "browser-rename-runner.cjs"
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
        runner_path.write_text(_browser_rename_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView rename smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=45,
        )


class WebViewBrowserRenameSmokeTests(unittest.TestCase):
    def test_real_browser_renders_rename_readiness_and_blocks_duplicate_apply(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView rename smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-rename-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_rename_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertEqual(browser_result["duplicateStatus"], "Blocked")
        self.assertEqual(browser_result["browsePosts"][0]["body"]["selection_mode"], "files")
        self.assertEqual(browser_result["appliedOutcomeStatus"], "Applied")
        self.assertEqual(browser_result["outcomeStatus"], "Applied")
        self.assertIn("blocked by apply readiness", browser_result["detail"])
        self.assertEqual(browser_result["posted"], [])


if __name__ == "__main__":
    unittest.main()




