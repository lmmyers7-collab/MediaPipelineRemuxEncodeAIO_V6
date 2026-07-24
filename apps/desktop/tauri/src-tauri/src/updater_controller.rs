use serde::{Deserialize, Serialize};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
    time::{SystemTime, UNIX_EPOCH},
};
use tauri::{utils::config::Updater as UpdaterArtifactMode, AppHandle, Manager};
use tauri_plugin_updater::{Error as UpdaterError, UpdaterExt};

use crate::{
    backend_process::{
        shutdown_backend_state, BackendProcess, BackendShutdownMode, BackendShutdownOutcome,
    },
    close_readiness::{close_readiness_warning_detail, request_close_readiness, CloseReadiness},
    dialogs::{
        confirm_update_download_dialog, confirm_update_install_dialog, shell_error,
        show_update_notice_dialog,
    },
    ShellResult,
};

const EVIDENCE_SCHEMA_VERSION: &str = "tauri_native_updater_event.v1";
const EVIDENCE_DIRECTORY: &str = "UpdateState/NativeUpdater";
const EVIDENCE_FILE_PREFIX: &str = "update-event-";
const MAX_EVIDENCE_FILES: usize = 64;
const MAX_EVIDENCE_FILE_BYTES: u64 = 32 * 1024;
const MAX_EVIDENCE_TEXT_CHARS: usize = 240;
static EVIDENCE_SEQUENCE: AtomicU64 = AtomicU64::new(1);

#[derive(Debug, Deserialize, Serialize)]
struct UpdaterEvidence {
    schema_version: String,
    event_id: String,
    recorded_at_unix_ms: u64,
    state: String,
    current_version: String,
    target_version: Option<String>,
    safe_to_close: Option<bool>,
    detail: String,
}

impl UpdaterEvidence {
    fn new(
        state: &str,
        current_version: &str,
        target_version: Option<&str>,
        safe_to_close: Option<bool>,
        detail: &str,
    ) -> Self {
        let recorded_at_unix_ms = unix_time_ms();
        let sequence = EVIDENCE_SEQUENCE.fetch_add(1, Ordering::Relaxed);
        Self {
            schema_version: EVIDENCE_SCHEMA_VERSION.to_string(),
            event_id: format!(
                "native-updater-{recorded_at_unix_ms}-{}-{sequence}",
                std::process::id()
            ),
            recorded_at_unix_ms,
            state: bounded_evidence_text(state),
            current_version: bounded_evidence_text(current_version),
            target_version: target_version.map(bounded_evidence_text),
            safe_to_close,
            detail: bounded_evidence_text(detail),
        }
    }
}

pub(crate) fn schedule_native_update_check(app: AppHandle) {
    if !updater_artifact_mode_enabled(&app.config().bundle.create_updater_artifacts) {
        eprintln!(
            "[mediapipeline-shell] native updater check skipped: updater artifacts are disabled"
        );
        return;
    }
    tauri::async_runtime::spawn(async move {
        run_native_update_check(app).await;
    });
}

async fn run_native_update_check(app: AppHandle) {
    let current_version = app.package_info().version.to_string();
    reconcile_previous_install_handoff(&app, &current_version);
    record_optional_event(
        &app,
        UpdaterEvidence::new(
            "check_started",
            &current_version,
            None,
            None,
            "Checking the configured signed updater channel.",
        ),
    );

    let updater = match app.updater() {
        Ok(updater) => updater,
        Err(error) => {
            record_updater_failure(&app, "configuration_failed", &current_version, None, &error);
            show_update_notice_dialog(
                "MediaPipeline update check unavailable",
                "The signed updater could not be initialized. No download or installation was attempted. Use the documented manual installer path or restart the app to retry.",
            );
            return;
        }
    };
    let update = match updater.check().await {
        Ok(Some(update)) => update,
        Ok(None) => {
            record_optional_event(
                &app,
                UpdaterEvidence::new(
                    "no_update",
                    &current_version,
                    None,
                    None,
                    "The installed version is current for the configured channel.",
                ),
            );
            return;
        }
        Err(error) => {
            record_updater_failure(&app, "check_failed", &current_version, None, &error);
            show_update_notice_dialog(
                "MediaPipeline update check failed",
                "The signed update channel could not be checked. No download or installation was attempted. The app will check again on its next launch; the documented manual installer remains available.",
            );
            return;
        }
    };

    let target_version = bounded_evidence_text(&update.version);
    if !record_required_event(
        &app,
        UpdaterEvidence::new(
            "update_available",
            &current_version,
            Some(&target_version),
            None,
            "A newer signed-channel version is available.",
        ),
    ) {
        return;
    }
    if !confirm_update_download_dialog(&current_version, &target_version) {
        record_optional_event(
            &app,
            UpdaterEvidence::new(
                "download_declined",
                &current_version,
                Some(&target_version),
                None,
                "The operator declined the download prompt.",
            ),
        );
        return;
    }
    if !record_required_event(
        &app,
        UpdaterEvidence::new(
            "download_started",
            &current_version,
            Some(&target_version),
            None,
            "Downloading the update package before signature verification.",
        ),
    ) {
        return;
    }

    let bytes = match update.download(|_, _| {}, || {}).await {
        Ok(bytes) => bytes,
        Err(error) => {
            record_updater_failure(
                &app,
                "download_or_verification_failed",
                &current_version,
                Some(&target_version),
                &error,
            );
            show_update_notice_dialog(
                "MediaPipeline update download rejected",
                "The update package could not be downloaded or its signature could not be verified. Nothing was installed and the backend remains running. Restart the app to retry or use the documented manual installer path.",
            );
            return;
        }
    };
    if !record_required_event(
        &app,
        UpdaterEvidence::new(
            "download_verified",
            &current_version,
            Some(&target_version),
            None,
            "The complete update package was downloaded and its signature verified.",
        ),
    ) {
        return;
    }
    if !confirm_update_install_dialog(&target_version) {
        record_optional_event(
            &app,
            UpdaterEvidence::new(
                "install_declined",
                &current_version,
                Some(&target_version),
                None,
                "The operator declined installation after verified download.",
            ),
        );
        return;
    }

    let readiness = match fresh_close_readiness(&app) {
        Ok(readiness) => readiness,
        Err(_) => {
            record_optional_event(
                &app,
                UpdaterEvidence::new(
                    "close_readiness_unverified",
                    &current_version,
                    Some(&target_version),
                    Some(false),
                    "Close-readiness could not be verified; installation was blocked.",
                ),
            );
            show_update_notice_dialog(
                "MediaPipeline update installation blocked",
                "Close-readiness could not be verified, so the backend was not stopped and the update was not installed. Resolve backend diagnostics and restart the app to retry.",
            );
            return;
        }
    };
    if let Some(detail) = install_block_reason(&readiness) {
        record_optional_event(
            &app,
            UpdaterEvidence::new(
                "close_readiness_blocked",
                &current_version,
                Some(&target_version),
                Some(false),
                "Backend close-readiness reported active or unsafe work; installation was blocked.",
            ),
        );
        show_update_notice_dialog(
            "MediaPipeline update installation blocked",
            &format!(
                "{detail}\n\nNo force-close option is available for update installation. Finish or safely stop active work, then restart the app to retry."
            ),
        );
        return;
    }
    if !record_required_event(
        &app,
        UpdaterEvidence::new(
            "install_close_ready",
            &current_version,
            Some(&target_version),
            Some(true),
            "Fresh backend close-readiness permitted safe-only shutdown.",
        ),
    ) {
        return;
    }

    match shutdown_backend_state(&app, BackendShutdownMode::SafeOnly) {
        BackendShutdownOutcome::Requested => {}
        BackendShutdownOutcome::Blocked | BackendShutdownOutcome::Failed => {
            record_optional_event(
                &app,
                UpdaterEvidence::new(
                    "backend_shutdown_blocked",
                    &current_version,
                    Some(&target_version),
                    Some(false),
                    "Safe-only backend shutdown did not complete; installation was blocked.",
                ),
            );
            show_update_notice_dialog(
                "MediaPipeline update installation blocked",
                "The backend did not complete a safe-only shutdown, so the update was not installed. Resolve backend diagnostics and restart the app to retry.",
            );
            return;
        }
    }
    if !record_required_event(
        &app,
        UpdaterEvidence::new(
            "install_started",
            &current_version,
            Some(&target_version),
            Some(true),
            "Safe-only backend shutdown completed; handing the verified package to the installer.",
        ),
    ) {
        restart_after_stopped_backend(&app);
    }

    if let Err(error) = update.install(bytes) {
        record_updater_failure(
            &app,
            "install_failed",
            &current_version,
            Some(&target_version),
            &error,
        );
        show_update_notice_dialog(
            "MediaPipeline update installation failed",
            "The verified update could not be handed to the installer after the backend stopped. The current app will restart to restore service; use updater evidence and the documented manual installer path for recovery.",
        );
        app.restart();
    }
}

fn fresh_close_readiness(app: &AppHandle) -> ShellResult<CloseReadiness> {
    let (backend_url, token) = {
        let backend = app.try_state::<BackendProcess>().ok_or_else(|| {
            shell_error("Backend state is unavailable for updater close-readiness.")
        })?;
        (backend.url().to_string(), backend.token().to_string())
    };
    request_close_readiness(&backend_url, &token)
}

fn install_block_reason(readiness: &CloseReadiness) -> Option<String> {
    if readiness.safe_to_close {
        None
    } else {
        Some(close_readiness_warning_detail(readiness))
    }
}

fn updater_artifact_mode_enabled(mode: &UpdaterArtifactMode) -> bool {
    match mode {
        UpdaterArtifactMode::Bool(enabled) => *enabled,
        UpdaterArtifactMode::String(_) => true,
    }
}

fn updater_failure_class(error: &UpdaterError) -> &'static str {
    match error {
        UpdaterError::Network(_) | UpdaterError::Reqwest(_) | UpdaterError::ReleaseNotFound => {
            "network_or_channel"
        }
        UpdaterError::Minisign(_) | UpdaterError::Base64(_) | UpdaterError::SignatureUtf8(_) => {
            "signature_verification"
        }
        _ => "updater",
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum PreviousInstallOutcome {
    Applied,
    RecoveryRequired,
}

fn previous_install_outcome(
    event: &UpdaterEvidence,
    current_version: &str,
) -> Option<PreviousInstallOutcome> {
    if event.schema_version != EVIDENCE_SCHEMA_VERSION || event.state != "install_started" {
        return None;
    }
    match event.target_version.as_deref() {
        Some(target_version) if target_version == current_version => {
            Some(PreviousInstallOutcome::Applied)
        }
        Some(_) => Some(PreviousInstallOutcome::RecoveryRequired),
        None => None,
    }
}

fn reconcile_previous_install_handoff(app: &AppHandle, current_version: &str) {
    let root = match updater_evidence_directory(app) {
        Ok(root) => root,
        Err(error) => {
            eprintln!("[mediapipeline-shell] updater recovery evidence root failed: {error}");
            return;
        }
    };
    let previous = match read_latest_event(&root) {
        Ok(previous) => previous,
        Err(error) => {
            eprintln!("[mediapipeline-shell] updater recovery evidence read failed: {error}");
            show_update_notice_dialog(
                "MediaPipeline update recovery evidence unavailable",
                "The last native updater event could not be validated. The app will continue without treating an earlier installer handoff as successful. Preserve the updater evidence directory and use the documented manual installer path if the installed version is unexpected.",
            );
            return;
        }
    };
    let Some(previous) = previous else {
        return;
    };
    match previous_install_outcome(&previous, current_version) {
        Some(PreviousInstallOutcome::Applied) => record_optional_event(
            app,
            UpdaterEvidence::new(
                "install_applied",
                current_version,
                previous.target_version.as_deref(),
                None,
                "The version launched after installer handoff matches the requested target.",
            ),
        ),
        Some(PreviousInstallOutcome::RecoveryRequired) => {
            record_optional_event(
                app,
                UpdaterEvidence::new(
                    "install_recovery_required",
                    current_version,
                    previous.target_version.as_deref(),
                    None,
                    "The version launched after installer handoff does not match the requested target.",
                ),
            );
            show_update_notice_dialog(
                "MediaPipeline update requires recovery",
                "The installed version did not advance after the previous installer handoff. The current version is running again. Preserve native updater evidence and use the documented signed manual installer or rollback path.",
            );
        }
        None => {}
    }
}

fn record_updater_failure(
    app: &AppHandle,
    state: &str,
    current_version: &str,
    target_version: Option<&str>,
    error: &UpdaterError,
) {
    let failure_class = updater_failure_class(error);
    eprintln!(
        "[mediapipeline-shell] native updater state '{state}' ({failure_class}); raw remote error omitted"
    );
    record_optional_event(
        app,
        UpdaterEvidence::new(
            state,
            current_version,
            target_version,
            None,
            &format!("Updater failure class: {failure_class}. Raw remote error omitted."),
        ),
    );
}

fn record_required_event(app: &AppHandle, event: UpdaterEvidence) -> bool {
    if let Err(error) = record_event(app, &event) {
        eprintln!("[mediapipeline-shell] required updater evidence failed: {error}");
        show_update_notice_dialog(
            "MediaPipeline update paused",
            "Required native updater evidence could not be written. No installation action will continue. Check local application-data permissions, then restart the app to retry or use the documented manual installer path.",
        );
        return false;
    }
    true
}

fn record_optional_event(app: &AppHandle, event: UpdaterEvidence) {
    if let Err(error) = record_event(app, &event) {
        eprintln!("[mediapipeline-shell] updater evidence write failed: {error}");
    }
}

fn record_event(app: &AppHandle, event: &UpdaterEvidence) -> ShellResult<PathBuf> {
    write_event_to_directory(&updater_evidence_directory(app)?, event)
}

fn updater_evidence_directory(app: &AppHandle) -> ShellResult<PathBuf> {
    Ok(app
        .path()
        .app_local_data_dir()
        .map_err(|error| shell_error(format!("Could not resolve updater evidence root: {error}")))?
        .join(EVIDENCE_DIRECTORY))
}

fn write_event_to_directory(root: &Path, event: &UpdaterEvidence) -> ShellResult<PathBuf> {
    fs::create_dir_all(root).map_err(|error| {
        shell_error(format!(
            "Could not create native updater evidence directory: {error}"
        ))
    })?;
    cleanup_orphaned_temporary_files(root)?;
    let file_name = format!("{EVIDENCE_FILE_PREFIX}{}.json", event.event_id);
    let destination = root.join(&file_name);
    let temporary = root.join(format!(".{file_name}.tmp"));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)
        .map_err(|error| {
            shell_error(format!(
                "Could not create updater evidence temp file: {error}"
            ))
        })?;
    serde_json::to_writer_pretty(&mut file, event)
        .map_err(|error| shell_error(format!("Could not serialize updater evidence: {error}")))?;
    file.write_all(b"\n")
        .and_then(|_| file.sync_all())
        .map_err(|error| shell_error(format!("Could not persist updater evidence: {error}")))?;
    drop(file);
    fs::rename(&temporary, &destination).map_err(|error| {
        let _ = fs::remove_file(&temporary);
        shell_error(format!(
            "Could not publish updater evidence atomically: {error}"
        ))
    })?;
    prune_evidence_files(root)?;
    Ok(destination)
}

fn read_latest_event(root: &Path) -> ShellResult<Option<UpdaterEvidence>> {
    if !root.exists() {
        return Ok(None);
    }
    let Some(path) = updater_evidence_files(root)?.pop() else {
        return Ok(None);
    };
    let metadata = fs::symlink_metadata(&path)
        .map_err(|error| shell_error(format!("Could not inspect updater evidence: {error}")))?;
    if !metadata.file_type().is_file() || metadata.len() > MAX_EVIDENCE_FILE_BYTES {
        return Err(shell_error(
            "Latest updater evidence is not a bounded regular file.",
        ));
    }
    let payload = fs::read_to_string(&path)
        .map_err(|error| shell_error(format!("Could not read updater evidence: {error}")))?;
    let event: UpdaterEvidence = serde_json::from_str(&payload)
        .map_err(|error| shell_error(format!("Latest updater evidence is invalid: {error}")))?;
    if event.schema_version != EVIDENCE_SCHEMA_VERSION {
        return Err(shell_error(
            "Latest updater evidence schema is unsupported.",
        ));
    }
    Ok(Some(event))
}

fn updater_evidence_files(root: &Path) -> ShellResult<Vec<PathBuf>> {
    let mut files = fs::read_dir(root)
        .map_err(|error| shell_error(format!("Could not enumerate updater evidence: {error}")))?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|value| value.to_str())
                .is_some_and(|name| {
                    name.starts_with(EVIDENCE_FILE_PREFIX) && name.ends_with(".json")
                })
        })
        .collect::<Vec<_>>();
    files.sort();
    Ok(files)
}

fn prune_evidence_files(root: &Path) -> ShellResult<()> {
    let files = updater_evidence_files(root)?;
    let remove_count = files.len().saturating_sub(MAX_EVIDENCE_FILES);
    for path in files.into_iter().take(remove_count) {
        fs::remove_file(path).map_err(|error| {
            shell_error(format!(
                "Could not prune superseded updater evidence: {error}"
            ))
        })?;
    }
    Ok(())
}

fn cleanup_orphaned_temporary_files(root: &Path) -> ShellResult<()> {
    for entry in fs::read_dir(root)
        .map_err(|error| shell_error(format!("Could not enumerate updater evidence: {error}")))?
    {
        let entry = entry
            .map_err(|error| shell_error(format!("Could not inspect updater evidence: {error}")))?;
        let name = entry.file_name();
        let Some(name) = name.to_str() else {
            continue;
        };
        if name.starts_with(&format!(".{EVIDENCE_FILE_PREFIX}")) && name.ends_with(".json.tmp") {
            let metadata = entry.metadata().map_err(|error| {
                shell_error(format!(
                    "Could not inspect updater evidence temp file: {error}"
                ))
            })?;
            if metadata.is_file() {
                fs::remove_file(entry.path()).map_err(|error| {
                    shell_error(format!(
                        "Could not remove updater evidence temp file: {error}"
                    ))
                })?;
            }
        }
    }
    Ok(())
}

fn restart_after_stopped_backend(app: &AppHandle) -> ! {
    show_update_notice_dialog(
        "MediaPipeline update paused",
        "The backend stopped safely, but required installation evidence could not be written. The current app will restart without installing the update.",
    );
    app.restart();
}

fn unix_time_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .min(u128::from(u64::MAX)) as u64
}

fn bounded_evidence_text(value: &str) -> String {
    let mut output = String::new();
    for (index, ch) in value.chars().enumerate() {
        if index >= MAX_EVIDENCE_TEXT_CHARS {
            output.push_str("...");
            break;
        }
        if ch.is_control() {
            if !output.ends_with(' ') {
                output.push(' ');
            }
        } else {
            output.push(ch);
        }
    }
    output.trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::{
        bounded_evidence_text, install_block_reason, previous_install_outcome, read_latest_event,
        updater_artifact_mode_enabled, updater_failure_class, write_event_to_directory,
        PreviousInstallOutcome, UpdaterEvidence, EVIDENCE_SCHEMA_VERSION, MAX_EVIDENCE_FILES,
    };
    use crate::close_readiness::{CloseReadiness, ContinuousWatcher};
    use std::{fs, path::PathBuf};
    use tauri::utils::config::{Updater as UpdaterArtifactMode, V1Compatible};
    use tauri_plugin_updater::Error as UpdaterError;

    fn readiness(safe_to_close: bool) -> CloseReadiness {
        CloseReadiness {
            schema_version: "desktop_close_readiness.v1".to_string(),
            safe_to_close,
            state: if safe_to_close { "idle" } else { "processing" }.to_string(),
            reason: if safe_to_close {
                "No active work.".to_string()
            } else {
                "An encode is active.".to_string()
            },
            warnings: Vec::new(),
            continuous_watcher: ContinuousWatcher::default(),
        }
    }

    fn unique_test_directory(label: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "mediapipeline-updater-controller-{label}-{}-{}",
            std::process::id(),
            super::unix_time_ms()
        ))
    }

    #[test]
    fn updater_check_is_enabled_only_for_artifact_builds() {
        assert!(!updater_artifact_mode_enabled(&UpdaterArtifactMode::Bool(
            false
        )));
        assert!(updater_artifact_mode_enabled(&UpdaterArtifactMode::Bool(
            true
        )));
        assert!(updater_artifact_mode_enabled(&UpdaterArtifactMode::String(
            V1Compatible::V1Compatible
        )));
    }

    #[test]
    fn unsafe_close_readiness_blocks_installation_without_force_path() {
        let detail = install_block_reason(&readiness(false)).expect("unsafe work must block");
        assert!(detail.contains("An encode is active."));
        assert!(install_block_reason(&readiness(true)).is_none());
    }

    #[test]
    fn updater_failure_classes_separate_network_and_signature_rejection() {
        assert_eq!(
            updater_failure_class(&UpdaterError::Network("offline".to_string())),
            "network_or_channel"
        );
        assert_eq!(
            updater_failure_class(&UpdaterError::SignatureUtf8("bad signature".to_string())),
            "signature_verification"
        );
        assert_eq!(
            updater_failure_class(&UpdaterError::EmptyEndpoints),
            "updater"
        );
    }

    #[test]
    fn next_launch_reconciles_installer_handoff_by_exact_target_version() {
        let event = UpdaterEvidence::new(
            "install_started",
            "2026.6.4+001",
            Some("2026.6.5+001"),
            Some(true),
            "handoff",
        );
        assert_eq!(
            previous_install_outcome(&event, "2026.6.5+001"),
            Some(PreviousInstallOutcome::Applied)
        );
        assert_eq!(
            previous_install_outcome(&event, "2026.6.4+001"),
            Some(PreviousInstallOutcome::RecoveryRequired)
        );
        let unrelated = UpdaterEvidence::new(
            "install_failed",
            "2026.6.4+001",
            Some("2026.6.5+001"),
            Some(true),
            "failed",
        );
        assert_eq!(previous_install_outcome(&unrelated, "2026.6.4+001"), None);
    }

    #[test]
    fn evidence_is_atomic_bounded_and_retained() {
        let root = unique_test_directory("evidence");
        for index in 0..(MAX_EVIDENCE_FILES + 3) {
            let event = UpdaterEvidence::new(
                "download_verified",
                "2026.6.4+001",
                Some(&format!("2026.6.5+{index:03}")),
                None,
                "verified",
            );
            write_event_to_directory(&root, &event).expect("write evidence");
        }
        let entries = fs::read_dir(&root)
            .expect("read evidence directory")
            .filter_map(Result::ok)
            .collect::<Vec<_>>();
        assert_eq!(entries.len(), MAX_EVIDENCE_FILES);
        assert!(entries.iter().all(|entry| {
            entry
                .file_name()
                .to_string_lossy()
                .starts_with("update-event-")
        }));
        let payload: serde_json::Value = serde_json::from_str(
            &fs::read_to_string(entries[0].path()).expect("read evidence payload"),
        )
        .expect("parse evidence payload");
        assert_eq!(payload["schema_version"], EVIDENCE_SCHEMA_VERSION);
        assert_eq!(payload["state"], "download_verified");
        let latest = read_latest_event(&root)
            .expect("read latest evidence")
            .expect("latest evidence exists");
        assert_eq!(latest.schema_version, EVIDENCE_SCHEMA_VERSION);
        fs::remove_dir_all(root).expect("remove test evidence directory");
    }

    #[test]
    fn remote_text_is_bounded_and_control_characters_are_removed() {
        let value = format!("2026.6.5\nsecret\t{}", "x".repeat(400));
        let bounded = bounded_evidence_text(&value);
        assert!(!bounded.contains('\n'));
        assert!(!bounded.contains('\t'));
        assert!(bounded.ends_with("..."));
        assert!(bounded.chars().count() <= 243);
    }
}
