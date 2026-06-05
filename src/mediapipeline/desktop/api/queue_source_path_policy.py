from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mediapipeline.core.config.library_profiles import library_profiles_from_config

SOURCE_ROOT_SCOPE_TEXT = "configured source roots (SourceMovies, SourceTV, or enabled LibraryProfiles source roots)"


def _absolute_path_text(value: str | Path) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return ""
    try:
        return os.path.abspath(str(path.resolve(strict=False)))
    except OSError:
        return os.path.abspath(str(path))


def _path_key(value: str | Path) -> str:
    path_text = _absolute_path_text(value)
    if not path_text:
        return ""
    if os.name == "nt":
        path_text = os.path.normcase(path_text)
    return path_text


def queue_source_roots(resolved: Any) -> list[Path]:
    roots: list[Path] = []
    for attr in ("source_movies", "source_tv"):
        value = getattr(resolved, attr, None)
        if value:
            roots.append(Path(value))
    try:
        profiles = library_profiles_from_config(getattr(resolved, "config_data", {}) or {})
    except Exception:
        profiles = []
    for profile in profiles:
        if not profile.get("enabled", True):
            continue
        source_path = str(profile.get("source_path") or "").strip()
        if source_path:
            roots.append(Path(source_path))
    return roots


def path_is_under_or_equal(path: str | Path, roots: list[Path]) -> bool:
    candidate = _path_key(path)
    if not candidate:
        return False
    for root in roots:
        root_key = _path_key(root)
        if not root_key:
            continue
        try:
            if os.path.commonpath([candidate, root_key]) == root_key:
                return True
        except ValueError:
            continue
    return False


def validate_queue_source_path(resolved: Any, raw_path: Any, *, field_name: str = "path") -> tuple[str | None, str | None]:
    path_text = str(raw_path or "").strip()
    if not path_text:
        return None, f"'{field_name}' is required."
    candidate = Path(path_text)
    if not candidate.is_absolute():
        return None, f"'{field_name}' must be an absolute path under {SOURCE_ROOT_SCOPE_TEXT}."
    roots = queue_source_roots(resolved)
    if not roots:
        return None, "SourceMovies, SourceTV, and LibraryProfiles are not configured; queue source path updates are unavailable."
    if not path_is_under_or_equal(candidate, roots):
        return None, f"Path is outside {SOURCE_ROOT_SCOPE_TEXT}."
    return _absolute_path_text(candidate), None
