use crate::dialogs::shell_error;
use crate::http_helpers::request_backend_json;
use crate::ShellResult;

use super::formatting::format_route_sample;
use super::routes::{
    RequiredLifecycleReconciliationRoute, REQUIRED_LIFECYCLE_RECONCILIATION_ROUTES,
    REQUIRED_NETWORK_LIFECYCLE_ROUTES, REQUIRED_NETWORK_SETUP_ROUTES, REQUIRED_ROUTES,
};
use super::types::{BackendContract, BackendRoute};

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
    for required in REQUIRED_LIFECYCLE_RECONCILIATION_ROUTES {
        let route = contract
            .routes
            .iter()
            .find(|route| {
                route.method == "POST" && route.path == required.path && route.auth_required
            })
            .ok_or_else(|| {
                shell_error(format!(
                    "Backend contract is missing required lifecycle reconciliation route: POST {}; backend reported {} route(s); sample: {}",
                    required.path,
                    contract.routes.len(),
                    format_route_sample(&contract.routes, 12)
                ))
            })?;
        validate_lifecycle_reconciliation_route(route, required)?;
    }
    for required in REQUIRED_NETWORK_LIFECYCLE_ROUTES {
        let route = contract
            .routes
            .iter()
            .find(|route| route.method == "POST" && route.path == required.path && route.auth_required)
            .ok_or_else(|| {
                shell_error(format!(
                    "Backend contract is missing required network lifecycle route: POST {}; backend reported {} route(s); sample: {}",
                    required.path,
                    contract.routes.len(),
                    format_route_sample(&contract.routes, 12)
                ))
            })?;
        let lifecycle = route.network_lifecycle.as_ref().ok_or_else(|| {
            shell_error(format!(
                "Backend contract route POST {} is missing network_lifecycle metadata.",
                required.path
            ))
        })?;
        if route.effect.as_deref() != Some(required.effect)
            || route.requires_confirmation != Some(required.requires_confirmation)
            || route.owner.as_deref() != Some(required.owner)
            || route.frontend_exposed != Some(required.frontend_exposed)
            || lifecycle.role != required.role
            || lifecycle.action != required.action
            || lifecycle.dry_run != required.dry_run
        {
            return Err(shell_error(format!(
                "Backend contract network lifecycle metadata drifted for POST {}.",
                required.path
            )));
        }
    }
    for required in REQUIRED_NETWORK_SETUP_ROUTES {
        let route = contract
            .routes
            .iter()
            .find(|route| route.method == "POST" && route.path == required.path && route.auth_required)
            .ok_or_else(|| {
                shell_error(format!(
                    "Backend contract is missing required network setup route: POST {}; backend reported {} route(s); sample: {}",
                    required.path,
                    contract.routes.len(),
                    format_route_sample(&contract.routes, 12)
                ))
            })?;
        if route.effect.as_deref() != Some(required.effect)
            || route.requires_confirmation != Some(required.requires_confirmation)
            || route.owner.as_deref() != Some(required.owner)
            || route.frontend_exposed != Some(required.frontend_exposed)
            || route.journaled != Some(required.journaled)
        {
            return Err(shell_error(format!(
                "Backend contract network setup metadata drifted for POST {}.",
                required.path
            )));
        }
    }
    Ok(())
}

pub(crate) fn validate_lifecycle_reconciliation_route(
    route: &BackendRoute,
    required: &RequiredLifecycleReconciliationRoute,
) -> ShellResult<()> {
    let request_keys_match = route
        .request_keys
        .iter()
        .map(String::as_str)
        .eq(required.request_keys.iter().copied());
    let strict_booleans_match = route
        .requires_strict_boolean
        .iter()
        .map(String::as_str)
        .eq(required.requires_strict_boolean.iter().copied());
    let safe_defaults_match = match (&route.safe_defaults, required.safe_defaults) {
        (None, None) => true,
        (Some(actual), Some(expected)) => actual.as_object().is_some_and(|actual| {
            actual.len() == expected.len()
                && expected.iter().all(|(key, value)| {
                    actual.get(*key).and_then(serde_json::Value::as_bool) == Some(*value)
                })
        }),
        _ => false,
    };

    if route.effect.as_deref() != Some(required.effect)
        || !request_keys_match
        || !safe_defaults_match
        || !strict_booleans_match
        || route.requires_dry_run_fingerprint != required.requires_dry_run_fingerprint
        || route.requires_confirmation != Some(required.requires_confirmation)
        || route.journaled != Some(required.journaled)
        || route.response_schema.as_deref() != Some(required.response_schema)
        || route.data_schema.as_deref() != Some(required.data_schema)
    {
        return Err(shell_error(format!(
            "Backend contract lifecycle reconciliation metadata drifted for POST {}.",
            required.path
        )));
    }
    Ok(())
}
