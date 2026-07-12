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


def _browser_sample_validation_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function sampleValidationScript() {
          return `
          (async () => {
            const posts = [];
            const originalApiPost = window.apiPost;
            window.apiPost = async (path, body, options) => {
              posts.push({ path: String(path || ""), body: body || {}, options: options || {} });
              if (String(path || "") === "/api/sample-validation/preview") {
                return originalApiPost(path, body, options);
              }
              return { ok: false, message: "sample-validation smoke blocks mutation posts" };
            };
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
            function requireSingleSelectedRows(tbodyId, label) {
              const tbody = byId(tbodyId);
              if (!tbody) throw new Error("missing tbody " + tbodyId);
              const selected = Array.from(tbody.querySelectorAll("tr.is-selected, tr[aria-selected='true']"));
              const unique = Array.from(new Set(selected));
              if (unique.length !== 1) {
                throw new Error(label + " expected exactly one selected row, saw " + unique.length + "\\nActual:\\n" + text(tbodyId));
              }
              const row = unique[0];
              if (!row.classList.contains("is-selected") || row.getAttribute("aria-selected") !== "true") {
                throw new Error(label + " selected row did not expose both class and aria-selected.");
              }
              return row;
            }
            function requireDecisionStrip() {
              const strip = byId("sample-validation-decision-strip");
              if (!strip) throw new Error("missing sample-validation-decision-strip");
              requireText("sample-validation-decision-strip-summary", ["Decision:", "Category:", "Checks:", "Gate:"]);
              if (!strip.dataset.state) throw new Error("sample validation decision strip missing data-state");
            }
            function requireButtonBusy(id, label) {
              const button = byId(id);
              if (!button) throw new Error("missing " + id);
              if (button.getAttribute("aria-busy") !== "true" || !button.disabled) {
                throw new Error(label + " did not expose immediate busy/disabled feedback.");
              }
              return button;
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
                "sampleStatus=" + text("sample-validation-status"),
                "sampleSummary=" + text("sample-validation-summary"),
                "cutoverSummary=" + text("sample-validation-cutover-summary"),
                "sampleSetSummary=" + text("sample-validation-sample-set-summary"),
                "sampleResult=" + text("sample-validation-result"),
                "posts=" + JSON.stringify(posts),
              ].join("\\n"));
            }
            await waitFor(() => typeof window.showPage === "function", "showPage global");
            [
              "showPage",
              "refreshAllNow",
              "renderCrossPageContext",
              "renderSampleValidationRecordPanel",
              "renderSampleValidationGapSummary",
              "renderSampleValidationRunbook",
              "renderSampleValidationCutoverGate",
              "renderSampleValidationSampleSetGuide",
              "renderSampleValidationCompletedPacketHandoff",
              "sampleValidationCompletedPacketRows",
              "sampleValidationCompletedPolicyReconciliationRow",
              "sampleValidationCompletedPolicyReconciliationStatus",
              "renderSampleValidationAcceptanceGate",
              "sampleValidationAcceptanceGateRows",
              "renderSampleValidationRecordReview",
              "sampleValidationRecordReviewRows",
              "renderSampleValidationCategorySummary",
              "sampleValidationCategorySummaryRows",
              "buildSampleValidationRequest",
              "getCommandHistory",
            ].forEach(requireFunction);
            const sampleRecordsSource = await fetch("/assets/crossPageContextView.sampleValidation.records.js").then((response) => response.text());
            [
              "completedPilotEvidencePacketRows",
              "completedPilotEvidencePacketStatus",
              "completedPilotEvidencePacketDetailLines",
              "completedPilotEvidencePacketMarkdownLines",
              "completedPilotEvidencePostureStatus",
            ].forEach((name) => {
              if (sampleRecordsSource.includes("window." + name)) {
                throw new Error("sample validation records still read flat Completed pilot helper " + name);
              }
            });

            await waitFor(
              () => window.performance?.getEntriesByName?.("mediapipeline-startup-critical-ready")?.length > 0,
              "startup critical refresh",
            );
            window.showPage("home");
            await window.refreshAllNow({ page: "home" });
            await waitFor(
              () => text("sample-validation-summary").includes("Real-media pilot plan:")
                && text("sample-validation-summary").includes("Read-only real-media pilot plan")
                && text("sample-validation-gap-summary").includes("Real-media evidence gap summary:")
                && text("sample-validation-runbook-summary").includes("Real-media pilot runbook:")
                && text("sample-validation-cutover-summary").includes("WebView cutover gate:")
                && text("sample-validation-sample-set-summary").includes("Recommended real-media sample set:")
                && text("sample-validation-category-summary").includes("Pilot category validation summary:")
                && text("sample-validation-execution-summary").includes("Operator-selected real-media sample execution:")
                && text("sample-validation-worksheet-summary").includes("Generated real-media worksheets:")
                && text("sample-validation-completed-packet-summary").includes("Completed evidence handoff for Sample Validation:")
                && text("sample-validation-acceptance-gate-summary").includes("Sample Validation acceptance readiness gate:")
                && text("sample-validation-record-review-summary").includes("Accepted sample-validation record proof review:"),
              "sample validation pilot plan rendering",
            );
            requireDecisionStrip();
            requireText("sample-validation-summary", [
              "Backend-owned sample validation records:",
              "WebView cutover gate:",
              "Real-media validation audit:",
              "Real-media policy alignment:",
              "Real-media sample set:",
              "Pilot runbook:",
              "Pilot category:",
              "Boundary: validation audit is read-only",
              "Read-only real-media policy alignment",
              "Real-media pilot plan:",
              "Generated real-media worksheets:",
              "Selected sample worksheet matches:",
              "Sample run required:",
              "Recommended sample count:",
              "Pilot checkpoints:",
              "Pilot next required action:",
              "Pilot attention:",
              "Select a small known sample:",
              "Run through backend-owned Launch only:",
              "Stop conditions:",
              "Backend readiness:",
              "Pilot categories:",
              "Current evidence reconciliation:",
              "Guardrail: records do not mark jobs complete",
            ]);
            requireText("sample-validation-gap-summary", [
              "Real-media evidence gap summary:",
              "Rows:",
              "Required gaps:",
              "Sample set required ready:",
              "Boundary: this gap summary is read-only",
              "Read-only real-media evidence-gap summary",
            ]);
            requireText("sample-validation-runbook-summary", [
              "Real-media pilot runbook:",
              "Steps:",
              "Required runbook gaps:",
              "Evidence gaps:",
              "Boundary: this runbook is read-only",
              "Read-only real-media pilot runbook",
            ]);
            const runbookRows = Array.from(document.querySelectorAll("#sample-validation-runbook-rows tr[data-selectable-row='true']"));
            if (runbookRows.length < 8) throw new Error("expected pilot runbook rows, saw " + runbookRows.length);
            const runbookText = runbookRows.map((row) => row.textContent || "").join("\\n");
            [
              "Choose one representative sample and category",
              "Confirm saved media policy before launch",
              "Start the sample only through backend-owned Launch",
              "Verify Completed output, route, sidecar, and size",
              "Preview and append evidence-only validation note",
            ].forEach((fragment) => {
              if (!runbookText.includes(fragment)) throw new Error("pilot runbook table missing " + fragment + "\\n" + runbookText);
            });
            runbookRows.find((row) => (row.textContent || "").includes("Verify Completed output")).click();
            requireSingleSelectedRows("sample-validation-runbook-rows", "Sample Validation runbook");
            requireText("sample-validation-runbook-detail", [
              "Step:",
              "Verify Completed output, route, sidecar, and size",
              "Required evidence:",
              "Safe next action:",
              "Read-only pilot runbook row",
            ]);
            requireText("sample-validation-runbook-markdown", [
              "# Real-Media WebView Pilot Runbook",
              "## Safety Boundary",
              "## Checklist",
              "Does not launch the pipeline",
              "Verify Completed output, route, sidecar, and size",
            ]);
            const gapRows = Array.from(document.querySelectorAll("#sample-validation-gap-rows tr[data-selectable-row='true']"));
            if (gapRows.length < 6) throw new Error("expected evidence-gap rows, saw " + gapRows.length);
            const gapText = gapRows.map((row) => row.textContent || "").join("\\n");
            [
              "Current backend evidence",
              "Selected sample and saved policy",
              "Post-run Completed and Diagnostics proof",
              "Representative category coverage",
              "Current accepted record reconciliation",
            ].forEach((fragment) => {
              if (!gapText.includes(fragment)) throw new Error("evidence-gap table missing " + fragment + "\\n" + gapText);
            });
            gapRows.find((row) => (row.textContent || "").includes("Representative category coverage")).click();
            requireSingleSelectedRows("sample-validation-gap-rows", "Sample Validation evidence gaps");
            requireText("sample-validation-gap-detail", [
              "Checkpoint: Representative category coverage",
              "Owner page: Home / Sample Validation",
              "Missing evidence:",
              "Safe next action:",
              "Read-only evidence-gap row",
            ]);
            requireText("sample-validation-cutover-summary", [
              "WebView cutover gate:",
              "Rows:",
              "current accepted records=",
              "Acceptance boundary:",
              "generated worksheets are context only",
              "Boundary: this is not a production cutover switch",
              "Read-only WebView cutover evidence",
            ]);
            requireText("sample-validation-sample-set-summary", [
              "Recommended real-media sample set:",
              "Recommended samples: 3-5",
              "Required categories ready:",
              "Proof boundary: worksheet samples are planned/context rows only",
              "Boundary: this guide is read-only",
              "Read-only representative sample-set guidance",
            ]);
            requireText("sample-validation-category-summary", [
              "Pilot category validation summary:",
              "Decision rule: a category is ready only when an accepted validation record",
              "Mutation guardrail",
            ]);
            const categorySummaryRows = Array.from(document.querySelectorAll("#sample-validation-category-summary-rows tr[data-selectable-row='true']"));
            if (categorySummaryRows.length < 5) throw new Error("expected pilot category validation summary rows, saw " + categorySummaryRows.length);
            const categorySummaryText = categorySummaryRows.map((row) => row.textContent || "").join("\\n");
            [
              "H.264 remux/direct-play copy",
              "Preferred-language subtitle to SRT",
              "Audio routing/default language",
              "Encode and size policy",
              "Deferred publish/final placement",
            ].forEach((fragment) => {
              if (!categorySummaryText.includes(fragment)) throw new Error("category summary missing " + fragment + "\\n" + categorySummaryText);
            });
            const h264CategoryRow = categorySummaryRows.find((row) => (row.textContent || "").includes("H.264 remux/direct-play copy"));
            if (!h264CategoryRow) throw new Error("missing H.264 category summary row");
            h264CategoryRow.click();
            requireSingleSelectedRows("sample-validation-category-summary-rows", "Sample Validation category summary");
            requireText("sample-validation-category-summary-detail", [
              "Pilot category validation summary:",
              "Category: H.264 remux/direct-play copy",
              "Proof boundary:",
              "Mutation guardrail",
            ]);
            const sampleSetRows = Array.from(document.querySelectorAll("#sample-validation-sample-set-rows tr[data-selectable-row='true']"));
            if (sampleSetRows.length < 5) throw new Error("expected representative sample-set rows, saw " + sampleSetRows.length);
            const sampleSetText = sampleSetRows.map((row) => row.textContent || "").join("\\n");
            [
              "H.264 remux/direct-play copy",
              "Preferred-language subtitle to SRT",
              "Audio routing/default language",
              "Encode and size policy",
              "Deferred publish/final placement",
            ].forEach((fragment) => {
              if (!sampleSetText.includes(fragment)) throw new Error("sample-set guide missing " + fragment + "\\n" + sampleSetText);
            });
            const category = byId("sample-validation-category");
            if (!category) throw new Error("missing sample-validation-category");
            if (category.value !== "") throw new Error("pilot category should start blank, saw " + category.value);
            sampleSetRows.find((row) => (row.textContent || "").includes("H.264 remux/direct-play copy")).click();
            requireSingleSelectedRows("sample-validation-sample-set-rows", "Sample Validation sample-set guide");
            if (category.value !== "") throw new Error("sample-set row click auto-applied category: " + category.value);
            requireText("sample-validation-sample-set-detail", [
              "Category: H.264 remux/direct-play copy",
              "Evidence goal:",
              "Current evidence:",
              "Safe next action:",
              "Read-only sample-set row",
            ]);
            const useSampleSetCategory = byId("sample-validation-use-sample-set-category-button");
            if (!useSampleSetCategory) throw new Error("missing sample-validation-use-sample-set-category-button");
            useSampleSetCategory.click();
            if (category.value !== "h264-remux-safe") {
              throw new Error("sample-set category handoff failed: " + category.value);
            }
            requireText("sample-validation-result", [
              "Pilot category set to h264-remux-safe",
              "evidence only",
              "cannot mutate media",
            ]);
            const deferredPublishRow = sampleSetRows.find((row) => (row.textContent || "").includes("Deferred publish/final placement"));
            if (!deferredPublishRow) throw new Error("missing deferred publish sample-set row");
            deferredPublishRow.click();
            if (category.value !== "h264-remux-safe") {
              throw new Error("sample-set row click changed category without button: " + category.value);
            }
            useSampleSetCategory.click();
            if (category.value !== "deferred-publish") {
              throw new Error("deferred-publish category handoff failed: " + category.value);
            }
            sampleSetRows.find((row) => (row.textContent || "").includes("H.264 remux/direct-play copy")).click();
            useSampleSetCategory.click();
            if (category.value !== "h264-remux-safe") {
              throw new Error("h264 category restore failed before preview: " + category.value);
            }
            const cutoverRows = Array.from(document.querySelectorAll("#sample-validation-cutover-rows tr[data-selectable-row='true']"));
            if (cutoverRows.length < 5) throw new Error("expected cutover gate rows, saw " + cutoverRows.length);
            const cutoverText = cutoverRows.map((row) => row.textContent || "").join("\\n");
            [
              "Backend evidence availability",
              "Current accepted sample record",
              "Playback subtitle audio publish checks",
              "Stale or review history",
            ].forEach((fragment) => {
              if (!cutoverText.includes(fragment)) throw new Error("cutover gate missing " + fragment + "\\n" + cutoverText);
            });
            cutoverRows.find((row) => (row.textContent || "").includes("Current accepted sample record")).click();
            requireSingleSelectedRows("sample-validation-cutover-rows", "Sample Validation cutover gate");
            requireText("sample-validation-cutover-detail", [
              "Checkpoint: Current accepted sample record",
              "Safe next action:",
              "Read-only cutover-gate evidence",
            ]);
            requireText("sample-validation-execution-summary", [
              "Operator-selected real-media sample execution:",
              "Execution required ready:",
              "Execution next action:",
              "Boundary: execution checklist is read-only guidance",
            ]);
            requireText("sample-validation-worksheet-summary", [
              "Generated real-media worksheets:",
              "Runs loaded: 1",
              "Selected sample worksheet matches: 1",
              "Read-only generated worksheet evidence",
            ]);
            requireText("sample-validation-worksheet-detail", [
              "Worksheet: real_media_validation_fixture.md",
              "Selected sample match: yes",
              "Pilot packet rows:",
              "Read-only generated worksheet evidence",
            ]);
            requireText("sample-validation-execution-legend", [
              "Sample execution checklist rows:",
            ]);
            const executionRows = Array.from(document.querySelectorAll("#sample-validation-execution-rows tr[data-selectable-row='true']"));
            if (executionRows.length < 7) throw new Error("expected execution checklist rows, saw " + executionRows.length);
            const executionText = executionRows.map((row) => row.textContent || "").join("\\n");
            [
              "Before Launch",
              "Backend Launch Boundary",
              "Post-run Completed Proof",
              "Post-run Diagnostics Proof",
              "Evidence Record",
            ].forEach((fragment) => {
              if (!executionText.includes(fragment)) throw new Error("execution checklist missing " + fragment + "\\n" + executionText);
            });
            executionRows.find((row) => (row.textContent || "").includes("Post-run Completed Proof")).click();
            requireSingleSelectedRows("sample-validation-execution-rows", "Sample Validation execution checklist");
            requireText("sample-validation-execution-detail", [
              "Phase: Post-run Completed Proof",
              "Owner page: Completed",
              "Backend evidence:",
              "Operator proof:",
              "Unsafe if ignored:",
              "Read-only execution checklist",
            ]);
            const executionSelectedDetail = text("sample-validation-execution-detail");
            requireText("sample-validation-check-status", [
              "Checks ready:",
              "manual:",
            ]);
            requireText("cross-page-real-media-summary", [
              "Real-media validation worksheet:",
              "Queue route intent, Completed output proof, Pending Publish final-destination proof",
              "Sample Validation evidence posture",
              "Sample validation:",
            ]);
            requireText("sample-validation-completed-packet-summary", [
              "Completed evidence handoff for Sample Validation:",
              "Saved-policy reconciliation:",
              "Decision rule: keep Sample Validation at hold/review",
              "Mutation guardrail",
            ]);
            requireText("sample-validation-acceptance-gate-summary", [
              "Sample Validation acceptance readiness gate:",
              "Decision rule: accepted sample evidence should not be appended",
              "Mutation guardrail",
            ]);
            const acceptanceGateRows = Array.from(document.querySelectorAll("#sample-validation-acceptance-gate-rows tr[data-selectable-row='true']"));
            if (acceptanceGateRows.length < 7) throw new Error("expected sample-validation acceptance gate rows, saw " + acceptanceGateRows.length);
            const policyGateRow = acceptanceGateRows.find((row) => (row.textContent || "").includes("Saved policy reconciliation"));
            if (!policyGateRow) throw new Error("acceptance gate missing saved policy reconciliation row");
            policyGateRow.click();
            requireSingleSelectedRows("sample-validation-acceptance-gate-rows", "Sample Validation acceptance gate");
            requireText("sample-validation-acceptance-gate-detail", [
              "Saved policy reconciliation",
              "mirrors Completed > Selected Pilot Evidence Packet",
              "Missing visible category tokens are review gaps",
              "Mutation guardrail",
            ]);
            const checklistGateRow = acceptanceGateRows.find((row) => (row.textContent || "").includes("Acceptance checklist coverage"));
            if (!checklistGateRow) throw new Error("acceptance gate missing checklist coverage row");
            checklistGateRow.click();
            requireText("sample-validation-acceptance-gate-detail", [
              "Acceptance checklist coverage",
              "Required checks cover route",
              "Mutation guardrail",
            ]);
            requireText("sample-validation-completed-packet-detail", [
              "Selected pilot evidence packet:",
              "Checkpoint:",
            ]);
            requireText("sample-validation-completed-packet-markdown", [
              "# Selected Completed Pilot Evidence Packet",
              "## Checklist",
              "Confirm Plex/client playback",
              "Home > Sample Validation evidence is evidence-only",
              "append accepted evidence only after",
              "Backend mutation boundary",
            ]);
            const completedPacketRows = Array.from(document.querySelectorAll("#sample-validation-completed-packet-rows tr[data-selectable-row='true']"));
            if (completedPacketRows.length < 6) throw new Error("expected Completed evidence handoff rows, saw " + completedPacketRows.length);
            const policyPacketRow = completedPacketRows.find((row) => (row.textContent || "").includes("Saved policy reconciliation"));
            if (!policyPacketRow) throw new Error("Completed evidence handoff missing Saved policy reconciliation row");
            policyPacketRow.click();
            requireSingleSelectedRows("sample-validation-completed-packet-rows", "Sample Validation completed-packet handoff");
            requireText("sample-validation-completed-packet-detail", [
              "Saved policy reconciliation",
              "Completed policy reconciliation:",
              "Category comparison rows:",
              "Post-run boundary: Completed can prove output-side evidence only",
            ]);
            const sampleReadinessRow = completedPacketRows.find((row) => (row.textContent || "").includes("Sample Validation readiness"));
            if (!sampleReadinessRow) throw new Error("Completed evidence handoff missing Sample Validation readiness row");
            sampleReadinessRow.click();
            requireText("sample-validation-completed-packet-detail", [
              "Sample Validation readiness",
              "Sample Validation is evidence-only",
            ]);
            const decision = byId("sample-validation-decision");
            if (!decision) throw new Error("missing sample-validation-decision");
            decision.value = "accepted";
            decision.dispatchEvent(new Event("change", { bubbles: true }));
            [
              "sample-validation-check-diagnostics",
              "sample-validation-check-subtitle",
              "sample-validation-check-audio",
              "sample-validation-check-pending-publish",
            ].forEach((id) => {
              const input = byId(id);
              if (!input) throw new Error("missing " + id);
              input.checked = true;
              input.dispatchEvent(new Event("change", { bubbles: true }));
            });
            requireText("sample-validation-check-status", [
              "Checks ready:",
              "manual:",
              "subtitle",
              "audio",
            ]);
            requireText("sample-validation-acceptance-gate-summary", [
              "Operator decision: accepted",
              "Evidence coverage:",
              "Mutation guardrail",
            ]);
            requireText("sample-validation-record-review-summary", [
              "Accepted sample-validation record proof review:",
              "Decision rule: treat accepted records as current proof only",
              "Mutation guardrail",
            ]);
            requireDecisionStrip();
            const preview = byId("sample-validation-preview-button");
            if (!preview) throw new Error("missing sample validation preview button");
            preview.click();
            requireButtonBusy("sample-validation-preview-button", "Preview Record");
            requireButtonBusy("sample-validation-strip-preview-button", "Decision-strip Preview Record");
            await waitFor(
              () => text("sample-validation-result").includes("Current backend evidence:") && text("sample-validation-result").includes("Read-only current-evidence preview"),
              "sample validation preview result",
            );
            if (byId("sample-validation-preview-button").getAttribute("aria-busy") === "true" || byId("sample-validation-preview-button").disabled) {
              throw new Error("Preview Record button did not restore after preview.");
            }
            if (byId("sample-validation-strip-preview-button").getAttribute("aria-busy") === "true" || byId("sample-validation-strip-preview-button").disabled) {
              throw new Error("Decision-strip Preview Record button did not restore after preview.");
            }
            requireText("sample-validation-result", [
              "OK: true",
              "Decision: accepted",
              "Proof:",
              "Pilot category: h264-remux-safe",
              "Current backend evidence:",
              "Status: review",
              "Matches:",
              "pending=yes",
              "verify parked/drained state",
              "Read-only current-evidence preview",
              "Pilot evidence packet:",
              "Queue route proof:",
              "Completed output and sidecar proof:",
              "Diagnostics and run-log proof:",
              "Pending Publish posture:",
              "Playback, subtitle, audio, and size proof:",
              "Stop conditions:",
              "Read-only pilot evidence packet",
              "Post-run evidence capture:",
              "Required capture gaps:",
              "Remux vs encode decision:",
              "Completed output and sidecar:",
              "Diagnostics and FFmpeg logs:",
              "Subtitle behavior:",
              "Audio behavior:",
              "Output size posture:",
              "Append decision:",
              "Copyable post-run Markdown:",
              "# Real-Media Post-Run Evidence Capture",
              "Read-only post-run evidence capture packet",
              "Append readiness:",
              "Status: review-before-append",
              "Current backend proof clean: no",
              "Required acceptance gaps: none",
              "Recommended review gaps: none",
              "Diagnostics / run logs: checked",
              "Subtitle behavior: checked",
              "Audio behavior: checked",
              "Read-only append-readiness advice",
              "Preview only. Sample validation records are operator evidence",
            ]);
            const forbidden = [
              "/api/sample-validation/append",
              "/api/pipeline/start",
              "/api/audit/start",
              "/api/rerun/start",
              "/api/settings/save-patch",
              "/api/rename/apply",
              "/api/pending-publish/drain",
            ];
            const forbiddenPosts = posts.filter((entry) => forbidden.some((path) => entry.path.includes(path)));
            if (forbiddenPosts.length) throw new Error("sample-validation smoke posted forbidden routes: " + JSON.stringify(forbiddenPosts));
            const previewPosts = posts.filter((entry) => entry.path === "/api/sample-validation/preview");
            if (previewPosts.length !== 1) throw new Error("expected exactly one preview POST, saw " + JSON.stringify(posts));
            const previewChecks = previewPosts[0].body?.checks || {};
            if (previewPosts[0].body?.sample_category !== "h264-remux-safe") {
              throw new Error("preview POST did not carry sample_category: " + JSON.stringify(previewPosts[0].body));
            }
            if (previewPosts[0].body?.shell !== "webview") {
              throw new Error("preview POST did not default to webview shell surface: " + JSON.stringify(previewPosts[0].body));
            }
            window.MEDIA_PIPELINE_BOOTSTRAP = Object.freeze({ ...window.MEDIA_PIPELINE_BOOTSTRAP, shellSurface: "tauri" });
            const tauriShellRequest = window.mediaPipelineCrossPageContextView.buildSampleValidationRequest();
            if (tauriShellRequest.shell !== "tauri") {
              throw new Error("sample validation request did not honor Tauri shell surface: " + JSON.stringify(tauriShellRequest));
            }
            window.MEDIA_PIPELINE_BOOTSTRAP = Object.freeze({ ...window.MEDIA_PIPELINE_BOOTSTRAP, shellSurface: "webview" });
            [
              "diagnostics_checked",
              "subtitle_checked",
              "audio_checked",
              "pending_publish_checked",
            ].forEach((key) => {
              if (previewChecks[key] !== true) throw new Error("preview POST did not carry manual check " + key + ": " + JSON.stringify(previewChecks));
            });
            const originalSampleSummary = text("sample-validation-summary");
            const originalCutoverSummary = text("sample-validation-cutover-summary");
            const originalCutoverDetail = text("sample-validation-cutover-detail");
            const originalSampleSetSummary = text("sample-validation-sample-set-summary");
            const originalSampleSetDetail = text("sample-validation-sample-set-detail");
            const originalExecutionSummary = text("sample-validation-execution-summary");
            const originalExecutionDetail = text("sample-validation-execution-detail");
            const originalSampleResult = text("sample-validation-result");
            const clearChecks = byId("sample-validation-strip-clear-checks-button") || byId("sample-validation-clear-checks-button");
            if (!clearChecks) throw new Error("missing sample validation clear manual checks button");
            clearChecks.click();
            requireButtonBusy("sample-validation-clear-checks-button", "Clear Manual Checks");
            requireButtonBusy("sample-validation-strip-clear-checks-button", "Decision-strip Clear Manual Checks");
            await waitFor(
              () => text("sample-validation-result").includes("Manual sample-validation checks cleared."),
              "sample validation clear manual checks feedback",
            );
            requireDecisionStrip();
            await waitFor(
              () => byId("sample-validation-clear-checks-button").getAttribute("aria-busy") !== "true"
                && byId("sample-validation-strip-clear-checks-button").getAttribute("aria-busy") !== "true"
                && !byId("sample-validation-clear-checks-button").disabled
                && !byId("sample-validation-strip-clear-checks-button").disabled,
              "sample validation clear manual checks restore",
            );
            const recordsFixture = {
              exists: true,
              records: [
                {
                  record_id: "current-record",
                  created_at: "2026-05-15T20:00:00-04:00",
                  operator_decision: "accepted",
                  sample_category: "h264-remux-safe",
                  proof_strength: "exact-path",
                  sample_label: "Current sample",
                  source_path: "C:/Samples/current.mkv",
                  output_path: "C:/Out/current.mkv",
                  checks: { queue_route_checked: true, completed_output_checked: true },
                  evidence: { queue: [{}], completed: [{}], pending_publish: [], diagnostics: [] },
                  operator_notes: "current row note",
                },
                {
                  record_id: "stale-record",
                  created_at: "2026-05-15T19:00:00-04:00",
                  operator_decision: "accepted",
                  sample_category: "subtitle-srt",
                  proof_strength: "exact-path",
                  sample_label: "Stale sample",
                  source_path: "C:/Samples/stale.mkv",
                  output_path: "C:/Out/stale.mkv",
                  checks: { completed_output_checked: true, diagnostics_checked: true },
                  evidence: { queue: [], completed: [{}], pending_publish: [], diagnostics: [{}] },
                  operator_notes: "stale row note",
                },
                {
                  record_id: "no-reconciliation-record",
                  created_at: "2026-05-15T18:00:00-04:00",
                  operator_decision: "accepted",
                  sample_category: "audio-routing",
                  proof_strength: "operator-review",
                  sample_label: "No reconciliation sample",
                  source_path: "C:/Samples/no-reconciliation.mkv",
                  output_path: "C:/Out/no-reconciliation.mkv",
                  checks: {},
                  evidence: {},
                  operator_notes: "no reconciliation row note",
                },
              ],
              reconciliation: {
                rows: [
                  {
                    record_id: "current-record",
                    status: "current",
                    severity: "info",
                    evidence: "queue_source=yes; completed_output=yes",
                    missing_current_evidence: [],
                    safe_next_action: "Current backend evidence still references this record.",
                  },
                  {
                    record_id: "stale-record",
                    status: "stale",
                    severity: "warning",
                    evidence: "queue_source=no; completed_output=no",
                    missing_current_evidence: [
                      "Completed manifest no longer contains the recorded output path.",
                      "Current Queue/Completed evidence no longer contains the recorded source path.",
                    ],
                    safe_next_action: "Treat stale validation records as historical notes only.",
                  },
                ],
              },
              guardrail: "Sample validation records are evidence only.",
            };
            window.mediaPipelineCrossPageContextView.renderSampleValidationRecordPanel({ sampleValidation: recordsFixture });
            const recordRows = Array.from(document.querySelectorAll("#sample-validation-records tr[data-selectable-row='true']"));
            if (recordRows.length !== 3) throw new Error("expected 3 sample-validation record rows, saw " + recordRows.length);
            const recordTableText = recordRows.map((row) => row.textContent || "").join("\\n");
            [
              "current",
              "none",
              "stale (warning)",
              "2 missing",
              "not checked",
              "Current sample",
              "Stale sample",
              "No reconciliation sample",
            ].forEach((fragment) => {
              if (!recordTableText.includes(fragment)) throw new Error("sample-validation records table missing " + fragment + "\\n" + recordTableText);
            });
            const currentRow = recordRows.find((row) => (row.textContent || "").includes("Current sample"));
            const staleRow = recordRows.find((row) => (row.textContent || "").includes("Stale sample"));
            const noReconciliationRow = recordRows.find((row) => (row.textContent || "").includes("No reconciliation sample"));
            if (!currentRow || currentRow.dataset.status !== "match") throw new Error("current record row should be match, saw " + (currentRow && currentRow.dataset.status));
            if (!staleRow || staleRow.dataset.status !== "warning") throw new Error("stale record row should be warning, saw " + (staleRow && staleRow.dataset.status));
            if (!noReconciliationRow || noReconciliationRow.dataset.status !== "warning") throw new Error("accepted no-reconciliation record row should be warning, saw " + (noReconciliationRow && noReconciliationRow.dataset.status));
            staleRow.click();
            requireSingleSelectedRows("sample-validation-records", "Sample Validation records");
            requireText("sample-validation-detail", [
              "Record: stale-record",
              "Current evidence status: stale (warning)",
              "Missing current evidence:",
              "Completed manifest no longer contains the recorded output path.",
              "Boundary: this record is evidence only",
            ]);
            noReconciliationRow.click();
            requireText("sample-validation-detail", [
              "Record: no-reconciliation-record",
              "Current evidence status: not checked",
              "no reconciliation row is loaded for this record",
              "refresh Sample Validation",
              "Boundary: this record is evidence only",
            ]);
            requireText("sample-validation-record-review-summary", [
              "Accepted sample-validation record proof review:",
              "Selected record: current-record",
              "Rows:",
            ]);
            const fixtureRecordReviewRows = Array.from(document.querySelectorAll("#sample-validation-record-review-rows tr[data-selectable-row='true']"));
            if (fixtureRecordReviewRows.length < 6) throw new Error("expected fixture accepted record proof review rows, saw " + fixtureRecordReviewRows.length);
            const diagnosticsProofRow = fixtureRecordReviewRows.find((row) => (row.textContent || "").includes("Diagnostics/run-log proof"));
            if (!diagnosticsProofRow) throw new Error("fixture record proof review missing Diagnostics/run-log proof row");
            diagnosticsProofRow.click();
            requireSingleSelectedRows("sample-validation-record-review-rows", "Sample Validation record proof review");
            requireText("sample-validation-record-review-detail", [
              "Diagnostics/run-log proof",
              "Diagnostics evidence is supporting proof only",
              "Mutation guardrail",
            ]);
            const subtitleAudioProofRow = fixtureRecordReviewRows.find((row) => (row.textContent || "").includes("Subtitle and audio proof"));
            if (!subtitleAudioProofRow) throw new Error("fixture record proof review missing subtitle/audio proof row");
            subtitleAudioProofRow.click();
            requireText("sample-validation-record-review-detail", [
              "Subtitle and audio proof",
              "preferred-language subtitles",
              "Plex playback",
            ]);
            window.mediaPipelineCrossPageContextView.renderSampleValidationRecordPanel({ sampleValidation: { exists: false, records: [], guardrail: "No validation log loaded." } });
            const emptyRecordCell = document.querySelector("#sample-validation-records td");
            if (!emptyRecordCell || emptyRecordCell.getAttribute("colspan") !== "7") {
              throw new Error("sample-validation empty row should span 7 columns");
            }
            if (!text("sample-validation-records").includes("No sample validation records loaded.")) {
              throw new Error("sample-validation empty state text drifted: " + text("sample-validation-records"));
            }
            window.apiPost = originalApiPost;
            return {
              ok: true,
              posts,
              tauriShellRequest,
              sampleStatus: text("sample-validation-status"),
              sampleSummary: originalSampleSummary,
              cutoverSummary: originalCutoverSummary,
              cutoverDetail: originalCutoverDetail,
              sampleSetSummary: originalSampleSetSummary,
              sampleSetDetail: originalSampleSetDetail,
              executionSummary: originalExecutionSummary,
              executionSelectedDetail,
              executionDetail: originalExecutionDetail,
              sampleResult: originalSampleResult,
              recordTableText,
              noReconciliationDetail: text("sample-validation-detail"),
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
                expression: `Boolean(document.getElementById("sample-validation-summary") && document.getElementById("sample-validation-gap-summary") && document.getElementById("sample-validation-runbook-summary") && document.getElementById("sample-validation-runbook-markdown") && document.getElementById("sample-validation-cutover-summary") && document.getElementById("sample-validation-sample-set-summary") && document.getElementById("sample-validation-use-sample-set-category-button") && document.getElementById("sample-validation-execution-summary") && document.getElementById("sample-validation-worksheet-summary") && document.getElementById("sample-validation-completed-packet-summary") && document.getElementById("sample-validation-completed-packet-rows") && document.getElementById("sample-validation-acceptance-gate-summary") && document.getElementById("sample-validation-acceptance-gate-rows") && document.getElementById("sample-validation-record-review-summary") && document.getElementById("sample-validation-record-review-rows") && document.getElementById("sample-validation-category-summary") && document.getElementById("sample-validation-category-summary-rows") && document.getElementById("sample-validation-preview-button") && document.getElementById("cross-page-real-media-summary") && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationRecordPanel === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationGapSummary === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationRunbook === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationCutoverGate === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationSampleSetGuide === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationCompletedPacketHandoff === "function" && typeof window.mediaPipelineCrossPageContextView.sampleValidationCompletedPacketRows === "function" && typeof window.sampleValidationCompletedPolicyReconciliationRow === "function" && typeof window.sampleValidationCompletedPolicyReconciliationStatus === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationAcceptanceGate === "function" && typeof window.mediaPipelineCrossPageContextView.sampleValidationAcceptanceGateRows === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationRecordReview === "function" && typeof window.mediaPipelineCrossPageContextView.sampleValidationRecordReviewRows === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationCategorySummary === "function" && typeof window.mediaPipelineCrossPageContextView.sampleValidationCategorySummaryRows === "function" && typeof window.mediaPipelineCrossPageContextView.useSelectedSampleSetCategory === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationExecutionChecklist === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationWorksheets === "function" && typeof window.mediaPipelineCrossPageContextView.buildSampleValidationRequest === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("sample-validation-summary") && document.getElementById("sample-validation-gap-summary") && document.getElementById("sample-validation-runbook-summary") && document.getElementById("sample-validation-runbook-markdown") && document.getElementById("sample-validation-cutover-summary") && document.getElementById("sample-validation-sample-set-summary") && document.getElementById("sample-validation-use-sample-set-category-button") && document.getElementById("sample-validation-execution-summary") && document.getElementById("sample-validation-worksheet-summary") && document.getElementById("sample-validation-completed-packet-summary") && document.getElementById("sample-validation-completed-packet-rows") && document.getElementById("sample-validation-acceptance-gate-summary") && document.getElementById("sample-validation-acceptance-gate-rows") && document.getElementById("sample-validation-record-review-summary") && document.getElementById("sample-validation-record-review-rows") && document.getElementById("sample-validation-category-summary") && document.getElementById("sample-validation-category-summary-rows") && document.getElementById("sample-validation-preview-button") && document.getElementById("cross-page-real-media-summary") && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationRecordPanel === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationGapSummary === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationRunbook === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationCutoverGate === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationSampleSetGuide === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationCompletedPacketHandoff === "function" && typeof window.mediaPipelineCrossPageContextView.sampleValidationCompletedPacketRows === "function" && typeof window.sampleValidationCompletedPolicyReconciliationRow === "function" && typeof window.sampleValidationCompletedPolicyReconciliationStatus === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationAcceptanceGate === "function" && typeof window.mediaPipelineCrossPageContextView.sampleValidationAcceptanceGateRows === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationRecordReview === "function" && typeof window.mediaPipelineCrossPageContextView.sampleValidationRecordReviewRows === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationCategorySummary === "function" && typeof window.mediaPipelineCrossPageContextView.sampleValidationCategorySummaryRows === "function" && typeof window.mediaPipelineCrossPageContextView.useSelectedSampleSetCategory === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationExecutionChecklist === "function" && typeof window.mediaPipelineCrossPageContextView.renderSampleValidationWorksheets === "function" && typeof window.mediaPipelineCrossPageContextView.buildSampleValidationRequest === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Sample Validation WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: sampleValidationScript(),
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


def _run_browser_sample_validation_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView sample-validation smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-sample-validation-payload.json"
        runner_path = tmp / "browser-sample-validation-runner.cjs"
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
        runner_path.write_text(_browser_sample_validation_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView sample-validation smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserSampleValidationSmoke(unittest.TestCase):
    def test_real_browser_renders_sample_validation_pilot_and_preview_without_append(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView sample-validation smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, source, output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-sample-validation-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            watched = {
                source: source.read_bytes(),
                output: output.read_bytes(),
                resolved.queue_snapshot_path: resolved.queue_snapshot_path.read_bytes(),
                resolved.completed_manifest_path: resolved.completed_manifest_path.read_bytes(),
            }
            try:
                server.start()
                result = _run_browser_sample_validation_smoke(browser_path=browser_path, url=server.url)
            finally:
                server.stop()

            self.assertTrue(result["ok"])
            browser_result = result["result"]
            posts = browser_result["posts"]
            preview_posts = [entry for entry in posts if entry["path"] == "/api/sample-validation/preview"]
            forbidden_posts = [
                entry
                for entry in posts
                if any(
                    path in entry["path"]
                    for path in (
                        "/api/sample-validation/append",
                        "/api/pipeline/start",
                        "/api/audit/start",
                        "/api/rerun/start",
                        "/api/settings/save-patch",
                        "/api/rename/apply",
                        "/api/pending-publish/drain",
                    )
                )
            ]
            self.assertEqual(len(preview_posts), 1, posts)
            self.assertEqual(forbidden_posts, [], posts)
            self.assertEqual(preview_posts[0]["body"]["shell"], "webview")
            self.assertEqual(browser_result["tauriShellRequest"]["shell"], "tauri")
            self.assertIn("WebView cutover gate:", browser_result["cutoverSummary"])
            self.assertIn("generated worksheets are context only", browser_result["cutoverSummary"])
            self.assertIn("Read-only WebView cutover evidence", browser_result["cutoverSummary"])
            self.assertIn("Backend evidence availability", browser_result["cutoverDetail"])
            self.assertIn("Recommended real-media sample set:", browser_result["sampleSetSummary"])
            self.assertIn("Required categories ready:", browser_result["sampleSetSummary"])
            self.assertIn("worksheet samples are planned/context rows only", browser_result["sampleSetSummary"])
            self.assertIn("Category: H.264 remux/direct-play copy", browser_result["sampleSetDetail"])
            self.assertIn("Real-media pilot plan:", browser_result["sampleSummary"])
            self.assertIn("Operator-selected real-media sample execution:", browser_result["executionSummary"])
            self.assertIn("Phase: Post-run Completed Proof", browser_result["executionSelectedDetail"])
            self.assertIn("Owner page: Completed", browser_result["executionSelectedDetail"])
            self.assertIn("Current backend evidence:", browser_result["sampleResult"])
            self.assertIn("Status: review", browser_result["sampleResult"])
            self.assertIn("pending=yes", browser_result["sampleResult"])
            self.assertIn("Pilot evidence packet:", browser_result["sampleResult"])
            self.assertIn("Queue route proof:", browser_result["sampleResult"])
            self.assertIn("Completed output and sidecar proof:", browser_result["sampleResult"])
            self.assertIn("Read-only pilot evidence packet", browser_result["sampleResult"])
            self.assertIn("Append readiness:", browser_result["sampleResult"])
            self.assertIn("review-before-append", browser_result["sampleResult"])
            validation_log = (resolved.state_root or (root / "State")) / "Validation" / "sample_validation_log.jsonl"
            self.assertFalse(validation_log.exists())
            for path, before in watched.items():
                self.assertEqual(path.read_bytes(), before, path)
            assert_media_no_mutation(self, media_snapshot)


if __name__ == "__main__":
    unittest.main()
