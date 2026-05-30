use crate::dialogs::shell_error;
use crate::http_helpers::request_backend_json;
use crate::ShellResult;

use super::formatting::format_list_preview;
use super::types::BackendHealth;

const REQUIRED_CAPABILITIES: &[&str] = &[
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
];

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
    for capability in REQUIRED_CAPABILITIES {
        if !health.capabilities.iter().any(|item| item == capability) {
            return Err(shell_error(format!(
                "Backend health is missing required capability: {capability}; backend reported capabilities: {}",
                format_list_preview(&health.capabilities, 12)
            )));
        }
    }
    Ok(())
}
