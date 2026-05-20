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
        .ok_or_else(|| shell_error("Could not resolve DesktopApp root from CARGO_MANIFEST_DIR."))?;
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
        if candidate.join("mediapipeline_desktop_app").exists() {
            return Ok(candidate.clone());
        }
    }
    if dev_desktop_root.join("mediapipeline_desktop_app").exists() {
        return Ok(dev_desktop_root);
    }
    Err(shell_error(format!(
        "Could not locate DesktopApp root for the Python backend. Development root checked: {}; executable: {}; packaged candidates checked: {}",
        display_bounded_path(&dev_desktop_root),
        display_bounded_path(&exe),
        format_path_candidates(&candidates)
    )))
}

pub(crate) fn desktop_root_candidates_from_exe_dir(exe_dir: &Path) -> Vec<PathBuf> {
    vec![
        exe_dir.join("DesktopApp"),
        exe_dir.join("..").join("DesktopApp"),
        exe_dir.join("..").join("..").join("DesktopApp"),
    ]
}

pub(crate) fn resolve_python(desktop_root: &Path) -> ShellResult<PathBuf> {
    let candidates = vec![
        desktop_root
            .join("Runtime")
            .join("Python")
            .join("python.exe"),
        desktop_root
            .parent()
            .unwrap_or(desktop_root)
            .join("Pipeline")
            .join("Runtime")
            .join("Python")
            .join("python.exe"),
    ];
    for candidate in &candidates {
        if candidate.exists() {
            return Ok(candidate.clone());
        }
    }
    Err(shell_error(format!(
        "Bundled Python runtime was not found for DesktopApp root '{}'. Checked: {}",
        display_bounded_path(desktop_root),
        format_path_candidates(&candidates)
    )))
}
