from __future__ import annotations

import os
from pathlib import Path


def iter_bundled_launch_dirs(app_root: Path, workspace_root: Path) -> list[Path]:
    candidates = [
        app_root / "Runtime" / "Python",
        workspace_root / "DesktopApp" / "Runtime" / "Python",
        workspace_root / "Pipeline" / "Tools" / "ffmpeg" / "bin",
        workspace_root / "Pipeline" / "Tools" / "MKVToolNix",
        app_root / "Pipeline" / "Tools" / "ffmpeg" / "bin",
        app_root / "Pipeline" / "Tools" / "MKVToolNix",
        workspace_root / "Pipeline" / "PowerShell-7.6.0-win-x64",
        app_root / "Pipeline" / "PowerShell-7.6.0-win-x64",
    ]
    seen: set[str] = set()
    resolved: list[Path] = []
    for candidate in candidates:
        if candidate.exists():
            key = str(candidate).casefold()
            if key not in seen:
                seen.add(key)
                resolved.append(candidate)
    return resolved


def build_launch_environment(app_root: Path, workspace_root: Path, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env) if base_env is not None else os.environ.copy()
    bundled_dirs = [str(path) for path in iter_bundled_launch_dirs(app_root, workspace_root)]
    if not bundled_dirs:
        return env

    existing_path = env.get("PATH", "")
    prefix = os.pathsep.join(bundled_dirs)
    env["PATH"] = prefix if not existing_path else prefix + os.pathsep + existing_path
    return env
