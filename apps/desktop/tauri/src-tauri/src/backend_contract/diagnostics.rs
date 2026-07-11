use crate::dialogs::shell_error;
use crate::http_helpers::request_backend_json;
use crate::ShellResult;

pub(super) fn validate_diagnostics(backend_url: &str, token: &str) -> ShellResult<()> {
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
    let mut diagnostics_refinement_script = String::new();
    for asset_path in [
        "/assets/diagnostics/matrixConsole.js",
        "/assets/diagnostics/triage.js",
        "/assets/diagnostics/firstResponse.js",
    ] {
        diagnostics_refinement_script.push_str(&request_backend_json(
            backend_url,
            "GET",
            asset_path,
            token,
            "",
        )?);
        diagnostics_refinement_script.push('\n');
    }
    for (label, fragment) in [
        (
            "diagnostics matrix-console split factory",
            "function createDiagnosticsMatrixConsoleModule",
        ),
        (
            "diagnostics triage split factory",
            "function createDiagnosticsTriageModule",
        ),
        (
            "diagnostics first-response split factory",
            "function createDiagnosticsFirstResponseModule",
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
        if !diagnostics_refinement_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView diagnostics refinement script is missing required fragment '{label}'."
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
            "diagnostics matrix-console child bridge",
            "const diagnosticsMatrixConsoleModule = window.__diagnosticsMatrixConsoleModule",
        ),
        (
            "diagnostics triage child bridge",
            "const diagnosticsTriageModule = window.__diagnosticsTriageModule",
        ),
        (
            "diagnostics first-response child bridge",
            "const diagnosticsFirstResponseModule = window.__diagnosticsFirstResponseModule",
        ),
    ] {
        if !diagnostics_script.contains(fragment) {
            return Err(shell_error(format!(
                "Backend WebView diagnostics script is missing required fragment '{label}'."
            )));
        }
    }
    Ok(())
}
