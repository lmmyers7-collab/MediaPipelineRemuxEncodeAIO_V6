use serde::Deserialize;

use crate::dialogs::shell_error;
use crate::http_helpers::{bounded_text, request_backend_json};
use crate::{ShellResult, MAX_CLOSE_READINESS_WARNINGS, MAX_CLOSE_READINESS_WARNING_CHARS};

#[derive(Debug, Deserialize)]
pub(crate) struct CloseReadiness {
    pub(crate) schema_version: String,
    pub(crate) safe_to_close: bool,
    pub(crate) state: String,
    pub(crate) reason: String,
    #[serde(default)]
    pub(crate) warnings: Vec<String>,
    #[serde(default)]
    pub(crate) continuous_watcher: ContinuousWatcher,
}

#[derive(Debug, Default, Deserialize)]
pub(crate) struct ContinuousWatcher {
    #[serde(default)]
    pub(crate) status: String,
    #[serde(default)]
    pub(crate) pid: u32,
    #[serde(default)]
    pub(crate) deadline: String,
    #[serde(default)]
    pub(crate) stop_requested: bool,
    #[serde(default)]
    pub(crate) generation: u64,
    #[serde(default)]
    pub(crate) message: String,
    #[serde(default)]
    pub(crate) error: String,
}

pub(crate) fn request_close_readiness(
    backend_url: &str,
    token: &str,
) -> ShellResult<CloseReadiness> {
    let response = request_backend_json(
        backend_url,
        "GET",
        "/api/backend/close-readiness",
        token,
        "",
    )?;
    let readiness: CloseReadiness = serde_json::from_str(&response)
        .map_err(|error| shell_error(format!("Close-readiness response was not JSON: {error}")))?;
    if readiness.schema_version != "desktop_close_readiness.v1" {
        return Err(shell_error(format!(
            "Unexpected close-readiness schema: {}",
            readiness.schema_version
        )));
    }
    Ok(readiness)
}

pub(crate) fn close_readiness_warning_detail(readiness: &CloseReadiness) -> String {
    let mut detail = if readiness.reason.trim().is_empty() {
        format!(
            "Backend reports active work. Current state: {}.",
            readiness.state
        )
    } else {
        readiness.reason.clone()
    };
    let warning_lines: Vec<String> = readiness
        .warnings
        .iter()
        .filter(|warning| !warning.trim().is_empty())
        .take(MAX_CLOSE_READINESS_WARNINGS)
        .map(|warning| bounded_text(warning.trim(), MAX_CLOSE_READINESS_WARNING_CHARS))
        .collect();
    if !warning_lines.is_empty() {
        detail.push_str("\n\nWarnings:");
        for warning in warning_lines {
            detail.push_str("\n- ");
            detail.push_str(&warning);
        }
    }
    let watcher_lines = close_readiness_watcher_lines(&readiness.continuous_watcher);
    if !watcher_lines.is_empty() {
        detail.push_str("\n\nContinuous schedule-stop watcher:");
        for line in watcher_lines {
            detail.push_str("\n- ");
            detail.push_str(&line);
        }
    }
    detail
}

pub(crate) fn close_readiness_watcher_lines(watcher: &ContinuousWatcher) -> Vec<String> {
    let status = watcher.status.trim();
    if status.is_empty() {
        return Vec::new();
    }
    let mut lines = vec![format!("status: {status}")];
    if watcher.pid > 0 {
        lines.push(format!("pid: {}", watcher.pid));
    }
    if !watcher.deadline.trim().is_empty() {
        lines.push(format!(
            "deadline: {}",
            bounded_text(watcher.deadline.trim(), MAX_CLOSE_READINESS_WARNING_CHARS)
        ));
    }
    lines.push(format!(
        "stop requested: {}",
        if watcher.stop_requested { "yes" } else { "no" }
    ));
    if watcher.generation > 0 {
        lines.push(format!("generation: {}", watcher.generation));
    }
    if !watcher.message.trim().is_empty() {
        lines.push(format!(
            "message: {}",
            bounded_text(watcher.message.trim(), MAX_CLOSE_READINESS_WARNING_CHARS)
        ));
    }
    if !watcher.error.trim().is_empty() {
        lines.push(format!(
            "error: {}",
            bounded_text(watcher.error.trim(), MAX_CLOSE_READINESS_WARNING_CHARS)
        ));
    }
    if status.eq_ignore_ascii_case("armed") {
        lines.push(
            "closing the backend would remove this in-process stop-at-schedule-boundary guard"
                .to_string(),
        );
    }
    lines
}
