from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

from mediapipeline.core.files.constants import VLC_LONG_PATH_THRESHOLD


MKLINK_JUNCTION_TIMEOUT_SECONDS = 10


def vlc_candidate_paths(
    *,
    which_vlc: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Path]:
    candidates: list[Path] = []
    resolved_vlc = which_vlc if which_vlc is not None else shutil.which("vlc")
    if resolved_vlc:
        candidates.append(Path(resolved_vlc))
    env = os.environ if environ is None else environ
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        root = env.get(env_name)
        if root:
            candidates.append(Path(root) / "VideoLAN" / "VLC" / "vlc.exe")
    return candidates


def vlc_needs_short_path(
    native_path: str,
    *,
    is_windows: bool | None = None,
    threshold: int = VLC_LONG_PATH_THRESHOLD,
) -> bool:
    windows = os.name == "nt" if is_windows is None else is_windows
    return windows and len(native_path) >= threshold and not native_path.startswith("\\\\")


def vlc_creation_flags(*, is_windows: bool | None = None) -> int:
    windows = os.name == "nt" if is_windows is None else is_windows
    if not windows:
        return 0
    return getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def build_vlc_launch_args(vlc_path: Path, launch_path: str) -> list[str]:
    return [
        str(vlc_path),
        "--no-one-instance",
        "--no-one-instance-when-started-from-file",
        "--no-playlist-enqueue",
        launch_path,
    ]


def explorer_select_args(native_path: str) -> list[str]:
    return ["explorer.exe", f"/select,{native_path}"]
