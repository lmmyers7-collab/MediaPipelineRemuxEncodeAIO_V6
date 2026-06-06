use std::{
    env,
    error::Error,
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
    vec![
        exe_dir.join(".."),
        exe_dir.join("apps").join("desktop"),
        exe_dir.join("..").join("..").join("apps").join("desktop"),
    ]
}

pub(crate) fn project_root_from_desktop_root(desktop_root: &Path) -> PathBuf {
    desktop_root
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or_else(|| desktop_root.to_path_buf())
}

pub(crate) fn resolve_python(desktop_root: &Path) -> ShellResult<PathBuf> {
    let project_root = project_root_from_desktop_root(desktop_root);
    let candidates = vec![
        desktop_root
            .join("runtime")
            .join("Python")
            .join("python.exe"),
        project_root
            .join("ops")
            .join("pipeline")
            .join("runtime")
            .join("Python")
            .join("python.exe"),
        PathBuf::from("python"),
    ];
    for candidate in &candidates {
        if candidate == Path::new("python") || candidate.exists() {
            return Ok(candidate.clone());
        }
    }
    Err(shell_error(format!(
        "Python runtime was not found for apps/desktop root '{}'. Checked bundled runtime paths and python on PATH: {}",
        display_bounded_path(desktop_root),
        format_path_candidates(&candidates)
    )))
}
