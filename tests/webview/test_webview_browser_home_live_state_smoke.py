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
from mediapipeline.desktop.models import Snapshot

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


def _write_command_history(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "desktop_command_history.v1",
                "entries": [
                    {
                        "at": "2026-05-15T01:00:00Z",
                        "command": "settings.preview_patch",
                        "ok": True,
                        "severity": "warning",
                        "message": "Preview completed with operator-review warnings.",
                        "refresh_hint": "settings",
                        "warnings": ["Legacy video flags require review before unattended use."],
                        "errors": [],
                        "log_paths": {},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _browser_home_live_state_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function homeLiveStateScript() {
          return `
          (async () => {
            const posts = [];
            const originalApiPost = window.apiPost;
            window.apiPost = async (path, body, options) => {
              posts.push({ path: String(path || ""), body: body || {}, options: options || {} });
              return { ok: false, message: "home live-state smoke blocks POST routes" };
            };
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function tableText(id) { const node = byId(id); return node ? node.innerText || node.textContent || "" : ""; }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireTableText(id, fragments) {
              const actual = tableText(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function clickRowByText(tbodyId, fragment) {
              const tbody = byId(tbodyId);
              if (!tbody) throw new Error("missing tbody " + tbodyId);
              const rows = Array.from(tbody.querySelectorAll("tr"));
              const row = rows.find((item) => {
                const firstCell = item.querySelector("td");
                const label = firstCell ? firstCell.textContent || "" : "";
                return label.includes(fragment);
              }) || rows.find((item) => (item.innerText || item.textContent || "").includes(fragment));
              if (!row) throw new Error(tbodyId + " missing selectable row " + fragment + "\\nActual:\\n" + tableText(tbodyId));
              row.click();
            }
            function requirePanelState(id, expectedStates) {
              const node = byId(id);
              if (!node) throw new Error("missing panel status " + id);
              const actual = node.dataset.state || node.getAttribute("data-state") || "";
              if (!expectedStates.includes(actual)) {
                throw new Error(id + " expected state " + expectedStates.join("|") + " but saw " + actual + "\\nText:\\n" + text(id));
              }
            }
            function requireSingleSelected(selector, label) {
              const selected = Array.from(document.querySelectorAll(selector + ".is-selected, " + selector + "[aria-selected='true']"));
              const unique = Array.from(new Set(selected));
              if (unique.length !== 1) {
                throw new Error(label + " expected exactly one selected row/item, saw " + unique.length);
              }
              const row = unique[0];
              if (!row.classList.contains("is-selected") || row.getAttribute("aria-selected") !== "true") {
                throw new Error(label + " selected row/item did not expose both class and aria-selected.");
              }
              return row;
            }
            function clickListItem(listId, fragment) {
              const list = byId(listId);
              if (!list) throw new Error("missing list " + listId);
              const item = Array.from(list.querySelectorAll("[role='option'], li")).find((node) => (node.innerText || node.textContent || "").includes(fragment));
              if (!item) throw new Error(listId + " missing selectable item " + fragment + "\\nActual:\\n" + text(listId));
              item.click();
              return requireSingleSelected("#" + listId + " [role='option']", listId);
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
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : "") + "\\nState:\\n" + [
                "homeReadiness=" + text("home-readiness-summary"),
                "nextQueue=" + text("home-next-queue-list"),
                "queueCount=" + text("queue-count"),
                "queueSnapshot=" + text("home-queue-snapshot"),
                "dailyDriver=" + text("daily-driver-summary"),
                "externalDependencies=" + text("home-external-dependencies-summary"),
                "activeWork=" + text("home-active-work-summary"),
                "progressBars=" + text("progress-bar-list"),
                "progressDetails=" + tableText("progress-detail-rows"),
                "progressEvidence=" + text("progress-evidence-summary"),
                "commandSummary=" + text("command-summary"),
                "worksheet=" + text("cross-page-real-media-summary"),
                "posts=" + JSON.stringify(posts),
              ].join("\\n"));
            }
            [
              "showPage",
              "renderHomeNextQueue",
              "renderHomeStorageHealth",
              "renderDailyDriverReadiness",
              "renderHomeReadiness",
              "renderHomeActiveWork",
              "renderProgressBars",
              "renderProgressDetails",
              "renderProgressEvidence",
              "renderDiagnosticsProgress",
              "renderCommandHistoryPayload",
              "getCommandHistory",
              "renderCrossPageContext",
              "refreshAllNow",
              "renderExternalDependencyDigest",
              "updatePagePanelEmptyStates",
            ].forEach(requireFunction);

            window.showPage("home");
            await waitFor(
              () => text("daily-driver-summary").includes("Daily-driver readiness checklist:")
                && text("state-pill").includes("Encoding")
                && text("home-next-queue-list").includes("Serial Experiments Lain")
                && text("home-next-queue-list").includes("S02E01")
                && text("home-scratch-storage-status").includes("OK")
                && text("home-output-storage-status").includes("OK")
                && text("progress-bar-list").includes("Current backend stage")
                && text("progress-bar-list").includes("Publish")
                && text("home-readiness-summary").includes("Backend snapshot: ok")
                && text("home-active-work-summary").includes("ActiveJobs:")
                && text("command-summary").includes("Results: 1")
                && text("cross-page-real-media-summary").includes("Sample validation:"),
              "Home live-state panels",
            );

            const evidenceToggle = document.getElementById("evidence-toggle");
            if (!evidenceToggle) throw new Error("Missing evidence-toggle button.");
            const homeInteractiveBefore = Array.from(document.querySelectorAll('[data-page-panel="home"] .panel[data-panel-type="interactive"]'))
              .filter((panel) => panel.offsetParent !== null);
            evidenceToggle.click();
            if (!document.body.classList.contains("evidence-hidden")) {
              throw new Error("Evidence toggle did not add evidence-hidden body class.");
            }
            const visibleEvidence = Array.from(document.querySelectorAll('.panel[data-panel-type="evidence"]'))
              .filter((panel) => panel.offsetParent !== null);
            if (visibleEvidence.length) {
              throw new Error("Evidence toggle left visible evidence panels: " + visibleEvidence.map((panel) => panel.querySelector("h2,h3")?.textContent || panel.id || "panel").join(", "));
            }
            const hiddenInteractive = homeInteractiveBefore.filter((panel) => panel.offsetParent === null);
            if (hiddenInteractive.length) {
              throw new Error("Evidence toggle hid Home interactive panels: " + hiddenInteractive.map((panel) => panel.querySelector("h2,h3")?.textContent || panel.id || "panel").join(", "));
            }
            const nextQueuePanel = document.querySelector(".home-next-queue-panel");
            if (!nextQueuePanel || nextQueuePanel.offsetParent === null) {
              throw new Error("Evidence toggle hid the Home next-queue panel.");
            }
            window.showPage("live");
            const visibleTelemetryGraphs = ["cpu-chart", "gpu-chart", "ram-chart"].filter((id) => {
              const canvas = document.getElementById(id);
              return canvas && canvas.offsetParent !== null;
            });
            if (visibleTelemetryGraphs.length !== 3) {
              throw new Error("Evidence toggle hid telemetry graph canvas(es): " + JSON.stringify(visibleTelemetryGraphs));
            }
            window.showPage("home");
            evidenceToggle.click();
            if (document.body.classList.contains("evidence-hidden")) {
              throw new Error("Evidence toggle did not restore evidence visibility.");
            }
            const scrollSpacer = document.createElement("div");
            scrollSpacer.style.height = "2000px";
            scrollSpacer.setAttribute("data-smoke-scroll-spacer", "true");
            const workspace = document.querySelector(".workspace") || document.scrollingElement || document.documentElement || document.body;
            workspace.appendChild(scrollSpacer);
            if (typeof workspace.scrollTo === "function") {
              workspace.scrollTo(0, workspace.scrollHeight || 1200);
            } else {
              workspace.scrollTop = workspace.scrollHeight || 1200;
            }
            await new Promise((resolve) => setTimeout(resolve, 50));
            const canStageScroll = workspace.scrollHeight > workspace.clientHeight && workspace.scrollTop > 0;
            if (canStageScroll) {
              window.showPage("settings");
              await new Promise((resolve) => setTimeout(resolve, 50));
              if (workspace.scrollTop !== 0) {
                scrollSpacer.remove();
                throw new Error("Page navigation did not reset workspace scroll to top; scrollTop=" + workspace.scrollTop);
              }
            }
            scrollSpacer.remove();
            window.showPage("home");
            const homePanels = Array.from(document.querySelectorAll('[data-page-panel="home"] .panel'));
            const priorHiddenAttrs = homePanels.map((panel) => panel.hasAttribute("data-panel-hidden"));
            homePanels.forEach((panel) => panel.setAttribute("data-panel-hidden", ""));
            window.updatePagePanelEmptyStates();
            const hiddenNotice = document.querySelector('[data-page-panel="home"] [data-page-empty-state="panel-visibility"]');
            if (!hiddenNotice || !hiddenNotice.classList.contains("is-visible")) {
              throw new Error("Hidden-panel notice did not appear when all Home panels were hidden.");
            }
            const hiddenNoticeText = hiddenNotice.innerText || hiddenNotice.textContent || "";
            for (const fragment of ["No boxes are visible on this tab.", "Boxes may be hidden", "Customize"]) {
              if (!hiddenNoticeText.includes(fragment)) {
                throw new Error("Hidden-panel notice missing " + fragment + "\\nActual:\\n" + hiddenNoticeText);
              }
            }
            homePanels.forEach((panel, index) => {
              if (!priorHiddenAttrs[index]) panel.removeAttribute("data-panel-hidden");
            });
            window.updatePagePanelEmptyStates();
            if (hiddenNotice.classList.contains("is-visible")) {
              throw new Error("Hidden-panel notice stayed visible after Home panels were restored.");
            }

            const gets = [];
            const originalApiGet = window.apiGet;
            window.apiGet = async (path, options) => {
              gets.push(String(path || ""));
              return originalApiGet(path, options);
            };
            const refreshPromise = window.refreshAllNow();
            const homeRefreshButton = byId("home-refresh-button");
            const globalRefreshButton = byId("refresh-button");
            if (!homeRefreshButton || homeRefreshButton.getAttribute("aria-busy") !== "true" || !homeRefreshButton.disabled) {
              throw new Error("Refresh Home button did not enter an immediate busy/disabled state.");
            }
            if (!globalRefreshButton || globalRefreshButton.getAttribute("aria-busy") !== "true" || !globalRefreshButton.disabled) {
              throw new Error("Global refresh button did not mirror Home refresh busy state.");
            }
            await refreshPromise;
            if (homeRefreshButton.getAttribute("aria-busy") === "true" || homeRefreshButton.disabled || text("home-refresh-button") !== "Refresh Home") {
              throw new Error("Refresh Home button did not restore after refresh.");
            }
            if (globalRefreshButton.getAttribute("aria-busy") === "true" || globalRefreshButton.disabled || text("refresh-button") !== "Refresh") {
              throw new Error("Global refresh button did not restore after refresh.");
            }
            if (gets.some((path) => path.startsWith("/api/maintenance"))) {
              throw new Error("Home refresh must not poll /api/maintenance because Maintenance health can run helper probes: " + JSON.stringify(gets));
            }
            await waitFor(
              () => text("home-external-dependencies-summary").includes("External dependency digest:")
                && text("home-external-dependencies-summary").includes("Maintenance toolchain"),
              "Home external dependency digest",
            );

            requireText("home-readiness-summary", [
              "Backend snapshot: ok",
              "Refresh health:",
              "Close readiness:",
              "Pipeline state:",
              "Next step:",
            ]);
            requireText("daily-driver-summary", [
              "Daily-driver readiness checklist:",
              "Real-media boundary:",
              "Next operator action:",
              "Mutation guardrail: this checklist is read-only",
            ]);
            requireText("state-pill", [
              "Encoding",
            ]);
            requireText("activity", [
              "Current Fixture",
              "Anime Library",
              "TV",
              "item 2 of 5",
              "Encode route",
              "42.5%",
            ]);
            const activityMeta = document.querySelector("#activity .activity-meta");
            if (!activityMeta) throw new Error("Topbar activity metadata line is missing.");
            const metaStyle = window.getComputedStyle(activityMeta);
            if (metaStyle.textOverflow !== "ellipsis" || metaStyle.whiteSpace !== "nowrap") {
              throw new Error("Topbar activity metadata is not clipped: textOverflow=" + metaStyle.textOverflow + "; whiteSpace=" + metaStyle.whiteSpace);
            }
            const activityText = text("activity");
            for (const forbidden of ["Original:", "Current Fixture.mkv", "Serial Experiments Lain S02E01 Weird.mkv"]) {
              if (activityText.includes(forbidden)) {
                throw new Error("Topbar activity leaked raw filename text: " + forbidden + "\\nActual:\\n" + activityText);
              }
            }
            requireText("home-next-queue-list", [
              "Serial Experiments Lain",
              "S02E01",
              "REMUX",
              "Ready",
              "1/1",
            ]);
            if (text("home-next-queue-list").includes("Weird")) {
              throw new Error("Home next queue leaked the TV episode title into the row label.\\nActual:\\n" + text("home-next-queue-list"));
            }
            clickListItem("home-next-queue-list", "Serial Experiments Lain");
            requireText("home-next-queue-detail", [
              "Selected queue item:",
              "Serial Experiments Lain S02E01",
              "Safe next step:",
            ]);
            requireSingleSelected("#home-recent-completed-tbody tr[data-selectable-row='true']", "Recently Completed");
            requireText("home-recent-completed-detail", [
              "Selected completed output:",
              "Safe next step:",
            ]);
            [
              ["home-readiness-status", ["warning", "ready", "blocked", "neutral"]],
              ["home-next-queue-status", ["ready", "warning", "empty", "neutral"]],
              ["home-recent-completed-status", ["ready", "empty", "warning", "neutral"]],
              ["home-active-work-status", ["ready", "warning", "blocked", "neutral", "running"]],
              ["progress-detail-status", ["ready", "warning", "blocked", "empty"]],
              ["progress-evidence-status", ["ready", "warning", "blocked", "empty"]],
              ["daily-driver-status", ["ready", "warning", "blocked", "neutral"]],
              ["home-external-dependencies-status", ["ready", "warning", "blocked", "neutral"]],
            ].forEach(([id, states]) => requirePanelState(id, states));
            requireText("home-run-state-handoff", [
              "Run state:",
              "Safe next step:",
              "Mutation guardrail:",
            ]);
            requireText("progress-bar-list", [
              "Active work",
              "Current backend stage",
              "42.5%",
              "Run total",
              "Publish",
              "Publish steps",
              "Publishing completed output",
              "50%",
            ]);
            requireText("home-external-dependencies-summary", [
              "External dependency digest:",
              "Scope: saved Settings OCR evidence, Settings raw-key action plan, Diagnostics settings handoff, and already-loaded Maintenance toolchain evidence.",
              "Settings raw-key action plan",
              "stage or save settings, edit secrets",
              "Maintenance toolchain",
              "Mutation guardrail: this digest is read-only",
            ]);
            requireTableText("daily-driver-rows", [
              "Refresh payloads",
              "Close / active work",
              "Saved settings",
              "External dependencies",
              "Real-media sample proof",
              "Recent commands",
            ]);
            requireText("home-active-work-summary", [
              "Pipeline state:",
              "Close readiness:",
              "ActiveJobs:",
              "Stage percent: 42.5",
              "Current Fixture.mkv",
              "Route: encode",
              "Next step:",
            ]);
            window.showPage("live");
            await waitFor(
              () => text("progress-detail-status").includes("checks")
                && text("progress-bar-list").includes("Active work")
                && text("progress-bar-list").includes("Current backend stage")
                && text("progress-bar-list").includes("42.5%")
                && text("progress-bar-list").includes("Run total")
                && text("progress-bar-list").includes("Publish")
                && tableText("progress-detail-rows").includes("Library")
                && tableText("progress-detail-rows").includes("Anime Library")
                && text("progress-evidence-summary").includes("Progress evidence board:")
                && tableText("progress-evidence-rows").includes("Current item"),
              "Live progress details and evidence",
            );
            const progressDetailText = tableText("progress-detail-rows");
            for (const hiddenLabel of ["State", "Stage", "Controls", "File"]) {
              if (progressDetailText.includes(hiddenLabel)) {
                throw new Error("Progress detail hidden card is still visible: " + hiddenLabel + "\\n" + progressDetailText);
              }
            }
            requireText("progress-bar-list", [
              "Active work",
              "3 checks",
              "Current backend stage",
              "42.5%",
              "active",
              "Run total",
              "Publishing completed output",
              "eta 1s",
              "Publish",
              "Publish steps",
              "50%",
              "source: pipeline_progress.json",
              "updated 01:04:00",
            ]);
            requireTableText("progress-detail-rows", [
              "Library",
              "Anime Library",
              "Profile: anime",
              "Source:",
              "Route",
              "encode",
              "operator-trust smoke fixture",
              "Done",
              "Remuxed",
              "Issues",
              "No failures reported",
            ]);
            requireText("progress-evidence-summary", [
              "Progress evidence board:",
              "Status: Active/review",
              "Rows:",
              "Rows needing attention:",
              "Mutation guardrail: this board is read-only",
            ]);
            requireTableText("progress-evidence-rows", [
              "Snapshot state",
              "ActiveJobs",
              "Current item",
              "Route / queue",
              "Proof boundary",
            ]);
            clickRowByText("progress-evidence-rows", "Current item");
            requireText("progress-evidence-detail", [
              "Checkpoint: Current item",
              "Posture: active",
              "Current file: Current Fixture.mkv",
              "Updated at: 2026-05-15 01:04:00",
              "Mutation guardrail: progress evidence is read-only",
            ]);
            clickRowByText("progress-evidence-rows", "ActiveJobs");
            requireText("progress-evidence-detail", [
              "Checkpoint: ActiveJobs",
              "Posture: active work",
              "pipeline; mode=continuous; status=active",
              "launch=launch-progress",
              "Mutation guardrail: progress evidence is read-only",
            ]);
            const structuredActiveJobRows = window.mediaPipelineProgressView.progressEvidenceRows({
              snapshot: {
                pipeline_state: "processing",
                activity: "Structured ActiveJobs fixture is active.",
                progress: { Status: "Processing", CurrentStage: "Encoding" },
              },
              closeReadiness: { safe_to_close: false, state: "active", reason: "structured ActiveJobs row" },
              diagnostics: {
                active_jobs: [],
                active_job_rows: [{
                  record_file: "structured-active.json",
                  launch_id: "structured-launch",
                  job_kind: "pipeline",
                  mode: "once",
                  status: "active",
                  status_state: "running",
                  pid: 1234,
                }],
              },
            });
            const structuredActiveJobs = structuredActiveJobRows.find((row) => row.key === "active-jobs");
            if (!structuredActiveJobs) throw new Error("structured ActiveJobs evidence row was not returned");
            if (!structuredActiveJobs.evidence.includes("1 ActiveJobs row")) {
              throw new Error("structured ActiveJobs evidence did not count active_job_rows: " + structuredActiveJobs.evidence);
            }
            const structuredDetail = structuredActiveJobs.detail.join("\\n");
            for (const fragment of ["pipeline", "mode=once", "status=active", "launch=structured-launch", "pid=1234"]) {
              if (!structuredDetail.includes(fragment)) throw new Error("structured ActiveJobs detail missing " + fragment + "\\nActual:\\n" + structuredDetail);
            }
            window.showPage("diagnostics");
            await waitFor(
              () => text("diagnostics-progress-status").includes("Pipeline active")
                && text("diagnostics-progress-detail").includes("Stage percent: 42.5")
                && tableText("diagnostics-progress-rows").includes("CurrentStagePercent"),
              "Diagnostics runtime progress summary",
            );
            requireText("diagnostics-progress-detail", [
              "Pipeline state: processing",
              "Stage: Encoding | Stage percent: 42.5 | File: Current Fixture.mkv",
              "Route: encode | Reason: operator-trust smoke fixture",
              "Queue position: 2 / 5",
              "Structured fields:",
              "Mutation guardrail: this table is read-only",
            ]);
            requireTableText("diagnostics-progress-rows", [
              "Pipeline",
              "CurrentStagePercent",
              "42.5",
              "CurrentFileDisplay",
              "Current Fixture.mkv",
            ]);
            window.showPage("home");
            requireText("command-summary", [
              "Results: 1",
              "Latest: settings.preview_patch",
              "Warnings: 1",
              "Owner pages:",
              "Settings",
            ]);
            requireTableText("command-rows", [
              "settings.preview_patch",
              "Settings",
              "warning",
              "Preview completed with operator-review warnings.",
            ]);
            requireText("cross-page-real-media-summary", [
              "Real-media validation worksheet:",
              "Queue route intent, Completed output proof, Pending Publish final-destination proof",
              "Sample Validation evidence posture",
              "Sample validation:",
            ]);
            requireTableText("cross-page-real-media-rows", [
              "Queue route decision",
              "Completed output and size proof",
              "Pending publish and final destination",
              "Diagnostics and run evidence",
              "Saved media policy",
              "Sample Validation readiness",
              "Acceptance boundary",
            ]);
            requireText("sample-validation-summary", [
              "Backend-owned sample validation records:",
              "Real-media pilot plan:",
              "Pilot checkpoints:",
              "Current evidence reconciliation:",
            ]);
            requireText("home-scratch-storage-detail", [
              "free / 1 GB reserve",
            ]);
            requireText("home-output-storage-detail", [
              "free / 1 GB reserve",
            ]);
            const preservedHomeLiveState = {
              statePill: text("state-pill"),
              readiness: text("home-readiness-summary"),
              queueCount: text("queue-count"),
              queueSnapshot: text("home-queue-snapshot"),
              nextQueue: text("home-next-queue-list"),
              scratchStorage: text("home-scratch-storage-status") + " " + text("home-scratch-storage-detail"),
              outputStorage: text("home-output-storage-status") + " " + text("home-output-storage-detail"),
              activity: text("activity"),
              dailyDriver: text("daily-driver-summary"),
              activeWork: text("home-active-work-summary"),
              progressBars: text("progress-bar-list"),
              progressDetails: tableText("progress-detail-rows"),
              progressEvidence: text("progress-evidence-summary"),
              progressEvidenceDetail: text("progress-evidence-detail"),
              diagnosticsProgress: text("diagnostics-progress-detail"),
              commandSummary: text("command-summary"),
              worksheet: text("cross-page-real-media-summary"),
            };
            if (typeof window.renderSnapshot !== "function") {
              throw new Error("renderSnapshot is not available for Home pipeline state formatting.");
            }
            const stoppedSnapshot = {
              app_version: "v5-test",
              pipeline_state: "idle",
              status_summary: "Stopped by request",
              current_work: { phase_label: "Idle" },
              counts: { queue_index: 0, queue_total: 0, processed: 9, failed: 1 },
              progress: { Status: "Stopped", CurrentStage: "stopped", StopRequested: true, Failed: 1 },
              progress_bars: [],
              recent_events: [
                {
                  event_type: "job_completed",
                  status: "stopped",
                  data: {
                    completion_status: "stopped",
                    error_code: "STOP_REQUESTED",
                    reason: "Processing stopped by operator",
                    publish_state: "parked",
                    publish_mode: "deferred",
                  },
                },
              ],
            };
            window.renderSnapshot(stoppedSnapshot);
            requireText("home-failed-label", ["Failed"]);
            requireText("failed-label", ["Failed"]);
            requireText("home-failed-count", ["0"]);
            requireText("progress-bar-list", ["Stopped after current", "Pending Publish"]);
            requireText("progress-detail-rows", ["Issues", "0", "Stop After Current is tracked"]);
            const stoppedMetricLabel = text("home-failed-label");
            const stoppedMetricTitle = byId("home-failed-count")?.title || "";
            const stoppedProgressBarText = text("progress-bar-list");
            const activeSnapshot = {
              app_version: "v5-test",
              pipeline_state: "encoding_tv_(cpu_fallback)",
              status_summary: "Status OK",
              current_work: { phase_label: "Encoding" },
              counts: { queue_index: 3, queue_total: 17, processed: 0, failed: 0 },
              progress: {},
              progress_bars: [],
              recent_events: [],
            };
            window.renderSnapshot(activeSnapshot);
            requireText("home-failed-label", ["Failed"]);
            requireText("queue-count", ["3 / 17"]);
            requireText("pipeline-state", [
              "Encoding TV",
              "(cpu fallback)",
            ]);
            const queueOutcomeRenderer = window.renderHomePipelineQueueOutcome
              || (typeof renderHomePipelineQueueOutcome === "function" ? renderHomePipelineQueueOutcome : null);
            if (typeof queueOutcomeRenderer !== "function") {
              throw new Error("renderHomePipelineQueueOutcome is not available for Home empty scan status.");
            }
            const emptyQueuePayload = {
              schema_version: "desktop_queue_preview.v1",
              rows: [],
              runnable_count: 0,
              warnings: ["Queue snapshot contains no runnable rows."],
              snapshot_file_freshness_status: "fresh",
              produced_freshness_status: "fresh",
              queue_progress: { schema_version: "desktop_queue_source_scan_progress.v1", status: "complete", stale: false },
              queue_scan_status: {
                schema_version: "desktop_queue_scan_status.v1",
                status: "completed",
                phase: "complete",
                curated_row_count: 0,
                inventory_count: 4,
              },
            };
            const activeEmptyApplied = queueOutcomeRenderer(window.getLastSnapshot?.(), emptyQueuePayload);
            if (activeEmptyApplied || !text("pipeline-state").includes("Encoding TV")) {
              throw new Error("Empty queue outcome overwrote active Pipeline tile: " + text("pipeline-state"));
            }
            window.renderSnapshot({
              app_version: "v5-test",
              pipeline_state: "idle",
              status_summary: "Status OK",
              current_work: { phase_label: "Idle" },
              counts: { queue_index: 3, queue_total: 17, processed: 0, failed: 0 },
              progress: {},
              progress_bars: [],
              recent_events: [],
            });
            const idleEmptyApplied = queueOutcomeRenderer(window.getLastSnapshot?.(), emptyQueuePayload);
            if (!idleEmptyApplied) {
              throw new Error("Empty queue outcome did not apply to idle Pipeline tile.");
            }
            requireText("pipeline-state", ["No New Sources"]);
            requireText("queue-count", ["3 / 17"]);
            const noNewPipelineState = text("pipeline-state");
            const noNewPipelineStateMain = byId("pipeline-state")?.querySelector(".pipeline-state-main")?.textContent || "";
            const noNewPipelineStateLabel = byId("pipeline-state")?.getAttribute("aria-label") || "";
            window.renderSnapshot(activeSnapshot);
            if (text("pipeline-state").includes("_")) {
              throw new Error("Home pipeline state still contains underscores: " + text("pipeline-state"));
            }
            if (posts.length) throw new Error("Home live-state render posted unexpected routes: " + JSON.stringify(posts));
            window.apiPost = originalApiPost;
            return {
              ok: true,
              posts,
              pipelineState: text("pipeline-state"),
              pipelineStateMain: byId("pipeline-state")?.querySelector(".pipeline-state-main")?.textContent || "",
              pipelineStateDetail: byId("pipeline-state")?.querySelector(".pipeline-state-detail")?.textContent || "",
              pipelineStateLabel: byId("pipeline-state")?.getAttribute("aria-label") || "",
              noNewPipelineState,
              noNewPipelineStateMain,
              noNewPipelineStateLabel,
              stoppedMetricLabel,
              stoppedMetricTitle,
              stoppedProgressBarText,
              ...preservedHomeLiveState,
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
                expression: `Boolean(document.getElementById("daily-driver-summary") && document.getElementById("home-readiness-summary") && document.getElementById("home-active-work-summary") && document.getElementById("command-summary") && typeof window.renderDailyDriverReadiness === "function" && typeof window.mediaPipelineCommandHistory.renderCommandHistoryPayload === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("daily-driver-summary") && document.getElementById("home-readiness-summary") && document.getElementById("home-active-work-summary") && document.getElementById("command-summary") && typeof window.renderDailyDriverReadiness === "function" && typeof window.mediaPipelineCommandHistory.renderCommandHistoryPayload === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Home live-state WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: homeLiveStateScript(),
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


def _run_browser_home_live_state_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView Home live-state smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-home-live-state-payload.json"
        runner_path = tmp / "browser-home-live-state-runner.cjs"
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
        runner_path.write_text(_browser_home_live_state_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Home live-state smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserHomeLiveStateSmoke(unittest.TestCase):
    def test_real_browser_renders_home_live_state_without_mutation_posts(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView Home live-state smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, source, output = _write_fixture_state(root)
            scratch_root = root / "Scratch"
            scratch_root.mkdir(parents=True, exist_ok=True)
            resolved.local_base = scratch_root
            resolved.config_data["LocalBase"] = str(scratch_root)
            resolved.config_data["Outsource"] = str(root / "Outsource")
            resolved.config_data["MinFreeSpaceGB"] = 1
            resolved.config_data["OutsourceMinFreeSpaceGB"] = 1
            media_snapshot = capture_media_no_mutation_snapshot(root)
            command_journal_path = root / "RunLogs" / "local_api_command_history.json"
            _write_command_history(command_journal_path)
            service = DummyWorkflowFacadeService(root)
            progress = {
                "ProgressVersion": 2,
                "Status": "Processing",
                "CurrentStage": "Encoding",
                "CurrentStagePercent": 42.5,
                "CurrentFileDisplay": "Current Fixture.mkv",
                "CurrentFile": str(source),
                "CurrentLibraryId": "anime",
                "CurrentLibraryName": "Anime Library",
                "CurrentLibraryDesignation": "TV",
                "CurrentLibrarySourceRoot": str(source.parent),
                "CurrentLibraryOutputRoot": str(output.parent),
                "CurrentQueueIndex": 2,
                "CurrentQueueTotal": 5,
                "CurrentRoute": "encode",
                "RouteReason": "operator-trust smoke fixture",
                "PushState": "copying",
                "CopyBytesCopied": 268435456,
                "CopyTotalBytes": 536870912,
                "CopyPercent": 50,
                "CopyStartedAt": "2026-05-15T01:04:00Z",
                "CopyUpdatedAt": "2026-05-15T01:04:01Z",
                "PauseRequested": False,
                "StopRequested": False,
                "UpdatedAt": "2026-05-15T01:04:00Z",
            }
            service.snapshot = Snapshot(
                resolved=resolved,
                current_activity="Current activity: Encoding Current Fixture.mkv.",
                status_summary="Status OK",
                log_tail="progress line",
                progress=progress,
                audit_progress=None,
                latest_failure_report=resolved.workspace_root / "failures.txt",
                latest_failure_json=resolved.workspace_root / "failures.json",
                latest_audit_csv=None,
                latest_priority_csv=None,
                pipeline_events=[
                    {
                        "schema_version": "pipeline_event.v1",
                        "event_id": "event-progress-1",
                        "event_type": "job_progress",
                        "timestamp": "2026-05-15T01:04:00Z",
                        "created_at": "2026-05-15T01:04:00Z",
                        "data": {"display_name": "Current Fixture.mkv", "percent": 42.5},
                    }
                ],
            )
            active_jobs = resolved.active_jobs_path or (root / "State" / "ActiveJobs")
            active_jobs.mkdir(parents=True, exist_ok=True)
            (active_jobs / "launch-progress.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-progress",
                        "job_kind": "pipeline",
                        "mode": "continuous",
                        "status": "active",
                        "pid": None,
                        "app_pid": None,
                        "command_line": "pwsh -File Pipeline.ps1",
                        "args": ["pwsh", "-File", "Pipeline.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(root / "RunLogs" / "run.stdout.log"),
                        "stderr_log": str(root / "RunLogs" / "run.stderr.log"),
                        "show_console": False,
                        "metadata": {"source": "browser-home-live-state-smoke"},
                        "launched_at": "2026-05-15T01:00:00Z",
                        "last_update": "2026-05-15T01:04:00Z",
                        "completed_at": "",
                        "return_code": None,
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-home-live-state-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                command_journal_path=command_journal_path,
            )
            watched = {
                source: source.read_bytes(),
                output: output.read_bytes(),
                resolved.queue_snapshot_path: resolved.queue_snapshot_path.read_bytes(),
                resolved.completed_manifest_path: resolved.completed_manifest_path.read_bytes(),
                command_journal_path: command_journal_path.read_bytes(),
            }
            try:
                server.start()
                result = _run_browser_home_live_state_smoke(browser_path=browser_path, url=server.url)
            finally:
                server.stop()

            self.assertTrue(result["ok"])
            browser_result = result["result"]
            self.assertEqual(browser_result["posts"], [])
            self.assertEqual(browser_result["queueCount"], "2 / 5")
            self.assertIn("Rows:", browser_result["queueSnapshot"])
            self.assertIn("Runnable:", browser_result["queueSnapshot"])
            self.assertEqual(browser_result["pipelineStateMain"], "Encoding TV")
            self.assertEqual(browser_result["pipelineStateDetail"], "(cpu fallback)")
            self.assertEqual(browser_result["pipelineStateLabel"], "Encoding TV (cpu fallback)")
            self.assertEqual(browser_result["noNewPipelineStateMain"], "No New Sources")
            self.assertEqual(browser_result["noNewPipelineStateLabel"], "No New Sources")
            self.assertEqual(browser_result["stoppedMetricLabel"], "Failed")
            self.assertIn("not counted as a failed media output", browser_result["stoppedMetricTitle"])
            self.assertIn("Stopped after current", browser_result["stoppedProgressBarText"])
            self.assertIn("Pending Publish", browser_result["stoppedProgressBarText"])
            self.assertIn("No New Sources", browser_result["noNewPipelineState"])
            self.assertNotIn("_", browser_result["pipelineState"])
            self.assertIn("Encoding", browser_result["statePill"])
            self.assertIn("Serial Experiments Lain", browser_result["nextQueue"])
            self.assertIn("S02E01", browser_result["nextQueue"])
            self.assertNotIn("Weird", browser_result["nextQueue"])
            self.assertIn("REMUX", browser_result["nextQueue"])
            self.assertIn("Ready", browser_result["nextQueue"])
            self.assertIn("OK", browser_result["scratchStorage"])
            self.assertIn("1 GB reserve", browser_result["scratchStorage"])
            self.assertIn("OK", browser_result["outputStorage"])
            self.assertIn("1 GB reserve", browser_result["outputStorage"])
            self.assertIn("Daily-driver readiness checklist:", browser_result["dailyDriver"])
            self.assertIn("Anime Library", browser_result["progressDetails"])
            self.assertNotIn("Controls", browser_result["progressDetails"])
            self.assertIn("Current backend stage", browser_result["progressBars"])
            self.assertIn("active", browser_result["progressBars"])
            self.assertIn("42.5%", browser_result["progressBars"])
            self.assertIn("Progress evidence board:", browser_result["progressEvidence"])
            self.assertIn("Checkpoint: ActiveJobs", browser_result["progressEvidenceDetail"])
            self.assertIn("Stage percent: 42.5", browser_result["diagnosticsProgress"])
            self.assertIn("Results: 1", browser_result["commandSummary"])
            self.assertIn("Sample validation:", browser_result["worksheet"])
            validation_log = (resolved.state_root or (root / "State")) / "Validation" / "sample_validation_log.jsonl"
            self.assertFalse(validation_log.exists())
            for path, before in watched.items():
                self.assertEqual(path.read_bytes(), before, path)
            assert_media_no_mutation(self, media_snapshot)


if __name__ == "__main__":
    unittest.main()
