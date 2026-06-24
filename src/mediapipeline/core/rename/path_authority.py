"""Configured-root authority and undo manifest root helpers for rename."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.config_keys import KEY_LIBRARY_PROFILES, KEY_OUTSOURCE, KEY_SOURCE_MOVIES, KEY_SOURCE_TV
from mediapipeline.core.paths.layout import path_within_root
from mediapipeline.core.rename.input_classification import classify_rename_input_paths
from mediapipeline.core.validation.strict_json import loads_strict_json

OUTSIDE_CONFIGURED_ROOTS_MESSAGE = "Rename apply includes path(s) outside configured media roots."
OUTSIDE_CONFIGURED_ROOTS_WARNING = (
    "Path is outside configured SourceMovies, SourceTV, Outsource, or enabled LibraryProfiles roots; standalone rename requires explicit outside-root confirmation."
)
UNSCOPED_OPERATOR_PATHS_MESSAGE = "Rename apply includes path(s) without configured media-root authority."
LIBRARY_PROFILE_PATH_FIELDS = ("source_path", "output_path", "promotion_destination")


def rename_request_paths(request: Mapping[str, Any]) -> list[Path]:
    return classify_rename_input_paths(request.get("paths") or []).media_paths


def rename_configured_media_roots_from_request(request: Mapping[str, Any]) -> list[Path]:
    roots: list[Path] = []
    raw_roots = request.get("_configured_media_roots")
    if isinstance(raw_roots, list):
        for item in raw_roots:
            text = str(item or "").strip()
            if text:
                roots.append(Path(text))
    return roots


def rename_undo_manifest_root_from_request(request: Mapping[str, Any]) -> Path | None:
    text = str(request.get("_rename_undo_manifest_root") or "").strip()
    return Path(text) if text else None


def rename_undo_manifest_root_from_resolved(resolved: Any) -> Path | None:
    state_root = getattr(resolved, "state_root", None)
    if state_root:
        return Path(state_root) / "RenameUndo"
    local_base = getattr(resolved, "local_base", None)
    if local_base:
        return Path(local_base) / "State" / "RenameUndo"
    return None


def _configured_root_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        path_text = os.path.abspath(str(Path(text).expanduser().resolve(strict=False)))
    except OSError:
        path_text = os.path.abspath(text)
    return os.path.normcase(path_text) if os.name == "nt" else path_text


def _append_configured_media_root(roots: list[str], seen: set[str], value: Any) -> None:
    text = str(value or "").strip()
    key = _configured_root_key(text)
    if not text or not key or key in seen:
        return
    seen.add(key)
    roots.append(text)


def _truthy_profile_value(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, int | float):
        return value != 0
    text = str(value or "").strip().casefold()
    if not text:
        return default
    if text in {"1", "true", "yes", "on", "enabled", "enable"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "disable"}:
        return False
    return default


def _profile_id(value: Mapping[str, Any]) -> str:
    text = str(value.get("id") or value.get("library_id") or "").strip().casefold()
    if text in {"movie", "movies"}:
        return "movies"
    if text in {"show", "shows", "tv"}:
        return "tv"
    return text


def _coerce_library_profile_authority_rows(raw: Any) -> list[Mapping[str, Any]]:
    if raw in (None, "", False):
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        raw = loads_strict_json(text)
    if isinstance(raw, Mapping):
        raw = [raw]
    if not isinstance(raw, Iterable) or isinstance(raw, (bytes, bytearray, str)):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _profile_inherited_path(profile: Mapping[str, Any], field: str, config: Mapping[str, Any]) -> str:
    tracking = profile.get("default_tracking")
    if not isinstance(tracking, Mapping):
        tracking = {}
    inherited = tracking.get("inherited_fields")
    inherited_fields = {str(item) for item in inherited} if isinstance(inherited, list) else set()
    if field not in inherited_fields:
        return ""
    field_default_keys = tracking.get("field_default_keys")
    if isinstance(field_default_keys, Mapping):
        key = str(field_default_keys.get(field) or "").strip()
        if key:
            return str(config.get(key) or "").strip()
    if field == "output_path":
        return str(config.get(KEY_OUTSOURCE) or "").strip()
    if field == "source_path":
        profile_id = _profile_id(profile)
        if profile_id == "movies":
            return str(config.get(KEY_SOURCE_MOVIES) or "").strip()
        if profile_id == "tv":
            return str(config.get(KEY_SOURCE_TV) or "").strip()
    return ""


def _profile_authority_path(profile: Mapping[str, Any], field: str, config: Mapping[str, Any]) -> str:
    text = str(profile.get(field) or "").strip()
    if text:
        return text
    inherited = _profile_inherited_path(profile, field, config)
    if inherited:
        return inherited
    profile_id = _profile_id(profile)
    if field == "source_path":
        if profile_id == "movies":
            return str(config.get(KEY_SOURCE_MOVIES) or "").strip()
        if profile_id == "tv":
            return str(config.get(KEY_SOURCE_TV) or "").strip()
    if field == "output_path" and profile_id in {"movies", "tv"}:
        return str(config.get(KEY_OUTSOURCE) or "").strip()
    return ""


def rename_authority_fields_for_source(source: object, configured_roots: Iterable[Path]) -> dict[str, Any]:
    roots = [root for root in configured_roots if str(root or "").strip()]
    if not roots:
        return {
            "path_authority": "unscoped_operator_path",
            "path_authority_status": "review",
            "path_authority_root_count": 0,
            "path_authority_message": "No configured media roots were available to the rename authority check.",
        }
    source_path = Path(str(source or ""))
    if any(path_within_root(source_path, root) for root in roots):
        return {
            "path_authority": "configured_media_root",
            "path_authority_status": "ready",
            "path_authority_root_count": len(roots),
            "path_authority_message": "Source is inside a configured media root.",
        }
    return {
        "path_authority": "outside_configured_roots",
        "path_authority_status": "review",
        "path_authority_root_count": len(roots),
        "path_authority_message": OUTSIDE_CONFIGURED_ROOTS_WARNING,
    }


def annotate_rename_plan_path_authority(
    rows: Iterable[Mapping[str, Any]],
    configured_roots: Iterable[Path],
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    roots = list(configured_roots)
    for raw_row in rows:
        row = dict(raw_row)
        fields = rename_authority_fields_for_source(row.get("source"), roots)
        row.update(fields)
        annotated.append(row)
    return annotated


def rename_plan_outside_configured_roots(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if str(row.get("path_authority") or "") == "outside_configured_roots"]


def rename_plan_unscoped_operator_paths(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if str(row.get("path_authority") or "") == "unscoped_operator_path"]


def rename_request_allows_outside_configured_roots(request: Mapping[str, Any]) -> bool:
    return request.get("allow_outside_configured_roots") is True


def rename_configured_media_roots_from_resolved(resolved: object) -> list[str]:
    roots: list[str] = []
    seen: set[str] = set()
    config_data = getattr(resolved, "config_data", None)
    config_map = config_data if isinstance(config_data, Mapping) else {}
    for attr, key in (("source_movies", KEY_SOURCE_MOVIES), ("source_tv", KEY_SOURCE_TV)):
        value = getattr(resolved, attr, None)
        if value is None or not str(value).strip():
            value = config_map.get(key)
        _append_configured_media_root(roots, seen, value)
    if isinstance(config_data, Mapping):
        _append_configured_media_root(roots, seen, config_data.get(KEY_OUTSOURCE))
        try:
            profiles = _coerce_library_profile_authority_rows(config_map.get(KEY_LIBRARY_PROFILES))
        except Exception:
            profiles = []
        for profile in profiles:
            if not _truthy_profile_value(profile.get("enabled", True), True):
                continue
            for field in LIBRARY_PROFILE_PATH_FIELDS:
                _append_configured_media_root(roots, seen, _profile_authority_path(profile, field, config_map))
    return roots


__all__ = [
    "OUTSIDE_CONFIGURED_ROOTS_MESSAGE",
    "OUTSIDE_CONFIGURED_ROOTS_WARNING",
    "UNSCOPED_OPERATOR_PATHS_MESSAGE",
    "rename_request_paths",
    "rename_configured_media_roots_from_request",
    "rename_undo_manifest_root_from_request",
    "rename_undo_manifest_root_from_resolved",
    "rename_authority_fields_for_source",
    "annotate_rename_plan_path_authority",
    "rename_plan_outside_configured_roots",
    "rename_plan_unscoped_operator_paths",
    "rename_request_allows_outside_configured_roots",
    "rename_configured_media_roots_from_resolved",
]
