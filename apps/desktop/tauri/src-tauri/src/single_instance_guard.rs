use crate::ShellResult;

#[cfg(windows)]
use windows_sys::Win32::{
    Foundation::{CloseHandle, GetLastError, ERROR_ALREADY_EXISTS, HANDLE},
    System::Threading::CreateMutexW,
};

#[cfg(windows)]
const SINGLE_INSTANCE_MUTEX_NAME: &str = "Local\\MediaPipelineRemuxEncodeAIO_TauriShell";

pub(crate) struct SingleInstanceGuard {
    #[cfg(windows)]
    handle: isize,
}

#[cfg(windows)]
pub(crate) fn acquire_single_instance_guard() -> ShellResult<SingleInstanceGuard> {
    let wide_name = wide_null(SINGLE_INSTANCE_MUTEX_NAME);
    let handle = unsafe { CreateMutexW(std::ptr::null(), 1, wide_name.as_ptr()) };
    if handle.is_null() {
        return Err(format!(
            "Could not create Tauri single-instance guard `{SINGLE_INSTANCE_MUTEX_NAME}`."
        )
        .into());
    }
    if unsafe { GetLastError() } == ERROR_ALREADY_EXISTS {
        unsafe {
            CloseHandle(handle);
        }
        return Err(
            "Another MediaPipeline Tauri/WebView2 shell instance is already running. Use the existing window or close it before launching another preview shell."
                .into(),
        );
    }
    Ok(SingleInstanceGuard {
        handle: handle as isize,
    })
}

#[cfg(not(windows))]
pub(crate) fn acquire_single_instance_guard() -> ShellResult<SingleInstanceGuard> {
    Ok(SingleInstanceGuard {})
}

#[cfg(windows)]
impl Drop for SingleInstanceGuard {
    fn drop(&mut self) {
        let handle = self.handle as HANDLE;
        if !handle.is_null() {
            unsafe {
                CloseHandle(handle);
            }
        }
    }
}

#[cfg(windows)]
fn wide_null(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(std::iter::once(0)).collect()
}
