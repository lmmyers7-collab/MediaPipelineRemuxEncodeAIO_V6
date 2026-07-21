use serde::Deserialize;
use std::{thread, time::Duration};

use crate::dialogs::shell_error;
use crate::http_helpers::{bounded_text, request_backend_json};
use crate::{ShellResult, MAX_CLOSE_READINESS_WARNINGS, MAX_CLOSE_READINESS_WARNING_CHARS};

// A just-started or briefly busy loopback server can reject one connection even
// though the managed backend is healthy. Retry only the transport request; an
// unsafe payload or an invalid payload is still handled immediately and never
// treated as safe by the shell.
const CLOSE_READINESS_REQUEST_ATTEMPTS: usize = 2;
const CLOSE_READINESS_RETRY_DELAY: Duration = Duration::from_millis(150);

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
    let mut response = None;
    let mut transport_error = None;
    for attempt in 0..CLOSE_READINESS_REQUEST_ATTEMPTS {
        match request_backend_json(
            backend_url,
            "GET",
            "/api/backend/close-readiness",
            token,
            "",
        ) {
            Ok(value) => {
                response = Some(value);
                break;
            }
            Err(error) => {
                transport_error = Some(error);
                if attempt + 1 < CLOSE_READINESS_REQUEST_ATTEMPTS {
                    thread::sleep(CLOSE_READINESS_RETRY_DELAY);
                }
            }
        }
    }
    let response = response.ok_or_else(|| {
        transport_error.expect("close-readiness retry loop records a transport error")
    })?;
    parse_close_readiness_response(&response)
}

pub(crate) fn parse_close_readiness_response(response: &str) -> ShellResult<CloseReadiness> {
    let readiness: CloseReadiness = serde_json::from_str(response)
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

#[cfg(test)]
mod tests {
    use super::{parse_close_readiness_response, request_close_readiness};
    use std::{
        io::{Read, Write},
        net::TcpListener,
        thread,
        time::Duration,
    };

    #[test]
    fn request_close_readiness_recovers_from_one_transient_transport_failure() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind test backend");
        let address = listener.local_addr().expect("test backend address");
        thread::spawn(move || {
            for response in [
                None,
                Some(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"schema_version\":\"desktop_close_readiness.v1\",\"safe_to_close\":true,\"state\":\"idle\",\"reason\":\"no active work\"}",
                ),
            ] {
                let (mut stream, _) = listener.accept().expect("accept test backend request");
                stream
                    .set_read_timeout(Some(Duration::from_secs(2)))
                    .expect("set test backend read timeout");
                let mut request = [0_u8; 4096];
                let _ = stream.read(&mut request);
                if let Some(response) = response {
                    stream
                        .write_all(response.as_bytes())
                        .expect("write test backend response");
                }
            }
        });

        let readiness = request_close_readiness(&format!("http://{address}"), "test-token")
            .expect("second close-readiness attempt should succeed");

        assert!(readiness.safe_to_close);
        assert_eq!(readiness.state, "idle");
    }

    #[test]
    fn malformed_string_close_readiness_boolean_is_never_treated_as_safe() {
        let error = parse_close_readiness_response(
            r#"{"schema_version":"desktop_close_readiness.v1","safe_to_close":"false","state":"processing","reason":"active work"}"#,
        )
        .expect_err("a string boolean must fail closed");

        assert!(error.to_string().contains("Close-readiness response was not JSON"));
    }

    #[test]
    fn missing_close_readiness_boolean_is_never_treated_as_safe() {
        let error = parse_close_readiness_response(
            r#"{"schema_version":"desktop_close_readiness.v1","state":"processing","reason":"active work"}"#,
        )
        .expect_err("missing safety authority must fail closed");

        assert!(error.to_string().contains("Close-readiness response was not JSON"));
    }
}
