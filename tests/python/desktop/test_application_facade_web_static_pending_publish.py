from __future__ import annotations

import unittest

from tests.python.desktop.application_facade_test_support import (
    assert_namespace_export as _assert_namespace_export,
    served_webview_static_contract_bundle,
)


def _assert_contains_all(testcase: unittest.TestCase, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        with testcase.subTest(snippet=snippet):
            testcase.assertIn(snippet, text)


def _assert_not_contains_any(testcase: unittest.TestCase, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        with testcase.subTest(snippet=snippet):
            testcase.assertNotIn(snippet, text)


class ApplicationFacadeWebStaticPendingPublishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = served_webview_static_contract_bundle()

    def test_pending_publish_dom_assets_and_page_placement_are_static_pinned(self) -> None:
        bundle = self.bundle
        html = bundle.html
        home_start = html.index('data-page-panel="home"')
        live_start = html.index('data-page-panel="live"')
        pending_start = html.index('data-page-panel="pending"')
        rename_start = html.index('data-page-panel="rename"')

        _assert_contains_all(
            self,
            html,
            (
                "/assets/pendingPublishView.js",
                "/assets/pendingPublishView.recovery.js",
                "/assets/pendingPublishView.diagnostics.js",
                "/assets/pendingPublishView.drain.js",
                "/assets/pendingPublishView.confidence.js",
                'id="pending-risk-status"',
                'id="pending-risk"',
                'id="pending-validation-status"',
                'id="pending-validation"',
                'id="pending-workflow-status"',
                'id="pending-workflow"',
                'id="pending-evidence-status"',
                'id="pending-evidence-summary"',
                'id="pending-evidence-rows"',
                'id="pending-recovery-plan-rows"',
                'id="pending-recovery-plan-row-detail"',
                'id="pending-drain-correlation-status"',
                'id="pending-drain-correlation"',
                'id="pending-drain-confidence-status"',
                'id="pending-drain-confidence-summary"',
                'id="pending-drain-confidence-rows"',
                'id="pending-drain-decision-status"',
                'id="pending-drain-decision-summary"',
                'id="pending-drain-decision-rows"',
                'id="pending-drain-decision-detail"',
                'id="pending-post-drain-trust-status"',
                'id="pending-post-drain-trust-summary"',
                'id="pending-post-drain-trust-rows"',
                'id="pending-post-drain-trust-detail"',
                'id="pending-diagnostics-status"',
                'id="pending-diagnostics-guidance"',
                'id="pending-diagnostics-actions"',
                "pending-rows",
                "pending-filter",
                "pending-drain-button",
                "pending-drain-status",
                "pending-drain-detail",
                "pending-drain-history",
                "pending-drain-events-status",
                "pending-drain-events",
                "pending-drain-summary-status",
                "pending-drain-summary",
                "pending-publish-readiness-status",
                "pending-publish-readiness",
                "pending-review-status",
                "pending-review-board",
                "pending-review-rows",
                "pending-review-legend",
                'id="pending-detail" class="prose-block" data-visual-keep="copy-output"',
                "pending-clear-filters-button",
                "pending-backend-scope-status",
                "pending-backend-scope-summary",
                "pending-backend-scope-rows",
                "pending-drain-decision-summary",
                "pending-drain-decision-detail",
                "pending-post-drain-trust-summary",
                "pending-post-drain-trust-detail",
                "pending-drain-guard-status",
                "pending-drain-guard-summary",
                "<h2>Pending Publish Guard Evidence</h2>",
                "<h2>Pending Publish Drain</h2>",
                "pending-recovery-plan-selected-button",
                "pending-recovery-plan-all-button",
                "pending-recovery-plan-status",
                "pending-recovery-plan-detail",
                "pending-recovery-plan-history",
                "pending-open-history",
                'data-open-target-row-actions="pending"',
            ),
        )
        self.assertEqual(html.count('id="pending-drain-button"'), 1)
        self.assertLess(html.index('id="pending-drain-button"'), html.index('id="pending-status"'))
        self.assertLess(html.index('id="pending-drain-button"'), html.index('id="pending-rows"'))
        self.assertNotIn("pending-detail", html[home_start:live_start])
        self.assertIn("pending-detail", html[pending_start:rename_start])
        _assert_contains_all(
            self,
            bundle.js,
            (
                "pendingClearFiltersButton.addEventListener(\"click\", () => window.mediaPipelinePendingPublishView?.resetPendingFilters?.())",
                "requestPendingRecoveryPlan(\"selected\")",
                "requestPendingRecoveryPlan(\"all\")",
                'targetDataset: "openPending"',
                "requestPendingPublishOpen",
                "Play Parked Output",
                "play_local_file",
            ),
        )

    def test_pending_publish_core_review_contract_is_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.pending_publish_view_js,
            (
                "window.mediaPipelinePendingPublishView",
                "function renderPendingPublish",
                "function renderPendingRows",
                "function selectPendingRow",
                "function renderPendingDetail",
                "function renderPendingPublishReadiness",
                "function renderPendingRiskBreakdown",
                "function renderPendingValidation",
                "function renderPendingReviewBoard",
                "function pendingReviewBoardLines",
                "Operator review board: Pending Publish",
                "function pendingPublishReadinessStatus",
                "function pendingPublishReadinessLines",
                "function pendingRiskLines",
                "function pendingValidationChecklistLines",
                "function pendingRowReviewChecklistLines",
                "function pendingRowIssueDigestLines",
                "function pendingRowCombinedReviewPlanLines",
                "function pendingSelectedQuickSignalLines",
                "available_open_target_counts",
                "function pendingFilterVisibilityLines",
                "function pendingFocusedInvestigationLabels",
                "function resetPendingFilters",
                "Pending Publish display filters cleared.",
                "function pendingInvestigationSignalLines",
                "function pendingRealMediaTraceLines",
                "function pendingSelectedCompletedCorrelationRows",
                "function pendingSelectedCompletedCorrelationLines",
                "function pendingSampleValidationHandoffLines",
                "Sample Validation handoff: Pending Publish",
                "function pendingSampleValidationComparisonLines",
                "Sample Validation comparison for selected Pending Publish row:",
                "Post-run capture: Preview Record includes pending/final-placement proof rows",
                "Suggested pilot category: deferred-publish",
                "Home Sample Validation can write JSONL evidence notes only",
                "Completed Manifest correlation for selected pending row:",
                "Exact pending destination -> completed output:",
                "Boundary: same-leaf matches are duplicate-title hints only",
                "Mutation guardrail: this pending-row correlation",
                "function pendingRowTrustSummaryLines",
                "Diagnostic statuses:",
                "Suggested open targets:",
                "Real-media validation checklist:",
                "Real-media sample trace: Pending Publish",
                "What remains unproven: final publish completion until Drain Parked Outputs succeeds",
                "Mutation guardrail: this checklist",
                "Selected pending-row review checklist:",
                "Selected pending-row quick signal:",
                "Current filter visibility:",
                "Hidden by current filters:",
                "Selected pending issue digest:",
                "Combined pending-row drain review plan:",
                "Pending manifest",
                "Completed Manifest correlation",
                "Guardrail: this combined plan is read-only and cannot drain",
                "Investigation view matches:",
                "investigation views are display filters only and do not change backend drain scope",
                "review-before-drain",
                "move, delete, drain, repair, or rewrite pending payloads",
                "Safe next action: do not drain; inspect row targets, Pending Publish diagnostics, Last Stderr, and Run Logs first.",
                "Safe next action: row looks ready, but use only the backend-owned Drain Parked Outputs command to move files.",
                "Health blockers:",
                "Drain recommendation:",
                "Operator guidance:",
                "Backend trust states:",
                "Backend trust state:",
                "Backend proof summary:",
                "operator_trust_state",
                "safe_next_action",
                "unsafe_if_ignored",
                "recommended_diagnostics_targets",
                "function pendingListText",
                "function pendingRecoverySummaryPayload",
                "function pendingRecoverySummaryLines",
                "Backend recovery summary:",
                "Recovery classes:",
                "Recovery class:",
                "Recovery action:",
                "Evidence fields:",
                "function pendingEmptyStateMessage",
                "Ready-looking",
                "Ready to drain:",
                "Issue summary:",
                "Operator note: drain readiness is advisory.",
                "Backend drain command remains the source of truth",
                "No parked outputs are waiting to publish.",
                "Select a pending publish row to see drain safety",
                "function getLastPendingPublishPayload",
                "let pendingOpenInFlight = false",
            ),
        )

    def test_pending_publish_drain_and_confidence_contracts_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.pending_publish_drain_js,
            (
                "function renderPendingDrainEvidence",
                "function pendingEvidenceRows",
                "function pendingDrainEvidenceLines",
                "Pending drain evidence board:",
                "No pending rows with drain blockers or review evidence.",
                "function renderPendingDrainEvents",
                "function renderPendingDrainSummary",
                "function pendingDrainEventsFromSnapshot",
                "function pendingDrainEventsLines",
                "function pendingDrainSummaryLines",
                "function pendingDrainSummaryPayload",
                "function createPendingPublishDrainModule",
                "window.__pendingPublishDrainModule",
                "pending_drain_summary.v1",
                "durable summary records the last backend drain attempt",
                "publish_drained",
                "Latest backend-authored drain events:",
                "function renderPendingDrainHistory",
                "function isPendingDrainCommand",
                "function pendingDrainSearchText",
                "No pending publish drain commands found in command history.",
                "function renderPendingDrainCorrelation",
                "function pendingDrainCorrelationLines",
                "Pending Publish drain correlation:",
                "Mutation guardrail: this correlation is read-only",
                "function pendingCurrentFilterScope",
                "function renderPendingBackendDrainScopePreview",
                "function pendingBackendDrainScopeRows",
                "Backend drain scope preview:",
                "Pending filters, selected row keys, and rendered table caps are not submitted as publish scope.",
                "Selecting a row cannot make Drain Parked Outputs drain only that row.",
                "attempted=${data.attempted_count}",
                "remaining=${data.remaining_count}",
            ),
        )
        _assert_contains_all(
            self,
            bundle.pending_publish_confidence_js,
            (
                "function createPendingPublishConfidenceModule",
                "window.__pendingPublishConfidenceModule",
                "function pendingDrainConfidenceRows",
                "function renderPendingDrainActionConfidence",
                "entry.evidenceClass",
                "Pending Publish drain action confidence:",
                "This is the final read-only operator handoff before Drain Parked Outputs.",
                "Backend Drain Parked Outputs remains the only authority that can validate and move parked files.",
                "Build a selected-row or all-rows dry-run plan before risky drains.",
                "Mutation guardrail: this panel cannot drain, repair, rewrite, move, delete, publish, or bypass backend validation.",
                "Display filter / drain scope",
                "Backend drain scope remains all loaded parked rows",
                "Drain Parked Outputs does not drain only the visible table subset.",
                "function renderPendingDrainDecisionChecklist",
                "function pendingDrainDecisionRows",
                "function pendingDrainDecisionStatusState",
                "Pending Publish drain decision checklist:",
                "Daily-use handoff: Pending Publish evidence decides whether it is sensible to press Drain Parked Outputs",
                "Scope boundary: Pending filters, selected rows, recovery dry-runs",
                "drain only after current parked rows, recovery dry-run, latest drain evidence, Completed/output proof, and diagnostics order agree.",
                "Mutation guardrail: this checklist cannot drain, repair, rewrite, move, delete, publish, accept outputs, write manifests, or bypass backend validation.",
                'statusNode.dataset.state = pendingDrainDecisionStatusState(decisionStatus)',
                "function renderPendingPostDrainTrust",
                "function pendingPostDrainTrustRows",
                "function pendingPostDrainTrustStatus",
                "Pending Publish post-drain trust review:",
                "a drain is trusted only when current parked rows, durable drain summary, recent drain events/logs, Completed output proof, and Sample Validation deferred-publish evidence agree.",
                "Blocking evidence rows:",
                "Do not trust this drain outcome yet.",
                "Mutation guardrail: this review is read-only and cannot drain, repair, rewrite, move, delete, publish, mark outputs complete, append validation records, or touch media.",
                "function pendingDrainGuardState",
                "function renderPendingDrainGuard",
                "Drain Parked Outputs blocked by WebView evidence",
                "Pending table filter:",
                "local filters do not narrow publish scope",
                "The backend will still perform authoritative validation before moving files. Continue?",
                "Mutation guardrail: this guard cannot drain, repair, rewrite, move, delete, publish, accept outputs, write manifests, or bypass backend validation.",
                "completedView.getLastCompletedRows()",
            ),
        )
        _assert_contains_all(
            self,
            bundle.pending_publish_view_js,
            (
                "const pendingDrainModule = window.__pendingPublishDrainModule || {}",
                "delete window.__pendingPublishDrainModule",
                "pendingDrainModule.createPendingPublishDrainModule",
                "const pendingConfidenceModule = window.__pendingPublishConfidenceModule || {}",
                "delete window.__pendingPublishConfidenceModule",
                "pendingConfidenceModule.createPendingPublishConfidenceModule",
            ),
        )
        _assert_namespace_export(self, bundle.pending_publish_view_js, "mediaPipelinePendingPublishView", "renderPendingPostDrainTrust")

    def test_pending_publish_diagnostics_open_and_recovery_are_backend_owned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.pending_publish_diagnostics_js,
            (
                "function pendingSelectedOpenTargetLines",
                "Open boundary: Pending Publish buttons send only row_key and target.",
                "appendDiagnosticsBridgeGroupedButtons(container, actions",
                "function createPendingPublishDiagnosticsModule",
                "window.__pendingPublishDiagnosticsModule",
                "function pendingDiagnosticsActionsForRow",
                "function pendingDiagnosticsGuidanceLines",
                "function renderPendingDiagnosticsLinks",
                "function requestPendingDiagnosticsAction",
                "Diagnostics actions below use backend allowlists.",
                "button.dataset.pendingDiagnosticsAction",
                "openRequester(target)",
                "tailRequester(target)",
                "Selected-row diagnostic order:",
                "function requestPendingPublishOpen",
                "/api/pending-publish/open",
                "function setPendingOpenBusy",
                "function rejectPendingOpenWhileBusy",
                "function renderPendingOpenHistory",
                "function isPendingOpenCommand",
                "Backend pending row keys and target allowlists remain the source of truth.",
                "Another pending publish open command is already in progress.",
            ),
        )
        _assert_contains_all(
            self,
            bundle.pending_publish_view_js,
            (
                "const pendingDiagnosticsModule = window.__pendingPublishDiagnosticsModule || {}",
                "delete window.__pendingPublishDiagnosticsModule",
                "pendingDiagnosticsModule.createPendingPublishDiagnosticsModule",
                "const pendingRecoveryModule = window.__pendingPublishRecoveryModule || {}",
                "delete window.__pendingPublishRecoveryModule",
                "pendingRecoveryModule.createPendingPublishRecoveryModule",
            ),
        )
        _assert_contains_all(
            self,
            bundle.pending_publish_recovery_js,
            (
                "function createPendingPublishRecoveryModule",
                "window.__pendingPublishRecoveryModule",
                "function requestPendingRecoveryPlan",
                "/api/pending-publish/recovery-plan",
                "pending_publish.recovery_plan_dry_run",
                "function renderPendingRecoveryPlanResult",
                "function renderPendingRecoveryPlanRows",
                "function pendingRecoveryPlanRowDetailLines",
                "Selected recovery-plan row:",
                "Mutation guardrail: this drilldown is read-only",
                "function renderPendingRecoveryPlanHistory",
                "function isPendingRecoveryPlanCommand",
                "Recovery plan is dry-run only",
                "renderPendingDrainGuard(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot()",
            ),
        )
        _assert_contains_all(
            self,
            bundle.command_history_js,
            (
                "renderPendingRecoveryPlanHistory(commandHistory)",
                "renderPendingDrainGuard(undefined, undefined, undefined, commandHistory)",
            ),
        )

    def test_pending_publish_completed_handoffs_use_completed_namespace(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.pending_publish_view_js,
            (
                "completedView.renderCompletedPendingProof(",
                "completedView.getLastCompletedRows()",
            ),
        )
        _assert_contains_all(
            self,
            bundle.pending_publish_details_js,
            ("const completedView = window.mediaPipelineCompletedView || {}",),
        )
        _assert_not_contains_any(
            self,
            bundle.pending_publish_view_js,
            (
                "window.renderCompletedPendingProof(",
                "window.getLastCompletedRows(",
            ),
        )
        self.assertNotIn("window.getLastCompletedRows(", bundle.pending_publish_confidence_js)
        self.assertNotIn("window.getLastCompletedRows(", bundle.pending_publish_details_js)


if __name__ == "__main__":
    unittest.main()
