use crate::dialogs::shell_error;
use crate::http_helpers::request_backend_json;
use crate::ShellResult;

pub(super) fn validate_web_shell(backend_url: &str, token: &str) -> ShellResult<()> {
    let index = request_backend_json(backend_url, "GET", "/", token, "")?;
    for (label, fragment) in [
        ("bootstrap data block", "id=\"media-pipeline-bootstrap\""),
        ("home page", "data-page-panel=\"home\""),
        (
            "real-media worksheet status",
            "id=\"cross-page-real-media-status\"",
        ),
        (
            "real-media worksheet rows",
            "id=\"cross-page-real-media-rows\"",
        ),
        (
            "sample validation status",
            "id=\"sample-validation-status\"",
        ),
        (
            "sample validation cutover status",
            "id=\"sample-validation-cutover-status\"",
        ),
        (
            "sample validation cutover rows",
            "id=\"sample-validation-cutover-rows\"",
        ),
        (
            "sample validation sample set status",
            "id=\"sample-validation-sample-set-status\"",
        ),
        (
            "sample validation sample set rows",
            "id=\"sample-validation-sample-set-rows\"",
        ),
        (
            "sample validation pilot category select",
            "id=\"sample-validation-category\"",
        ),
        (
            "sample validation sample set category handoff",
            "id=\"sample-validation-use-sample-set-category-button\"",
        ),
        (
            "external dependency digest status",
            "id=\"home-external-dependencies-status\"",
        ),
        (
            "external dependency digest summary",
            "id=\"home-external-dependencies-summary\"",
        ),
        (
            "diagnostics state triage status",
            "id=\"diagnostics-state-triage-status\"",
        ),
        (
            "diagnostics close readiness",
            "id=\"diagnostics-close-readiness\"",
        ),
        (
            "backend lifecycle summary",
            "id=\"backend-lifecycle-summary\"",
        ),
        ("backend shutdown button", "id=\"backend-shutdown-button\""),
        ("settings page", "data-page-panel=\"settings\""),
        (
            "settings handbrake preview status",
            "id=\"settings-handbrake-preview-status\"",
        ),
        (
            "settings handbrake decision",
            "id=\"settings-handbrake-decision\"",
        ),
        (
            "settings handbrake active preset",
            "id=\"settings-handbrake-active-preset\"",
        ),
        (
            "settings handbrake output video",
            "id=\"settings-handbrake-output-video\"",
        ),
        (
            "settings handbrake output guards",
            "id=\"settings-handbrake-output-guards\"",
        ),
        (
            "settings handbrake preview detail",
            "id=\"settings-handbrake-preview-detail\"",
        ),
        (
            "settings backend media policy status",
            "id=\"settings-backend-media-policy-status\"",
        ),
        (
            "settings backend media policy rows",
            "id=\"settings-backend-media-policy-rows\"",
        ),
        (
            "settings backend preview/save result rows",
            "id=\"settings-backend-result-rows\"",
        ),
        (
            "settings backend preview/save result detail",
            "id=\"settings-backend-result-detail\"",
        ),
        (
            "settings staged media policy delta rows",
            "id=\"settings-policy-delta-rows\"",
        ),
        (
            "settings effective policy trust rows",
            "id=\"settings-effective-policy-rows\"",
        ),
        (
            "settings effective policy trust detail",
            "id=\"settings-effective-policy-detail\"",
        ),
        (
            "settings builder routing profile",
            "id=\"settings-builder-routing-profile\"",
        ),
        (
            "settings builder size guard",
            "id=\"settings-builder-size-guard\"",
        ),
        (
            "settings builder output container",
            "id=\"settings-builder-output-container\"",
        ),
        (
            "launch settings risk rows",
            "id=\"launch-settings-risk-rows\"",
        ),
        (
            "launch pilot readiness summary",
            "id=\"launch-pilot-readiness-summary\"",
        ),
        (
            "launch pilot readiness rows",
            "id=\"launch-pilot-readiness-rows\"",
        ),
        ("diagnostics page", "data-page-panel=\"diagnostics\""),
    ] {
        if !index.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView index is missing required fragment '{label}'."
            )));
        }
    }
    if index.contains("__MEDIA_PIPELINE_BOOTSTRAP__") {
        return Err(shell_error(
            "Backend WebView index still contains the raw bootstrap placeholder.",
        ));
    }
    if !token.is_empty() && index.contains(token) {
        return Err(shell_error(
            "Backend WebView index leaked the bearer token instead of relying on Tauri shell injection.",
        ));
    }

    let app_script = request_backend_json(backend_url, "GET", "/assets/app.js", token, "")?;
    for (label, fragment) in [
        (
            "backend lifecycle renderer",
            "function renderBackendLifecycle",
        ),
        (
            "backend lifecycle shutdown request",
            "async function requestBackendShutdown",
        ),
        ("backend lifecycle shutdown route", "/api/backend/shutdown"),
        (
            "backend lifecycle close-readiness guard",
            "Backend shutdown is disabled in WebView until close-readiness reports safe",
        ),
        (
            "external dependency digest renderer",
            "function renderExternalDependencyDigest",
        ),
        (
            "external dependency digest evidence",
            "function externalDependencyRows",
        ),
    ] {
        if !app_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView app script is missing required fragment '{label}'."
            )));
        }
    }

    let app_dashboard_script =
        request_backend_json(backend_url, "GET", "/assets/app/dashboard.js", token, "")?;
    for (label, fragment) in [
        ("dashboard snapshot projection", "function renderSnapshot"),
        (
            "dashboard current-work metric",
            "function renderDashboardCurrentWorkMetric",
        ),
        (
            "dashboard queue outcome",
            "function renderHomePipelineQueueOutcome",
        ),
    ] {
        if !app_dashboard_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView app dashboard script is missing required fragment '{label}'."
            )));
        }
    }

    let app_refresh_coordinator_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/app/refreshCoordinator.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        ("refresh coordinator", "async function refreshAllNow"),
        ("cross-page context payload", "const crossPageContext = {"),
        (
            "cross-page renderer",
            "renderCrossPageContext(crossPageContext)",
        ),
        (
            "sample validation read route",
            "/api/sample-validation?limit=10",
        ),
        (
            "settings handoff",
            "settings: values.settings || window.mediaPipelineSettingsView.getLastSettings()",
        ),
        (
            "floating pipeline log refresh handoff",
            "renderFloatingPipelineLog?.(values.diagnostics)",
        ),
    ] {
        if !app_refresh_coordinator_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView app refresh coordinator script is missing required fragment '{label}'."
            )));
        }
    }

    let app_lifecycle_orchestration_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/app/lifecycleOrchestration.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "app lifecycle DOM ready binding",
            "document.addEventListener(\"DOMContentLoaded\"",
        ),
        (
            "floating pipeline log init",
            "initFloatingPipelineLogEvents",
        ),
        ("startup critical refresh", "initialCritical: true"),
    ] {
        if !app_lifecycle_orchestration_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView app lifecycle orchestration script is missing required fragment '{label}'."
            )));
        }
    }

    let floating_pipeline_log_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/floatingPipelineLog.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "floating pipeline log diagnostics route",
            "/api/diagnostics",
        ),
        (
            "floating pipeline log refresh interval",
            "const REFRESH_INTERVAL_MS = 2000",
        ),
        (
            "floating pipeline log namespace",
            "window.mediaPipelineFloatingPipelineLog",
        ),
        (
            "floating pipeline log renderer",
            "function renderFloatingPipelineLog",
        ),
        (
            "floating pipeline log topbar button",
            "pipeline-log-window-button",
        ),
    ] {
        if !floating_pipeline_log_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView floating pipeline log script is missing required fragment '{label}'."
            )));
        }
    }

    let pipeline_log_bridge_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pipelineLogWindowBridge.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "pipeline log read-only window path",
            "/assets/pipelineLogWindow.html?surface=pipeline-log",
        ),
        ("pipeline log browser open", "window.open"),
        (
            "pipeline log native window command",
            "open_pipeline_log_window",
        ),
        ("pipeline log native Tauri bridge", "window.__TAURI__"),
        (
            "pipeline log browser fallback",
            "function showDiagnosticsLogsFallback",
        ),
        (
            "pipeline log diagnostics fallback status",
            "diagnostics-pipeline-log-status",
        ),
    ] {
        if !pipeline_log_bridge_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pipeline log bridge script is missing required fragment '{label}'."
            )));
        }
    }

    let pipeline_log_window = request_backend_json(
        backend_url,
        "GET",
        "/assets/pipelineLogWindow.html",
        token,
        "",
    )?;
    for (label, fragment) in [
        ("pipeline log status", "id=\"pipeline-log-window-status\""),
        (
            "pipeline log follow toggle",
            "id=\"pipeline-log-window-follow\"",
        ),
        (
            "pipeline log refresh button",
            "id=\"pipeline-log-window-refresh-button\"",
        ),
        ("pipeline log API client", "src=\"/assets/apiClient.js\""),
        (
            "pipeline log window script",
            "src=\"/assets/pipelineLogWindow.js\"",
        ),
    ] {
        if !pipeline_log_window.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pipeline log window is missing required fragment '{label}'."
            )));
        }
    }

    let pipeline_log_window_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pipelineLogWindow.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        ("pipeline log diagnostics route", "/api/diagnostics"),
        (
            "pipeline log refresh interval",
            "const REFRESH_INTERVAL_MS = 2000",
        ),
        (
            "pipeline log namespace",
            "window.mediaPipelinePipelineLogWindow",
        ),
        ("pipeline log renderer", "function renderPipelineLogWindow"),
    ] {
        if !pipeline_log_window_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pipeline log window script is missing required fragment '{label}'."
            )));
        }
    }

    let cross_page_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/crossPageContextView.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        ("conflict module bridge", "createCrossPageConflictModule"),
        ("sample module bridge", "createCrossPageSampleModule"),
        ("settings module bridge", "createCrossPageSettingsModule"),
        (
            "sample validation module bridge",
            "createCrossPageSampleValidationModule",
        ),
    ] {
        if !cross_page_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView cross-page script is missing required fragment '{label}'."
            )));
        }
    }
    let cross_page_conflict_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/crossPageContextView.conflict.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        ("conflict factory", "function createCrossPageConflictModule"),
        ("conflict rows", "function crossPageConflictRows"),
        ("conflict renderer", "function renderCrossPageConflictBoard"),
        ("conflict stash", "window.__crossPageConflictModule"),
    ] {
        if !cross_page_conflict_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView cross-page conflict script is missing required fragment '{label}'."
            )));
        }
    }
    let cross_page_sample_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/crossPageContextView.sample.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        ("sample factory", "function createCrossPageSampleModule"),
        ("sample rows", "function crossPageSampleRows"),
        (
            "validation template",
            "function crossPageValidationTemplateLines",
        ),
        ("sample stash", "window.__crossPageSampleModule"),
    ] {
        if !cross_page_sample_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView cross-page sample script is missing required fragment '{label}'."
            )));
        }
    }
    let cross_page_settings_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/crossPageContextView.settings.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        ("settings factory", "function createCrossPageSettingsModule"),
        (
            "saved media policy evidence",
            "function crossPageSettingsPolicyEvidence",
        ),
        (
            "backend media policy readiness evidence",
            "Backend media-policy readiness",
        ),
        ("backend media policy readiness summary", "media readiness="),
        ("settings stash", "window.__crossPageSettingsModule"),
    ] {
        if !cross_page_settings_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView cross-page settings script is missing required fragment '{label}'."
            )));
        }
    }
    let cross_page_sample_validation_worksheet_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/crossPageContextView.sampleValidation.worksheet.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "real-media worksheet renderer",
            "function renderCrossPageRealMediaWorksheet",
        ),
        (
            "real-media worksheet rows",
            "function crossPageRealMediaWorksheetRows",
        ),
        (
            "sample validation policy alignment",
            "function sampleValidationPolicyAlignmentSummaryLines",
        ),
        (
            "sample validation sample set renderer",
            "function renderSampleValidationSampleSetGuide",
        ),
        (
            "sample validation sample set category handoff",
            "function useSelectedSampleSetCategory",
        ),
        (
            "sample validation sample set summary",
            "Recommended real-media sample set:",
        ),
        (
            "worksheet mutation boundary",
            "this worksheet does not save, accept, repair, rerun, drain, delete, publish, rename, rewrite manifests, or touch media files",
        ),
        ("worksheet stash", "window.__crossPageSvWorksheetModule"),
    ] {
        if !cross_page_sample_validation_worksheet_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView cross-page sample validation worksheet script is missing required fragment '{label}'."
            )));
        }
    }
    let cross_page_sample_validation_runbook_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/crossPageContextView.sampleValidation.runbook.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "sample validation cutover renderer",
            "function renderSampleValidationCutoverGate",
        ),
        ("sample validation cutover summary", "WebView cutover gate:"),
        (
            "sample validation runbook renderer",
            "function renderSampleValidationRunbook",
        ),
        (
            "sample validation execution checklist",
            "function renderSampleValidationExecutionChecklist",
        ),
        ("runbook stash", "window.__crossPageSvRunbookModule"),
    ] {
        if !cross_page_sample_validation_runbook_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView cross-page sample validation runbook script is missing required fragment '{label}'."
            )));
        }
    }
    let cross_page_sample_validation_records_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/crossPageContextView.sampleValidation.records.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "sample validation record comparison",
            "function sampleValidationRecordComparisonRowsForPaths",
        ),
        (
            "sample validation completed packet",
            "function sampleValidationCompletedPacketRows",
        ),
        (
            "sample validation acceptance gate",
            "function renderSampleValidationAcceptanceGate",
        ),
        (
            "sample validation record review",
            "function renderSampleValidationRecordReview",
        ),
        (
            "acceptance gate boundary",
            "Decision rule: accepted sample evidence should not be appended",
        ),
        ("records stash", "window.__crossPageSvRecordsModule"),
    ] {
        if !cross_page_sample_validation_records_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView cross-page sample validation records script is missing required fragment '{label}'."
            )));
        }
    }
    let cross_page_sample_validation_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/crossPageContextView.sampleValidation.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "sample validation builder",
            "function buildSampleValidationRequest",
        ),
        (
            "sample validation append route",
            "/api/sample-validation/append",
        ),
        (
            "nested worksheet child bridge",
            "createCrossPageSvWorksheetModule",
        ),
        (
            "nested runbook child bridge",
            "createCrossPageSvRunbookModule",
        ),
        (
            "nested records child bridge",
            "createCrossPageSvRecordsModule",
        ),
    ] {
        if !cross_page_sample_validation_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView cross-page sample validation script is missing required fragment '{label}'."
            )));
        }
    }
    Ok(())
}
