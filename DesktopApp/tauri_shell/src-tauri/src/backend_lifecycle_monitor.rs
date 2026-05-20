use serde::Serialize;
use std::{
    thread,
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use tauri::{AppHandle, Emitter, Manager, Wry};

use crate::backend_process::BackendProcess;

pub(crate) const BACKEND_LIFECYCLE_EVENT: &str = "mediapipeline://backend-lifecycle";
pub(crate) const BACKEND_HEALTH_MONITOR_INTERVAL: Duration = Duration::from_secs(5);
pub(crate) const BACKEND_HEALTH_FAILURE_THRESHOLD: usize = 2;

#[derive(Clone, Serialize)]
struct BackendLifecycleNotification {
    schema_version: &'static str,
    status: String,
    detail: String,
    consecutive_failures: usize,
    emitted_at_unix_seconds: u64,
}

pub(crate) fn start_backend_lifecycle_monitor(app_handle: AppHandle<Wry>) {
    thread::spawn(move || {
        let mut consecutive_health_failures = 0_usize;
        let mut health_failure_reported = false;
        loop {
            thread::sleep(BACKEND_HEALTH_MONITOR_INTERVAL);
            let Some(backend) = app_handle.try_state::<BackendProcess>() else {
                break;
            };
            match backend.try_take_exited() {
                Ok(Some(Some(code))) => {
                    let detail = format!("Backend process exited unexpectedly with code {code}.");
                    eprintln!("[mediapipeline-shell] {detail}");
                    emit_lifecycle_event(&app_handle, "backend_exited", detail, 0);
                    break;
                }
                Ok(Some(None)) => break,
                Ok(None) => {}
                Err(error) => {
                    let detail = format!(
                        "Backend lifecycle monitor could not inspect process state: {error}"
                    );
                    eprintln!("[mediapipeline-shell] {detail}");
                    emit_lifecycle_event(
                        &app_handle,
                        "monitor_error",
                        detail,
                        consecutive_health_failures,
                    );
                    break;
                }
            }
            match backend.health_check() {
                Ok(()) => {
                    consecutive_health_failures = 0;
                    health_failure_reported = false;
                }
                Err(error) => {
                    consecutive_health_failures = consecutive_health_failures.saturating_add(1);
                    let detail = format!("Backend lifecycle health check failed: {error}");
                    eprintln!("[mediapipeline-shell] {detail}");
                    if consecutive_health_failures >= BACKEND_HEALTH_FAILURE_THRESHOLD
                        && !health_failure_reported
                    {
                        emit_lifecycle_event(
                            &app_handle,
                            "backend_health_failed",
                            detail,
                            consecutive_health_failures,
                        );
                        health_failure_reported = true;
                    }
                }
            }
        }
    });
}

fn emit_lifecycle_event(
    app_handle: &AppHandle<Wry>,
    status: &str,
    detail: String,
    consecutive_failures: usize,
) {
    let payload = BackendLifecycleNotification {
        schema_version: "mediapipeline_backend_lifecycle_event.v1",
        status: status.to_string(),
        detail,
        consecutive_failures,
        emitted_at_unix_seconds: unix_seconds_now(),
    };
    if let Err(error) = app_handle.emit(BACKEND_LIFECYCLE_EVENT, payload) {
        eprintln!("[mediapipeline-shell] backend lifecycle event emission failed: {error}");
    }
}

fn unix_seconds_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}
