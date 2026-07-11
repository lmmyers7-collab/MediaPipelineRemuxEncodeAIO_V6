use crate::dialogs::shell_error;
use crate::http_helpers::request_backend_json;
use crate::ShellResult;

pub(super) fn validate_launch(backend_url: &str, token: &str) -> ShellResult<()> {
    let mut launch_risk_script = String::new();
    for asset_path in [
        "/assets/launch/risk/settingsAccess.js",
        "/assets/launch/risk/mediaPolicyValues.js",
        "/assets/launch/risk/riskRows.js",
        "/assets/launch/risk/policyPatch.js",
        "/assets/launch/risk/policyBoundary.js",
        "/assets/launchView.risk.js",
    ] {
        launch_risk_script.push_str(&request_backend_json(
            backend_url,
            "GET",
            asset_path,
            token,
            "",
        )?);
        launch_risk_script.push('\n');
    }
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
    let launch_pilot_readiness_script = request_backend_json(
        backend_url,
        "GET",
        "/assets/launch/preflight/pilotReadiness.js",
        token,
        "",
    )?;
    for (label, fragment) in [
        (
            "launch pilot readiness split factory",
            "function createLaunchPilotReadinessModule",
        ),
        (
            "launch pilot readiness split stash",
            "window.__launchPilotReadinessModule",
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
        if !launch_pilot_readiness_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView launch pilot readiness script is missing required fragment '{label}'."
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
            "launch pilot readiness parent stash read",
            "const launchPilotReadinessModule = window.__launchPilotReadinessModule || {}",
        ),
        (
            "launch pilot readiness parent stash cleanup",
            "delete window.__launchPilotReadinessModule",
        ),
        (
            "launch pilot readiness parent composition",
            "launchPilotReadinessModule.createLaunchPilotReadinessModule",
        ),
    ] {
        if !launch_preflight_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView launch preflight script is missing required fragment '{label}'."
            )));
        }
    }
    let mut launch_child_script = String::new();
    for asset_path in [
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
    ] {
        launch_child_script.push_str(&request_backend_json(
            backend_url,
            "GET",
            asset_path,
            token,
            "",
        )?);
        launch_child_script.push('\n');
    }
    for (label, fragment) in [
        (
            "launch controller state split factory",
            "function createLaunchControllerStateModule",
        ),
        (
            "launch controller state split stash",
            "window.__launchControllerStateModule",
        ),
        (
            "launch status render split factory",
            "function createLaunchStatusRenderModule",
        ),
        (
            "launch status render split stash",
            "window.__launchStatusRenderModule",
        ),
        (
            "launch start request split factory",
            "function createLaunchStartRequestModule",
        ),
        (
            "launch start request split stash",
            "window.__launchStartRequestModule",
        ),
        (
            "launch scope controls split factory",
            "function createLaunchScopeControlsModule",
        ),
        (
            "launch scope controls split stash",
            "window.__launchScopeControlsModule",
        ),
        (
            "launch command buttons split factory",
            "function createLaunchCommandButtonsModule",
        ),
        (
            "launch command buttons split stash",
            "window.__launchCommandButtonsModule",
        ),
        (
            "launch command orchestration split factory",
            "function createLaunchCommandOrchestrationModule",
        ),
        (
            "launch rerun evidence split factory",
            "function createLaunchRerunEvidenceModule",
        ),
        (
            "launch rerun presentation split factory",
            "function createLaunchRerunPresentationModule",
        ),
        (
            "launch rerun orchestration split factory",
            "function createLaunchRerunOrchestrationModule",
        ),
        (
            "launch rerun facade split factory",
            "function createLaunchRerunFacade",
        ),
    ] {
        if !launch_child_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView launch child script is missing required fragment '{label}'."
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
        (
            "launch controller state parent stash read",
            "const launchControllerStateModule = window.__launchControllerStateModule || {}",
        ),
        (
            "launch controller state parent stash cleanup",
            "delete window.__launchControllerStateModule",
        ),
        (
            "launch status render parent stash read",
            "const launchStatusRenderModule = window.__launchStatusRenderModule || {}",
        ),
        (
            "launch status render parent stash cleanup",
            "delete window.__launchStatusRenderModule",
        ),
        (
            "launch start request parent stash read",
            "const launchStartRequestModule = window.__launchStartRequestModule || {}",
        ),
        (
            "launch start request parent stash cleanup",
            "delete window.__launchStartRequestModule",
        ),
        (
            "launch scope controls parent stash read",
            "const launchScopeControlsModule = window.__launchScopeControlsModule || {}",
        ),
        (
            "launch scope controls parent stash cleanup",
            "delete window.__launchScopeControlsModule",
        ),
        (
            "launch command buttons parent stash read",
            "const launchCommandButtonsModule = window.__launchCommandButtonsModule || {}",
        ),
        (
            "launch command buttons parent stash cleanup",
            "delete window.__launchCommandButtonsModule",
        ),
        (
            "launch command orchestration parent composition",
            "launchCommandOrchestrationFactory.createLaunchCommandOrchestrationModule",
        ),
        (
            "launch rerun facade parent composition",
            "rerunFacadeFactory.createLaunchRerunFacade",
        ),
    ] {
        if !launch_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView launch script is missing required fragment '{label}'."
            )));
        }
    }
    Ok(())
}
