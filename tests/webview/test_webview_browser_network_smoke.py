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


def _browser_network_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function networkScript(data) {
          return `
          (async () => {
            const payload = ${JSON.stringify(data)};
            const posted = [];
            const opened = [];
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
            function setSelect(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing select " + id);
              node.value = value;
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function setInput(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing input " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
            }
            function setInputSelector(selector, value, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
            }
            function click(selector, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.click();
            }
            async function waitForText(id, fragments) {
              const deadline = Date.now() + 4000;
              while (Date.now() < deadline) {
                try {
                  requireText(id, fragments);
                  return;
                } catch (_error) {
                  await new Promise((resolve) => setTimeout(resolve, 80));
                }
              }
              requireText(id, fragments);
            }
            function requireVisible(id) {
              const node = byId(id);
              if (!node) throw new Error("missing visible node " + id);
              const style = window.getComputedStyle(node);
              if (style.display === "none" || style.visibility === "hidden") {
                throw new Error(id + " is not visible");
              }
            }
            function requireDialogOpen(id, fragments) {
              const node = byId(id);
              if (!node) throw new Error("missing dialog " + id);
              if (!node.open) throw new Error(id + " did not open");
              for (const fragment of fragments) {
                if (!node.textContent.includes(fragment)) throw new Error(id + " missing " + fragment);
              }
            }
            function requireTitle(id, fragments) {
              const node = byId(id);
              if (!node) throw new Error("missing titled node " + id);
              const actual = node.getAttribute("title") || "";
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " title missing " + fragment + "\\nActual:\\n" + actual);
              }
              const describedBy = String(node.getAttribute("aria-describedby") || "");
              if (!describedBy.trim()) throw new Error(id + " missing aria-describedby for setting tip");
            }
            function settingsPatch() {
              const raw = byId("settings-patch-json")?.value || "{}";
              try {
                return JSON.parse(raw);
              } catch (error) {
                throw new Error("settings patch JSON did not parse: " + error.message + "\\n" + raw);
              }
            }
            [
              "showPage",
            ].forEach(requireFunction);
            [
              "renderNetworkView",
              "renderNetworkLifecycleHandoff",
              "renderNetworkRerunRows",
              "networkLifecycleRows",
              "renderNetworkStateFiles",
              "initNetworkViewEvents",
              "renderNetworkAttentionStack",
              "renderNetworkTopologyStrip",
              "renderNetworkActionReadinessGates",
            ].forEach((name) => {
              if (typeof window.mediaPipelineNetworkView?.[name] !== "function") {
                throw new Error("missing mediaPipelineNetworkView." + name + " function");
              }
            });
            if (typeof window.mediaPipelineSettingsView?.syncNetworkSettingsBuilderFromConfig !== "function") {
              throw new Error("missing network settings builder sync function");
            }
            if (typeof window.mediaPipelineNetworkView?.syncNetworkRoleDashboards !== "function") {
              throw new Error("missing network role dashboard sync function");
            }
            if (typeof window.mediaPipelineNetworkView?.networkCoordinatorOverviewModel !== "function") {
              throw new Error("missing coordinator overview model function");
            }
            if (typeof window.mediaPipelineNetworkView?.networkWorkerOverviewModel !== "function") {
              throw new Error("missing worker overview model function");
            }
            if (typeof window.mediaPipelineNetworkView?.networkWorkerTestConnectionRoute !== "function") {
              throw new Error("missing worker test-connection route function");
            }
            if (typeof window.mediaPipelineNetworkView?.networkCoordinatorJoinBlobRoute !== "function") {
              throw new Error("missing coordinator join blob route function");
            }
            if (typeof window.mediaPipelineNetworkView?.networkWorkerJoinClusterRoute !== "function") {
              throw new Error("missing worker join cluster route function");
            }
            if (typeof window.mediaPipelineNetworkView?.networkWorkerDiscoverCoordinatorsRoute !== "function") {
              throw new Error("missing worker coordinator discovery route function");
            }
            if (typeof window.mediaPipelineNetworkView?.networkLifecycleDryRunAllowsConfirmed !== "function") {
              throw new Error("missing lifecycle dry-run freshness helper");
            }
            if (typeof window.mediaPipelineNetworkView?.networkLifecycleRelevantRoles !== "function") {
              throw new Error("missing lifecycle role-group helper");
            }
            if (typeof window.mediaPipelineNetworkView?.renderNetworkDiagnosticRail !== "function") {
              throw new Error("missing diagnostic rail renderer");
            }
            if (typeof window.mediaPipelineNetworkView?.networkWorkerStatusState !== "function") {
              throw new Error("missing worker status taxonomy helper");
            }
            const preservedStopLines = window.mediaPipelineNetworkView.networkLifecycleCommandResultLines({
              ok: true,
              command: "network.worker.stop",
              severity: "warning",
              message: "Network worker stop requested; active work is preserved for done reporting.",
              data: {
                dry_run_only: false,
                active_work_preserved: true,
                state_after: { status: "active_work_preserved" },
                post_action_active_work: {
                  active_job_count: 1,
                  local_active_job_count: 1,
                  remote_active_claim_count: 0,
                  active_jobs: [{ job_id: "job-1", source_name: "Movie.mkv", source: "provider_app" }],
                },
              },
            }).join("\\n");
            if (!preservedStopLines.includes("Active work preserved:") || !preservedStopLines.includes("stopped polling/new claims")) {
              throw new Error("active-work-preserved lifecycle result did not render backend evidence:\\n" + preservedStopLines);
            }
            if (typeof window.mediaPipelineNetworkView?.createNetworkJoinBlob !== "function") {
              throw new Error("missing create join blob function");
            }
            if (typeof window.mediaPipelineNetworkView?.importNetworkJoinBlob !== "function") {
              throw new Error("missing import join blob function");
            }
            if (typeof window.mediaPipelineNetworkView?.discoverNetworkCoordinators !== "function") {
              throw new Error("missing discover coordinators function");
            }

            window.apiPost = async (url, body) => {
              posted.push({ url: String(url || ""), body });
              if (String(url || "").includes("/api/network/coordinator/start-dry-run") || String(url || "").includes("/api/network/coordinator/stop-dry-run")) {
                const dryRunAction = String(url || "").includes("/stop-dry-run") ? "stop" : "start";
                return {
                  ok: true,
                  command: "network.coordinator." + dryRunAction + ".dry_run",
                  severity: "info",
                  message: "mocked coordinator " + dryRunAction + " dry-run",
                  data: {
                    schema_version: "desktop_network_lifecycle_command_result.v1",
                    dry_run_only: true,
                    effect: "none",
                    safe_to_apply: true,
                    state_before: { status: dryRunAction === "stop" ? "running" : "stopped" },
                    state_after: { status: dryRunAction === "stop" ? "would_stop" : "would_start" },
                    precondition_results: [{ key: "provider_ready", status: "pass", evidence: "mock provider ready" }],
                    would_not_touch: {
                      media_sources: "no write/delete/rename/move",
                      queue_state: "no claim, enqueue, dequeue, reorder, or launch",
                    },
                  },
                };
              }
              if (String(url || "").includes("/api/network/worker/test-connection")) {
                return {
                  ok: true,
                  command: "network.worker.test_connection",
                  severity: "info",
                  message: "mocked worker test connection",
                  data: {
                    schema_version: "desktop_network_worker_test_connection.v1",
                    effect: "none",
                    layers: {
                      l1_url: { ok: true, status: "pass", detail: "mocked url layer" },
                      l2_auth: { ok: true, status: "pass", detail: "mocked auth layer" },
                      l3_paths: { ok: true, status: "pass", detail: "mocked path layer", paths: [] },
                    },
                    would_not_touch: {
                      media_sources: true,
                      queue: true,
                      output: true,
                    },
                  },
                };
              }
              if (String(url || "").includes("/api/network/worker/discover-coordinators")) {
                return {
                  ok: true,
                  command: "network.worker.discover_coordinators",
                  severity: "info",
                  message: "mocked coordinator discovery",
                  data: {
                    schema_version: "desktop_network_coordinator_discovery.v1",
                    effect: "none",
                    suppress_command_journal: true,
                    zeroconf_available: true,
                    count: 1,
                    coordinators: [
                      {
                        url: "http://discovered.test:7830",
                        host: "discovered.test",
                        port: 7830,
                        source: "mdns",
                        selectable: true,
                      },
                    ],
                    would_not_touch: {
                      source_media: "no write/delete/rename/move",
                      queue_state: "no claim, enqueue, dequeue, reorder, or launch",
                    },
                  },
                };
              }
              if (String(url || "").includes("/api/network/coordinator/join-blob")) {
                return {
                  ok: true,
                  command: "network.coordinator.join_blob",
                  severity: "info",
                  message: "mocked coordinator join blob",
                  data: {
                    schema_version: "desktop_network_join_blob_result.v1",
                    join_blob: "mediapipeline-join:browser-smoke",
                    coordinator_url: "http://coordinator.test:7830",
                    token_fingerprint: "sha256:browser-smoke",
                    token_source: "app_state",
                    library_count: 2,
                  },
                };
              }
              if (String(url || "").includes("/api/network/worker/join-cluster")) {
                return {
                  ok: true,
                  command: "network.worker.join_cluster",
                  severity: "info",
                  message: "mocked worker join import",
                  data: {
                    schema_version: "desktop_network_join_import_result.v1",
                    coordinator_url: "http://coordinator.test:7830",
                    token_fingerprint: "sha256:browser-smoke",
                    library_count: 2,
                    settings_save: { status: "saved", ok: true, changed_keys: ["NetworkRole", "WorkerCoordinatorUrl"] },
                    join_plan: { library_count: 2, auto_path_map_entries: 1, effective_path_map_entries: 1 },
                    test_connection: {
                      ok: true,
                      command: "network.worker.test_connection",
                      severity: "info",
                      message: "mocked worker test connection",
                      data: {
                        layers: {
                          l1_url: { ok: true, status: "pass", detail: "mocked url layer" },
                          l2_auth: { ok: true, status: "pass", detail: "mocked auth layer" },
                          l3_paths: { ok: true, status: "pass", detail: "mocked path layer", paths: [] },
                        },
                        would_not_touch: {
                          media_sources: true,
                          queue: true,
                          output: true,
                        },
                      },
                    },
                  },
                };
              }
              return { ok: true, command: "diagnostics.open", message: "browser smoke mocked diagnostics open", data: { target: body?.target || "" } };
            };
            try { refreshAll = () => {}; } catch (_error) {}
            window.refreshAll = () => {};
            window.open = (url) => {
              opened.push(String(url || ""));
              return null;
            };

            window.showPage("network");
            if (typeof window.applyEvidenceHiddenPreference === "function") {
              window.applyEvidenceHiddenPreference(false);
            }
            window.mediaPipelineNetworkView.renderNetworkView(payload);
            window.mediaPipelineSettingsView.syncNetworkSettingsBuilderFromConfig();
            if (document.querySelector("[data-network-tab]")) {
              throw new Error("Network role tabs should not render.");
            }
            const coordinatorPanel = document.querySelector('[data-network-role-panel="coordinator"]');
            const workerPanel = document.querySelector('[data-network-role-panel="worker"]');
            if (!coordinatorPanel || !coordinatorPanel.classList.contains("is-active") || coordinatorPanel.hidden) {
              throw new Error("Coordinator dashboard should be visible for coordinator mode.");
            }
            if (!workerPanel || workerPanel.classList.contains("is-active") || !workerPanel.hidden) {
              throw new Error("Worker dashboard should be hidden for coordinator mode.");
            }
            requireTitle("settings-network-role", ["Standalone", "Coordinator", "Worker", "Coordinator + local worker"]);
            requireText("network-status", ["Backend lifecycle controls"]);
            requireText("network-status-banner-title", ["Coordinator only", "Running settings drift"]);
            requireText("network-status-banner-detail", ["Normal Launch blocked", "Running worker differs from saved"]);
            requireText("network-status-banner-lines", ["Mode: Coordinator only.", "Runtime: Blocked", "Worker-facing coordinator URL", "Restart note", "Worker settings drift"]);
            requireText("network-health-strip", ["Role", "Runtime", "Coordinator", "Drift", "Workers", "Alerts"]);
            requireText("network-health-workers", ["1 active / 1 idle"]);
            requireText("network-health-alerts", ["review"]);
            requireText("network-attention-stack", ["Pending done report", "worker-failed: blocked", "Worker settings drift"]);
            requireText("network-topology-strip", ["Coordinator", "http://coordinator.test:7830", "worker-active", "Episode 01.mkv"]);
            requireText("network-diagnostic-rail", ["TCP: ready", "Auth: review", "Paths: ready", "Queue: ready", "Claim: review", "State files: review"]);
            requireText("network-action-readiness-gates", ["TCP: ready", "Auth: review", "Paths: ready", "State: review", "Queue: ready", "Close: ready", "Dry-run: review"]);
            const coordinatorActionGroup = document.querySelector('[data-network-action-group="coordinator"]');
            const workerActionGroup = document.querySelector('[data-network-action-group="worker"]');
            const standaloneActionGroup = document.querySelector('[data-network-action-group="standalone"]');
            if (!coordinatorActionGroup || coordinatorActionGroup.hidden) throw new Error("coordinator quick actions should be visible");
            if (!workerActionGroup || !workerActionGroup.hidden) throw new Error("worker quick actions should be hidden in coordinator-only mode");
            if (!standaloneActionGroup || !standaloneActionGroup.hidden) throw new Error("standalone quick actions should be hidden in coordinator mode");
            requireText("network-lifecycle-control-buttons", ["Check & Start Coordinator", "Request Coordinator Stop", "Open Cluster Log", "Configure"]);
            requireText("network-coordinator-overview-status", ["Blocked review"]);
            requireText("network-coordinator-overview-summary", ["Coordinator overview:", "Queue on deck:", "Mutation guardrail"]);
            requireText("network-coordinator-active-rows", ["worker-active", "Episode 01.mkv", "Encode", "encoding", "42%"]);
            if (text("network-coordinator-active-rows").includes("worker-failed")) {
              throw new Error("historical failure row should not render as active claimed work");
            }
            requireText("network-coordinator-queue-rows", ["Episode 03.mkv", "Remux", "normal", "copy_compatible"]);
            requireText("network-mode-model", ["Standalone:", "Coordinator only:", "Worker only:", "Coordinator + local worker:", "Runtime authority:"]);
            const summaryRows = Array.from(document.querySelectorAll("#network-summary .network-summary-row"));
            if (summaryRows.length < 3) throw new Error("expected readable network summary rows, saw " + summaryRows.length);
            if (!summaryRows[0].querySelector(".network-summary-row-label") || !summaryRows[0].querySelector(".network-summary-row-value")) {
              throw new Error("expected saved-role summary row to expose label and value spans");
            }
            const modeRows = Array.from(document.querySelectorAll("#network-mode-model .network-summary-row"));
            if (modeRows.length < 5) throw new Error("expected readable network mode model rows, saw " + modeRows.length);
            requireText("network-readiness-summary", [
              "Lifecycle owner: backend Network diagnostics / Python dispatcher.",
              "backend-owned lifecycle controls available",
              "Restart note:",
              "Coordinator token:",
              "Worker token:",
            ]);
            requireText("network-lifecycle-boundary-summary", [
              "Lifecycle owner: backend Network diagnostics / Python dispatcher.",
              "Lifecycle dry-run routes: present (4); confirmed lifecycle routes: present (4).",
              "Setup write/secret routes:",
              "run the backend dry-run route before any confirmed network lifecycle command",
            ]);
            requireText("network-route-summary", [
              "GET /api/network/workers available with effect=none",
              "Worker test-connection route: available with effect=none",
              "Worker mDNS discovery route: available with effect=none",
              "Coordinator join blob route: available; setup secret-transfer",
              "Worker join cluster route: available; setup config-write",
              "Lifecycle dry-run routes: 4; confirmed lifecycle start/stop routes: 4.",
              "Setup write/secret routes:",
              "published lifecycle contracts",
              "mutation enabled=yes",
              "Deep API contract detail remains in Advanced",
            ]);
            requireText("network-lifecycle-summary", [
              "Network lifecycle handoff:",
              "Decision rule: trust only backend-owned Network evidence and lifecycle routes",
              "Mutation guardrail",
            ]);
            requireText("network-evidence-summary", ["Network evidence checklist:", "persisted worker state is visible through /api/network/workers"]);
            requireText("network-state-files-summary", ["Network runtime state file evidence:", "Files: 3; present=2; missing=1; unreadable=0", "Read order: Cluster log -> Coordinator in-flight registry -> Local worker state"]);
            requireText("network-worker-summary", ["Persisted worker state: loaded", "State source: runtime_state_files", "Lifecycle controls remain backend-owned", "Warning(s):", "coordinator persisted state may be stale"]);
            const workerSummaryRows = Array.from(document.querySelectorAll("#network-worker-summary .network-summary-row"));
            if (workerSummaryRows.length < 8) throw new Error("expected readable worker state rows, saw " + workerSummaryRows.length);
            if (!workerSummaryRows[0].querySelector(".network-summary-row-label") || !workerSummaryRows[0].querySelector(".network-summary-row-value")) {
              throw new Error("expected persisted worker summary row to expose label and value spans");
            }
            requireText("network-worker-progress-summary", ["Last reported worker progress:", "Active worker bars:", "Mutation guardrail: this panel uses backend-owned Network lifecycle routes only"]);
            requireText("network-worker-progress-bars", ["worker-active", "42%", "worker-failed"]);
            requireText("network-worker-filter-summary", ["Showing 3/3", "No active/problem/review rows hidden", "Filters are visual only"]);
            requireText("network-worker-view-presets", ["All", "Needs Attention", "Active", "Idle", "Stale", "Path/Auth"]);
            click('[data-network-worker-view="stale"]', "stale worker board preset");
            requireText("network-worker-filter-summary", ["Showing 1/3", "Filter: view=Stale/Failed", "1 active/problem/review hidden"]);
            click('[data-network-worker-view=""]', "all worker board preset");
            requireText("network-worker-filter-summary", ["Showing 3/3", "Filter: none"]);

            const lifecycleRows = Array.from(document.querySelectorAll('#network-lifecycle-rows tr[data-selectable-row="true"]'));
            if (lifecycleRows.length < 6) throw new Error("expected network lifecycle handoff rows, saw " + lifecycleRows.length);
            const claimHealthRow = lifecycleRows.find((row) => (row.textContent || "").includes("Claim and worker health"));
            if (!claimHealthRow) throw new Error("missing claim health lifecycle row");
            claimHealthRow.click();
            requireText("network-lifecycle-detail", [
              "Gate: Claim and worker health",
              "Failed/stale/offline rows: 1",
              "Pending done report",
              "Mutation guardrail",
            ]);

            click('#network-state-files-rows tr[data-selectable-row="true"]', "network state file row");
            requireText("network-state-files-detail", ["File:", "Status:", "Safe next step:", "Mutation guardrail"]);

            click('#network-worker-rows tr[data-selectable-row="true"]', "network worker row");
            requireText("network-worker-detail", ["Worker", "Current file", "Stage", "Progress", "Evidence links", "Lifecycle controls remain backend-owned"]);

            setSelect("network-worker-status-filter", "idle");
            requireText("network-worker-filter-summary", ["Showing 1/3", "2 active/problem/review hidden", "clear filters before lifecycle decisions"]);

            setSelect("network-worker-status-filter", "");
            setInput("network-worker-filter", "failed-job");
            requireText("network-worker-filter-summary", ["Showing 1/3", "1 active/problem/review hidden", "Filters are visual only"]);
            requireText("network-worker-detail", ["failed-job", "SOURCE_NOT_FOUND", "Last failure reason", "Evidence links"]);

            setInput("network-worker-filter", "no-match-filter");
            requireText("network-worker-filter-summary", ["Showing 0/3", "2 active/problem/review hidden"]);
            requireText("network-worker-detail", ["No network worker row selected."]);
            const preJoinSmokeResult = {
              filterSummary: text("network-worker-filter-summary"),
              lifecycleStatus: text("network-lifecycle-status"),
              lifecycleSummary: text("network-lifecycle-summary"),
              evidenceStatus: text("network-evidence-status"),
              stateFilesStatus: text("network-state-files-status"),
              stateFilesSummary: text("network-state-files-summary"),
              workerStatus: text("network-worker-status"),
            };

            const safeLifecyclePayload = JSON.parse(JSON.stringify(payload));
            safeLifecyclePayload.settings.config.NetworkRole = "coordinator";
            safeLifecyclePayload.settings.config.CoordinatorAlsoEncodeLocally = false;
            safeLifecyclePayload.networkWorkers.runtime_status_label = "Running";
            safeLifecyclePayload.networkWorkers.runtime_status_severity = "match";
            safeLifecyclePayload.networkWorkers.lifecycle_state.coordinator.status = "running";
            safeLifecyclePayload.networkWorkers.operator_summary_lines = [
              "Mode: Coordinator only.",
              "Runtime: Running (match).",
              "Normal Launch: blocked in this network mode; use Network Lifecycle controls.",
              "Lifecycle state: coordinator running.",
              "Worker-facing coordinator URL: http://coordinator.test:7830.",
            ];
            await new Promise((resolve) => setTimeout(resolve, 500));
            window.mediaPipelineNetworkView.renderNetworkView(safeLifecyclePayload);
            const coordinatorStopButton = document.querySelector('[data-network-lifecycle-role="coordinator"][data-network-lifecycle-action="stop"][data-network-lifecycle-guided="true"]');
            if (!coordinatorStopButton || coordinatorStopButton.disabled) {
              throw new Error("guided coordinator stop should be enabled in safe running state: " + (coordinatorStopButton?.title || "missing"));
            }
            const beforeGuidedPosts = posted.length;
            click('[data-network-lifecycle-role="coordinator"][data-network-lifecycle-action="stop"][data-network-lifecycle-guided="true"]', "guided coordinator stop");
            await waitForText("network-lifecycle-command-result", ["Check complete. This was a dry-run only.", "Effect: none.", "Safe to apply: yes"]);
            requireText("network-action-readiness-gates", ["Dry-run: ready"]);
            requireDialogOpen("network-lifecycle-confirm-dialog", ["coordinator stop", "Matching dry-run accepted", "backend confirmation field"]);
            const guidedPosts = posted.slice(beforeGuidedPosts).filter((entry) => String(entry.url).includes("/api/network/coordinator/"));
            if (guidedPosts.length !== 1 || !String(guidedPosts[0].url).endsWith("/api/network/coordinator/stop-dry-run")) {
              throw new Error("guided coordinator stop should post exactly one dry-run before confirmation: " + JSON.stringify(guidedPosts));
            }
            click("#network-lifecycle-confirm-cancel", "cancel lifecycle confirmation");
            await waitForText("network-lifecycle-command-result", ["Guided lifecycle command stopped after dry-run"]);
            if (posted.some((entry) => String(entry.url).endsWith("/api/network/coordinator/stop"))) {
              throw new Error("cancelled confirmed lifecycle command still posted: " + JSON.stringify(posted));
            }
            const staleLifecyclePayload = JSON.parse(JSON.stringify(safeLifecyclePayload));
            staleLifecyclePayload.networkWorkers.lifecycle_state.coordinator.status = "stopped";
            window.mediaPipelineNetworkView.renderNetworkView(staleLifecyclePayload);
            if (!coordinatorStopButton.disabled) {
              throw new Error("confirmed coordinator stop should be disabled after lifecycle-state mismatch");
            }

            const coordinatorLocalPayload = JSON.parse(JSON.stringify(payload));
            coordinatorLocalPayload.settings.config.NetworkRole = "coordinator";
            coordinatorLocalPayload.settings.config.CoordinatorAlsoEncodeLocally = true;
            window.mediaPipelineNetworkView.renderNetworkView(coordinatorLocalPayload);
            if (coordinatorPanel.hidden || workerPanel.hidden) {
              throw new Error("Coordinator + local worker mode should show both role dashboards.");
            }
            if (coordinatorActionGroup.hidden || workerActionGroup.hidden || !standaloneActionGroup.hidden) {
              throw new Error("Coordinator + local worker mode should show coordinator and local worker quick actions only.");
            }

            const workerModePayload = JSON.parse(JSON.stringify(payload));
            workerModePayload.settings.config.NetworkRole = "worker";
            workerModePayload.settings.config.WorkerCoordinatorUrl = "http://coordinator.test:7830";
            workerModePayload.networkWorkers.role = "worker";
            workerModePayload.networkWorkers.runtime_status_label = "Worker ready";
            workerModePayload.networkWorkers.runtime_status_severity = "match";
            workerModePayload.networkWorkers.lifecycle_state.worker.status = "stopped";
            workerModePayload.networkWorkers.operator_summary_lines = [
              "Mode: Worker only.",
              "Runtime: Worker ready (match).",
              "Lifecycle state: worker stopped.",
              "Worker-facing coordinator URL: http://coordinator.test:7830.",
            ];
            window.mediaPipelineNetworkView.renderNetworkView(workerModePayload);
            if (coordinatorPanel.classList.contains("is-active") || !coordinatorPanel.hidden) {
              throw new Error("Coordinator dashboard should be hidden for worker mode.");
            }
            if (!workerPanel.classList.contains("is-active") || workerPanel.hidden) {
              throw new Error("Worker dashboard should be visible for worker mode.");
            }
            requireText("network-worker-overview-status", ["Pending done report"]);
            requireText("network-worker-overview-summary", ["Worker overview:", "Remote coordinator queue: Phase 2", "Mutation guardrail"]);
            requireText("network-worker-claim-rows", ["local-job", "Episode 04.mkv", "Encode", "worker current local claim", "Pending done report", "yes"]);
            requireText("network-worker-remote-queue-summary", ["Phase 2 placeholder:", "read-only coordinator queue reporting contract"]);
            if (!coordinatorActionGroup.hidden || workerActionGroup.hidden || !standaloneActionGroup.hidden) {
              throw new Error("Worker mode should show only worker quick actions.");
            }
            click("[data-network-test-connection]", "worker test connection button");
            await waitForText("network-lifecycle-command-result", [
              "Worker test-connection complete.",
              "Effect: none.",
              "No files, queue, scratch, output, pending publish, lifecycle state, or media policy changed.",
            ]);
            const standalonePayload = JSON.parse(JSON.stringify(payload));
            standalonePayload.settings.config.NetworkRole = "standalone";
            standalonePayload.settings.config.CoordinatorAlsoEncodeLocally = false;
            window.mediaPipelineNetworkView.renderNetworkView(standalonePayload);
            if (!coordinatorPanel.hidden || !workerPanel.hidden) {
              throw new Error("Standalone mode should not show coordinator or worker role dashboards.");
            }
            if (!coordinatorActionGroup.hidden || !workerActionGroup.hidden || standaloneActionGroup.hidden) {
              throw new Error("Standalone mode should show only standalone quick actions.");
            }
            requireText("network-summary", ["Standalone mode keeps all processing local to this workstation."]);
            click('[data-network-open-drawer="network-settings-drawer"]', "standalone configure drawer");
            if (!byId("network-settings-drawer").open) throw new Error("Configure Distributed Mode should open Settings drawer");
            const missingJoinRoutePayload = JSON.parse(JSON.stringify(payload));
            missingJoinRoutePayload.contract.routes = missingJoinRoutePayload.contract.routes.filter((route) => route.path !== "/api/network/coordinator/join-blob");
            window.mediaPipelineNetworkView.renderNetworkView(missingJoinRoutePayload);
            requireText("network-coordinator-join-status", ["Route missing"]);
            window.mediaPipelineNetworkView.renderNetworkView(payload);

            setSelect("settings-network-role", "worker");
            requireDialogOpen("network-role-setup-dialog", ["Worker Setup", "Designation", "Worker", "Distributed setup stages saved config only"]);
            requireTitle("network-role-setup-worker-url", ["http://<coordinator-ip>:7830"]);
            requireTitle("network-role-setup-worker-name", ["Windows computer name", "BEAST-PC"]);
            requireTitle("network-role-setup-worker-poll", ["10 to 15 seconds"]);
            requireTitle("network-role-setup-path-map", ["{} when paths match"]);
            requireTitle("network-role-setup-worker-overrides", ["{} unless a specific worker needs tuning"]);
            const actionStyle = window.getComputedStyle(byId("network-role-setup-stage-button").parentElement);
            if (actionStyle.position !== "sticky") throw new Error("role setup action row is not sticky: " + actionStyle.position);
            setInput("network-role-setup-worker-url", "http://0.0.0.0:7830");
            click("#network-role-setup-stage-button", "worker setup invalid stage button");
            requireText("network-role-setup-worker-url-error", ["0.0.0.0", "listen addresses"]);
            requireText("settings-patch-detail", ["0.0.0.0", "worker targets"]);
            setInput("network-role-setup-worker-url", "http://10.0.0.20:7830");
            if (text("network-role-setup-worker-url-error").trim()) {
              throw new Error("valid worker URL still shows an inline error: " + text("network-role-setup-worker-url-error"));
            }
            setInput("network-role-setup-worker-name", "browser-worker");
            setInput("network-role-setup-worker-poll", "15");
            const pathMapRow = "#network-role-setup-path-map-rows tr[data-path-map-row]";
            setInputSelector(pathMapRow + ' [data-path-map-field="from"]', "D:/Source", "path map from");
            setInputSelector(pathMapRow + ' [data-path-map-field="to"]', "//SERVER/Source", "path map to");
            setInputSelector(pathMapRow + ' [data-path-map-field="sample"]', "D:/Source/Episode 01.mkv", "path map sample");
            const originalWorkerTestConnection = window.mediaPipelineNetworkView.runNetworkWorkerTestConnection;
            window.mediaPipelineNetworkView.runNetworkWorkerTestConnection = async () => ({
              ok: true,
              command: "network.worker.test_connection",
              severity: "info",
              message: "mocked worker preflight",
              data: {
                layers: {
                  l3_paths: { ok: true, status: "pass", detail: "mocked path layer" },
                },
              },
            });
            click(pathMapRow + ' [data-path-map-action="test"]', "path map row test button");
            await waitForText("network-role-setup-path-map-test-result", [
              "Local staged rewrite result: //SERVER/Source/Episode 01.mkv",
              "Backend saved-config preflight: path layer reported pass",
            ]);
            window.mediaPipelineNetworkView.runNetworkWorkerTestConnection = originalWorkerTestConnection;
            setInput("network-role-setup-worker-overrides", '{"browser-worker":{"VideoPreset":"p4"}}');
            click("#network-role-setup-stage-button", "worker setup stage button");
            const workerPatch = settingsPatch();
            if (workerPatch.NetworkRole !== "worker") {
              throw new Error("worker setup did not stage NetworkRole=worker: " + JSON.stringify(workerPatch) + "\\nStatus: " + text("settings-patch-status") + "\\nDetail: " + text("settings-patch-detail"));
            }
            if (workerPatch.WorkerCoordinatorUrl !== "http://10.0.0.20:7830") throw new Error("worker coordinator URL not staged");
            if (workerPatch.WorkerName !== "browser-worker") throw new Error("worker name not staged");
            const pathMap = JSON.parse(workerPatch.WorkerSourcePathMap || "{}");
            if (pathMap["D:/Source"] !== "//SERVER/Source") {
              throw new Error("worker source path map row did not serialize: " + JSON.stringify(workerPatch));
            }
            click("#network-role-setup-close-button", "worker setup close button");

            setSelect("settings-network-role", "coordinator");
            requireDialogOpen("network-role-setup-dialog", ["Coordinator Setup", "Designation", "Coordinator", "Distributed setup stages saved config only"]);
            requireTitle("network-role-setup-coordinator-port", ["7830 unless another local service"]);
            requireTitle("network-role-setup-bind-address", ["0.0.0.0 for LAN workers"]);
            requireTitle("network-role-setup-heartbeat-timeout", ["5 to 10 minutes"]);
            setInput("network-role-setup-coordinator-port", "7835");
            setInput("network-role-setup-bind-address", "0.0.0.0");
            setInput("network-role-setup-heartbeat-timeout", "9");
            click("#network-role-setup-stage-button", "coordinator setup stage button");
            const coordinatorPatch = settingsPatch();
            if (coordinatorPatch.NetworkRole !== "coordinator") throw new Error("coordinator setup did not stage NetworkRole=coordinator: " + JSON.stringify(coordinatorPatch));
            if (coordinatorPatch.CoordinatorPort !== 7835) throw new Error("coordinator port not staged");
            if (coordinatorPatch.CoordinatorHeartbeatTimeoutMins !== 9) throw new Error("coordinator heartbeat not staged");
            click("#network-role-setup-close-button", "coordinator setup close button");

            requireText("network-coordinator-join-status", ["Route ready"]);
            requireText("network-worker-join-status", ["Route ready"]);
            requireText("network-worker-discovery-status", ["Route ready"]);
            const createJoinButton = byId("network-coordinator-join-create");
            const copyJoinButton = byId("network-coordinator-join-copy");
            const importJoinButton = byId("network-worker-join-import");
            const discoverButton = byId("network-worker-discover");
            if (!createJoinButton || createJoinButton.disabled) throw new Error("coordinator join button should be enabled");
            if (!copyJoinButton || !copyJoinButton.disabled) throw new Error("copy join button should be disabled before blob creation");
            if (!importJoinButton || !importJoinButton.disabled) throw new Error("worker import button should be disabled before blob paste");
            if (!discoverButton || discoverButton.disabled) throw new Error("worker discovery button should be enabled");
            click("#network-worker-discover", "worker coordinator discovery button");
            await waitForText("network-worker-discovery-status", ["Discovery complete"]);
            requireText("network-worker-discovery-result", [
              "mDNS coordinator discovery complete.",
              "Selectable coordinators: 1",
              "http://discovered.test:7830",
              "No files, queue, scratch, output, pending publish",
            ]);
            requireText("network-worker-discovery-list", ["http://discovered.test:7830", "Use"]);
            click('#network-worker-discovery-list [data-network-discovery-url]', "use discovered coordinator button");
            await waitForText("network-worker-discovery-status", ["Coordinator staged"]);
            if (byId("settings-network-worker-url").value !== "http://discovered.test:7830") {
              throw new Error("discovered coordinator did not fill settings worker URL");
            }
            const discoveryPatch = settingsPatch();
            if (discoveryPatch.NetworkRole !== "worker") throw new Error("discovery did not stage NetworkRole=worker: " + JSON.stringify(discoveryPatch));
            if (discoveryPatch.WorkerCoordinatorUrl !== "http://discovered.test:7830") {
              throw new Error("discovery did not stage WorkerCoordinatorUrl: " + JSON.stringify(discoveryPatch));
            }
            setInput("network-coordinator-join-url", "http://coordinator.test:7830");
            const joinBlobPostsBeforeCancel = posted.filter((entry) => String(entry.url).includes("/api/network/coordinator/join-blob")).length;
            const rotateCheckbox = byId("network-coordinator-join-rotate");
            rotateCheckbox.checked = true;
            rotateCheckbox.dispatchEvent(new Event("change", { bubbles: true }));
            click("#network-coordinator-join-create", "coordinator join blob button");
            requireDialogOpen("network-lifecycle-confirm-dialog", ["Rotate token + create blob", "secret-transfer", "Token rotation: yes"]);
            click("#network-lifecycle-confirm-cancel", "cancel join blob confirmation");
            await waitForText("network-coordinator-join-status", ["Cancelled"]);
            const joinBlobPostsAfterCancel = posted.filter((entry) => String(entry.url).includes("/api/network/coordinator/join-blob")).length;
            if (joinBlobPostsAfterCancel !== joinBlobPostsBeforeCancel) {
              throw new Error("cancelled join blob confirmation still posted: " + JSON.stringify(posted));
            }
            click("#network-coordinator-join-create", "coordinator join blob button after cancel");
            requireDialogOpen("network-lifecycle-confirm-dialog", ["Rotate token + create blob", "secret-transfer", "Token rotation: yes"]);
            click("#network-lifecycle-confirm-submit", "confirm join blob command");
            await waitForText("network-coordinator-join-status", ["Blob ready"]);
            requireText("network-coordinator-join-result", [
              "Coordinator join blob created.",
              "intentionally not written to command history",
              "Token fingerprint: sha256:browser-smoke",
              "Libraries: 2",
            ]);
            if (byId("network-coordinator-join-output").value !== "mediapipeline-join:browser-smoke") {
              throw new Error("coordinator join output did not receive mocked blob");
            }
            if (copyJoinButton.disabled) throw new Error("copy join button should enable after blob creation");
            setInput("network-worker-join-blob", byId("network-coordinator-join-output").value);
            if (importJoinButton.disabled) throw new Error("worker import button should enable after blob paste");
            click("#network-worker-join-import", "worker join cluster button");
            requireDialogOpen("network-lifecycle-confirm-dialog", ["Join Cluster", "config-write", "does not start worker polling"]);
            click("#network-lifecycle-confirm-cancel", "cancel join cluster confirmation");
            await waitForText("network-worker-join-status", ["Cancelled"]);
            const joinClusterPostsAfterCancel = posted.filter((entry) => String(entry.url).includes("/api/network/worker/join-cluster")).length;
            if (joinClusterPostsAfterCancel !== 0) {
              throw new Error("cancelled join cluster confirmation still posted: " + JSON.stringify(posted));
            }
            click("#network-worker-join-import", "worker join cluster button after cancel");
            requireDialogOpen("network-lifecycle-confirm-dialog", ["Join Cluster", "config-write", "does not start worker polling"]);
            click("#network-lifecycle-confirm-submit", "confirm join cluster command");
            await waitForText("network-worker-join-status", ["Joined"]);
            requireText("network-worker-join-result", [
              "Worker join import complete.",
              "Effect: backend config-write",
              "Lifecycle: worker polling was not started.",
              "Settings save: saved",
              "Auto path-map entries: 1",
              "Test connection: passed",
            ]);

            const allowedPostTargets = [
              "/api/diagnostics/open",
              "/api/network/coordinator/start-dry-run",
              "/api/network/coordinator/stop-dry-run",
              "/api/network/worker/test-connection",
              "/api/network/worker/discover-coordinators",
              "/api/network/coordinator/join-blob",
              "/api/network/worker/join-cluster",
            ];
            const isAllowedUiPreferencePost = (entry) => {
              if (!String(entry.url || "").includes("/api/ui-preferences")) return false;
              const storage = entry.body && typeof entry.body === "object" ? entry.body.storage || {} : {};
              return entry.body?.source_surface === "webview"
                && !Object.keys(storage).some((key) => key.startsWith("mediapipeline-network-tab"));
            };
            if (posted.some((entry) => !allowedPostTargets.some((target) => String(entry.url).includes(target)) && !isAllowedUiPreferencePost(entry))) {
              throw new Error("Network smoke observed unexpected POST target: " + JSON.stringify(posted));
            }
            const joinBlobPost = posted.find((entry) => String(entry.url).includes("/api/network/coordinator/join-blob"));
            if (!joinBlobPost?.body?.confirm_create || !joinBlobPost?.body?.rotate_token || !joinBlobPost?.body?.confirm_rotate) {
              throw new Error("join blob request did not carry explicit confirmation fields: " + JSON.stringify(joinBlobPost));
            }
            const joinClusterPost = posted.find((entry) => String(entry.url).includes("/api/network/worker/join-cluster"));
            if (!joinClusterPost?.body?.confirm_import) {
              throw new Error("join cluster request did not carry explicit confirmation field: " + JSON.stringify(joinClusterPost));
            }
            return {
              ok: true,
              filterSummary: preJoinSmokeResult.filterSummary,
              lifecycleStatus: preJoinSmokeResult.lifecycleStatus,
              lifecycleSummary: preJoinSmokeResult.lifecycleSummary,
              evidenceStatus: preJoinSmokeResult.evidenceStatus,
              stateFilesStatus: preJoinSmokeResult.stateFilesStatus,
              stateFilesSummary: preJoinSmokeResult.stateFilesSummary,
              workerStatus: preJoinSmokeResult.workerStatus,
              posted,
              opened,
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
                expression: `Boolean(document.getElementById("network-worker-filter-summary") && document.getElementById("network-state-files-summary") && document.getElementById("network-lifecycle-summary") && document.getElementById("network-coordinator-overview-summary") && document.getElementById("network-worker-overview-summary") && document.getElementById("settings-patch-json") && typeof window.mediaPipelineNetworkView.renderNetworkView === "function" && typeof window.mediaPipelineNetworkView.renderNetworkLifecycleHandoff === "function" && typeof window.mediaPipelineNetworkView.networkLifecycleRows === "function" && typeof window.mediaPipelineNetworkView.renderNetworkStateFiles === "function" && typeof window.mediaPipelineNetworkView.syncNetworkRoleDashboards === "function" && typeof window.mediaPipelineNetworkView.networkCoordinatorOverviewModel === "function" && typeof window.mediaPipelineNetworkView.networkWorkerOverviewModel === "function" && typeof window.mediaPipelineSettingsView?.syncNetworkSettingsBuilderFromConfig === "function" && typeof window.showPage === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("network-worker-filter-summary") && document.getElementById("network-state-files-summary") && document.getElementById("network-lifecycle-summary") && document.getElementById("network-coordinator-overview-summary") && document.getElementById("network-worker-overview-summary") && document.getElementById("settings-patch-json") && typeof window.mediaPipelineNetworkView.renderNetworkView === "function" && typeof window.mediaPipelineNetworkView.renderNetworkLifecycleHandoff === "function" && typeof window.mediaPipelineNetworkView.networkLifecycleRows === "function" && typeof window.mediaPipelineNetworkView.renderNetworkStateFiles === "function" && typeof window.mediaPipelineNetworkView.syncNetworkRoleDashboards === "function" && typeof window.mediaPipelineNetworkView.networkCoordinatorOverviewModel === "function" && typeof window.mediaPipelineNetworkView.networkWorkerOverviewModel === "function" && typeof window.mediaPipelineSettingsView?.syncNetworkSettingsBuilderFromConfig === "function" && typeof window.showPage === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Network WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: networkScript(payload.networkPayload),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
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


def _run_browser_network_smoke(*, browser_path: str, url: str, network_payload: dict[str, object]) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView Network smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-network-payload.json"
        runner_path = tmp / "browser-network-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "networkPayload": network_payload,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_network_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Network smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


def _network_payload(root: Path) -> dict[str, object]:
    def lifecycle_route(path: str, role: str, action: str, dry_run: bool) -> dict[str, object]:
        return {
            "path": path,
            "method": "POST",
            "effect": "none" if dry_run else "backend-lifecycle",
            "auth_required": True,
            "owner": "Network",
            "frontend_exposed": True,
            "requires_confirmation": not dry_run,
            "journaled": not dry_run,
            "network_lifecycle": {"role": role, "action": action, "dry_run": dry_run},
        }

    return {
        "settings": {
            "config": {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "0.0.0.0",
                "CoordinatorAlsoEncodeLocally": False,
                "CoordinatorHeartbeatTimeoutMins": 5,
                "CoordinatorMaxJobRetries": 3,
                "WorkerPollIntervalSecs": 10,
            },
            "field_definitions": [],
        },
        "contract": {
            "schema_version": "local_api_contract.v1",
            "auth": {"public_routes": ["/api/health"]},
            "routes": [
                {"path": "/api/network/workers", "method": "GET", "effect": "none", "auth_required": True},
                {"path": "/api/network/status", "method": "GET", "effect": "none", "auth_required": True},
                lifecycle_route("/api/network/coordinator/start-dry-run", "coordinator", "start", True),
                lifecycle_route("/api/network/coordinator/stop-dry-run", "coordinator", "stop", True),
                lifecycle_route("/api/network/worker/start-dry-run", "worker", "start", True),
                lifecycle_route("/api/network/worker/stop-dry-run", "worker", "stop", True),
                {
                    "path": "/api/network/worker/test-connection",
                    "method": "POST",
                    "effect": "none",
                    "auth_required": True,
                    "owner": "Network",
                    "frontend_exposed": True,
                    "requires_confirmation": False,
                    "journaled": False,
                    "request_keys": ["timeout_seconds"],
                    "response_schema": "desktop_command_result.v1",
                    "data_schema": "desktop_network_worker_test_connection.v1",
                },
                {
                    "path": "/api/network/worker/discover-coordinators",
                    "method": "POST",
                    "effect": "none",
                    "auth_required": True,
                    "owner": "Network",
                    "frontend_exposed": True,
                    "requires_confirmation": False,
                    "journaled": False,
                    "request_keys": ["timeout_seconds"],
                    "response_schema": "desktop_command_result.v1",
                    "data_schema": "desktop_network_coordinator_discovery.v1",
                },
                {
                    "path": "/api/network/coordinator/join-blob",
                    "method": "POST",
                    "effect": "secret-transfer",
                    "auth_required": True,
                    "owner": "Network",
                    "frontend_exposed": True,
                    "requires_confirmation": True,
                    "journaled": False,
                    "request_keys": ["coordinator_url", "confirm_create", "rotate_token", "confirm_rotate"],
                    "response_schema": "desktop_command_result.v1",
                    "data_schema": "desktop_network_join_blob_result.v1",
                },
                {
                    "path": "/api/network/worker/join-cluster",
                    "method": "POST",
                    "effect": "config-write",
                    "auth_required": True,
                    "owner": "Network",
                    "frontend_exposed": True,
                    "requires_confirmation": True,
                    "journaled": False,
                    "request_keys": ["join_blob", "confirm_import", "timeout_seconds"],
                    "response_schema": "desktop_command_result.v1",
                    "data_schema": "desktop_network_join_import_result.v1",
                },
                lifecycle_route("/api/network/coordinator/start", "coordinator", "start", False),
                lifecycle_route("/api/network/coordinator/stop", "coordinator", "stop", False),
                lifecycle_route("/api/network/worker/start", "worker", "start", False),
                lifecycle_route("/api/network/worker/stop", "worker", "stop", False),
                {"path": "/api/diagnostics/open", "method": "POST", "effect": "open-path", "auth_required": True},
            ],
            "network_lifecycle_summary": {
                "schema_version": "desktop_network_lifecycle_contracts.v1",
                "status": "backend_lifecycle_routes_available_provider_guarded",
                "mutation_enabled": True,
                "frontend_allowed": True,
                "safe_next_step": "Use Network/Workers dry-runs first. Confirmed start/stop commands are backend-owned, command-journaled, confirmation-gated, and blocked when provider hooks are unavailable or preconditions fail.",
            },
            "network_lifecycle_contracts": [
                {"command": "coordinator.start", "current_status": "backend_route_available_provider_guarded"},
                {"command": "coordinator.stop", "current_status": "backend_route_available_provider_guarded"},
                {"command": "worker.polling_lifecycle", "current_status": "backend_route_available_provider_guarded"},
            ],
        },
        "closeReadiness": {"safe_to_close": True, "reason": "idle"},
        "snapshot": {"pipeline_state": "idle", "queue_depth": 0},
        "queue": {
            "schema_version": "desktop_queue_preview.v1",
            "source": str(root / "State" / "queue_snapshot.json"),
            "runnable_count": 3,
            "priority_count": 1,
            "snapshot_file_freshness_status": "fresh",
            "produced_freshness_status": "fresh",
            "rows": [
                {
                    "global_order": 1,
                    "queue_index": 1,
                    "display_name": "Episode 01.mkv",
                    "source_path": str(root / "TV" / "Show" / "Episode 01.mkv"),
                    "route_name": "encode",
                    "route_reason_code": "size_policy",
                    "route_decision_summary": "encode required",
                    "manifest_priority_level": "high",
                    "size_gb": 2.5,
                    "operator_status": "ready",
                },
                {
                    "global_order": 2,
                    "queue_index": 2,
                    "display_name": "Episode 03.mkv",
                    "source_path": str(root / "TV" / "Show" / "Episode 03.mkv"),
                    "route_name": "remux",
                    "route_reason_code": "copy_compatible",
                    "route_decision_summary": "already compatible",
                    "manifest_priority_level": "normal",
                    "size_gb": 1.4,
                    "operator_status": "ready",
                },
                {
                    "global_order": 3,
                    "queue_index": 3,
                    "display_name": "Episode 04.mkv",
                    "source_path": str(root / "TV" / "Show" / "Episode 04.mkv"),
                    "route_name": "encode",
                    "route_reason_code": "worker current local claim",
                    "route_decision_summary": "worker current local claim",
                    "manifest_priority_level": "low",
                    "size_gb": 2.1,
                    "operator_status": "ready",
                },
            ],
            "warnings": [],
        },
        "networkWorkers": {
            "source": "runtime_state_files",
            "role": "coordinator",
            "runtime_status_label": "Blocked",
            "runtime_status_severity": "blocked",
            "lifecycle_state": {
                "schema_version": "desktop_network_lifecycle_state.v1",
                "source": "session_memory_only",
                "coordinator": {"role": "coordinator", "status": "running", "state_scope": "session_memory_only", "read_only": True},
                "worker": {"role": "worker", "status": "stopped", "state_scope": "session_memory_only", "read_only": True},
                "read_only": True,
            },
            "token_posture": {
                "schema_version": "desktop_network_token_posture.v1",
                "coordinator": {"status": "present", "display": "present, hidden", "hidden": True},
                "worker": {"status": "missing", "display": "missing; must match the coordinator token", "hidden": True},
                "summary_lines": [
                    "Coordinator token: present, hidden.",
                    "Worker token: missing; must match the coordinator token.",
                    "Token values are hidden; workers must use the same shared token as the coordinator.",
                ],
                "read_only": True,
            },
            "operator_summary_lines": [
                "Mode: Coordinator only.",
                "Runtime: Blocked (blocked).",
                "Normal Launch: blocked in this network mode; use Network Lifecycle controls.",
                "Lifecycle state: coordinator running.",
                "Worker-facing coordinator URL: http://coordinator.test:7830.",
                "Workers: active=1; idle=1.",
                "Coordinator token: present, hidden.",
                "Worker token: missing; must match the coordinator token.",
                "Restart note: if backend Python files were updated while this app/API was already running, restart the app/API before using lifecycle controls.",
            ],
            "diagnostic_layers": {
                "schema_version": "desktop_network_diagnostic_layers.v1",
                "url_reachable": "ready",
                "auth_ok": "review",
                "paths_ok": "ready",
                "queue_fresh": "ready",
                "last_claim_result": "review",
                "layers": [
                    {"key": "url_reachable", "label": "URL reachability", "status": "ready", "detail": "Worker-facing URL configured.", "read_only": True},
                    {"key": "auth_ok", "label": "Auth posture", "status": "review", "detail": "Worker token missing; value hidden.", "read_only": True},
                    {"key": "paths_ok", "label": "Path access posture", "status": "ready", "detail": "configured roots=3; path_map_entries=1.", "read_only": True},
                    {"key": "queue_fresh", "label": "Queue freshness", "status": "ready", "detail": "coordinator_inflight age=120s.", "read_only": True},
                    {"key": "last_claim_result", "label": "Last claim result", "status": "review", "detail": "last worker failure reason_code=SOURCE_NOT_FOUND.", "read_only": True},
                ],
                "summary_lines": [
                    "url_reachable: ready - Worker-facing URL configured.",
                    "auth_ok: review - Worker token missing; value hidden.",
                    "paths_ok: ready - configured roots=3; path_map_entries=1.",
                    "queue_fresh: ready - coordinator_inflight age=120s.",
                    "last_claim_result: review - last worker failure reason_code=SOURCE_NOT_FOUND.",
                ],
                "read_only": True,
            },
            "running_vs_saved": {
                "schema_version": "desktop_network_worker_running_vs_saved.v1",
                "status": "drift",
                "drift_fields": ["WorkerPollIntervalSecs"],
                "drift_field_labels": ["Worker poll interval"],
                "summary_lines": [
                    "Worker settings drift: Worker poll interval differs from saved config.",
                ],
                "read_only": True,
            },
            "active_count": 1,
            "idle_count": 1,
            "session_completed": 12,
            "session_failed": 1,
            "coordinator_connectivity": {
                "schema_version": "desktop_network_coordinator_connectivity.v1",
                "role": "coordinator",
                "bind_endpoint": "0.0.0.0:7830",
                "worker_coordinator_url": "http://coordinator.test:7830",
                "candidate_urls": [{"label": "Computer name", "url": "http://coordinator.test:7830", "source": "fixture"}],
                "warnings": [],
                "summary_lines": [
                    "Worker coordinator URL: http://coordinator.test:7830",
                    "Coordinator bind endpoint: 0.0.0.0:7830",
                    "Use the worker coordinator URL in WorkerCoordinatorUrl on worker machines; do not use 0.0.0.0 as a worker target.",
                ],
                "read_only": True,
            },
            "coordinator_inflight_path": str(root / "State" / "Network" / "coordinator_inflight.json"),
            "worker_state_path": str(root / "State" / "Network" / "worker_state.json"),
            "cluster_log_path": str(root / "RunLogs" / "cluster.log"),
            "state_files": [
                {
                    "key": "coordinator_inflight",
                    "label": "Coordinator in-flight registry",
                    "path": str(root / "State" / "Network" / "coordinator_inflight.json"),
                    "purpose": "Tracks active and idle worker rows persisted by the coordinator dispatcher.",
                    "exists": True,
                    "status": "present",
                    "size_bytes": 512,
                    "modified_at": "2026-05-15T20:00:00+00:00",
                    "age_seconds": 120,
                    "error": "",
                },
                {
                    "key": "worker_state",
                    "label": "Local worker state",
                    "path": str(root / "State" / "Network" / "worker_state.json"),
                    "purpose": "Tracks the current local worker claim and any pending done report.",
                    "exists": True,
                    "status": "present",
                    "size_bytes": 128,
                    "modified_at": "2026-05-15T20:01:00+00:00",
                    "age_seconds": 60,
                    "error": "",
                },
                {
                    "key": "cluster_log",
                    "label": "Cluster log",
                    "path": str(root / "RunLogs" / "cluster.log"),
                    "purpose": "Records coordinator/worker network lifecycle and claim events.",
                    "exists": False,
                    "status": "missing",
                    "size_bytes": 0,
                    "modified_at": "",
                    "age_seconds": None,
                    "error": "",
                },
            ],
            "warnings": ["coordinator persisted state may be stale"],
            "worker_state": {
                "job_id": "local-job",
                "source_file": str(root / "TV" / "Show" / "Episode 04.mkv"),
                "source_path": str(root / "TV" / "Show" / "Episode 04.mkv"),
                "pending_done_report": True,
            },
            "worker_progress": {
                "schema_version": "desktop_network_worker_progress.v1",
                "mode": "worker_progress",
                "status": "blocked",
                "active_count": 1,
                "blocked_count": 1,
                "warning_count": 0,
                "bar_count": 3,
                "summary_lines": [
                    "Last reported worker progress: blocked",
                    "Runtime evidence role: coordinator",
                    "Progress bars: 3",
                    "Active worker bars: 1",
                    "Blocked/stale worker bars: 1",
                    "Warning worker bars: 0",
                    "Mutation guardrail: Last reported network progress is read-only persisted runtime evidence; WebView lifecycle controls must use backend-owned Network lifecycle routes and must not reclaim jobs, release claims, send done reports, mutate queue state, or touch media files.",
                ],
                "progress_bars": [
                    {
                        "id": "network_mode",
                        "label": "Runtime evidence",
                        "mode": "indeterminate",
                        "percent": None,
                        "status": "active",
                        "detail": "role=coordinator; worker_rows=3; warnings=1",
                        "source": "desktop_network_workers.v1",
                    },
                    {
                        "id": "network_worker_worker_a_active_job",
                        "label": "worker-active",
                        "mode": "determinate",
                        "percent": 42,
                        "status": "active",
                        "detail": "file=Episode 01.mkv; stage=encoding; heartbeat_age=12s; job=active-job",
                        "source": "coordinator_inflight",
                    },
                    {
                        "id": "network_worker_worker_b_failed_job",
                        "label": "worker-failed",
                        "mode": "determinate",
                        "percent": 63,
                        "status": "blocked",
                        "detail": "file=Episode 02.mkv; stage=failed; heartbeat_age=900s; job=failed-job; error=ffmpeg exited 1",
                        "source": "coordinator_inflight",
                        "stale": True,
                    },
                ],
                "read_only": True,
            },
            "rows": [
                {
                    "worker_name": "worker-active",
                    "worker_id": "worker-a",
                    "status": "active",
                    "job_id": "active-job",
                    "source_path": str(root / "TV" / "Show" / "Episode 01.mkv"),
                    "current_file": str(root / "TV" / "Show" / "Episode 01.mkv"),
                    "current_file_name": "Episode 01.mkv",
                    "current_stage": "encoding",
                    "progress_percent": 42,
                    "heartbeat_age_seconds": 12,
                    "accessible_library_ids": ["movies", "tv"],
                    "files_completed": 3,
                    "total_gb_encoded": 15.2,
                    "avg_speed_gbh": 48.1,
                },
                {
                    "worker_name": "worker-failed",
                    "worker_id": "worker-b",
                    "status": "failed",
                    "job_id": "failed-job",
                    "source_path": str(root / "TV" / "Show" / "Episode 02.mkv"),
                    "current_file": str(root / "TV" / "Show" / "Episode 02.mkv"),
                    "current_file_name": "Episode 02.mkv",
                    "current_stage": "failed",
                    "progress_percent": 63,
                    "heartbeat_age_seconds": 900,
                    "accessible_library_ids": ["movies"],
                    "return_code": 1,
                    "error": "ffmpeg exited 1",
                    "last_failure_reason_code": "SOURCE_NOT_FOUND",
                    "last_failure_reason": "C:/Media/Episode 02.mkv not found on worker",
                    "last_failure_job_id": "failed-job",
                    "last_failure_source_path": str(root / "TV" / "Show" / "Episode 02.mkv"),
                    "last_failure_at": "2026-05-15T20:00:00+00:00",
                    "failure_streak_reason_code": "SOURCE_NOT_FOUND",
                    "failure_streak_count": 3,
                    "worker_misconfigured_reason_code": "SOURCE_NOT_FOUND",
                    "worker_misconfigured_at": "2026-05-15T20:02:00+00:00",
                },
                {
                    "worker_name": "worker-idle",
                    "worker_id": "worker-c",
                    "status": "idle",
                    "job_id": "",
                    "current_file_name": "",
                    "current_stage": "idle",
                    "accessible_library_ids": ["movies", "tv"],
                    "files_completed": 9,
                    "total_gb_encoded": 88.0,
                    "avg_speed_gbh": 52.0,
                },
            ],
        },
    }


class WebViewBrowserNetworkSmoke(unittest.TestCase):
    def test_real_browser_network_worker_filters_warn_when_hiding_review_rows(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView Network smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="browser-network-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_network_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    network_payload=_network_payload(root),
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertEqual(browser_result["lifecycleStatus"], "Blocked review")
        self.assertIn("Network lifecycle handoff:", browser_result["lifecycleSummary"])
        self.assertEqual(browser_result["evidenceStatus"], "Blocked review")
        self.assertEqual(browser_result["stateFilesStatus"], "Review")
        self.assertIn("Network runtime state file evidence:", browser_result["stateFilesSummary"])
        self.assertIn("Showing 0/3", browser_result["filterSummary"])
        self.assertIn('Filter: search="no-match-filter"', browser_result["filterSummary"])
        self.assertIn("clear filters before lifecycle decisions", browser_result["filterSummary"])
        posted = browser_result["posted"]
        ui_preference_posts = [entry for entry in posted if entry["url"] == "/api/ui-preferences"]
        for entry in ui_preference_posts:
            self.assertEqual(entry["body"]["source_surface"], "webview")
            storage = entry["body"].get("storage") or {}
            self.assertFalse([key for key in storage if key.startswith("mediapipeline-network-tab")])
        command_posts = [entry for entry in posted if entry["url"] != "/api/ui-preferences"]
        self.assertEqual(
            [entry["url"] for entry in command_posts],
            [
                "/api/network/coordinator/stop-dry-run",
                "/api/network/worker/test-connection",
                "/api/network/worker/discover-coordinators",
                "/api/network/coordinator/join-blob",
                "/api/network/worker/join-cluster",
            ],
        )
        self.assertEqual(
            command_posts[0]["body"],
            {"reason": "webview_network_lifecycle_guided_dry_run"},
        )
        self.assertEqual(
            command_posts[1]["body"],
            {},
        )
        self.assertEqual(
            command_posts[2]["body"],
            {"timeout_seconds": 2},
        )
        self.assertEqual(
            command_posts[3]["body"],
            {
                "confirm_create": True,
                "rotate_token": True,
                "coordinator_url": "http://coordinator.test:7830",
                "confirm_rotate": True,
            },
        )
        self.assertEqual(
            command_posts[4]["body"],
            {
                "join_blob": "mediapipeline-join:browser-smoke",
                "confirm_import": True,
            },
        )
