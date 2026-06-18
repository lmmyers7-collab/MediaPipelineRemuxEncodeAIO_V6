use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub(crate) struct BackendHealth {
    pub(crate) schema_version: String,
    pub(crate) status: String,
    pub(crate) capabilities: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct BackendContract {
    pub(crate) schema_version: String,
    pub(crate) routes: Vec<BackendRoute>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct BackendRoute {
    pub(crate) method: String,
    pub(crate) path: String,
    pub(crate) auth_required: bool,
    #[serde(default)]
    pub(crate) effect: Option<String>,
    #[serde(default)]
    pub(crate) requires_confirmation: Option<bool>,
    #[serde(default)]
    pub(crate) owner: Option<String>,
    #[serde(default)]
    pub(crate) frontend_exposed: Option<bool>,
    #[serde(default)]
    pub(crate) journaled: Option<bool>,
    #[serde(default)]
    pub(crate) network_lifecycle: Option<NetworkLifecycleRoute>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct NetworkLifecycleRoute {
    pub(crate) role: String,
    pub(crate) action: String,
    pub(crate) dry_run: bool,
}
