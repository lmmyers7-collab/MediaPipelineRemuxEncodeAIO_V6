use serde::Deserialize;

use crate::dialogs::shell_error;
use crate::http_helpers::{bounded_text, request_backend_json};
use crate::ShellResult;

#[derive(Debug, Deserialize)]
struct BackendHealth {
    schema_version: String,
    status: String,
    capabilities: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct BackendContract {
    schema_version: String,
    routes: Vec<BackendRoute>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct BackendRoute {
    pub(crate) method: String,
    pub(crate) path: String,
    pub(crate) auth_required: bool,
}

pub(crate) fn validate_backend_health(backend_url: &str, token: &str) -> ShellResult<()> {
    let response = request_backend_json(backend_url, "GET", "/api/health", token, "")?;
    let health: BackendHealth = serde_json::from_str(&response)
        .map_err(|error| shell_error(format!("Backend health response was not JSON: {error}")))?;
    if health.schema_version != "desktop_backend_health.v1" {
        return Err(shell_error(format!(
            "Unexpected backend health schema: {}",
            health.schema_version
        )));
    }
    if health.status != "ok" {
        return Err(shell_error(format!(
            "Backend health status is not ok: {}",
            health.status
        )));
    }
    for capability in [
        "snapshot",
        "telemetry",
        "diagnostics",
        "close-readiness",
        "command-history",
        "settings-workspace",
        "settings-validate",
        "pipeline-start",
        "audit-start",
        "rerun-start",
    ] {
        if !health.capabilities.iter().any(|item| item == capability) {
            return Err(shell_error(format!(
                "Backend health is missing required capability: {capability}; backend reported capabilities: {}",
                format_list_preview(&health.capabilities, 12)
            )));
        }
    }
    Ok(())
}

pub(crate) fn validate_backend_contract(backend_url: &str, token: &str) -> ShellResult<()> {
    let response = request_backend_json(backend_url, "GET", "/api/contract", token, "")?;
    let contract: BackendContract = serde_json::from_str(&response)
        .map_err(|error| shell_error(format!("Backend contract response was not JSON: {error}")))?;
    if contract.schema_version != "desktop_local_api_contract.v1" {
        return Err(shell_error(format!(
            "Unexpected backend contract schema: {}",
            contract.schema_version
        )));
    }
    for (method, path, auth_required) in [
        ("GET", "/api/health", false),
        ("GET", "/api/contract", true),
        ("GET", "/api/snapshot", true),
        ("GET", "/api/telemetry", true),
        ("GET", "/api/diagnostics", true),
        ("GET", "/api/diagnostics/tail", true),
        ("GET", "/api/diagnostics/state-summary", true),
        ("GET", "/api/backend/close-readiness", true),
        ("GET", "/api/launch/preflight", true),
        ("GET", "/api/commands", true),
        ("GET", "/api/queue", true),
        ("GET", "/api/queue/priority", true),
        ("GET", "/api/queue/strategy", true),
        ("GET", "/api/queue/file-overrides", true),
        ("GET", "/api/completed", true),
        ("GET", "/api/failures", true),
        ("GET", "/api/audit-results", true),
        ("GET", "/api/pending-publish", true),
        ("GET", "/api/publish-reconciliation", true),
        ("GET", "/api/maintenance", true),
        ("GET", "/api/maintenance/progress", true),
        ("GET", "/api/schedule", true),
        ("GET", "/api/settings/workspace", true),
        ("GET", "/api/network/workers", true),
        ("GET", "/api/sample-validation", true),
        ("POST", "/api/queue/priority", true),
        ("POST", "/api/queue/strategy", true),
        ("POST", "/api/queue/file-overrides", true),
        ("POST", "/api/queue/open", true),
        ("POST", "/api/completed/open", true),
        ("POST", "/api/failures/clear", true),
        ("POST", "/api/pending-publish/open", true),
        ("POST", "/api/pending-publish/recovery-plan", true),
        ("POST", "/api/maintenance/release-dry-run", true),
        ("POST", "/api/maintenance/release-build", true),
        ("POST", "/api/maintenance/completed-backfill-dry-run", true),
        ("POST", "/api/diagnostics/open", true),
        ("POST", "/api/rename/preview", true),
        ("POST", "/api/rename/browse", true),
        ("POST", "/api/rename/apply", true),
        ("POST", "/api/schedule/preview", true),
        ("POST", "/api/schedule/save", true),
        ("POST", "/api/settings/validate", true),
        ("POST", "/api/settings/browse-path", true),
        ("POST", "/api/settings/preview-patch", true),
        ("POST", "/api/settings/save-patch", true),
        ("POST", "/api/settings/reload", true),
        ("POST", "/api/sample-validation/preview", true),
        ("POST", "/api/sample-validation/append", true),
        ("POST", "/api/pipeline/control", true),
        ("POST", "/api/pipeline/start", true),
        ("POST", "/api/audit/start", true),
        ("POST", "/api/rerun/start", true),
        ("POST", "/api/backend/shutdown", true),
    ] {
        if !contract.routes.iter().any(|route| {
            route.method == method && route.path == path && route.auth_required == auth_required
        }) {
            return Err(shell_error(format!(
                "Backend contract is missing required route: {method} {path} auth_required={auth_required}; backend reported {} route(s); sample: {}",
                contract.routes.len(),
                format_route_sample(&contract.routes, 12)
            )));
        }
    }
    Ok(())
}

pub(crate) fn validate_backend_web_ui(backend_url: &str, token: &str) -> ShellResult<()> {
    let index = request_backend_json(backend_url, "GET", "/", token, "")?;
    for (label, fragment) in [
        (
            "bootstrap assignment",
            "window.MEDIA_PIPELINE_BOOTSTRAP = Object.assign(",
        ),
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
            "settings: values.settings || getLastSettings()",
        ),
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
    let diagnostics_active_jobs_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/diagnosticsView.activejobs.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "diagnostics active-jobs split factory",
            "function createDiagnosticsActiveJobsModule",
        ),
        (
            "diagnostics active-jobs split stash",
            "window.__diagnosticsActiveJobsModule",
        ),
        (
            "diagnostics active-jobs real-media trace",
            "function diagnosticsActiveJobRealMediaTraceLines",
        ),
    ] {
        if !diagnostics_active_jobs_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView diagnostics active-jobs script is missing required fragment '{label}'."
            )));
        }
    }
    let diagnostics_log_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/diagnosticsView.log.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "diagnostics log split factory",
            "function createDiagnosticsLogModule",
        ),
        (
            "diagnostics log split stash",
            "window.__diagnosticsLogModule",
        ),
        ("diagnostics log rows", "function diagnosticsLogRows"),
        ("diagnostics log triage guidance", "Log triage guidance:"),
    ] {
        if !diagnostics_log_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView diagnostics log script is missing required fragment '{label}'."
            )));
        }
    }
    let diagnostics_investigation_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/diagnosticsView.investigation.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "diagnostics investigation split factory",
            "function createDiagnosticsInvestigationModule",
        ),
        (
            "diagnostics investigation split stash",
            "window.__diagnosticsInvestigationModule",
        ),
        (
            "diagnostics investigation actions",
            "function diagnosticsInvestigationActions",
        ),
        (
            "diagnostics owning-page handoff",
            "Owning-page evidence handoff:",
        ),
    ] {
        if !diagnostics_investigation_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView diagnostics investigation script is missing required fragment '{label}'."
            )));
        }
    }
    let diagnostics_script =
        request_backend_json(backend_url, "GET", "/assets/diagnosticsView.js", token, "")?;
    for (label, fragment) in [
        (
            "diagnostics active-jobs child bridge",
            "const diagnosticsActiveJobsModule = window.__diagnosticsActiveJobsModule || {}",
        ),
        (
            "diagnostics log child bridge",
            "const diagnosticsLogModule = window.__diagnosticsLogModule || {}",
        ),
        (
            "diagnostics investigation child bridge",
            "const diagnosticsInvestigationModule = window.__diagnosticsInvestigationModule || {}",
        ),
        (
            "diagnostics external dependency first response",
            "External dependency readiness",
        ),
        (
            "diagnostics external dependency safe action",
            "Resolve blocked Settings OCR or Maintenance toolchain evidence",
        ),
    ] {
        if !diagnostics_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView diagnostics script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_raw_triage_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settingsView.rawTriage.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings raw triage split factory",
            "function createSettingsRawTriageModule",
        ),
        (
            "settings raw triage split stash",
            "window.__settingsRawTriageModule",
        ),
        ("settings raw triage rows", "function settingsRawTriageRows"),
        (
            "settings raw action plan rows",
            "function settingsRawActionPlanRows",
        ),
        (
            "settings raw action plan summary",
            "Settings raw-key action plan:",
        ),
    ] {
        if !settings_raw_triage_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings raw-triage script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_safety_locks_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/settingsView.safetyLocks.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "settings safety locks split factory",
            "function createSettingsSafetyLocksModule",
        ),
        (
            "settings safety locks split stash",
            "window.__settingsSafetyLocksModule",
        ),
        (
            "settings safety lock rows",
            "function settingsSafetyLockRows",
        ),
        (
            "settings safety lock summary",
            "Settings safety lock review:",
        ),
    ] {
        if !settings_safety_locks_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings safety-lock script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_script =
        request_backend_json(backend_url, "GET", "/assets/settingsView.js", token, "")?;
    for (label, fragment) in [
        (
            "settings raw triage child bridge",
            "const settingsRawTriageModule = window.__settingsRawTriageModule || {}",
        ),
        (
            "settings safety locks child bridge",
            "const settingsSafetyLocksModule = window.__settingsSafetyLocksModule || {}",
        ),
        (
            "settings backend readiness reader",
            "function settingsBackendMediaPolicyReadiness",
        ),
        (
            "settings backend readiness renderer",
            "function renderSettingsBackendMediaPolicyReadiness",
        ),
        (
            "settings backend readiness heading",
            "Backend media-policy readiness:",
        ),
        ("settings backend readiness guardrail", "this table cannot stage settings, save config, launch work, run FFmpeg, publish files, or touch source media"),
        ("settings staged policy delta rows", "function settingsPolicyDeltaRows"),
        ("settings staged policy delta summary", "Staged media-policy delta:"),
        (
            "settings effective policy trust rows",
            "function settingsEffectivePolicyRows",
        ),
        (
            "settings effective policy trust summary",
            "Effective policy trust summary:",
        ),
        (
            "settings effective policy launch-active boundary",
            "Launch-active policy is the saved backend config",
        ),
        (
            "settings preview/save result rows",
            "function settingsBackendResultRows",
        ),
        (
            "settings preview/save result detail",
            "function settingsBackendResultDetailLines",
        ),
        (
            "settings preview/save result renderer",
            "function renderSettingsBackendResultFromEntries",
        ),
        (
            "settings preview/save stale guard",
            "Patch JSON changed after the last preview. Preview again before saving.",
        ),
        (
            "settings preview/save persistence boundary",
            "Save Patch is the only persistence command",
        ),
    ] {
        if !settings_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings script is missing required fragment '{label}'."
            )));
        }
    }
    let settings_overview_script =
        request_backend_json(backend_url, "GET", "/assets/settingsOverview.js", token, "")?;
    for (label, fragment) in [
        (
            "settings trust readiness line",
            "function settingsMediaPolicyReadinessLine",
        ),
        (
            "settings trust readiness payload",
            "settings.media_policy_readiness",
        ),
    ] {
        if !settings_overview_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView settings overview script is missing required fragment '{label}'."
            )));
        }
    }
    let launch_risk_script =
        request_backend_json(backend_url, "GET", "/assets/launchView.risk.js", token, "")?;
    for (label, fragment) in [
        (
            "launch risk split factory",
            "function createLaunchRiskModule",
        ),
        ("launch risk split stash", "window.__launchViewRiskModule"),
        (
            "launch backend readiness row",
            "Backend media-policy readiness",
        ),
        ("launch backend readiness payload", "media_policy_readiness"),
        (
            "launch blocked readiness guidance",
            "Resolve blocked saved media-policy rows before launching unattended work.",
        ),
        (
            "launch active policy boundary",
            "Launch active media-policy boundary:",
        ),
        (
            "launch saved-settings intent",
            "Saved settings vs launch intent checklist:",
        ),
    ] {
        if !launch_risk_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView launch risk script is missing required fragment '{label}'."
            )));
        }
    }
    let launch_scope_script =
        request_backend_json(backend_url, "GET", "/assets/launchView.scope.js", token, "")?;
    for (label, fragment) in [
        (
            "launch scope split factory",
            "function createLaunchScopeModule",
        ),
        ("launch scope split stash", "window.__launchViewScopeModule"),
        (
            "launch scope reconciliation",
            "Launch scope reconciliation:",
        ),
        (
            "launch start decision summary",
            "Launch start decision summary:",
        ),
    ] {
        if !launch_scope_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView launch scope script is missing required fragment '{label}'."
            )));
        }
    }
    let launch_realmedia_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/launchView.realmedia.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "launch real-media split factory",
            "function createLaunchRealMediaModule",
        ),
        (
            "launch real-media split stash",
            "window.__launchViewRealMediaModule",
        ),
        (
            "launch real-media proof handoff",
            "Launch real-media sample proof handoff:",
        ),
        (
            "launch sample execution checklist",
            "Launch sample execution checklist:",
        ),
    ] {
        if !launch_realmedia_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView launch real-media script is missing required fragment '{label}'."
            )));
        }
    }
    let launch_preflight_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/launchView.preflight.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "launch preflight split factory",
            "function createLaunchPreflightModule",
        ),
        (
            "launch preflight split stash",
            "window.__launchViewPreflightModule",
        ),
        (
            "launch pilot readiness rows",
            "function launchPilotRunReadinessRows",
        ),
        (
            "launch pilot readiness renderer",
            "function renderLaunchPilotRunReadiness",
        ),
        (
            "launch pilot readiness summary",
            "Launch pilot run readiness:",
        ),
    ] {
        if !launch_preflight_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView launch preflight script is missing required fragment '{label}'."
            )));
        }
    }
    let launch_script =
        request_backend_json(backend_url, "GET", "/assets/launchView.js", token, "")?;
    for (label, fragment) in [
        (
            "launch preflight parent stash read",
            "const launchPreflightModule = window.__launchViewPreflightModule || {}",
        ),
        (
            "launch preflight parent stash cleanup",
            "delete window.__launchViewPreflightModule",
        ),
    ] {
        if !launch_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView launch script is missing required fragment '{label}'."
            )));
        }
    }
    let diagnostics_state_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/diagnosticsStateSummaryView.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "diagnostics read-order renderer",
            "function renderDiagnosticsStateTriage",
        ),
        (
            "diagnostics read-order rows",
            "function renderDiagnosticsStateTriageRows",
        ),
        (
            "diagnostics read-order action target",
            "diagnostics-state-triage-actions",
        ),
        ("diagnostics read-order summary", "Backend read order:"),
    ] {
        if !diagnostics_state_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView diagnostics state script is missing required fragment '{label}'."
            )));
        }
    }
    let pending_recovery_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublishView.recovery.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "pending recovery split factory",
            "function createPendingPublishRecoveryModule",
        ),
        (
            "pending recovery split stash",
            "window.__pendingPublishRecoveryModule",
        ),
        (
            "pending recovery result renderer",
            "function renderPendingRecoveryPlanResult",
        ),
        (
            "pending recovery dry-run route",
            "/api/pending-publish/recovery-plan",
        ),
    ] {
        if !pending_recovery_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pending publish recovery script is missing required fragment '{label}'."
            )));
        }
    }
    let pending_diagnostics_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublishView.diagnostics.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "pending diagnostics split factory",
            "function createPendingPublishDiagnosticsModule",
        ),
        (
            "pending diagnostics split stash",
            "window.__pendingPublishDiagnosticsModule",
        ),
        (
            "pending diagnostics open route",
            "/api/pending-publish/open",
        ),
        (
            "pending diagnostics allowlist boundary",
            "The Pending page never sends arbitrary filesystem paths.",
        ),
    ] {
        if !pending_diagnostics_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pending publish diagnostics script is missing required fragment '{label}'."
            )));
        }
    }
    let pending_drain_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublishView.drain.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "pending drain split factory",
            "function createPendingPublishDrainModule",
        ),
        (
            "pending drain split stash",
            "window.__pendingPublishDrainModule",
        ),
        (
            "pending drain evidence renderer",
            "function renderPendingDrainEvidence",
        ),
        (
            "pending drain correlation renderer",
            "function renderPendingDrainCorrelation",
        ),
        (
            "pending drain evidence board",
            "Pending drain evidence board:",
        ),
    ] {
        if !pending_drain_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pending publish drain script is missing required fragment '{label}'."
            )));
        }
    }
    let pending_confidence_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublishView.confidence.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "pending confidence split factory",
            "function createPendingPublishConfidenceModule",
        ),
        (
            "pending confidence split stash",
            "window.__pendingPublishConfidenceModule",
        ),
        (
            "pending drain guard state",
            "function pendingDrainGuardState",
        ),
        (
            "pending drain decision checklist",
            "function renderPendingDrainDecisionChecklist",
        ),
        (
            "pending drain action confidence",
            "Pending Publish drain action confidence:",
        ),
    ] {
        if !pending_confidence_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pending publish confidence script is missing required fragment '{label}'."
            )));
        }
    }
    let pending_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublishView.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "pending sample validation handoff",
            "function pendingSampleValidationHandoffLines",
        ),
        (
            "pending recovery parent stash read",
            "const pendingRecoveryModule = window.__pendingPublishRecoveryModule || {}",
        ),
        (
            "pending diagnostics parent stash read",
            "const pendingDiagnosticsModule = window.__pendingPublishDiagnosticsModule || {}",
        ),
        (
            "pending drain parent stash read",
            "const pendingDrainModule = window.__pendingPublishDrainModule || {}",
        ),
        (
            "pending confidence parent stash read",
            "const pendingConfidenceModule = window.__pendingPublishConfidenceModule || {}",
        ),
    ] {
        if !pending_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pending publish script is missing required fragment '{label}'."
            )));
        }
    }
    Ok(())
}

pub(crate) fn format_list_preview(items: &[String], max_items: usize) -> String {
    let preview = items
        .iter()
        .take(max_items)
        .map(|item| bounded_text(item, 80))
        .collect::<Vec<String>>()
        .join(", ");
    if items.len() > max_items {
        format!("{preview}, ...")
    } else {
        preview
    }
}

pub(crate) fn format_route_sample(routes: &[BackendRoute], max_items: usize) -> String {
    let preview = routes
        .iter()
        .take(max_items)
        .map(|route| {
            format!(
                "{} {} auth_required={}",
                route.method, route.path, route.auth_required
            )
        })
        .collect::<Vec<String>>()
        .join("; ");
    if routes.len() > max_items {
        format!("{preview}; ...")
    } else {
        preview
    }
}
