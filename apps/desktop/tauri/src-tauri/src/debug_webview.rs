#[cfg(debug_assertions)]
use crate::ShellResult;

#[cfg(debug_assertions)]
const TEST_AUTH_CAPTURE_ENV_VAR: &str = "MEDIA_PIPELINE_TAURI_TEST_TOKEN_CAPTURE_FILE";

#[cfg(debug_assertions)]
const TEST_NAVIGATION_DENIAL_ENV_VAR: &str = "MEDIA_PIPELINE_TAURI_TEST_NAVIGATION_DENIAL_FILE";

#[cfg(debug_assertions)]
static NAVIGATION_EVIDENCE_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

#[cfg(debug_assertions)]
pub(crate) fn maybe_write_debug_backend_auth_capture(backend_url: &str, token: &str) {
    use std::{env, fs};

    let Ok(path_text) = env::var(TEST_AUTH_CAPTURE_ENV_VAR) else {
        return;
    };
    if path_text.trim().is_empty() {
        return;
    }

    let path = match resolve_debug_capture_path(&path_text, ".backend_auth.json") {
        Ok(path) => path,
        Err(error) => {
            eprintln!("[mediapipeline-shell] test auth capture path rejected: {error}");
            return;
        }
    };

    let payload = serde_json::json!({
        "schema_version": "mediapipeline_tauri_test_auth_capture.v1",
        "url": backend_url,
        "token": token,
    });
    let body = match serde_json::to_string_pretty(&payload) {
        Ok(value) => value,
        Err(error) => {
            eprintln!("[mediapipeline-shell] test auth capture serialization failed: {error}");
            return;
        }
    };
    if let Err(error) = fs::write(path, format!("{body}\n")) {
        eprintln!("[mediapipeline-shell] test auth capture write failed: {error}");
    }
}

#[cfg(debug_assertions)]
fn resolve_debug_capture_path(
    path_text: &str,
    required_suffix: &str,
) -> ShellResult<std::path::PathBuf> {
    use std::{env, fs, path::PathBuf};

    let requested = PathBuf::from(path_text.trim());
    let file_name = requested
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("");
    if !file_name.ends_with(required_suffix) {
        return Err(format!("debug capture files must end with {required_suffix}").into());
    }

    let temp_root = env::temp_dir()
        .canonicalize()
        .unwrap_or_else(|_| env::temp_dir());
    let absolute_path = if requested.is_absolute() {
        requested
    } else {
        temp_root.join(requested)
    };
    let parent = absolute_path
        .parent()
        .ok_or("debug auth capture path did not have a parent directory")?;
    fs::create_dir_all(parent)?;
    let canonical_parent = parent.canonicalize()?;
    if !canonical_parent.starts_with(&temp_root) {
        return Err("debug auth capture path must stay under the system temp directory".into());
    }
    Ok(absolute_path)
}

#[cfg(debug_assertions)]
pub(crate) fn maybe_record_debug_navigation_denial(window_label: &str, candidate: &url::Url) {
    use std::{env, fs::OpenOptions, io::Write};

    let Ok(path_text) = env::var(TEST_NAVIGATION_DENIAL_ENV_VAR) else {
        return;
    };
    if path_text.trim().is_empty() {
        return;
    }
    let path = match resolve_debug_capture_path(&path_text, ".navigation_denials.jsonl") {
        Ok(path) => path,
        Err(error) => {
            eprintln!("[mediapipeline-shell] test navigation evidence path rejected: {error}");
            return;
        }
    };
    let payload = serde_json::json!({
        "schema_version": "mediapipeline_tauri_navigation_denial.v1",
        "window_label": window_label,
        "candidate_origin": candidate.origin().ascii_serialization(),
    });
    let Ok(line) = serde_json::to_string(&payload) else {
        return;
    };
    let Ok(_guard) = NAVIGATION_EVIDENCE_LOCK.lock() else {
        return;
    };
    match OpenOptions::new().create(true).append(true).open(path) {
        Ok(mut file) => {
            if let Err(error) = writeln!(file, "{line}") {
                eprintln!("[mediapipeline-shell] test navigation evidence write failed: {error}");
            }
        }
        Err(error) => {
            eprintln!("[mediapipeline-shell] test navigation evidence open failed: {error}");
        }
    }
}

#[cfg(not(debug_assertions))]
pub(crate) fn maybe_record_debug_navigation_denial(_window_label: &str, _candidate: &url::Url) {}

#[cfg(not(debug_assertions))]
pub(crate) fn maybe_write_debug_backend_auth_capture(_backend_url: &str, _token: &str) {}

#[cfg(debug_assertions)]
pub(crate) fn maybe_schedule_debug_webview_autolaunch(window: &tauri::WebviewWindow) {
    use std::{env, thread, time::Duration};

    let Ok(mode) = env::var("MEDIA_PIPELINE_TAURI_TEST_AUTOMATION") else {
        return;
    };
    if mode == "origin-confinement-probe" {
        schedule_debug_origin_confinement_probe(window);
        return;
    }
    if mode != "pg2-webview-launch" {
        return;
    }
    let source_file = match env::var("MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_SINGLE_FILE") {
        Ok(value) if !value.trim().is_empty() => value,
        _ => {
            eprintln!(
                "[mediapipeline-shell] {mode} requested but MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_SINGLE_FILE was empty"
            );
            return;
        }
    };
    let launch_mode = env::var("MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_MODE")
        .unwrap_or_else(|_| "once".to_string());
    let schedule_override = env::var("MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_SCHEDULE_OVERRIDE")
        .unwrap_or_else(|_| "run_once".to_string());
    let script =
        match debug_webview_autolaunch_script(&source_file, &launch_mode, &schedule_override) {
            Ok(script) => script,
            Err(error) => {
                eprintln!("[mediapipeline-shell] could not build debug autolaunch script: {error}");
                return;
            }
        };
    let window = window.clone();
    thread::spawn(move || {
        thread::sleep(Duration::from_millis(1500));
        if let Err(error) = window.eval(&script) {
            eprintln!("[mediapipeline-shell] debug WebView autolaunch eval failed: {error}");
        }
    });
}

#[cfg(debug_assertions)]
fn schedule_debug_origin_confinement_probe(window: &tauri::WebviewWindow) {
    use std::{env, thread, time::Duration};
    use tauri::Manager;

    let denied_url = match env::var("MEDIA_PIPELINE_TAURI_TEST_DENIED_NAVIGATION_URL") {
        Ok(value) if url::Url::parse(&value).is_ok() => value,
        _ => {
            eprintln!("[mediapipeline-shell] origin probe denied-navigation URL was invalid");
            return;
        }
    };
    let Ok(denied_url_json) = serde_json::to_string(&denied_url) else {
        return;
    };
    let app = window.app_handle().clone();
    let main_window = window.clone();
    thread::spawn(move || {
        thread::sleep(Duration::from_millis(1500));
        if let Err(error) = crate::open_pipeline_log_window(app.clone()) {
            eprintln!("[mediapipeline-shell] origin probe could not open Pipeline Log: {error}");
            return;
        }
        thread::sleep(Duration::from_millis(500));
        let assign_script = format!("window.location.assign({denied_url_json});");
        if let Err(error) = main_window.eval(&assign_script) {
            eprintln!("[mediapipeline-shell] origin probe main navigation eval failed: {error}");
        }
        let Some(pipeline_log_window) = app.get_webview_window("pipeline-log") else {
            eprintln!("[mediapipeline-shell] origin probe Pipeline Log window was unavailable");
            return;
        };
        let replace_script = format!("window.location.replace({denied_url_json});");
        if let Err(error) = pipeline_log_window.eval(&replace_script) {
            eprintln!(
                "[mediapipeline-shell] origin probe Pipeline Log navigation eval failed: {error}"
            );
        }
    });
}

#[cfg(not(debug_assertions))]
pub(crate) fn maybe_schedule_debug_webview_autolaunch(_window: &tauri::WebviewWindow) {}

#[cfg(debug_assertions)]
fn debug_webview_autolaunch_script(
    source_file: &str,
    launch_mode: &str,
    schedule_override: &str,
) -> ShellResult<String> {
    let source_json = serde_json::to_string(source_file)?;
    let mode_json = serde_json::to_string(launch_mode)?;
    let schedule_json = serde_json::to_string(schedule_override)?;
    Ok(format!(
        r#"(function mediaPipelinePg2Autolaunch() {{
  const sourceFile = {source_json};
  const launchMode = {mode_json};
  const scheduleOverride = {schedule_json};
  const setField = (id, value) => {{
    const node = document.getElementById(id);
    if (!node) throw new Error("PG-2 autolaunch missing field: " + id);
    node.value = value;
    node.dispatchEvent(new Event("input", {{ bubbles: true }}));
    node.dispatchEvent(new Event("change", {{ bubbles: true }}));
  }};
  const attempt = (remaining) => {{
    const button = document.getElementById("pipeline-start-button");
    if (!button || typeof window.showPage !== "function") {{
      if (remaining <= 0) throw new Error("PG-2 autolaunch could not find Launch controls.");
      window.setTimeout(() => attempt(remaining - 1), 500);
      return;
    }}
    window.showPage("launch");
    setField("pipeline-start-mode", launchMode);
    setField("pipeline-start-single-file", sourceFile);
    setField("pipeline-start-schedule-override", scheduleOverride);
    const originalConfirm = window.confirm;
    window.confirm = () => true;
    button.click();
    window.setTimeout(() => {{ window.confirm = originalConfirm; }}, 3000);
  }};
  attempt(120);
}})();"#
    ))
}
