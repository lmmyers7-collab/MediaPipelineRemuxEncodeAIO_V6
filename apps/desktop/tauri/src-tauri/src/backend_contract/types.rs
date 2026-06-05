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
}
