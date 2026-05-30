use crate::dialogs::shell_error;
use crate::http_helpers::request_backend_json;
use crate::ShellResult;

use super::formatting::format_route_sample;
use super::routes::REQUIRED_ROUTES;
use super::types::BackendContract;

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
    for (method, path, auth_required) in REQUIRED_ROUTES {
        if !contract.routes.iter().any(|route| {
            route.method == *method && route.path == *path && route.auth_required == *auth_required
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
