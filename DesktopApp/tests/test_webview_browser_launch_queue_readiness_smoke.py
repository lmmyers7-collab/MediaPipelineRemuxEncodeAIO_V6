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
              button.click();
              requireLaunchTab(tabId);
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
              "launchStartDecisionRows",
              "launchWorksheetEvidence",
              "launchSampleValidationRecordEvidence",
              "launchPolicyAlignmentQueueIntentEvidence",
              "launchQueueIntentCategoryMatch",
              "renderLaunchSampleExecutionChecklist",
              "launchSampleExecutionRows",
              "renderLaunchPilotRunReadiness",
              "launchPilotRunReadinessRows",
              "refreshLaunchBackendPreflight",
              "renderQueueLaunchDecisionChecklist",
              "queueLaunchDecisionRows",
              "renderScheduleTimingTrust",
              "getCommandHistory",
              "renderLaunchCommandHistory",
              "commandHistoryOwnerPage",
            ].forEach(requireFunction);

            window.showPage("launch");
            if (typeof window.mediaPipelineLaunchView?.activateLaunchTab !== "function") throw new Error("missing mediaPipelineLaunchView.activateLaunchTab");
            requireLaunchTab("pipeline");
            clickLaunchTab("pipeline");
            setInput("pipeline-start-mode", "continuous");
            setInput("pipeline-start-single-file", "E:\\\\Videos\\\\Scratch\\\\Encoded\\\\TV\\\\Sample Pilot.mkv");
            setInput("pipeline-start-schedule-override", "");
            window.mediaPipelineLaunchView.renderAllLaunchPreflights();
            clickLaunchTab("readiness");
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
                && text("launch-sample-execution-summary").includes("Launch sample execution checklist:")
                && text("launch-pilot-readiness-summary").includes("Launch pilot run readiness:")
                && text("launch-backend-preflight-summary").includes("Backend launch preflight:")
                && !text("launch-backend-preflight-status").includes("Loading")
                && text("queue-launch-decision-summary").includes("Queue launch decision checklist:")
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
              "Decision rule: the visible Queue table, selected Launch mode, cached backend preflight, Schedule posture, close-readiness, and recent command evidence must agree before starting queued work.",
              "First action:",
              "Mutation guardrail: this reconciliation is read-only",
            ]);
            requireTableText("launch-scope-reconciliation-rows", [
              "Backend authority",
              "Queue payload",
              "Queue display filter scope",
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
              "Decision rule: treat Start as sensible only when Launch readiness, backend preflight, Queue, Settings, schedule/close-readiness, real-media proof, sample checklist, and recent command evidence agree.",
              "First action:",
              "Mutation guardrail: this summary is read-only",
            ]);
            requireTableText("launch-start-decision-rows", [
              "Launch readiness",
              "Backend preflight",
              "Queue launch decision",
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
              "Backend launch preflight:",
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
              "Decision rule: before pressing Start",
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
            requireText("launch-backend-preflight-summary", [
              "Backend launch preflight:",
              "Source: GET /api/launch/preflight",
              "Source: GET /api/launch/preflight",
            ]);
            requireTableText("launch-backend-preflight-rows", [
              "Pipeline",
              "Process launch lock",
              "Active work guard",
              "CSV Rerun",
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
            if (!validateStartButton.disabled || !validateStartButton.title.includes("Refresh Backend Preflight")) {
              throw new Error("Run Once should require backend preflight before start; disabled=" + validateStartButton.disabled + "; title=" + validateStartButton.title);
            }
            setInput("pipeline-start-mode", "continuous");
            const blockedPipelinePreflight = {
              ...originalPipelinePreflight,
              status: "blocked",
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
            const launchGateChecks = [
              ["pipeline-start-button", "Resolve blocked Backend Preflight checks"],
              ["pending-drain-button", "Refresh Backend Preflight"],
              ["audit-start-button", "Resolve blocked Backend Preflight checks"],
              ["rerun-start-button", "Resolve blocked Backend Preflight checks"],
            ];
            launchGateChecks.forEach(([id, titleFragment]) => {
              const button = byId(id);
              if (!button) throw new Error("missing launch gate button " + id);
              if (!button.disabled || !button.title.includes(titleFragment)) {
                throw new Error(id + " did not expose blocked launch gate title; disabled=" + button.disabled + "; title=" + button.title);
              }
            });
            window.mediaPipelineLaunchView.renderLaunchBackendPreflight(originalBackendPreflightPayloads);
            window.mediaPipelineLaunchView.updateLaunchCommandButtonStates();
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
              "Correlated checklist/preflight evidence:",
              "Guardrail: backend start routes re-check this state at submission time",
            ]);
            requireText("launch-history", [
              "Last 1 launch command:",
              "Pipeline",
              "Backend launch locking and validation remain the source of truth.",
            ]);

            window.showPage("queue");
            await waitFor(
              () => text("queue-launch-decision-summary").includes("Queue launch decision checklist:"),
              "Queue launch decision after page switch",
            );
            requireText("queue-launch-decision-summary", [
              "Queue launch decision checklist:",
              "Decision rule: launch only after backend launch preflight",
              "Mutation guardrail: this checklist cannot launch",
            ]);
            requireText("queue-backend-scope-summary", [
              "Backend launch scope preview:",
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
              "Queue launch decision checklist:",
              "Guardrail: only backend Launch routes can start processing",
            ]);

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
            const owner = window.commandHistoryOwnerPage(launchEntry);
            if (owner !== "Launch") throw new Error("pipeline.start owner should be Launch, got " + owner);
            if (posts.length) throw new Error("Launch/Queue readiness render posted unexpected routes: " + JSON.stringify(posts));
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
                expression: `Boolean(document.getElementById("launch-backend-preflight-summary") && document.getElementById("launch-scope-reconciliation-summary") && document.getElementById("launch-start-decision-summary") && document.getElementById("launch-real-media-proof-summary") && document.getElementById("launch-sample-execution-summary") && document.getElementById("launch-pilot-readiness-summary") && document.getElementById("queue-launch-decision-summary") && document.getElementById("schedule-guidance") && document.getElementById("close-readiness") && typeof window.mediaPipelineLaunchView.activateLaunchTab === "function" && typeof window.mediaPipelineLaunchView.renderAllLaunchPreflights === "function" && typeof window.mediaPipelineLaunchView.renderLaunchScopeReconciliation === "function" && typeof window.mediaPipelineLaunchView.renderLaunchStartDecisionSummary === "function" && typeof window.mediaPipelineLaunchView.renderLaunchRealMediaProofHandoff === "function" && typeof window.mediaPipelineLaunchView.renderLaunchSampleExecutionChecklist === "function" && typeof window.mediaPipelineLaunchView.renderLaunchPilotRunReadiness === "function" && typeof window.queueLaunchDecisionRows === "function" && typeof window.commandHistoryOwnerPage === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("launch-backend-preflight-summary") && document.getElementById("launch-scope-reconciliation-summary") && document.getElementById("launch-start-decision-summary") && document.getElementById("launch-real-media-proof-summary") && document.getElementById("launch-sample-execution-summary") && document.getElementById("launch-pilot-readiness-summary") && document.getElementById("queue-launch-decision-summary") && document.getElementById("schedule-guidance") && document.getElementById("close-readiness") && typeof window.mediaPipelineLaunchView.activateLaunchTab === "function" && typeof window.mediaPipelineLaunchView.renderAllLaunchPreflights === "function" && typeof window.mediaPipelineLaunchView.renderLaunchScopeReconciliation === "function" && typeof window.mediaPipelineLaunchView.renderLaunchStartDecisionSummary === "function" && typeof window.mediaPipelineLaunchView.renderLaunchRealMediaProofHandoff === "function" && typeof window.mediaPipelineLaunchView.renderLaunchSampleExecutionChecklist === "function" && typeof window.mediaPipelineLaunchView.renderLaunchPilotRunReadiness === "function" && typeof window.queueLaunchDecisionRows === "function" && typeof window.commandHistoryOwnerPage === "function")`,
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


class WebViewBrowserLaunchQueueReadinessSmokeTests(unittest.TestCase):
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
            self.assertEqual(browser_result["posts"], [])
            self.assertEqual(
                browser_result["singleFileRequest"]["single_file"],
                r"E:\Videos\Scratch\Encoded\TV\Sample Pilot.mkv",
            )
            self.assertIn(
                "Single-file launch: WebView submits the path only",
                browser_result["launchPreflight"],
            )
            self.assertEqual(browser_result["launchActiveTab"], "readiness")
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
            self.assertIn("Backend launch preflight:", browser_result["backendPreflight"])
            self.assertIn("Queue launch decision checklist:", browser_result["queueDecision"])
            self.assertIn("Backend launch gating remains the source of truth.", browser_result["scheduleGuidance"])
            self.assertIn("Launch command review:", browser_result["commandReview"])
            for path, before in watched.items():
                self.assertEqual(path.read_bytes(), before, path)
            assert_media_no_mutation(self, media_snapshot)


if __name__ == "__main__":
    unittest.main()
