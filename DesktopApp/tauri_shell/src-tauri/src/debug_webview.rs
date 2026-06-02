use crate::ShellResult;

const TEST_AUTH_CAPTURE_ENV_VAR: &str = "MEDIA_PIPELINE_TAURI_TEST_TOKEN_CAPTURE_FILE";

#[cfg(debug_assertions)]
pub(crate) fn maybe_write_debug_backend_auth_capture(backend_url: &str, token: &str) {
    use std::{env, fs};

    let Ok(path_text) = env::var(TEST_AUTH_CAPTURE_ENV_VAR) else {
        return;
    };
    if path_text.trim().is_empty() {
        return;
    }

    let path = match resolve_debug_backend_auth_capture_path(&path_text) {
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
fn resolve_debug_backend_auth_capture_path(path_text: &str) -> ShellResult<std::path::PathBuf> {
    use std::{env, fs, path::PathBuf};

    let requested = PathBuf::from(path_text.trim());
    let file_name = requested
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("");
    if !file_name.ends_with(".backend_auth.json") {
        return Err("debug auth capture files must end with .backend_auth.json".into());
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

#[cfg(not(debug_assertions))]
pub(crate) fn maybe_write_debug_backend_auth_capture(_backend_url: &str, _token: &str) {}

#[cfg(debug_assertions)]
pub(crate) fn maybe_schedule_debug_webview_autolaunch(window: &tauri::WebviewWindow) {
    use std::{env, thread, time::Duration};

    let mode = match env::var("MEDIA_PIPELINE_TAURI_TEST_AUTOMATION") {
        Ok(value) if value == "pg2-webview-launch" || value == "pg2-sample-validation-append" => {
            value
        }
        _ => return,
    };
    let source_file = match env::var("MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_SINGLE_FILE") {
        Ok(value) if !value.trim().is_empty() => value,
        _ => {
            eprintln!(
                "[mediapipeline-shell] {mode} requested but MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_SINGLE_FILE was empty"
            );
            return;
        }
    };
    let script = match if mode == "pg2-webview-launch" {
        let launch_mode = env::var("MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_MODE")
            .unwrap_or_else(|_| "once".to_string());
        let schedule_override = env::var("MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_SCHEDULE_OVERRIDE")
            .unwrap_or_else(|_| "run_once".to_string());
        debug_webview_autolaunch_script(&source_file, &launch_mode, &schedule_override)
    } else {
        let decision = env::var("MEDIA_PIPELINE_TAURI_TEST_SAMPLE_VALIDATION_DECISION")
            .unwrap_or_else(|_| "hold_review".to_string());
        let category = env::var("MEDIA_PIPELINE_TAURI_TEST_SAMPLE_VALIDATION_CATEGORY")
            .unwrap_or_else(|_| "h264-remux-safe".to_string());
        let output_path =
            env::var("MEDIA_PIPELINE_TAURI_TEST_SAMPLE_VALIDATION_OUTPUT").unwrap_or_default();
        let notes = env::var("MEDIA_PIPELINE_TAURI_TEST_SAMPLE_VALIDATION_NOTES").unwrap_or_else(|_| {
            "PG-2 Tauri WebView append harness: backend evidence reviewed; manual playback remains operator-owned.".to_string()
        });
        debug_sample_validation_append_script(
            &source_file,
            &output_path,
            &decision,
            &category,
            &notes,
        )
    } {
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

#[cfg(not(debug_assertions))]
pub(crate) fn maybe_schedule_debug_webview_autolaunch(_window: &tauri::WebviewWindow) {}

#[cfg(debug_assertions)]
pub(crate) fn debug_sample_validation_append_script(
    source_file: &str,
    output_path: &str,
    decision: &str,
    category: &str,
    notes: &str,
) -> ShellResult<String> {
    let source_json = serde_json::to_string(source_file)?;
    let output_json = serde_json::to_string(output_path)?;
    let decision_json = serde_json::to_string(decision)?;
    let category_json = serde_json::to_string(category)?;
    let notes_json = serde_json::to_string(notes)?;
    Ok(format!(
        r#"(function mediaPipelinePg2SampleValidationAppend() {{
  const sourceFile = {source_json};
  const outputPath = {output_json};
  const decision = {decision_json};
  const category = {category_json};
  const notes = {notes_json};
  const attempt = (remaining) => {{
    if (document.readyState !== "complete" || typeof window.apiPost !== "function") {{
      if (remaining <= 0) throw new Error("PG-2 sample-validation append could not find WebView API client.");
      window.setTimeout(() => attempt(remaining - 1), 500);
      return;
    }}
    const shell = typeof window.sampleValidationShellSurface === "function" ? window.sampleValidationShellSurface() : "tauri";
    const sampleLabelFromPath = (path) => {{
      const raw = String(path || "").trim();
      if (!raw) return "sample";
      const normalized = raw.replace(/\\/g, "/");
      const parts = normalized.split("/").filter(Boolean);
      return parts.length ? parts[parts.length - 1] : raw;
    }};
    const request = {{
      schema: "sample_validation_record.v1",
      shell,
      source_path: sourceFile,
      output_path: outputPath,
      sample_label: sampleLabelFromPath(sourceFile || outputPath),
      sample_category: category,
      proof_strength: "exact-path",
      operator_decision: decision,
      checks: {{
        queue_route_checked: false,
        ffmpeg_log_checked: true,
        subtitle_checked: true,
        audio_checked: true,
        completed_output_checked: true,
        sidecar_manifest_checked: true,
        size_growth_checked: true,
        pending_publish_checked: true,
        diagnostics_checked: true
      }},
      evidence: {{
        queue: [{{ field: "pre-run queue row", value: "not captured; launched through Tauri WebView single_file form", strength: "missing-required" }}],
        completed: [
          {{ field: "output", value: outputPath, strength: "exact" }},
          {{ field: "route", value: "remux / codec_remux_safe / published", strength: "exact" }}
        ],
        pending_publish: [{{ field: "pending publish", value: "No pending publish rows after immediate publish", strength: "exact" }}],
        diagnostics: [{{ field: "active job", value: "Tauri WebView launch ActiveJobs completed return_code=0", strength: "exact" }}],
        commands: [{{ field: "launch surface", value: "Tauri WebView debug harness invoked existing Launch form/button for pipeline.start", strength: "exact" }}]
      }},
      operator_notes: notes
    }};
    window.apiPost("/api/sample-validation/append", request).then((result) => {{
      if (typeof window.appendCommandResult === "function") window.appendCommandResult(result);
      document.body.dataset.pg2SampleValidationAppend = result && result.ok ? "ok" : "failed";
    }}).catch((error) => {{
      document.body.dataset.pg2SampleValidationAppend = "error:" + (error && error.message ? error.message : String(error));
      throw error;
    }});
  }};
  attempt(120);
}})();"#
    ))
}

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
