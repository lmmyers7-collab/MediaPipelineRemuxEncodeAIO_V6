from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from .service_constants import MEDIA_FILE_SUFFIXES, VLC_LONG_PATH_THRESHOLD
from .service_file_open_plan import (
    MKLINK_JUNCTION_TIMEOUT_SECONDS,
    build_vlc_launch_args,
    explorer_select_args,
    vlc_candidate_paths,
    vlc_creation_flags,
    vlc_needs_short_path,
)
from .service_utils import _coerce_open_path, _windows_native_path


VLC_TEMP_JUNCTION_PREFIX = "mediapipeline-vlc-"
VLC_TEMP_JUNCTION_NAME = "m"


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

    def open_parent(self, path: Path | str | None) -> None:
        path = _coerce_open_path(path)
        target = path.parent if path.exists() and path.is_file() else path
        if not target.exists():
            raise FileNotFoundError(f"Path does not exist: {target}")
        self.open_path(target)
