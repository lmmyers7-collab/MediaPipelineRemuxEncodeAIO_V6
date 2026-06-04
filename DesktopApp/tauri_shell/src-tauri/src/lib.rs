use std::error::Error;
#[cfg(test)]
use std::{
    path::{Path, PathBuf},
    time::Duration,
};
use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent};

mod backend_contract;
mod backend_lifecycle_monitor;
mod backend_process;
mod close_readiness;
mod debug_webview;
mod dialogs;
mod http_helpers;
mod single_instance_guard;

#[cfg(test)]
use backend_contract::{
    format_list_preview, format_route_sample, validate_backend_contract, validate_backend_health,
    validate_backend_web_ui, BackendRoute,
};
use backend_lifecycle_monitor::start_backend_lifecycle_monitor;
#[cfg(test)]
use backend_process::{
    bootstrap_error, push_bootstrap_stdout_context, redact_bootstrap_stdout,
    web_ui_validation_error_is_fatal, MAX_BOOTSTRAP_STDOUT_CHARS, MAX_BOOTSTRAP_STDOUT_LINES,
};
use backend_process::{confirm_close_if_needed, shutdown_backend_state, start_backend};
#[cfg(test)]
use close_readiness::{
    close_readiness_warning_detail, close_readiness_watcher_lines, request_close_readiness,
    CloseReadiness, ContinuousWatcher,
};
use debug_webview::{
    maybe_schedule_debug_webview_autolaunch, maybe_write_debug_backend_auth_capture,
};
use dialogs::resolve_desktop_root;
#[cfg(test)]
use dialogs::{desktop_root_candidates_from_exe_dir, format_path_candidates};
#[cfg(test)]
use http_helpers::{read_backend_response_capped, request_backend_json};
use single_instance_guard::acquire_single_instance_guard;

type ShellResult<T> = Result<T, Box<dyn Error>>;
const MAX_BACKEND_RESPONSE_BYTES: usize = 16 * 1024 * 1024;
const MAX_STARTUP_VALIDATION_WARNINGS: usize = 4;
const MAX_STARTUP_VALIDATION_WARNING_CHARS: usize = 280;
const MAX_CLOSE_READINESS_WARNINGS: usize = 5;
const MAX_CLOSE_READINESS_WARNING_CHARS: usize = 240;
const MAX_OPERATOR_PATH_CHARS: usize = 320;

pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let single_instance_guard = acquire_single_instance_guard()?;
            app.manage(single_instance_guard);
            let desktop_root = resolve_desktop_root()?;
            let backend = start_backend(&desktop_root)?;
            maybe_write_debug_backend_auth_capture(backend.url(), backend.token());
            let initialization_script =
                tauri_bootstrap_initialization_script(backend.token(), backend.startup_warnings());
            let url = url::Url::parse(backend.url())?;
            app.manage(backend);
            start_backend_lifecycle_monitor(app.app_handle().clone());
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .initialization_script(initialization_script)
                .title("MediaPipelineRemuxEncodeAIO V6")
                .inner_size(1440.0, 920.0)
                .min_inner_size(1120.0, 720.0)
                .build()?;
            maybe_schedule_debug_webview_autolaunch(&window);
            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() != "main" {
                return;
            }
            match event {
                WindowEvent::CloseRequested { api, .. } => {
                    if !confirm_close_if_needed(window) {
                        api.prevent_close();
                        return;
                    }
                    shutdown_backend_state(window);
                    window.app_handle().exit(0);
                }
                WindowEvent::Destroyed => {
                    shutdown_backend_state(window);
                }
                _ => {}
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running MediaPipeline Tauri shell");

    app.run(|app_handle, event| match event {
        RunEvent::ExitRequested { .. } | RunEvent::Exit => {
            shutdown_backend_state(app_handle);
        }
        _ => {}
    });
}

pub(crate) fn tauri_bootstrap_initialization_script(
    token: &str,
    startup_warnings: &[String],
) -> String {
    let token_json = serde_json::to_string(token).unwrap_or_else(|_| "\"\"".to_string());
    let warnings_json =
        serde_json::to_string(&bounded_startup_validation_warnings(startup_warnings))
            .unwrap_or_else(|_| "[]".to_string());
    format!(
        r#"(function(){{const startupWarnings={warnings_json};window.MEDIA_PIPELINE_TAURI_BOOTSTRAP=Object.freeze({{token:{token_json},tokenSource:"tauri-initialization-script",startupWarnings}});if(startupWarnings.length){{console.warn("MediaPipeline Tauri startup validation warnings",startupWarnings);const render=function(){{if(!document.body||document.querySelector("[data-tauri-startup-validation-warning]"))return;const node=document.createElement("div");node.className="tauri-lifecycle-alert";node.dataset.state="warning";node.dataset.tauriStartupValidationWarning="true";node.setAttribute("role","alert");const title=document.createElement("strong");title.textContent="Startup validation warning";const detail=document.createElement("span");detail.textContent=startupWarnings.slice(0,3).join(" | ");const hint=document.createElement("span");hint.textContent="The backend opened, but Tauri detected WebView asset drift. Open Diagnostics before starting, draining, saving, renaming, publishing, or closing.";node.replaceChildren(title,detail,hint);const topbar=document.querySelector(".topbar");if(topbar&&topbar.parentNode)topbar.insertAdjacentElement("afterend",node);else document.body.prepend(node);}};if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",render,{{once:true}});else render();}}}})();"#
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
mod tests {
    use super::*;
    use std::{
        io::{Cursor, Read, Write},
        net::TcpListener,
        sync::mpsc::Receiver,
    };

    fn serve_once(response: impl Into<String>) -> (String, Receiver<String>) {
        serve_sequence(vec![response.into()])
    }

    fn serve_sequence(responses: Vec<String>) -> (String, Receiver<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind test backend");
        let address = listener.local_addr().expect("test backend local addr");
        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            for response in responses {
                let (mut stream, _) = listener.accept().expect("accept test backend request");
                stream
                    .set_read_timeout(Some(Duration::from_secs(2)))
                    .expect("set test backend read timeout");
                let mut buffer = [0_u8; 4096];
                let count = stream.read(&mut buffer).unwrap_or(0);
                let request = String::from_utf8_lossy(&buffer[..count]).to_string();
                let _ = tx.send(request);
                stream
                    .write_all(response.as_bytes())
                    .expect("write test backend response");
            }
        });
        (format!("http://{address}"), rx)
    }

    #[test]
    fn bootstrap_error_includes_bounded_stdout_context() {
        let mut lines = Vec::new();
        push_bootstrap_stdout_context(&mut lines, &"x".repeat(MAX_BOOTSTRAP_STDOUT_CHARS + 20));
        push_bootstrap_stdout_context(&mut lines, "second line");

        let error = bootstrap_error("Timed out waiting for backend bootstrap payload.", &lines);
        let detail = error.to_string();

        assert!(detail.contains("Timed out waiting for backend bootstrap payload."));
        assert!(detail.contains("Recent stdout before bootstrap:"));
        assert!(detail.contains("second line"));
        assert!(detail.contains("..."));
        assert!(detail.len() < MAX_BOOTSTRAP_STDOUT_CHARS + 220);
    }

    #[test]
    fn bootstrap_stdout_context_respects_line_limit() {
        let mut lines = Vec::new();
        for index in 0..(MAX_BOOTSTRAP_STDOUT_LINES + 3) {
            push_bootstrap_stdout_context(&mut lines, &format!("line {index}"));
        }

        assert_eq!(lines.len(), MAX_BOOTSTRAP_STDOUT_LINES);
        assert_eq!(lines.last().map(String::as_str), Some("line 4"));
    }

    #[test]
    fn bootstrap_stdout_context_redacts_token_like_values() {
        let mut lines = Vec::new();
        push_bootstrap_stdout_context(
            &mut lines,
            r#"startup {"token":"secret-token","auth_token": "auth-secret","WorkerAuthToken":"worker-secret"} Authorization: Bearer bearer-secret"#,
        );

        let error = bootstrap_error("Failed reading backend bootstrap payload.", &lines);
        let detail = error.to_string();
        assert!(detail.contains("[redacted]"));
        assert!(!detail.contains("secret-token"));
        assert!(!detail.contains("auth-secret"));
        assert!(!detail.contains("worker-secret"));
        assert!(!detail.contains("bearer-secret"));

        let direct = redact_bootstrap_stdout("Authorization: bearer lower-secret");
        assert!(direct.contains("bearer [redacted]"));
        assert!(!direct.contains("lower-secret"));
    }

    #[test]
    fn tauri_bootstrap_initialization_script_injects_token_without_index_assignment() {
        let script = tauri_bootstrap_initialization_script("secret-token\"<", &[]);

        assert!(script.contains("window.MEDIA_PIPELINE_TAURI_BOOTSTRAP"));
        assert!(script.contains("Object.freeze"));
        assert!(script.contains("tauri-initialization-script"));
        assert!(script.contains("startupWarnings"));
        assert!(script.contains(r#"secret-token\"<"#));
        assert!(!script.contains("window.MEDIA_PIPELINE_BOOTSTRAP ="));
    }

    #[test]
    fn tauri_bootstrap_initialization_script_includes_bounded_startup_warnings() {
        let warnings = (0..(MAX_STARTUP_VALIDATION_WARNINGS + 3))
            .map(|index| {
                format!(
                    "warning-{index}-{}",
                    "x".repeat(MAX_STARTUP_VALIDATION_WARNING_CHARS + 20)
                )
            })
            .collect::<Vec<String>>();
        let script = tauri_bootstrap_initialization_script("secret-token", &warnings);

        assert!(script.contains("Startup validation warning"));
        assert!(script.contains("WebView asset drift"));
        assert!(script.contains("warning-0-"));
        assert!(script.contains(&format!("warning-{}-", MAX_STARTUP_VALIDATION_WARNINGS - 1)));
        assert!(!script.contains(&format!("warning-{}-", MAX_STARTUP_VALIDATION_WARNINGS)));
        assert!(script.contains("..."));
        assert!(script.contains("secret-token"));
        assert!(!script.contains("window.MEDIA_PIPELINE_BOOTSTRAP ="));
    }

    #[test]
    fn web_ui_validation_only_treats_bootstrap_security_failures_as_fatal() {
        assert!(web_ui_validation_error_is_fatal(
            "Backend WebView index leaked the bearer token instead of relying on Tauri shell injection."
        ));
        assert!(web_ui_validation_error_is_fatal(
            "Backend WebView index still contains the raw bootstrap placeholder."
        ));
        assert!(web_ui_validation_error_is_fatal(
            "Backend WebView index is missing required fragment 'bootstrap assignment'."
        ));
        assert!(!web_ui_validation_error_is_fatal(
            "Backend WebView settings script is missing required fragment 'settings backend readiness guardrail'."
        ));
        assert!(!web_ui_validation_error_is_fatal(
            "Backend request did not return HTTP 200: HTTP/1.0 404 Not Found"
        ));
    }

    #[test]
    fn operator_path_candidate_display_is_bounded() {
        let candidates = vec![
            PathBuf::from(format!("C:\\{}", "a".repeat(MAX_OPERATOR_PATH_CHARS + 40))),
            PathBuf::from("C:\\MediaPipeline\\DesktopApp"),
        ];
        let display = format_path_candidates(&candidates);

        assert!(display.contains("..."));
        assert!(display.contains("C:\\MediaPipeline\\DesktopApp"));
        assert!(display.len() < (MAX_OPERATOR_PATH_CHARS * 2));
    }

    #[test]
    fn packaged_desktop_root_candidates_cover_bundle_relative_locations() {
        let candidates =
            desktop_root_candidates_from_exe_dir(Path::new("C:\\Bundle\\DesktopApp\\tauri_shell"));

        assert_eq!(
            candidates[0],
            PathBuf::from("C:\\Bundle\\DesktopApp\\tauri_shell\\DesktopApp")
        );
        assert_eq!(
            candidates[1],
            PathBuf::from("C:\\Bundle\\DesktopApp\\tauri_shell\\..\\DesktopApp")
        );
        assert_eq!(
            candidates[2],
            PathBuf::from("C:\\Bundle\\DesktopApp\\tauri_shell\\..\\..\\DesktopApp")
        );
    }

    #[test]
    fn capability_and_route_samples_are_bounded() {
        let capabilities = (0..16)
            .map(|index| format!("capability-{index}"))
            .collect::<Vec<String>>();
        let capability_preview = format_list_preview(&capabilities, 3);

        assert!(capability_preview.contains("capability-0"));
        assert!(capability_preview.contains("capability-2"));
        assert!(capability_preview.ends_with(", ..."));
        assert!(!capability_preview.contains("capability-3"));

        let routes = (0..16)
            .map(|index| BackendRoute {
                method: "GET".to_string(),
                path: format!("/api/test-{index}"),
                auth_required: true,
            })
            .collect::<Vec<BackendRoute>>();
        let route_preview = format_route_sample(&routes, 2);

        assert!(route_preview.contains("GET /api/test-0 auth_required=true"));
        assert!(route_preview.contains("GET /api/test-1 auth_required=true"));
        assert!(route_preview.ends_with("; ..."));
        assert!(!route_preview.contains("/api/test-2"));
    }

    #[test]
    fn read_backend_response_capped_rejects_oversized_and_invalid_utf8() {
        let mut oversized = Cursor::new(b"HTTP/1.1 200 OK\r\n\r\nabcdef".to_vec());
        let oversized_error = read_backend_response_capped(&mut oversized, 12)
            .expect_err("oversized response should fail")
            .to_string();
        assert!(oversized_error.contains("Backend response exceeded 12 byte limit."));

        let mut invalid_utf8 = Cursor::new(vec![0xff, 0xfe, 0xfd]);
        let utf8_error = read_backend_response_capped(&mut invalid_utf8, 32)
            .expect_err("invalid UTF-8 should fail")
            .to_string();
        assert!(utf8_error.contains("Backend response was not UTF-8"));
    }

    #[test]
    fn request_backend_json_success_sends_expected_request_without_frontend_bypass() {
        let (url, rx) = serve_once(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"ok\":true}",
        );

        let body = request_backend_json(&url, "POST", "/api/test", "secret-token", "{\"x\":1}")
            .expect("test backend request should succeed");
        let request = rx
            .recv_timeout(Duration::from_secs(2))
            .expect("test backend should receive request");

        assert_eq!(body, "{\"ok\":true}");
        assert!(request.starts_with("POST /api/test HTTP/1.1\r\n"));
        assert!(request.contains("Authorization: Bearer secret-token\r\n"));
        assert!(request.contains("Content-Type: application/json\r\n"));
        assert!(request.contains("Content-Length: 7\r\n"));
        assert!(request.ends_with("\r\n\r\n{\"x\":1}"));
    }

    #[test]
    fn request_backend_json_rejects_non_200_with_bounded_body_preview() {
        let long_body = "failure detail ".repeat(80);
        let (url, _rx) = serve_once(format!(
            "HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n{long_body}"
        ));

        let error = request_backend_json(&url, "GET", "/api/test", "secret-token", "")
            .expect_err("non-200 response should fail")
            .to_string();

        assert!(error.contains("Backend request did not return HTTP 200"));
        assert!(error.contains("HTTP/1.1 500 Internal Server Error"));
        assert!(error.contains("body: failure detail"));
        assert!(error.contains("..."));
        assert!(!error.contains("secret-token"));
        assert!(error.len() < 700);
    }

    #[test]
    fn request_backend_json_rejects_missing_body_and_non_http_url() {
        let (url, _rx) = serve_once("HTTP/1.1 200 OK\r\nConnection: close\r\n");
        let missing_body_error = request_backend_json(&url, "GET", "/api/test", "", "")
            .expect_err("missing body separator should fail")
            .to_string();
        assert!(missing_body_error.contains("Backend response did not include an HTTP body."));

        let scheme_error = request_backend_json("https://127.0.0.1:1", "GET", "/api/test", "", "")
            .expect_err("https backend URL should fail")
            .to_string();
        assert!(scheme_error.contains("Only http backend URLs are supported"));
    }

    #[test]
    fn close_readiness_warning_detail_includes_bounded_watcher_evidence() {
        let readiness = CloseReadiness {
            schema_version: "desktop_close_readiness.v1".to_string(),
            safe_to_close: false,
            state: "idle".to_string(),
            reason: "Shell close blocked because the backend schedule-stop watcher is armed."
                .to_string(),
            warnings: vec!["schedule watcher active".to_string()],
            continuous_watcher: ContinuousWatcher {
                status: "armed".to_string(),
                pid: 24680,
                deadline: "2026-05-14T23:59:00-04:00".to_string(),
                stop_requested: false,
                generation: 7,
                message: "m".repeat(MAX_CLOSE_READINESS_WARNING_CHARS + 20),
                error: String::new(),
            },
        };

        let detail = close_readiness_warning_detail(&readiness);

        assert!(detail.contains("schedule-stop watcher is armed"));
        assert!(detail.contains("Warnings:"));
        assert!(detail.contains("schedule watcher active"));
        assert!(detail.contains("Continuous schedule-stop watcher:"));
        assert!(detail.contains("status: armed"));
        assert!(detail.contains("pid: 24680"));
        assert!(detail.contains("deadline: 2026-05-14T23:59:00-04:00"));
        assert!(detail.contains("stop requested: no"));
        assert!(detail.contains("generation: 7"));
        assert!(detail.contains("message: "));
        assert!(detail.contains("..."));
        assert!(detail.contains("remove this in-process stop-at-schedule-boundary guard"));
        assert!(detail.len() < MAX_CLOSE_READINESS_WARNING_CHARS + 700);
    }

    #[test]
    fn request_close_readiness_parses_structured_watcher_evidence() {
        let (url, _rx) = serve_once(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"schema_version\":\"desktop_close_readiness.v1\",\"safe_to_close\":false,\"state\":\"idle\",\"reason\":\"watcher armed\",\"warnings\":[\"warning one\"],\"continuous_watcher\":{\"status\":\"armed\",\"pid\":24680,\"deadline\":\"2026-05-14T23:59:00-04:00\",\"stop_requested\":false,\"generation\":7,\"message\":\"armed message\",\"error\":\"\"}}",
        );

        let readiness =
            request_close_readiness(&url, "secret-token").expect("readiness should parse");

        assert!(!readiness.safe_to_close);
        assert_eq!(readiness.state, "idle");
        assert_eq!(readiness.continuous_watcher.status, "armed");
        assert_eq!(readiness.continuous_watcher.pid, 24680);
        assert_eq!(
            readiness.continuous_watcher.deadline,
            "2026-05-14T23:59:00-04:00"
        );
        assert!(!readiness.continuous_watcher.stop_requested);
        assert_eq!(readiness.continuous_watcher.generation, 7);
        assert_eq!(readiness.continuous_watcher.message, "armed message");
    }

    #[test]
    fn close_readiness_warning_detail_combined_active_work_and_armed_watcher() {
        // PG-1 adversarial: active-work reason AND armed watcher both present — all three
        // sections (reason, warnings, watcher) must appear in the dialog text.
        let readiness = CloseReadiness {
            schema_version: "desktop_close_readiness.v1".to_string(),
            safe_to_close: false,
            state: "active".to_string(),
            reason: "Pipeline encode job is running.".to_string(),
            warnings: vec!["active work in progress".to_string()],
            continuous_watcher: ContinuousWatcher {
                status: "armed".to_string(),
                pid: 99999,
                deadline: "2026-05-15T02:00:00-04:00".to_string(),
                stop_requested: false,
                generation: 8,
                message: "stop guard active".to_string(),
                error: "".to_string(),
            },
        };

        let detail = close_readiness_warning_detail(&readiness);

        // Reason section
        assert!(detail.contains("Pipeline encode job is running."));
        // Warnings section
        assert!(detail.contains("Warnings:"));
        assert!(detail.contains("active work in progress"));
        // Watcher section — all fields
        assert!(detail.contains("Continuous schedule-stop watcher:"));
        assert!(detail.contains("status: armed"));
        assert!(detail.contains("pid: 99999"));
        assert!(detail.contains("deadline: 2026-05-15T02:00:00-04:00"));
        assert!(detail.contains("stop requested: no"));
        assert!(detail.contains("generation: 8"));
        assert!(detail.contains("message: stop guard active"));
        assert!(detail.contains("remove this in-process stop-at-schedule-boundary guard"));
    }

    #[test]
    fn close_readiness_watcher_lines_stop_requested_shows_yes() {
        // PG-1 adversarial: watcher in stop-requested state.
        let watcher = ContinuousWatcher {
            status: "stop_requested".to_string(),
            pid: 55555,
            deadline: "2026-05-15T03:00:00-04:00".to_string(),
            stop_requested: true,
            generation: 9,
            message: "stop was requested".to_string(),
            error: "".to_string(),
        };

        let lines = close_readiness_watcher_lines(&watcher);

        assert!(!lines.is_empty());
        assert!(lines.iter().any(|l| l.contains("stop requested: yes")));
        assert!(lines.iter().any(|l| l.contains("stop_requested")));
        assert!(lines.iter().any(|l| l.contains("generation: 9")));
        // "armed" guard line should NOT appear for non-armed status
        assert!(!lines
            .iter()
            .any(|l| l.contains("remove this in-process stop-at-schedule-boundary guard")));
    }

    #[test]
    fn close_readiness_watcher_lines_error_field_shown() {
        // PG-1 adversarial: watcher reports an error — error field must surface.
        let watcher = ContinuousWatcher {
            status: "failed".to_string(),
            pid: 0,
            deadline: "".to_string(),
            stop_requested: false,
            generation: 0,
            message: "".to_string(),
            error: "watcher process exited unexpectedly".to_string(),
        };

        let lines = close_readiness_watcher_lines(&watcher);

        assert!(!lines.is_empty());
        assert!(lines.iter().any(|l| l.contains("status: failed")));
        assert!(lines
            .iter()
            .any(|l| l.contains("error: watcher process exited unexpectedly")));
        // pid=0 should not produce a pid line
        assert!(!lines.iter().any(|l| l.contains("pid:")));
        // empty deadline should not produce a deadline line
        assert!(!lines.iter().any(|l| l.contains("deadline:")));
    }

    #[test]
    fn close_readiness_watcher_lines_empty_status_returns_no_lines() {
        // PG-1: empty watcher status means watcher is not reported — no lines.
        let watcher = ContinuousWatcher::default();
        let lines = close_readiness_watcher_lines(&watcher);
        assert!(lines.is_empty());
    }

    #[test]
    fn request_close_readiness_rejects_wrong_schema_version() {
        // PG-1: wrong schema version must be rejected before the caller trusts the payload.
        let (url, _rx) = serve_once(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"schema_version\":\"desktop_close_readiness.v99\",\"safe_to_close\":false,\"state\":\"idle\",\"reason\":\"test\",\"warnings\":[],\"continuous_watcher\":{\"status\":\"\",\"pid\":0,\"deadline\":\"\",\"stop_requested\":false,\"message\":\"\",\"error\":\"\"}}",
        );

        let error = request_close_readiness(&url, "secret-token")
            .expect_err("wrong schema version should be rejected");

        assert!(error
            .to_string()
            .contains("Unexpected close-readiness schema"));
    }

    #[test]
    fn validate_backend_health_missing_capability_reports_sample_without_token() {
        let (url, _rx) = serve_once(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"schema_version\":\"desktop_backend_health.v1\",\"status\":\"ok\",\"capabilities\":[\"snapshot\",\"telemetry\"]}",
        );

        let error = validate_backend_health(&url, "secret-token")
            .expect_err("missing health capability should fail")
            .to_string();

        assert!(error.contains("Backend health is missing required capability"));
        assert!(error.contains("backend reported capabilities: snapshot, telemetry"));
        assert!(!error.contains("secret-token"));
    }

    #[test]
    fn validate_backend_contract_missing_route_reports_route_sample_without_token() {
        let (url, _rx) = serve_once(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"schema_version\":\"desktop_local_api_contract.v1\",\"routes\":[{\"method\":\"GET\",\"path\":\"/api/health\",\"auth_required\":false}]}",
        );

        let error = validate_backend_contract(&url, "secret-token")
            .expect_err("missing route should fail")
            .to_string();

        assert!(error.contains("Backend contract is missing required route"));
        assert!(error
            .contains("backend reported 1 route(s); sample: GET /api/health auth_required=false"));
        assert!(!error.contains("secret-token"));
    }

    #[cfg(debug_assertions)]
    #[test]
    fn debug_sample_validation_append_script_derives_label_from_source_path() {
        let script = super::debug_webview::debug_sample_validation_append_script(
            r"\\LAYNE-SERVER\Users\Layne\Videos\Encode\TV\Show\Show - S01E04.mkv",
            r"\\LAYNE-SERVER\Users\Layne\Videos\outsource\TV\Show\Season 01\Show - S01E04.mkv",
            "hold_review",
            "subtitle-srt-generation",
            "test note",
        )
        .expect("debug script should render");

        assert!(script.contains("const sampleLabelFromPath"));
        assert!(script.contains("sample_label: sampleLabelFromPath(sourceFile || outputPath)"));
        assert!(!script.contains("Spy X Family - S01E10 - THE GREAT DODGEBALL PLAN.mkv"));
    }

    #[test]
    fn validate_backend_web_ui_requires_index_and_real_media_assets_without_leaking_token() {
        let index = r#"<!doctype html>
<script>window.MEDIA_PIPELINE_BOOTSTRAP = Object.assign({}, {"apiBase":"","token":"","appVersion":"v6.000","shellSurface":"tauri","tokenSource":"tauri-initialization-script"}, window.MEDIA_PIPELINE_TAURI_BOOTSTRAP || {});</script>
<section data-page-panel="home">
  <strong id="cross-page-real-media-status">Not loaded</strong>
  <tbody id="cross-page-real-media-rows"></tbody>
  <strong id="sample-validation-status">Not loaded</strong>
  <strong id="sample-validation-cutover-status">Not loaded</strong>
  <tbody id="sample-validation-cutover-rows"></tbody>
  <strong id="sample-validation-sample-set-status">Not loaded</strong>
  <tbody id="sample-validation-sample-set-rows"></tbody>
  <select id="sample-validation-category"></select>
  <button id="sample-validation-use-sample-set-category-button"></button>
  <strong id="home-external-dependencies-status">Not loaded</strong>
  <pre id="home-external-dependencies-summary"></pre>
</section>
<section data-page-panel="settings">
  <strong id="settings-handbrake-preview-status">Predicted pending cutover</strong>
  <strong id="settings-handbrake-decision">NOT EVALUATED</strong>
  <strong id="settings-handbrake-active-preset">Saved settings</strong>
  <dd id="settings-handbrake-output-video"></dd>
  <dd id="settings-handbrake-output-guards"></dd>
  <pre id="settings-handbrake-preview-detail"></pre>
  <strong id="settings-backend-media-policy-status">Not loaded</strong>
  <tbody id="settings-backend-media-policy-rows"></tbody>
  <tbody id="settings-policy-delta-rows"></tbody>
  <tbody id="settings-effective-policy-rows"></tbody>
  <pre id="settings-effective-policy-detail"></pre>
  <tbody id="settings-backend-result-rows"></tbody>
  <pre id="settings-backend-result-detail"></pre>
  <select id="settings-builder-routing-profile"></select>
  <select id="settings-builder-size-guard"></select>
  <select id="settings-builder-output-container"></select>
</section>
<section data-page-panel="launch">
  <tbody id="launch-settings-risk-rows"></tbody>
  <pre id="launch-pilot-readiness-summary"></pre>
  <tbody id="launch-pilot-readiness-rows"></tbody>
</section>
<section data-page-panel="diagnostics">
  <strong id="diagnostics-state-triage-status">Not loaded</strong>
  <pre id="diagnostics-close-readiness"></pre>
  <pre id="backend-lifecycle-summary"></pre>
  <button id="backend-shutdown-button"></button>
</section>"#;
        let app_script = r#"async function refreshAllNow() {
  await apiGet("/api/sample-validation?limit=10");
  const crossPageContext = {
    settings: values.settings || getLastSettings(),
  };
  renderCrossPageContext(crossPageContext);
}
function renderBackendLifecycle() {}
function renderExternalDependencyDigest() {}
function externalDependencyRows() {}
async function requestBackendShutdown() {
  await apiPost("/api/backend/shutdown", {});
  return "Backend shutdown is disabled in WebView until close-readiness reports safe";
}"#;
        let cross_page_script = r#"function createCrossPageConflictModule() {}
function createCrossPageSampleModule() {}
function createCrossPageSettingsModule() {}
function createCrossPageSampleValidationModule() {}"#;
        let cross_page_conflict_script = r#"function createCrossPageConflictModule() {}
function crossPageConflictRows() {}
function renderCrossPageConflictBoard() {}
window.__crossPageConflictModule = { createCrossPageConflictModule };"#;
        let cross_page_sample_script = r#"function createCrossPageSampleModule() {}
function crossPageSampleRows() {}
function crossPageValidationTemplateLines() {}
window.__crossPageSampleModule = { createCrossPageSampleModule };"#;
        let cross_page_settings_script = r#"function createCrossPageSettingsModule() {}
function crossPageSettingsPolicyEvidence() {
  return "Backend media-policy readiness; media readiness=Ready";
}
window.__crossPageSettingsModule = { createCrossPageSettingsModule };"#;
        let cross_page_sample_validation_worksheet_script = r#"function createCrossPageSvWorksheetModule() {}
function crossPageRealMediaWorksheetRows() {}
function sampleValidationPolicyAlignmentSummaryLines() {}
function renderSampleValidationSampleSetGuide() { return "Recommended real-media sample set:"; }
function useSelectedSampleSetCategory() {}
function renderCrossPageRealMediaWorksheet() {
  const summary = "Backend media-policy readiness; media readiness=Ready";
  return "this worksheet does not save, accept, repair, rerun, drain, delete, publish, rename, rewrite manifests, or touch media files";
}
window.__crossPageSvWorksheetModule = { createCrossPageSvWorksheetModule };"#;
        let cross_page_sample_validation_runbook_script = r#"function createCrossPageSvRunbookModule() {}
function renderSampleValidationCutoverGate() { return "WebView cutover gate:"; }
function renderSampleValidationRunbook() {}
function renderSampleValidationExecutionChecklist() {}
window.__crossPageSvRunbookModule = { createCrossPageSvRunbookModule };"#;
        let cross_page_sample_validation_records_script = r#"function createCrossPageSvRecordsModule() {}
function sampleValidationRecordComparisonRowsForPaths() {}
function sampleValidationCompletedPacketRows() {}
function renderSampleValidationAcceptanceGate() {
  return "Decision rule: accepted sample evidence should not be appended";
}
function renderSampleValidationRecordReview() {}
window.__crossPageSvRecordsModule = { createCrossPageSvRecordsModule };"#;
        let cross_page_sample_validation_script = r#"function createCrossPageSvWorksheetModule() {}
function createCrossPageSvRunbookModule() {}
function createCrossPageSvRecordsModule() {}
function buildSampleValidationRequest() { return "/api/sample-validation/append"; }"#;
        let diagnostics_active_jobs_script = r#"function createDiagnosticsActiveJobsModule() {}
function diagnosticsActiveJobRealMediaTraceLines() {}
window.__diagnosticsActiveJobsModule = { createDiagnosticsActiveJobsModule };"#;
        let diagnostics_log_script = r#"function createDiagnosticsLogModule() {
  return "Log triage guidance:";
}
function diagnosticsLogRows() {}
window.__diagnosticsLogModule = { createDiagnosticsLogModule };"#;
        let diagnostics_investigation_script = r#"function createDiagnosticsInvestigationModule() {
  return "Owning-page evidence handoff:";
}
function diagnosticsInvestigationActions() {}
window.__diagnosticsInvestigationModule = { createDiagnosticsInvestigationModule };"#;
        let diagnostics_script = r#"function diagnosticsFirstResponseRows() {
const diagnosticsActiveJobsModule = window.__diagnosticsActiveJobsModule || {};
const diagnosticsLogModule = window.__diagnosticsLogModule || {};
const diagnosticsInvestigationModule = window.__diagnosticsInvestigationModule || {};
  return "External dependency readiness Resolve blocked Settings OCR or Maintenance toolchain evidence";
}"#;
        let settings_raw_triage_script = r#"function createSettingsRawTriageModule() {
  return "Settings raw-key action plan:";
}
function settingsRawTriageRows() {}
function settingsRawActionPlanRows() {}
window.__settingsRawTriageModule = { createSettingsRawTriageModule };"#;
        let settings_safety_locks_script = r#"function createSettingsSafetyLocksModule() {
  return "Settings safety lock review:";
}
function settingsSafetyLockRows() {}
window.__settingsSafetyLocksModule = { createSettingsSafetyLocksModule };"#;
        let settings_backend_result_script = r#"function createSettingsBackendResultModule() {}
function settingsBackendResultRows() {
  return "Patch JSON changed after the last preview. Preview again before saving.";
}
function settingsBackendResultDetailLines() {
  return "Patch identity:";
}
function renderSettingsBackendResultFromEntries() {
  return "Save Patch is the only persistence command";
}
window.__settingsBackendResultModule = { createSettingsBackendResultModule };"#;
        let settings_patch_review_script = r#"function renderHandbrakePreviewSummary(settings) {
  return "Source-specific route previews are not exposed in Settings";
}
function collectSettingsBuilderPatch() {
  return {
    RoutingProfile: settingsBuilderInputValue("settings-builder-routing-profile"),
    OutputContainer: settingsBuilderInputValue("settings-builder-output-container"),
  };
}
function bindSettingsClick() {}"#;
        let settings_script = r#"const settingsRawTriageModule = window.__settingsRawTriageModule || {};
const settingsSafetyLocksModule = window.__settingsSafetyLocksModule || {};
const settingsBackendResultModule = window.__settingsBackendResultModule || {};
const settingsPolicyImpactModule = window.__settingsPolicyImpactModule || {};
delete window.__settingsPolicyImpactModule;
"#;
        let settings_policy_impact_script = r#"function createSettingsPolicyImpactModule() {}
function settingsBackendMediaPolicyReadiness() {}
function renderSettingsBackendMediaPolicyReadiness() {
  return "Backend media-policy readiness: this table cannot stage settings, save config, launch work, run FFmpeg, publish files, or touch source media";
}
function settingsPolicyDeltaRows() {
  return "Staged media-policy delta:";
}
function settingsEffectivePolicyRows() {
  return "Effective policy trust summary: Launch-active policy is the saved backend config";
}
window.__settingsPolicyImpactModule = { createSettingsPolicyImpactModule };"#;
        let settings_overview_script = r#"function settingsMediaPolicyReadinessLine(settings) {
  return settings.media_policy_readiness;
}"#;
        let launch_risk_script = r#"function createLaunchRiskModule(settings) {
  const mediaReadiness = settings.media_policy_readiness;
  return "Backend media-policy readiness Resolve blocked saved media-policy rows before launching unattended work. Launch active media-policy boundary: Saved settings vs launch intent checklist:";
}
window.__launchViewRiskModule = { createLaunchRiskModule };"#;
        let launch_scope_script = r#"function createLaunchScopeModule() {
  return "Launch scope reconciliation: Launch start decision summary:";
}
window.__launchViewScopeModule = { createLaunchScopeModule };"#;
        let launch_realmedia_script = r#"function createLaunchRealMediaModule() {
  return "Launch real-media sample proof handoff: Launch sample execution checklist:";
}
window.__launchViewRealMediaModule = { createLaunchRealMediaModule };"#;
        let launch_preflight_script = r#"function createLaunchPreflightModule() {
  return "Launch pilot run readiness:";
}
window.__launchViewPreflightModule = { createLaunchPreflightModule };
function launchPilotRunReadinessRows() {
  return "Launch pilot run readiness:";
}
function renderLaunchPilotRunReadiness() {
  return "Launch pilot run readiness:";
}"#;
        let launch_script = r#"const launchPreflightModule = window.__launchViewPreflightModule || {};
delete window.__launchViewPreflightModule;"#;
        let diagnostics_state_script = r#"function renderDiagnosticsStateTriage() { return "Backend read order:"; }
function renderDiagnosticsStateTriageRows() {}
const diagnosticsStateTriageActionsId = "diagnostics-state-triage-actions";"#;
        let pending_publish_recovery_script = r#"function createPendingPublishRecoveryModule() {
  return "/api/pending-publish/recovery-plan";
}
function renderPendingRecoveryPlanResult() {}
window.__pendingPublishRecoveryModule = { createPendingPublishRecoveryModule };"#;
        let pending_publish_diagnostics_script = r#"function createPendingPublishDiagnosticsModule() {
  return "/api/pending-publish/open The Pending page never sends arbitrary filesystem paths.";
}
function requestPendingPublishOpen() {}
window.__pendingPublishDiagnosticsModule = { createPendingPublishDiagnosticsModule };"#;
        let pending_publish_drain_script = r#"function createPendingPublishDrainModule() {
  return "Pending drain evidence board:";
}
function renderPendingDrainEvidence() {}
function renderPendingDrainCorrelation() {}
window.__pendingPublishDrainModule = { createPendingPublishDrainModule };"#;
        let pending_publish_confidence_script = r#"function createPendingPublishConfidenceModule() {
  return "Pending Publish drain action confidence:";
}
function pendingDrainGuardState() {}
function renderPendingDrainDecisionChecklist() {}
window.__pendingPublishConfidenceModule = { createPendingPublishConfidenceModule };"#;
        let pending_publish_script = r#"let pendingSampleValidationHandoffLines = function () {};
const pendingRecoveryModule = window.__pendingPublishRecoveryModule || {};
const pendingDiagnosticsModule = window.__pendingPublishDiagnosticsModule || {};
const pendingDrainModule = window.__pendingPublishDrainModule || {};
const pendingConfidenceModule = window.__pendingPublishConfidenceModule || {};"#;
        let responses = [
            index,
            app_script,
            cross_page_script,
            cross_page_conflict_script,
            cross_page_sample_script,
            cross_page_settings_script,
            cross_page_sample_validation_worksheet_script,
            cross_page_sample_validation_runbook_script,
            cross_page_sample_validation_records_script,
            cross_page_sample_validation_script,
            diagnostics_active_jobs_script,
            diagnostics_log_script,
            diagnostics_investigation_script,
            diagnostics_script,
            settings_raw_triage_script,
            settings_safety_locks_script,
            settings_backend_result_script,
            settings_patch_review_script,
            settings_script,
            settings_policy_impact_script,
            settings_overview_script,
            launch_risk_script,
            launch_scope_script,
            launch_realmedia_script,
            launch_preflight_script,
            launch_script,
            diagnostics_state_script,
            pending_publish_recovery_script,
            pending_publish_diagnostics_script,
            pending_publish_drain_script,
            pending_publish_confidence_script,
            pending_publish_script,
        ]
        .map(|body| format!("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n{body}"))
        .to_vec();
        let (url, rx) = serve_sequence(responses);

        validate_backend_web_ui(&url, "secret-token").expect("web UI validation should pass");
        let requests = (0..32)
            .map(|_| {
                rx.recv_timeout(Duration::from_secs(2))
                    .expect("request received")
            })
            .collect::<Vec<String>>();

        assert!(requests[0].starts_with("GET / HTTP/1.1\r\n"));
        assert!(requests[1].starts_with("GET /assets/app.js HTTP/1.1\r\n"));
        assert!(requests[2].starts_with("GET /assets/crossPageContextView.js HTTP/1.1\r\n"));
        assert!(
            requests[3].starts_with("GET /assets/crossPageContextView.conflict.js HTTP/1.1\r\n")
        );
        assert!(requests[4].starts_with("GET /assets/crossPageContextView.sample.js HTTP/1.1\r\n"));
        assert!(
            requests[5].starts_with("GET /assets/crossPageContextView.settings.js HTTP/1.1\r\n")
        );
        assert!(requests[6].starts_with(
            "GET /assets/crossPageContextView.sampleValidation.worksheet.js HTTP/1.1\r\n"
        ));
        assert!(requests[7].starts_with(
            "GET /assets/crossPageContextView.sampleValidation.runbook.js HTTP/1.1\r\n"
        ));
        assert!(requests[8].starts_with(
            "GET /assets/crossPageContextView.sampleValidation.records.js HTTP/1.1\r\n"
        ));
        assert!(requests[9]
            .starts_with("GET /assets/crossPageContextView.sampleValidation.js HTTP/1.1\r\n"));
        assert!(requests[10].starts_with("GET /assets/diagnosticsView.activejobs.js HTTP/1.1\r\n"));
        assert!(requests[11].starts_with("GET /assets/diagnosticsView.log.js HTTP/1.1\r\n"));
        assert!(
            requests[12].starts_with("GET /assets/diagnosticsView.investigation.js HTTP/1.1\r\n")
        );
        assert!(requests[13].starts_with("GET /assets/diagnosticsView.js HTTP/1.1\r\n"));
        assert!(requests[14].starts_with("GET /assets/settingsView.rawTriage.js HTTP/1.1\r\n"));
        assert!(requests[15].starts_with("GET /assets/settingsView.safetyLocks.js HTTP/1.1\r\n"));
        assert!(requests[16].starts_with("GET /assets/settings/backendResult.js HTTP/1.1\r\n"));
        assert!(requests[17].starts_with("GET /assets/settings/patchReview.js HTTP/1.1\r\n"));
        assert!(requests[18].starts_with("GET /assets/settingsView.js HTTP/1.1\r\n"));
        assert!(requests[19].starts_with("GET /assets/settings/policyImpact.js HTTP/1.1\r\n"));
        assert!(requests[20].starts_with("GET /assets/settingsOverview.js HTTP/1.1\r\n"));
        assert!(requests[21].starts_with("GET /assets/launchView.risk.js HTTP/1.1\r\n"));
        assert!(requests[22].starts_with("GET /assets/launchView.scope.js HTTP/1.1\r\n"));
        assert!(requests[23].starts_with("GET /assets/launchView.realmedia.js HTTP/1.1\r\n"));
        assert!(requests[24].starts_with("GET /assets/launchView.preflight.js HTTP/1.1\r\n"));
        assert!(requests[25].starts_with("GET /assets/launchView.js HTTP/1.1\r\n"));
        assert!(requests[26].starts_with("GET /assets/diagnosticsStateSummaryView.js HTTP/1.1\r\n"));
        assert!(requests[27].starts_with("GET /assets/pendingPublishView.recovery.js HTTP/1.1\r\n"));
        assert!(
            requests[28].starts_with("GET /assets/pendingPublishView.diagnostics.js HTTP/1.1\r\n")
        );
        assert!(requests[29].starts_with("GET /assets/pendingPublishView.drain.js HTTP/1.1\r\n"));
        assert!(
            requests[30].starts_with("GET /assets/pendingPublishView.confidence.js HTTP/1.1\r\n")
        );
        assert!(requests[31].starts_with("GET /assets/pendingPublishView.js HTTP/1.1\r\n"));
        assert!(requests
            .iter()
            .all(|request| request.contains("Authorization: Bearer secret-token\r\n")));
    }

    #[test]
    fn validate_backend_web_ui_reports_missing_fragments_without_token() {
        let index = r#"<!doctype html>
<script>window.MEDIA_PIPELINE_BOOTSTRAP = Object.assign({}, {"apiBase":"","token":"","appVersion":"v6.000","shellSurface":"tauri","tokenSource":"tauri-initialization-script"}, window.MEDIA_PIPELINE_TAURI_BOOTSTRAP || {});</script>
<section data-page-panel="home">
  <strong id="cross-page-real-media-status">Not loaded</strong>
  <tbody id="cross-page-real-media-rows"></tbody>
  <strong id="sample-validation-status">Not loaded</strong>
  <strong id="sample-validation-cutover-status">Not loaded</strong>
  <tbody id="sample-validation-cutover-rows"></tbody>
  <strong id="sample-validation-sample-set-status">Not loaded</strong>
  <tbody id="sample-validation-sample-set-rows"></tbody>
  <select id="sample-validation-category"></select>
  <button id="sample-validation-use-sample-set-category-button"></button>
  <strong id="home-external-dependencies-status">Not loaded</strong>
  <pre id="home-external-dependencies-summary"></pre>
</section>
<section data-page-panel="settings">
  <strong id="settings-handbrake-preview-status">Predicted pending cutover</strong>
  <strong id="settings-handbrake-decision">NOT EVALUATED</strong>
  <strong id="settings-handbrake-active-preset">Saved settings</strong>
  <dd id="settings-handbrake-output-video"></dd>
  <dd id="settings-handbrake-output-guards"></dd>
  <pre id="settings-handbrake-preview-detail"></pre>
  <strong id="settings-backend-media-policy-status">Not loaded</strong>
  <tbody id="settings-backend-media-policy-rows"></tbody>
  <tbody id="settings-policy-delta-rows"></tbody>
  <tbody id="settings-effective-policy-rows"></tbody>
  <pre id="settings-effective-policy-detail"></pre>
  <tbody id="settings-backend-result-rows"></tbody>
  <pre id="settings-backend-result-detail"></pre>
  <select id="settings-builder-routing-profile"></select>
  <select id="settings-builder-size-guard"></select>
  <select id="settings-builder-output-container"></select>
</section>
<section data-page-panel="launch">
  <tbody id="launch-settings-risk-rows"></tbody>
  <pre id="launch-pilot-readiness-summary"></pre>
  <tbody id="launch-pilot-readiness-rows"></tbody>
</section>
<section data-page-panel="diagnostics">
  <strong id="diagnostics-state-triage-status">Not loaded</strong>
  <pre id="diagnostics-close-readiness"></pre>
  <pre id="backend-lifecycle-summary"></pre>
  <button id="backend-shutdown-button"></button>
</section>"#;
        let app_script = r#"async function refreshAllNow() {
  await apiGet("/api/sample-validation?limit=10");
  const crossPageContext = {
    settings: values.settings || getLastSettings(),
  };
  renderCrossPageContext(crossPageContext);
}
function renderBackendLifecycle() {}
function renderExternalDependencyDigest() {}
function externalDependencyRows() {}
async function requestBackendShutdown() {
  await apiPost("/api/backend/shutdown", {});
  return "Backend shutdown is disabled in WebView until close-readiness reports safe";
}"#;
        let cross_page_script = r#"function createCrossPageConflictModule() {}
function createCrossPageSampleModule() {}
function createCrossPageSettingsModule() {}
function createCrossPageSampleValidationModule() {}"#;
        let cross_page_conflict_script = r#"function createCrossPageConflictModule() {}
function crossPageConflictRows() {}
function renderCrossPageConflictBoard() {}
window.__crossPageConflictModule = { createCrossPageConflictModule };"#;
        let cross_page_sample_script = r#"function createCrossPageSampleModule() {}
function crossPageSampleRows() {}
function crossPageValidationTemplateLines() {}
window.__crossPageSampleModule = { createCrossPageSampleModule };"#;
        let cross_page_settings_script = r#"function createCrossPageSettingsModule() {}
function crossPageSettingsPolicyEvidence() {
  return "Backend media-policy readiness; media readiness=Ready";
}
window.__crossPageSettingsModule = { createCrossPageSettingsModule };"#;
        let cross_page_sample_validation_script = "function renderCrossPageContext() {}";
        let responses = [
            index,
            app_script,
            cross_page_script,
            cross_page_conflict_script,
            cross_page_sample_script,
            cross_page_settings_script,
            cross_page_sample_validation_script,
        ]
        .map(|body| format!("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n{body}"))
        .to_vec();
        let (url, _rx) = serve_sequence(responses);

        let error = validate_backend_web_ui(&url, "secret-token")
            .expect_err("missing worksheet helper should fail")
            .to_string();

        assert!(error.contains(
            "Backend WebView cross-page sample validation worksheet script is missing required fragment"
        ));
        assert!(error.contains("real-media worksheet renderer"));
        assert!(!error.contains("secret-token"));
    }
}
