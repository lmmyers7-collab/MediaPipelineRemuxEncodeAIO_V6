mod web_ui;
use super::*;
use std::{
    io::{Cursor, Read, Write},
    net::TcpListener,
    sync::mpsc::Receiver,
};

pub(super) fn serve_once(response: impl Into<String>) -> (String, Receiver<String>) {
    serve_sequence(vec![response.into()])
}

pub(super) fn serve_sequence(responses: Vec<String>) -> (String, Receiver<String>) {
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
fn web_ui_validation_treats_all_asset_validation_failures_as_fatal() {
    assert!(web_ui_validation_error_is_fatal(
            "Backend WebView index leaked the bearer token instead of relying on Tauri shell injection."
        ));
    assert!(web_ui_validation_error_is_fatal(
        "Backend WebView index still contains the raw bootstrap placeholder."
    ));
    assert!(web_ui_validation_error_is_fatal(
        "Backend WebView index is missing required fragment 'bootstrap data block'."
    ));
    assert!(web_ui_validation_error_is_fatal(
            "Backend WebView settings script is missing required fragment 'settings backend readiness guardrail'."
        ));
    assert!(web_ui_validation_error_is_fatal(
        "Backend request did not return HTTP 200: HTTP/1.0 404 Not Found"
    ));
}

#[test]
fn operator_path_candidate_display_is_bounded() {
    let candidates = vec![
        PathBuf::from(format!("C:\\{}", "a".repeat(MAX_OPERATOR_PATH_CHARS + 40))),
        PathBuf::from("C:\\MediaPipeline\\apps\\desktop"),
    ];
    let display = format_path_candidates(&candidates);

    assert!(display.contains("..."));
    assert!(display.contains("C:\\MediaPipeline\\apps\\desktop"));
    assert!(display.len() < (MAX_OPERATOR_PATH_CHARS * 2));
}

#[test]
fn packaged_desktop_root_candidates_cover_bundle_relative_locations() {
    let candidates =
        desktop_root_candidates_from_exe_dir(Path::new("C:\\Bundle\\apps\\desktop\\tauri"));

    assert_eq!(candidates[0], PathBuf::from("C:\\Bundle\\apps\\desktop"));
    assert_eq!(
        candidates[1],
        PathBuf::from("C:\\Bundle\\apps\\desktop\\tauri\\apps\\desktop")
    );
    assert_eq!(
        candidates[2],
        PathBuf::from("C:\\Bundle\\apps\\apps\\desktop")
    );
}

#[test]
fn packaged_desktop_root_derives_project_root_for_pythonpath() {
    let candidates =
        desktop_root_candidates_from_exe_dir(Path::new("C:\\Bundle\\apps\\desktop\\tauri"));

    assert_eq!(
        project_root_from_desktop_root(&candidates[0]),
        PathBuf::from("C:\\Bundle")
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
            effect: None,
            request_keys: Vec::new(),
            safe_defaults: None,
            requires_strict_boolean: Vec::new(),
            requires_dry_run_fingerprint: None,
            requires_confirmation: None,
            journaled: None,
            owner: None,
            frontend_exposed: None,
            network_lifecycle: None,
            response_schema: None,
            data_schema: None,
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

    let readiness = request_close_readiness(&url, "secret-token").expect("readiness should parse");

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
    assert!(
        error.contains("backend reported 1 route(s); sample: GET /api/health auth_required=false")
    );
    assert!(!error.contains("secret-token"));
}

fn lifecycle_reconciliation_dry_run_route_payload() -> serde_json::Value {
    serde_json::json!({
        "method": "POST",
        "path": "/api/backend/lifecycle/reconcile-dry-run",
        "auth_required": true,
        "effect": "none",
        "request_keys": ["reason"],
        "requires_confirmation": false,
        "journaled": false,
        "response_schema": "desktop_command_result.v1",
        "data_schema": "desktop_lifecycle_reconciliation.v1"
    })
}

fn lifecycle_reconciliation_apply_route_payload() -> serde_json::Value {
    serde_json::json!({
        "method": "POST",
        "path": "/api/backend/lifecycle/reconcile",
        "auth_required": true,
        "effect": "lifecycle-evidence-reconciliation",
        "request_keys": ["confirm_apply", "dry_run_fingerprint", "reason"],
        "safe_defaults": {"confirm_apply": false},
        "requires_strict_boolean": ["confirm_apply"],
        "requires_dry_run_fingerprint": true,
        "requires_confirmation": true,
        "journaled": true,
        "response_schema": "desktop_command_result.v1",
        "data_schema": "desktop_lifecycle_reconciliation.v1"
    })
}

fn lifecycle_route_from_payload(payload: serde_json::Value) -> BackendRoute {
    serde_json::from_value(payload).expect("deserialize lifecycle reconciliation route")
}

fn assert_lifecycle_route_drift(payload: serde_json::Value, required_index: usize, field: &str) {
    let route = lifecycle_route_from_payload(payload);
    let required = &REQUIRED_LIFECYCLE_RECONCILIATION_ROUTES[required_index];
    let error = validate_lifecycle_reconciliation_route(&route, required)
        .expect_err("lifecycle reconciliation metadata drift should fail")
        .to_string();

    assert!(
        error.contains("Backend contract lifecycle reconciliation metadata drifted"),
        "unexpected {field} drift error: {error}"
    );
    assert!(error.contains(required.path));
}

fn replace_route_field(
    mut payload: serde_json::Value,
    key: &str,
    value: serde_json::Value,
) -> serde_json::Value {
    payload
        .as_object_mut()
        .expect("route payload should be an object")
        .insert(key.to_string(), value);
    payload
}

fn remove_route_field(mut payload: serde_json::Value, key: &str) -> serde_json::Value {
    payload
        .as_object_mut()
        .expect("route payload should be an object")
        .remove(key);
    payload
}

#[test]
fn lifecycle_reconciliation_route_semantics_accept_exact_contracts() {
    let payloads = [
        lifecycle_reconciliation_dry_run_route_payload(),
        lifecycle_reconciliation_apply_route_payload(),
    ];

    assert_eq!(REQUIRED_LIFECYCLE_RECONCILIATION_ROUTES.len(), 2);
    for (payload, required) in payloads
        .into_iter()
        .zip(REQUIRED_LIFECYCLE_RECONCILIATION_ROUTES)
    {
        let route = lifecycle_route_from_payload(payload);
        validate_lifecycle_reconciliation_route(&route, required)
            .expect("exact lifecycle reconciliation contract should validate");
    }
}

#[test]
fn lifecycle_reconciliation_apply_route_rejects_request_guard_drift() {
    let cases = [
        (
            "request_keys order",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "request_keys",
                serde_json::json!(["dry_run_fingerprint", "confirm_apply", "reason"]),
            ),
        ),
        (
            "request_keys expansion",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "request_keys",
                serde_json::json!([
                    "confirm_apply",
                    "dry_run_fingerprint",
                    "reason",
                    "caller_selected_path"
                ]),
            ),
        ),
        (
            "safe_defaults missing",
            remove_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "safe_defaults",
            ),
        ),
        (
            "confirm_apply unsafe default",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "safe_defaults",
                serde_json::json!({"confirm_apply": true}),
            ),
        ),
        (
            "strict boolean missing",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "requires_strict_boolean",
                serde_json::json!([]),
            ),
        ),
        (
            "fingerprint guard missing",
            remove_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "requires_dry_run_fingerprint",
            ),
        ),
        (
            "fingerprint guard disabled",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "requires_dry_run_fingerprint",
                serde_json::json!(false),
            ),
        ),
        (
            "confirmation guard disabled",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "requires_confirmation",
                serde_json::json!(false),
            ),
        ),
    ];

    for (field, payload) in cases {
        assert_lifecycle_route_drift(payload, 1, field);
    }
}

#[test]
fn lifecycle_reconciliation_apply_route_rejects_evidence_contract_drift() {
    let cases = [
        (
            "effect",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "effect",
                serde_json::json!("none"),
            ),
        ),
        (
            "journal disabled",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "journaled",
                serde_json::json!(false),
            ),
        ),
        (
            "journal declaration missing",
            remove_route_field(lifecycle_reconciliation_apply_route_payload(), "journaled"),
        ),
        (
            "response schema",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "response_schema",
                serde_json::json!("desktop_command_result.v2"),
            ),
        ),
        (
            "data schema",
            replace_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "data_schema",
                serde_json::json!("desktop_lifecycle_reconciliation.v2"),
            ),
        ),
        (
            "data schema missing",
            remove_route_field(
                lifecycle_reconciliation_apply_route_payload(),
                "data_schema",
            ),
        ),
    ];

    for (field, payload) in cases {
        assert_lifecycle_route_drift(payload, 1, field);
    }
}

#[test]
fn lifecycle_reconciliation_preview_route_remains_unconfirmed_and_unjournaled() {
    let cases = [
        (
            "preview safe default metadata",
            replace_route_field(
                lifecycle_reconciliation_dry_run_route_payload(),
                "safe_defaults",
                serde_json::json!({}),
            ),
        ),
        (
            "preview strict boolean metadata",
            replace_route_field(
                lifecycle_reconciliation_dry_run_route_payload(),
                "requires_strict_boolean",
                serde_json::json!(["confirm_apply"]),
            ),
        ),
        (
            "preview fingerprint guard",
            replace_route_field(
                lifecycle_reconciliation_dry_run_route_payload(),
                "requires_dry_run_fingerprint",
                serde_json::json!(true),
            ),
        ),
        (
            "preview confirmation",
            replace_route_field(
                lifecycle_reconciliation_dry_run_route_payload(),
                "requires_confirmation",
                serde_json::json!(true),
            ),
        ),
        (
            "preview journal",
            replace_route_field(
                lifecycle_reconciliation_dry_run_route_payload(),
                "journaled",
                serde_json::json!(true),
            ),
        ),
    ];

    for (field, payload) in cases {
        assert_lifecycle_route_drift(payload, 0, field);
    }
}

#[test]
fn lifecycle_reconciliation_safe_default_requires_a_json_boolean() {
    let payload = replace_route_field(
        lifecycle_reconciliation_apply_route_payload(),
        "safe_defaults",
        serde_json::json!({"confirm_apply": "false"}),
    );

    let route = lifecycle_route_from_payload(payload);
    let error = validate_lifecycle_reconciliation_route(
        &route,
        &REQUIRED_LIFECYCLE_RECONCILIATION_ROUTES[1],
    )
    .expect_err("string safe default should fail exact semantic validation")
    .to_string();
    assert!(error.contains("Backend contract lifecycle reconciliation metadata drifted"));
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
