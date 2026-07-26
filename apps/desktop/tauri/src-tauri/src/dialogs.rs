use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::{
    env,
    error::Error,
    fs::File,
    io::Read,
    path::{Path, PathBuf},
};

use crate::http_helpers::bounded_text;
use crate::{ShellResult, MAX_OPERATOR_PATH_CHARS};

pub(crate) fn shell_error(message: impl Into<String>) -> Box<dyn Error> {
    Box::new(std::io::Error::new(
        std::io::ErrorKind::Other,
        message.into(),
    ))
}

pub(crate) fn display_bounded_path(path: &Path) -> String {
    bounded_text(&path.display().to_string(), MAX_OPERATOR_PATH_CHARS)
}

pub(crate) fn format_path_candidates(candidates: &[PathBuf]) -> String {
    candidates
        .iter()
        .map(|candidate| display_bounded_path(candidate))
        .collect::<Vec<String>>()
        .join("; ")
}

#[cfg(target_os = "windows")]
pub(crate) fn confirm_close_dialog(message: &str) -> bool {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        MessageBoxW, IDOK, MB_DEFBUTTON2, MB_ICONWARNING, MB_OKCANCEL,
    };

    fn wide(value: &str) -> Vec<u16> {
        value.encode_utf16().chain(std::iter::once(0)).collect()
    }

    let title = wide("MediaPipeline active work");
    let body = wide(message);
    let result = unsafe {
        MessageBoxW(
            std::ptr::null_mut(),
            body.as_ptr(),
            title.as_ptr(),
            MB_OKCANCEL | MB_ICONWARNING | MB_DEFBUTTON2,
        )
    };
    result == IDOK
}

#[cfg(not(target_os = "windows"))]
pub(crate) fn confirm_close_dialog(message: &str) -> bool {
    eprintln!("[mediapipeline-shell] close readiness warning: {message}");
    false
}

#[cfg(target_os = "windows")]
fn confirm_update_dialog(title: &str, message: &str) -> bool {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        MessageBoxW, IDYES, MB_DEFBUTTON2, MB_ICONINFORMATION, MB_YESNO,
    };

    fn wide(value: &str) -> Vec<u16> {
        value.encode_utf16().chain(std::iter::once(0)).collect()
    }

    let title = wide(title);
    let body = wide(message);
    let result = unsafe {
        MessageBoxW(
            std::ptr::null_mut(),
            body.as_ptr(),
            title.as_ptr(),
            MB_YESNO | MB_ICONINFORMATION | MB_DEFBUTTON2,
        )
    };
    result == IDYES
}

#[cfg(not(target_os = "windows"))]
fn confirm_update_dialog(title: &str, message: &str) -> bool {
    eprintln!("[mediapipeline-shell] {title}: {message}");
    false
}

pub(crate) fn confirm_update_download_dialog(current_version: &str, target_version: &str) -> bool {
    confirm_update_dialog(
        "MediaPipeline update available",
        &format!(
            "A signed MediaPipeline update is available.\n\nInstalled: {current_version}\nAvailable: {target_version}\n\nDownload and verify it now? No work will be stopped and nothing will be installed during this step."
        ),
    )
}

pub(crate) fn confirm_update_install_dialog(target_version: &str) -> bool {
    confirm_update_dialog(
        "Install verified MediaPipeline update",
        &format!(
            "MediaPipeline {target_version} has been downloaded and its signature verified.\n\nInstall it now? The app will first verify that no active work is running, safely stop its backend, launch the installer, and restart through the installer.\n\nIf close-readiness cannot be proven safe, installation will be blocked."
        ),
    )
}

#[cfg(target_os = "windows")]
pub(crate) fn show_update_notice_dialog(title: &str, message: &str) {
    use windows_sys::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONWARNING, MB_OK};

    fn wide(value: &str) -> Vec<u16> {
        value.encode_utf16().chain(std::iter::once(0)).collect()
    }

    let title = wide(title);
    let body = wide(message);
    unsafe {
        MessageBoxW(
            std::ptr::null_mut(),
            body.as_ptr(),
            title.as_ptr(),
            MB_OK | MB_ICONWARNING,
        );
    }
}

#[cfg(not(target_os = "windows"))]
pub(crate) fn show_update_notice_dialog(title: &str, message: &str) {
    eprintln!("[mediapipeline-shell] {title}: {message}");
}

pub(crate) fn resolve_desktop_root() -> ShellResult<PathBuf> {
    let manifest_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let dev_desktop_root = manifest_root
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .ok_or_else(|| {
            shell_error("Could not resolve apps/desktop root from CARGO_MANIFEST_DIR.")
        })?;
    let exe = std::env::current_exe().map_err(|error| {
        shell_error(format!(
            "Could not resolve current executable path: {error}"
        ))
    })?;
    let exe_dir = exe
        .parent()
        .ok_or_else(|| shell_error("Could not resolve executable directory."))?;
    let candidates = desktop_root_candidates_from_exe_dir(exe_dir);
    for candidate in &candidates {
        if is_desktop_app_root(candidate) {
            return Ok(candidate.clone());
        }
    }
    if is_desktop_app_root(&dev_desktop_root) {
        return Ok(dev_desktop_root);
    }
    Err(shell_error(format!(
        "Could not locate apps/desktop root for the Python backend. Development root checked: {}; executable: {}; packaged candidates checked: {}",
        display_bounded_path(&dev_desktop_root),
        display_bounded_path(&exe),
        format_path_candidates(&candidates)
    )))
}

fn is_desktop_app_root(candidate: &Path) -> bool {
    candidate
        .join("webview")
        .join("static")
        .join("index.html")
        .exists()
}

pub(crate) fn desktop_root_candidates_from_exe_dir(exe_dir: &Path) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Some(parent) = exe_dir.parent() {
        candidates.push(parent.to_path_buf());
    }
    candidates.push(exe_dir.join("apps").join("desktop"));
    if let Some(parent) = exe_dir.parent().and_then(Path::parent) {
        candidates.push(parent.join("apps").join("desktop"));
    }
    candidates
}

pub(crate) fn project_root_from_desktop_root(desktop_root: &Path) -> PathBuf {
    desktop_root
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or_else(|| desktop_root.to_path_buf())
}

pub(crate) fn resolve_python(desktop_root: &Path) -> ShellResult<PathBuf> {
    resolve_python_for_mode(desktop_root, cfg!(debug_assertions))
}

pub(crate) fn resolve_python_for_mode(
    desktop_root: &Path,
    allow_ambient_python: bool,
) -> ShellResult<PathBuf> {
    let project_root = project_root_from_desktop_root(desktop_root);
    let bundled_python = desktop_root
        .join("runtime")
        .join("Python")
        .join("python.exe");
    if !allow_ambient_python {
        if !bundled_python.is_file() {
            return Err(shell_error(format!(
                "Productized startup requires the bundled Python runtime at '{}'; PATH fallback is disabled.",
                display_bounded_path(&bundled_python)
            )));
        }
        verify_release_python(&project_root, &bundled_python)?;
        return Ok(bundled_python);
    }

    let candidates = vec![
        bundled_python,
        project_root
            .join("ops")
            .join("pipeline")
            .join("runtime")
            .join("Python")
            .join("python.exe"),
        PathBuf::from("python"),
    ];
    for candidate in &candidates {
        if candidate == Path::new("python") || candidate.is_file() {
            return Ok(candidate.clone());
        }
    }
    Err(shell_error(format!(
        "Python runtime was not found for apps/desktop root '{}'. Checked bundled runtime paths and python on PATH: {}",
        display_bounded_path(desktop_root),
        format_path_candidates(&candidates)
    )))
}

const RELEASE_MANIFEST_MAX_BYTES: u64 = 64 * 1024 * 1024;
const BUNDLED_PYTHON_MANIFEST_PATH: &str = "apps/desktop/runtime/Python/python.exe";

#[derive(Deserialize)]
struct ReleaseManifest {
    schema_version: String,
    integrity: ReleaseManifestIntegrity,
}

#[derive(Deserialize)]
struct ReleaseManifestIntegrity {
    algorithm: String,
    files: Vec<ReleaseManifestFile>,
}

#[derive(Deserialize)]
struct ReleaseManifestFile {
    path: String,
    sha256: String,
    bytes: u64,
}

fn normalized_manifest_path(value: &str) -> String {
    value.replace('\\', "/").trim_start_matches('/').to_string()
}

fn verify_release_python(project_root: &Path, python: &Path) -> ShellResult<()> {
    let manifest_path = project_root.join("release_manifest.json");
    let manifest_metadata = manifest_path.metadata().map_err(|error| {
        shell_error(format!(
            "Productized startup requires release manifest '{}': {error}",
            display_bounded_path(&manifest_path)
        ))
    })?;
    if !manifest_metadata.is_file() || manifest_metadata.len() > RELEASE_MANIFEST_MAX_BYTES {
        return Err(shell_error(format!(
            "Release manifest '{}' is not a bounded regular file.",
            display_bounded_path(&manifest_path)
        )));
    }
    let manifest_text = std::fs::read_to_string(&manifest_path).map_err(|error| {
        shell_error(format!(
            "Could not read release manifest '{}': {error}",
            display_bounded_path(&manifest_path)
        ))
    })?;
    let manifest: ReleaseManifest = serde_json::from_str(&manifest_text).map_err(|error| {
        shell_error(format!(
            "Release manifest '{}' is invalid JSON: {error}",
            display_bounded_path(&manifest_path)
        ))
    })?;
    if manifest.schema_version != "mediapipeline_release_manifest.v1"
        || !manifest.integrity.algorithm.eq_ignore_ascii_case("sha256")
    {
        return Err(shell_error(
            "Release manifest schema or integrity algorithm is not supported for productized startup.",
        ));
    }
    let matching = manifest
        .integrity
        .files
        .iter()
        .filter(|entry| {
            normalized_manifest_path(&entry.path).eq_ignore_ascii_case(BUNDLED_PYTHON_MANIFEST_PATH)
        })
        .collect::<Vec<_>>();
    if matching.len() != 1 {
        return Err(shell_error(format!(
            "Release manifest must contain exactly one integrity entry for {BUNDLED_PYTHON_MANIFEST_PATH}; found {}.",
            matching.len()
        )));
    }
    let entry = matching[0];
    let python_metadata = python.metadata().map_err(|error| {
        shell_error(format!(
            "Could not inspect bundled Python runtime '{}': {error}",
            display_bounded_path(python)
        ))
    })?;
    if python_metadata.len() != entry.bytes {
        return Err(shell_error(format!(
            "Bundled Python runtime size does not match release manifest evidence (expected {}, found {}).",
            entry.bytes,
            python_metadata.len()
        )));
    }
    let expected_hash = entry.sha256.trim().to_ascii_lowercase();
    if expected_hash.len() != 64 || !expected_hash.bytes().all(|value| value.is_ascii_hexdigit()) {
        return Err(shell_error(
            "Bundled Python release-manifest SHA-256 evidence is malformed.",
        ));
    }
    let actual_hash = sha256_file(python)?;
    if actual_hash != expected_hash {
        return Err(shell_error(
            "Bundled Python runtime SHA-256 does not match release manifest evidence.",
        ));
    }
    Ok(())
}

fn sha256_file(path: &Path) -> ShellResult<String> {
    let mut file = File::open(path).map_err(|error| {
        shell_error(format!(
            "Could not open bundled Python runtime '{}': {error}",
            display_bounded_path(path)
        ))
    })?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let count = file.read(&mut buffer).map_err(|error| {
            shell_error(format!(
                "Could not hash bundled Python runtime '{}': {error}",
                display_bounded_path(path)
            ))
        })?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}
