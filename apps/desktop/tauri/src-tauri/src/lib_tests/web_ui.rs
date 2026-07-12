#![allow(unused_variables)]

use super::*;

#[test]
fn validate_backend_web_ui_requires_index_and_real_media_assets_without_leaking_token() {
    let index = r#"<!doctype html>
<script type="application/json" id="media-pipeline-bootstrap">{"apiBase":"","token":"","appVersion":"2026.06.04.001","shellSurface":"tauri","tokenSource":"tauri-initialization-script"}</script>
<section data-page-panel="home">
  <strong id="cross-page-real-media-status">Not loaded</strong>
  <tbody id="cross-page-real-media-rows"></tbody>
  <strong id="sample-validation-status">Not loaded</strong>
  <strong id="sample-validation-cutover-status">Not loaded</strong>
  <tbody id="sample-validation-cutover-rows"></tbody>
  <strong id="sample-validation-sample-set-status">Not loaded</strong>
  <tbody id="sample-validation-sample-set-rows"></tbody>
  <select id="sample-validation-category"></select>
  <button id="sample-validation-use-sample-set-category-button"></button>
  <strong id="home-external-dependencies-status">Not loaded</strong>
  <pre id="home-external-dependencies-summary"></pre>
</section>
<section data-page-panel="settings">
  <strong id="settings-handbrake-preview-status">Predicted pending cutover</strong>
  <strong id="settings-handbrake-decision">NOT EVALUATED</strong>
  <strong id="settings-handbrake-active-preset">Saved settings</strong>
  <dd id="settings-handbrake-output-video"></dd>
  <dd id="settings-handbrake-output-guards"></dd>
  <pre id="settings-handbrake-preview-detail"></pre>
  <strong id="settings-backend-media-policy-status">Not loaded</strong>
  <tbody id="settings-backend-media-policy-rows"></tbody>
  <tbody id="settings-policy-delta-rows"></tbody>
  <tbody id="settings-effective-policy-rows"></tbody>
  <pre id="settings-effective-policy-detail"></pre>
  <tbody id="settings-backend-result-rows"></tbody>
  <pre id="settings-backend-result-detail"></pre>
  <select id="settings-builder-routing-profile"></select>
  <select id="settings-builder-size-guard"></select>
  <select id="settings-builder-output-container"></select>
</section>
<section data-page-panel="launch">
  <tbody id="launch-settings-risk-rows"></tbody>
  <pre id="launch-pilot-readiness-summary"></pre>
  <tbody id="launch-pilot-readiness-rows"></tbody>
</section>
<section data-page-panel="diagnostics">
  <strong id="diagnostics-state-triage-status">Not loaded</strong>
  <pre id="diagnostics-close-readiness"></pre>
  <pre id="backend-lifecycle-summary"></pre>
  <button id="backend-shutdown-button"></button>
</section>"#;
    let app_script = r#"async function refreshAllNow() {
  await apiGet("/api/sample-validation?limit=10");
  const crossPageContext = {
    settings: values.settings || window.mediaPipelineSettingsView.getLastSettings(),
  };
  renderCrossPageContext(crossPageContext);
  window.mediaPipelineFloatingPipelineLog?.renderFloatingPipelineLog?.(values.diagnostics);
}
function renderBackendLifecycle() {}
function renderExternalDependencyDigest() {}
function externalDependencyRows() {}
async function requestBackendShutdown() {
  await apiPost("/api/backend/shutdown", {});
  return "Backend shutdown is disabled in WebView until close-readiness reports safe";
}
window.mediaPipelineFloatingPipelineLog?.initFloatingPipelineLogEvents?.();"#;
    let floating_pipeline_log_script = r#"const REFRESH_INTERVAL_MS = 2000;
function renderFloatingPipelineLog() {}
async function refreshFloatingPipelineLog() {
  await window.mediaPipelineApi.apiGet("/api/diagnostics");
}
function initFloatingPipelineLogEvents() {
  return "pipeline-log-window-button";
}
window.mediaPipelineFloatingPipelineLog = { initFloatingPipelineLogEvents, renderFloatingPipelineLog, refreshFloatingPipelineLog };"#;
    let pipeline_log_bridge_script = r#"function showDiagnosticsLogsFallback() {
  return "diagnostics-pipeline-log-status";
}
function tauriInvoke() {
  return window.__TAURI__.core.invoke;
}
async function openPipelineLogWindow() {
  await tauriInvoke()("open_pipeline_log_window");
}
window.mediaPipelinePipelineLogWindowBridge = { openPipelineLogWindow, showDiagnosticsLogsFallback };"#;
    let pipeline_log_window = r#"<!doctype html>
<strong id="pipeline-log-window-status">Loading</strong>
<input id="pipeline-log-window-follow" type="checkbox">
<button id="pipeline-log-window-refresh-button"></button>
<script src="/assets/apiClient.js"></script>
<script src="/assets/pipelineLogWindow.js"></script>"#;
    let pipeline_log_window_script = r#"const REFRESH_INTERVAL_MS = 2000;
function renderPipelineLogWindow() {}
async function refreshPipelineLogWindow() {
  await window.mediaPipelineApi.apiGet("/api/diagnostics");
}
window.mediaPipelinePipelineLogWindow = { renderPipelineLogWindow, refreshPipelineLogWindow };"#;
    let cross_page_script = r#"function createCrossPageConflictModule() {}
function createCrossPageSampleModule() {}
function createCrossPageSettingsModule() {}
function createCrossPageSampleValidationModule() {}"#;
    let cross_page_conflict_script = r#"function createCrossPageConflictModule() {}
function crossPageConflictRows() {}
function renderCrossPageConflictBoard() {}
window.__crossPageConflictModule = { createCrossPageConflictModule };"#;
    let cross_page_sample_script = r#"function createCrossPageSampleModule() {}
function crossPageSampleRows() {}
function crossPageValidationTemplateLines() {}
window.__crossPageSampleModule = { createCrossPageSampleModule };"#;
    let cross_page_settings_script = r#"function createCrossPageSettingsModule() {}
function crossPageSettingsPolicyEvidence() {
  return "Backend media-policy readiness; media readiness=Ready";
}
window.__crossPageSettingsModule = { createCrossPageSettingsModule };"#;
    let cross_page_sample_validation_worksheet_script = r#"function createCrossPageSvWorksheetModule() {}
function crossPageRealMediaWorksheetRows() {}
function sampleValidationPolicyAlignmentSummaryLines() {}
function renderSampleValidationSampleSetGuide() { return "Recommended real-media sample set:"; }
function useSelectedSampleSetCategory() {}
function renderCrossPageRealMediaWorksheet() {
  const summary = "Backend media-policy readiness; media readiness=Ready";
  return "this worksheet does not save, accept, repair, rerun, drain, delete, publish, rename, rewrite manifests, or touch media files";
}
window.__crossPageSvWorksheetModule = { createCrossPageSvWorksheetModule };"#;
    let cross_page_sample_validation_runbook_script = r#"function createCrossPageSvRunbookModule() {}
function renderSampleValidationCutoverGate() { return "WebView cutover gate:"; }
function renderSampleValidationRunbook() {}
function renderSampleValidationExecutionChecklist() {}
window.__crossPageSvRunbookModule = { createCrossPageSvRunbookModule };"#;
    let cross_page_sample_validation_records_script = r#"function createCrossPageSvRecordsModule() {}
function sampleValidationRecordComparisonRowsForPaths() {}
function sampleValidationCompletedPacketRows() {}
function renderSampleValidationAcceptanceGate() {
  return "Decision rule: accepted sample evidence should not be appended";
}
function renderSampleValidationRecordReview() {}
window.__crossPageSvRecordsModule = { createCrossPageSvRecordsModule };"#;
    let cross_page_sample_validation_script = r#"function createCrossPageSvWorksheetModule() {}
function createCrossPageSvRunbookModule() {}
function createCrossPageSvRecordsModule() {}
function buildSampleValidationRequest() { return "/api/sample-validation/append"; }"#;
    let diagnostics_active_jobs_script = r#"function createDiagnosticsActiveJobsModule() {}
function diagnosticsActiveJobRealMediaTraceLines() {}
window.__diagnosticsActiveJobsModule = { createDiagnosticsActiveJobsModule };"#;
    let diagnostics_log_script = r#"function createDiagnosticsLogModule() {
  return "Log triage guidance:";
}
function diagnosticsLogRows() {}
window.__diagnosticsLogModule = { createDiagnosticsLogModule };"#;
    let diagnostics_investigation_script = r#"function createDiagnosticsInvestigationModule() {
  return "Owning-page evidence handoff:";
}
function diagnosticsInvestigationActions() {}
window.__diagnosticsInvestigationModule = { createDiagnosticsInvestigationModule };"#;
    let diagnostics_matrix_console_script = r#"function createDiagnosticsMatrixConsoleModule() {}
function requestTdarrMatrixEvidenceOpen() { return "/api/diagnostics/tdarr-matrix/evidence/open"; }
window.__diagnosticsMatrixConsoleModule = { createDiagnosticsMatrixConsoleModule };"#;
    let diagnostics_triage_script = r#"function createDiagnosticsTriageModule() {}
window.__diagnosticsTriageModule = { createDiagnosticsTriageModule };"#;
    let diagnostics_first_response_script = r#"function createDiagnosticsFirstResponseModule() {
  return "External dependency readiness Resolve blocked Settings OCR or Maintenance toolchain evidence";
}
window.__diagnosticsFirstResponseModule = { createDiagnosticsFirstResponseModule };"#;
    let diagnostics_script = r#"function diagnosticsFirstResponseRows() {
const diagnosticsActiveJobsModule = window.__diagnosticsActiveJobsModule || {};
const diagnosticsLogModule = window.__diagnosticsLogModule || {};
const diagnosticsInvestigationModule = window.__diagnosticsInvestigationModule || {};
const diagnosticsMatrixConsoleModule = window.__diagnosticsMatrixConsoleModule || {};
const diagnosticsFirstResponseModule = window.__diagnosticsFirstResponseModule || {};
  return "External dependency readiness Resolve blocked Settings OCR or Maintenance toolchain evidence";
}"#;
    let settings_raw_triage_script = r#"function createSettingsRawTriageModule() {
  return "Settings raw-key action plan:";
}
function settingsRawTriageRows() {}
function settingsRawActionPlanRows() {}
window.__settingsRawTriageModule = { createSettingsRawTriageModule };"#;
    let settings_safety_locks_script = r#"function createSettingsSafetyLocksModule() {
  return "Settings safety lock review:";
}
function settingsSafetyLockRows() {}
window.__settingsSafetyLocksModule = { createSettingsSafetyLocksModule };"#;
    let settings_backend_result_script = r#"function createSettingsBackendResultModule() {}
function settingsBackendResultRows() {
  return "Save Settings will review the current values before writing.";
}
function settingsBackendResultDetailLines() {
  return "Patch identity:";
}
function renderSettingsBackendResultFromEntries() {
  return "Save Settings is the persistence command";
}
window.__settingsBackendResultModule = { createSettingsBackendResultModule };"#;
    let settings_final_library_promotion_script = r#"function createSettingsFinalLibraryPromotionModule() {}
window.__settingsFinalLibraryPromotionModule = { createSettingsFinalLibraryPromotionModule };"#;
    let settings_patch_overview_script = r#"function createSettingsPatchOverviewModule() {}
function renderHandbrakePreviewSummary(settings) {
  return "Source-specific route previews are not exposed in Settings";
}
window.__settingsPatchOverviewModule = { createSettingsPatchOverviewModule };"#;
    let settings_patch_interactions_script = r#"function createSettingsPatchInteractionsModule() {}
function initSettingsViewEvents() {}
window.__settingsPatchInteractionsModule = { createSettingsPatchInteractionsModule };"#;
    let settings_patch_readiness_script = r#"function createSettingsPatchReadinessModule() {}
function settingsPatchSaveReadinessIssues() {}
window.__settingsPatchReadinessModule = { createSettingsPatchReadinessModule };"#;
    let settings_patch_review_script = r#"function createSettingsPatchReviewModule() {}
const settingsPatchReadinessModule = window.__settingsPatchReadinessModule || {};
function renderHandbrakePreviewSummary(settings) {
  return "Source-specific route previews are not exposed in Settings";
}
function collectSettingsBuilderPatch() {
  return {
    RoutingProfile: settingsBuilderInputValue("settings-builder-routing-profile"),
  };
}
function bindSettingsClick() {}"#;
    let settings_metadata_script = r#"const videoDetailSettingsBuilderFields = [
  ["OutputContainer", "settings-builder-output-container", "select"],
];"#;
    let settings_video_builder_script = r#"function collectVideoDetailSettingsBuilderPatch() {
  patch[key] = readVideoDetailBuilderValue(id, kind, field?.label || key);
}
function syncVideoDetailSettingsBuilderFromConfig() {
  setVideoDetailBuilderControl("settings-builder-output-container", "OutputContainer", "select", "mkv");
}"#;
    let settings_script = r#"const settingsRawTriageModule = window.__settingsRawTriageModule || {};
const settingsSafetyLocksModule = window.__settingsSafetyLocksModule || {};
const settingsBackendResultModule = window.__settingsBackendResultModule || {};
const settingsFinalLibraryPromotionModule = window.__settingsFinalLibraryPromotionModule || {};
const settingsPatchOverviewModule = window.__settingsPatchOverviewModule || {};
const settingsPatchInteractionsModule = window.__settingsPatchInteractionsModule || {};
const settingsPatchReadinessModule = window.__settingsPatchReadinessModule || {};
const settingsPolicyImpactModule = window.__settingsPolicyImpactModule || {};
delete window.__settingsPolicyImpactModule;
"#;
    let settings_media_projection_script = r#"function createSettingsMediaProjection() {}
window.__settingsMediaProjectionModule = createSettingsMediaProjection;"#;
    let settings_effective_policy_view_script = r#"function createSettingsEffectivePolicyView() {}
window.__settingsEffectivePolicyViewModule = createSettingsEffectivePolicyView;"#;
    let settings_policy_impact_script = r#"const createSettingsMediaProjection = window.__settingsMediaProjectionModule;
const createSettingsEffectivePolicyView = window.__settingsEffectivePolicyViewModule;
delete window.__settingsMediaProjectionModule;
delete window.__settingsEffectivePolicyViewModule;
function createSettingsPolicyImpactModule() {}
function settingsBackendMediaPolicyReadiness() {}
function renderSettingsBackendMediaPolicyReadiness() {
  return "Backend media-policy readiness: this table cannot stage settings, save config, launch work, run FFmpeg, publish files, or touch source media";
}
function settingsPolicyDeltaRows() {
  return "Save-candidate media-policy delta:";
}
function settingsEffectivePolicyRows() {
  return "Effective policy trust summary: Launch-active policy is the saved backend config";
}
window.__settingsPolicyImpactModule = { createSettingsPolicyImpactModule };"#;
    let settings_overview_script = r#"function settingsMediaPolicyReadinessLine(settings) {
  return settings.media_policy_readiness;
}"#;
    let launch_risk_settings_access_script = r#"function createLaunchRiskSettingsAccessModule() {}
window.__launchRiskSettingsAccessModule = { createLaunchRiskSettingsAccessModule };"#;
    let launch_risk_media_policy_values_script = r#"function createLaunchRiskMediaPolicyValuesModule() {}
window.__launchRiskMediaPolicyValuesModule = { createLaunchRiskMediaPolicyValuesModule };"#;
    let launch_risk_rows_script = r#"function createLaunchRiskRowsModule(settings) {
  const mediaReadiness = settings.media_policy_readiness;
  return "Backend media-policy readiness Resolve blocked saved media-policy rows before launching unattended work.";
}
window.__launchRiskRowsModule = { createLaunchRiskRowsModule };"#;
    let launch_risk_policy_patch_script = r#"function createLaunchRiskPolicyPatchModule() {}
window.__launchRiskPolicyPatchModule = { createLaunchRiskPolicyPatchModule };"#;
    let launch_risk_policy_boundary_script = r#"function createLaunchRiskPolicyBoundaryModule() {
  return "Launch active media-policy boundary:";
}
window.__launchRiskPolicyBoundaryModule = { createLaunchRiskPolicyBoundaryModule };"#;
    let launch_risk_script = r#"function createLaunchRiskModule() {
  return "Saved settings vs launch intent checklist:";
}
window.__launchViewRiskModule = { createLaunchRiskModule };"#;
    let launch_scope_script = r#"function createLaunchScopeModule() {
  return "Launch scope reconciliation: Launch start decision summary:";
}
window.__launchViewScopeModule = { createLaunchScopeModule };"#;
    let launch_realmedia_script = r#"function createLaunchRealMediaModule() {
  return "Launch real-media sample proof handoff: Launch sample execution checklist:";
}
window.__launchViewRealMediaModule = { createLaunchRealMediaModule };"#;
    let launch_pilot_readiness_script = r#"function createLaunchPilotReadinessModule() {
  return "Launch pilot run readiness:";
}
window.__launchPilotReadinessModule = { createLaunchPilotReadinessModule };
function launchPilotRunReadinessRows() {
  return "Launch pilot run readiness:";
}
function renderLaunchPilotRunReadiness() {
  return "Launch pilot run readiness:";
}"#;
    let launch_preflight_script = r#"function createLaunchPreflightModule() {
  const launchPilotReadinessModule = window.__launchPilotReadinessModule || {};
  delete window.__launchPilotReadinessModule;
  return launchPilotReadinessModule.createLaunchPilotReadinessModule();
}
window.__launchViewPreflightModule = { createLaunchPreflightModule };"#;
    let launch_controller_state_script = r#"function createLaunchControllerStateModule() {}
window.__launchControllerStateModule = { createLaunchControllerStateModule };"#;
    let launch_status_render_script = r#"function createLaunchStatusRenderModule() {}
window.__launchStatusRenderModule = { createLaunchStatusRenderModule };"#;
    let launch_start_request_script = r#"function createLaunchStartRequestModule() {}
window.__launchStartRequestModule = { createLaunchStartRequestModule };"#;
    let launch_scope_controls_script = r#"function createLaunchScopeControlsModule() {}
window.__launchScopeControlsModule = { createLaunchScopeControlsModule };"#;
    let launch_command_buttons_script = r#"function createLaunchCommandButtonsModule() {}
window.__launchCommandButtonsModule = { createLaunchCommandButtonsModule };"#;
    let launch_script = r#"const launchPreflightModule = window.__launchViewPreflightModule || {};
delete window.__launchViewPreflightModule;
const launchControllerStateModule = window.__launchControllerStateModule || {};
delete window.__launchControllerStateModule;
const launchStatusRenderModule = window.__launchStatusRenderModule || {};
delete window.__launchStatusRenderModule;
const launchStartRequestModule = window.__launchStartRequestModule || {};
delete window.__launchStartRequestModule;
const launchScopeControlsModule = window.__launchScopeControlsModule || {};
delete window.__launchScopeControlsModule;
const launchCommandButtonsModule = window.__launchCommandButtonsModule || {};
delete window.__launchCommandButtonsModule;"#;
    let diagnostics_state_script = r#"function renderDiagnosticsStateTriage() { return "Backend read order:"; }
function renderDiagnosticsStateTriageRows() {}
const diagnosticsStateTriageActionsId = "diagnostics-state-triage-actions";"#;
    let pending_publish_recovery_script = r#"function createPendingPublishRecoveryModule() {
  return "/api/pending-publish/recovery-plan";
}
function renderPendingRecoveryPlanResult() {}
window.__pendingPublishRecoveryModule = { createPendingPublishRecoveryModule };"#;
    let pending_publish_diagnostics_script = r#"function createPendingPublishDiagnosticsModule() {
  return "/api/pending-publish/open The Pending page never sends arbitrary filesystem paths.";
}
function requestPendingPublishOpen() {}
window.__pendingPublishDiagnosticsModule = { createPendingPublishDiagnosticsModule };"#;
    let pending_publish_drain_script = r#"function createPendingPublishDrainModule() {
  return "Pending drain evidence board:";
}
function renderPendingDrainEvidence() {}
function renderPendingDrainCorrelation() {}
window.__pendingPublishDrainModule = { createPendingPublishDrainModule };"#;
    let pending_publish_post_drain_trust_script = r#"function createPendingPostDrainTrustModule() {
  return "Pending Publish post-drain trust review:";
}
function renderPendingPostDrainTrust() {}
window.__pendingPostDrainTrustModule = { createPendingPostDrainTrustModule };"#;
    let pending_publish_confidence_script = r#"function createPendingPublishConfidenceModule() {
  const pendingPostDrainTrustModule = window.__pendingPostDrainTrustModule || {};
  delete window.__pendingPostDrainTrustModule;
  pendingPostDrainTrustModule.createPendingPostDrainTrustModule();
  return "Pending Publish drain action confidence:";
}
function pendingDrainGuardState() {}
function renderPendingDrainDecisionChecklist() {}
window.__pendingPublishConfidenceModule = { createPendingPublishConfidenceModule };"#;
    let pending_publish_script = r#"let pendingSampleValidationHandoffLines = function () {};
const pendingRecoveryModule = window.__pendingPublishRecoveryModule || {};
const pendingDiagnosticsModule = window.__pendingPublishDiagnosticsModule || {};
const pendingDrainModule = window.__pendingPublishDrainModule || {};
const pendingConfidenceModule = window.__pendingPublishConfidenceModule || {};"#;
    let app_dashboard_script = include_str!("../../../../webview/static/assets/app/dashboard.js");
    let app_refresh_coordinator_script =
        include_str!("../../../../webview/static/assets/app/refreshCoordinator.js");
    let app_lifecycle_orchestration_script =
        include_str!("../../../../webview/static/assets/app/lifecycleOrchestration.js");
    let settings_view_builder_script =
        include_str!("../../../../webview/static/assets/settings/view/builder.js");
    let settings_view_impact_script =
        include_str!("../../../../webview/static/assets/settings/view/impact.js");
    let settings_view_review_script =
        include_str!("../../../../webview/static/assets/settings/view/review.js");
    let settings_view_commands_script =
        include_str!("../../../../webview/static/assets/settings/view/commands.js");
    let settings_view_lifecycle_script =
        include_str!("../../../../webview/static/assets/settings/view/lifecycle.js");
    let settings_view_facade_script =
        include_str!("../../../../webview/static/assets/settings/view/facade.js");
    let settings_view_parent_script =
        include_str!("../../../../webview/static/assets/settingsView.js");
    let launch_command_orchestration_script =
        include_str!("../../../../webview/static/assets/launch/commandOrchestration.js");
    let launch_rerun_evidence_script =
        include_str!("../../../../webview/static/assets/launch/rerunEvidence.js");
    let launch_rerun_presentation_script =
        include_str!("../../../../webview/static/assets/launch/rerunPresentation.js");
    let launch_rerun_orchestration_script =
        include_str!("../../../../webview/static/assets/launch/rerunOrchestration.js");
    let launch_rerun_facade_script =
        include_str!("../../../../webview/static/assets/launch/rerunFacade.js");
    let launch_parent_script = include_str!("../../../../webview/static/assets/launchView.js");
    let pending_action_center_script =
        include_str!("../../../../webview/static/assets/pendingPublish/actionCenter.js");
    let pending_rendering_script =
        include_str!("../../../../webview/static/assets/pendingPublish/rendering.js");
    let pending_table_support_script =
        include_str!("../../../../webview/static/assets/pendingPublish/tableSupport.js");
    let pending_default_adapters_script =
        include_str!("../../../../webview/static/assets/pendingPublish/defaultAdapters.js");
    let web_shell_asset_bundle = concat!(
        include_str!("../../../../webview/static/assets/app.js"),
        include_str!("../../../../webview/static/assets/app/dashboard.js"),
        include_str!("../../../../webview/static/assets/app/refreshCoordinator.js"),
        include_str!("../../../../webview/static/assets/app/lifecycleOrchestration.js"),
        include_str!("../../../../webview/static/assets/floatingPipelineLog.js"),
        include_str!("../../../../webview/static/assets/pipelineLogWindowBridge.js"),
    );
    let settings_asset_bundle = concat!(
        include_str!("../../../../webview/static/assets/settingsView.rawTriage.js"),
        include_str!("../../../../webview/static/assets/settingsView.safetyLocks.js"),
        include_str!("../../../../webview/static/assets/settings/backendResult.js"),
        include_str!("../../../../webview/static/assets/settings/finalLibraryPromotion.js"),
        include_str!("../../../../webview/static/assets/settings/patchOverview.js"),
        include_str!("../../../../webview/static/assets/settings/patchInteractions.js"),
        include_str!("../../../../webview/static/assets/settings/patchReadiness.js"),
        include_str!("../../../../webview/static/assets/settings/patchReview.js"),
        include_str!("../../../../webview/static/assets/settingsMetadata.js"),
        include_str!("../../../../webview/static/assets/settingsView.builders.video.js"),
        include_str!("../../../../webview/static/assets/settings/view/builder.js"),
        include_str!("../../../../webview/static/assets/settings/view/impact.js"),
        include_str!("../../../../webview/static/assets/settings/view/review.js"),
        include_str!("../../../../webview/static/assets/settings/view/commands.js"),
        include_str!("../../../../webview/static/assets/settings/view/lifecycle.js"),
        include_str!("../../../../webview/static/assets/settings/view/facade.js"),
        include_str!("../../../../webview/static/assets/settingsView.js"),
        include_str!("../../../../webview/static/assets/settings/policyImpact/mediaProjection.js"),
        include_str!(
            "../../../../webview/static/assets/settings/policyImpact/effectivePolicyView.js"
        ),
        include_str!("../../../../webview/static/assets/settings/policyImpact.js"),
        include_str!("../../../../webview/static/assets/settingsOverview.js"),
    );
    let responses = [
        index,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        pipeline_log_window,
        pipeline_log_window_script,
        cross_page_script,
        cross_page_conflict_script,
        cross_page_sample_script,
        cross_page_settings_script,
        cross_page_sample_validation_worksheet_script,
        cross_page_sample_validation_runbook_script,
        cross_page_sample_validation_records_script,
        cross_page_sample_validation_script,
        diagnostics_active_jobs_script,
        diagnostics_log_script,
        diagnostics_investigation_script,
        diagnostics_matrix_console_script,
        diagnostics_triage_script,
        diagnostics_first_response_script,
        include_str!("../../../../webview/static/assets/diagnosticsView.js"),
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        settings_asset_bundle,
        launch_risk_settings_access_script,
        launch_risk_media_policy_values_script,
        launch_risk_rows_script,
        launch_risk_policy_patch_script,
        launch_risk_policy_boundary_script,
        launch_risk_script,
        launch_scope_script,
        launch_realmedia_script,
        launch_pilot_readiness_script,
        launch_preflight_script,
        launch_controller_state_script,
        launch_status_render_script,
        launch_start_request_script,
        launch_scope_controls_script,
        launch_command_buttons_script,
        launch_command_orchestration_script,
        launch_rerun_evidence_script,
        launch_rerun_presentation_script,
        launch_rerun_orchestration_script,
        launch_rerun_facade_script,
        launch_parent_script,
        diagnostics_state_script,
        pending_publish_recovery_script,
        pending_publish_diagnostics_script,
        pending_publish_drain_script,
        pending_publish_post_drain_trust_script,
        pending_publish_confidence_script,
        pending_publish_script,
        pending_action_center_script,
        pending_rendering_script,
        pending_table_support_script,
        pending_default_adapters_script,
    ]
    .map(|body| format!("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n{body}"))
    .to_vec();
    let (url, rx) = serve_sequence(responses);

    validate_backend_web_ui(&url, "secret-token").expect("web UI validation should pass");
    let expected_request_paths = [
        "/",
        "/assets/app.js",
        "/assets/app/dashboard.js",
        "/assets/app/refreshCoordinator.js",
        "/assets/app/lifecycleOrchestration.js",
        "/assets/floatingPipelineLog.js",
        "/assets/pipelineLogWindowBridge.js",
        "/assets/pipelineLogWindow.html",
        "/assets/pipelineLogWindow.js",
        "/assets/crossPageContextView.js",
        "/assets/crossPageContextView.conflict.js",
        "/assets/crossPageContextView.sample.js",
        "/assets/crossPageContextView.settings.js",
        "/assets/crossPageContextView.sampleValidation.worksheet.js",
        "/assets/crossPageContextView.sampleValidation.runbook.js",
        "/assets/crossPageContextView.sampleValidation.records.js",
        "/assets/crossPageContextView.sampleValidation.js",
        "/assets/diagnosticsView.activejobs.js",
        "/assets/diagnosticsView.log.js",
        "/assets/diagnosticsView.investigation.js",
        "/assets/diagnostics/matrixConsole.js",
        "/assets/diagnostics/triage.js",
        "/assets/diagnostics/firstResponse.js",
        "/assets/diagnosticsView.js",
        "/assets/settingsView.rawTriage.js",
        "/assets/settingsView.safetyLocks.js",
        "/assets/settings/backendResult.js",
        "/assets/settings/finalLibraryPromotion.js",
        "/assets/settings/patchOverview.js",
        "/assets/settings/patchInteractions.js",
        "/assets/settings/patchReadiness.js",
        "/assets/settings/patchReview.js",
        "/assets/settingsMetadata.js",
        "/assets/settingsView.builders.video.js",
        "/assets/settings/view/builder.js",
        "/assets/settings/view/impact.js",
        "/assets/settings/view/review.js",
        "/assets/settings/view/commands.js",
        "/assets/settings/view/lifecycle.js",
        "/assets/settings/view/facade.js",
        "/assets/settingsView.js",
        "/assets/settings/policyImpact/mediaProjection.js",
        "/assets/settings/policyImpact/effectivePolicyView.js",
        "/assets/settings/policyImpact.js",
        "/assets/settingsOverview.js",
        "/assets/launch/risk/settingsAccess.js",
        "/assets/launch/risk/mediaPolicyValues.js",
        "/assets/launch/risk/riskRows.js",
        "/assets/launch/risk/policyPatch.js",
        "/assets/launch/risk/policyBoundary.js",
        "/assets/launchView.risk.js",
        "/assets/launchView.scope.js",
        "/assets/launchView.realmedia.js",
        "/assets/launch/preflight/pilotReadiness.js",
        "/assets/launchView.preflight.js",
        "/assets/launch/controllerState.js",
        "/assets/launch/statusRender.js",
        "/assets/launch/startRequest.js",
        "/assets/launch/scopeControls.js",
        "/assets/launch/commandButtons.js",
        "/assets/launch/commandOrchestration.js",
        "/assets/launch/rerunEvidence.js",
        "/assets/launch/rerunPresentation.js",
        "/assets/launch/rerunOrchestration.js",
        "/assets/launch/rerunFacade.js",
        "/assets/launchView.js",
        "/assets/diagnosticsStateSummaryView.js",
        "/assets/pendingPublishView.recovery.js",
        "/assets/pendingPublishView.diagnostics.js",
        "/assets/pendingPublishView.drain.js",
        "/assets/pendingPublish/confidence/postDrainTrust.js",
        "/assets/pendingPublishView.confidence.js",
        "/assets/pendingPublishView.js",
        "/assets/pendingPublish/actionCenter.js",
        "/assets/pendingPublish/rendering.js",
        "/assets/pendingPublish/tableSupport.js",
        "/assets/pendingPublish/defaultAdapters.js",
    ];
    let requests = (0..expected_request_paths.len())
        .map(|_| {
            rx.recv_timeout(Duration::from_secs(2))
                .expect("request received")
        })
        .collect::<Vec<String>>();

    for (request, path) in requests.iter().zip(expected_request_paths) {
        assert!(request.starts_with(&format!("GET {path} HTTP/1.1\r\n")));
    }
    assert!(requests
        .iter()
        .all(|request| request.contains("Authorization: Bearer secret-token\r\n")));
}

#[test]
fn validate_backend_web_ui_reports_missing_fragments_without_token() {
    let index = r#"<!doctype html>
<script type="application/json" id="media-pipeline-bootstrap">{"apiBase":"","token":"","appVersion":"2026.06.04.001","shellSurface":"tauri","tokenSource":"tauri-initialization-script"}</script>
<section data-page-panel="home">
  <strong id="cross-page-real-media-status">Not loaded</strong>
  <tbody id="cross-page-real-media-rows"></tbody>
  <strong id="sample-validation-status">Not loaded</strong>
  <strong id="sample-validation-cutover-status">Not loaded</strong>
  <tbody id="sample-validation-cutover-rows"></tbody>
  <strong id="sample-validation-sample-set-status">Not loaded</strong>
  <tbody id="sample-validation-sample-set-rows"></tbody>
  <select id="sample-validation-category"></select>
  <button id="sample-validation-use-sample-set-category-button"></button>
  <strong id="home-external-dependencies-status">Not loaded</strong>
  <pre id="home-external-dependencies-summary"></pre>
</section>
<section data-page-panel="settings">
  <strong id="settings-handbrake-preview-status">Predicted pending cutover</strong>
  <strong id="settings-handbrake-decision">NOT EVALUATED</strong>
  <strong id="settings-handbrake-active-preset">Saved settings</strong>
  <dd id="settings-handbrake-output-video"></dd>
  <dd id="settings-handbrake-output-guards"></dd>
  <pre id="settings-handbrake-preview-detail"></pre>
  <strong id="settings-backend-media-policy-status">Not loaded</strong>
  <tbody id="settings-backend-media-policy-rows"></tbody>
  <tbody id="settings-policy-delta-rows"></tbody>
  <tbody id="settings-effective-policy-rows"></tbody>
  <pre id="settings-effective-policy-detail"></pre>
  <tbody id="settings-backend-result-rows"></tbody>
  <pre id="settings-backend-result-detail"></pre>
  <select id="settings-builder-routing-profile"></select>
  <select id="settings-builder-size-guard"></select>
  <select id="settings-builder-output-container"></select>
</section>
<section data-page-panel="launch">
  <tbody id="launch-settings-risk-rows"></tbody>
  <pre id="launch-pilot-readiness-summary"></pre>
  <tbody id="launch-pilot-readiness-rows"></tbody>
</section>
<section data-page-panel="diagnostics">
  <strong id="diagnostics-state-triage-status">Not loaded</strong>
  <pre id="diagnostics-close-readiness"></pre>
  <pre id="backend-lifecycle-summary"></pre>
  <button id="backend-shutdown-button"></button>
</section>"#;
    let app_script = r#"async function refreshAllNow() {
  await apiGet("/api/sample-validation?limit=10");
  const crossPageContext = {
    settings: values.settings || window.mediaPipelineSettingsView.getLastSettings(),
  };
  renderCrossPageContext(crossPageContext);
  window.mediaPipelineFloatingPipelineLog?.renderFloatingPipelineLog?.(values.diagnostics);
}
function renderBackendLifecycle() {}
function renderExternalDependencyDigest() {}
function externalDependencyRows() {}
async function requestBackendShutdown() {
  await apiPost("/api/backend/shutdown", {});
  return "Backend shutdown is disabled in WebView until close-readiness reports safe";
}
window.mediaPipelineFloatingPipelineLog?.initFloatingPipelineLogEvents?.();"#;
    let floating_pipeline_log_script = r#"const REFRESH_INTERVAL_MS = 2000;
function renderFloatingPipelineLog() {}
async function refreshFloatingPipelineLog() {
  await window.mediaPipelineApi.apiGet("/api/diagnostics");
}
function initFloatingPipelineLogEvents() {
  return "pipeline-log-window-button";
}
window.mediaPipelineFloatingPipelineLog = { initFloatingPipelineLogEvents, renderFloatingPipelineLog, refreshFloatingPipelineLog };"#;
    let pipeline_log_bridge_script = r#"function showDiagnosticsLogsFallback() {
  return "diagnostics-pipeline-log-status";
}
function tauriInvoke() {
  return window.__TAURI__.core.invoke;
}
async function openPipelineLogWindow() {
  await tauriInvoke()("open_pipeline_log_window");
}"#;
    let pipeline_log_window = r#"<strong id="pipeline-log-window-status">Loading</strong>
<input id="pipeline-log-window-follow" type="checkbox">
<button id="pipeline-log-window-refresh-button"></button>
<script src="/assets/apiClient.js"></script>
<script src="/assets/pipelineLogWindow.js"></script>"#;
    let pipeline_log_window_script = r#"const REFRESH_INTERVAL_MS = 2000;
function renderPipelineLogWindow() {}
window.mediaPipelinePipelineLogWindow = {};
const route = "/api/diagnostics";"#;
    let cross_page_script = r#"function createCrossPageConflictModule() {}
function createCrossPageSampleModule() {}
function createCrossPageSettingsModule() {}
function createCrossPageSampleValidationModule() {}"#;
    let cross_page_conflict_script = r#"function createCrossPageConflictModule() {}
function crossPageConflictRows() {}
function renderCrossPageConflictBoard() {}
window.__crossPageConflictModule = { createCrossPageConflictModule };"#;
    let cross_page_sample_script = r#"function createCrossPageSampleModule() {}
function crossPageSampleRows() {}
function crossPageValidationTemplateLines() {}
window.__crossPageSampleModule = { createCrossPageSampleModule };"#;
    let cross_page_settings_script = r#"function createCrossPageSettingsModule() {}
function crossPageSettingsPolicyEvidence() {
  return "Backend media-policy readiness; media readiness=Ready";
}
window.__crossPageSettingsModule = { createCrossPageSettingsModule };"#;
    let cross_page_sample_validation_script = "function renderCrossPageContext() {}";
    let web_shell_asset_bundle = concat!(
        include_str!("../../../../webview/static/assets/app.js"),
        include_str!("../../../../webview/static/assets/app/dashboard.js"),
        include_str!("../../../../webview/static/assets/app/refreshCoordinator.js"),
        include_str!("../../../../webview/static/assets/app/lifecycleOrchestration.js"),
        include_str!("../../../../webview/static/assets/floatingPipelineLog.js"),
        include_str!("../../../../webview/static/assets/pipelineLogWindowBridge.js"),
    );
    let responses = [
        index,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        web_shell_asset_bundle,
        pipeline_log_window,
        pipeline_log_window_script,
        cross_page_script,
        cross_page_conflict_script,
        cross_page_sample_script,
        cross_page_settings_script,
        cross_page_sample_validation_script,
    ]
    .map(|body| format!("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n{body}"))
    .to_vec();
    let (url, _rx) = serve_sequence(responses);

    let error = validate_backend_web_ui(&url, "secret-token")
        .expect_err("missing worksheet helper should fail")
        .to_string();

    assert!(error.contains(
            "Backend WebView cross-page sample validation worksheet script is missing required fragment"
        ));
    assert!(error.contains("real-media worksheet renderer"));
    assert!(!error.contains("secret-token"));
}
