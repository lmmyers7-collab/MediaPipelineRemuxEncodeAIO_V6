mod diagnostics;
mod launch;
mod pending_publish;
mod settings;
mod web_shell;

mod formatting;
mod health;
mod route_contract;
mod routes;
mod types;

#[allow(unused_imports)]
pub(crate) use formatting::{format_list_preview, format_route_sample};
pub(crate) use health::validate_backend_health;
pub(crate) use route_contract::validate_backend_contract;
#[allow(unused_imports)]
pub(crate) use types::BackendRoute;

use crate::ShellResult;

pub(crate) fn validate_backend_web_ui(backend_url: &str, token: &str) -> ShellResult<()> {
    web_shell::validate_web_shell(backend_url, token)?;
    diagnostics::validate_diagnostics(backend_url, token)?;
    settings::validate_settings(backend_url, token)?;
    launch::validate_launch(backend_url, token)?;
    pending_publish::validate_pending_publish(backend_url, token)?;
    Ok(())
}
