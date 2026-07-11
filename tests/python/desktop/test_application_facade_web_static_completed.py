from __future__ import annotations

import unittest

from tests.python.desktop.application_facade_test_support import (
    assert_namespace_export as _assert_namespace_export,
    served_webview_static_contract_bundle,
)


def _completed_page_html(html: str) -> str:
    start = html.index('data-page-panel="completed"')
    end = html.find('data-page-panel="pending"', start)
    return html[start : end if end != -1 else len(html)]


def _assert_contains_all(testcase: unittest.TestCase, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        with testcase.subTest(snippet=snippet):
            testcase.assertIn(snippet, text)


def _assert_not_contains_any(testcase: unittest.TestCase, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        with testcase.subTest(snippet=snippet):
            testcase.assertNotIn(snippet, text)


class ApplicationFacadeWebStaticCompletedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = served_webview_static_contract_bundle()

    def test_completed_page_dom_contract_is_static_pinned(self) -> None:
        bundle = self.bundle
        completed_page_html = _completed_page_html(bundle.html)

        _assert_contains_all(
            self,
            bundle.html,
            (
                'data-page-panel="completed"',
                "completed-filter",
                "completed-rows",
                "completed-history-filter",
                "completed-history-rows",
                "completed-refresh-current-output-button",
                "output-overview-section-current",
                "output-overview-section-history",
                "completed-current-at-a-glance",
                "completed-current-filter-line",
                "completed-current-details",
                "completed-summary",
                'id="completed-breakdown-status"',
                'id="completed-breakdown"',
                'id="completed-consistency-status"',
                'id="completed-consistency"',
                "completed-integrity-status",
                "completed-integrity",
                "completed-validation-status",
                "completed-validation",
                "completed-workflow-status",
                "completed-workflow",
                "/assets/completed/evidence/pendingProofModel.js",
                "/assets/completed/evidence/pendingProofView.js",
                "/assets/completed/proof/pilotEvidence.js",
                'id="completed-size-evidence-status"',
                'id="completed-size-evidence-summary"',
                'id="completed-size-evidence-rows"',
                'id="completed-size-evidence-detail"',
                'id="completed-pending-proof-status"',
                'id="completed-pending-proof-summary"',
                'id="completed-pending-proof-rows"',
                'id="completed-pending-proof-detail"',
                'id="publish-reconciliation-status"',
                'id="publish-reconciliation-refresh-button"',
                'id="publish-reconciliation-summary"',
                'id="publish-reconciliation-rows"',
                'id="publish-reconciliation-detail"',
                "Publish Reconciliation",
                'id="completed-final-trust-status"',
                'id="completed-final-trust-summary"',
                'id="completed-final-trust-rows"',
                'id="completed-final-trust-detail"',
                'id="completed-pilot-evidence-status"',
                'id="completed-pilot-evidence-summary"',
                'id="completed-pilot-evidence-rows"',
                'id="completed-pilot-evidence-detail"',
                'id="completed-pilot-evidence-markdown"',
                'id="completed-output-acceptance-status"',
                'id="completed-output-acceptance-summary"',
                'id="completed-output-acceptance-rows"',
                'id="completed-output-acceptance-detail"',
                'id="completed-route-agreement-status"',
                'id="completed-route-agreement-summary"',
                'id="completed-route-agreement-rows"',
                'id="completed-route-agreement-detail"',
                'id="completed-detail" class="prose-block" data-visual-keep="copy-output"',
                "completed-diagnostics-status",
                "completed-diagnostics-guidance",
                "completed-diagnostics-actions",
                "completed-clear-filters-button",
                "completed-open-history",
                'id="completed-open-history" class="prose-block completed-open-history-block" hidden aria-hidden="true"',
                "Media And Route Proof",
                "Output Verification",
                "Evidence Packet",
                "Route Agreement",
                "Manifest Check",
                "Output Checklist",
                "Run History",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.html,
            (
                "completed-review-status",
                "completed-review-board",
                "completed-review-rows",
                "completed-review-legend",
                "completed-size-review-status",
                "completed-size-review-summary",
                "completed-size-review-rows",
            ),
        )
        _assert_contains_all(
            self,
            completed_page_html,
            (
                "completed-current-row-actions",
                'data-open-target-row-actions="completed"',
                '<details id="completed-current-details" class="completed-current-details">',
                '<pre id="completed-current-summary" class="completed-current-detail-text">',
                '<pre id="completed-filter-summary" class="completed-current-detail-text">',
            ),
        )
        self.assertLess(
            completed_page_html.index('id="completed-table-legend"'),
            completed_page_html.index('data-open-target-row-actions="completed"'),
        )
        self.assertLess(
            completed_page_html.index('data-open-target-row-actions="completed"'),
            completed_page_html.index("<h2>Why This Output Looks Different</h2>"),
        )
        self.assertLess(
            completed_page_html.index('id="completed-open-status"'),
            completed_page_html.index("<h2>Why This Output Looks Different</h2>"),
        )
        self.assertLess(
            completed_page_html.index('<h2 id="completed-current-output-heading">Current Output Status</h2>'),
            completed_page_html.index("<h2>Why This Output Looks Different</h2>"),
        )
        self.assertLess(
            completed_page_html.index("<h2>Why This Output Looks Different</h2>"),
            completed_page_html.index("<h2>Repair/Reconcile</h2>"),
        )

    def test_completed_view_namespace_and_module_wiring_is_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.completed_view_js,
            (
                "window.mediaPipelineCompletedView",
                "function renderCompleted",
                "renderCompletedRows = completedReviewNoop",
                "const completedEvidenceModule = window.__completedViewEvidenceModule || {}",
                "delete window.__completedViewEvidenceModule",
                "createCompletedEvidenceModule({",
                "commandHistoryCommandText: window.mediaPipelineCommandHistory?.commandHistoryCommandText",
                "commandHistoryIssueLevel: window.mediaPipelineCommandHistory?.commandHistoryIssueLevel",
                "commandHistoryOwnerPage: window.mediaPipelineCommandHistory?.commandHistoryOwnerPage",
                "commandHistorySuggestedAction: window.mediaPipelineCommandHistory?.commandHistorySuggestedAction",
                "const completedProofModule = window.__completedViewProofModule || {}",
                "delete window.__completedViewProofModule",
                "createCompletedProofModule({",
                "const completedReviewModule = window.__completedViewReviewModule || {}",
                "delete window.__completedViewReviewModule",
                "createCompletedReviewModule({",
                "const completedDiagnosticsModule = window.__completedViewDiagnosticsModule || {}",
                "delete window.__completedViewDiagnosticsModule",
                "available_open_target_counts",
                "Operator statuses:",
                "Operator severities:",
                "Backend trust states:",
                "Rows needing review:",
                "Rows over +5% output growth:",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.completed_view_js,
            (
                "window.renderCompleted = renderCompleted",
                "window.selectCompletedRow = selectCompletedRow",
                "window.renderCompletedPendingProof = renderCompletedPendingProof",
                "window.selectCompletedFinalTrustStep = selectCompletedFinalTrustStep",
                "window.completedReviewRows = completedReviewRows",
                "window.renderCompletedPilotEvidencePacket = renderCompletedPilotEvidencePacket",
                "window.renderCompletedRealMediaProof = renderCompletedRealMediaProof",
                "window.renderCompletedOutputAcceptance = renderCompletedOutputAcceptance",
                "window.resetCompletedFilters = resetCompletedFilters",
                "commandHistoryCommandText: window.commandHistoryCommandText",
                "commandHistoryIssueLevel: window.commandHistoryIssueLevel",
                "commandHistoryOwnerPage: window.commandHistoryOwnerPage",
                "commandHistorySuggestedAction: window.commandHistorySuggestedAction",
            ),
        )
        _assert_contains_all(
            self,
            bundle.js,
            (
                "window.mediaPipelineCompletedView?.renderCompleted?.(values.completed)",
                'targetDataset: "openCompleted"',
                "Play Output",
                "play_output_file",
                "publishReconciliationRefreshButton.addEventListener(\"click\", () => window.mediaPipelineCompletedView?.requestPublishReconciliation?.())",
                "completedClearFiltersButton.addEventListener(\"click\", () => window.mediaPipelineCompletedView?.resetCompletedFilters?.())",
            ),
        )
        self.assertIn("window.mediaPipelineCompletedView?.renderCompleted?.(completed)", bundle.app_refresh_js)
        self.assertNotIn("renderCompleted(values.completed)", bundle.js)
        self.assertNotIn("renderCompleted(completed)", bundle.app_refresh_js)
        _assert_namespace_export(self, bundle.completed_view_js, "mediaPipelineCompletedView", "selectCompletedRow")
        _assert_namespace_export(self, bundle.completed_view_js, "mediaPipelineCompletedView", "renderCompletedPendingProof")
        _assert_namespace_export(self, bundle.completed_view_js, "mediaPipelineCompletedView", "selectCompletedFinalTrustStep")
        _assert_namespace_export(self, bundle.completed_view_js, "mediaPipelineCompletedView", "completedReviewRows")
        _assert_namespace_export(self, bundle.completed_view_js, "mediaPipelineCompletedView", "renderCompletedPilotEvidencePacket")
        _assert_namespace_export(self, bundle.completed_view_js, "mediaPipelineCompletedView", "renderCompletedRealMediaProof")
        _assert_namespace_export(self, bundle.completed_view_js, "mediaPipelineCompletedView", "renderCompletedOutputAcceptance")
        _assert_namespace_export(self, bundle.completed_view_js, "mediaPipelineCompletedView", "resetCompletedFilters")

    def test_completed_review_contract_surfaces_operator_evidence(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.completed_view_review_js,
            (
                "Output review:",
                "function renderCompletedIntegrity",
                "function renderCompletedBreakdown",
                "function renderCompletedRuntime",
                "function completedIntegrityStatus",
                "function completedIntegrityLines",
                "function completedBreakdownLines",
                "function completedRuntimeLines",
                "function renderCompletedConsistency",
                "function completedConsistencyStatus",
                "function completedConsistencyLines",
                "function renderCompletedValidation",
                "function renderCompletedReviewBoard",
                "function completedReviewBoardLines",
                "Operator review board: Completed",
                "function renderCompletedSizeReview",
                "function completedSizeReviewRows",
                "function completedSizeReviewLines",
                "Size growth review board:",
                "function renderCompletedSizeEvidence",
                "function completedSizeEvidenceRows",
                "Size growth evidence handoff:",
                "Size growth may be intentional for compatibility, subtitles, or audio normalization",
                "exact full-path proof beats same-leaf review",
                "function completedSampleValidationComparisonLines",
                "Sample Validation comparison for selected Completed row:",
                "Post-run capture: Preview Record now includes a copyable route/output/log/publish/subtitle/audio/size checklist",
                "function completedValidationChecklistLines",
                "function completedRowReviewChecklistLines",
                "function completedRowIssueDigestLines",
                "function completedRowCombinedReviewPlanLines",
                "function completedSelectedQuickSignalLines",
                "function completedFilterVisibilityLines",
                "function completedFocusedInvestigationLabels",
                "function completedInvestigationSignalLines",
                "Consistency statuses:",
                "Missing sidecars:",
                "Output/sidecar mismatches:",
                "COMPLETED_READ_ONLY_BOUNDARY",
                "Manifest age",
                "History aged",
                "Real-media validation checklist:",
                "desktop_validation_state.v1",
                "Proof boundary: this checklist does not run ffprobe, hash files, or mark playback accepted.",
                "Selected completed-row review checklist:",
                "Selected completed-row quick signal:",
                "Current filter visibility:",
                "Hidden by current filters:",
                "Selected completed issue digest:",
                "Combined completed-row review plan:",
                "Completed Manifest",
                "Route/size proof",
                "Guardrail: this combined plan is read-only and cannot repair manifests",
                "Investigation view matches:",
                "investigation views are display filters only and do not repair manifests",
                "function completedRealMediaTraceLines",
                "Real-media sample trace: Completed",
                "What remains unproven: final publish success when output is parked",
                "Safe next action: inspect Completed Manifest, Pending Publish, output folder, Run Logs, and Last Stderr before rerun.",
                "Safe next action: compare route metadata and logs before accepting this output as intentional compatibility growth.",
                "Mutation guardrail: read-only evidence; backend routes own output and manifest changes.",
                "Select a completed row to see output, sidecar, size-growth",
                "function completedRowTrustSummaryLines",
                "review-before-rerun-or-cleanup",
                "delete outputs, rerun sources, repair manifests",
                "Audio/subtitle decisions:",
                "Output track verifier:",
                "verifier mismatch:",
                "Rows with exact source/output runtime history:",
                "Runtime outcome matches:",
                "Stale history is shown only as context.",
            ),
        )

    def test_completed_evidence_contract_surfaces_publish_and_acceptance_proof(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.completed_view_evidence_js,
            (
                "function createCompletedEvidenceModule",
                "window.__completedViewEvidenceModule",
                "function createCompletedPendingProofModel",
                "window.__completedPendingProofModelModule",
                "function createCompletedPendingProofViewModule",
                "window.__completedPendingProofViewModule",
                "function renderCompletedPendingProof",
                "function completedPendingProofRows",
                "function completedPendingProofDetailLines",
                "function selectCompletedPendingProofRow",
                "function renderPublishReconciliation",
                "function requestPublishReconciliation",
                "function publishReconciliationRows",
                "function publishReconciliationDetailLines",
                "/api/publish-reconciliation?limit=250",
                "Backend publish reconciliation row:",
                "Mutation guardrail: this backend row",
                "Completed-to-Pending output proof cross-check:",
                "function completedProofRowMissingOutput",
                "completed-missing-output-no-pending-proof",
                "completed-missing-output-still-pending",
                "completed-missing-output-with-drain-proof",
                "function completedPendingProofIsFinalPlacementReviewSignal",
                "Missing completed output with pending proof:",
                "Missing completed output with drain proof:",
                "Missing completed output without pending/drain proof:",
                "Treat as final-placement conflict",
                "an empty Pending Publish page is not proof that the file published.",
                "Mutation guardrail: this cross-check is read-only",
                "same-leaf matches are duplicate-title hints only",
                "Mutation guardrail: this detail panel does not accept, repair, rerun, drain, cleanup, delete, publish, rewrite manifests, or touch media files.",
                "function renderCompletedOutputAcceptance",
                "function completedAcceptanceRows",
                "Completed output acceptance readiness:",
                "Daily-use handoff: Completed evidence supports an operator trust decision",
                "Scope boundary: Current Output filters, Completed History filters",
                "readiness requires display filter scope, output/sidecar proof, route/size explanation, pending-publish proof, and recent command evidence to agree.",
                "Mutation guardrail: this checklist does not accept, delete, rerun, reprocess, drain, cleanup, write manifests, or change policy.",
                "function completedCurrentFilterScope",
                "function completedFilterScopeDetailLines",
                "Display filter / backend action scope",
                "Current Output display filter / backend action scope:",
                "Backend action scope: unchanged.",
                "Current Output filters never accept outputs",
                "function renderCompletedRouteAgreement",
                "function completedRouteAgreementRows",
                "function completedRouteAgreementStatus",
                "function completedRouteAgreementRouteToken",
                "Queue / Completed route agreement:",
                "Completed source still queued",
                "Route mismatch",
                "a completed source should not appear runnable in Queue unless this is deliberate reprocess",
                "typeof window.getLastQueuePayload === \"function\" ? window.getLastQueuePayload() : {}",
                "Mutation guardrail: this agreement panel does not launch, rerun, drain, repair, reconcile, delete, rewrite manifests, or touch media files.",
            ),
        )
        _assert_contains_all(
            self,
            bundle.completed_view_table_js,
            (
                "function renderCompletedRowsImpl",
                "completed_at_sort_key",
                "completedCell.dataset.sortValue = sortValue",
                "ctx.renderCompletedOutputAcceptance(ctx.state.lastCompletedPayload, lastCompletedRows",
            ),
        )
        self.assertIn("renderCompletedOutputAcceptance(payload, rows", bundle.completed_view_js)

    def test_completed_proof_contract_surfaces_final_trust_and_pilot_evidence(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.completed_view_proof_js,
            (
                "function createCompletedProofModule",
                "window.__completedViewProofModule",
                "function createCompletedPilotEvidenceModule",
                "window.__completedPilotEvidenceModule",
                "function renderCompletedRealMediaProof",
                "function completedRealMediaProofRows",
                "function completedRealMediaProofSummaryLines",
                "Real-media output proof ladder:",
                "Decision rule: output proof, sidecar proof, route/size/media decision, pending/drain posture, and diagnostics/runtime evidence must agree before trusting a sample.",
                "function completedPolicyAlignmentOutputEvidence",
                "Saved policy reconciliation",
                "Completed policy reconciliation:",
                "Post-run boundary: Completed can prove output-side evidence only",
                "Sample validation handoff",
                "Sample Validation handoff is evidence-only.",
                "Home Sample Validation can write JSONL evidence notes only",
                "function renderCompletedFinalTrust",
                "function completedFinalTrustRows",
                "function selectCompletedFinalTrustStep",
                "Completed final output trust walkthrough:",
                "trust the selected output only after Completed Manifest, disk/sidecar state, Pending Publish/drain proof, Plex/media policy evidence, Diagnostics logs, and Sample Validation preview agree.",
                "Manual playback/subtitle/audio/size inspection remains required before acceptance.",
                "function renderCompletedPilotEvidencePacket",
                "function completedPilotEvidencePacketRows",
                "Selected pilot evidence packet:",
                "Purpose: copyable post-run proof for a selected Completed row after a real-media pilot run.",
                "3b. Saved policy reconciliation",
                "do not append an accepted Sample Validation record until output, sidecar, route/size/media, pending/final placement, diagnostics, and manual playback checks agree.",
                "Validation state proof",
            ),
        )
        self.assertNotIn("function completedRealMediaProofRows", bundle.completed_view_js)
        _assert_contains_all(
            self,
            bundle.command_history_js,
            (
                "renderCompletedFinalTrust(undefined, undefined, undefined, undefined, commandHistory)",
                "completedView.renderCompletedPilotEvidencePacket?.(undefined, undefined, undefined, undefined, commandHistory)",
                "completedView.renderCompletedOutputAcceptance?.(undefined, undefined, undefined, commandHistory)",
            ),
        )
        _assert_contains_all(
            self,
            bundle.pending_publish_view_js,
            (
                "completedView.renderCompletedPilotEvidencePacket(",
                "completedView.renderCompletedRealMediaProof(",
                "completedView.getLastCompletedPendingProofRows()",
            ),
        )

    def test_completed_filters_diagnostics_selection_and_open_actions_are_backend_owned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.completed_view_filters_js,
            (
                "function resetCompletedFilters",
                "Current Output Status filters cleared.",
                "function resetCompletedHistoryFilters",
            ),
        )
        _assert_contains_all(
            self,
            bundle.completed_view_diagnostics_js,
            (
                "function createCompletedDiagnosticsModule",
                "window.__completedViewDiagnosticsModule",
                "function completedDiagnosticsActionsForRow",
                "function renderCompletedDiagnosticsLinks",
                "async function requestCompletedDiagnosticsAction",
                "Diagnostics actions below use backend allowlists. The Completed page never sends arbitrary filesystem paths.",
                "completed-diagnostics-actions",
                "requestDiagnosticsOpen(target)",
                "requestDiagnosticsTail(target)",
                "appendDiagnosticsBridgeGroupedButtons(container, actions",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.completed_view_js,
            (
                "function completedDiagnosticsActionsForRow",
                "function renderCompletedDiagnosticsLinks",
                "function requestCompletedDiagnosticsAction",
            ),
        )
        _assert_contains_all(
            self,
            bundle.completed_view_open_actions_js,
            (
                "function completedSelectedOpenTargetLines",
                "Open boundary: Completed buttons send only row_key and target.",
                "function requestCompletedOpen",
                "/api/completed/open",
                "[data-open-completed]",
                "let completedOpenInFlight = false",
                "function setCompletedOpenBusy",
                "function rejectCompletedOpenWhileBusy",
                "function renderCompletedOpenHistory",
                "function isCompletedOpenCommand",
                "Backend manifest row keys and target allowlists remain the source of truth.",
                "Another completed open command is already in progress.",
                "button.disabled = completedOpenInFlight",
            ),
        )
        _assert_contains_all(
            self,
            bundle.completed_view_selection_js,
            (
                "function getLastCompletedPayload",
                "Operator status:",
                "Backend trust state:",
                "Backend proof summary:",
                "operator_trust_state",
                "safe_next_action",
                "unsafe_if_ignored",
                "recommended_diagnostics_targets",
                "Review flags:",
                "Route decision:",
                "Route evidence:",
                "route_evidence_lines",
                "operator_guidance",
                "Validation state:",
                "Output growth:",
                "audio_decision_preview",
                "subtitle_decision_preview",
                "Runtime error code:",
                "Runtime match:",
                "Route reason:",
            ),
        )
        _assert_contains_all(
            self,
            bundle.completed_view_status_boards_js,
            (
                "function completedFreshnessLine",
                "function completedManifestIsAged",
                "function completedEmptyStateMessage",
                "No completed history rows.",
            ),
        )


if __name__ == "__main__":
    unittest.main()
