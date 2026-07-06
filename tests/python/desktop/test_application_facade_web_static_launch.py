from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
import unittest

from tests.python.desktop.application_facade_test_support import (
    assert_namespace_export as _assert_namespace_export,
    served_webview_static_contract_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
START_REQUEST_JS = PROJECT_ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launch" / "startRequest.js"
QUEUE_RERUN_REQUEST_JS = PROJECT_ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "queue" / "rerunRequest.js"


def _assert_contains_all(testcase: unittest.TestCase, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        with testcase.subTest(snippet=snippet):
            testcase.assertIn(snippet, text)


def _assert_not_contains_any(testcase: unittest.TestCase, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        with testcase.subTest(snippet=snippet):
            testcase.assertNotIn(snippet, text)


def _assert_launch_exports(testcase: unittest.TestCase, source: str, symbols: tuple[str, ...]) -> None:
    for symbol in symbols:
        with testcase.subTest(symbol=symbol):
            _assert_namespace_export(testcase, source, "mediaPipelineLaunchView", symbol)


def _assert_csv_rerun_exports(testcase: unittest.TestCase, source: str, symbols: tuple[str, ...]) -> None:
    for symbol in symbols:
        with testcase.subTest(symbol=symbol):
            _assert_namespace_export(testcase, source, "mediaPipelineCsvRerunWorkflow", symbol)


class ApplicationFacadeWebStaticLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = served_webview_static_contract_bundle()

    def test_launch_assets_dom_and_tabs_are_static_pinned(self) -> None:
        html = self.bundle.html

        _assert_contains_all(
            self,
            html,
            (
                "/assets/launchReadinessView.js",
                "/assets/launchHistoryView.js",
                "/assets/launch/risk/settingsAccess.js",
                "/assets/launch/risk/mediaPolicyValues.js",
                "/assets/launch/risk/riskRows.js",
                "/assets/launch/risk/policyPatch.js",
                "/assets/launch/risk/policyBoundary.js",
                "/assets/launchView.risk.js",
                "/assets/launchView.scope.js",
                "/assets/launchView.realmedia.js",
                "/assets/launchView.preflight.js",
                "/assets/launch/controllerState.js",
                "/assets/launch/statusRender.js",
                "/assets/launch/startRequest.js",
                "/assets/queue/rerunRequest.js",
                "/assets/launch/scopeControls.js",
                "/assets/launch/commandButtons.js",
                "/assets/launchView.js",
                'id="launch-settings-intent-status"',
                'id="launch-settings-intent-summary"',
                'id="launch-settings-intent-rows"',
                'id="launch-settings-intent-detail"',
                'id="launch-scope-reconciliation-status"',
                'id="launch-scope-reconciliation-summary"',
                'id="launch-scope-reconciliation-rows"',
                'id="launch-scope-reconciliation-detail"',
                'id="launch-start-decision-status"',
                'id="launch-start-decision-summary"',
                'id="launch-start-decision-rows"',
                'id="launch-start-decision-detail"',
                'id="launch-real-media-proof-status"',
                'id="launch-real-media-proof-summary"',
                'id="launch-real-media-proof-rows"',
                'id="launch-real-media-proof-detail"',
                'id="launch-sample-execution-status"',
                'id="launch-sample-execution-summary"',
                'id="launch-sample-execution-rows"',
                'id="launch-sample-execution-detail"',
                'id="launch-pilot-readiness-status"',
                'id="launch-pilot-readiness-summary"',
                'id="launch-pilot-readiness-rows"',
                'id="launch-pilot-readiness-detail"',
                'id="launch-backend-preflight-status"',
                'id="launch-backend-preflight-summary"',
                'id="launch-backend-preflight-rows"',
                'id="launch-backend-preflight-detail"',
                'data-page-panel="launch"',
                'data-launch-tab="pipeline"',
                'data-launch-tab="history"',
                'data-launch-tab-panel="pipeline"',
                'data-launch-tab-panel="history"',
                'data-page-panel="queue"',
                'data-queue-tab="rerun"',
                'data-queue-tab-panel="rerun"',
                "launch-readiness-status",
                "launch-readiness",
                "launch-timing-status",
                "launch-timing",
                "launch-settings-trust-status",
                "launch-settings-trust-summary",
                "launch-settings-risk-status",
                "launch-settings-risk-summary",
                "launch-settings-risk-rows",
                "launch-settings-risk-detail",
                "pipeline-start-mode",
                "pipeline-start-single-file",
                "pipeline-single-file-path-picker-badge",
                'data-path-picker-target="launch.single_file"',
                'data-path-picker-input="pipeline-start-single-file"',
                "pipeline-single-file-browse-button",
                "pipeline-single-file-clear-button",
                "pipeline-single-file-browse-status",
                "Advanced Controller",
                "pipeline-start-schedule-override",
                "Start Evidence",
                "pipeline-launch-preflight",
                "pipeline-start-button",
                "rerun-review-header",
                "rerun-review-status",
                "rerun-review-csv",
                "rerun-review-counts",
                "rerun-review-next-action",
                "CSV rerun review summary",
                "rerun-lifecycle-evidence",
                "rerun-lifecycle-title",
                "rerun-lifecycle-phase",
                "rerun-lifecycle-summary",
                "rerun-lifecycle-detail",
                "Lifecycle Evidence",
                "rerun-start-csv-path",
                'aria-describedby="rerun-mode-policy-note"',
                "rerun-start-execution-mode",
                "rerun-start-window-size",
                "rerun-start-destination-mode",
                "rerun-start-collision-policy",
                "auto destination",
                "auto collision",
                "Rerun handling",
                "Destination Collision",
                'data-rerun-policy-card="destination"',
                'data-rerun-policy-card="collision"',
                "Destination handling",
                "When output exists",
                "Clean verified outputs use backend-derived final placement",
                "rerun-mode-policy-note",
                "rerun-csv-path-picker-badge",
                'data-path-picker-target="queue.rerun_csv"',
                'data-path-picker-input="rerun-start-csv-path"',
                "rerun-queue-preflight",
                "rerun-scope-enabled-only",
                "rerun-scope-skip-blocked",
                "rerun-scope-skip-warning-rows",
                "rerun-scope-first-n",
                "rerun-scope-issue-filter",
                "rerun-scope-bucket-filter",
                "rerun-preview-limit",
                "rerun-preview-tiles",
                "rerun-recent-csv-rows",
                "rerun-preview-summary",
                "rerun-policy-panel",
                "rerun-preview-rows",
                "rerun-preview-table",
                "<th scope=\"col\">Identity</th>",
                "<th scope=\"col\">Categories</th>",
                "rerun-results-panel",
                "rerun-history-summary",
                'id="rerun-open-audit-tool-button"',
                'id="rerun-inspect-csv-button"',
                'id="rerun-open-csv-button"',
                'id="rerun-open-csv-folder-button"',
                "Typed CSV paths can be previewed; Open CSV requires",
                "Typed CSV paths can be previewed; Open Folder requires",
                'id="rerun-open-latest-manifest-button"',
                'id="rerun-open-run-logs-button"',
                'id="rerun-open-last-stdout-button"',
                'id="rerun-open-last-stderr-button"',
                'id="rerun-open-active-jobs-button"',
                'id="rerun-show-command-history-button"',
                'data-cross-page-target="reports" data-cross-page-reports-tab="audit"',
                "rerun-start-button",
                "Review &amp; Start",
                "launch-history-status",
                "launch-history",
                "launch-command-review-status",
                "launch-command-review-summary",
                "launch-command-review-rows",
                "launch-command-review-legend",
                "launch-command-review-detail",
                "launch-command-diagnostics-guidance",
                "launch-command-diagnostics-actions",
                "Checklist Correlation",
                "launch-policy-boundary-summary",
                "launch-policy-boundary-detail",
                "launch-backend-preflight-refresh-button",
                "Refresh Backend Preflight",
                "launch-encoder-capability-refresh-button",
                "Refresh Encoder Evidence",
            ),
        )
        _assert_not_contains_any(
            self,
            html,
            (
                "Confirm Replace Final",
                "Confirm Original Policy",
                "Confirm Hold/Delete Intent",
                "rerun-confirm-replace-final",
                "rerun-confirm-original-policy",
                "rerun-confirm-delete-original",
            ),
        )
        self.assertNotIn("rerun-plan-only-button", html)
        self.assertNotIn("Plan CSV Rerun", html)
        self.assertNotIn("rerun-dry-run-button", html)
        self.assertNotIn("Preview CSV Rerun", html)
        self.assertNotIn("rerun-start-show-console", html)
        self.assertNotIn('data-launch-tab="rerun"', html)
        self.assertNotIn('data-launch-tab-panel="rerun"', html)
        self.assertNotIn('data-path-picker-target="launch.rerun_csv"', html)
        self.assertNotIn('data-launch-tab="audit"', html)
        self.assertNotIn('data-launch-tab-panel="audit"', html)
        for absent in (
            "Selected Mode",
            'id="audit-start-library-root"',
            'id="audit-launch-preflight"',
            'id="audit-launch-progress-status"',
            'id="audit-launch-log-rows"',
            'id="audit-score-policy-save-button"',
            "High issue: <code>foreign-audio-no-text-subtitles</code>",
            'id="audit-ignore-selected-button"',
            'id="audit-export-rerun-csv-button"',
            'id="audit-start-button"',
        ):
            self.assertNotIn(absent, html)
        launch_tab_order = [
            'data-launch-tab="pipeline"',
            'data-launch-tab="history"',
        ]
        prior_index = -1
        for launch_tab in launch_tab_order:
            current_index = html.index(launch_tab)
            self.assertGreater(current_index, prior_index)
            prior_index = current_index
        self.assertEqual(html.count('id="pipeline-start-button"'), 1)
        self.assertLess(html.index('id="pipeline-start-show-console"'), html.index('id="pipeline-start-button"'))
        self.assertLess(html.index('id="pipeline-start-button"'), html.index('id="launch-start-decision-status"'))

    def test_launch_readiness_and_history_contracts_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.launch_readiness_view_js,
            (
                "window.mediaPipelineLaunchReadinessView",
                "function launchReadinessSettingsStatus",
                "function launchReadinessStatus",
                "function launchReadinessLines",
                "function launchReadinessScheduleWatcherSummary",
                "function launchReadinessBackendReadiness",
                "function launchReadinessBackendLines",
                "Launch readiness (backend-authored):",
                "Evidence authority: frontend advisory only until backend preflight payload is loaded.",
                "function launchTimingTrustLines",
                "function renderLaunchTimingTrust",
                "function getLastLaunchReadinessPayload",
                "window.mediaPipelineLaunchView?.renderLaunchSettingsIntentChecklist?.(undefined, lastLaunchReadinessPayload)",
                "Launch timing trust:",
                "Mutation guardrail: this Launch timing panel is read-only",
                "function renderLaunchReadiness",
                "Saved settings:",
                "Settings issue",
                "Saved settings need review",
                "Active work is reported",
                "Backend launch locking and gating remain the source of truth.",
                "Run Once and Continuous are schedule-blocked",
                "Backend continuous watcher:",
                "Continuous schedule-stop watcher",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.launch_readiness_view_js,
            (
                "window.launchReadinessStatus =",
                "window.launchReadinessStatusState =",
                "window.launchReadinessLines =",
                "window.launchReadinessRecoveryActions =",
                "window.renderLaunchReadinessRecoveryActions =",
                "window.launchTimingStatus =",
                "window.launchTimingTrustLines =",
                "window.renderLaunchTimingTrust =",
                "window.renderLaunchReadiness =",
                "window.getLastLaunchReadinessPayload =",
            ),
        )
        _assert_contains_all(
            self,
            bundle.launch_history_view_js,
            (
                "window.mediaPipelineLaunchHistoryView",
                "function isLaunchCommand",
                'return command === "pipeline.start"',
                "function renderLaunchCommandHistory",
                "function launchHistoryLine",
                "function launchHistoryTarget",
                "function launchHistoryRequest",
                "function launchCommandCorrelationRows",
                "function launchCommandCorrelationStatus",
                "function launchCommandCorrelationSummary",
                "function launchCommandDiagnosticsActions",
                "function launchCommandDiagnosticsGuidanceLines",
                "function renderLaunchCommandDiagnosticsActions",
                "function launchCommandReviewRows",
                "function launchCommandReviewDetailLines",
                "function renderLaunchCommandReview",
                "commandHistoryView.commandHistoryRowKey(entry)",
                "commandHistoryView.selectCommandEntry(item.entry)",
                "commandHistoryView.commandHistoryRefreshTarget(entry)",
                "commandHistoryView.commandHistoryDiagnosticsActions(entry)",
                "commandHistoryView.commandHistorySuggestedAction(entry)",
                "Launch command review:",
                "Checklist correlation:",
                "Correlated checklist/preflight context:",
                "Predicted by checklist",
                "Not predicted by cached checks",
                "Launch diagnostics retry guidance:",
                "Retry rule: do not press Start again until command detail, correlated checklist context, and diagnostics targets agree on the cause.",
                "these actions use backend allowlisted diagnostics targets only",
                "launchCommandDiagnosticsAdd(actions, \"open\", \"queue_snapshot\"",
                "launchCommandDiagnosticsAdd(actions, \"open\", \"active_jobs\"",
                "requestCommandDiagnosticsAction(action)",
                "function launchViewApi",
                "launchView.launchBackendPreflightPayloadForTarget(target)",
                "queueLaunchDecisionRows(undefined, undefined, history)",
                "launchView.launchSettingsIntentRows(request)",
                "selecting a launch command review row selects that command",
                "pipeline launch, Queue CSV Rerun, drain, and control commands remain backend-owned",
                "Pending Publish drain history remains on the Pending Publish page.",
                "commandHistoryCompactEvidenceLine(entry",
                "Backend launch locking and validation remain the source of truth.",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.launch_history_view_js,
            (
                "typeof commandHistoryRowKey === \"function\"",
                "typeof selectCommandEntry === \"function\"",
                "window.launchCommandCorrelationRows =",
                "window.launchCommandCorrelationStatus =",
                "window.launchCommandDiagnosticsActions =",
                "window.launchCommandReviewRows =",
                "window.launchCommandReviewStatus =",
                "window.launchCommandReviewSummaryLines =",
                "window.renderLaunchCommandHistory =",
                "window.isLaunchCommand =",
                "window.launchHistoryLine =",
            ),
        )

    def test_launch_view_control_and_start_requests_are_backend_owned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.launch_view_js,
            (
                "window.mediaPipelineLaunchView",
                "function requestPipelineControl",
                "function confirmControlAction",
                "const routeToRerunControl = (normalized === \"stop\" || normalized === \"pause\") && launchRerunCsvIsActive",
                "const rerunControlDispatcher = normalized === \"pause\" ? \"postRerunControlPause\" : \"postRerunControlStopAfterCurrent\";",
                "queueRerunRouteDispatcher(rerunControlDispatcher)()",
                "let controlCommandInFlight = false",
                "function setControlCommandBusy",
                "function rejectControlCommandWhileBusy",
                "Another pipeline control command is already in progress.",
                "mediaPipelineLaunchReadinessView",
                "mediaPipelineLaunchHistoryView",
                "const launchReadinessStatus = launchReadinessView.launchReadinessStatus || window.launchReadinessStatus",
                "const launchTimingStatus = launchReadinessView.launchTimingStatus || window.launchTimingStatus",
                "const getLastLaunchReadinessPayload = launchReadinessView.getLastLaunchReadinessPayload || window.getLastLaunchReadinessPayload",
                "const isLaunchCommand = launchHistoryView.isLaunchCommand || function () { return false; }",
                "const renderLaunchCommandHistory = launchHistoryView.renderLaunchCommandHistory || function () {}",
                "const launchCommandCorrelationRows = launchHistoryView.launchCommandCorrelationRows",
                "launchCommandReviewRows: typeof launchCommandReviewRows === \"function\" ? launchCommandReviewRows : null",
                "function createLaunchControllerStateModule",
                "window.__launchControllerStateModule",
                "const launchControllerStateModule = window.__launchControllerStateModule || {}",
                "delete window.__launchControllerStateModule",
                "function createLaunchStatusRenderModule",
                "window.__launchStatusRenderModule",
                "const launchStatusRenderModule = window.__launchStatusRenderModule || {}",
                "delete window.__launchStatusRenderModule",
                "function createLaunchStartRequestModule",
                "window.__launchStartRequestModule",
                "const launchStartRequestModule = window.__launchStartRequestModule || {}",
                "delete window.__launchStartRequestModule",
                "window.__queueRerunRequestModule",
                "const queueRerunRequestModule = window.__queueRerunRequestModule || {}",
                "delete window.__queueRerunRequestModule",
                "function createLaunchScopeControlsModule",
                "window.__launchScopeControlsModule",
                "const launchScopeControlsModule = window.__launchScopeControlsModule || {}",
                "delete window.__launchScopeControlsModule",
                "function createLaunchCommandButtonsModule",
                "window.__launchCommandButtonsModule",
                "const launchCommandButtonsModule = window.__launchCommandButtonsModule || {}",
                "delete window.__launchCommandButtonsModule",
                "const launchCommandButtonIds",
                "CSV rerun active: current row/window will finish; no next CSV row starts.",
                "Pause CSV rerun after the current row/window; no next CSV row starts until Continue Pending Rows is used.",
                "CSV rerun does not support Rescan; use Pause or Stop After Current to finish the current row/window first.",
                "function setLaunchCommandBusy",
                "function rejectLaunchCommandWhileBusy",
                "Another launch command is already in progress.",
                "function collectPipelineStartRequest",
                'byId("pipeline-start-single-file")',
                "request.single_file = singleFile",
                "function browsePipelineSingleFile",
                'apiPost("/api/pipeline/browse-file", request)',
                "function startPipelineFromForm",
                "Submitting ${label} for ${scope}. Backend will re-check queue, settings, schedule, and locks before starting.",
                "Pipeline start request submitted to the backend; backend launch guards remain authoritative.",
                "function launchCommandStatusLabel",
                "function launchCommandResultCorrelationLines",
                "Command evidence snapshot:",
                "Diagnostics retry guidance:",
                "launchCommandDiagnosticsActions(entry)",
                "Evidence is explanatory only; backend start routes remain authoritative at submission time.",
                "function formatLaunchCommandDetail",
                "function renderLaunchCommandResult",
                "function initLaunchViewEvents",
                "function initLaunchTabNav",
                "function activateLaunchTab",
                "mediapipeline-launch-tab",
                "commandResultDisplayMessage(payload)",
                "Backend data:",
                "Submitted request:",
                "pending-drain-detail",
                "/api/pipeline/start",
            ),
        )
        _assert_launch_exports(
            self,
            bundle.launch_view_js,
            (
                "requestPipelineControl",
                "isPipelineControlCommand",
                "pipelineControlHistoryLine",
                "renderPipelineControlHistory",
                "syncPipelineModeControls",
                "selectPipelineModePreset",
                "browsePipelineSingleFile",
                "clearPipelineSingleFile",
                "startPipelineFromForm",
                "initLaunchViewEvents",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.launch_view_js,
            (
                "window.requestPipelineControl =",
                "window.isPipelineControlCommand =",
                "window.pipelineControlHistoryLine =",
                "window.renderPipelineControlHistory =",
                "window.launchReadinessStatus =",
                "window.launchReadinessLines =",
                "window.renderLaunchReadiness =",
                "window.isLaunchCommand =",
                "window.renderLaunchCommandHistory =",
                "window.launchHistoryLine =",
                "window.syncPipelineModeControls =",
                "window.selectPipelineModePreset =",
                "window.browsePipelineSingleFile =",
                "window.clearPipelineSingleFile =",
                "window.startPipelineFromForm =",
                "window.initLaunchViewEvents =",
                "function collectAuditStartRequest",
                "function startAuditFromForm",
                "function renderLaunchAuditControls",
                "/api/audit/",
                "renderLaunchAuditIssueRows",
                "function renderLaunchAuditLog",
                "renderLaunchAuditControls",
                "renderLaunchAuditLog",
                "window.confirm(pipelineStartConfirmMessage(request, label))",
                "Pipeline start request confirmed by the operator",
            ),
        )
        _assert_contains_all(
            self,
            bundle.launch_view_preflight_js,
            (
                "function renderPipelineControlHistory",
                "function isPipelineControlCommand",
                'command.startsWith("rerun.control.")',
                "No pipeline or CSV rerun control command history loaded.",
                "Backend control-flag writes and launch locks remain the source of truth.",
                "Single-file launch: WebView submits the path only",
                "Backend validation and launch locking remain the source of truth.",
                "operator_readiness",
                "rerunPreflightLabels",
                '`Execution: ${rerunPreflightLabel("execution", request.execution_mode, "one_at_a_time")}; window=${request.window_size || 1}`',
                '`Destination handling: ${rerunPreflightLabel("destination", request.destination_mode, "auto_replace_clean_else_pending_review")}; collision=${rerunPreflightLabel("collision", request.collision_policy, "replace_final")}`',
                'Source handling: source overwrite ${request.confirm_source_overwrite ? "confirmed" : "not confirmed"}; destination/collision determine verified-output placement.',
                "function rerunOutputPairingLine",
                "Pairing note: final-output replacement keeps source files untouched unless source-path overwrite is explicitly confirmed.",
                'Scope: enabled only ${scope.enabled_only !== false ? "yes" : "no"}',
                "Confirmation warning: replacing a final output requires confirm_replace_final=true.",
                "Safety policy: live rerun stages bounded scratch input, verifies output, applies destination policy, and only overwrites a source path when explicitly confirmed.",
            ),
        )

    def test_launch_risk_policy_and_settings_intent_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.launch_view_risk_js,
            (
                "function createLaunchRiskModule",
                "window.__launchViewRiskModule",
                "function launchSettingsTrustStatus",
                "function launchSettingsDecision",
                "function launchSettingsDecisionLines",
                "function launchSettingsRiskLines",
                "function launchRealMediaReadinessLines",
                "function launchSettingsRiskRows",
                "function launchSettingsRiskDetailLines",
                "function renderLaunchSettingsRiskHandoff",
                "Launch Risk Handoff detail:",
                "Daily-driver rule: resolve blocked rows",
                "Proof chain:",
                "function launchPolicyBoundaryRows",
                "function renderLaunchPolicyBoundary",
                "Launch active media-policy boundary:",
                "Active saved subtitle policy",
                "Staged subtitle candidate",
                "Active saved audio policy",
                "Staged audio candidate",
                "Active saved publish/source safety",
                "Staged publish/source candidate",
                "Launch uses the active saved subtitle, audio, and pending-publish/source-safety policy",
                "function launchSettingsIntentRows",
                "function renderLaunchSettingsIntentChecklist",
                "Saved settings evidence:",
                "Launch settings evidence snapshot:",
                "Launch settings risk handoff:",
                "Real-media validation boundary",
                "Preview/build/release checks prove shell/package readiness only",
                "Real-media proof still requires a completed sample run",
                "Saved settings vs launch intent checklist:",
                "Launch uses saved backend settings and selected form intent only",
                "unsaved Settings changes do not count until Save Settings succeeds",
                "Queue display scope",
                "Do not treat the visible Queue table as launch scope",
                "Launch start requests do not include Queue filter text",
                "Backend Launch remains authoritative for queue scope",
                "queueCurrentFilterScope(queueRows)",
                "Mutation guardrail: this checklist is read-only and cannot launch, save settings, drain, rename, repair, delete, publish, or touch media files.",
                "This panel translates saved settings posture into launch-specific operator checks.",
                "Evidence guidance:",
                "Evidence owner: Settings page edits/save; Launch page displays saved posture only.",
                "Backend risk summary:",
                "Deferred publish:",
                "PATH tool fallback:",
                "H.264 copy / remux precision",
                "Container / original subtitle preservation",
                "Plex-compatible H.264 sources should remain copy/remux candidates",
                "MP4 cannot carry every original subtitle format",
                "normal growth=${maxGrowth}%",
                "Do not launch media work with drop-without-convert subtitle contradictions.",
                "No-audio output is unsafe for normal Plex publishing",
                "Backend launch validation, process locks, and Settings Save remain the source of truth.",
            ),
        )
        _assert_contains_all(
            self,
            bundle.launch_view_js,
            (
                "const launchRiskModule = window.__launchViewRiskModule || {}",
                "delete window.__launchViewRiskModule",
                "launchRiskModule.createLaunchRiskModule",
            ),
        )
        _assert_launch_exports(
            self,
            bundle.launch_view_js,
            (
                "launchSettingsWorkspace",
                "launchSettingsTrustStatus",
                "launchSettingsDecision",
                "launchSettingsDecisionLines",
                "launchSettingsRiskLines",
                "launchRealMediaReadinessLines",
                "launchSettingsRiskRows",
                "launchSettingsRiskStatus",
                "launchSettingsRiskSummaryLines",
                "launchSettingsRiskDetailLines",
                "renderLaunchSettingsRiskHandoff",
                "launchPolicyBoundaryRows",
                "launchPolicyBoundaryStatus",
                "launchPolicyBoundarySummaryLines",
                "launchPolicyBoundaryDetailLines",
                "renderLaunchPolicyBoundary",
                "launchSettingsIntentRows",
                "launchSettingsIntentStatus",
                "renderLaunchSettingsIntentChecklist",
                "launchSettingsIntentSummaryLines",
                "launchSettingsIntentDetailLines",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.launch_view_js,
            (
                "window.launchSettingsWorkspace =",
                "window.launchSettingsTrustStatus =",
                "window.launchSettingsDecision =",
                "window.launchSettingsDecisionLines =",
                "window.launchSettingsRiskLines =",
                "window.launchRealMediaReadinessLines =",
                "window.launchSettingsRiskRows =",
                "window.launchSettingsRiskStatus =",
                "window.launchSettingsRiskSummaryLines =",
                "window.renderLaunchSettingsRiskHandoff =",
                "window.launchPolicyBoundaryStatus =",
                "window.launchPolicyBoundarySummaryLines =",
                "window.launchPolicyBoundaryDetailLines =",
                "window.renderLaunchPolicyBoundary =",
                "window.launchSettingsIntentRows =",
                "window.launchSettingsIntentStatus =",
                "window.renderLaunchSettingsIntentChecklist =",
                "window.launchSettingsIntentSummaryLines =",
                "window.launchSettingsIntentDetailLines =",
            ),
        )
        self.assertIn("renderLaunchPolicyBoundary()", bundle.launch_view_preflight_js)
        self.assertIn("renderLaunchSettingsIntentChecklist(pipelineRequest)", bundle.launch_view_preflight_js)
        self.assertIn("renderLaunchSettingsRiskHandoff(pipelineRequest)", bundle.launch_view_preflight_js)
        self.assertIn("launchView.renderLaunchSettingsIntentChecklist?.()", bundle.command_history_js)

    def test_launch_scope_realmedia_and_preflight_are_static_pinned(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.launch_view_scope_js,
            (
                "function createLaunchScopeModule",
                "window.__launchViewScopeModule",
                "function launchScopeReconciliationRows",
                "function renderLaunchScopeReconciliation",
                "Launch scope reconciliation:",
                "these read-only signals explain launch posture; backend start remains authoritative",
                "Mutation guardrail: this reconciliation is read-only",
                "function launchStartDecisionRows",
                "function renderLaunchStartDecisionSummary",
                "Launch start decision summary:",
                "treat these signals as advisory evidence for Start; backend start remains authoritative",
                "Mutation guardrail: this summary is read-only",
            ),
        )
        _assert_contains_all(
            self,
            bundle.launch_view_realmedia_js,
            (
                "function createLaunchRealMediaModule",
                "window.__launchViewRealMediaModule",
                "function launchPolicyAlignmentQueueIntentEvidence",
                "Saved policy vs Queue route:",
                "Saved policy vs Queue route evidence packet:",
                "Advisory boundary: queue-route matching uses loaded route/status text only.",
                "function launchRealMediaProofRows",
                "function renderLaunchRealMediaProofHandoff",
                "Launch real-media sample proof handoff:",
                "Home Real-Media Validation Worksheet",
                "daily-driver trust still requires post-run output",
                "function launchSampleExecutionRows",
                "function renderLaunchSampleExecutionChecklist",
                "Launch sample execution checklist:",
                "Home's backend-authored operator sample execution checklist",
            ),
        )
        _assert_contains_all(
            self,
            bundle.launch_view_preflight_js,
            (
                "function createLaunchPreflightModule",
                "window.__launchViewPreflightModule",
                "function launchPilotRunReadinessRows",
                "function renderLaunchPilotRunReadiness",
                "Launch pilot run readiness:",
                "selected Queue sample, saved Settings policy, backend preflight, pilot category, pending-publish posture, and post-run proof plan",
                "function launchBackendPreflightRows",
                "function getLastLaunchBackendPreflightPayloads",
                "function launchBackendPreflightPayloadForTarget",
                "function getLastLaunchBackendPreflightRefreshInfo",
                "function refreshLaunchBackendPreflight",
                "function refreshLaunchBackendPreflightEncoderCapability",
                "refresh_encoder_capability_report",
                "refresh_encoder_capability_report_requested",
                "Last refresh:",
                "fetch_failure_count",
                "renderQueueLaunchDecisionChecklist()",
                "/api/launch/preflight",
                "GET /api/launch/preflight",
                "This read route mirrors backend launch guards without journaling commands or mutating runtime state",
                "Mutation guardrail: this panel cannot launch, reserve locks, clear flags, save settings, drain, rename, repair, delete, publish, or touch media files.",
                "function pipelineLaunchPreflightLines",
                "function rerunQueuePreflightLines",
                "const launchReadinessView = window.mediaPipelineLaunchReadinessView || {}",
                "launchReadinessView.getLastLaunchReadinessPayload()",
                "launchReadinessView.renderLaunchReadiness({",
                "renderLaunchTimingTrust()",
                "renderScheduleTimingTrust()",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.launch_view_preflight_js,
            (
                "function renderLaunchAuditProgress",
                "audit-launch-progress-bars",
                "function auditLaunchPreflightLines",
            ),
        )
        _assert_contains_all(
            self,
            bundle.launch_view_js,
            (
                "const launchScopeModule = window.__launchViewScopeModule || {}",
                "delete window.__launchViewScopeModule",
                "launchScopeModule.createLaunchScopeModule",
                "const launchRealMediaModule = window.__launchViewRealMediaModule || {}",
                "delete window.__launchViewRealMediaModule",
                "launchRealMediaModule.createLaunchRealMediaModule",
                "const launchPreflightModule = window.__launchViewPreflightModule || {}",
                "delete window.__launchViewPreflightModule",
                "launchPreflightModule.createLaunchPreflightModule",
                "refreshLaunchBackendPreflight()",
                "refreshLaunchBackendPreflightEncoderCapability()",
                "launch-encoder-capability-refresh-button",
                "const scheduleView = window.mediaPipelineScheduleView || {}",
                "renderScheduleTimingTrust: typeof renderScheduleTimingTrust === \"function\" ? renderScheduleTimingTrust : null",
            ),
        )
        _assert_launch_exports(
            self,
            bundle.launch_view_js,
            (
                "launchScopeReconciliationRows",
                "launchScopeReconciliationStatus",
                "launchScopeReconciliationSummaryLines",
                "launchScopeReconciliationDetailLines",
                "launchStartDecisionRows",
                "launchStartDecisionStatus",
                "launchStartDecisionSummaryLines",
                "launchStartDecisionDetailLines",
                "renderLaunchStartDecisionSummary",
                "launchWorksheetRunRows",
                "launchWorksheetRunsMatchingSample",
                "launchPolicyAlignmentPayload",
                "launchPolicyAlignmentRows",
                "launchWorksheetEvidence",
                "launchQueueIntentCategoryMatch",
                "launchPolicyAlignmentQueueIntentEvidence",
                "launchRealMediaProofRows",
                "launchRealMediaProofStatus",
                "launchRealMediaProofSummaryLines",
                "launchRealMediaProofDetailLines",
                "renderLaunchRealMediaProofHandoff",
                "launchSampleSetCoverageLine",
                "launchSampleValidationRecordEvidence",
                "launchSampleValidationRecordRows",
                "launchSampleValidationRecordsMatchingSample",
                "launchSampleExecutionRows",
                "launchSampleExecutionStatus",
                "launchSampleExecutionSummaryLines",
                "launchSampleExecutionDetailLines",
                "renderLaunchSampleExecutionChecklist",
                "launchPilotRunReadinessRows",
                "launchPilotRunReadinessStatus",
                "launchPilotRunReadinessSummaryLines",
                "launchPilotRunReadinessDetailLines",
                "renderLaunchPilotRunReadiness",
                "launchBackendPreflightRows",
                "getLastLaunchBackendPreflightPayloads",
                "launchBackendPreflightPayloadForTarget",
                "getLastLaunchBackendPreflightRefreshInfo",
                "launchBackendPreflightSummaryLines",
                "launchBackendPreflightDetailLines",
                "renderLaunchBackendPreflight",
                "refreshLaunchBackendPreflight",
                "refreshLaunchBackendPreflightEncoderCapability",
                "pipelineLaunchPreflightLines",
            ),
        )

    def test_queue_rerun_helpers_and_pending_drain_commands_are_guarded(self) -> None:
        bundle = self.bundle

        _assert_contains_all(
            self,
            bundle.launch_view_js,
            (
                "window.mediaPipelineCsvRerunWorkflow",
                "function startRerunFromForm",
                "function refreshRerunPreview",
                "function refreshRerunResults",
                "function renderRerunPreview",
                "function renderRerunResults",
                "function requestRerunContinue",
                "function renderRerunHistorySummary",
                "function renderRerunReviewHeader",
                "function renderRerunLifecycleEvidence",
                "function renderRerunPreviewCategoryChips",
                "function applyRerunOpenButtonState",
                "lookup_title",
                "relative_path",
                "duplicate_source",
                "entry.raw?.request",
                "result?.request?.csv_path",
                "Scoped row count:",
                "Typed CSV paths can be previewed, but Open CSV and Open Folder require",
                "function rerunPreviewConflictLines",
                "Why blocked:",
                "Selected policy conflict:",
                "Executable CSV rerun currently supports scratch-copy staging, backend-owned destination handling, and explicit source-path overwrite confirmation.",
                'queueRerunRouteDispatcher("postRerunStart")(request)',
                'queueRerunRouteDispatcher("postRerunPreview")(request)',
                'queueRerunRouteDispatcher("getRerunResults")()',
                'queueRerunRouteDispatcher("postRerunContinue")(request)',
                "Continue Pending Rows",
                "confirm_continue: true",
                "can_continue_pending",
                "RERUN_POLICY_CHOICES",
                "function rerunPolicyConflictReason",
                "function applyRerunPolicySelectionRules",
                "function updateRerunPolicyOptionStates",
                "option.dataset.rerunConflict = reason ? \"true\" : \"false\"",
                "Auto-adjusted ${kind} pairing.",
                "Backend still receives concrete policy values after auto resolution.",
                "Auto resolved from the current destination/collision policy before backend submit.",
                "function rerunSourceHandlingLine",
                "Source handling: source files stay untouched unless source-path overwrite is explicitly confirmed.",
                "function renderRerunHandlingSummary",
                "function rerunStartPolicySummary",
                "Destination handling: ${destination.label}. ${destination.detail}",
                "rerunPreviewBlockedReason",
                "frontend_guard: true",
                'mode: "drain_pending_pushes"',
                'command: "pending_publish.drain"',
                'typeof pendingDrainGuardState === "function" ? pendingDrainGuardState() : null',
                "frontend_guard: true",
                "guard?.confirm_message",
            ),
        )
        _assert_contains_all(
            self,
            bundle.queue_rerun_request_js,
            (
                "function createQueueRerunRequestModule",
                "window.__queueRerunRequestModule",
                "function collectRerunStartRequest",
                "function collectRerunScopeRequest",
                "function collectRerunPreviewRequest",
                'execution_mode: byId("rerun-start-execution-mode")?.value || "one_at_a_time"',
                "destination_mode: destinationMode",
                "confirm_replace_final: replaceFinalRequested",
                "confirm_source_overwrite: replaceFinalRequested && sourceOverwriteConfirmed",
                "function resolveRerunPolicySelection",
                "scope,",
            ),
        )
        _assert_csv_rerun_exports(
            self,
            bundle.launch_view_js,
            (
                "collectRerunPreviewRequest",
                "collectRerunScopeRequest",
                "collectRerunStartRequest",
                "renderRerunReviewHeader",
                "renderRerunLifecycleEvidence",
                "renderRerunPreviewCategoryChips",
                "applyRerunOpenButtonState",
                "refreshRerunPreview",
                "inspectSelectedRerunCsv",
                "openSelectedRerunCsv",
                "renderRerunPreview",
                "refreshRerunResults",
                "renderRerunResults",
                "requestRerunContinue",
                "renderRerunHistorySummary",
                "startRerunFromForm",
                "rerunQueuePreflightLines",
                "renderRerunQueuePreflight",
            ),
        )
        _assert_not_contains_any(
            self,
            bundle.launch_view_js,
            (
                "if (request.plan_only) {\n      await refreshRerunPreview();",
                "appendCommandResult(blocked);",
                "appendCommandResult(missing);",
                "window.collectRerunStartRequest =",
                "window.startStateJournalArchive =",
                "window.startRerunFromForm =",
            ),
        )
        _assert_contains_all(
            self,
            bundle.queue_view_js,
            (
                'wireClick("rerun-start-button", () => startRerunFromForm({ dry_run: false }))',
                '"rerun-start-confirm-source-overwrite"',
            ),
        )
        _assert_contains_all(
            self,
            bundle.js,
            (
                "function renderLaunchReadinessPanel",
                "window.mediaPipelineLaunchReadinessView?.renderLaunchReadiness?.(payload)",
                "renderLaunchReadinessPanel({",
                "settings: getLastSettings()",
                "settings: values.settings || getLastSettings()",
                "startupProgressLines",
                "bootstrap.startupProgress",
                'refreshGet("/api/health", refreshOptions)',
                "values.health?.startup_progress",
            ),
        )

    def test_rerun_policy_auto_resolver_submits_concrete_backend_values(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")

        script = """
const fs = require("fs");
global.window = {};
const source = fs.readFileSync(__QUEUE_RERUN_REQUEST_PATH__, "utf8");
eval(source);
const fields = {
  "rerun-start-window-size": { value: "1" },
  "rerun-start-csv-path": { value: "C:/Media/rerun.csv" },
  "rerun-start-execution-mode": { value: "one_at_a_time" },
  "rerun-start-destination-mode": { value: "auto" },
  "rerun-start-collision-policy": { value: "replace_final" },
  "rerun-start-confirm-source-overwrite": { checked: true },
  "rerun-scope-enabled-only": { checked: true },
  "rerun-scope-skip-blocked": { checked: false },
  "rerun-scope-skip-warning-rows": { checked: false },
  "rerun-scope-first-n": { value: "0" },
  "rerun-preview-limit": { value: "50" },
  "rerun-scope-issue-filter": { options: [] },
  "rerun-scope-bucket-filter": { options: [] },
};
const startModule = window.__queueRerunRequestModule.createQueueRerunRequestModule({
  byId(id) { return fields[id] || null; },
});
function assertEqual(actual, expected, label) {
  if (actual !== expected) throw new Error(`${label}: expected ${expected}, got ${actual}`);
}
const replacement = startModule.collectRerunStartRequest({ dry_run: false });
assertEqual(replacement.destination_mode, "auto_replace_clean_else_pending_review", "replacement destination");
assertEqual(replacement.collision_policy, "replace_final", "replacement collision");
assertEqual(replacement.confirm_replace_final, true, "replacement confirmation");
assertEqual(replacement.confirm_source_overwrite, true, "source overwrite confirmation");
if ("original_policy" in replacement) throw new Error("replacement should not send original_policy");
if ("confirm_original_policy" in replacement) throw new Error("replacement should not send confirm_original_policy");

fields["rerun-start-destination-mode"].value = "auto";
fields["rerun-start-collision-policy"].value = "suffix";
fields["rerun-start-confirm-source-overwrite"].checked = true;
const safe = startModule.collectRerunStartRequest({ dry_run: false });
assertEqual(safe.destination_mode, "review_workspace", "safe destination");
assertEqual(safe.collision_policy, "suffix", "safe collision");
assertEqual(safe.confirm_replace_final, false, "safe replace confirmation");
assertEqual(safe.confirm_source_overwrite, false, "safe source overwrite confirmation");
if ("original_policy" in safe) throw new Error("safe request should not send original_policy");
if ("confirm_original_policy" in safe) throw new Error("safe request should not send confirm_original_policy");
console.log(JSON.stringify({ replacement, safe }));
""".replace("__QUEUE_RERUN_REQUEST_PATH__", json.dumps(str(QUEUE_RERUN_REQUEST_JS)))

        result = subprocess.run(
            [node, "-e", script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["replacement"]["destination_mode"], "auto_replace_clean_else_pending_review")
        self.assertNotIn("original_policy", payload["replacement"])
        self.assertEqual(payload["safe"]["destination_mode"], "review_workspace")
        self.assertNotIn("original_policy", payload["safe"])


if __name__ == "__main__":
    unittest.main()
