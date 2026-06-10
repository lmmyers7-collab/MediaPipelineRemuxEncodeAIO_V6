from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES, VLC_LONG_PATH_THRESHOLD

from .open_plan import (
    MKLINK_JUNCTION_TIMEOUT_SECONDS,
    build_vlc_launch_args,
    explorer_select_args,
    vlc_candidate_paths,
    vlc_creation_flags,
    vlc_needs_short_path,
)


WINDOWS_EXTENDED_PATH_PREFIX = "\\\\?\\"
WINDOWS_EXTENDED_UNC_PREFIX = "\\\\?\\UNC\\"
VLC_TEMP_JUNCTION_PREFIX = "mediapipeline-vlc-"
VLC_TEMP_JUNCTION_NAME = "m"
EXPLORER_WINDOW_CLASSES = {"CabinetWClass", "ExploreWClass"}
EXPLORER_FOREGROUND_RETRY_DELAYS_SECONDS = (0.0, 0.05, 0.1, 0.2, 0.4)
WINDOWS_SW_SHOWNORMAL = 1
WINDOWS_SW_RESTORE = 9


def _strip_windows_extended_path_prefix(path_text: str) -> str:
    if path_text.startswith(WINDOWS_EXTENDED_UNC_PREFIX):
        return "\\\\" + path_text[len(WINDOWS_EXTENDED_UNC_PREFIX):]
    if path_text.startswith(WINDOWS_EXTENDED_PATH_PREFIX):
        return path_text[len(WINDOWS_EXTENDED_PATH_PREFIX):]
    return path_text


def _path_from_file_uri(path_text: str) -> str:
    if os.name == "nt" and path_text.lower().startswith("file://?/"):
        candidate = unquote(path_text[len("file://?/"):]).replace("/", "\\")
        if candidate.upper().startswith("UNC\\"):
            return "\\\\" + candidate[4:]
        return candidate
    if os.name == "nt" and path_text.lower().startswith("file:\\?\\"):
        candidate = unquote(path_text[len("file:\\?\\"):]).replace("/", "\\")
        if candidate.upper().startswith("UNC\\"):
            return "\\\\" + candidate[4:]
        return candidate

    parsed = urlsplit(path_text)
    if parsed.scheme.lower() != "file":
        return path_text

    netloc = unquote(parsed.netloc)
    uri_path = unquote(parsed.path)
    if os.name != "nt":
        return uri_path

    if netloc and netloc.lower() not in ("localhost", "?"):
        return "\\\\" + netloc + uri_path.replace("/", "\\")

    if netloc == "?":
        candidate = uri_path.lstrip("/").replace("/", "\\")
        if candidate.upper().startswith("UNC\\"):
            return "\\\\" + candidate[4:]
        return candidate

    if uri_path.startswith("/?/"):
        uri_path = uri_path[3:]
    elif re.match(r"^/[A-Za-z]:", uri_path):
        uri_path = uri_path[1:]
    return uri_path.replace("/", "\\")


def _normalize_open_path_text(path_text: str) -> str:
    cleaned = path_text.strip().strip('"')
    if cleaned.lower().startswith("file:"):
        cleaned = _path_from_file_uri(cleaned)
    return _strip_windows_extended_path_prefix(cleaned)


def _coerce_open_path(path: Path | str | None) -> Path:
    if not path:
        raise RuntimeError("No path is available for this action.")
    return Path(_normalize_open_path_text(str(path)))


def _windows_native_path(path: Path) -> str:
    return _normalize_open_path_text(str(path))


def _windows_api_libraries() -> tuple[Any, Any] | None:
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return None
    return windll.user32, windll.kernel32


def _top_level_explorer_window_handles() -> list[int]:
    libraries = _windows_api_libraries()
    if libraries is None:
        return []
    user32, _kernel32 = libraries
    callback_factory = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
    callback_type = callback_factory(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
    handles: list[int] = []
    try:
        user32.EnumWindows.argtypes = [callback_type, ctypes.c_void_p]
        user32.EnumWindows.restype = ctypes.c_int
        user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        user32.IsWindowVisible.restype = ctypes.c_int
        user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        user32.GetClassNameW.restype = ctypes.c_int
    except (AttributeError, TypeError):
        pass

    def _visit(hwnd: int, _lparam: int) -> int:
        try:
            hwnd_value = int(hwnd or 0)
            if not hwnd_value:
                return 1
            hwnd_ref = ctypes.c_void_p(hwnd_value)
            if not user32.IsWindowVisible(hwnd_ref):
                return 1
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd_ref, class_name, len(class_name))
            if class_name.value in EXPLORER_WINDOW_CLASSES:
                handles.append(hwnd_value)
        except (AttributeError, OSError, ValueError):
            return 1
        return 1

    callback = callback_type(_visit)
    try:
        user32.EnumWindows(callback, 0)
    except (AttributeError, OSError):
        return []
    return handles


def _bring_window_to_foreground(hwnd: int) -> bool:
    libraries = _windows_api_libraries()
    if libraries is None or not hwnd:
        return False
    user32, kernel32 = libraries
    current_thread_id = 0
    attached_thread_ids: list[int] = []
    try:
        hwnd_ref = ctypes.c_void_p(hwnd)
        try:
            kernel32.GetCurrentThreadId.restype = ctypes.c_ulong
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
            user32.AttachThreadInput.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int]
            user32.AttachThreadInput.restype = ctypes.c_int
            user32.IsIconic.argtypes = [ctypes.c_void_p]
            user32.IsIconic.restype = ctypes.c_int
            user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.ShowWindow.restype = ctypes.c_int
            user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
            user32.BringWindowToTop.restype = ctypes.c_int
            user32.SetActiveWindow.argtypes = [ctypes.c_void_p]
            user32.SetActiveWindow.restype = ctypes.c_void_p
            user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
            user32.SetForegroundWindow.restype = ctypes.c_int
        except (AttributeError, TypeError):
            pass
        try:
            user32.AllowSetForegroundWindow(-1)
        except (AttributeError, OSError):
            pass

        current_thread_id = int(kernel32.GetCurrentThreadId())
        target_thread_id = int(user32.GetWindowThreadProcessId(hwnd_ref, None))
        foreground_hwnd = int(user32.GetForegroundWindow() or 0)
        foreground_thread_id = 0
        if foreground_hwnd:
            foreground_thread_id = int(
                user32.GetWindowThreadProcessId(ctypes.c_void_p(foreground_hwnd), None)
            )

        for thread_id in (target_thread_id, foreground_thread_id):
            if thread_id and thread_id != current_thread_id:
                try:
                    if user32.AttachThreadInput(current_thread_id, thread_id, True):
                        attached_thread_ids.append(thread_id)
                except (AttributeError, OSError):
                    continue

        show_mode = WINDOWS_SW_RESTORE if user32.IsIconic(hwnd_ref) else WINDOWS_SW_SHOWNORMAL
        user32.ShowWindow(hwnd_ref, show_mode)
        user32.BringWindowToTop(hwnd_ref)
        user32.SetActiveWindow(hwnd_ref)
        if user32.SetForegroundWindow(hwnd_ref):
            return True
        switch_to_this_window = getattr(user32, "SwitchToThisWindow", None)
        if switch_to_this_window is not None:
            try:
                switch_to_this_window.argtypes = [ctypes.c_void_p, ctypes.c_int]
                switch_to_this_window.restype = None
            except (AttributeError, TypeError):
                pass
            switch_to_this_window(hwnd_ref, True)
            return True
    except (AttributeError, OSError, ValueError):
        return False
    finally:
        if current_thread_id:
            for thread_id in reversed(attached_thread_ids):
                try:
                    user32.AttachThreadInput(current_thread_id, thread_id, False)
                except (AttributeError, OSError):
                    continue
    return False


def _focus_opened_explorer_window(existing_handles: set[int]) -> bool:
    for delay in EXPLORER_FOREGROUND_RETRY_DELAYS_SECONDS:
        if delay > 0:
            time.sleep(delay)
        handles = _top_level_explorer_window_handles()
        candidates = [hwnd for hwnd in handles if hwnd not in existing_handles] or handles[:1]
        for hwnd in candidates:
            if _bring_window_to_foreground(hwnd):
                return True
    return False


class FileOpenServiceMixin:
    def _find_vlc_executable(self) -> Path | None:
        if self._vlc_checked:
            return self._vlc_path

        self._vlc_checked = True
        for candidate in vlc_candidate_paths():
            try:
                if candidate.exists() and candidate.is_file():
                    self._vlc_path = candidate
                    return candidate
            except OSError:
                continue
        return None

    def _vlc_launch_path_for_media(self, path: Path) -> tuple[str, Path | None]:
        native_path = _windows_native_path(path)
        if not vlc_needs_short_path(native_path):
            return native_path, None

        root = Path(tempfile.mkdtemp(prefix=VLC_TEMP_JUNCTION_PREFIX))
        link = root / VLC_TEMP_JUNCTION_NAME
        try:
            subprocess.run(
                ["cmd", "/d", "/c", "mklink", "/J", str(link), _windows_native_path(path.parent)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=MKLINK_JUNCTION_TIMEOUT_SECONDS,
            )
            launch_path = link / path.name
            if not launch_path.exists() or len(str(launch_path)) >= len(native_path):
                self._cleanup_vlc_junction_root(root)
                return native_path, None
            return str(launch_path), root
        except Exception as exc:
            self._cleanup_vlc_junction_root(root)
            self.logger.warning("Failed to create short VLC junction for long media path: %s", exc)
            return native_path, None

    def _cleanup_vlc_junction_root(self, root: Path | None) -> None:
        if root is None:
            return
        link = root / VLC_TEMP_JUNCTION_NAME
        try:
            if link.exists():
                link.rmdir()
            root.rmdir()
        except OSError as exc:
            self.logger.warning("Failed to clean up temporary VLC junction %s: %s", root, exc)

    def _wait_for_vlc_and_cleanup(self, proc: subprocess.Popen[Any], cleanup_root: Path | None) -> None:
        try:
            proc.wait()
        finally:
            self._cleanup_vlc_junction_root(cleanup_root)

    def _open_media_with_vlc(self, path: Path) -> bool:
        vlc_path = self._find_vlc_executable()
        if vlc_path is None:
            return False

        creationflags = vlc_creation_flags()
        launch_path, cleanup_root = self._vlc_launch_path_for_media(path)
        args = build_vlc_launch_args(vlc_path, launch_path)
        self.logger.info(
            "Launching VLC media path: executable=%s long_path=%s junction=%s args=%s",
            vlc_path,
            len(_windows_native_path(path)) >= VLC_LONG_PATH_THRESHOLD,
            cleanup_root if cleanup_root else "",
            subprocess.list2cmdline(args),
        )
        try:
            proc = subprocess.Popen(
                args,
                cwd=str(Path(launch_path).parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=creationflags,
            )
        except Exception:
            self._cleanup_vlc_junction_root(cleanup_root)
            raise
        threading.Thread(target=self._wait_for_vlc_and_cleanup, args=(proc, cleanup_root), daemon=True).start()
        return True

    def _open_windows_path_with_shell(self, path: Path) -> None:
        native_path = _windows_native_path(path)
        self.logger.info("Opening Windows path with shell: %s", native_path)
        if path.is_dir():
            existing_handles = set(_top_level_explorer_window_handles())
            subprocess.Popen(["explorer.exe", native_path], close_fds=True)
            if not _focus_opened_explorer_window(existing_handles):
                self.logger.debug("Explorer foreground request did not report success: %s", native_path)
            return
        try:
            os.startfile(native_path)  # type: ignore[attr-defined]
            return
        except OSError:
            if path.is_file():
                subprocess.Popen(explorer_select_args(native_path), close_fds=True)
                return
            raise

    def open_path(self, path: Path | str | None) -> None:
        raw_path_text = str(path) if path is not None else ""
        path = _coerce_open_path(path)
        self.logger.info("Open path requested: raw=%s normalized=%s", raw_path_text, path)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if os.name == "nt":
            if path.is_file() and path.suffix.lower() in MEDIA_FILE_SUFFIXES and self._open_media_with_vlc(path):
                return
            self._open_windows_path_with_shell(path)
            return
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        proc = subprocess.Popen([opener, str(path)], close_fds=True)
        threading.Thread(target=proc.wait, daemon=True).start()

    def open_path_with_default_app(self, path: Path | str | None) -> None:
        raw_path_text = str(path) if path is not None else ""
        path = _coerce_open_path(path)
        self.logger.info("Open path with default app requested: raw=%s normalized=%s", raw_path_text, path)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if os.name == "nt":
            self._open_windows_path_with_shell(path)
            return
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        proc = subprocess.Popen([opener, str(path)], close_fds=True)
        threading.Thread(target=proc.wait, daemon=True).start()

    def open_parent(self, path: Path | str | None) -> None:
        path = _coerce_open_path(path)
        target = path.parent if path.exists() and path.is_file() else path
        if not target.exists():
            raise FileNotFoundError(f"Path does not exist: {target}")
        self.open_path(target)
