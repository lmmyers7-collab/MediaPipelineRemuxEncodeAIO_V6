use crate::dialogs::shell_error;
use crate::http_helpers::request_backend_json;
use crate::ShellResult;

pub(super) fn validate_pending_publish(backend_url: &str, token: &str) -> ShellResult<()> {
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
    let pending_post_drain_trust_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublish/confidence/postDrainTrust.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "pending post-drain trust split factory",
            "function createPendingPostDrainTrustModule",
        ),
        (
            "pending post-drain trust split stash",
            "window.__pendingPostDrainTrustModule",
        ),
        (
            "pending post-drain trust renderer",
            "function renderPendingPostDrainTrust",
        ),
    ] {
        if !pending_post_drain_trust_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pending post-drain trust script is missing required fragment '{label}'."
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
            "pending post-drain trust composition",
            "pendingPostDrainTrustModule.createPendingPostDrainTrustModule",
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
            "let pendingSampleValidationHandoffLines",
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
    let pending_action_center_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublish/actionCenter.js",
        token,
        "",
    )?;
    let pending_rendering_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublish/rendering.js",
        token,
        "",
    )?;
    let pending_table_support_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublish/tableSupport.js",
        token,
        "",
    )?;
    let pending_default_adapters_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/pendingPublish/defaultAdapters.js",
        token,
        "",
    )?;
    for (label, fragment, script) in [
        (
            "pending action-center factory",
            "function createPendingPublishActionCenterModule",
            pending_action_center_script.as_str(),
        ),
        (
            "pending action-center boundary",
            "backend-owned drain command",
            pending_action_center_script.as_str(),
        ),
        (
            "pending rendering factory",
            "function createPendingPublishRenderingModule",
            pending_rendering_script.as_str(),
        ),
        (
            "pending rendering file inventory",
            "function renderPendingFileInventory",
            pending_rendering_script.as_str(),
        ),
        (
            "pending table-support factory",
            "function createPendingPublishTableSupportModule",
            pending_table_support_script.as_str(),
        ),
        (
            "pending default-adapter factory",
            "function createPendingPublishDefaultAdapters",
            pending_default_adapters_script.as_str(),
        ),
    ] {
        if !script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView pending publish child script is missing required fragment '{label}'."
            )));
        }
    }
    Ok(())
}
