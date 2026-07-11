from __future__ import annotations

import json
import re
import unittest

from tests.python.desktop.application_facade_test_support import (
    assert_namespace_export as _assert_namespace_export,
    served_webview_static_contract_bundle,
)


ASSET_ORDER_PAIRS = [
    ("/assets/apiClient.js", "/assets/app.js"),
    ("/assets/apiClient.js", "/assets/dom/query.js"),
    ("/assets/dom/query.js", "/assets/dom/text.js"),
    ("/assets/dom/text.js", "/assets/dom/status.js"),
    ("/assets/dom/status.js", "/assets/dom/filtering.js"),
    ("/assets/dom/filtering.js", "/assets/dom/table.js"),
    ("/assets/dom/table.js", "/assets/domHelpers.js"),
    ("/assets/domHelpers.js", "/assets/formatters.js"),
    ("/assets/apiClient.js", "/assets/pathPicker.js"),
    ("/assets/formatters.js", "/assets/pathPicker.js"),
    ("/assets/pathPicker.js", "/assets/progressView.js"),
    ("/assets/formatters.js", "/assets/progressView.js"),
    ("/assets/progressView.js", "/assets/commandHistory/formatters.js"),
    ("/assets/commandHistory/formatters.js", "/assets/commandHistory/diagnostics.js"),
    ("/assets/commandHistory/diagnostics.js", "/assets/commandHistory/diagnosticEvidence.js"),
    ("/assets/commandHistory/diagnosticEvidence.js", "/assets/commandHistory/resolutionChecklist.js"),
    ("/assets/commandHistory/resolutionChecklist.js", "/assets/commandHistory.js"),
    ("/assets/commandHistory.js", "/assets/diagnosticsBridge.js"),
    ("/assets/diagnosticsBridge.js", "/assets/completed/evidence/commands.js"),
    ("/assets/completed/evidence/commands.js", "/assets/completed/evidence/filterScope.js"),
    ("/assets/completed/evidence/filterScope.js", "/assets/completed/evidence/acceptance.js"),
    ("/assets/completed/evidence/acceptance.js", "/assets/completed/evidence/routeAgreement.js"),
    ("/assets/completed/evidence/routeAgreement.js", "/assets/completed/evidence/pendingProofModel.js"),
    ("/assets/completed/evidence/pendingProofModel.js", "/assets/completed/evidence/pendingProofView.js"),
    ("/assets/completed/evidence/pendingProofView.js", "/assets/completedView.evidence.js"),
    ("/assets/completedView.evidence.js", "/assets/completed/proof/pilotEvidence.js"),
    ("/assets/completed/proof/pilotEvidence.js", "/assets/completedView.proof.js"),
    ("/assets/completedView.proof.js", "/assets/completed/review/integrity.js"),
    ("/assets/completed/review/integrity.js", "/assets/completed/review/workflowOverview.js"),
    ("/assets/completed/review/workflowOverview.js", "/assets/completed/review/sizeReview.js"),
    ("/assets/completed/review/sizeReview.js", "/assets/completed/review/healthSignals.js"),
    ("/assets/completed/review/healthSignals.js", "/assets/completed/review/reviewRows.js"),
    ("/assets/completed/review/reviewRows.js", "/assets/completed/review/investigationFilters.js"),
    ("/assets/completed/review/investigationFilters.js", "/assets/completed/review/tablePanels.js"),
    ("/assets/completed/review/tablePanels.js", "/assets/completed/review/metricsValidation.js"),
    ("/assets/completed/review/metricsValidation.js", "/assets/completed/review/selectedAtAGlance.js"),
    ("/assets/completed/review/selectedAtAGlance.js", "/assets/completed/review/selectedEvidence.js"),
    ("/assets/completed/review/selectedEvidence.js", "/assets/completedView.review.js"),
    ("/assets/completedView.review.js", "/assets/completedView.diagnostics.js"),
    ("/assets/completedView.diagnostics.js", "/assets/completed/sizeMode.js"),
    ("/assets/completed/sizeMode.js", "/assets/completed/presentation.js"),
    ("/assets/completed/presentation.js", "/assets/completedView.js"),
    ("/assets/completedView.js", "/assets/queueView.summary.js"),
    ("/assets/queueView.summary.js", "/assets/queueView.review.js"),
    ("/assets/queueView.review.js", "/assets/queueView.detail.js"),
    ("/assets/queueView.detail.js", "/assets/queueView.launch.js"),
    ("/assets/queueView.launch.js", "/assets/queue/statusPanels.js"),
    ("/assets/queue/statusPanels.js", "/assets/queue/tableView.js"),
    ("/assets/queue/tableView.js", "/assets/queue/manualOrder.js"),
    ("/assets/queue/priority.js", "/assets/queue/manualOrder.js"),
    ("/assets/queue/manualOrder.js", "/assets/queue/strategy.js"),
    ("/assets/queue/strategy.js", "/assets/queue/controls.js"),
    ("/assets/queue/controls.js", "/assets/queue/excluded.js"),
    ("/assets/queue/excluded.js", "/assets/queue/scan.js"),
    ("/assets/queue/scan.js", "/assets/queueView.js"),
    ("/assets/queueView.js", "/assets/pendingPublishView.recovery.js"),
    ("/assets/pendingPublishView.recovery.js", "/assets/pendingPublishView.diagnostics.js"),
    ("/assets/pendingPublishView.diagnostics.js", "/assets/pendingPublishView.drain.js"),
    ("/assets/pendingPublishView.drain.js", "/assets/pendingPublish/confidence/postDrainTrust.js"),
    ("/assets/pendingPublish/confidence/postDrainTrust.js", "/assets/pendingPublishView.confidence.js"),
    ("/assets/pendingPublishView.confidence.js", "/assets/pendingPublishView.repair.js"),
    ("/assets/pendingPublishView.repair.js", "/assets/pendingPublish/tableSupport.js"),
    ("/assets/pendingPublish/tableSupport.js", "/assets/pendingPublish/defaultAdapters.js"),
    ("/assets/pendingPublish/defaultAdapters.js", "/assets/pendingPublish/summary.js"),
    ("/assets/pendingPublish/summary.js", "/assets/pendingPublish/filters.js"),
    ("/assets/pendingPublish/filters.js", "/assets/pendingPublish/details.js"),
    ("/assets/pendingPublish/details.js", "/assets/pendingPublish/actionCenter.js"),
    ("/assets/pendingPublish/actionCenter.js", "/assets/pendingPublish/rendering.js"),
    ("/assets/pendingPublish/rendering.js", "/assets/pendingPublishView.js"),
    ("/assets/pendingPublishView.js", "/assets/crossPageContextView.conflict.js"),
    ("/assets/crossPageContextView.conflict.js", "/assets/crossPageContextView.sample.js"),
    ("/assets/crossPageContextView.sample.js", "/assets/crossPageContextView.settings.js"),
    ("/assets/crossPageContextView.settings.js", "/assets/crossPageContextView.sampleValidation.worksheet.js"),
    ("/assets/crossPageContextView.sampleValidation.worksheet.js", "/assets/crossPageContextView.sampleValidation.runbook.js"),
    ("/assets/crossPageContextView.sampleValidation.runbook.js", "/assets/crossPageContextView.sampleValidation.records.js"),
    ("/assets/crossPageContextView.sampleValidation.records.js", "/assets/crossPageContextView.sampleValidation.js"),
    ("/assets/crossPageContextView.sampleValidation.js", "/assets/crossPageContextView.js"),
    ("/assets/crossPageContextView.js", "/assets/renameLabels.js"),
    ("/assets/renameLabels.js", "/assets/renameHistoryView.js"),
    ("/assets/renameHistoryView.js", "/assets/rename/cleaningFilters.js"),
    ("/assets/rename/cleaningFilters.js", "/assets/rename/cleaningWorkbench.js"),
    ("/assets/rename/cleaningWorkbench.js", "/assets/rename/selection.js"),
    ("/assets/rename/selection.js", "/assets/rename/paths.js"),
    ("/assets/rename/paths.js", "/assets/rename/preview.js"),
    ("/assets/rename/preview.js", "/assets/rename/applyReadiness.js"),
    ("/assets/rename/applyReadiness.js", "/assets/rename/editing.js"),
    ("/assets/rename/editing.js", "/assets/rename/applyResult.js"),
    ("/assets/rename/applyResult.js", "/assets/rename/commandEvidence.js"),
    ("/assets/rename/commandEvidence.js", "/assets/rename/previewLifecycle.js"),
    ("/assets/rename/previewLifecycle.js", "/assets/rename/interactions.js"),
    ("/assets/rename/interactions.js", "/assets/rename/confirmSummary.js"),
    ("/assets/rename/confirmSummary.js", "/assets/rename/dialogs.js"),
    ("/assets/rename/dialogs.js", "/assets/renameView.js"),
    ("/assets/formatters.js", "/assets/settingsOverview.js"),
    ("/assets/renameView.js", "/assets/settingsOverview.js"),
    ("/assets/settingsOverview.js", "/assets/settingsCommandHistory.js"),
    ("/assets/settingsCommandHistory.js", "/assets/settingsMetadata.js"),
    ("/assets/settingsMetadata.js", "/assets/settings/metadataFields.js"),
    ("/assets/settings/metadataFields.js", "/assets/settings/builderControls.js"),
    ("/assets/settings/builderControls.js", "/assets/settingsView.builders.audio.js"),
    ("/assets/settingsView.builders.audio.js", "/assets/settingsView.builders.video.js"),
    ("/assets/settingsView.builders.video.js", "/assets/settingsView.builders.subtitle.js"),
    ("/assets/settingsView.builders.subtitle.js", "/assets/settingsView.builders.queue.js"),
    ("/assets/settingsView.builders.queue.js", "/assets/settingsView.builders.runtime.js"),
    ("/assets/settingsView.builders.runtime.js", "/assets/settingsView.builders.file_safety.js"),
    ("/assets/settingsView.builders.file_safety.js", "/assets/settingsView.builders.pending.js"),
    ("/assets/settingsView.builders.pending.js", "/assets/settingsView.builders.network.js"),
    ("/assets/settingsView.builders.network.js", "/assets/settingsView.rawTriage.js"),
    ("/assets/settingsView.rawTriage.js", "/assets/settingsView.safetyLocks.js"),
    ("/assets/settingsView.safetyLocks.js", "/assets/settings/backendResult.js"),
    ("/assets/settings/backendResult.js", "/assets/settings/routePolicyModel.js"),
    ("/assets/settings/routePolicyModel.js", "/assets/settings/finalLibraryPromotion.js"),
    ("/assets/settings/finalLibraryPromotion.js", "/assets/settings/patchOverview.js"),
    ("/assets/settings/patchOverview.js", "/assets/settings/patchInteractions.js"),
    ("/assets/settings/patchInteractions.js", "/assets/settings/patchReadiness.js"),
    ("/assets/settings/patchReadiness.js", "/assets/settings/patchReview.js"),
    ("/assets/settings/patchReview.js", "/assets/settings/policyImpact/mediaProjection.js"),
    ("/assets/settings/policyImpact/mediaProjection.js", "/assets/settings/policyImpact/effectivePolicyView.js"),
    ("/assets/settings/policyImpact/effectivePolicyView.js", "/assets/settings/policyImpact.js"),
    ("/assets/settings/policyImpact.js", "/assets/settingsView.js"),
    ("/assets/settingsView.js", "/assets/networkView.js"),
    ("/assets/networkView.js", "/assets/diagnosticsTailView.js"),
    ("/assets/diagnosticsTailView.js", "/assets/diagnosticsStateSummaryView.js"),
    ("/assets/diagnosticsStateSummaryView.js", "/assets/diagnosticsView.activejobs.js"),
    ("/assets/diagnosticsView.activejobs.js", "/assets/diagnosticsView.log.js"),
    ("/assets/diagnosticsView.log.js", "/assets/diagnosticsView.investigation.js"),
    ("/assets/diagnosticsView.investigation.js", "/assets/diagnostics/matrixConsole.js"),
    ("/assets/diagnostics/matrixConsole.js", "/assets/diagnostics/triage.js"),
    ("/assets/diagnostics/triage.js", "/assets/diagnostics/firstResponse.js"),
    ("/assets/diagnostics/firstResponse.js", "/assets/diagnosticsView.js"),
    ("/assets/diagnosticsView.js", "/assets/reportsView.js"),
    ("/assets/reports/triage.js", "/assets/reports/investigation.js"),
    ("/assets/reports/investigation.js", "/assets/reportsView.js"),
    ("/assets/reportsView.js", "/assets/schedule/watchFolder.js"),
    ("/assets/schedule/watchFolder.js", "/assets/schedule/editor.js"),
    ("/assets/schedule/editor.js", "/assets/scheduleView.js"),
    ("/assets/scheduleView.js", "/assets/maintenanceView.js"),
    ("/assets/maintenanceView.js", "/assets/telemetry/gpuProjection.js"),
    ("/assets/telemetry/gpuProjection.js", "/assets/telemetryView.js"),
    ("/assets/telemetryView.js", "/assets/launchReadinessView.js"),
    ("/assets/progressView.js", "/assets/launchReadinessView.js"),
    ("/assets/launchReadinessView.js", "/assets/launchHistoryView.js"),
    ("/assets/launchHistoryView.js", "/assets/launch/risk/settingsAccess.js"),
    ("/assets/launch/risk/settingsAccess.js", "/assets/launch/risk/mediaPolicyValues.js"),
    ("/assets/launch/risk/mediaPolicyValues.js", "/assets/launch/risk/riskRows.js"),
    ("/assets/launch/risk/riskRows.js", "/assets/launch/risk/policyPatch.js"),
    ("/assets/launch/risk/policyPatch.js", "/assets/launch/risk/policyBoundary.js"),
    ("/assets/launch/risk/policyBoundary.js", "/assets/launchView.risk.js"),
    ("/assets/launchView.risk.js", "/assets/launch/scope/compactGate.js"),
    ("/assets/launch/scope/compactGate.js", "/assets/launchView.scope.js"),
    ("/assets/launchView.scope.js", "/assets/launchView.realmedia.js"),
    ("/assets/launchView.realmedia.js", "/assets/launch/preflight/pilotReadiness.js"),
    ("/assets/launch/preflight/pilotReadiness.js", "/assets/launchView.preflight.js"),
    ("/assets/launchView.preflight.js", "/assets/launch/controllerState.js"),
    ("/assets/launch/controllerState.js", "/assets/launch/statusRender.js"),
    ("/assets/launch/statusRender.js", "/assets/launch/startRequest.js"),
    ("/assets/launch/startRequest.js", "/assets/launch/scopeControls.js"),
    ("/assets/launch/scopeControls.js", "/assets/launch/commandButtons.js"),
    ("/assets/launch/commandButtons.js", "/assets/launch/commandOrchestration.js"),
    ("/assets/launch/commandOrchestration.js", "/assets/launch/rerunEvidence.js"),
    ("/assets/launch/rerunEvidence.js", "/assets/launch/rerunPresentation.js"),
    ("/assets/launch/rerunPresentation.js", "/assets/launch/rerunOrchestration.js"),
    ("/assets/launch/rerunOrchestration.js", "/assets/launch/rerunFacade.js"),
    ("/assets/launch/rerunFacade.js", "/assets/launchView.js"),
    ("/assets/launchView.js", "/assets/contractView.js"),
    ("/assets/contractView.js", "/assets/app.js"),
    ("/assets/commandHistory.js", "/assets/app.js"),
    ("/assets/formatters.js", "/assets/app.js"),
]

class ApplicationFacadeWebStaticShellTests(unittest.TestCase):
    def test_served_index_uses_http_only_cookie_bootstrap(self) -> None:
        bundle = served_webview_static_contract_bundle()

        self.assertIn("text/html", bundle.content_type)
        bootstrap_match = re.search(
            r'<script type="application/json" id="media-pipeline-bootstrap">(.+?)</script>',
            bundle.html,
        )
        self.assertIsNotNone(bootstrap_match)
        bootstrap = json.loads(bootstrap_match.group(1))
        self.assertEqual(bootstrap["token"], "")
        self.assertEqual(bootstrap["tokenSource"], "http-only-cookie")
        self.assertIn("MediaPipelineAuth=", bundle.set_cookie)
        self.assertIn("HttpOnly", bundle.set_cookie)
        self.assertNotIn("window.MEDIA_PIPELINE_BOOTSTRAP", bundle.html)
        self.assertNotIn("web-token", bundle.html)

    def test_index_references_static_assets_in_dependency_order(self) -> None:
        bundle = served_webview_static_contract_bundle()

        for before, after in ASSET_ORDER_PAIRS:
            self.assertIn(before, bundle.html)
            self.assertIn(after, bundle.html)
            self.assertLess(bundle.html.index(before), bundle.html.index(after), f"{before} must load before {after}")

    def test_index_cache_busts_home_summary_assets_for_tauri_webview(self) -> None:
        bundle = served_webview_static_contract_bundle()

        version = "v=20260630-csv-home-queue-fastpath"
        self.assertIn(f'/assets/styles.css?{version}', bundle.html)
        self.assertIn(f'/assets/progressView.js?{version}', bundle.html)
        self.assertIn(f'/assets/app/topbar.js?{version}', bundle.html)
        self.assertIn(f'/assets/app/home.js?{version}', bundle.html)
        self.assertIn(f'/assets/app.js?{version}', bundle.html)

    def test_served_static_assets_return_expected_content_types(self) -> None:
        bundle = served_webview_static_contract_bundle()

        for name, value in vars(bundle).items():
            if not name.endswith("_content_type"):
                continue
            expected = "text/css" if name.startswith("css") else "text/javascript"
            self.assertIn(expected, value, name)
        for map_name in (
            "dom_helper_child_content_types",
            "completed_view_evidence_child_content_types",
            "completed_view_review_child_content_types",
            "launch_view_risk_child_content_types",
            "launch_view_child_content_types",
        ):
            for asset_path, content_type in getattr(bundle, map_name).items():
                self.assertIn("text/javascript", content_type, asset_path)

    def test_common_app_shell_exports_are_static_pinned(self) -> None:
        bundle = served_webview_static_contract_bundle()

        self.assertIn('@import url("./styles.tokens.css");', bundle.css)
        self.assertIn('@import url("./styles.theme.css");', bundle.css)
        self.assertIn('@import url("./styles.layout.css");', bundle.css)
        self.assertIn('@import url("./styles.components.css");', bundle.css)
        self.assertIn('@import url("./styles.pages.css");', bundle.css)
        self.assertIn('@import url("./styles.controls.css");', bundle.css)
        self.assertIn('@import url("./styles.layout-manager.css");', bundle.css)
        self.assertIn('@import url("./styles.queue.css");', bundle.css)
        self.assertIn(":root {", bundle.css_tokens)
        self.assertIn("body.light-mode {", bundle.css_tokens)
        self.assertIn("body.light-mode .nav-button.is-active", bundle.css_theme)
        self.assertIn(".app-shell {", bundle.css_layout)
        self.assertIn(".metric-grid {", bundle.css_components)
        self.assertIn(".workflow-table {", bundle.css_components)
        self.assertIn(".home-next-queue-panel {", bundle.css_pages)
        self.assertIn(".settings-tab-bar {", bundle.css_pages)
        self.assertIn(".primary-button {", bundle.css_controls)
        self.assertIn(".status-chip {", bundle.css_controls)
        self.assertIn("#customize-layout-btn {", bundle.css_layout_manager)
        self.assertIn(".panel-customize-bar {", bundle.css_layout_manager)
        self.assertIn(".layout-editor-drawer {", bundle.css_layout_manager)
        self.assertIn(".layout-editor-panel-row {", bundle.css_layout_manager)
        self.assertIn(".layout-panel-preview {", bundle.css_layout_manager)
        self.assertIn(".layout-drag-hint {", bundle.css_layout_manager)
        self.assertIn(".panel-drag-hint-active .panel-customize-bar", bundle.css_layout_manager)
        self.assertIn(".priority-badge {", bundle.css_queue)
        self.assertIn(".queue-strategy-select {", bundle.css_queue)
        self.assertIn(".fo-drawer {", bundle.css_queue)
        self.assertIn("window.mediaPipelineApi", bundle.api_client_js)
        self.assertIn("async function apiGet", bundle.api_client_js)
        self.assertIn("async function apiPost", bundle.api_client_js)
        self.assertIn("Authorization", bundle.api_client_js)
        self.assertIn("DEFAULT_GET_TIMEOUT_MS", bundle.api_client_js)
        self.assertIn("fetchWithTimeout", bundle.api_client_js)
        self.assertIn("AbortController", bundle.api_client_js)
        self.assertIn("ApiClientTimeoutError", bundle.api_client_js)
        self.assertIn("backend timed out after", bundle.api_client_js)
        self.assertIn("apiGet(path, options = {})", bundle.api_client_js)
        self.assertIn("apiPost(path, payload, options = {})", bundle.api_client_js)
        self.assertIn('normalizedMethod === "GET" ? DEFAULT_GET_TIMEOUT_MS : 0', bundle.api_client_js)
        self.assertIn("const raw = await response.text()", bundle.api_client_js)
        self.assertIn("JSON.parse(raw)", bundle.api_client_js)
        self.assertIn("sanitizeBackendDetail", bundle.api_client_js)
        self.assertIn("backend returned invalid JSON", bundle.api_client_js)
        self.assertIn("httpError(response, path, data, method, options)", bundle.api_client_js)
        self.assertNotIn("Response starts with", bundle.api_client_js)
        self.assertNotIn("data.error || data.message || `HTTP ${response.status}`", bundle.api_client_js)
        self.assertNotIn("await response.json()", bundle.api_client_js)
        self.assertIn("window.mediaPipelineDom", bundle.dom_helpers_js)
        self.assertIn("function filterRows", bundle.dom_helpers_js)
        self.assertIn("function appendCells", bundle.dom_helpers_js)
        self.assertIn("window.mediaPipelineFormatters", bundle.formatters_js)
        _assert_namespace_export(self, bundle.formatters_js, "mediaPipelineFormatters", "formatProgressValue")
        self.assertIn("function formatMemoryMb", bundle.formatters_js)
        self.assertIn("function settingsValuesEqual", bundle.formatters_js)
        self.assertNotIn("window.formatProgressValue =", bundle.formatters_js)
        self.assertNotIn("window.formatPercent =", bundle.formatters_js)
        self.assertNotIn("window.formatMemoryMb =", bundle.formatters_js)
        self.assertNotIn("window.formatConfigValue =", bundle.formatters_js)
        self.assertNotIn("window.parseSettingsListText =", bundle.formatters_js)
        self.assertNotIn("window.formatSettingsListValue =", bundle.formatters_js)
        self.assertNotIn("window.shortenPath =", bundle.formatters_js)
        self.assertNotIn("window.settingsValuesEqual =", bundle.formatters_js)

    def test_command_history_diagnostics_contract_is_static_pinned(self) -> None:
        bundle = served_webview_static_contract_bundle()

        self.assertIn("window.mediaPipelineCommandHistory", bundle.command_history_js)
        self.assertIn("let commandHistory", bundle.command_history_js)
        self.assertIn("function appendCommandResult", bundle.command_history_js)
        self.assertIn("function renderCommandHistoryPayload", bundle.command_history_js)
        self.assertIn("function getCommandHistory", bundle.command_history_js)
        self.assertIn("function mergeCommandHistory", bundle.command_history_js)
        self.assertIn("function renderCommandSummary", bundle.command_history_js)
        self.assertIn("function renderCommandDetail", bundle.command_history_js)
        self.assertIn("function commandHistorySummaryLines", bundle.command_history_js)
        self.assertIn("function commandHistoryDetailLines", bundle.command_history_js)
        self.assertIn("function commandHistoryCommandText", bundle.command_history_js)
        self.assertIn("function commandHistoryOwnerPage", bundle.command_history_js)
        self.assertIn("function commandHistoryIssueLevel", bundle.command_history_js)
        self.assertIn("function commandHistoryCompactEvidenceLine", bundle.command_history_js)
        self.assertIn("function commandHistoryDiagnosticLine", bundle.command_history_js)
        self.assertIn("function compactCommandHistoryEntries", bundle.command_history_js)
        self.assertIn("function compactCommandHistoryBlockText", bundle.command_history_js)
        self.assertIn("function renderCompactCommandHistoryBlock", bundle.command_history_js)
        self.assertIn("window.commandHistoryCompactEvidenceLine = commandHistoryCompactEvidenceLine", bundle.command_history_js)
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "renderCompactCommandHistoryBlock")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "commandHistoryDiagnosticLine")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "commandHistoryCommandText")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "commandHistoryOwnerPage")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "commandHistoryIssueLevel")
        self.assertIn("function commandHistorySuggestedAction", bundle.command_history_js)
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "commandHistorySuggestedAction")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "commandHistoryIssueEntries")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "commandHistoryRefreshTarget")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "commandHistoryDiagnosticsActions")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "getSelectedCommandEntry")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "commandHistoryRowKey")
        _assert_namespace_export(self, bundle.command_history_js, "mediaPipelineCommandHistory", "selectCommandEntry")
        self.assertNotIn("window.commandHistoryCommandText = commandHistoryCommandText", bundle.command_history_js)
        self.assertNotIn("window.commandHistorySuggestedAction = commandHistorySuggestedAction", bundle.command_history_js)
        self.assertNotIn("window.commandHistoryOwnerPage = commandHistoryOwnerPage", bundle.command_history_js)
        self.assertNotIn("window.commandHistoryIssueLevel = commandHistoryIssueLevel", bundle.command_history_js)
        self.assertNotIn("window.commandHistoryIssueEntries = commandHistoryIssueEntries", bundle.command_history_js)
        self.assertNotIn("window.commandHistoryRefreshTarget = commandHistoryRefreshTarget", bundle.command_history_js)
        self.assertNotIn("window.commandHistoryDiagnosticsActions = commandHistoryDiagnosticsActions", bundle.command_history_js)
        self.assertNotIn("window.getSelectedCommandEntry = getSelectedCommandEntry", bundle.command_history_js)
        self.assertNotIn("window.commandHistoryRowKey = commandHistoryRowKey", bundle.command_history_js)
        self.assertNotIn("window.selectCommandEntry = selectCommandEntry", bundle.command_history_js)
        self.assertIn('command === "backend.shutdown"', bundle.command_history_js)
        self.assertIn("Backend shutdown was requested.", bundle.command_history_js)
        self.assertIn("function commandHistoryIssueDigestLines", bundle.command_history_js)
        self.assertIn("function commandHistoryOwnerLiveStateSummary", bundle.command_history_js)
        self.assertIn("function commandHistoryOwnerLiveStateLines", bundle.command_history_js)
        self.assertIn("Owner page live state handoff:", bundle.command_history_js)
        self.assertIn("Owner page live state", bundle.command_history_js)
        self.assertIn(
            "Compare cached owner-page state with command detail before retrying from the owning page.",
            bundle.command_history_js,
        )
        self.assertIn("getLastQueueRows", bundle.command_history_js)
        self.assertIn("completedView.getLastCompletedRows", bundle.command_history_js)
        self.assertNotIn("typeof getLastCompletedRows === \"function\"", bundle.command_history_js)
        self.assertIn("getLastPendingPublishPayload", bundle.command_history_js)
        self.assertIn("function commandHistoryTraceLines", bundle.command_history_js)
        self.assertIn("function renderCommandResolutionChecklist", bundle.command_history_js)
        self.assertIn("function commandHistoryResolutionRows", bundle.command_history_js)
        self.assertIn("function commandHistoryResolutionStatusState", bundle.command_history_js)
        self.assertIn("Command failure resolution checklist:", bundle.command_history_js)
        self.assertIn(
            "retry or repeat only from the owning page after command detail, refresh target, diagnostics tails, and owner state agree.",
            bundle.command_history_js,
        )
        self.assertIn(
            "Mutation guardrail: this checklist cannot retry, launch, drain, save, rename, repair, delete, publish, open arbitrary paths, or bypass backend validation.",
            bundle.command_history_js,
        )
        self.assertIn("Command issue digest:", bundle.command_history_js)
        self.assertIn("Command trace:", bundle.command_history_js)
        self.assertIn("Owner page:", bundle.command_history_js)
        self.assertIn("Suggested next action:", bundle.command_history_js)
        self.assertIn("command history is read-only", bundle.command_history_js)
        self.assertIn("function selectCommandEntry", bundle.command_history_js)
        self.assertIn("Select a row to inspect backend message", bundle.command_history_js)
        self.assertIn("Local pending visibility:", bundle.command_history_js)
        self.assertIn("const launchHistoryView = window.mediaPipelineLaunchHistoryView || {}", bundle.command_history_js)
        self.assertIn("launchHistoryView.renderLaunchCommandHistory(commandHistory)", bundle.command_history_js)
        self.assertIn("renderPendingDrainHistory(commandHistory)", bundle.command_history_js)
        self.assertIn(
            "renderPendingDrainDecisionChecklist(undefined, undefined, undefined, commandHistory)",
            bundle.command_history_js,
        )
        self.assertIn("renderMaintenanceDryRunHistory(commandHistory)", bundle.command_history_js)
        self.assertIn(
            "window.mediaPipelineSettingsCommandHistory?.renderSettingsCommandHistory?.(commandHistory)",
            bundle.command_history_js,
        )
        self.assertIn("renderQueueOpenHistory(commandHistory)", bundle.command_history_js)
        self.assertIn("renderQueueLaunchDecisionChecklist(undefined, undefined, commandHistory)", bundle.command_history_js)
        self.assertIn("const completedView = window.mediaPipelineCompletedView || {}", bundle.command_history_js)
        self.assertIn("completedView.renderCompletedOpenHistory?.(commandHistory)", bundle.command_history_js)
        self.assertIn("renderPendingOpenHistory(commandHistory)", bundle.command_history_js)
        self.assertIn("function renderDiagnosticsOpenHistoryFromNamespace", bundle.command_history_js)
        self.assertIn("window.mediaPipelineDiagnosticsView?.renderDiagnosticsOpenHistory?.(history)", bundle.command_history_js)
        self.assertIn("renderDiagnosticsOpenHistoryFromNamespace(commandHistory)", bundle.command_history_js)
        self.assertIn("window.mediaPipelineRenameHistoryView?.renderRenameApplyHistory?.(commandHistory)", bundle.command_history_js)
        self.assertNotIn("typeof renderRenameApplyHistory === \"function\"", bundle.command_history_js)
        self.assertNotIn("typeof renderDiagnosticsOpenHistory === \"function\"", bundle.command_history_js)
        self.assertIn("function renderLaunchPipelineControlHistory", bundle.command_history_js)
        self.assertIn("const launchView = window.mediaPipelineLaunchView || {}", bundle.command_history_js)
        self.assertIn("launchView.renderPipelineControlHistory(history)", bundle.command_history_js)
        self.assertIn("renderLaunchPipelineControlHistory(commandHistory)", bundle.command_history_js)
        self.assertNotIn("typeof renderPipelineControlHistory === \"function\"", bundle.command_history_js)
        self.assertIn("window.mediaPipelineReportsView?.renderReportOpenHistory?.(commandHistory)", bundle.command_history_js)
        self.assertNotIn("typeof renderReportOpenHistory === \"function\"", bundle.command_history_js)
        self.assertIn("window.mediaPipelineNetworkView?.renderNetworkOpenHistory?.(commandHistory)", bundle.command_history_js)
        self.assertIn("window.mediaPipelineNetworkView?.initNetworkViewEvents?.();", bundle.js)
