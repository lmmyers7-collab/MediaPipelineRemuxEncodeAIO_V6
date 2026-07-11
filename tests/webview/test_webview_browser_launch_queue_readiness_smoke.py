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


def _write_launch_command_history(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "desktop_command_history.v1",
                "entries": [
                    {
                        "at": "2026-05-15T02:00:00Z",
                        "command": "pipeline.start",
                        "ok": False,
                        "severity": "error",
                        "result": "error",
                        "message": "Start rejected by backend launch preflight in smoke fixture.",
                        "refresh_hint": "snapshot",
                        "request": {
                            "mode": "continuous",
                            "sleep_seconds": 30,
                            "schedule_override": "",
                            "show_config": False,
                            "show_console": False,
                        },
                        "data": {"mode": "continuous", "actual_mode": "continuous"},
                        "warnings": [],
                        "errors": ["Active launch verification requires backend acceptance."],
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


def _write_launch_sample_validation_log(path: Path, *, source: Path, output: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "sample_validation_record.v1",
                "record_id": "launch-smoke-sample-validation-record",
                "created_at": "2026-05-15T03:00:00Z",
                "app_version": "v5-test",
                "shell": "webview",
                "source_path": str(source),
                "output_path": str(output),
                "sample_label": "Serial Experiments Lain - S02E01 - Weird.mkv",
                "sample_category": "h264-remux-safe",
                "proof_strength": "exact-path",
                "operator_decision": "accepted",
                "checks": {
                    "queue_route_checked": True,
                    "ffmpeg_log_checked": True,
                    "subtitle_checked": True,
                    "audio_checked": True,
                    "completed_output_checked": True,
                    "sidecar_manifest_checked": True,
                    "size_growth_checked": True,
                    "pending_publish_checked": True,
                    "diagnostics_checked": True,
                },
                "evidence": {
                    "queue": [{"field": "source", "value": str(source), "strength": "exact"}],
                    "completed": [{"field": "output", "value": str(output), "strength": "exact"}],
                    "pending_publish": [{"field": "pending output", "value": str(output), "strength": "exact"}],
                    "diagnostics": [{"field": "run logs", "value": "remux complete for selected sample", "strength": "advisory"}],
                    "commands": [],
                },
                "operator_notes": "Launch smoke fixture: playback, subtitle, audio, size, diagnostics, and pending-publish proof were reviewed.",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _browser_launch_queue_readiness_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function launchQueueReadinessScript() {
          return `
          (async () => {
            const posts = [];
            const originalApiPost = window.apiPost;
            window.apiPost = async (path, body, options) => {
              posts.push({ path: String(path || ""), body: body || {}, options: options || {} });
              return { ok: false, message: "launch/queue readiness smoke blocks POST routes" };
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
            function requireCompactGate(id, status, fragments) {
              const gate = byId(id);
              if (!gate) throw new Error("missing compact gate " + id);
              const actualStatus = gate.dataset.status || "";
              const actualText = gate.textContent || "";
              const ariaLabel = gate.getAttribute("aria-label") || "";
              if (actualStatus !== status) {
                throw new Error(id + " expected status " + status + ", got " + actualStatus + "\\nText:\\n" + actualText + "\\nAria:\\n" + ariaLabel);
              }
              if (!ariaLabel.includes("gate:")) throw new Error(id + " missing compact gate aria label: " + ariaLabel);
              for (const fragment of fragments) {
                if (!actualText.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actualText);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function setInput(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing input " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function activeLaunchTab() {
              return document.querySelector('[data-page-panel="launch"] .settings-tab-btn[data-launch-tab][aria-selected="true"]')?.dataset.launchTab || "";
            }
            function activeQueueTab() {
              return document.querySelector('[data-page-panel="queue"] .settings-tab-btn[data-queue-tab][aria-selected="true"]')?.dataset.queueTab || "";
            }
            function activeDiagnosticsTab() {
              return document.querySelector('[data-page-panel="diagnostics"] .settings-tab-btn[data-diag-tab][aria-selected="true"]')?.dataset.diagTab || "";
            }
            function requireLaunchTab(tabId) {
              const active = activeLaunchTab();
              if (active !== tabId) throw new Error("expected Launch tab " + tabId + ", got " + active);
              const visiblePanels = Array.from(document.querySelectorAll('[data-page-panel="launch"] > .settings-tab-pane.launch-tab-panel[data-launch-tab-panel].is-active'))
                .map((panel) => panel.dataset.launchTabPanel);
              if (!visiblePanels.length || visiblePanels.some((tab) => tab !== tabId)) {
                throw new Error("Launch tab " + tabId + " has unexpected visible panels: " + JSON.stringify(visiblePanels));
              }
            }
            function clickLaunchTab(tabId) {
              const button = document.querySelector('[data-page-panel="launch"] .settings-tab-btn[data-launch-tab="' + tabId + '"]');
              if (!button) throw new Error("missing Launch tab button " + tabId);
              window.mediaPipelineLaunchView.activateLaunchTab(tabId, { persist: false });
              requireLaunchTab(tabId);
            }
            function requireQueueTab(tabId) {
              const active = activeQueueTab();
              if (active !== tabId) throw new Error("expected Queue tab " + tabId + ", got " + active);
              const visiblePanels = Array.from(document.querySelectorAll('[data-page-panel="queue"] > .settings-tab-pane.queue-tab-panel[data-queue-tab-panel].is-active'))
                .map((panel) => panel.dataset.queueTabPanel);
              if (!visiblePanels.length || visiblePanels.some((tab) => tab !== tabId)) {
                throw new Error("Queue tab " + tabId + " has unexpected visible panels: " + JSON.stringify(visiblePanels));
              }
            }
            function clickQueueTab(tabId) {
              const button = document.querySelector('[data-page-panel="queue"] .settings-tab-btn[data-queue-tab="' + tabId + '"]');
              if (!button) throw new Error("missing Queue tab button " + tabId);
              window.mediaPipelineQueueView.activateQueueTab(tabId, { persist: false });
              requireQueueTab(tabId);
            }
            function requireDiagnosticsReadinessTab() {
              const pageVisible = document.querySelector('[data-page-panel="diagnostics"]')?.classList.contains("is-visible");
              if (!pageVisible) throw new Error("Diagnostics page is not visible");
              const active = activeDiagnosticsTab();
              if (active !== "readiness") throw new Error("expected Diagnostics readiness tab, got " + active);
              const panel = document.querySelector('[data-page-panel="diagnostics"] .settings-tab-pane[data-diag-tab="readiness"]');
              if (!panel?.classList.contains("is-active")) throw new Error("Diagnostics readiness panel is not active");
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 20000;
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
                "close=" + text("close-readiness"),
                "launchReadiness=" + text("launch-readiness-status") + "\\n" + text("launch-readiness"),
                "launchTiming=" + text("launch-timing-status") + "\\n" + text("launch-timing"),
                "scopeReconciliation=" + text("launch-scope-reconciliation-status") + "\\n" + text("launch-scope-reconciliation-summary"),
                "startDecision=" + text("launch-start-decision-status") + "\\n" + text("launch-start-decision-summary"),
                "realMediaProof=" + text("launch-real-media-proof-status") + "\\n" + text("launch-real-media-proof-summary"),
                "sampleExecution=" + text("launch-sample-execution-status") + "\\n" + text("launch-sample-execution-summary"),
                "pilotReadiness=" + text("launch-pilot-readiness-status") + "\\n" + text("launch-pilot-readiness-summary"),
                "backendPreflight=" + text("launch-backend-preflight-status") + "\\n" + text("launch-backend-preflight-summary"),
                "queueDecision=" + text("queue-launch-decision-status") + "\\n" + text("queue-launch-decision-summary"),
                "schedule=" + text("schedule-guidance-status") + "\\n" + text("schedule-guidance"),
                "commandReview=" + text("launch-command-review-status") + "\\n" + text("launch-command-review-summary"),
                "posts=" + JSON.stringify(posts),
              ].join("\\n\\n"));
            }
            [
              "showPage",
              "renderAllLaunchPreflights",
              "renderLaunchScopeReconciliation",
              "launchScopeReconciliationRows",
              "renderLaunchStartDecisionSummary",
              "renderLaunchSampleExecutionChecklist",
              "renderLaunchPilotRunReadiness",
              "refreshLaunchBackendPreflight",
              "renderQueueLaunchDecisionChecklist",
              "queueLaunchDecisionRows",
              "getCommandHistory",
            ].forEach(requireFunction);
            if (typeof window.mediaPipelineCommandHistory?.commandHistoryOwnerPage !== "function") {
              throw new Error("missing mediaPipelineCommandHistory.commandHistoryOwnerPage");
            }
            if (typeof window.mediaPipelineLaunchHistoryView?.renderLaunchCommandHistory !== "function") {
              throw new Error("missing mediaPipelineLaunchHistoryView.renderLaunchCommandHistory");
            }
            if (typeof window.mediaPipelineScheduleView?.renderScheduleTimingTrust !== "function") {
              throw new Error("missing mediaPipelineScheduleView.renderScheduleTimingTrust");
            }
            [
              "launchStartDecisionRows",
              "launchCompactGateRows",
              "renderLaunchCompactGate",
              "launchWorksheetEvidence",
              "launchSampleValidationRecordEvidence",
              "launchPolicyAlignmentQueueIntentEvidence",
              "launchQueueIntentCategoryMatch",
              "launchSampleExecutionRows",
              "launchPilotRunReadinessRows",
              "pipelineLaunchPreflightLines",
            ].forEach((name) => {
              if (typeof window.mediaPipelineLaunchView?.[name] !== "function") {
                throw new Error("missing mediaPipelineLaunchView." + name);
              }
            });
            [
              "rerunQueuePreflightLines",
              "renderRerunQueuePreflight",
            ].forEach((name) => {
              if (typeof window.mediaPipelineCsvRerunWorkflow?.[name] !== "function") {
                throw new Error("missing mediaPipelineCsvRerunWorkflow." + name);
              }
            });

            window.showPage("launch");
            if (typeof window.mediaPipelineLaunchView?.activateLaunchTab !== "function") throw new Error("missing mediaPipelineLaunchView.activateLaunchTab");
            const launchTabLabels = Array.from(document.querySelectorAll('[data-page-panel="launch"] .settings-tab-btn[data-launch-tab]'))
              .map((button) => button.textContent.trim());
            const expectedLaunchTabs = ["Pipeline Processor", "History"];
            if (JSON.stringify(launchTabLabels) !== JSON.stringify(expectedLaunchTabs)) {
              throw new Error("unexpected Launch tab order: " + JSON.stringify(launchTabLabels));
            }
            const launchPanelOrder = Array.from(document.querySelectorAll('[data-page-panel="launch"] > .launch-tab-panel[data-launch-tab-panel]'))
              .map((panel) => panel.dataset.launchTabPanel)
              .filter((tabId, index, all) => all.indexOf(tabId) === index);
            const expectedPanelOrder = ["pipeline", "history"];
            if (JSON.stringify(launchPanelOrder) !== JSON.stringify(expectedPanelOrder)) {
              throw new Error("unexpected Launch panel DOM order: " + JSON.stringify(launchPanelOrder));
            }
            requireLaunchTab("pipeline");
            clickLaunchTab("pipeline");
            setInput("pipeline-start-mode", "continuous");
            setInput("pipeline-start-single-file", "E:\\\\Videos\\\\Scratch\\\\Encoded\\\\TV\\\\Sample Pilot.mkv");
            setInput("pipeline-start-schedule-override", "");
            window.mediaPipelineLaunchView.renderAllLaunchPreflights();
            const compactGateStrip = byId("pipeline-compact-gate-strip");
            const startButton = byId("pipeline-start-button");
            if (!compactGateStrip || !startButton || (compactGateStrip.compareDocumentPosition(startButton) & Node.DOCUMENT_POSITION_PRECEDING)) {
              throw new Error("compact gate strip must render before Start Pipeline");
            }
            window.mediaPipelineLaunchView.renderLaunchCompactGate();
            [
              "pipeline-gate-backend",
              "pipeline-gate-queue",
              "pipeline-gate-settings",
              "pipeline-gate-schedule",
              "pipeline-gate-active",
              "pipeline-gate-last",
            ].forEach((id) => {
              const gate = byId(id);
              if (!gate) throw new Error("missing compact gate " + id);
              if (gate.tagName !== "BUTTON") throw new Error(id + " is not a button");
              const ariaLabel = gate.getAttribute("aria-label") || "";
              if (!ariaLabel.includes("gate:") || !/(OK|Needs Evidence|At Risk|Will Fail|Active)/.test(gate.textContent || "")) {
                throw new Error(id + " missing visible/audible state; aria=" + ariaLabel + "; text=" + gate.textContent);
              }
            });
            byId("pipeline-gate-backend").click();
            requireText("pipeline-compact-gate-detail", ["Backend:", "Opened Diagnostics > Readiness > Backend Preflight", "Backend start remains authoritative."]);
            requireDiagnosticsReadinessTab();
            if (!document.querySelector("#launch-backend-preflight-refresh-button.is-attention-target, #launch-backend-preflight-rows tr.is-attention-target")) {
              throw new Error("Backend compact gate did not highlight backend preflight evidence");
            }
            window.showPage("launch");
            clickLaunchTab("pipeline");
            byId("pipeline-gate-settings").click();
            requireText("pipeline-compact-gate-detail", ["Settings:", "Opened Diagnostics > Readiness > Settings Check", "Backend start remains authoritative."]);
            requireDiagnosticsReadinessTab();
            window.showPage("launch");
            clickLaunchTab("pipeline");
            const singleFileRequest = window.mediaPipelineLaunchView.collectPipelineStartRequest();
            if (singleFileRequest.single_file !== "E:\\\\Videos\\\\Scratch\\\\Encoded\\\\TV\\\\Sample Pilot.mkv") {
              throw new Error("Launch single-file request was not collected correctly: " + JSON.stringify(singleFileRequest));
            }
            if (!text("pipeline-launch-preflight").includes("Single-file launch: WebView submits the path only")) {
              throw new Error("Launch preflight did not describe single-file backend boundary:\\n" + text("pipeline-launch-preflight"));
            }
            await waitFor(
              () => text("close-readiness").includes("Close:")
                && text("launch-readiness").includes("Backend snapshot: ok")
                && text("launch-timing").includes("Launch timing trust:")
                && text("launch-scope-reconciliation-summary").includes("Launch scope reconciliation:")
                && text("launch-start-decision-summary").includes("Launch start decision summary:")
                && text("launch-real-media-proof-summary").includes("Launch real-media sample proof handoff:")
                && text("launch-real-media-proof-summary").includes("matches=1")
                && text("launch-real-media-proof-summary").includes("historical accepted category records=1")
                && text("launch-sample-execution-summary").includes("Launch sample execution checklist:")
                && text("launch-pilot-readiness-summary").includes("Launch pilot run readiness:")
                && text("launch-backend-preflight-summary").includes("backend preflight")
                && !text("launch-backend-preflight-status").includes("Loading")
                && text("queue-decision-summary").includes("Queue decision header:")
                && text("queue-attention-summary").includes("Attention required:")
                && text("queue-launch-decision-summary").includes("Queue-to-Launch handoff:")
                && text("launch-command-review-summary").includes("Launch command review:")
                && text("schedule-guidance").includes("Backend launch gating remains the source of truth."),
              "Launch/Queue/Schedule readiness panels",
            );

            requireText("close-readiness", ["Close:"]);
            requireText("launch-readiness", [
              "Backend snapshot: ok",
              "Pipeline state:",
              "Close readiness:",
              "Saved settings:",
              "Schedule:",
              "Backend launch locking and gating remain the source of truth.",
            ]);
            requireText("launch-timing", [
              "Launch timing trust:",
              "Selected mode: Continuous",
              "Close readiness:",
              "Schedule enforcement:",
              "Mutation guardrail: this Launch timing panel is read-only",
            ]);
            requireText("launch-settings-intent-summary", [
              "Saved settings vs launch intent checklist:",
              "Decision rule: Launch uses saved backend settings",
              "First action:",
              "Mutation guardrail: this checklist is read-only",
            ]);
            requireText("launch-scope-reconciliation-summary", [
              "Launch scope reconciliation:",
              "Decision context: these read-only signals explain launch posture; backend start remains authoritative",
              "Suggested action:",
              "Mutation guardrail: this reconciliation is read-only",
            ]);
            requireTableText("launch-scope-reconciliation-rows", [
              "Backend authority",
              "Queue payload",
              "Queue tab display state",
              "Queue-to-Launch Handoff",
              "Backend Launch Preflight",
              "Recent Launch command",
            ]);
            requireText("launch-scope-reconciliation-detail", [
              "Launch scope reconciliation:",
              "Signal:",
              "Safe next step:",
              "Guardrail: backend start routes remain authoritative",
            ]);
            requireText("launch-start-decision-summary", [
              "Launch start decision summary:",
              "Decision context: treat these signals as advisory evidence for Start; backend start remains authoritative",
              "Suggested action:",
              "Mutation guardrail: this summary is read-only",
            ]);
            requireTableText("launch-start-decision-rows", [
              "Launch readiness",
              "Backend preflight",
              "Queue-to-Launch handoff",
              "Settings / policy",
              "Real-media proof",
              "Pilot category coverage",
              "Start boundary",
            ]);
            const backendDecisionRow = Array.from(document.querySelectorAll("#launch-start-decision-rows tr"))
              .find((row) => row.textContent.includes("Backend preflight"));
            if (!backendDecisionRow) throw new Error("missing Launch start decision backend preflight row");
            backendDecisionRow.click();
            requireText("launch-start-decision-detail", [
              "Launch start decision summary:",
              "Signal: Backend preflight",
              "Operator action:",
              "backend preflight",
              "Guardrail: backend-owned start routes remain the only path",
            ]);
            requireText("launch-real-media-proof-summary", [
              "Launch real-media sample proof handoff:",
              "Home Real-Media Validation Worksheet",
              "Generated worksheet evidence:",
              "matches=1",
              "Sample Validation record evidence:",
              "Pilot category coverage:",
              "current category records=0",
              "historical accepted category records=1",
              "Saved policy vs Queue route:",
              "visible category signals=",
              "Pre-run boundary: Launch can prove selected intent",
              "daily-driver trust still requires post-run output",
              "Mutation guardrail: this Launch proof handoff is read-only",
            ]);
            requireTableText("launch-real-media-proof-rows", [
              "Sample identity",
              "Generated worksheet evidence",
              "Sample Validation record evidence",
              "Pilot category coverage",
              "Saved policy vs Queue route",
              "Completed output and size proof",
              "Pending publish and final destination",
              "Launch proof boundary",
            ]);
            const worksheetProofRow = Array.from(document.querySelectorAll("#launch-real-media-proof-rows tr"))
              .find((row) => row.textContent.includes("Generated worksheet evidence"));
            if (!worksheetProofRow) throw new Error("missing Launch real-media generated worksheet evidence row");
            worksheetProofRow.click();
            requireText("launch-real-media-proof-detail", [
              "Launch real-media sample proof handoff:",
              "Checkpoint: Generated worksheet evidence",
              "Selected sample: Serial Experiments Lain",
              "Matching worksheet runs: 1",
              "First matching worksheet detail:",
              "Worksheet: real_media_validation_fixture.md",
              "Selected sample match: yes",
              "Read-only generated worksheet evidence",
            ]);
            const worksheetProofDetail = text("launch-real-media-proof-detail");
            const recordProofRow = Array.from(document.querySelectorAll("#launch-real-media-proof-rows tr"))
              .find((row) => row.textContent.includes("Sample Validation record evidence"));
            if (!recordProofRow) throw new Error("missing Launch real-media Sample Validation record evidence row");
            recordProofRow.click();
            requireText("launch-real-media-proof-detail", [
              "Launch real-media sample proof handoff:",
              "Checkpoint: Sample Validation record evidence",
              "Selected sample: Serial Experiments Lain",
              "Matching records: 1",
              "First matching validation record detail:",
              "Record: launch-smoke-sample-validation-record",
              "Decision: accepted",
              "Current evidence status:",
              "Read-only sample validation history",
            ]);
            const recordProofDetail = text("launch-real-media-proof-detail");
            const completedProofRow = Array.from(document.querySelectorAll("#launch-real-media-proof-rows tr"))
              .find((row) => row.textContent.includes("Completed output and size proof"));
            if (!completedProofRow) throw new Error("missing Launch real-media Completed proof row");
            completedProofRow.click();
            requireText("launch-real-media-proof-detail", [
              "Launch real-media sample proof handoff:",
              "Checkpoint: Completed output and size proof",
              "Operator proof:",
              "Completed for output/sidecar/size proof",
              "pre-run intent context",
            ]);
            const completedProofDetail = text("launch-real-media-proof-detail");
            const categoryProofRow = Array.from(document.querySelectorAll("#launch-real-media-proof-rows tr"))
              .find((row) => row.textContent.includes("Pilot category coverage"));
            if (!categoryProofRow) throw new Error("missing Launch real-media Pilot category coverage row");
            categoryProofRow.click();
            requireText("launch-real-media-proof-detail", [
              "Launch real-media sample proof handoff:",
              "Checkpoint: Pilot category coverage",
              "Pilot category coverage:",
              "Current category record matches: 0",
              "Accepted/historical category record matches: 1",
              "Review category records: 1",
              "H.264 remux/direct-play copy",
              "Read-only representative sample-set guidance",
            ]);
            const categoryProofDetail = text("launch-real-media-proof-detail");
            const policyProofRow = Array.from(document.querySelectorAll("#launch-real-media-proof-rows tr"))
              .find((row) => row.textContent.includes("Saved policy vs Queue route"));
            if (!policyProofRow) throw new Error("missing Launch real-media saved policy vs Queue route row");
            policyProofRow.click();
            requireText("launch-real-media-proof-detail", [
              "Launch real-media sample proof handoff:",
              "Checkpoint: Saved policy vs Queue route",
              "Saved policy vs Queue route evidence packet:",
              "Policy alignment status:",
              "Representative Queue intent:",
              "Category comparison rows:",
              "H.264 remux/direct-play copy",
              "queue signal=visible-route-signal",
              "Advisory boundary: queue-route matching uses loaded route/status text only",
              "Read-only real-media policy alignment",
            ]);
            const policyProofDetail = text("launch-real-media-proof-detail");
            const staleCategoryContext = {
              sampleValidation: {
                sample_set_guide: {
                  operator_status: "review",
                  required_ready_count: 0,
                  required_count: 1,
                  current_accepted_record_count: 0,
                  worksheet_sample_count: 1,
                  safe_next_action: "Accepted category records exist, but current backend reconciliation is not clean.",
                  guardrail: "Read-only representative sample-set guidance.",
                  rows: [
                    {
                      category_key: "h264-remux-safe",
                      category: "H.264 remux/direct-play copy",
                      status: "review",
                      severity: "warning",
                      required: true,
                      accepted_record_match_count: 1,
                      current_record_match_count: 0,
                      stale_record_match_count: 1,
                      review_record_match_count: 0,
                      worksheet_sample_count: 1,
                      safe_next_action: "Re-check Queue, Completed, Pending Publish, and Diagnostics proof before using this category.",
                      guardrail: "Read-only sample-set row.",
                    },
                  ],
                },
              },
            };
            const staleCategoryCoverage = window.mediaPipelineLaunchView.launchSampleSetCoverageEvidence(staleCategoryContext);
            if (staleCategoryCoverage.posture !== "warning") {
              throw new Error("stale category coverage should be warning, saw " + staleCategoryCoverage.posture);
            }
            [
              "current category records=0",
              "historical accepted category records=1",
              "stale=1",
            ].forEach((fragment) => {
              if (!staleCategoryCoverage.evidence.includes(fragment)) {
                throw new Error("stale category coverage evidence missing " + fragment + "\\n" + staleCategoryCoverage.evidence);
              }
            });
            const staleCategoryDetail = staleCategoryCoverage.detail.join("\\n");
            [
              "Current category record matches: 0",
              "Accepted/historical category record matches: 1",
              "Stale category records: 1",
              "H.264 remux/direct-play copy: review",
              "accepted=1; current=0; stale=1",
            ].forEach((fragment) => {
              if (!staleCategoryDetail.includes(fragment)) {
                throw new Error("stale category coverage detail missing " + fragment + "\\n" + staleCategoryDetail);
              }
            });
            requireText("launch-sample-execution-summary", [
              "Launch sample execution checklist:",
              "Home's backend-authored operator sample execution checklist",
              "Execution rows:",
              "Pilot context: before-launch and backend-launch-boundary rows explain sample-validation evidence",
              "Mutation guardrail: this Launch checklist is read-only",
            ]);
            requireTableText("launch-sample-execution-rows", [
              "Before Launch",
              "Backend Launch Boundary",
              "Post-run Completed Proof",
              "Post-run Diagnostics Proof",
              "Evidence Record",
            ]);
            const launchExecutionCompletedRow = Array.from(document.querySelectorAll("#launch-sample-execution-rows tr"))
              .find((row) => row.textContent.includes("Post-run Completed Proof"));
            if (!launchExecutionCompletedRow) throw new Error("missing Launch sample execution Completed proof row");
            launchExecutionCompletedRow.click();
            requireText("launch-sample-execution-detail", [
              "Launch sample execution checklist:",
              "Phase: Post-run Completed Proof",
              "Owner page: Completed",
              "Current backend evidence:",
              "Operator proof:",
              "Unsafe if ignored:",
              "Launch boundary: this row does not start processing",
            ]);
            requireText("launch-pilot-readiness-summary", [
              "Launch pilot run readiness:",
              "selected Queue sample, saved Settings policy, backend preflight, pilot category, pending-publish posture, and post-run proof plan",
              "First action:",
              "Mutation guardrail: this pilot readiness panel is read-only",
            ]);
            requireTableText("launch-pilot-readiness-rows", [
              "Selected Queue sample",
              "Saved Settings policy",
              "Saved policy vs Queue route",
              "Backend preflight",
              "Pilot category coverage",
              "Pending Publish posture",
              "Post-run proof plan",
              "Mutation boundary",
            ]);
            const pilotCategoryRow = Array.from(document.querySelectorAll("#launch-pilot-readiness-rows tr"))
              .find((row) => row.textContent.includes("Pilot category coverage"));
            if (!pilotCategoryRow) throw new Error("missing Launch pilot readiness category row");
            pilotCategoryRow.click();
            requireText("launch-pilot-readiness-detail", [
              "Launch pilot run readiness:",
              "Checkpoint: Pilot category coverage",
              "Current category record matches: 0",
              "Accepted/historical category record matches: 1",
              "Guardrail: backend-owned launch, publish, settings, rename, and filesystem operations remain the only mutation paths.",
            ]);
            const pilotCategoryDetail = text("launch-pilot-readiness-detail");
            const pilotPolicyRow = Array.from(document.querySelectorAll("#launch-pilot-readiness-rows tr"))
              .find((row) => row.textContent.includes("Saved policy vs Queue route"));
            if (!pilotPolicyRow) throw new Error("missing Launch pilot readiness saved policy vs Queue route row");
            pilotPolicyRow.click();
            requireText("launch-pilot-readiness-detail", [
              "Launch pilot run readiness:",
              "Checkpoint: Saved policy vs Queue route",
              "Saved policy vs Queue route evidence packet:",
              "Representative Queue intent:",
              "visible category signals=",
              "Category comparison rows:",
              "Advisory boundary: queue-route matching uses loaded route/status text only",
            ]);
            const pilotPolicyDetail = text("launch-pilot-readiness-detail");
            const backendPreflightRefreshButton = byId("launch-backend-preflight-refresh-button");
            if (!backendPreflightRefreshButton) throw new Error("missing Launch Backend Preflight refresh button");
            backendPreflightRefreshButton.click();
            await waitFor(
              () => tableText("launch-backend-preflight-rows").includes("Pipeline"),
              "explicit Launch Backend Preflight refresh rows"
            );
            requireText("launch-backend-preflight-summary", [
              "Pipeline backend preflight:",
              "Source: GET /api/launch/preflight",
              "Status scope: active targets only",
              "active requests=1",
              "skipped inactive=0",
            ]);
            requireTableText("launch-backend-preflight-rows", [
              "Pipeline",
              "Process launch lock",
              "Active work guard",
            ]);
            const originalBackendPreflightPayloads = window.mediaPipelineLaunchView.getLastLaunchBackendPreflightPayloads();
            const originalPipelinePreflight = originalBackendPreflightPayloads.find((payload) => String(payload?.target || "").toLowerCase() === "pipeline");
            if (!originalPipelinePreflight) throw new Error("missing pipeline backend preflight payload for gate smoke");
            const idleSnapshot = { pipeline_state: "idle" };
            const idleCloseReadiness = { safe_to_close: true, active_work: false, state: "idle" };
            const validateStartButton = byId("pipeline-start-button");
            setInput("pipeline-start-mode", "once");
            window.mediaPipelineLaunchView.renderLaunchBackendPreflight([]);
            window.mediaPipelineLaunchView.updateLaunchCommandButtonStates(idleSnapshot, idleCloseReadiness);
            if (validateStartButton.disabled || !validateStartButton.title.includes("can submit without cached Backend Preflight")) {
              throw new Error("Run Once should submit without cached Backend Preflight; disabled=" + validateStartButton.disabled + "; title=" + validateStartButton.title);
            }
            requireText("pipeline-start-disabled-reason", ["can submit without cached Backend Preflight"]);
            window.mediaPipelineLaunchView.renderLaunchCompactGate();
            requireCompactGate("pipeline-gate-backend", "unknown", ["Backend", "Needs Evidence", "Refresh"]);
            byId("pipeline-gate-backend").click();
            requireText("pipeline-compact-gate-detail", ["Backend", "No cached Backend Preflight", "routine Start can still submit"]);
            setInput("pipeline-start-mode", "continuous");
            const reviewPipelinePreflight = {
              ...originalPipelinePreflight,
              status: "review",
              can_request_start: true,
              request: window.mediaPipelineLaunchView.collectPipelineStartRequest(),
              checks: [
                {
                  key: "browser-smoke-risk",
                  label: "Browser smoke risk",
                  status: "review",
                  evidence: "Injected cached Backend Preflight review for UI gate smoke.",
                  action: "Review injected Backend Preflight risk.",
                },
              ],
            };
            const reviewPreflightPayloads = [
              reviewPipelinePreflight,
              ...originalBackendPreflightPayloads.filter((payload) => String(payload?.target || "").toLowerCase() !== "pipeline"),
            ];
            window.mediaPipelineLaunchView.renderLaunchBackendPreflight(reviewPreflightPayloads);
            window.mediaPipelineLaunchView.updateLaunchCommandButtonStates(idleSnapshot, idleCloseReadiness);
            window.mediaPipelineLaunchView.renderLaunchCompactGate();
            requireCompactGate("pipeline-gate-backend", "warning", ["Backend", "At Risk"]);
            byId("pipeline-gate-backend").click();
            requireDiagnosticsReadinessTab();
            requireText("launch-backend-preflight-detail", [
              "Browser smoke risk",
              "Injected cached Backend Preflight review",
              "Review injected Backend Preflight risk.",
            ]);
            const readyPipelinePreflight = {
              ...originalPipelinePreflight,
              status: "ready",
              can_request_start: true,
              request: window.mediaPipelineLaunchView.collectPipelineStartRequest(),
              checks: [
                {
                  key: "browser-smoke-ready",
                  label: "Browser smoke ready",
                  status: "ready",
                  evidence: "Injected cached Backend Preflight ready check for UI gate smoke.",
                  action: "No action.",
                },
              ],
            };
            const readyPreflightPayloads = [
              readyPipelinePreflight,
              ...originalBackendPreflightPayloads.filter((payload) => String(payload?.target || "").toLowerCase() !== "pipeline"),
            ];
            window.mediaPipelineLaunchView.renderLaunchBackendPreflight(readyPreflightPayloads);
            window.mediaPipelineLaunchView.updateLaunchCommandButtonStates(idleSnapshot, idleCloseReadiness);
            window.mediaPipelineLaunchView.renderLaunchCompactGate();
            requireCompactGate("pipeline-gate-backend", "ready", ["Backend", "OK"]);
            const blockedPipelinePreflight = {
              ...originalPipelinePreflight,
              status: "blocked",
              can_request_start: false,
              request: window.mediaPipelineLaunchView.collectPipelineStartRequest(),
              checks: [
                {
                  key: "browser-smoke-blocker",
                  label: "Browser smoke blocker",
                  status: "blocked",
                  evidence: "Injected cached Backend Preflight blocker for UI gate smoke.",
                  action: "Resolve injected Backend Preflight blocker.",
                },
              ],
            };
            const blockedPreflightPayloads = [
              blockedPipelinePreflight,
              ...originalBackendPreflightPayloads.filter((payload) => String(payload?.target || "").toLowerCase() !== "pipeline"),
            ];
            window.mediaPipelineLaunchView.renderLaunchBackendPreflight(blockedPreflightPayloads);
            window.mediaPipelineLaunchView.updateLaunchCommandButtonStates(idleSnapshot, idleCloseReadiness);
            window.mediaPipelineLaunchView.renderLaunchCompactGate();
            requireText("pipeline-compact-gate-status", ["Will Fail"]);
            requireCompactGate("pipeline-gate-backend", "blocked", ["Backend", "Will Fail", "Blocked"]);
            requireText("pipeline-compact-gate-detail", ["Backend", "Backend start remains authoritative."]);
            byId("pipeline-gate-backend").click();
            requireText("pipeline-compact-gate-detail", ["Backend", "Opened Diagnostics > Readiness > Backend Preflight", "Backend start remains authoritative."]);
            requireDiagnosticsReadinessTab();
            requireText("launch-backend-preflight-detail", [
              "Browser smoke blocker",
              "Injected cached Backend Preflight blocker",
              "Resolve injected Backend Preflight blocker.",
            ]);
            const selectedBackendBlocker = document.querySelector("#launch-backend-preflight-rows tr.is-selected.is-attention-target");
            if (!selectedBackendBlocker || !selectedBackendBlocker.textContent.includes("Browser smoke blocker")) {
              throw new Error("Backend compact gate did not select and highlight the injected blocker row");
            }
            const launchGateChecks = [
              ["pipeline-start-button", "Browser smoke blocker"],
              ["pending-drain-button", "Refresh Backend Preflight"],
            ];
            launchGateChecks.forEach(([id, titleFragment]) => {
              const button = byId(id);
              if (!button) throw new Error("missing launch gate button " + id);
              if (!button.disabled || !button.title.includes(titleFragment)) {
                throw new Error(id + " did not expose blocked launch gate title; disabled=" + button.disabled + "; title=" + button.title);
              }
            });
            ["rerun-start-button"].forEach((id) => {
              const button = byId(id);
              if (!button) throw new Error("missing launch gate button " + id);
              if (button.title.includes("Browser smoke blocker")) {
                throw new Error(id + " should not inherit pipeline-only blocker title: " + button.title);
              }
            });
            window.mediaPipelineLaunchView.renderLaunchBackendPreflight(originalBackendPreflightPayloads);
            window.mediaPipelineLaunchView.updateLaunchCommandButtonStates();
            window.mediaPipelineLaunchView.renderLaunchCompactGate();
            requireCompactGate("pipeline-gate-last", "ready", ["Last", "OK", "No issue"]);
            byId("pipeline-gate-last").click();
            requireText("pipeline-compact-gate-detail", [
              "Last: OK",
              "Recent launch history is visible",
              "Backend start remains authoritative.",
            ]);
            clickLaunchTab("pipeline");
            requireText("launch-command-review-summary", [
              "Launch command review:",
              "Launch commands loaded: 1",
              "Launch commands needing review: 1",
              "First issue: pipeline.start",
              "Guardrail: this panel is read-only",
            ]);
            requireText("launch-command-review-detail", [
              "Launch command review detail:",
              "Command: pipeline.start",
              "Submitted request:",
              "Correlated checklist/preflight context:",
              "Guardrail: backend start routes re-check this state at submission time",
            ]);
            requireText("launch-history", [
              "Last 1 launch command:",
              "Pipeline",
              "Backend launch locking and validation remain the source of truth.",
            ]);

            window.showPage("queue");
            if (typeof window.mediaPipelineQueueView?.activateQueueTab !== "function") throw new Error("missing mediaPipelineQueueView.activateQueueTab");
            const queueTabLabels = Array.from(document.querySelectorAll('[data-page-panel="queue"] .settings-tab-btn[data-queue-tab]'))
              .map((button) => button.textContent.trim());
            const expectedQueueTabs = ["Main Queue", "CSV Rerun"];
            if (JSON.stringify(queueTabLabels) !== JSON.stringify(expectedQueueTabs)) {
              throw new Error("unexpected Queue tab order: " + JSON.stringify(queueTabLabels));
            }
            clickQueueTab("main");
            clickQueueTab("rerun");
            requireText("rerun-mode-policy-note", [
              "Backend owns output proof",
              "verified outputs stay out of the final library",
              "Original source files are never replaced.",
            ]);
            requireText("rerun-state-status-filter", [
              "All statuses",
              "Pending Publish",
              "Replaced / Returned",
            ]);
            requireText("rerun-results-refresh-button", ["Refresh State"]);
            requireText("rerun-stop-after-current-button", ["Stop After Current"]);
            requireText("rerun-open-latest-manifest-button", ["Open Latest Manifest"]);
            requireText("rerun-open-run-logs-button", ["Open Run Logs"]);
            requireText("rerun-open-last-stdout-button", ["Open Last Stdout"]);
            requireText("rerun-open-last-stderr-button", ["Open Last Stderr"]);
            requireText("rerun-open-active-jobs-button", ["Open Active Jobs"]);
            requireText("rerun-show-command-history-button", ["Show Rerun Commands"]);
            await waitFor(
              () => text("rerun-history-summary").includes("CSV rerun queue-state"),
              "CSV rerun backend-owned queue-state summary",
            );
            requireText("rerun-history-summary", [
              "CSV rerun queue-state is backend-owned",
              "/api/rerun/results",
              "not normal /api/pipeline/start queue rows",
            ]);
            requireText("rerun-state-rows", ["No CSV rerun queue-state"]);
            const statePanel = document.querySelector(".rerun-state-panel");
            const historyPanel = document.querySelector(".rerun-history-panel");
            if (!statePanel || !historyPanel) throw new Error("missing rerun state/history panels");
            if (!(statePanel.compareDocumentPosition(historyPanel) & Node.DOCUMENT_POSITION_FOLLOWING)) {
              throw new Error("CSV rerun state panel must render above history panel");
            }
            const rerunStateTable = document.querySelector(".rerun-state-table");
            if (!rerunStateTable) throw new Error("missing CSV rerun state table");
            if (rerunStateTable.textContent.includes("Evidence")) {
              throw new Error("CSV rerun state table should not render a separate Evidence column");
            }
            if (typeof window.mediaPipelineCsvRerunWorkflow?.renderRerunPreview !== "function") {
              throw new Error("missing mediaPipelineCsvRerunWorkflow.renderRerunPreview");
            }
            setInput("rerun-start-csv-path", "C:/Typed/manual-rerun.csv");
            const rerunStartPostsBeforePreview = posts.filter((post) => post.path === "/api/rerun/start").length;
            window.mediaPipelineCsvRerunWorkflow.renderRerunPreview({
              status: "blocked",
              ok: false,
              message: "CSV rerun preview is blocked by row evidence.",
              csv_path: "C:/Typed/manual-rerun.csv",
              destination_mode: "auto_replace_clean_else_pending_review",
              collision_policy: "replace_final",
              execution_mode: "one_at_a_time",
              counts: {
                total_rows: 4,
                enabled_rows: 3,
                disabled_rows: 1,
                effective_scoped_rows: 3,
                blocked_rows: 1,
                blocked_scoped_rows: 1,
                warning_rows: 1,
                duplicate_source_rows: 1,
                missing_source_rows: 1,
              },
              rows: [
                {
                  row_index: 2,
                  status: "blocked",
                  enabled: true,
                  in_scope: true,
                  source_path: "Relative/Paprika (2006).mkv",
                  lookup_title: "Paprika",
                  relative_path: "Anime/Paprika (2006).mkv",
                  issue: "audio-default-policy-mismatch",
                  bucket: "rerun",
                  reason: "duplicate source_path; source file not found",
                  duplicate_source: true,
                  source_missing: true,
                  source_found: false,
                  rerun_rule_label: "Audio Remediation Rule",
                  rerun_rule_reason: "Audio default-policy evidence requires backend rerun policy.",
                  rerun_rule_blocked: true,
                },
                {
                  row_index: 3,
                  status: "warning",
                  enabled: true,
                  in_scope: true,
                  source_path: "C:/Media/Warning.mkv",
                  lookup_title: "Warning Movie",
                  relative_path: "Movies/Warning.mkv",
                  reason: "warning row remains operator-reviewable",
                  warning_reason: "backend warning evidence",
                  rerun_rule_warning: true,
                },
                {
                  row_index: 4,
                  status: "skipped",
                  enabled: false,
                  in_scope: false,
                  source_path: "C:/Media/Disabled.mkv",
                  lookup_title: "Disabled Movie",
                  relative_path: "Movies/Disabled.mkv",
                  reason: "disabled row filtered by backend preview scope",
                },
                {
                  row_index: 5,
                  status: "ready",
                  enabled: true,
                  in_scope: true,
                  source_path: "C:/Media/Ready.mkv",
                  lookup_title: "Ready Movie",
                  relative_path: "Movies/Ready.mkv",
                  reason: "ready for backend rerun command",
                },
              ],
              recent_csvs: [
                { path: "C:/Backend/known-rerun.csv", csv_key: "known", label: "known-rerun.csv" },
              ],
            });
            requireText("rerun-review-header", [
              "blocked",
              "Total Rows",
              "4",
              "Scoped Rows",
              "3",
              "Next Action",
            ]);
            requireText("rerun-lifecycle-summary", [
              "Phase: Preview blocked.",
              "CSV: C:/Typed/manual-rerun.csv.",
              "Preview rows: total 4, scoped 3",
            ]);
            requireText("rerun-lifecycle-detail", [
              "destination Auto replace clean, else Pending Publish",
              "Scoped row count: 3",
              "Safe next action:",
            ]);
            requireText("rerun-preview-rows", [
              "Paprika",
              "Anime/Paprika (2006).mkv",
              "duplicate",
              "missing source",
              "relative source",
              "source not found",
              "rule blocked",
              "rule warning",
              "filtered/skipped",
              "disabled",
              "ready",
              "Rule detail: Audio default-policy evidence",
            ]);
            const identityCell = document.querySelector("#rerun-preview-rows .rerun-preview-identity-cell");
            const categoryCell = document.querySelector("#rerun-preview-rows .rerun-preview-category-cell");
            const destinationCell = document.querySelector("#rerun-preview-rows .rerun-preview-destination-cell");
            const reasonCell = document.querySelector("#rerun-preview-rows .rerun-preview-reason-cell");
            if (!identityCell || identityCell.dataset.label !== "Identity") throw new Error("CSV rerun identity cell is missing a responsive label");
            if (!destinationCell || destinationCell.dataset.label !== "Destination") throw new Error("CSV rerun destination cell is missing a responsive label");
            if (!reasonCell || reasonCell.dataset.label !== "Reason") throw new Error("CSV rerun reason cell is missing a responsive label");
            const previewTable = document.querySelector(".rerun-preview-table");
            const previewPanel = previewTable.closest("[data-queue-tab-panel]");
            const reasonRect = reasonCell.getBoundingClientRect();
            if (reasonRect.width < 220) {
              const tableRect = previewTable.getBoundingClientRect();
              const panelRect = previewPanel.getBoundingClientRect();
              throw new Error("CSV rerun reason column is too narrow: " + JSON.stringify({
                reasonWidth: reasonRect.width,
                tableWidth: tableRect.width,
                panelWidth: panelRect.width,
                innerWidth: window.innerWidth,
                cellWidths: Array.from(reasonCell.parentElement.children).map((cell) => cell.getBoundingClientRect().width),
                cellComputedWidths: Array.from(reasonCell.parentElement.children).map((cell) => getComputedStyle(cell).width),
                cellDisplays: Array.from(reasonCell.parentElement.children).map((cell) => getComputedStyle(cell).display),
                tableDisplay: getComputedStyle(previewTable).display,
                tableMinWidth: getComputedStyle(previewTable).minWidth,
                tableLayout: getComputedStyle(previewTable).tableLayout,
              }));
            }
            if (destinationCell.textContent.includes(" / ")) throw new Error("CSV rerun destination cell should render wrapped destination/execution lines");
            const categoryRight = categoryCell.getBoundingClientRect().right;
            const overflowingCategoryChip = Array.from(categoryCell.querySelectorAll(".rerun-category-chip"))
              .find((chip) => chip.getBoundingClientRect().right > categoryRight + 1);
            if (overflowingCategoryChip) throw new Error("CSV rerun category chip overflowed its table cell: " + overflowingCategoryChip.textContent);
            ["rerun-open-csv-button", "rerun-open-csv-folder-button"].forEach((id) => {
              const button = byId(id);
              if (!button?.disabled) throw new Error(id + " should stay disabled for typed non-candidate CSV paths");
              if (!button.title.includes("Typed CSV paths can be previewed")) throw new Error(id + " missing typed-path open behavior title: " + button.title);
            });
            window.mediaPipelineCsvRerunWorkflow.renderRerunPreview({
              status: "ready",
              ok: true,
              message: "CSV rerun preview parsed.",
              csv_path: "C:/Typed/manual-rerun.csv",
              destination_mode: "review_workspace",
              collision_policy: "suffix",
              execution_mode: "one_at_a_time",
              counts: { total_rows: 1, effective_scoped_rows: 1, blocked_rows: 0, warning_rows: 0 },
              rows: [
                {
                  row_index: 0,
                  status: "ready",
                  enabled: true,
                  in_scope: true,
                  source_path: "C:/Media/Ready.mkv",
                  lookup_title: "Ready Movie",
                  relative_path: "Movies/Ready.mkv",
                  reason: "ready for backend rerun command",
                },
              ],
              recent_csvs: [
                { path: "C:/Typed/manual-rerun.csv", csv_key: "typed-known", label: "manual-rerun.csv" },
              ],
            });
            ["rerun-open-csv-button", "rerun-open-csv-folder-button"].forEach((id) => {
              const button = byId(id);
              if (button?.disabled) throw new Error(id + " should enable for a backend-known CSV candidate");
            });
            const rerunStartPostsAfterPreview = posts.filter((post) => post.path === "/api/rerun/start").length;
            if (rerunStartPostsAfterPreview !== rerunStartPostsBeforePreview) {
              throw new Error("CSV rerun preview rendering posted /api/rerun/start: " + JSON.stringify(posts));
            }
            if (typeof window.mediaPipelineQueueView?.renderRerunResults !== "function") {
              throw new Error("missing mediaPipelineQueueView.renderRerunResults");
            }
            window.mediaPipelineQueueView.renderRerunResults({
              manifests: [],
              queue_state: {
                rows: [
                  {
                    row_key: "browser-smoke-rerun-row",
                    queue_status: "failed",
                    queue_status_label: "Failed",
                    original_source_path: "Paprika(2006).mkv",
                    output_path: "Paprika(2006).rerun.mkv",
                    final_output_path: "\\\\SERVER\\Videos\\Paprika (2006)\\Paprika (2006).mkv",
                    audit_issue_code_list: ["audio-default-policy-mismatch", "vobsub-subtitles-ocr-candidate"],
                    rerun_rule_label: "Subtitle Remediation Rule",
                    rerun_rule_reason: "Issue evidence is subtitle-focused; rerun uses backend subtitle policy.",
                    blocking_reason: "destination policy failed: pending publish destination is already queued",
                  },
                ],
                status_counts: { failed: 1 },
              },
            });
            const audioChip = document.querySelector('.rerun-issue-chip[data-issue-family="audio"]');
            const subtitleChip = document.querySelector('.rerun-issue-chip[data-issue-family="subtitle"]');
            if (!audioChip || !subtitleChip) throw new Error("CSV rerun issue chips did not render expected families");
            requireText("rerun-state-rows", ["Failed", "A", "default policy", "S", "ocr candidate"]);
            const compactStateText = text("rerun-state-rows");
            if (compactStateText.includes("Rule detail") || compactStateText.includes("Rule reason") || compactStateText.includes("destination policy failed")) {
              throw new Error("CSV rerun details leaked into compact state rows");
            }
            audioChip.click();
            requireText("rerun-queue-detail", [
              "Issue: audio-default-policy-mismatch",
              "Family: audio",
              "Rule: Subtitle Remediation Rule",
              "Rule detail: Issue evidence is subtitle-focused",
              "Blocking detail: destination policy failed",
            ]);
            clickQueueTab("main");
            await waitFor(
              () => text("queue-decision-summary").includes("Queue decision header:")
                && text("queue-launch-decision-summary").includes("Queue-to-Launch handoff:"),
              "Queue decision header after page switch",
            );
            requireText("queue-decision-summary", [
              "Queue decision header:",
              "Visible rows after display filters:",
              "Selected for Queue actions:",
              "Backend launch scope is owned by Launch; Queue filters, selected rows, and rendered row caps are not submitted as processing scope.",
            ]);
            requireText("queue-readiness", [
              "Mutation guardrail: backend queue mutation and processing start remain backend-owned commands",
              "local staging controls are not launch scope",
            ]);
            requireText("queue-attention-summary", [
              "Attention required:",
              "Hidden blocked/review rows behind display filters:",
              "Boundary: attention evidence is read-only",
            ]);
            requireText("queue-launch-decision-summary", [
              "Queue-to-Launch handoff:",
              "Decision context: use backend launch preflight",
              "Launch performs authoritative start checks",
              "Mutation guardrail: this handoff cannot launch",
            ]);
            requireText("queue-backend-scope-summary", [
              "Backend launch scope boundary:",
              "Backend start route: /api/pipeline/start",
              "Queue filters, row selection, and rendered table caps are not submitted as processing scope.",
            ]);
            requireTableText("queue-backend-scope-rows", [
              "Backend start authority",
              "Display filter vs launch scope",
              "Selected row",
            ]);
            requireTableText("queue-launch-decision-rows", [
              "Backend launch preflight",
              "Queue payload",
              "Recent launch command",
            ]);
            requireText("queue-launch-decision-detail", [
              "Queue-to-Launch handoff:",
              "Guardrail: only backend Launch routes can start processing",
            ]);
            const queueRefreshButton = document.querySelector("[data-queue-refresh-button]");
            if (!queueRefreshButton) throw new Error("missing Scan Sources button");
            const queueRowsBeforeScan = tableText("queue-rows");
            if (!queueRowsBeforeScan.trim() || queueRowsBeforeScan.includes("No queue loaded")) {
              throw new Error("Queue rows were not loaded before Scan Sources smoke: " + queueRowsBeforeScan);
            }
            queueRefreshButton.click();
            const topbarPrimaryNode = document.querySelector("#activity .activity-primary");
            const topbarPrimary = topbarPrimaryNode && topbarPrimaryNode.textContent ? topbarPrimaryNode.textContent.trim() : "";
            if (topbarPrimary !== "Scanning") {
              throw new Error("Scan Sources did not update topbar activity immediately; got " + topbarPrimary);
            }
            if (!text("queue-source-inventory").includes("Queue source scan requested.")) {
              throw new Error("Scan Sources did not update source inventory status immediately:\\n" + text("queue-source-inventory"));
            }
            requireText("queue-filter-summary", [
              "Queue source scan requested.",
              "filters, launch scope, queue state commands, source files, and processing commands remain backend-owned",
            ]);
            const queueFilterSummary = document.getElementById("queue-filter-summary");
            if (!queueFilterSummary || window.getComputedStyle(queueFilterSummary).display !== "none" || queueFilterSummary.getClientRects().length !== 0) {
              throw new Error("Queue filter summary should keep textContent but stay visually hidden.");
            }
            if (queueRefreshButton.textContent.trim() !== "Scanning...") {
              throw new Error("Scan Sources button did not switch to scanning text; got " + queueRefreshButton.textContent.trim());
            }
            const queueWrap = document.querySelector(".queue-table-wrap");
            const loadingScreen = document.getElementById("queue-loading-screen");
            if (!queueWrap || queueWrap.dataset.queueLoading !== "true" || !queueWrap.classList.contains("is-queue-loading")) {
              throw new Error("Scan Sources did not mark the queue with loading state.");
            }
            if (!loadingScreen || loadingScreen.hidden) {
              throw new Error("Queue loading screen was not visible after Scan Sources.");
            }
            requireText("queue-loading-status", [
              "Scanning configured source roots",
              "previous backend snapshot",
              "No media mutation has been submitted",
            ]);
            const queueTableLegend = byId("queue-table-legend");
            if (!queueTableLegend || !queueTableLegend.hidden || queueTableLegend.textContent.trim()) {
              throw new Error("Queue table legend should stay hidden during Scan Sources: " + (queueTableLegend?.textContent || ""));
            }
            const loadingRowsText = tableText("queue-rows");
            if (!loadingRowsText.includes("Serial Experiments Lain") || loadingRowsText.includes("Current queue rows are hidden")) {
              throw new Error("Queue table body did not keep previous backend rows visible during loading: " + loadingRowsText);
            }
            await waitFor(
              () => {
                const button = document.querySelector("[data-queue-refresh-button]");
                const wrap = document.querySelector(".queue-table-wrap");
                return Boolean(button && !button.hasAttribute("aria-busy") && wrap && wrap.dataset.queueLoading !== "true");
              },
              "Queue refresh completion",
            );
            if (queueWrap.classList.contains("is-queue-loading") || !loadingScreen.hidden) {
              throw new Error("Queue loading screen did not clear after refreshed queue render.");
            }

            window.showPage("schedule");
            await waitFor(
              () => text("schedule-guidance").includes("Backend launch gating remains the source of truth.")
                && text("schedule-timing").includes("Schedule timing trust:"),
              "Schedule guidance after page switch",
            );
            requireText("schedule-guidance", [
              "Current state:",
              "Backend continuous watcher:",
              "Pipeline launch guidance:",
              "Backend launch gating remains the source of truth.",
            ]);
            requireText("schedule-timing", [
              "Schedule timing trust:",
              "Selected pipeline mode: Continuous",
              "Selected schedule override:",
              "Backend continuous watcher:",
              "Mutation guardrail: this trust panel is read-only",
            ]);

            const history = window.getCommandHistory();
            const launchEntry = history.find((entry) => entry.command === "pipeline.start" || entry.raw?.command === "pipeline.start");
            if (!launchEntry) throw new Error("pipeline.start command history entry was not loaded");
            const owner = window.mediaPipelineCommandHistory.commandHistoryOwnerPage(launchEntry);
            if (owner !== "Launch") throw new Error("pipeline.start owner should be Launch, got " + owner);
            const scanPosts = posts.filter((post) => post.path === "/api/queue/scan");
            const unexpectedPosts = posts.filter((post) => !["/api/queue/scan", "/api/ui-preferences"].includes(post.path));
            if (scanPosts.length !== 1) throw new Error("Scan Sources should post exactly one backend queue scan command: " + JSON.stringify(posts));
            if (scanPosts[0].body.mode !== "inventory_then_curate" || scanPosts[0].body.scope !== "all" || scanPosts[0].body.force !== true) {
              throw new Error("Scan Sources posted unexpected scan payload: " + JSON.stringify(scanPosts[0]));
            }
            if (unexpectedPosts.length) throw new Error("Launch/Queue readiness render posted unexpected routes: " + JSON.stringify(unexpectedPosts));
            window.apiPost = originalApiPost;
            return {
              ok: true,
              posts,
              singleFileRequest,
              launchPreflight: text("pipeline-launch-preflight"),
              close: text("close-readiness"),
              launchReadiness: text("launch-readiness"),
              scopeReconciliation: text("launch-scope-reconciliation-summary"),
              startDecision: text("launch-start-decision-summary"),
              startDecisionDetail: text("launch-start-decision-detail"),
              realMediaProof: text("launch-real-media-proof-summary"),
              realMediaProofDetail: categoryProofDetail,
              policyProofDetail,
              completedProofDetail,
              worksheetProofDetail,
              recordProofDetail,
              sampleExecution: text("launch-sample-execution-summary"),
              sampleExecutionDetail: text("launch-sample-execution-detail"),
              pilotReadiness: text("launch-pilot-readiness-summary"),
              pilotReadinessDetail: pilotCategoryDetail,
              pilotPolicyDetail,
              backendPreflight: text("launch-backend-preflight-summary"),
              queueDecision: text("queue-launch-decision-summary"),
              scheduleGuidance: text("schedule-guidance"),
              commandReview: text("launch-command-review-summary"),
              launchActiveTab: activeLaunchTab(),
              diagnosticsActiveTab: activeDiagnosticsTab(),
              historyOwner: owner,
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
            "--window-size=1600,1000",
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
            await client.send("Emulation.setDeviceMetricsOverride", {
              width: 1600,
              height: 1000,
              deviceScaleFactor: 1,
              mobile: false,
            });
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.getElementById("pipeline-compact-gate-strip") && document.getElementById("launch-backend-preflight-summary") && document.getElementById("launch-scope-reconciliation-summary") && document.getElementById("launch-start-decision-summary") && document.getElementById("launch-real-media-proof-summary") && document.getElementById("launch-sample-execution-summary") && document.getElementById("launch-pilot-readiness-summary") && document.getElementById("queue-launch-decision-summary") && document.getElementById("schedule-guidance") && document.getElementById("close-readiness") && typeof window.mediaPipelineLaunchView.activateLaunchTab === "function" && typeof window.mediaPipelineLaunchView.renderAllLaunchPreflights === "function" && typeof window.mediaPipelineLaunchView.renderLaunchCompactGate === "function" && typeof window.mediaPipelineLaunchView.renderLaunchScopeReconciliation === "function" && typeof window.mediaPipelineLaunchView.renderLaunchStartDecisionSummary === "function" && typeof window.mediaPipelineLaunchView.renderLaunchRealMediaProofHandoff === "function" && typeof window.mediaPipelineLaunchView.renderLaunchSampleExecutionChecklist === "function" && typeof window.mediaPipelineLaunchView.renderLaunchPilotRunReadiness === "function" && typeof window.queueLaunchDecisionRows === "function" && typeof window.mediaPipelineCommandHistory?.commandHistoryOwnerPage === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("pipeline-compact-gate-strip") && document.getElementById("launch-backend-preflight-summary") && document.getElementById("launch-scope-reconciliation-summary") && document.getElementById("launch-start-decision-summary") && document.getElementById("launch-real-media-proof-summary") && document.getElementById("launch-sample-execution-summary") && document.getElementById("launch-pilot-readiness-summary") && document.getElementById("queue-launch-decision-summary") && document.getElementById("schedule-guidance") && document.getElementById("close-readiness") && typeof window.mediaPipelineLaunchView.activateLaunchTab === "function" && typeof window.mediaPipelineLaunchView.renderAllLaunchPreflights === "function" && typeof window.mediaPipelineLaunchView.renderLaunchCompactGate === "function" && typeof window.mediaPipelineLaunchView.renderLaunchScopeReconciliation === "function" && typeof window.mediaPipelineLaunchView.renderLaunchStartDecisionSummary === "function" && typeof window.mediaPipelineLaunchView.renderLaunchRealMediaProofHandoff === "function" && typeof window.mediaPipelineLaunchView.renderLaunchSampleExecutionChecklist === "function" && typeof window.mediaPipelineLaunchView.renderLaunchPilotRunReadiness === "function" && typeof window.queueLaunchDecisionRows === "function" && typeof window.mediaPipelineCommandHistory?.commandHistoryOwnerPage === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Launch/Queue readiness WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: launchQueueReadinessScript(),
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


def _run_browser_launch_queue_readiness_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView Launch/Queue readiness smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-launch-queue-readiness-payload.json"
        runner_path = tmp / "browser-launch-queue-readiness-runner.cjs"
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
        runner_path.write_text(_browser_launch_queue_readiness_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Launch/Queue readiness smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=75,
        )


def _browser_pipeline_start_click_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function pipelineStartClickScript() {
          return `
          (async () => {
            const posts = [];
            const originalApiPost = window.apiPost;
            window.apiPost = async (path, body, options) => {
              const result = await originalApiPost(path, body, options);
              posts.push({
                path: String(path || ""),
                body: body || {},
                command: result?.command || "",
                ok: result?.ok === true,
                severity: result?.severity || "",
                message: result?.message || "",
              });
              return result;
            };
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function setInput(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing input " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 20000;
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
                "launchStatus=" + text("pipeline-launch-status"),
                "launchDetail=" + text("pipeline-launch-detail"),
                "backendPreflight=" + text("launch-backend-preflight-summary"),
                "disabledReason=" + text("pipeline-start-disabled-reason"),
                "posts=" + JSON.stringify(posts),
              ].join("\\n\\n"));
            }
            try {
              window.showPage("launch");
              window.mediaPipelineLaunchView.activateLaunchTab("pipeline", { persist: false });
              setInput("pipeline-start-mode", "once");
              setInput("pipeline-start-single-file", "");
              setInput("pipeline-start-sleep", "3");
              setInput("pipeline-start-schedule-override", "");
              await window.mediaPipelineLaunchView.refreshLaunchBackendPreflight();
              await waitFor(
                () => text("launch-backend-preflight-summary").includes("Pipeline backend preflight"),
                "pipeline backend preflight render"
              );
              window.mediaPipelineLaunchView.updateLaunchCommandButtonStates(
                { pipeline_state: "idle" },
                { safe_to_close: true, active_work: false, state: "idle" }
              );
              await waitFor(
                () => {
                  const button = byId("pipeline-start-button");
                  return Boolean(button && !button.disabled);
                },
                "enabled pipeline start button"
              );
              byId("pipeline-start-button").click();
              await waitFor(
                () => posts.some((post) => post.path === "/api/pipeline/start"),
                "pipeline start POST"
              );
              const launchPost = posts.find((post) => post.path === "/api/pipeline/start");
              if (!launchPost.ok || launchPost.command !== "pipeline.start") {
                throw new Error("pipeline start POST did not return command success: " + JSON.stringify(launchPost));
              }
              return {
                ok: true,
                posts,
                launchPost,
                launchStatus: text("pipeline-launch-status"),
                launchDetail: text("pipeline-launch-detail"),
                disabledReason: text("pipeline-start-disabled-reason"),
              };
            } finally {
              window.apiPost = originalApiPost;
            }
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
            const readyExpression = `Boolean(document.getElementById("pipeline-start-button") && typeof window.apiPost === "function" && typeof window.showPage === "function" && typeof window.mediaPipelineLaunchView?.activateLaunchTab === "function" && typeof window.mediaPipelineLaunchView?.refreshLaunchBackendPreflight === "function" && typeof window.mediaPipelineLaunchView?.updateLaunchCommandButtonStates === "function")`;
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: readyExpression,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: readyExpression,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Pipeline start WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: pipelineStartClickScript(),
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


def _run_browser_pipeline_start_click_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView pipeline start smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-pipeline-start-click-payload.json"
        runner_path = tmp / "browser-pipeline-start-click-runner.cjs"
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
        runner_path.write_text(_browser_pipeline_start_click_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView pipeline start click smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=75,
        )


class WebViewBrowserLaunchQueueReadinessSmoke(unittest.TestCase):
    def test_real_browser_renders_launch_queue_readiness_without_mutation_posts(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView Launch/Queue readiness smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, source, output = _write_fixture_state(root)
            command_journal_path = root / "RunLogs" / "local_api_command_history.json"
            _write_launch_command_history(command_journal_path)
            validation_log = (resolved.state_root or (root / "State")) / "Validation" / "sample_validation_log.jsonl"
            _write_launch_sample_validation_log(validation_log, source=source, output=output)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-launch-queue-readiness-token",
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
                validation_log: validation_log.read_bytes(),
            }
            try:
                server.start()
                result = _run_browser_launch_queue_readiness_smoke(browser_path=browser_path, url=server.url)
            finally:
                server.stop()

            self.assertTrue(result["ok"])
            browser_result = result["result"]
            scan_posts = [post for post in browser_result["posts"] if post["path"] == "/api/queue/scan"]
            unexpected_posts = [
                post
                for post in browser_result["posts"]
                if post["path"] not in {"/api/queue/scan", "/api/ui-preferences"}
            ]
            self.assertEqual(unexpected_posts, [])
            self.assertEqual(len(scan_posts), 1)
            self.assertEqual(scan_posts[0]["body"]["mode"], "inventory_then_curate")
            self.assertEqual(scan_posts[0]["body"]["scope"], "all")
            self.assertIs(scan_posts[0]["body"]["force"], True)
            self.assertEqual(
                browser_result["singleFileRequest"]["single_file"],
                r"E:\Videos\Scratch\Encoded\TV\Sample Pilot.mkv",
            )
            self.assertIn(
                "Single-file launch: WebView submits the path only",
                browser_result["launchPreflight"],
            )
            self.assertEqual(browser_result["launchActiveTab"], "pipeline")
            self.assertEqual(browser_result["diagnosticsActiveTab"], "readiness")
            self.assertEqual(browser_result["historyOwner"], "Launch")
            self.assertIn("Launch scope reconciliation:", browser_result["scopeReconciliation"])
            self.assertIn("Launch start decision summary:", browser_result["startDecision"])
            self.assertIn("Signal: Backend preflight", browser_result["startDecisionDetail"])
            self.assertIn("Launch real-media sample proof handoff:", browser_result["realMediaProof"])
            self.assertIn("Generated worksheet evidence:", browser_result["realMediaProof"])
            self.assertIn("Matching worksheet runs: 1", browser_result["worksheetProofDetail"])
            self.assertIn("Sample Validation record evidence:", browser_result["realMediaProof"])
            self.assertIn("Matching records: 1", browser_result["recordProofDetail"])
            self.assertIn("Record: launch-smoke-sample-validation-record", browser_result["recordProofDetail"])
            self.assertIn("Completed output and size proof", browser_result["completedProofDetail"])
            self.assertIn("Pilot category coverage", browser_result["realMediaProofDetail"])
            self.assertIn("Current category record matches: 0", browser_result["realMediaProofDetail"])
            self.assertIn("Accepted/historical category record matches: 1", browser_result["realMediaProofDetail"])
            self.assertIn("Saved policy vs Queue route evidence packet:", browser_result["policyProofDetail"])
            self.assertIn("queue signal=visible-route-signal", browser_result["policyProofDetail"])
            self.assertIn("Launch sample execution checklist:", browser_result["sampleExecution"])
            self.assertIn("Phase: Post-run Completed Proof", browser_result["sampleExecutionDetail"])
            self.assertIn("Launch pilot run readiness:", browser_result["pilotReadiness"])
            self.assertIn("Pilot category coverage", browser_result["pilotReadinessDetail"])
            self.assertIn("Current category record matches: 0", browser_result["pilotReadinessDetail"])
            self.assertIn("Saved policy vs Queue route evidence packet:", browser_result["pilotPolicyDetail"])
            self.assertIn("Pipeline backend preflight:", browser_result["backendPreflight"])
            self.assertIn("Status scope: active targets only", browser_result["backendPreflight"])
            self.assertNotIn("CSV Rerun Start", browser_result["backendPreflight"])
            self.assertIn("Queue-to-Launch handoff:", browser_result["queueDecision"])
            self.assertIn("Backend launch gating remains the source of truth.", browser_result["scheduleGuidance"])
            self.assertIn("Launch command review:", browser_result["commandReview"])
            for path, before in watched.items():
                self.assertEqual(path.read_bytes(), before, path)
            assert_media_no_mutation(self, media_snapshot)

    def test_real_browser_pipeline_start_button_posts_backend_start(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView pipeline start smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, source, output = _write_fixture_state(root)
            resolved.pending_push_path = root / "EmptyPendingServerPush"
            resolved.pending_push_path.mkdir(parents=True, exist_ok=True)
            resolved.config_data = {**(resolved.config_data or {}), "NetworkRole": "standalone"}
            command_journal_path = root / "RunLogs" / "local_api_command_history.json"
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            service.snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
                pipeline_events=[],
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-pipeline-start-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                command_journal_path=command_journal_path,
            )
            try:
                server.start()
                result = _run_browser_pipeline_start_click_smoke(browser_path=browser_path, url=server.url)
            finally:
                server.stop()

            self.assertTrue(result["ok"])
            browser_result = result["result"]
            self.assertEqual(browser_result["launchPost"]["path"], "/api/pipeline/start")
            self.assertTrue(browser_result["launchPost"]["ok"])
            self.assertEqual(browser_result["launchPost"]["command"], "pipeline.start")
            self.assertEqual(browser_result["launchPost"]["body"]["mode"], "once")
            self.assertEqual(browser_result["launchPost"]["body"]["sleep_seconds"], 3)
            self.assertEqual(service.started_pipeline["mode"], "once")
            self.assertEqual(service.started_pipeline["sleep_seconds"], 3)
            self.assertIsNone(service.started_pipeline["single_file"])
            self.assertIn("Started pipeline (once)", browser_result["launchPost"]["message"])
            self.assertFalse(source.read_bytes() == b"")
            self.assertFalse(output.read_bytes() == b"")
            assert_media_no_mutation(self, media_snapshot)


if __name__ == "__main__":
    unittest.main()
