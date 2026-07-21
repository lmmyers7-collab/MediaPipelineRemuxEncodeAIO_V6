from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

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
        find_browser,
        free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )


def _runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function safeOperatorCommandsScript() {
          return `
          (async () => {
            const byId = (id) => document.getElementById(id);
            const text = (id) => byId(id)?.textContent || "";
            const posts = [];
            const confirmations = [];
            const activated = [];
            const mark = (label) => console.log("SAFE_OPERATOR_STAGE:" + label);
            const fixture = window.__MEDIA_PIPELINE_SAFE_OPERATOR_FIXTURE || {};

            async function waitFor(predicate, label, timeoutMs = 20000) {
              const deadline = Date.now() + timeoutMs;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (await predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              const bounded = (value) => String(value || "").slice(0, 1200);
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : "") + "\\n" + [
                "page=" + document.querySelector("[data-page-panel].is-visible")?.dataset?.pagePanel,
                "posts=" + JSON.stringify(posts.map((entry) => ({ path: entry.path, action: entry.body?.action || "" }))),
                "completedOpen=" + bounded(text("completed-open-status")),
                "pendingOpen=" + bounded(text("pending-open-status")),
                "queueOpen=" + bounded(text("queue-open-status")),
                "sample=" + bounded(text("sample-validation-result")).slice(0, 160),
                "metrics=" + bounded(text("metrics-backfill-detail")).slice(0, 160),
                "support=" + bounded(text("maintenance-support-result")).slice(0, 160),
                "releasePreview=" + bounded(text("release-dry-run-detail")).slice(0, 160),
                "releaseBuild=" + bounded(text("release-build-detail")).slice(0, 160),
                "backfill=" + bounded(text("backfill-dry-run-detail")).slice(0, 160),
                "atlas=" + bounded(text("dependency-atlas-detail")).slice(0, 160),
              ].join("\\n"));
            }

            function dispatchValue(element, value) {
              if (!element) throw new Error("missing value control");
              element.value = value;
              element.dispatchEvent(new Event("input", { bubbles: true }));
              element.dispatchEvent(new Event("change", { bubbles: true }));
            }

            function clickControl(control, label) {
              if (!control) throw new Error("missing control " + label);
              control.click();
              activated.push(label);
            }

            function postCount(path) {
              return posts.filter((entry) => entry.path === path).length;
            }

            await waitFor(
              () => window.performance?.getEntriesByName?.("mediapipeline-startup-critical-ready")?.length > 0
                && typeof window.showPage === "function"
                && typeof window.refreshAllNow === "function",
              "startup critical refresh",
            );

            const originalApiPost = window.mediaPipelineApi?.apiPost || window.apiPost;
            if (typeof originalApiPost !== "function") throw new Error("missing Local API POST client");
            const trackedApiPost = async (path, body, options) => {
              if (String(path || "") !== "/api/ui-preferences") {
                posts.push({ path: String(path || ""), body: body || {}, options: options || {} });
              }
              return originalApiPost(path, body, options);
            };
            window.apiPost = trackedApiPost;
            if (window.mediaPipelineApi) window.mediaPipelineApi.apiPost = trackedApiPost;
            window.confirm = (message) => {
              confirmations.push(String(message || ""));
              return true;
            };

            // Home: preview and append one evidence-only record through the visible controls.
            mark("home-start");
            window.showPage("home");
            await window.refreshAllNow({ page: "home", reason: "safe-operator-command-smoke" });
            await waitFor(
              () => text("sample-validation-summary").includes("Current sample:")
                && !text("sample-validation-summary").includes("Current sample: none loaded"),
              "Home sample selection",
            );
            dispatchValue(byId("sample-validation-decision"), "accepted");
            dispatchValue(byId("sample-validation-category"), "h264-remux-safe");
            dispatchValue(byId("sample-validation-notes"), "Disposable-root UI activation evidence.");
            document.querySelectorAll("[data-sample-validation-check]").forEach((input) => {
              if (!input.checked) input.click();
              activated.push(input.id);
            });
            clickControl(byId("sample-validation-preview-button"), "sample-validation-preview-button");
            await waitFor(
              () => postCount("/api/sample-validation/preview") === 1
                && !byId("sample-validation-preview-button")?.disabled
                && text("sample-validation-result").includes("Preview only"),
              "sample validation preview",
            );
            clickControl(byId("sample-validation-append-button"), "sample-validation-append-button");
            await waitFor(
              () => postCount("/api/sample-validation/append") === 1
                && !byId("sample-validation-append-button")?.disabled
                && text("sample-validation-result").includes("operator evidence"),
              "sample validation append",
            );
            mark("home-complete");

            // Metrics: activate every static control plus every dynamic source action.
            mark("metrics-start");
            window.showPage("metrics");
            await window.refreshAllNow({ page: "metrics", reason: "safe-operator-command-smoke" });
            await waitFor(
              () => document.querySelector('[data-page-panel="metrics"]')?.dataset?.availability === "available"
                && !byId("metrics-source-add-button")?.disabled,
              "Metrics availability",
            );
            const metricTiles = Array.from(document.querySelectorAll('[data-page-panel="metrics"] [data-ui-quick-link]'));
            if (metricTiles.length !== 6) throw new Error("expected 6 Metrics quick-link tiles, saw " + metricTiles.length);
            metricTiles.forEach((tile, index) => clickControl(tile, "metrics-quick-link-" + (index + 1)));
            const metricTabs = Array.from(document.querySelectorAll('[data-page-panel="metrics"] [data-metrics-tab]'));
            if (metricTabs.length !== 5) throw new Error("expected 5 Metrics tabs, saw " + metricTabs.length);
            metricTabs.forEach((tab) => clickControl(tab, "metrics-tab-" + tab.dataset.metricsTab));
            clickControl(byId("metrics-source-path-picker-badge"), "metrics-source-path-picker-badge");
            await waitFor(
              () => postCount("/api/path-picker/browse") === 1 && byId("metrics-source-path")?.value === fixture.metricsSource,
              "Metrics path picker",
            );
            dispatchValue(byId("metrics-source-label"), "Disposable Metrics Source");
            clickControl(byId("metrics-source-add-button"), "metrics-source-add-button");
            await waitFor(
              () => postCount("/api/metrics/sources") === 1
                && document.querySelector('[data-metrics-source-action="scan"]')
                && !document.querySelector('[data-metrics-source-action="scan"]')?.disabled
                && !byId("metrics-source-add-button")?.disabled,
              "Metrics source add",
            );
            clickControl(document.querySelector('[data-metrics-source-action="scan"]'), "metrics-source-scan");
            await waitFor(
              () => postCount("/api/metrics/backfill") === 1
                && !document.querySelector('[data-metrics-source-action="scan"]')?.disabled,
              "Metrics source scan",
            );
            clickControl(document.querySelector('[data-metrics-source-action="disable"]'), "metrics-source-disable");
            await waitFor(
              () => postCount("/api/metrics/sources") === 2
                && document.querySelector('[data-metrics-source-action="enable"]')
                && !document.querySelector('[data-metrics-source-action="enable"]')?.disabled,
              "Metrics source disable",
            );
            clickControl(document.querySelector('[data-metrics-source-action="enable"]'), "metrics-source-enable");
            await waitFor(
              () => postCount("/api/metrics/sources") === 3
                && document.querySelector('[data-metrics-source-action="disable"]')
                && !document.querySelector('[data-metrics-source-action="disable"]')?.disabled
                && !byId("metrics-backfill-button")?.disabled,
              "Metrics source enable",
            );
            clickControl(byId("metrics-backfill-button"), "metrics-backfill-button");
            await waitFor(
              () => postCount("/api/metrics/backfill") === 2 && !byId("metrics-backfill-button")?.disabled,
              "Metrics enabled-source backfill",
            );
            const attentionAction = document.querySelector("[data-metrics-attention-target]");
            if (!attentionAction) throw new Error("Metrics attention action was not rendered for the fixture backlog.");
            const attentionTarget = attentionAction.dataset.metricsAttentionTarget;
            clickControl(attentionAction, "metrics-attention-view-details");
            await waitFor(
              () => document.querySelector('[data-page-panel="metrics"] [data-metrics-tab="' + attentionTarget + '"]')?.getAttribute("aria-selected") === "true"
                && document.querySelector('[data-page-panel="metrics"] [data-metrics-tab-panel="' + attentionTarget + '"]')?.classList.contains("is-active"),
              "Metrics attention target",
            );
            clickControl(document.querySelector('[data-page-panel="metrics"] [data-cross-page-target="network"]'), "metrics-open-workers");
            await waitFor(() => document.querySelector('[data-page-panel="network"]')?.classList.contains("is-visible"), "Metrics worker handoff");
            window.showPage("metrics");
            clickControl(document.querySelector('[data-metrics-source-action="remove"]'), "metrics-source-remove");
            await waitFor(
              () => postCount("/api/metrics/sources") === 4
                && text("metrics-sources-rows").includes("No Metrics source roots configured"),
              "Metrics source removal",
            );
            mark("metrics-complete");

            // Maintenance: activate local fields and real backend-owned safe commands.
            mark("maintenance-start");
            window.showPage("maintenance");
            await window.refreshAllNow({ page: "maintenance", reason: "safe-operator-command-smoke" });
            await waitFor(() => byId("maintenance-support-create") && byId("release-dry-run-button"), "Maintenance controls");
            const maintenanceTiles = Array.from(document.querySelectorAll('[data-page-panel="maintenance"] [data-ui-quick-link]'));
            if (maintenanceTiles.length !== 4) throw new Error("expected 4 Maintenance quick-link tiles, saw " + maintenanceTiles.length);
            for (let index = 0; index < maintenanceTiles.length; index += 1) {
              clickControl(maintenanceTiles[index], "maintenance-quick-link-" + (index + 1));
              window.showPage("maintenance");
            }
            dispatchValue(byId("maintenance-support-reason"), "Disposable functional audit");
            dispatchValue(byId("maintenance-support-max-log-bytes"), "16384");
            clickControl(byId("maintenance-support-include-logs"), "maintenance-support-include-logs-off");
            clickControl(byId("maintenance-support-include-logs"), "maintenance-support-include-logs-on");
            clickControl(byId("maintenance-support-create"), "maintenance-support-create");
            await waitFor(
              () => postCount("/api/maintenance/support-export") === 1
                && text("maintenance-support-result").includes("Support export written")
                && text("maintenance-support-result").includes("Destination:"),
              "support export",
            );
            mark("support-complete");
            clickControl(byId("maintenance-refresh-button"), "maintenance-refresh-button");
            await waitFor(() => !byId("maintenance-refresh-button")?.disabled, "maintenance refresh");
            dispatchValue(byId("release-dry-run-destination"), fixture.deployRoot);
            const releaseOptionIds = [
              "release-dry-run-zip", "release-dry-run-verify", "release-dry-run-tests",
              "release-dry-run-dev-docs", "release-dry-run-optional-tools", "release-dry-run-tool-docs",
              "release-dry-run-tauri-binary", "release-dry-run-keep-config", "release-build-force",
            ];
            releaseOptionIds.forEach((id) => {
              const checkbox = byId(id);
              clickControl(checkbox, id + "-toggle-1");
              clickControl(checkbox, id + "-toggle-2");
            });
            if (byId("release-dry-run-keep-config")?.checked) byId("release-dry-run-keep-config").click();
            const releaseSummary = byId("release-options-summary") || document.querySelector('[data-page-panel="maintenance"] details summary');
            if (releaseSummary) {
              clickControl(releaseSummary, "maintenance-release-options-summary-open");
              clickControl(releaseSummary, "maintenance-release-options-summary-close");
            }
            clickControl(byId("release-dry-run-button"), "release-dry-run-button");
            await waitFor(
              () => postCount("/api/maintenance/release-dry-run") === 1
                && text("release-dry-run-status").includes("Complete")
                && !byId("release-dry-run-button")?.disabled,
              "deployment preview",
            );
            mark("release-preview-complete");
            clickControl(byId("release-build-button"), "release-build-button");
            await waitFor(
              () => postCount("/api/maintenance/release-build") === 1
                && text("release-build-status").includes("Complete")
                && !byId("release-build-button")?.disabled,
              "deployment build fixture",
            );
            mark("release-build-complete");
            clickControl(byId("backfill-dry-run-button"), "backfill-dry-run-button");
            await waitFor(
              () => postCount("/api/maintenance/completed-backfill-dry-run") === 1
                && text("backfill-dry-run-status").includes("Complete")
                && !byId("backfill-dry-run-button")?.disabled,
              "completed manifest backfill dry run",
            );
            mark("backfill-complete");
            clickControl(byId("dependency-atlas-button"), "dependency-atlas-button");
            await waitFor(
              () => postCount("/api/maintenance/dependency-atlas") === 1
                && text("dependency-atlas-status").includes("Complete")
                && !byId("dependency-atlas-button")?.disabled
                && !byId("dependency-atlas-open-folder-button")?.disabled,
              "dependency atlas update fixture",
            );
            mark("atlas-update-complete");
            clickControl(byId("dependency-atlas-open-folder-button"), "dependency-atlas-open-folder-button");
            await waitFor(
              () => postCount("/api/maintenance/dependency-atlas/open-folder") === 1
                && !byId("dependency-atlas-open-folder-button")?.disabled,
              "dependency atlas open fixture",
            );
            if (!text("dependency-atlas-status").includes("Opened")) {
              throw new Error("dependency atlas open did not succeed: " + text("dependency-atlas-status") + "\\n" + text("dependency-atlas-detail"));
            }
            mark("maintenance-complete");

            // Completed, Pending, and Queue: prove the shared generated row-open controls
            // reach their owning allowlisted routes. The fixture service records paths only.
            async function activateRowOpenActions(options) {
              window.showPage(options.page);
              await window.refreshAllNow({ page: options.page, reason: "safe-row-open-action-smoke" });
              await waitFor(
                () => document.querySelector(options.rowSelector)
                  && document.querySelectorAll(options.buttonSelector).length === options.expectedButtons,
                options.page + " row open controls",
              );
              if (options.unavailableRowSelector) {
                clickControl(document.querySelector(options.unavailableRowSelector), options.page + "-select-unavailable-row");
                await waitFor(
                  () => Array.from(document.querySelectorAll(options.buttonSelector)).every(
                    (button) => button.disabled && button.dataset.openTargetAvailable === "false"
                  ),
                  options.page + " unavailable row targets disabled",
                );
              }
              clickControl(document.querySelector(options.rowSelector), options.page + "-select-row");
              await waitFor(
                () => Array.from(document.querySelectorAll(options.buttonSelector)).every(
                  (button) => !button.disabled && button.dataset.openTargetAvailable === "true"
                ),
                options.page + " available row targets enabled",
              );
              const buttons = Array.from(document.querySelectorAll(options.buttonSelector));
              for (let index = 0; index < buttons.length; index += 1) {
                let observedClick = false;
                buttons[index].addEventListener("click", () => { observedClick = true; }, { once: true });
                clickControl(buttons[index], options.page + "-open-" + buttons[index].dataset.openTarget);
                if (!observedClick) throw new Error(options.page + " browser did not dispatch click for " + buttons[index].dataset.openTarget);
                await waitFor(
                  () => !buttons[index].disabled
                    && /^Opened\\b/i.test(text(options.statusId)),
                  options.page + " open " + buttons[index].dataset.openTarget,
                  3000,
                );
                if (/failed|select .* first/i.test(text(options.statusId))) {
                  throw new Error(options.page + " open action failed: " + text(options.statusId));
                }
              }
            }

            mark("row-open-actions-start");
            await activateRowOpenActions({
              page: "completed",
              unavailableRowSelector: "#completed-history-rows tr[data-row-key]:first-child",
              rowSelector: "#completed-history-rows tr[data-row-key]:last-child",
              buttonSelector: "[data-open-completed]",
              expectedButtons: 4,
              statusId: "completed-open-status",
            });
            await activateRowOpenActions({
              page: "pending",
              rowSelector: "#pending-rows tr[data-row-key]",
              buttonSelector: "[data-open-pending]",
              expectedButtons: 4,
              statusId: "pending-open-status",
            });
            await activateRowOpenActions({
              page: "queue",
              rowSelector: "#queue-rows tr[data-row-key]",
              buttonSelector: "[data-open-queue]",
              expectedButtons: 3,
              statusId: "queue-open-status",
            });
            mark("row-open-actions-complete");

            const requiredRoutes = {
              "/api/sample-validation/preview": 1,
              "/api/sample-validation/append": 1,
              "/api/path-picker/browse": 1,
              "/api/metrics/sources": 4,
              "/api/metrics/backfill": 2,
              "/api/maintenance/support-export": 1,
              "/api/maintenance/release-dry-run": 1,
              "/api/maintenance/release-build": 1,
              "/api/maintenance/completed-backfill-dry-run": 1,
              "/api/maintenance/dependency-atlas": 1,
              "/api/maintenance/dependency-atlas/open-folder": 1,
              "/api/queue/open": 3,
            };
            Object.entries(requiredRoutes).forEach(([path, expected]) => {
              if (postCount(path) !== expected) {
                throw new Error(path + " expected " + expected + " POST(s), saw " + postCount(path) + "\\n" + JSON.stringify(posts));
              }
            });
            const unexpected = posts.filter((entry) => !Object.prototype.hasOwnProperty.call(requiredRoutes, entry.path));
            if (unexpected.length) throw new Error("unexpected POST routes: " + JSON.stringify(unexpected));
            if (confirmations.length !== 2) throw new Error("expected sample append and deployment confirmations, saw " + JSON.stringify(confirmations));

            return {
              ok: true,
              posts,
              confirmations,
              activated,
              sampleResult: text("sample-validation-result"),
              metricsDetail: text("metrics-backfill-detail"),
              supportResult: text("maintenance-support-result"),
              releasePreview: text("release-dry-run-detail"),
              releaseBuild: text("release-build-detail"),
              backfillDetail: text("backfill-dry-run-detail"),
              atlasDetail: text("dependency-atlas-detail"),
            };
          })()
          `;
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new", "--disable-gpu", "--disable-background-networking", "--disable-default-apps",
            "--disable-extensions", "--disable-sync", "--metrics-recording-only", "--no-first-run",
            "--no-default-browser-check", `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`, payload.url,
          ]);
          let client = null;
          let progressTimer = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            let progressIndex = 0;
            progressTimer = setInterval(() => {
              while (progressIndex < client.consoleEvents.length) {
                const event = client.consoleEvents[progressIndex++];
                if (event.includes("SAFE_OPERATOR_STAGE:")) console.error(event);
              }
            }, 100);
            const readyDeadline = Date.now() + 20000;
            while (Date.now() < readyDeadline) {
              try {
                const ready = await client.send("Runtime.evaluate", {
                  expression: `Boolean(document.readyState === "complete" && document.getElementById("sample-validation-preview-button") && document.getElementById("metrics-source-add-button") && document.getElementById("maintenance-support-create") && typeof window.showPage === "function")`,
                  returnByValue: true,
                });
                if (ready.result?.value === true) break;
              } catch (error) {
                if (!String(error?.message || error).includes("Execution context was destroyed")) throw error;
              }
              await sleep(150);
            }
            await client.send("Runtime.evaluate", {
              expression: `window.__MEDIA_PIPELINE_SAFE_OPERATOR_FIXTURE = ${JSON.stringify({
                metricsSource: payload.metricsSource,
                deployRoot: payload.deployRoot,
              })}`,
              returnByValue: true,
            });
            const result = await client.send("Runtime.evaluate", {
              expression: safeOperatorCommandsScript(), awaitPromise: true, returnByValue: true,
            });
            clearInterval(progressTimer);
            progressTimer = null;
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            const ignoredConsoleFragments = ["favicon.ico"];
            const errors = client.consoleEvents.filter((entry) => entry.startsWith("error:") && !ignoredConsoleFragments.some((fragment) => entry.includes(fragment)));
            if (client.exceptions.length || errors.length) throw new Error(client.exceptions.concat(errors).join("; "));
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {} }));
          } finally {
            if (progressTimer) clearInterval(progressTimer);
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }
        main().catch((error) => { console.error(error.stack || error.message || String(error)); process.exit(1); });
        """
    )


class WebViewBrowserSafeOperatorCommandsSmoke(unittest.TestCase):
    def test_safe_operator_commands_execute_only_inside_disposable_roots(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the safe operator command browser smoke.")
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the safe operator command browser smoke.")

        with tempfile.TemporaryDirectory() as raw_root, tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
            root = Path(raw_root)
            tmp = Path(raw_tmp)
            resolved, source, output = _write_fixture_state(root)
            resolved.local_base = root
            resolved.state_root = root / "State"
            resolved.runtime_state_root = resolved.state_root
            resolved.run_logs_root = root / "RunLogs"
            resolved.app_state_path = root / "desktop_app_state.json"
            resolved.state_root.mkdir(parents=True, exist_ok=True)
            resolved.run_logs_root.mkdir(parents=True, exist_ok=True)

            canonical_completed_sidecar = output.with_suffix(".pipeline.json")
            canonical_completed_sidecar.write_text(
                output.with_name(output.name + ".pipeline.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            metrics_source = root / "Outsource"
            deploy_root = root / "DeployableUiFixture"
            atlas_root = root / "docs" / "generated" / "dependency-atlas"
            atlas_root.mkdir(parents=True, exist_ok=True)
            (atlas_root / "dependency-atlas.html").write_text("fixture atlas", encoding="utf-8")
            appdata_root = root / "Profile" / "MediaPipeline"
            temp_root = root / "Profile" / "Temp"
            temp_root.mkdir(parents=True, exist_ok=True)

            media_snapshots = [
                capture_media_no_mutation_snapshot(root / "TV"),
                capture_media_no_mutation_snapshot(root / "Outsource"),
                capture_media_no_mutation_snapshot(root / "PendingServerPush"),
            ]
            watched_state = {
                Path(resolved.queue_snapshot_path): Path(resolved.queue_snapshot_path).read_bytes(),
                Path(resolved.completed_manifest_path): Path(resolved.completed_manifest_path).read_bytes(),
            }
            service = DummyWorkflowFacadeService(root)
            service.open_path_with_default_app = service.open_path  # type: ignore[attr-defined]
            backfill_calls: list[dict[str, object]] = []

            def fake_backfill(resolved_arg: object, **kwargs: object) -> tuple[bool, str]:
                backfill_calls.append({"resolved": resolved_arg, **kwargs})
                return True, "\n".join(
                    [
                        "Backfill dry run complete.",
                        "  Sidecars ingested : 1",
                        "  Skipped (bad JSON): 0",
                        f"  Manifest          : {resolved.completed_manifest_path}",
                    ]
                )

            service.backfill_completed_manifest = fake_backfill  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-safe-operator-command-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                command_journal_path=resolved.state_root / "RunLogs" / "local_api_command_history.json",
            )
            server._path_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
                "ok": True,
                "canceled": False,
                "selection_mode": "folder",
                "paths": [str(metrics_source)],
                "message": "Disposable fixture folder selected.",
                "errors": [],
            }

            payload_path = tmp / "safe-operator-commands-payload.json"
            runner_path = tmp / "safe-operator-commands-runner.cjs"
            runner_path.write_text(_runner_source(), encoding="utf-8")

            isolated_environment = {
                "MEDIAPIPELINE_APPDATA_ROOT": str(appdata_root),
                "APPDATA": str(root / "Profile" / "Roaming"),
                "LOCALAPPDATA": str(root / "Profile" / "Local"),
                "TEMP": str(temp_root),
                "TMP": str(temp_root),
            }
            with patch.dict(os.environ, isolated_environment, clear=False):
                try:
                    server.start()
                    payload_path.write_text(
                        json.dumps(
                            {
                                "browserPath": browser_path,
                                "port": free_port(),
                                "tmpRoot": str(tmp),
                                "url": f"{server.url}/",
                                "metricsSource": str(metrics_source),
                                "deployRoot": str(deploy_root),
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    result = run_node_browser_smoke(
                        "Browser-backed safe operator command smoke",
                        node=node,
                        runner_path=runner_path,
                        payload_path=payload_path,
                        timeout_seconds=90,
                    )
                finally:
                    server.stop()

            for media_snapshot in media_snapshots:
                assert_media_no_mutation(self, media_snapshot)
            for path, expected in watched_state.items():
                self.assertEqual(path.read_bytes(), expected, f"Watched fixture state changed: {path}")
            self.assertEqual(source.read_bytes(), b"source-media")
            self.assertEqual(output.read_bytes(), b"output-media")

            browser_result = result["result"]
            self.assertTrue(result["ok"])
            self.assertGreaterEqual(len(browser_result["activated"]), 50)
            self.assertEqual(len(browser_result["confirmations"]), 2)
            self.assertIn("operator evidence", browser_result["sampleResult"])
            self.assertIn("Configured sources: 0", browser_result["metricsDetail"])
            self.assertIn("Support export written", browser_result["supportResult"])
            self.assertIn("Dry-run trust summary", browser_result["releasePreview"])
            self.assertIn("Deployment build summary", browser_result["releaseBuild"])
            self.assertIn("Dry-run trust summary", browser_result["backfillDetail"])
            self.assertIn("Dependency atlas", browser_result["atlasDetail"])

            validation_log = resolved.state_root / "Validation" / "sample_validation_log.jsonl"
            self.assertTrue(validation_log.exists())
            validation_lines = [line for line in validation_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(validation_lines), 1)
            self.assertEqual(json.loads(validation_lines[0])["operator_decision"], "accepted")

            metrics_root = resolved.state_root / "Metrics"
            registry = json.loads((metrics_root / "metrics_sources.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["roots"], [])
            self.assertTrue((metrics_root / "metrics_sidecar_backfill.jsonl").exists())
            self.assertTrue((metrics_root / "metrics_backfill_status.json").exists())

            exports = list((appdata_root / "DiagnosticsExports").glob("support_export_*.json"))
            self.assertEqual(len(exports), 1)
            self.assertTrue(str(exports[0].resolve()).casefold().startswith(str(root.resolve()).casefold()))
            self.assertEqual(len(service.release_build_calls), 2)
            self.assertTrue(service.release_build_calls[0]["dry_run"])
            self.assertFalse(service.release_build_calls[1]["dry_run"])
            self.assertEqual(Path(str(service.release_build_calls[0]["destination_root"])), deploy_root)
            self.assertEqual(Path(str(service.release_build_calls[1]["destination_root"])), deploy_root)
            self.assertFalse(deploy_root.exists())
            self.assertFalse(Path(str(deploy_root) + ".zip").exists())
            self.assertEqual(len(backfill_calls), 1)
            self.assertTrue(backfill_calls[0]["dry_run"])
            self.assertEqual(len(service.dependency_atlas_calls), 1)
            self.assertIn(atlas_root, service.opened_paths)
            self.assertEqual(len(service.opened_paths), 12)
            command_journal_path = resolved.state_root / "RunLogs" / "local_api_command_history.json"
            self.assertTrue(command_journal_path.exists())
            command_journal = json.loads(command_journal_path.read_text(encoding="utf-8"))
            command_names = [entry.get("command") for entry in command_journal.get("entries", [])]
            self.assertEqual(command_names.count("completed.open"), 4)
            self.assertEqual(command_names.count("pending_publish.open"), 4)
            self.assertEqual(command_names.count("queue.open"), 3)


if __name__ == "__main__":
    unittest.main()
