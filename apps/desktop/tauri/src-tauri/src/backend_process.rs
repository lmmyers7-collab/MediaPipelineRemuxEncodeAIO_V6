use serde::Deserialize;
use std::{
    error::Error,
    ffi::OsString,
    io::{BufRead, BufReader, Read},
    path::Path,
    process::{Child, Command, Stdio},
    sync::{mpsc, mpsc::RecvTimeoutError, Mutex},
    thread,
    time::{Duration, Instant},
};
use tauri::Manager;

use crate::backend_contract::{
    validate_backend_contract, validate_backend_health, validate_backend_web_ui,
};
use crate::close_readiness::{close_readiness_warning_detail, request_close_readiness};
use crate::dialogs::{
    confirm_close_dialog, display_bounded_path, project_root_from_desktop_root, resolve_python,
    shell_error,
};
use crate::http_helpers::{bounded_text, request_backend_json};
use crate::ShellResult;

pub(crate) const MAX_BOOTSTRAP_STDOUT_LINES: usize = 5;
pub(crate) const MAX_BOOTSTRAP_STDOUT_CHARS: usize = 500;
const FORCE_CLOSE_RECOVERY_WARNING: &str = "The backend will be asked to stop app-owned pipeline work before shutdown. Any interrupted work may require recovery from ActiveJobs, run logs, or the completed/pending manifests.";

#[derive(Debug, Deserialize)]
pub(crate) struct BackendBootstrap {
    pub(crate) schema_version: String,
    pub(crate) url: String,
    pub(crate) token: String,
}

pub(crate) struct BackendProcess {
    child: Mutex<Option<Child>>,
    url: String,
    token: String,
    startup_warnings: Vec<String>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum BackendProcessExit {
    Running,
    Exited(Option<i32>),
    NoChild,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum BackendShutdownMode {
    SafeOnly,
    ConfirmedForceActiveWork,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum BackendShutdownOutcome {
    Requested,
    Blocked,
    Failed,
}

#[derive(Debug, Deserialize)]
struct BackendShutdownResponse {
    schema_version: String,
    ok: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum CloseRequestDecision {
    AllowSafe,
    AllowConfirmedForce,
    Deny,
}

impl BackendProcess {
    pub(crate) fn url(&self) -> &str {
        &self.url
    }

    pub(crate) fn token(&self) -> &str {
        &self.token
    }

    pub(crate) fn startup_warnings(&self) -> &[String] {
        &self.startup_warnings
    }

    pub(crate) fn health_check(&self) -> ShellResult<()> {
        validate_backend_health(&self.url, &self.token)
    }

    pub(crate) fn try_take_exited(&self) -> ShellResult<BackendProcessExit> {
        let mut guard = self
            .child
            .lock()
            .map_err(|_| shell_error("Backend process lock was poisoned."))?;
        let Some(child) = guard.as_mut() else {
            return Ok(BackendProcessExit::NoChild);
        };
        match child.try_wait()? {
            Some(status) => {
                let code = status.code();
                let _ = guard.take();
                Ok(BackendProcessExit::Exited(code))
            }
            None => Ok(BackendProcessExit::Running),
        }
    }

    pub(crate) fn shutdown(&self, mode: BackendShutdownMode) -> BackendShutdownOutcome {
        if let Ok(mut guard) = self.child.lock() {
            if guard.is_none() {
                return BackendShutdownOutcome::Requested;
            }
            let shutdown_request_failed =
                match request_backend_shutdown(&self.url, &self.token, mode) {
                    Ok(BackendShutdownOutcome::Requested) => false,
                    Ok(BackendShutdownOutcome::Failed) => {
                        eprintln!("[mediapipeline-shell] backend did not acknowledge shutdown");
                        return BackendShutdownOutcome::Failed;
                    }
                    Ok(BackendShutdownOutcome::Blocked) => {
                        eprintln!(
                        "[mediapipeline-shell] backend shutdown request blocked by close-readiness"
                    );
                        return BackendShutdownOutcome::Blocked;
                    }
                    Err(error) => {
                        eprintln!("[mediapipeline-shell] backend shutdown request failed: {error}");
                        true
                    }
                };
            if shutdown_request_failed {
                let Some(child) = guard.as_mut() else {
                    return BackendShutdownOutcome::Requested;
                };
                if wait_for_child_exit(child, Duration::from_secs(3)) {
                    let _ = guard.take();
                    return BackendShutdownOutcome::Requested;
                }
                // Never turn an unavailable backend into permission to kill
                // its tree, even after a native force-close confirmation.
                return BackendShutdownOutcome::Failed;
            }
            let Some(mut child) = guard.take() else {
                return BackendShutdownOutcome::Requested;
            };
            drop(guard);
            if wait_for_child_exit(&mut child, Duration::from_secs(3)) {
                return BackendShutdownOutcome::Requested;
            }
            eprintln!(
                "[mediapipeline-shell] backend did not exit within grace period; terminating process tree"
            );
            terminate_child(&mut child);
            return BackendShutdownOutcome::Requested;
        }
        BackendShutdownOutcome::Failed
    }
}

impl Drop for BackendProcess {
    fn drop(&mut self) {
        self.shutdown(BackendShutdownMode::SafeOnly);
    }
}

pub(crate) fn shutdown_backend_state(
    manager: &impl Manager<tauri::Wry>,
    mode: BackendShutdownMode,
) -> BackendShutdownOutcome {
    if let Some(backend) = manager.try_state::<BackendProcess>() {
        backend.shutdown(mode)
    } else {
        BackendShutdownOutcome::Requested
    }
}

pub(crate) fn close_request_decision(manager: &impl Manager<tauri::Wry>) -> CloseRequestDecision {
    let Some(backend) = manager.try_state::<BackendProcess>() else {
        return CloseRequestDecision::AllowSafe;
    };
    match request_close_readiness(&backend.url, &backend.token) {
        Ok(readiness) if readiness.safe_to_close => CloseRequestDecision::AllowSafe,
        Ok(readiness) => {
            let detail = close_readiness_warning_detail(&readiness);
            if confirm_close_dialog(&format!(
                "{detail}\n\nClose the MediaPipeline shell anyway?\n\n{FORCE_CLOSE_RECOVERY_WARNING}"
            )) {
                CloseRequestDecision::AllowConfirmedForce
            } else {
                CloseRequestDecision::Deny
            }
        }
        Err(error) => {
            if confirm_close_dialog(&format!(
                "Close readiness could not be verified: {error}\n\nThis is not treated as safe. Close the MediaPipeline shell anyway?\n\n{FORCE_CLOSE_RECOVERY_WARNING}"
            )) {
                CloseRequestDecision::AllowConfirmedForce
            } else {
                CloseRequestDecision::Deny
            }
        }
    }
}

pub(crate) fn start_backend(desktop_root: &Path) -> ShellResult<BackendProcess> {
    let python = resolve_python(desktop_root)?;
    let src_root = project_root_from_desktop_root(desktop_root).join("src");
    let python_path = python_path_with_src_root(&src_root);
    let mut child = Command::new(&python)
        .arg("-m")
        .arg("mediapipeline.desktop.local_api_main")
        .arg("--app-root")
        .arg(desktop_root)
        .arg("--shell-surface")
        .arg("tauri")
        .arg("--emit-startup-progress")
        .current_dir(desktop_root)
        .env("PYTHONPATH", python_path)
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env(
            "MEDIAPIPELINE_PRODUCTIZED_APP",
            if cfg!(debug_assertions) { "0" } else { "1" },
        )
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| {
            shell_error(format!(
                "Failed to start Python backend '{}': {error}",
                python.display()
            ))
        })?;

    let stdout = match child.stdout.take() {
        Some(stdout) => stdout,
        None => {
            terminate_child(&mut child);
            return Err(shell_error(format!(
                "Backend stdout was not captured after starting Python backend '{}'.",
                display_bounded_path(&python)
            )));
        }
    };
    let stderr = match child.stderr.take() {
        Some(stderr) => stderr,
        None => {
            terminate_child(&mut child);
            return Err(shell_error(format!(
                "Backend stderr was not captured after starting Python backend '{}'.",
                display_bounded_path(&python)
            )));
        }
    };
    let rx = spawn_backend_stdout_reader(stdout);
    spawn_pipe_drain(stderr, "stderr");

    let bootstrap = match read_backend_bootstrap(&rx, Duration::from_secs(20)) {
        Ok(bootstrap) => bootstrap,
        Err(error) => {
            terminate_child(&mut child);
            return Err(error);
        }
    };
    if let Err(error) = validate_backend_health(&bootstrap.url, &bootstrap.token) {
        terminate_child(&mut child);
        return Err(shell_error(format!(
            "Backend health validation failed for '{}': {error}",
            bootstrap.url
        )));
    }
    if let Err(error) = validate_backend_contract(&bootstrap.url, &bootstrap.token) {
        terminate_child(&mut child);
        return Err(shell_error(format!(
            "Backend route contract validation failed for '{}': {error}",
            bootstrap.url
        )));
    }
    let mut startup_warnings = Vec::new();
    if let Err(error) = validate_backend_web_ui(&bootstrap.url, &bootstrap.token) {
        let detail = redact_validation_detail(&error.to_string(), &bootstrap.token);
        if web_ui_validation_error_is_fatal(&detail) {
            terminate_child(&mut child);
            return Err(shell_error(format!(
                "Backend WebView asset validation failed for '{}': {detail}",
                bootstrap.url
            )));
        }
        let warning = format!(
            "Backend WebView asset validation warning for '{}': {}",
            bootstrap.url,
            bounded_text(&detail, 700)
        );
        eprintln!("[mediapipeline-shell] {warning}");
        startup_warnings.push(warning);
    }
    Ok(BackendProcess {
        child: Mutex::new(Some(child)),
        url: bootstrap.url,
        token: bootstrap.token,
        startup_warnings,
    })
}

fn python_path_with_src_root(src_root: &Path) -> OsString {
    let mut python_path = OsString::from(src_root.as_os_str());
    if let Some(existing) = std::env::var_os("PYTHONPATH") {
        if !existing.is_empty() {
            python_path.push(if cfg!(windows) { ";" } else { ":" });
            python_path.push(existing);
        }
    }
    python_path
}

pub(crate) fn web_ui_validation_error_is_fatal(_detail: &str) -> bool {
    // Backend-served WebView validation checks authority-boundary and guardrail
    // fragments. Any failure means the shell cannot safely trust the UI surface.
    true
}

fn redact_validation_detail(detail: &str, token: &str) -> String {
    let redacted = redact_bootstrap_stdout(detail);
    if token.trim().is_empty() {
        redacted
    } else {
        redacted.replace(token, "[redacted]")
    }
}

pub(crate) fn read_backend_bootstrap(
    rx: &mpsc::Receiver<std::io::Result<String>>,
    timeout: Duration,
) -> ShellResult<BackendBootstrap> {
    let started = Instant::now();
    let mut stdout_context: Vec<String> = Vec::new();
    loop {
        let elapsed = started.elapsed();
        if elapsed >= timeout {
            return Err(bootstrap_error(
                "Timed out waiting for backend bootstrap payload.",
                &stdout_context,
            ));
        }
        let remaining = timeout.saturating_sub(elapsed);
        let line = match rx.recv_timeout(remaining) {
            Ok(Ok(line)) => line,
            Ok(Err(error)) => {
                return Err(bootstrap_error(
                    format!("Failed reading backend bootstrap payload: {error}"),
                    &stdout_context,
                ));
            }
            Err(RecvTimeoutError::Timeout) => {
                return Err(bootstrap_error(
                    "Timed out waiting for backend bootstrap payload.",
                    &stdout_context,
                ));
            }
            Err(RecvTimeoutError::Disconnected) => {
                return Err(bootstrap_error(
                    "Backend stdout closed before bootstrap payload was received.",
                    &stdout_context,
                ));
            }
        };
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        match serde_json::from_str::<BackendBootstrap>(trimmed) {
            Ok(bootstrap) => {
                if bootstrap.schema_version != "desktop_local_api_bootstrap.v1" {
                    return Err(shell_error(format!(
                        "Unexpected backend bootstrap schema: {}",
                        bootstrap.schema_version
                    )));
                }
                return Ok(bootstrap);
            }
            Err(_) => {
                let redacted_bootstrap_stdout = redact_bootstrap_stdout(trimmed);
                push_bootstrap_stdout_context(&mut stdout_context, trimmed);
                eprintln!(
                    "[mediapipeline-backend:stdout-before-bootstrap] {}",
                    bounded_text(&redacted_bootstrap_stdout, MAX_BOOTSTRAP_STDOUT_CHARS)
                );
            }
        }
    }
}

fn spawn_backend_stdout_reader(
    stdout: impl Read + Send + 'static,
) -> mpsc::Receiver<std::io::Result<String>> {
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            match line {
                Ok(text) => {
                    if tx.send(Ok(text.clone())).is_err() {
                        let redacted = redact_bootstrap_stdout(&text);
                        eprintln!("[mediapipeline-backend:stdout] {redacted}");
                    }
                }
                Err(error) => {
                    let _ = tx.send(Err(error));
                    break;
                }
            }
        }
    });
    rx
}

fn spawn_pipe_drain(reader: impl Read + Send + 'static, stream_name: &'static str) {
    thread::spawn(move || {
        let reader = BufReader::new(reader);
        for line in reader.lines() {
            match line {
                Ok(text) => {
                    let redacted = redact_bootstrap_stdout(&text);
                    eprintln!("[mediapipeline-backend:{stream_name}] {redacted}");
                }
                Err(_) => break,
            }
        }
    });
}

fn terminate_child(child: &mut Child) {
    terminate_process_tree(child);
    if let Err(error) = child.wait() {
        eprintln!(
            "[mediapipeline-shell] backend process wait after tree termination failed: {error}"
        );
    }
}

#[cfg(windows)]
fn terminate_process_tree(child: &mut Child) {
    let pid = child.id().to_string();
    let status = Command::new("taskkill")
        .args(["/PID", &pid, "/T", "/F"])
        .status();
    match status {
        Ok(status) if status.success() => {}
        Ok(status) => {
            eprintln!("[mediapipeline-shell] taskkill /T failed with status {status}; falling back to direct kill");
            terminate_process_direct(child);
        }
        Err(error) => {
            eprintln!(
                "[mediapipeline-shell] taskkill /T failed: {error}; falling back to direct kill"
            );
            terminate_process_direct(child);
        }
    }
}

#[cfg(not(windows))]
fn terminate_process_tree(child: &mut Child) {
    terminate_process_direct(child);
}

fn terminate_process_direct(child: &mut Child) {
    if let Err(error) = child.kill() {
        eprintln!("[mediapipeline-shell] backend process kill failed: {error}");
    }
}

fn wait_for_child_exit(child: &mut Child, timeout: Duration) -> bool {
    let started = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_status)) => return true,
            Ok(None) => {
                if started.elapsed() >= timeout {
                    return false;
                }
                thread::sleep(Duration::from_millis(100));
            }
            Err(_) => return true,
        }
    }
}

fn backend_shutdown_request_body(mode: BackendShutdownMode) -> &'static str {
    match mode {
        BackendShutdownMode::SafeOnly => r#"{"reason":"tauri-shell-exit"}"#,
        BackendShutdownMode::ConfirmedForceActiveWork => {
            r#"{"reason":"tauri-shell-close","force_active_work_shutdown":true}"#
        }
    }
}

fn parse_backend_shutdown_outcome(body: &str) -> ShellResult<BackendShutdownOutcome> {
    let response: BackendShutdownResponse = serde_json::from_str(body)
        .map_err(|error| shell_error(format!("Backend shutdown response was not JSON: {error}")))?;
    if response.schema_version != "desktop_command_result.v1" {
        return Err(shell_error(format!(
            "Unexpected backend shutdown schema: {}",
            response.schema_version
        )));
    }
    if response.ok {
        Ok(BackendShutdownOutcome::Requested)
    } else {
        Ok(BackendShutdownOutcome::Blocked)
    }
}

fn request_backend_shutdown(
    backend_url: &str,
    token: &str,
    mode: BackendShutdownMode,
) -> ShellResult<BackendShutdownOutcome> {
    let response = request_backend_json(
        backend_url,
        "POST",
        "/api/backend/shutdown",
        token,
        backend_shutdown_request_body(mode),
    )?;
    parse_backend_shutdown_outcome(&response)
}

pub(crate) fn redact_bootstrap_stdout(value: &str) -> String {
    let mut redacted = value.to_string();
    for field in [
        "token",
        "auth_token",
        "bearer_token",
        "api_token",
        "ApiToken",
        "Token",
        "WorkerAuthToken",
    ] {
        redacted = redact_json_string_field(&redacted, field);
    }
    redacted = redact_bearer_marker(&redacted, "Bearer ");
    redacted = redact_bearer_marker(&redacted, "bearer ");
    redacted = redact_bearer_marker(&redacted, "BEARER ");
    for marker in [
        "token=",
        "token:",
        "auth_token=",
        "api_token=",
        "WorkerAuthToken=",
        "password=",
        "credential=",
        "config=",
        "config:",
        "LocalBase=",
        "local_base=",
    ] {
        redacted = redact_assignment_marker(&redacted, marker);
    }
    redacted = redact_windows_user_paths(&redacted);
    redact_unc_paths(&redacted)
}

fn redact_windows_user_paths(value: &str) -> String {
    let lower = value.to_ascii_lowercase();
    let bytes = value.as_bytes();
    let mut output = String::with_capacity(value.len());
    let mut cursor = 0;
    while let Some(relative_start) = lower[cursor..].find(":\\users\\") {
        let marker_start = cursor + relative_start;
        let path_start = marker_start.saturating_sub(1);
        let path_end = path_value_end(bytes, marker_start + 8);
        output.push_str(&value[cursor..path_start]);
        output.push_str("[redacted-path]");
        cursor = path_end;
    }
    output.push_str(&value[cursor..]);
    output
}

fn redact_unc_paths(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut output = String::with_capacity(value.len());
    let mut cursor = 0;
    while let Some(relative_start) = value[cursor..].find("\\\\") {
        let path_start = cursor + relative_start;
        let path_end = path_value_end(bytes, path_start + 2);
        output.push_str(&value[cursor..path_start]);
        output.push_str("[redacted-path]");
        cursor = path_end;
    }
    output.push_str(&value[cursor..]);
    output
}

fn path_value_end(bytes: &[u8], mut index: usize) -> usize {
    while index < bytes.len()
        && !bytes[index].is_ascii_whitespace()
        && !matches!(bytes[index], b'\"' | b'\'' | b',' | b'}' | b']' | b';')
    {
        index += 1;
    }
    index
}

fn redact_json_string_field(value: &str, field: &str) -> String {
    let needle = format!("\"{field}\"");
    let bytes = value.as_bytes();
    let mut output = String::with_capacity(value.len());
    let mut cursor = 0;

    while let Some(relative_start) = value[cursor..].find(&needle) {
        let field_start = cursor + relative_start;
        let after_field = field_start + needle.len();
        output.push_str(&value[cursor..after_field]);

        let colon_index = skip_ascii_whitespace(bytes, after_field);
        if colon_index >= bytes.len() || bytes[colon_index] != b':' {
            cursor = after_field;
            continue;
        }
        output.push_str(&value[after_field..colon_index + 1]);

        let quote_index = skip_ascii_whitespace(bytes, colon_index + 1);
        output.push_str(&value[colon_index + 1..quote_index]);
        if quote_index >= bytes.len() || !matches!(bytes[quote_index], b'"' | b'\'') {
            cursor = quote_index;
            continue;
        }

        let quote = bytes[quote_index];
        output.push(quote as char);
        let value_start = quote_index + 1;
        output.push_str("[redacted]");
        if let Some(closing_quote) = find_closing_quote(bytes, value_start, quote) {
            output.push(quote as char);
            cursor = closing_quote + 1;
        } else {
            cursor = bytes.len();
        }
    }

    output.push_str(&value[cursor..]);
    output
}

fn redact_bearer_marker(value: &str, marker: &str) -> String {
    let bytes = value.as_bytes();
    let mut output = String::with_capacity(value.len());
    let mut cursor = 0;

    while let Some(relative_start) = value[cursor..].find(marker) {
        let marker_start = cursor + relative_start;
        let value_start = marker_start + marker.len();
        let mut value_end = value_start;
        while value_end < bytes.len()
            && !bytes[value_end].is_ascii_whitespace()
            && !matches!(bytes[value_end], b'"' | b'\'' | b',' | b'}' | b']' | b';')
        {
            value_end += 1;
        }

        output.push_str(&value[cursor..value_start]);
        if value_end > value_start {
            output.push_str("[redacted]");
        }
        cursor = value_end;
    }

    output.push_str(&value[cursor..]);
    output
}

fn redact_assignment_marker(value: &str, marker: &str) -> String {
    let bytes = value.as_bytes();
    let mut output = String::with_capacity(value.len());
    let mut cursor = 0;
    while let Some(relative_start) = value[cursor..].find(marker) {
        let marker_start = cursor + relative_start;
        let value_start = marker_start + marker.len();
        let value_end = path_value_end(bytes, value_start);
        output.push_str(&value[cursor..value_start]);
        if value_end > value_start {
            output.push_str("[redacted]");
        }
        cursor = value_end;
    }
    output.push_str(&value[cursor..]);
    output
}

fn skip_ascii_whitespace(bytes: &[u8], mut index: usize) -> usize {
    while index < bytes.len() && bytes[index].is_ascii_whitespace() {
        index += 1;
    }
    index
}

fn find_closing_quote(bytes: &[u8], mut index: usize, quote: u8) -> Option<usize> {
    let mut escaped = false;
    while index < bytes.len() {
        let byte = bytes[index];
        if escaped {
            escaped = false;
        } else if byte == b'\\' {
            escaped = true;
        } else if byte == quote {
            return Some(index);
        }
        index += 1;
    }
    None
}

pub(crate) fn push_bootstrap_stdout_context(lines: &mut Vec<String>, value: &str) {
    if lines.len() < MAX_BOOTSTRAP_STDOUT_LINES {
        lines.push(bounded_text(
            &redact_bootstrap_stdout(value),
            MAX_BOOTSTRAP_STDOUT_CHARS,
        ));
    }
}

pub(crate) fn bootstrap_error(
    message: impl Into<String>,
    stdout_context: &[String],
) -> Box<dyn Error> {
    let mut detail = message.into();
    if !stdout_context.is_empty() {
        detail.push_str(" Recent stdout before bootstrap:");
        for line in stdout_context {
            detail.push_str("\n- ");
            detail.push_str(line);
        }
    }
    shell_error(detail)
}

#[cfg(test)]
#[path = "backend_process/tests.rs"]
mod tests;
