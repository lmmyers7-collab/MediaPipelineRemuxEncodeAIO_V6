from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from typing import Any

from mediapipeline.core.kernel.config_keys import (
    KEY_LIBRARY_PROFILES,
    KEY_OUTSOURCE,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
)

from .library_profile_defaults import (
    DEFAULT_LIBRARY_IDS,
    LIBRARY_OVERRIDE_GROUPS,
    LIBRARY_OVERRIDE_KEYS_BY_GROUP,
    LIBRARY_PROFILE_PATH_FIELDS,
    _jsonable,
    default_library_settings,
    default_tracking_for_profile,
)
from .library_profile_normalization import (
    _bool_value,
    _profile_id_from_mapping,
    _text,
    coerce_library_overrides,
    coerce_library_profiles,
    library_profiles_from_config,
)
from .library_profile_promotion import normalize_library_profile_config_values

def _ensure_tracking(profile: dict[str, Any]) -> dict[str, Any]:
    tracking = profile.get("default_tracking")
    if not isinstance(tracking, Mapping):
        tracking = default_tracking_for_profile(str(profile.get("id") or ""), str(profile.get("designation") or "auto"))
    tracking = {str(key): _jsonable(value) for key, value in dict(tracking).items()}
    inherited = tracking.get("inherited_fields")
    tracking["inherited_fields"] = [str(item) for item in inherited] if isinstance(inherited, list) else []
    field_default_keys = tracking.get("field_default_keys")
    tracking["field_default_keys"] = (
        {str(key): _jsonable(value) for key, value in field_default_keys.items()}
        if isinstance(field_default_keys, Mapping)
        else {}
    )
    profile["default_tracking"] = tracking
    return tracking

def _set_path_inherited(profile: dict[str, Any], field: str, source_key: str) -> None:
    tracking = _ensure_tracking(profile)
    inherited = [str(item) for item in tracking.get("inherited_fields", []) if item]
    if field not in inherited:
        inherited.append(field)
    tracking["inherited_fields"] = [
        path_field for path_field in LIBRARY_PROFILE_PATH_FIELDS if path_field in set(inherited)
    ] + sorted(
        item
        for item in inherited
        if item not in set(LIBRARY_PROFILE_PATH_FIELDS)
    )
    field_default_keys = tracking["field_default_keys"]
    field_default_keys[field] = source_key
    profile[field] = ""

def _reset_profile_path(
    profile: dict[str, Any],
    field: str,
    errors: list[str],
) -> None:
    profile_id = str(profile.get("id") or "")
    label = str(profile.get("name") or profile_id or "Library")
    if field not in LIBRARY_PROFILE_PATH_FIELDS:
        errors.append(f"Library profile {label} reset path field is unsupported: {field}.")
        return
    if field == "promotion_destination":
        errors.append(f"Library profile {label} promotion_destination cannot be reset to inherited.")
        return
    if field == "source_path":
        if profile_id == "movies":
            _set_path_inherited(profile, "source_path", KEY_SOURCE_MOVIES)
            return
        if profile_id == "tv":
            _set_path_inherited(profile, "source_path", KEY_SOURCE_TV)
            return
        errors.append(f"Library profile {label} source_path cannot be reset to inherited.")
        return
    if field == "output_path":
        _set_path_inherited(profile, "output_path", KEY_OUTSOURCE)

def _reset_profile_override(
    profile: dict[str, Any],
    group: str,
    key: str,
    errors: list[str],
) -> None:
    label = str(profile.get("name") or profile.get("id") or "Library")
    normalized_group = "subtitles" if group == "subtitle" else str(group)
    if normalized_group not in LIBRARY_OVERRIDE_GROUPS:
        errors.append(f"Library profile {label} override reset group is unsupported: {group}.")
        return
    if key not in LIBRARY_OVERRIDE_KEYS_BY_GROUP[normalized_group]:
        errors.append(f"Library profile {label} override reset key is not allowed in {normalized_group}: {key}.")
        return
    overrides = coerce_library_overrides(profile)
    overrides[normalized_group].pop(key, None)
    profile["overrides"] = overrides

def apply_library_profile_resets(
    values: Mapping[str, Any],
    resets: Any,
) -> tuple[dict[str, Any], list[str]]:
    if resets in (None, "", False):
        return dict(values or {}), []
    if isinstance(resets, Mapping):
        reset_items = [resets]
    elif isinstance(resets, Iterable) and not isinstance(resets, (bytes, bytearray, str)):
        reset_items = list(resets)
    else:
        return dict(values or {}), ["library_profile_resets must be an object or list of objects."]

    updated = dict(values or {})
    try:
        profiles = [dict(profile) for profile in library_profiles_from_config(updated)]
    except (ValueError, TypeError) as exc:
        return dict(values or {}), [f"LibraryProfiles is invalid: {exc}"]
    by_id = {str(profile.get("id") or ""): profile for profile in profiles}
    errors: list[str] = []

    for item in reset_items:
        if not isinstance(item, Mapping):
            errors.append("library_profile_resets entries must be objects.")
            continue
        raw_id = _text(item.get("library_id") or item.get("id"))
        if not raw_id:
            errors.append("library_profile_resets entries require library_id.")
            continue
        profile_id = _profile_id_from_mapping({"id": raw_id}, 0)
        profile = by_id.get(profile_id)
        if profile is None:
            errors.append(f"Library profile reset target was not found: {raw_id}.")
            continue

        path_fields = item.get("path_fields") or item.get("paths") or []
        if isinstance(path_fields, str):
            path_fields = [path_fields]
        if not isinstance(path_fields, Iterable) or isinstance(path_fields, (bytes, bytearray, Mapping)):
            errors.append(f"Library profile {profile_id} path_fields must be a list.")
        else:
            for field in path_fields:
                _reset_profile_path(profile, str(field), errors)

        override_resets = item.get("overrides") or item.get("setting_overrides") or {}
        if override_resets in (None, "", False):
            override_resets = {}
        if not isinstance(override_resets, Mapping):
            errors.append(f"Library profile {profile_id} override resets must be an object.")
            continue
        for group, keys in override_resets.items():
            key_items = [keys] if isinstance(keys, str) else keys
            if not isinstance(key_items, Iterable) or isinstance(key_items, (bytes, bytearray, Mapping)):
                errors.append(f"Library profile {profile_id} override reset keys for {group} must be a list.")
                continue
            for key in key_items:
                _reset_profile_override(profile, str(group), str(key), errors)

    updated[KEY_LIBRARY_PROFILES] = profiles
    if errors:
        return updated, errors
    return normalize_library_profile_config_values(updated, require_profiles=True), []

def _deep_merge(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    merged = {str(key): _jsonable(value) for key, value in base.items()}
    for key, value in overrides.items():
        key_text = str(key)
        if (
            key_text in merged
            and isinstance(merged[key_text], Mapping)
            and isinstance(value, Mapping)
        ):
            merged[key_text] = _deep_merge(merged[key_text], value)
        else:
            merged[key_text] = _jsonable(value)
    return merged

def resolve_effective_library_settings(
    global_defaults: Mapping[str, Any],
    library_profile: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    defaults = default_library_settings(global_defaults)
    overrides = coerce_library_overrides(library_profile)
    return {
        group: _deep_merge(defaults[group], overrides.get(group, {}))
        for group in LIBRARY_OVERRIDE_GROUPS
    }

def library_override_state(library_profile: Mapping[str, Any]) -> dict[str, dict[str, bool]]:
    overrides = coerce_library_overrides(library_profile)
    return {
        group: {key: True for key in values.keys()}
        for group, values in overrides.items()
    }

def flatten_library_settings(settings: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for group in LIBRARY_OVERRIDE_GROUPS:
        values = settings.get(group, {})
        if isinstance(values, Mapping):
            flattened.update({str(key): _jsonable(value) for key, value in values.items()})
    return flattened

def _path_default_source_key(profile_id: str, field: str) -> str:
    if field == "output_path":
        return KEY_OUTSOURCE
    if field == "source_path":
        if profile_id == "movies":
            return KEY_SOURCE_MOVIES
        if profile_id == "tv":
            return KEY_SOURCE_TV
    return ""

def _path_field_required(profile: Mapping[str, Any], field: str) -> bool:
    enabled = _bool_value(profile.get("enabled", True), True)
    if not enabled:
        return False
    if field in {"source_path", "output_path"}:
        return True
    if field == "promotion_destination":
        return _bool_value(profile.get("promotion_enabled", False), False)
    return False

def _profile_origin(raw_profile: Mapping[str, Any] | None, *, synthesized: bool) -> str:
    if synthesized:
        return "synthesized_builtin_default"
    if raw_profile and (
        "library_id" in raw_profile
        or str(raw_profile.get("designation") or "").strip().casefold() in {"mixed", "custom"}
    ):
        return "legacy_coerced"
    return "configured"

def library_profile_path_field_state(
    library_profile: Mapping[str, Any],
    field: str,
    *,
    raw_profile: Mapping[str, Any] | None = None,
    synthesized: bool = False,
) -> dict[str, Any]:
    profile_id = str(library_profile.get("id") or "")
    tracking = library_profile.get("default_tracking")
    tracking_map = tracking if isinstance(tracking, Mapping) else {}
    inherited_fields = {str(item) for item in tracking_map.get("inherited_fields", []) if item}
    field_default_keys = tracking_map.get("field_default_keys")
    field_default_map = field_default_keys if isinstance(field_default_keys, Mapping) else {}
    source_key = _text(field_default_map.get(field)) or _path_default_source_key(profile_id, field)
    effective_value = _text(library_profile.get(field))
    raw_has_field = raw_profile is not None and field in raw_profile
    raw_value = _text(raw_profile.get(field)) if raw_has_field and raw_profile is not None else ""
    explicit_value = raw_value if raw_value else None
    required = _path_field_required(library_profile, field)

    if synthesized and profile_id in DEFAULT_LIBRARY_IDS and field in {"source_path", "output_path"}:
        state = "synthesized_builtin_default"
        explicit_value = None
    elif field in inherited_fields:
        state = "inherited"
        explicit_value = None
    elif effective_value:
        state = "explicit"
        explicit_value = effective_value
        source_key = ""
    elif required:
        state = "invalid_unresolved"
        source_key = ""
    else:
        state = "not_configured"
        source_key = ""

    return {
        "field": field,
        "state": state,
        "origin": _profile_origin(raw_profile, synthesized=synthesized),
        "source_key": source_key,
        "effective_value": effective_value,
        "explicit_value": explicit_value,
        "required": required,
    }

def _setting_override_field_state(
    inherited_group: Mapping[str, Any],
    group_overrides: Mapping[str, Any],
    group: str,
    key: str,
) -> dict[str, Any]:
    inherited_value = inherited_group.get(key)
    is_explicit = key in group_overrides
    explicit_value = group_overrides.get(key) if is_explicit else None
    effective_value = explicit_value if is_explicit else inherited_value
    return {
        "field": key,
        "group": group,
        "state": "explicit" if is_explicit else "inherited",
        "effective_value": _jsonable(effective_value),
        "inherited_value": _jsonable(inherited_value),
        "explicit_value": _jsonable(explicit_value),
        "value_equals_global": is_explicit and _jsonable(explicit_value) == _jsonable(inherited_value),
    }

def library_setting_override_field_state(
    global_defaults: Mapping[str, Any],
    library_profile: Mapping[str, Any],
    group: str,
    key: str,
) -> dict[str, Any]:
    defaults = default_library_settings(global_defaults)
    overrides = coerce_library_overrides(library_profile)
    return _setting_override_field_state(
        defaults.get(group, {}), overrides.get(group, {}), group, key
    )

def library_profile_state(
    config: Mapping[str, Any],
    library_profile: Mapping[str, Any],
    *,
    raw_profile: Mapping[str, Any] | None = None,
    synthesized: bool = False,
) -> dict[str, Any]:
    defaults = default_library_settings(config)
    overrides = coerce_library_overrides(library_profile)
    setting_overrides: dict[str, dict[str, Any]] = {}
    for group, keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.items():
        inherited_group = defaults.get(group, {})
        group_overrides = overrides.get(group, {})
        setting_overrides[group] = {
            key: _setting_override_field_state(inherited_group, group_overrides, group, key)
            for key in keys
        }
    return {
        "schema_version": "library_profile_state.v1",
        "library_id": str(library_profile.get("id") or ""),
        "library_name": str(library_profile.get("name") or ""),
        "path_fields": {
            field: library_profile_path_field_state(
                library_profile,
                field,
                raw_profile=raw_profile,
                synthesized=synthesized,
            )
            for field in LIBRARY_PROFILE_PATH_FIELDS
        },
        "setting_overrides": setting_overrides,
    }

def _raw_library_profile_lookup(config: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw_profiles = coerce_library_profiles(config.get(KEY_LIBRARY_PROFILES))
    lookup: dict[str, Mapping[str, Any]] = {}
    for index, raw_profile in enumerate(raw_profiles, start=1):
        lookup[_profile_id_from_mapping(raw_profile, index)] = raw_profile
    return lookup

def library_profile_state_from_config(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_by_id = _raw_library_profile_lookup(config)
    states: list[dict[str, Any]] = []
    for profile in library_profiles_from_config(config):
        profile_id = str(profile.get("id") or "")
        states.append(
            library_profile_state(
                config,
                profile,
                raw_profile=raw_by_id.get(profile_id),
                synthesized=profile_id in DEFAULT_LIBRARY_IDS and profile_id not in raw_by_id,
            )
        )
    return states

def effective_library_profiles_from_config(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    effective: list[dict[str, Any]] = []
    raw_by_id = _raw_library_profile_lookup(config)
    for profile in library_profiles_from_config(config):
        profile_id = str(profile.get("id") or "")
        state = library_profile_state(
            config,
            profile,
            raw_profile=raw_by_id.get(profile_id),
            synthesized=profile_id in DEFAULT_LIBRARY_IDS and profile_id not in raw_by_id,
        )
        settings = resolve_effective_library_settings(config, profile)
        overrides = coerce_library_overrides(profile)
        row = dict(profile)
        row["overrides"] = overrides
        row["field_state"] = state
        row["path_field_state"] = state["path_fields"]
        row["setting_override_state"] = state["setting_overrides"]
        row["effective_settings"] = settings
        row["effective_editor"] = settings["editor"]
        row["effective_video"] = settings["video"]
        row["effective_subtitles"] = settings["subtitles"]
        row["effective_audio"] = settings["audio"]
        row["effective_media"] = flatten_library_settings(
            {
                "video": settings["video"],
                "subtitles": settings["subtitles"],
                "audio": settings["audio"],
            }
        )
        row["override_state"] = library_override_state(profile)
        row["library_id"] = row["id"]
        row["effective_output_root"] = row.get("output_path", "")
        row["effective_source_root"] = row.get("source_path", "")
        effective.append(row)
    return effective

def _resolved_match_key(value: Any) -> str:
    """Resolve a path to a canonical comparison key.

    Mirrors the engine's ``[System.IO.Path]::GetFullPath`` + ``OrdinalIgnoreCase``
    handling (ops/pipeline/engine/paths/path_capability.ps1): collapse ``..``,
    make absolute, normalize separators, and case-fold for the host filesystem.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        full = os.path.abspath(text)
    except (OSError, ValueError):
        full = text
    return os.path.normcase(full.rstrip("\\/"))

def _path_is_under_or_equal(candidate_key: str, root_key: str) -> bool:
    if not candidate_key or not root_key:
        return False
    if candidate_key == root_key:
        return True
    return candidate_key.startswith(root_key + os.sep)

def _profile_match_root_key(profile: Mapping[str, Any]) -> str:
    return _resolved_match_key(profile.get("effective_source_root") or profile.get("source_path"))

def effective_library_profile_for_source_path(
    config: Mapping[str, Any],
    source_path: str | os.PathLike[str],
    *,
    selected_profile_id: str | None = None,
) -> dict[str, Any] | None:
    """Return the enabled effective Library profile that owns ``source_path``.

    Mirrors the pipeline engine's path-to-library resolution
    (ops/pipeline/engine/paths/library_profiles.ps1::Get-MediaPipelineLibraryProfileForPath):
    source roots are compared as resolved, case-insensitive paths and the
    deepest matching enabled source root wins. When ``selected_profile_id`` is
    supplied and that enabled profile's source root contains the path, it takes
    precedence over the deepest-match rule -- matching the engine's
    ``CurrentLibraryProfileId`` behavior. Read-only preview callers that have no
    runtime selection omit it and therefore reflect the engine's default
    (selection-free) routing.
    """
    candidate = _resolved_match_key(source_path)
    if not candidate:
        return None
    profiles = [
        profile
        for profile in effective_library_profiles_from_config(config)
        if profile.get("enabled", True)
    ]

    selected_id = str(selected_profile_id or "").strip().casefold()
    if selected_id:
        for profile in profiles:
            if str(profile.get("id") or "").strip().casefold() != selected_id:
                continue
            if _path_is_under_or_equal(candidate, _profile_match_root_key(profile)):
                return profile
            break

    best: dict[str, Any] | None = None
    best_len = -1
    for profile in profiles:
        root_key = _profile_match_root_key(profile)
        if _path_is_under_or_equal(candidate, root_key) and len(root_key) > best_len:
            best = profile
            best_len = len(root_key)
    return best
