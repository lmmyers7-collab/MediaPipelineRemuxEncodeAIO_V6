from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mediapipeline.core.config.library_profiles import library_profiles_from_config
from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.core.kernel.config_key_groups import KEY_SOURCE_MOVIES, KEY_SOURCE_TV

SOURCE_ROOT_SCOPE_TEXT = "configured source roots (SourceMovies, SourceTV, or enabled LibraryProfiles source roots)"
QUEUE_SOURCE_FILE_VALIDATION_SCHEMA_VERSION = "desktop_queue_source_file_validation.v1"


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


def _append_source_root(roots: list[Path], seen: set[str], value: Any) -> None:
    text = str(value or "").strip()
    if not text:
        return
    key = _path_key(text)
    if not key or key in seen:
        return
    seen.add(key)
    roots.append(Path(text))


def queue_source_roots(resolved: Any) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()
    config = getattr(resolved, "config_data", {}) or {}
    for attr, key in (("source_movies", KEY_SOURCE_MOVIES), ("source_tv", KEY_SOURCE_TV)):
        value = getattr(resolved, attr, None) or (config.get(key) if isinstance(config, dict) else None)
        _append_source_root(roots, seen, value)
    try:
        profiles = library_profiles_from_config(config if isinstance(config, dict) else {})
    except Exception:
        profiles = []
    for profile in profiles:
        if not profile.get("enabled", True):
            continue
        source_path = str(profile.get("source_path") or "").strip()
        _append_source_root(roots, seen, source_path)
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


def queue_source_file_validation(resolved: Any, raw_path: Any, *, field_name: str = "path") -> dict[str, Any]:
    path_text = str(raw_path or "").strip()
    roots = queue_source_roots(resolved)
    validation: dict[str, Any] = {
        "schema_version": QUEUE_SOURCE_FILE_VALIDATION_SCHEMA_VERSION,
        "field_name": field_name,
        "path": path_text,
        "normalized_path": "",
        "source_root_scope": SOURCE_ROOT_SCOPE_TEXT,
        "source_root_count": len(roots),
        "source_roots_configured": bool(roots),
        "exists": False,
        "is_file": False,
        "is_absolute": False,
        "under_source_root": False,
        "media_suffix": "",
        "media_suffix_supported": False,
        "supported_suffixes": sorted(MEDIA_FILE_SUFFIXES),
        "status": "blocked",
        "status_state": "blocked",
        "ok": False,
        "message": "",
        "errors": [],
    }

    if not path_text:
        validation["message"] = f"'{field_name}' is required."
        validation["errors"] = [validation["message"]]
        return validation

    try:
        candidate = Path(path_text).expanduser()
        validation["is_absolute"] = candidate.is_absolute()
        validation["media_suffix"] = candidate.suffix.casefold()
        validation["media_suffix_supported"] = validation["media_suffix"] in MEDIA_FILE_SUFFIXES
        if validation["is_absolute"]:
            validation["normalized_path"] = _absolute_path_text(candidate)
            validation["under_source_root"] = path_is_under_or_equal(candidate, roots)
            validation["exists"] = candidate.exists()
            validation["is_file"] = candidate.is_file()
    except OSError as exc:
        validation["message"] = f"Selected source file path could not be checked: {exc}"
        validation["errors"] = [validation["message"]]
        return validation

    errors: list[str] = []
    if not validation["is_absolute"]:
        errors.append(f"'{field_name}' must be an absolute path under {SOURCE_ROOT_SCOPE_TEXT}.")
    elif not validation["source_roots_configured"]:
        errors.append("SourceMovies, SourceTV, and LibraryProfiles are not configured; queue source file launches are unavailable.")
    elif not validation["under_source_root"]:
        errors.append(f"Path is outside {SOURCE_ROOT_SCOPE_TEXT}.")
    elif not validation["exists"]:
        errors.append(f"'{field_name}' does not exist.")
    elif not validation["is_file"]:
        errors.append(f"'{field_name}' exists but is not a file.")
    elif not validation["media_suffix_supported"]:
        suffix = validation["media_suffix"] or "(none)"
        errors.append(f"'{field_name}' uses unsupported media suffix {suffix}.")

    if errors:
        validation["message"] = errors[0]
        validation["errors"] = errors
        return validation

    validation["status"] = "ready"
    validation["status_state"] = "ready"
    validation["ok"] = True
    validation["message"] = f"'{field_name}' is an existing supported media file under {SOURCE_ROOT_SCOPE_TEXT}."
    validation["errors"] = []
    return validation


def validate_queue_source_file_path(resolved: Any, raw_path: Any, *, field_name: str = "path") -> tuple[str | None, str | None]:
    validation = queue_source_file_validation(resolved, raw_path, field_name=field_name)
    if not validation.get("ok"):
        return None, str(validation.get("message") or f"'{field_name}' is invalid.")
    return str(validation.get("normalized_path") or ""), None


__all__ = [
    "QUEUE_SOURCE_FILE_VALIDATION_SCHEMA_VERSION",
    "SOURCE_ROOT_SCOPE_TEXT",
    "path_is_under_or_equal",
    "queue_source_file_validation",
    "queue_source_roots",
    "validate_queue_source_file_path",
    "validate_queue_source_path",
]
