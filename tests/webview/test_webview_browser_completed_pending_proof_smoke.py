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
    from .test_webview_real_media_smoke import _get_json, _write_fixture_state
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
    from test_webview_real_media_smoke import _get_json, _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_completed_pending_proof_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function completedPendingProofScript(data) {
          return `
          (async () => {
            const payload = ${JSON.stringify(data)};
            const posts = [];
            let confirmCalls = 0;
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function requireNamespaceFunction(namespaceName, name) {
              const namespace = window[namespaceName];
              if (!namespace || typeof namespace[name] !== "function") {
                throw new Error("missing namespace function " + namespaceName + "." + name);
              }
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 8000;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : ""));
            }
            let completedTabsInitialized = false;
            function ensureCompletedTabsInitialized() {
              if (completedTabsInitialized) return;
              if (window.mediaPipelineAppLifecycle?.initCompletedTabNav) {
                window.mediaPipelineAppLifecycle.initCompletedTabNav();
              }
              completedTabsInitialized = true;
            }
            function clickCompletedTab(tabId) {
              ensureCompletedTabsInitialized();
              const node = document.querySelector('.settings-tab-btn[data-completed-tab="' + tabId + '"]');
              if (!node) throw new Error("missing Completed tab " + tabId);
              node.click();
              document.querySelectorAll(".settings-tab-btn[data-completed-tab]").forEach((button) => {
                button.setAttribute("aria-selected", String(button.dataset.completedTab === tabId));
              });
              document.querySelectorAll(".settings-tab-pane[data-completed-tab]").forEach((pane) => {
                pane.classList.toggle("is-active", pane.dataset.completedTab === tabId);
              });
            }
            function requireDisplayState(id, expectedVisible) {
              const node = byId(id);
              if (!node) throw new Error("missing " + id);
              const display = window.getComputedStyle(node).display;
              const visible = display !== "none" && node.getClientRects().length > 0;
              if (visible !== expectedVisible) {
                throw new Error(id + " expected visible=" + expectedVisible + " but display was " + display + " and rect count was " + node.getClientRects().length);
              }
            }
            function requireSelectedOutputHistoryPaneActive(expectedActive) {
              const node = byId("completed-active-output-context");
              if (!node) throw new Error("missing completed-active-output-context");
              const pane = node.closest('.settings-tab-pane[data-completed-tab="history"]');
              if (!pane) throw new Error("selected output context is not inside the History tab pane");
              const active = pane.classList.contains("is-active");
              if (active !== expectedActive) throw new Error("History pane active=" + active + ", expected " + expectedActive);
            }
            [
              "renderCompleted",
              "renderPendingPublish",
              "renderCompletedPendingProof",
              "selectCompletedPendingProofRow",
              "completedPendingProofRows",
              "completedPendingProofDetailLines",
              "renderCompletedRealMediaProof",
              "completedRealMediaProofRows",
              "completedRealMediaProofDetailLines",
              "renderCompletedFinalTrust",
              "completedFinalTrustRows",
              "completedFinalTrustDetailLines",
              "requestPublishReconciliation",
              "renderPublishReconciliation",
              "selectPublishReconciliationRow",
              "publishReconciliationRows",
              "publishReconciliationDetailLines",
              "selectPendingRow",
              "pendingSelectedCompletedCorrelationRows",
              "pendingSelectedCompletedCorrelationLines",
              "pendingSampleValidationHandoffLines",
              "sampleValidationRecordComparisonRowsForPaths",
              "completedPolicyAlignmentOutputEvidence",
              "completedPolicyOutputCategorySignal",
              "pendingSampleValidationComparisonLines"
            ].forEach(requireFunction);
            [
              "completedOutputPlacement",
              "completedPlacementCounts",
              "completedFormatCounts",
              "completedFreshnessLine",
              "completedManifestIsAged",
              "renderCompletedTrustDecision",
              "renderCompletedActiveOutputContext",
              "showSelectedCompletedRow",
              "markPublishReconciliationStale",
              "renderCompletedEvidenceCopyState",
              "copyCompletedEvidencePacket",
              "requestCompletedDiagnosticsAction",
              "completedRowTrustSummaryLines",
              "completedSampleValidationComparisonLines",
              "completedDiagnosticsActionsForRow",
              "completedDiagnosticsGuidanceLines",
              "renderCompletedDiagnosticsLinks",
              "renderCompletedRepairControls",
              "requestCompletedRepairDryRun",
              "requestCompletedRepairApply"
            ].forEach((name) => requireNamespaceFunction("mediaPipelineCompletedView", name));
            const completedViewSource = await fetch("/assets/completedView.js").then((response) => response.text());
            if (completedViewSource.includes("window.completedOutputPlacement =")) {
              throw new Error("served completedView.js still contains completedOutputPlacement flat assignment");
            }
            if (completedViewSource.includes("window.completedPlacementCounts =")) {
              throw new Error("served completedView.js still contains completedPlacementCounts flat assignment");
            }
            if (completedViewSource.includes("window.completedFormatCounts =")) {
              throw new Error("served completedView.js still contains completedFormatCounts flat assignment");
            }
            if (completedViewSource.includes("window.completedFreshnessLine =")) {
              throw new Error("served completedView.js still contains completedFreshnessLine flat assignment");
            }
            if (completedViewSource.includes("window.completedManifestIsAged =")) {
              throw new Error("served completedView.js still contains completedManifestIsAged flat assignment");
            }
            if (completedViewSource.includes("window.renderCompletedTrustDecision =")) {
              throw new Error("served completedView.js still contains renderCompletedTrustDecision flat assignment");
            }
            if (completedViewSource.includes("window.renderCompletedActiveOutputContext =")) {
              throw new Error("served completedView.js still contains renderCompletedActiveOutputContext flat assignment");
            }
            if (completedViewSource.includes("window.showSelectedCompletedRow =")) {
              throw new Error("served completedView.js still contains showSelectedCompletedRow flat assignment");
            }
            if (completedViewSource.includes("window.markPublishReconciliationStale =")) {
              throw new Error("served completedView.js still contains markPublishReconciliationStale flat assignment");
            }
            if (completedViewSource.includes("window.renderCompletedEvidenceCopyState =")) {
              throw new Error("served completedView.js still contains renderCompletedEvidenceCopyState flat assignment");
            }
            if (completedViewSource.includes("window.copyCompletedEvidencePacket =")) {
              throw new Error("served completedView.js still contains copyCompletedEvidencePacket flat assignment");
            }
            if (completedViewSource.includes("window.requestCompletedDiagnosticsAction =")) {
              throw new Error("served completedView.js still contains requestCompletedDiagnosticsAction flat assignment");
            }
            if (completedViewSource.includes("window.renderCompletedDiagnosticsLinks =")) {
              throw new Error("served completedView.js still contains renderCompletedDiagnosticsLinks flat assignment");
            }
            if (completedViewSource.includes("window.completedDiagnosticsGuidanceLines =")) {
              throw new Error("served completedView.js still contains completedDiagnosticsGuidanceLines flat assignment");
            }
            if (completedViewSource.includes("window.completedDiagnosticsActionsForRow =")) {
              throw new Error("served completedView.js still contains completedDiagnosticsActionsForRow flat assignment");
            }
            if (completedViewSource.includes("window.completedSampleValidationComparisonLines =")) {
              throw new Error("served completedView.js still contains completedSampleValidationComparisonLines flat assignment");
            }
            if (completedViewSource.includes("window.completedRowTrustSummaryLines =")) {
              throw new Error("served completedView.js still contains completedRowTrustSummaryLines flat assignment");
            }

            window.confirm = () => {
              confirmCalls += 1;
              return true;
            };
            function restoreSampleValidationContext() {
              window.mediaPipelineLastCrossPageContext = { sampleValidation: payload.sampleValidation || {} };
            }
            window.apiPost = async (path, body) => {
              posts.push({ path, body });
              if (path === "/api/completed/reconcile-manifest-dry-run") {
                return {
                  ok: true,
                  severity: "info",
                  message: "Completed manifest reconcile dry-run safe.",
                  command: "completed.reconcile_manifest_dry_run",
                  data: {
                    schema_version: "desktop_repair_reconcile_dry_run.v1",
                    candidate_command: "completed.reconcile_manifest",
                    dry_run_only: true,
                    effect: "none",
                    scope: body.scope,
                    selected_row_keys: [body.row_key],
                    precondition_results: [{ name: "selected row", ok: true }],
                    diff_summary: {
                      schema_version: "desktop_repair_reconcile_diff_summary.v1",
                      candidate_count: 1,
                      would_write_count: 1,
                      would_move_count: 0,
                      would_delete_count: 0,
                    },
                    would_write_paths: ["backend-selected-completed-manifest"],
                    would_move_paths: [],
                    would_delete_paths: [],
                    would_not_touch: {
                      source_media: "hash unchanged",
                      output_media: "hash unchanged",
                      scratch_media: "not touched",
                    },
                    safe_to_apply: true,
                    mutation_route_available: true,
                    apply_route_available: true,
                    dry_run_fingerprint: "completed-manifest-fingerprint",
                    operator_confirmation_scope: "selected row only",
                    suppress_command_journal: true,
                  },
                };
              }
              if (path === "/api/completed/reconcile-manifest") {
                return {
                  ok: true,
                  severity: "info",
                  message: "Completed manifest reconcile applied.",
                  command: "completed.reconcile_manifest",
                  data: {
                    schema_version: "desktop_repair_reconcile_apply.v1",
                    candidate_command: "completed.reconcile_manifest",
                    effect: "completed-manifest-write",
                    selected_row_keys: [body.row_key],
                    applied: true,
                    blocked: false,
                    written_paths: ["backend-selected-completed-manifest"],
                    backup_paths: ["backend-selected-completed-manifest.backup"],
                    transaction_id: "completed-manifest-browser-smoke",
                    rollback_status: "not_needed",
                    dry_run_fingerprint: body.dry_run_fingerprint,
                    expected_dry_run_fingerprint: body.dry_run_fingerprint,
                    source_payload_output_unchanged: true,
                  },
                };
              }
              if (path === "/api/completed/repair-sidecar-metadata-dry-run") {
                return {
                  ok: true,
                  severity: "info",
                  message: "Completed sidecar metadata dry-run safe.",
                  command: "completed.repair_sidecar_metadata_dry_run",
                  data: {
                    schema_version: "desktop_repair_reconcile_dry_run.v1",
                    candidate_command: "completed.repair_sidecar_metadata",
                    dry_run_only: true,
                    effect: "none",
                    scope: body.scope,
                    selected_row_keys: [body.row_key],
                    precondition_results: [{ name: "selected row", ok: true }],
                    diff_summary: {
                      schema_version: "desktop_repair_reconcile_diff_summary.v1",
                      candidate_count: 1,
                      would_write_count: 1,
                      would_move_count: 0,
                      would_delete_count: 0,
                    },
                    would_write_paths: ["backend-selected-completed-sidecar"],
                    would_move_paths: [],
                    would_delete_paths: [],
                    would_not_touch: {
                      source_media: "hash unchanged",
                      output_media: "hash unchanged",
                      scratch_media: "not touched",
                    },
                    safe_to_apply: true,
                    mutation_route_available: true,
                    apply_route_available: true,
                    dry_run_fingerprint: "completed-sidecar-fingerprint",
                    operator_confirmation_scope: "selected row only",
                    suppress_command_journal: true,
                  },
                };
              }
              if (path === "/api/completed/repair-sidecar-metadata") {
                return {
                  ok: true,
                  severity: "info",
                  message: "Completed sidecar metadata repair applied.",
                  command: "completed.repair_sidecar_metadata",
                  data: {
                    schema_version: "desktop_repair_reconcile_apply.v1",
                    candidate_command: "completed.repair_sidecar_metadata",
                    effect: "completed-sidecar-json-write",
                    selected_row_keys: [body.row_key],
                    applied: true,
                    blocked: false,
                    written_paths: ["backend-selected-completed-sidecar"],
                    backup_paths: ["backend-selected-completed-sidecar.backup"],
                    transaction_id: "completed-sidecar-browser-smoke",
                    rollback_status: "not_needed",
                    dry_run_fingerprint: body.dry_run_fingerprint,
                    expected_dry_run_fingerprint: body.dry_run_fingerprint,
                    source_payload_output_unchanged: true,
                  },
                };
              }
              return { ok: true, message: "unexpected mocked post", data: { path, body } };
            };
            function isIncidentalPreferencePost(entry) {
              return entry && entry.path === "/api/ui-preferences";
            }
            restoreSampleValidationContext();

            window.renderPendingPublish(payload.pending, {});
            window.renderCompleted(payload.completed);
            const selectedCompleted = window.getSelectedCompletedRow();
            if (!selectedCompleted) throw new Error("missing completed row for repair controls");
            await waitFor(
              () => !byId("completed-reconcile-manifest-dry-run-button").disabled
                && byId("completed-reconcile-manifest-apply-button").disabled
                && !byId("completed-repair-sidecar-dry-run-button").disabled
                && byId("completed-repair-sidecar-apply-button").disabled,
              "completed repair controls ready with apply disabled",
            );
            byId("completed-reconcile-manifest-dry-run-button").click();
            await waitFor(
              () => text("completed-repair-manifest-status") === "Dry-run safe"
                && !byId("completed-reconcile-manifest-apply-button").disabled,
              "completed manifest dry-run completed",
            );
            byId("completed-reconcile-manifest-apply-button").click();
            await waitFor(
              () => text("completed-repair-manifest-status") === "Applied",
              "completed manifest apply completed",
            );
            byId("completed-repair-sidecar-dry-run-button").click();
            await waitFor(
              () => text("completed-repair-sidecar-status") === "Dry-run safe"
                && !byId("completed-repair-sidecar-apply-button").disabled,
              "completed sidecar dry-run completed",
            );
            byId("completed-repair-sidecar-apply-button").click();
            await waitFor(
              () => text("completed-repair-sidecar-status") === "Applied",
              "completed sidecar apply completed",
            );
            const expectedRepairPaths = [
              "/api/completed/reconcile-manifest-dry-run",
              "/api/completed/reconcile-manifest",
              "/api/completed/repair-sidecar-metadata-dry-run",
              "/api/completed/repair-sidecar-metadata",
            ];
            const completedRepairPosts = posts.filter((entry) => expectedRepairPaths.includes(entry.path));
            const unexpectedRepairPosts = posts.filter((entry) => !expectedRepairPaths.includes(entry.path) && !isIncidentalPreferencePost(entry));
            if (unexpectedRepairPosts.length) {
              throw new Error("completed repair controls posted unexpected paths: " + JSON.stringify(posts));
            }
            if (JSON.stringify(completedRepairPosts.map((entry) => entry.path)) !== JSON.stringify(expectedRepairPaths)) {
              throw new Error("completed repair controls posted unexpected paths: " + JSON.stringify(completedRepairPosts));
            }
            const dryRunKeys = ["limit", "reason", "row_key", "scope"];
            const applyKeys = ["confirm_apply", "dry_run_fingerprint", "limit", "reason", "row_key", "scope"];
            completedRepairPosts.forEach((entry, index) => {
              const expectedKeys = index % 2 === 0 ? dryRunKeys : applyKeys;
              const actualKeys = Object.keys(entry.body).sort();
              if (JSON.stringify(actualKeys) !== JSON.stringify(expectedKeys)) {
                throw new Error("completed repair post sent unexpected keys: " + JSON.stringify(entry));
              }
              for (const forbiddenKey of ["manifest_path", "local_file", "server_out", "source_path", "output_path", "payload_path", "patch", "sidecar_json"]) {
                if (Object.prototype.hasOwnProperty.call(entry.body, forbiddenKey)) {
                  throw new Error("completed repair post sent forbidden key " + forbiddenKey + ": " + JSON.stringify(entry.body));
                }
              }
            });
            if (completedRepairPosts[1].body.confirm_apply !== true || completedRepairPosts[3].body.confirm_apply !== true) {
              throw new Error("completed repair apply posts omitted confirm_apply=true: " + JSON.stringify(completedRepairPosts));
            }
            if (completedRepairPosts[1].body.dry_run_fingerprint !== "completed-manifest-fingerprint") {
              throw new Error("completed manifest apply used wrong fingerprint: " + JSON.stringify(completedRepairPosts[1]));
            }
            if (completedRepairPosts[3].body.dry_run_fingerprint !== "completed-sidecar-fingerprint") {
              throw new Error("completed sidecar apply used wrong fingerprint: " + JSON.stringify(completedRepairPosts[3]));
            }
            if (confirmCalls !== 2) throw new Error("completed repair applies should ask for two confirmations; confirm calls=" + confirmCalls);
            requireText("completed-repair-detail", [
              "Completed repair/reconcile controls:",
              "Source/output/scratch unchanged evidence",
              "Mutation guardrail",
            ]);
            posts.length = 0;
            confirmCalls = 0;
            restoreSampleValidationContext();
            window.renderCompletedPendingProof(payload.completed, payload.completed.rows, payload.pending);
            window.renderCompletedRealMediaProof(payload.completed, payload.completed.rows, window.getLastCompletedPendingProofRows ? window.getLastCompletedPendingProofRows() : [], payload.pending);
            window.mediaPipelineCompletedView.renderCompletedFinalTrust(payload.completed, payload.completed.rows, window.getLastCompletedPendingProofRows ? window.getLastCompletedPendingProofRows() : [], payload.pending);
            const currentCompletedRows = (payload.completed.rows || []).filter((row) => row.output_exists !== false);
            requireText("completed-count", [String(currentCompletedRows.length)]);
            requireText("completed-encode-count", [String(currentCompletedRows.filter((row) => String(row.route || "").startsWith("encode")).length)]);
            requireText("completed-remux-count", [String(currentCompletedRows.filter((row) => String(row.route || "") === "remux").length)]);
            requireText("completed-missing-count", [String((payload.completed.rows || []).filter((row) => row.output_exists === false).length)]);
            if (!document.getElementById("completed-history-rows")) throw new Error("expected Completed History table");
            if (!document.getElementById("completed-refresh-current-output-button")) throw new Error("expected Refresh Current Output Status button");
            requireText("completed-trust-decision-summary", [
              "Output trust decision:",
              "Operator outcome:",
              "Placement evidence:",
              "Pending/drain proof:",
              "Backend publish reconciliation:",
              "Mutation guardrail",
            ]);
            requireText("completed-trust-decision-chips", [
              "Trust ready",
              "Review first",
              "Investigate",
              "Evidence incomplete",
            ]);
            requireText("completed-reconciliation-hint", [
              "Backend publish reconciliation: not loaded.",
              "Advanced -> Refresh Backend Reconciliation",
              "Boundary: this hint is read-only"
            ]);
            requireText("completed-real-media-proof-summary", [
              "Real-media output proof ladder:",
              "Checkpoints loaded: 8",
              "Decision rule: output proof, sidecar proof, route/size/media decision, pending/drain posture, and diagnostics/runtime evidence must agree before trusting a sample.",
              "Phase boundary: Launch proof is pre-run intent only",
              "Mutation guardrail",
            ]);
            requireText("completed-real-media-proof-detail", [
              "Checkpoint: Output and sidecar",
              "Output path:",
              "Associated completed row:",
              "Boundary: this is operator proof support only",
            ]);
            const realMediaRows = Array.from(document.querySelectorAll("#completed-real-media-proof-rows tr[data-selectable-row='true']"));
            const transitionProofRow = realMediaRows.find((row) => row.textContent.includes("Launch-to-output transition"));
            if (!transitionProofRow) throw new Error("expected launch-to-output transition real-media proof row");
            transitionProofRow.click();
            requireText("completed-real-media-proof-detail", [
              "Checkpoint: Launch-to-output transition",
              "Pre-run proof source: Launch real-media sample proof handoff",
              "Post-run proof source: Completed output/sidecar",
              "Transition rule: Launch can prove intent before start",
              "Boundary: this is operator proof support only",
            ]);
            requireText("completed-final-trust-summary", [
              "Completed final output trust walkthrough:",
              "Decision rule: trust the selected output only after Completed Manifest, disk/sidecar state, Pending Publish/drain proof, Plex/media policy evidence, Diagnostics logs, and Sample Validation preview agree.",
              "Mutation guardrail",
            ]);
            requireText("completed-final-trust-rows", [
              "1. Selected Completed row",
              "2. Output and sidecar on disk",
              "3. Pending/drain final placement",
              "6. Sample Validation evidence",
            ]);
            const finalTrustRows = Array.from(document.querySelectorAll("#completed-final-trust-rows tr[data-selectable-row='true']"));
            const sampleValidationTrustRow = finalTrustRows.find((row) => row.textContent.includes("Sample Validation evidence"));
            if (!sampleValidationTrustRow) throw new Error("expected sample validation final trust row");
            sampleValidationTrustRow.click();
            requireText("completed-final-trust-detail", [
              "Completed final output trust walkthrough:",
              "Step: 6. Sample Validation evidence",
              "Sample Validation is evidence-only JSONL.",
              "Manual playback/subtitle/audio/size inspection remains required before acceptance.",
              "Guardrail: this walkthrough is decision support only",
            ]);
            const routeProofRow = realMediaRows.find((row) => row.textContent.includes("Route, size, and media decisions"));
            if (!routeProofRow) throw new Error("expected route/size/media real-media proof row");
            routeProofRow.click();
            requireText("completed-real-media-proof-detail", [
              "Checkpoint: Route, size, and media decisions",
              "Plex compatibility proof needs more than output existence.",
              "Audio/subtitle decisions:",
              "Boundary: this is operator proof support only",
            ]);
            const policyProofRow = realMediaRows.find((row) => row.textContent.includes("Saved policy reconciliation"));
            if (!policyProofRow) throw new Error("expected saved policy reconciliation real-media proof row");
            policyProofRow.click();
            requireText("completed-real-media-proof-detail", [
              "Checkpoint: Saved policy reconciliation",
              "Completed policy reconciliation:",
              "Policy alignment status:",
              "Category comparison rows:",
              "H.264 remux/direct-play copy",
              "completed signal=completed-route-signal",
              "Post-run boundary: Completed can prove output-side evidence only",
              "Read-only real-media policy alignment",
            ]);
            const pendingDrainProofRow = realMediaRows.find((row) => row.textContent.includes("Pending/drain proof"));
            if (!pendingDrainProofRow) throw new Error("expected pending/drain real-media proof row");
            pendingDrainProofRow.click();
            requireText("completed-real-media-proof-detail", [
              "Checkpoint: Pending/drain proof",
              "Proof order: Completed Manifest row",
              "Same-leaf matches are duplicate-title hints only.",
              "Boundary: this is operator proof support only",
            ]);
            const sampleValidationProofRow = realMediaRows.find((row) => row.textContent.includes("Sample validation handoff"));
            if (!sampleValidationProofRow) throw new Error("expected sample-validation handoff proof row");
            sampleValidationProofRow.click();
            requireText("completed-real-media-proof-detail", [
              "Checkpoint: Sample validation handoff",
              "Sample Validation handoff is evidence-only.",
              "Suggested record source_path is the selected Completed source path.",
              "Suggested record output_path is the selected Completed output path.",
              "Use Preview Record first",
              "Home Sample Validation can write JSONL evidence notes only",
              "Boundary: this is operator proof support only",
            ]);
            requireText("completed-pending-proof-status", ["Review overlaps"]);
            requireText("completed-pending-proof-summary", [
              "Completed-to-Pending output proof cross-check:",
              "Exact completed output -> pending destination: 1",
              "Proof order:",
              "Mutation guardrail",
            ]);
            const firstRow = document.querySelector("#completed-pending-proof-rows tr[data-row-key]");
            if (!firstRow) throw new Error("expected selectable completed-pending proof row");
            firstRow.click();
            requireText("completed-pending-proof-detail", [
              "Signal: Pending destination overlap",
              "Completed row:",
              "Pending Publish row:",
              "Proof order: Completed Manifest row",
              "Boundary: same-leaf matches are duplicate-title hints only",
              "Mutation guardrail",
            ]);
            requireText("completed-detail", ["Selected completed-row quick signal:"]);
            requireText("completed-detail", [
              "Sample Validation comparison for selected Completed row:",
              "Matching evidence records: 1",
              "current=1",
              "Post-run capture: Preview Record now includes a copyable",
              "Mutation guardrail: this comparison is read-only",
            ]);
            clickCompletedTab("evidence");
            requireSelectedOutputHistoryPaneActive(false);
            requireDisplayState("completed-active-output-context", false);
            clickCompletedTab("history");
            requireSelectedOutputHistoryPaneActive(true);
            clickCompletedTab("evidence");
            if (!document.getElementById("completed-copy-evidence-button")) throw new Error("expected Copy Evidence Packet button");
            let copiedEvidence = "";
            Object.defineProperty(navigator, "clipboard", {
              configurable: true,
              value: { writeText: async (text) => { copiedEvidence = String(text || ""); } }
            });
            return window.mediaPipelineCompletedView.copyCompletedEvidencePacket().then((copied) => {
              if (copied !== true) throw new Error("expected evidence packet copy to succeed");
              if (!copiedEvidence.includes("# Selected Completed Pilot Evidence Packet")) throw new Error("copied evidence packet missing markdown title");
              requireText("completed-copy-evidence-status", [
                "Copied evidence packet.",
                "did not append evidence",
                "touch media"
              ]);
              return true;
            }).then(() => {
              Object.defineProperty(navigator, "clipboard", {
                configurable: true,
                value: { writeText: async () => { throw new Error("clipboard denied"); } }
              });
              return window.mediaPipelineCompletedView.copyCompletedEvidencePacket();
            }).then((copied) => {
              if (copied !== false) throw new Error("expected evidence packet copy failure");
              requireText("completed-copy-evidence-status", ["Copy failed: clipboard denied"]);
              const copyButton = byId("completed-copy-evidence-button");
              if (!copyButton || copyButton.disabled) throw new Error("copy button should remain enabled while packet text exists after copy failure");
              byId("completed-pilot-evidence-markdown").textContent = "No copyable pilot evidence packet loaded.";
              window.mediaPipelineCompletedView.renderCompletedEvidenceCopyState();
              if (!copyButton.disabled) throw new Error("copy button should disable when no evidence packet text exists");
              return window.mediaPipelineCompletedView.copyCompletedEvidencePacket();
            }).then((copied) => {
              if (copied !== false) throw new Error("empty evidence copy should return false");
              requireText("completed-copy-evidence-status", ["No evidence packet text is available to copy."]);
              window.renderCompleted(payload.completed);
              window.renderCompletedPendingProof(payload.completed, payload.completed.rows, payload.pending);
              return true;
            }).then(() => {

            const firstCompletedOutput = String((payload.completed.rows[0] || {}).output_path || "");
            const normalizedFirstCompletedOutput = firstCompletedOutput.replace(/\\//g, "\\\\").replace(/\\\\+/g, "\\\\").toLowerCase();
            const selectedPending = (payload.pending.rows || []).find((row) => {
              const destination = String(row.server_out || row.destination_path || row.output_path || "");
              const normalizedDestination = destination.replace(/\\//g, "\\\\").replace(/\\\\+/g, "\\\\").toLowerCase();
              return normalizedDestination && normalizedDestination === normalizedFirstCompletedOutput;
            }) || payload.pending.rows[0] || {};
            window.selectPendingRow(selectedPending);
            requireText("pending-detail", [
              "Completed Manifest correlation for selected pending row:",
              "Exact pending destination -> completed output: 1",
              "Proof order: exact normalized destination/source path matches are stronger",
              "Boundary: same-leaf matches are duplicate-title hints only",
              "Sample Validation handoff: Pending Publish",
              "Suggested pilot category: deferred-publish",
              "Home Sample Validation can write JSONL evidence notes only",
              "Sample Validation comparison for selected Pending Publish row:",
              "Matching evidence records: 1",
              "current=1",
              "Post-run capture: Preview Record includes pending/final-placement proof rows",
              "Mutation guardrail: this pending-row correlation",
            ]);
            const exactCorrelation = window.mediaPipelinePendingPublishView.pendingSelectedCompletedCorrelationRows(selectedPending);
            if (!exactCorrelation.exactDestination.length) {
              throw new Error("expected selected Pending row to have exact Completed output correlation");
            }

            const reconciliationPromise = window.mediaPipelineCompletedView.requestPublishReconciliation();
            requireText("publish-reconciliation-status", ["Loading"]);
            requireText("publish-reconciliation-summary", ["Previous reconciliation rows are hidden"]);
            requireText("publish-reconciliation-rows", ["previous proof rows are hidden"]);
            return reconciliationPromise.then(() => {
              requireText("publish-reconciliation-status", ["Review overlaps"]);
              requireText("completed-reconciliation-hint", ["Backend publish reconciliation:", "Use Advanced"]);
              requireText("publish-reconciliation-summary", [
                "Backend publish reconciliation:",
                "Exact completed output -> pending destination: 1",
                "Exact completed source -> pending source: 1",
                "Proof order:",
                "Mutation guardrail: this backend evidence endpoint is read-only",
              ]);
              const backendRow = document.querySelector("#publish-reconciliation-rows tr[data-row-key]");
              if (!backendRow) throw new Error("expected selectable backend reconciliation row");
              backendRow.click();
              requireText("publish-reconciliation-detail", [
                "Backend publish reconciliation row:",
                "Signal:",
                "Completed row:",
                "Pending Publish row:",
                "Proof order: Completed Manifest row",
                "Mutation guardrail: this backend row",
              ]);
              window.mediaPipelineCompletedView.markPublishReconciliationStale("Smoke test refreshed Completed output status after reconciliation.");
              requireText("publish-reconciliation-status", ["Stale"]);
              requireText("publish-reconciliation-summary", ["Stale snapshot:", "Refresh Backend Reconciliation"]);
              requireText("completed-reconciliation-hint", ["Backend publish reconciliation: stale."]);
              requireText("completed-trust-decision-summary", ["publish reconciliation stale"]);
              const staleBackendRow = document.querySelector("#publish-reconciliation-rows tr[data-row-key]");
              if (staleBackendRow && staleBackendRow.dataset.status !== "stale") {
                throw new Error("stale reconciliation rows should be visibly marked stale");
              }
              window.renderPublishReconciliation({ status: "error", rows: [], summary_lines: ["Backend publish reconciliation failed: smoke error"] });
              requireText("publish-reconciliation-status", ["Error"]);
              requireText("publish-reconciliation-summary", ["smoke error"]);
              requireText("publish-reconciliation-rows", ["Backend reconciliation failed."]);
              return true;
            }).then(() => {
            const sameLeafCompleted = JSON.parse(JSON.stringify(payload.completed));
            const pendingLeaf = String(selectedPending.server_out || selectedPending.local_file || "sample.mkv")
              .split(/[\\\\/]/)
              .filter(Boolean)
              .pop() || "sample.mkv";
            sameLeafCompleted.rows = [Object.assign({}, sameLeafCompleted.rows[0] || {}, {
              row_key: "same-leaf-completed-output",
              output_path: "C:/Different/Output/" + pendingLeaf,
              source_path: "C:/Different/Source/source-" + pendingLeaf,
              output_file: pendingLeaf
            })];
            sameLeafCompleted.count = 1;
            window.renderCompleted(sameLeafCompleted);
            window.selectPendingRow(selectedPending);
            requireText("pending-detail", [
              "Completed Manifest correlation for selected pending row:",
              "Exact pending destination -> completed output: 0",
              "Same-leaf completed output hints: 1",
              "Boundary: same-leaf matches are duplicate-title hints only",
            ]);
            window.renderCompleted(payload.completed);
            window.selectPendingRow(selectedPending);

            const missingDrainedCompleted = JSON.parse(JSON.stringify(payload.completed));
            const drainedBase = missingDrainedCompleted.rows[0] || {};
            const missingDrainedOutput = String(drainedBase.output_path || "missing-output.mkv") + ".drained.mkv";
            const missingDrainedSource = String(drainedBase.source_path || "missing-source.mkv") + ".drained-source.mkv";
            missingDrainedCompleted.rows = [Object.assign({}, drainedBase, {
              row_key: "completed-missing-with-drain-proof",
              output_path: missingDrainedOutput,
              source_path: missingDrainedSource,
              output_file: "Missing Drained Example.mkv",
              output_exists: false,
              output_health: "missing output",
              operator_trust_state: "broken-output",
              consistency_status: "broken",
              consistency_issues: ["missing_output"]
            })];
            missingDrainedCompleted.count = 1;
            const missingDrainedPending = {
              rows: [],
              count: 0,
              drain_summary: {
                exists: true,
                started_at: "2026-05-15T02:30:00Z",
                completed_at: "2026-05-15T02:31:00Z",
                items: [{
                  status: "succeeded",
                  server_out: missingDrainedOutput,
                  source_path: missingDrainedSource,
                  local_file: String(selectedPending.local_file || "pending-payload.mkv") + ".drained"
                }]
              }
            };
            window.renderCompleted(missingDrainedCompleted);
            window.renderCompletedPendingProof(missingDrainedCompleted, missingDrainedCompleted.rows, missingDrainedPending);
            window.renderCompleted(missingDrainedCompleted);
            requireText("completed-pending-proof-status", ["Review final placement"]);
            requireText("completed-pending-proof-summary", [
              "Missing completed output with drain proof: 2",
              "final-placement conflict",
              "Mutation guardrail",
            ]);
            const drainedPlacementLabels = (missingDrainedCompleted.rows || []).map((row) => window.mediaPipelineCompletedView.completedOutputPlacement(row, window.getLastCompletedPendingProofRows ? window.getLastCompletedPendingProofRows() : []).label);
            if (!drainedPlacementLabels.includes("Missing: drain proof")) throw new Error("expected a missing-output row with drain proof placement");
            requireText("completed-history-rows", ["Missing: drain proof"]);
            const finalPlacementRows = Array.from(document.querySelectorAll("#completed-pending-proof-rows tr[data-row-key]"));
            const finalPlacementRow = finalPlacementRows.find((row) => row.textContent.includes("Missing output with drain proof"));
            if (!finalPlacementRow) throw new Error("expected missing-output-with-drain-proof row");
            finalPlacementRow.click();
            requireText("completed-pending-proof-detail", [
              "Signal: Missing output with drain proof",
              "Completed row reports a missing output, but exact durable drain-summary proof exists",
              "Treat as final-placement conflict",
              "Durable drain summary item:",
              "Mutation guardrail",
            ]);

            const brokenCompleted = JSON.parse(JSON.stringify(payload.completed));
            const base = brokenCompleted.rows[0] || {};
            brokenCompleted.rows = [Object.assign({}, base, {
              row_key: "completed-missing-no-pending-proof",
              output_path: String(base.output_path || "missing-output.mkv") + ".missing.mkv",
              output_file: "Missing Example.mkv",
              output_exists: false,
              output_health: "missing output",
              operator_trust_state: "broken-output",
              consistency_status: "broken",
              consistency_issues: ["missing_output"]
            })];
            brokenCompleted.count = 1;
            window.renderCompleted(brokenCompleted);
            window.renderCompletedPendingProof(brokenCompleted, brokenCompleted.rows, { rows: [], count: 0 });
            window.renderCompleted(brokenCompleted);
            const noProofPlacementLabels = (brokenCompleted.rows || []).map((row) => window.mediaPipelineCompletedView.completedOutputPlacement(row, window.getLastCompletedPendingProofRows ? window.getLastCompletedPendingProofRows() : []).label);
            if (!noProofPlacementLabels.includes("Missing: no proof")) throw new Error("expected a missing-output row with no-proof placement");
            requireText("completed-history-rows", ["Missing: no proof"]);
            window.renderCompletedRealMediaProof(brokenCompleted, brokenCompleted.rows, window.getLastCompletedPendingProofRows ? window.getLastCompletedPendingProofRows() : [], { rows: [], count: 0 });
            window.mediaPipelineCompletedView.renderCompletedFinalTrust(brokenCompleted, brokenCompleted.rows, window.getLastCompletedPendingProofRows ? window.getLastCompletedPendingProofRows() : [], { rows: [], count: 0 });
            requireText("completed-real-media-proof-status", ["Blocked proof"]);
            requireText("completed-real-media-proof-summary", [
              "Real-media output proof ladder:",
              "Blocked checkpoints:",
              "First action: stop treating this sample as proof",
              "Mutation guardrail",
            ]);
            const brokenRealMediaRows = Array.from(document.querySelectorAll("#completed-real-media-proof-rows tr[data-selectable-row='true']"));
            const brokenOutputProofRow = brokenRealMediaRows.find((row) => row.textContent.includes("Output and sidecar"));
            if (!brokenOutputProofRow) throw new Error("expected broken output/sidecar real-media proof row");
            brokenOutputProofRow.click();
            requireText("completed-real-media-proof-detail", [
              "Checkpoint: Output and sidecar",
              "output=missing",
              "Open Completed Manifest, output folder, sidecar, Run Logs, and Last Stderr before rerun or cleanup.",
              "Boundary: this is operator proof support only",
            ]);
            requireText("completed-final-trust-status", ["Blocked trust"]);
            requireText("completed-final-trust-summary", [
              "Completed final output trust walkthrough:",
              "First action: stop before acceptance",
              "Mutation guardrail",
            ]);
            const brokenTrustRows = Array.from(document.querySelectorAll("#completed-final-trust-rows tr[data-selectable-row='true']"));
            const brokenDiskTrustRow = brokenTrustRows.find((row) => row.textContent.includes("Output and sidecar on disk"));
            if (!brokenDiskTrustRow) throw new Error("expected broken output/sidecar final trust row");
            brokenDiskTrustRow.click();
            requireText("completed-final-trust-detail", [
              "Step: 2. Output and sidecar on disk",
              "Open Completed Manifest, output folder, sidecar, Run Logs, and Last Stderr",
              "Guardrail: this walkthrough is decision support only",
            ]);
            requireText("completed-pending-proof-status", ["Review blockers"]);
            requireText("completed-pending-proof-summary", [
              "Missing completed output without pending/drain proof: 1",
              "empty Pending Publish is not proof of publish",
              "Mutation guardrail",
            ]);
            const blockedRow = document.querySelector("#completed-pending-proof-rows tr[data-row-key]");
            if (!blockedRow) throw new Error("expected missing-output proof blocker row");
            blockedRow.click();
            requireText("completed-pending-proof-detail", [
              "Signal: Missing output without pending proof",
              "Completed row:",
              "Output health: missing output",
              "an empty Pending Publish page is not proof that the file published",
              "Mutation guardrail",
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
            if (forbiddenPosts.length) throw new Error("completed-pending proof smoke posted forbidden routes: " + JSON.stringify(forbiddenPosts));
            const unexpectedPosts = posts.filter((entry) => !isIncidentalPreferencePost(entry));
            if (unexpectedPosts.length !== 0) throw new Error("completed-pending proof smoke unexpectedly posted commands: " + JSON.stringify(posts));
            return {
              ok: true,
              status: text("completed-pending-proof-status"),
              summary: text("completed-pending-proof-summary"),
              detail: text("completed-pending-proof-detail"),
              backendReconciliationStatus: text("publish-reconciliation-status"),
              backendReconciliationSummary: text("publish-reconciliation-summary"),
              backendReconciliationDetail: text("publish-reconciliation-detail"),
              realMediaProofStatus: text("completed-real-media-proof-status"),
              realMediaProofSummary: text("completed-real-media-proof-summary"),
              realMediaProofDetail: text("completed-real-media-proof-detail"),
              finalTrustStatus: text("completed-final-trust-status"),
              finalTrustSummary: text("completed-final-trust-summary"),
              finalTrustDetail: text("completed-final-trust-detail"),
              pendingDetail: text("pending-detail"),
              postCount: posts.length
            };
            });
            });
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
                expression: `Boolean(document.getElementById("completed-pending-proof-detail") && document.getElementById("completed-real-media-proof-detail") && document.getElementById("completed-final-trust-detail") && document.getElementById("publish-reconciliation-detail") && typeof window.renderCompleted === "function" && typeof window.renderPendingPublish === "function" && typeof window.renderCompletedPendingProof === "function" && typeof window.renderCompletedRealMediaProof === "function" && typeof window.mediaPipelineCompletedView.renderCompletedFinalTrust === "function" && typeof window.mediaPipelineCompletedView.completedRealMediaProofRows === "function" && typeof window.mediaPipelineCompletedView.completedFinalTrustRows === "function" && typeof window.mediaPipelinePendingPublishView.pendingSelectedCompletedCorrelationLines === "function" && typeof window.mediaPipelineCompletedView.requestPublishReconciliation === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("completed-pending-proof-detail") && document.getElementById("completed-real-media-proof-detail") && document.getElementById("completed-final-trust-detail") && document.getElementById("publish-reconciliation-detail") && typeof window.renderCompleted === "function" && typeof window.renderPendingPublish === "function" && typeof window.renderCompletedPendingProof === "function" && typeof window.renderCompletedRealMediaProof === "function" && typeof window.mediaPipelineCompletedView.renderCompletedFinalTrust === "function" && typeof window.mediaPipelineCompletedView.completedRealMediaProofRows === "function" && typeof window.mediaPipelineCompletedView.completedFinalTrustRows === "function" && typeof window.mediaPipelinePendingPublishView.pendingSelectedCompletedCorrelationLines === "function" && typeof window.mediaPipelineCompletedView.requestPublishReconciliation === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) {
              throw new Error("WebView Completed/Pending proof globals or DOM nodes did not become ready.");
            }
            const result = await client.send("Runtime.evaluate", {
              expression: completedPendingProofScript(payload.data),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const detail = result.exceptionDetails;
              const exception = detail.exception || {};
              throw new Error([
                detail.text || "browser evaluation failed",
                exception.description || exception.value || "",
              ].filter(Boolean).join("\\n"));
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


def _run_browser_completed_pending_proof_smoke(
    *,
    browser_path: str,
    url: str,
    completed: dict[str, object],
    pending: dict[str, object],
    sample_validation: dict[str, object] | None = None,
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed Completed/Pending proof smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-completed-pending-proof-payload.json"
        runner_path = tmp / "browser-completed-pending-proof-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "data": {
                        "completed": completed,
                        "pending": pending,
                        "sampleValidation": sample_validation or {},
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_completed_pending_proof_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Completed/Pending proof smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=45,
        )


class WebViewBrowserCompletedPendingProofSmoke(unittest.TestCase):
    def test_real_browser_renders_completed_pending_proof_overlap_and_missing_output_detail(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Completed/Pending proof smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                completed_status, completed = _get_json(f"{server.url}/api/completed", token="browser-smoke-token")
                pending_status, pending = _get_json(f"{server.url}/api/pending-publish", token="browser-smoke-token")
                self.assertEqual(completed_status, 200)
                self.assertEqual(pending_status, 200)
                self.assertGreaterEqual(len(completed.get("rows", [])), 1)
                self.assertGreaterEqual(len(pending.get("rows", [])), 1)
                first_completed = completed["rows"][0]
                sample_validation = {
                    "exists": True,
                    "record_count": 1,
                    "records": [
                        {
                            "record_id": "sample-record-current",
                            "created_at": "2026-05-15T22:00:00-04:00",
                            "operator_decision": "accepted",
                            "sample_category": "deferred-publish",
                            "proof_strength": "exact-path",
                            "sample_label": first_completed.get("output_file") or first_completed.get("lookup_title") or "sample",
                            "source_path": first_completed.get("source_path", ""),
                            "output_path": first_completed.get("output_path", ""),
                        }
                    ],
                    "summary": {"record_count": 1},
                    "policy_alignment": {
                        "schema_version": "desktop_real_media_policy_alignment.v1",
                        "operator_status": "ready-looking",
                        "policy_ready": True,
                        "required_ready_count": 4,
                        "required_count": 4,
                        "ready_count": 5,
                        "review_count": 0,
                        "blocked_count": 0,
                        "missing_count": 0,
                        "rows": [
                            {
                                "category_key": "h264-remux-safe",
                                "category": "H.264 remux/direct-play copy",
                                "required": True,
                                "status": "ready",
                                "severity": "info",
                                "evidence": "Routing / Output Size Check: H.264 remux-safe; Source preservation: copy-to-scratch.",
                                "safe_next_action": "Confirm completed route stayed remux/copy.",
                            },
                            {
                                "category_key": "subtitle-srt-generation",
                                "category": "Preferred-language subtitle to SRT",
                                "required": True,
                                "status": "ready",
                                "severity": "info",
                                "evidence": "Subtitle language routing: preferred language; TX3G / mov_text SRT: enabled.",
                                "safe_next_action": "Confirm Completed subtitle evidence.",
                            },
                            {
                                "category_key": "audio-routing",
                                "category": "Audio routing/default language",
                                "required": True,
                                "status": "ready",
                                "severity": "info",
                                "evidence": "Audio language / default track: preferred; Audio passthrough / channels: configured.",
                                "safe_next_action": "Confirm Completed audio evidence.",
                            },
                            {
                                "category_key": "encode-size-policy",
                                "category": "Encode and size policy",
                                "required": True,
                                "status": "ready",
                                "severity": "info",
                                "evidence": "Routing / Output Size Check: advisory Output Size Check enabled.",
                                "safe_next_action": "Confirm Completed size policy evidence.",
                            },
                            {
                                "category_key": "deferred-publish",
                                "category": "Deferred publish/final placement",
                                "required": False,
                                "status": "ready",
                                "severity": "info",
                                "evidence": "Publish / recovery safety: deferred publish enabled.",
                                "safe_next_action": "Confirm Pending Publish or drain proof.",
                            },
                        ],
                        "summary_lines": ["Real-media policy alignment: ready-looking"],
                        "guardrail": "Read-only real-media policy alignment.",
                    },
                    "reconciliation": {
                        "operator_status": "current",
                        "rows": [
                            {
                                "record_id": "sample-record-current",
                                "status": "current",
                                "severity": "info",
                                "missing_current_evidence": [],
                                "evidence": "completed_output=yes; diagnostics=yes; pending=yes",
                                "safe_next_action": "Matching sample validation proof is current.",
                            }
                        ],
                    },
                }
                result = _run_browser_completed_pending_proof_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    completed=completed,
                    pending=pending,
                    sample_validation=sample_validation,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertEqual(browser_result["status"], "Review blockers")
        self.assertIn("Missing completed output without pending/drain proof: 1", browser_result["summary"])
        self.assertIn("Signal: Missing output without pending proof", browser_result["detail"])
        self.assertEqual(browser_result["realMediaProofStatus"], "Blocked proof")
        self.assertIn("Real-media output proof ladder:", browser_result["realMediaProofSummary"])
        self.assertIn("Checkpoint: Output and sidecar", browser_result["realMediaProofDetail"])
        self.assertIn("output=missing", browser_result["realMediaProofDetail"])
        self.assertIn("Completed Manifest correlation for selected pending row:", browser_result["pendingDetail"])
        self.assertIn("Mutation guardrail: this pending-row correlation", browser_result["pendingDetail"])
        self.assertEqual(browser_result["postCount"], 0)


if __name__ == "__main__":
    unittest.main()
