from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from app.config.constants import PROFILE_NAME_PATTERN


def normalize_profile_name(raw_name: str) -> str:
    profile_name = str(raw_name or "").strip().replace(" ", "_")
    if not profile_name:
        raise ValueError("Profile name cannot be empty.")
    if not PROFILE_NAME_PATTERN.fullmatch(profile_name):
        raise ValueError("Profile names may only contain letters, digits, hyphens, and underscores.")
    return profile_name


def config_profiles_dir(config_path: Path) -> Path:
    return config_path.parent / "Profiles"


def config_profile_path(
    config_path: Path,
    profile_name: str,
    *,
    path_within_root: Callable[[Path, Path], bool] | None = None,
) -> tuple[str, Path]:
    safe_name = normalize_profile_name(profile_name)
    profiles_dir = config_profiles_dir(config_path)
    profile_path = profiles_dir / f"{safe_name}.psd1"
    within_root = path_within_root or _path_within_root
    if not within_root(profile_path, profiles_dir):
        raise RuntimeError(f"Refusing profile path outside Profiles directory: {profile_path}")
    return safe_name, profile_path


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path_text = os.path.abspath(str(path.resolve(strict=False)))
        root_text = os.path.abspath(str(root.resolve(strict=False)))
    except OSError:
        path_text = os.path.abspath(str(path))
        root_text = os.path.abspath(str(root))
    if os.name == "nt":
        path_text = os.path.normcase(path_text)
        root_text = os.path.normcase(root_text)
    try:
        return os.path.commonpath([path_text, root_text]) == root_text
    except ValueError:
        return False
