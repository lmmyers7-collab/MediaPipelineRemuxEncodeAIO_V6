from __future__ import annotations

import unittest

from tests.python.desktop.application_facade_test_support import served_webview_static_contract_bundle


def _queue_page_html(html: str) -> str:
    start = html.index('data-page-panel="queue"')
    end = html.find('data-page-panel="completed"', start)
    return html[start : end if end != -1 else len(html)]


def _assert_contains_all(testcase: unittest.TestCase, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        with testcase.subTest(snippet=snippet):
            testcase.assertIn(snippet, text)


class ApplicationFacadeWebStaticQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = served_webview_static_contract_bundle()

    def test_queue_page_dom_and_assets_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.html,
            (
                "/assets/queueView.summary.js",
                "/assets/queueView.review.js",
                "/assets/queueView.detail.js",
                "/assets/queueView.launch.js",
                "/assets/queueView.js",
                "queue-filter",
                "queue-summary",
                "queue-readiness-status",
                "queue-readiness",
                "queue-breakdown-status",
                "queue-breakdown",
                "queue-validation-status",
                "queue-validation",
                "queue-workflow-status",
                "queue-workflow",
                "queue-backend-scope-status",
                "queue-backend-scope-summary",
                "queue-backend-scope-rows",
                "queue-launch-decision-status",
                "queue-launch-decision-summary",
                "queue-launch-decision-rows",
                "queue-launch-decision-detail",
                "queue-review-status",
                "queue-review-board",
                "queue-review-rows",
                "queue-review-legend",
                "queue-collision-status",
                "queue-collision",
                "queue-excluded-status",
                "queue-excluded-summary",
                "queue-excluded-rows",
                "queue-excluded-detail",
                "queue-excluded-open-status",
                'data-open-target-row-actions="queue-excluded"',
                'id="queue-detail" class="prose-block" data-visual-keep="copy-output"',
                "queue-diagnostics-status",
                "queue-diagnostics-guidance",
                "queue-diagnostics-actions",
                "queue-open-status",
                "queue-open-history",
                'data-open-target-row-actions="queue"',
                "queue-progress-bars",
                "queue-progress-summary",
                "Collision Risk",
                "Queue Decision",
                "queue-decision-summary",
                "Attention Required",
                "queue-attention-summary",
                "Search loaded queue rows",
                "Display status filter",
                "Investigation view",
                "Clear Display Filters",
                "Selected Row Detail (not launch scope)",
                "Backend Launch Scope Boundary",
                "Queue-to-Launch Handoff",
                "Backend-Excluded Source Files",
                "Selected Row Diagnostics Links",
                "queue-launch-decision-summary",
                "queue-launch-decision-detail",
                "queue-clear-filters-button",
                "data-queue-refresh-button",
                "Scan Sources asks the backend to inventory configured source roots",
                "queue-source-inventory",
                "Run History",
            ),
        )
        _assert_contains_all(
            self,
            bundle.js,
            (
                'targetDataset: "openQueueExcluded"',
                "Open Excluded Source",
                'targetDataset: "openQueue"',
                "Open Source Root",
                "queueClearFiltersButton.addEventListener(\"click\", resetQueueFilters)",
            ),
        )
        self.assertLess(bundle.html.index('data-queue-refresh-button'), bundle.html.index('id="queue-rows"'))
        self.assertLess(bundle.html.index('id="queue-rows"'), bundle.html.index('id="queue-readiness"'))

    def test_queue_panel_order_is_static_pinned(self) -> None:
        queue_page_html = _queue_page_html(self.bundle.html)
        queue_panel_order = [
            "<h2>Queue Decision</h2>",
            "<h2>Source Scan And Display Filters</h2>",
            "<h2>Attention Required</h2>",
            "<h2>Queue Rows</h2>",
            "<h2>Selected Row Detail (not launch scope)</h2>",
            "<h2>Selected Row Diagnostics Links</h2>",
            "<h2>Backend Launch Scope Boundary</h2>",
            "<h2>Queue-to-Launch Handoff</h2>",
            "<h2>Source Scan Progress</h2>",
            "<h2>Queue Snapshot</h2>",
            "<h2>Readiness</h2>",
            "<h2>Queue Summary</h2>",
            "<h2>Run History</h2>",
            "<h2>Queue Readiness Checklist</h2>",
            "<h2>Next Step</h2>",
            "<h2>Flagged Items</h2>",
            "<h2>Collision Risk</h2>",
            "<h2>Backend-Excluded Source Files</h2>",
        ]
        positions = [queue_page_html.index(marker) for marker in queue_panel_order]
        self.assertEqual(positions, sorted(positions))

    def test_queue_view_namespace_progress_and_snapshot_contracts_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.queue_view_js,
            (
                "window.mediaPipelineQueueView",
                "function renderQueue",
                "function renderQueueRows",
                "function selectQueueRow",
                "function renderQueueProgress",
                "function queueProgressBars",
                "const progressRenderer = window.mediaPipelineProgressView?.renderProgressBarsInto",
                "progressRenderer(\"queue-progress-bars\"",
                "function renderQueueCollision",
                "function queueCollisionStatus",
                "function queueCollisionLines",
                "function renderQueueExcluded",
                "function renderQueueExcludedDetail",
                "function selectQueueExcludedRow",
                "function queueExcludedRowKey",
                "row_scope",
                "Row-level excluded-file detail: unavailable",
                "function renderQueueDetail",
                "function renderQueueSummary",
                "function renderQueueReadiness",
                "function renderQueueBreakdown",
                "function renderQueueRuntime",
                "function renderQueueValidation",
                "function queueReadinessStatus",
                "function queueReadinessLines",
                "function queueBreakdownLines",
                "function queueRuntimeLines",
                "function queueEmptyStateMessage",
                "window.getLastQueuePayload = getLastQueuePayload",
                "window.getLastQueueRows = getLastQueueRows",
                "Route reasons:",
                "Invalid snapshot rows:",
                "Operator note: this is a read-only snapshot breakdown.",
                "No runnable queue rows.",
                "Source candidates:",
                "Completed/blocked exclusions:",
                "Visible blocked rows:",
                "Visible blocked reason codes:",
                "Visible blocked reasons:",
                "Runtime checks deferred:",
                "Runtime deferred checks:",
                "Runtime outcome matches:",
                "Rows with exact source-path runtime history:",
                "Stale history is shown only as context.",
                "Produced:",
                "Snapshot file age",
                "Produced age",
                "Snapshot stale",
                "function queueSnapshotIsStale",
                "Source roots:",
            ),
        )

    def test_queue_launch_scope_and_backend_preflight_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.queue_view_js,
            (
                "function renderQueueBackendLaunchScopePreview",
                "function queueBackendLaunchScopeRows",
                "function renderQueueDecisionHeader",
                "function renderQueueAttentionSummary",
                "Queue decision header:",
                "Attention required:",
                "Backend launch scope boundary:",
                "Queue filters, row selection, and rendered table caps are not submitted as processing scope.",
                "Backend launch scope is owned by Launch; Queue filters, selected rows, and rendered row caps are not submitted as processing scope.",
                "Selecting a row cannot make Launch process only that row.",
                "function renderQueueLaunchDecisionChecklist",
                "function queueLaunchDecisionRows",
                "function queueLaunchDecisionStatusState",
                "function launchViewApi",
                "function queueCurrentFilterScope",
                "function queueFilterScopeDetailLines",
                "Display filter / backend launch scope",
                "Backend launch scope: unchanged.",
                "Launch routes use backend queue/schedule/settings checks, not the visible WebView table subset.",
                "renderQueueLaunchDecisionChecklist(lastQueuePayload, lastQueueRows",
                "function queueLaunchBackendPreflightPayload",
                "function queueLaunchBackendPreflightCheckpoint",
                'launchView.launchBackendPreflightPayloadForTarget("pipeline")',
                "launchView.getLastLaunchBackendPreflightRefreshInfo()",
                "Last backend preflight refresh:",
                "Backend launch preflight",
                "Pipeline backend launch preflight has not been loaded",
                "function isQueueLaunchCommand",
                "Queue-to-Launch handoff:",
                "Daily-use handoff: Queue evidence decides whether it is sensible to open Launch",
                "Scope boundary: Queue filters, selected rows, review boards",
                "use backend launch preflight, queue payload, display filter scope, freshness, blocked rows, runtime context, completed exclusions, selected-row proof, command history, and Launch readiness as advisory context",
                "Mutation guardrail: this handoff cannot launch, reorder, drop, rewrite queue snapshots, delete files, clear completed state, override schedule, or bypass backend validation.",
            ),
        )
        _assert_contains_all(
            self,
            bundle.app_refresh_js,
            (
                "function renderQueueRefreshInProgress()",
                'activity: "Scanning"',
                "setQueueRefreshButtonBusy(true)",
                "setQueueRefreshButtonBusy(queueScanRunning)",
            ),
        )

    def test_queue_review_filter_and_diagnostics_contracts_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.queue_view_js,
            (
                "function renderQueueReviewBoard",
                "function queueReviewBoardLines",
                "Operator review board: Queue",
                "function queueValidationChecklistLines",
                "function queueRowReviewChecklistLines",
                "function queueRowIssueDigestLines",
                "function queueRowCombinedReviewPlanLines",
                "function queueSelectedQuickSignalLines",
                "function queueSelectedOpenTargetLines",
                "Open boundary: Queue buttons send only row_key, row_scope, and target.",
                "available_open_target_counts",
                "function queueFilterVisibilityLines",
                "function queueFocusedInvestigationLabels",
                "function resetQueueFilters",
                "Queue display filters cleared.",
                "function queueInvestigationSignalLines",
                "function queueRowTrustSummaryLines",
                "function queueDiagnosticsActionsForRow",
                "function renderQueueDiagnosticsLinks",
                "function requestQueueDiagnosticsAction",
                "Real-media validation checklist:",
                "Mutation guardrail: this checklist",
                "Selected row review checklist:",
                "Selected row quick signal:",
                "Current filter visibility:",
                "Hidden by current filters:",
                "Selected queue issue digest:",
                "Combined row review plan:",
                "Queue Snapshot",
                "Launch readiness",
                "Guardrail: this combined plan is read-only and cannot change queue order",
                "Investigation view matches:",
                "investigation views are display filters only and do not alter backend launch scope",
                "function queueRealMediaTraceLines",
                "Real-media sample trace: Queue",
                "What remains unproven: FFmpeg execution",
                "review-before-launch",
                "diagnosticsBridgeRowTrustLines",
                "appendDiagnosticsBridgeGroupedButtons(container, actions",
                "Safe next action: use Queue Diagnostics Cross-Links before launch",
                "Safe next action: row is coherent in the current snapshot",
                "selected-row detail is read-only",
                "Diagnostics actions below use backend allowlists. The Queue page never sends arbitrary filesystem paths.",
                "queue-diagnostics-actions",
                "requestDiagnosticsOpen(target)",
                "requestDiagnosticsTail(target)",
            ),
        )

    def test_queue_open_scan_and_operator_state_are_backend_owned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.queue_view_js,
            (
                "[data-queue-refresh-button]",
                "/api/queue/scan",
                "function requestQueueScan()",
                "window.mediaPipelineAppRefresh?.renderQueueRefreshInProgress?.();",
                "function requestQueueOpen",
                "function renderQueueOpenHistory",
                "function isQueueOpenCommand",
                "/api/queue/open",
                "Another queue open command is already in progress.",
                "Backend queue snapshot row keys and target allowlists remain the source of truth.",
                "Mutation guardrail: backend queue mutation and processing start remain backend-owned commands",
                "Select a queue row to see launch readiness",
                "Runtime error code:",
                "Runtime match:",
                "Operator status:",
                "Blocked reason code:",
                "Runtime note:",
                "Operator statuses:",
                "Operator severities:",
                "Backend trust states:",
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
            ),
        )


if __name__ == "__main__":
    unittest.main()
