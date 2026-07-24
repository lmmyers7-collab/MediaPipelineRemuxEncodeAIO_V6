use std::error::Error;
#[cfg(test)]
use std::{
    path::{Path, PathBuf},
    time::Duration,
};
use tauri::{AppHandle, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent};

mod backend_contract;
mod backend_lifecycle_monitor;
mod backend_process;
mod close_readiness;
mod debug_webview;
mod dialogs;
mod http_helpers;
mod single_instance_guard;
mod updater_controller;
mod webview_origin;

#[cfg(test)]
use backend_contract::{
    format_list_preview, format_route_sample, validate_backend_contract, validate_backend_health,
    validate_backend_web_ui, validate_lifecycle_reconciliation_route, BackendRoute,
    REQUIRED_LIFECYCLE_RECONCILIATION_ROUTES,
};
use backend_lifecycle_monitor::start_backend_lifecycle_monitor;
#[cfg(test)]
use backend_process::{
    bootstrap_error, isolated_python_module_bootstrap, push_bootstrap_stdout_context,
    redact_bootstrap_stdout, web_ui_validation_error_is_fatal, MAX_BOOTSTRAP_STDOUT_CHARS,
    MAX_BOOTSTRAP_STDOUT_LINES,
};
use backend_process::{
    close_request_decision, shutdown_backend_state, start_backend, BackendProcess,
    BackendShutdownMode, BackendShutdownOutcome, CloseRequestDecision,
};
#[cfg(test)]
use close_readiness::{
    close_readiness_warning_detail, close_readiness_watcher_lines, request_close_readiness,
    CloseReadiness, ContinuousWatcher,
};
use debug_webview::{
    maybe_record_debug_navigation_denial, maybe_schedule_debug_webview_autolaunch,
    maybe_write_debug_backend_auth_capture,
};
use dialogs::resolve_desktop_root;
#[cfg(test)]
use dialogs::{
    desktop_root_candidates_from_exe_dir, format_path_candidates, project_root_from_desktop_root,
    resolve_python_for_mode,
};
use http_helpers::validate_loopback_backend_url;
#[cfg(test)]
use http_helpers::{read_backend_response_capped, request_backend_json};
use single_instance_guard::acquire_single_instance_guard;
use updater_controller::schedule_native_update_check;
use webview_origin::{navigation_matches_webview_origin, normalized_webview_origin};

type ShellResult<T> = Result<T, Box<dyn Error>>;
const MAX_BACKEND_RESPONSE_BYTES: usize = 16 * 1024 * 1024;
const MAX_STARTUP_VALIDATION_WARNINGS: usize = 4;
const MAX_STARTUP_VALIDATION_WARNING_CHARS: usize = 280;
const MAX_CLOSE_READINESS_WARNINGS: usize = 5;
const MAX_CLOSE_READINESS_WARNING_CHARS: usize = 240;
const MAX_OPERATOR_PATH_CHARS: usize = 320;
const PIPELINE_LOG_WINDOW_LABEL: &str = "pipeline-log";
const PIPELINE_LOG_WINDOW_PATH: &str = "/assets/pipelineLogWindow.html";

fn pipeline_log_window_url(backend_url: &str) -> ShellResult<url::Url> {
    let mut url = validate_loopback_backend_url(backend_url)?;
    url.set_path(PIPELINE_LOG_WINDOW_PATH);
    url.set_query(Some("surface=pipeline-log"));
    Ok(url)
}

#[tauri::command]
fn open_pipeline_log_window(app: AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window(PIPELINE_LOG_WINDOW_LABEL) {
        window
            .show()
            .map_err(|error| format!("Could not show Pipeline Log window: {error}"))?;
        window
            .unminimize()
            .map_err(|error| format!("Could not unminimize Pipeline Log window: {error}"))?;
        window
            .set_focus()
            .map_err(|error| format!("Could not focus Pipeline Log window: {error}"))?;
        return Ok(());
    }

    let (backend_url, token, startup_warnings) = {
        let backend = app
            .try_state::<BackendProcess>()
            .ok_or_else(|| "Backend state is not available yet.".to_string())?;
        (
            backend.url().to_string(),
            backend.token().to_string(),
            backend.startup_warnings().to_vec(),
        )
    };

    let url = pipeline_log_window_url(&backend_url)
        .map_err(|error| format!("Could not build Pipeline Log window URL: {error}"))?;
    let allowed_origin = normalized_webview_origin(&url);
    let navigation_origin = allowed_origin.clone();
    WebviewWindowBuilder::new(&app, PIPELINE_LOG_WINDOW_LABEL, WebviewUrl::External(url))
        .initialization_script(tauri_bootstrap_initialization_script(
            &token,
            &startup_warnings,
            &allowed_origin,
        ))
        .on_navigation(move |candidate| {
            let allowed = navigation_matches_webview_origin(candidate, &navigation_origin);
            if !allowed {
                maybe_record_debug_navigation_denial(PIPELINE_LOG_WINDOW_LABEL, candidate);
            }
            allowed
        })
        .title("Pipeline Log")
        .inner_size(980.0, 680.0)
        .min_inner_size(720.0, 420.0)
        .build()
        .map_err(|error| format!("Could not open Pipeline Log window: {error}"))?;
    Ok(())
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![open_pipeline_log_window])
        .setup(|app| {
            eprintln!("[mediapipeline-shell] setup: acquiring single-instance guard");
            let single_instance_guard = acquire_single_instance_guard()?;
            app.manage(single_instance_guard);
            eprintln!("[mediapipeline-shell] setup: resolving desktop root");
            let desktop_root = resolve_desktop_root()?;
            eprintln!(
                "[mediapipeline-shell] setup: starting backend for '{}'",
                desktop_root.display()
            );
            let backend = start_backend(&desktop_root)?;
            eprintln!(
                "[mediapipeline-shell] setup: backend listening at '{}'",
                backend.url()
            );
            maybe_write_debug_backend_auth_capture(backend.url(), backend.token());
            let url = validate_loopback_backend_url(backend.url())?;
            let allowed_origin = normalized_webview_origin(&url);
            let initialization_script = tauri_bootstrap_initialization_script(
                backend.token(),
                backend.startup_warnings(),
                &allowed_origin,
            );
            let navigation_origin = allowed_origin.clone();
            app.manage(backend);
            start_backend_lifecycle_monitor(app.app_handle().clone());
            eprintln!("[mediapipeline-shell] setup: building main WebView window");
            let window = match WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .initialization_script(initialization_script)
                .on_navigation(move |candidate| {
                    let allowed = navigation_matches_webview_origin(candidate, &navigation_origin);
                    if !allowed {
                        maybe_record_debug_navigation_denial("main", candidate);
                    }
                    allowed
                })
                .title("MediaPipelineRemuxEncodeAIO")
                .inner_size(1440.0, 920.0)
                .min_inner_size(1120.0, 720.0)
                .build()
            {
                Ok(window) => window,
                Err(error) => {
                    eprintln!("[mediapipeline-shell] setup: main WebView window failed: {error}");
                    return Err(error.into());
                }
            };
            eprintln!("[mediapipeline-shell] setup: main WebView window built");
            maybe_schedule_debug_webview_autolaunch(&window);
            schedule_native_update_check(app.app_handle().clone());
            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() != "main" {
                return;
            }
            match event {
                WindowEvent::CloseRequested { api, .. } => {
                    match close_request_decision(window) {
                        CloseRequestDecision::Deny => {
                            api.prevent_close();
                            return;
                        }
                        CloseRequestDecision::AllowSafe => {
                            match shutdown_backend_state(window, BackendShutdownMode::SafeOnly) {
                                BackendShutdownOutcome::Requested => {}
                                BackendShutdownOutcome::Blocked
                                | BackendShutdownOutcome::Failed => {
                                    api.prevent_close();
                                    return;
                                }
                            }
                        }
                        CloseRequestDecision::AllowConfirmedForce => {
                            match shutdown_backend_state(
                                window,
                                BackendShutdownMode::ConfirmedForceActiveWork,
                            ) {
                                BackendShutdownOutcome::Requested => {}
                                BackendShutdownOutcome::Blocked
                                | BackendShutdownOutcome::Failed => {
                                    api.prevent_close();
                                    return;
                                }
                            }
                        }
                    }
                    window.app_handle().exit(0);
                }
                WindowEvent::Destroyed => {
                    shutdown_backend_state(window, BackendShutdownMode::SafeOnly);
                }
                _ => {}
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running MediaPipeline Tauri shell");

    app.run(|app_handle, event| match event {
        RunEvent::ExitRequested { api, .. } => {
            match shutdown_backend_state(app_handle, BackendShutdownMode::SafeOnly) {
                BackendShutdownOutcome::Requested => {}
                BackendShutdownOutcome::Blocked | BackendShutdownOutcome::Failed => {
                    api.prevent_exit();
                }
            }
        }
        RunEvent::Exit => {
            shutdown_backend_state(app_handle, BackendShutdownMode::SafeOnly);
        }
        _ => {}
    });
}

pub(crate) fn tauri_bootstrap_initialization_script(
    token: &str,
    startup_warnings: &[String],
    allowed_origin: &str,
) -> String {
    let token_json = serde_json::to_string(token).unwrap_or_else(|_| "\"\"".to_string());
    let allowed_origin_json =
        serde_json::to_string(allowed_origin).unwrap_or_else(|_| "\"\"".to_string());
    let warnings_json =
        serde_json::to_string(&bounded_startup_validation_warnings(startup_warnings))
            .unwrap_or_else(|_| "[]".to_string());
    format!(
        r#"(function(){{const allowedOrigin={allowed_origin_json};if(window.top!==window||window.location.origin!==allowedOrigin){{try{{delete window.MEDIA_PIPELINE_TAURI_BOOTSTRAP;}}catch(_error){{window.MEDIA_PIPELINE_TAURI_BOOTSTRAP=undefined;}}return;}}const startupWarnings={warnings_json};window.MEDIA_PIPELINE_TAURI_BOOTSTRAP=Object.freeze({{token:{token_json},tokenSource:"tauri-initialization-script",startupWarnings}});if(startupWarnings.length){{console.warn("MediaPipeline Tauri startup validation warnings",startupWarnings);const render=function(){{if(!document.body||document.querySelector("[data-tauri-startup-validation-warning]"))return;const node=document.createElement("div");node.className="tauri-lifecycle-alert";node.dataset.state="warning";node.dataset.tauriStartupValidationWarning="true";node.setAttribute("role","alert");const title=document.createElement("strong");title.textContent="Startup validation warning";const detail=document.createElement("span");detail.textContent=startupWarnings.slice(0,3).join(" | ");const hint=document.createElement("span");hint.textContent="The backend opened, but Tauri detected WebView asset drift. Open Diagnostics before starting, draining, saving, renaming, publishing, or closing.";node.replaceChildren(title,detail,hint);const topbar=document.querySelector(".topbar");if(topbar&&topbar.parentNode)topbar.insertAdjacentElement("afterend",node);else document.body.prepend(node);}};if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",render,{{once:true}});else render();}}}})();"#
    )
}

fn bounded_startup_validation_warnings(startup_warnings: &[String]) -> Vec<String> {
    startup_warnings
        .iter()
        .take(MAX_STARTUP_VALIDATION_WARNINGS)
        .map(|warning| {
            let mut preview = String::new();
            for (index, ch) in warning.chars().enumerate() {
                if index >= MAX_STARTUP_VALIDATION_WARNING_CHARS {
                    preview.push_str("...");
                    break;
                }
                preview.push(ch);
            }
            preview
        })
        .collect()
}

#[cfg(test)]
mod lib_tests;
