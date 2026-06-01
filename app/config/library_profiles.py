from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping
from typing import Any

from app.config.numeric_policy import validate_required_and_numeric_config
from app.config.option_policy import validate_option_config
from app.config.metadata_parts.field_definitions import (
    CONFIG_FIELD_DEFINITIONS,
    METADATA_LIBRARY_OVERRIDE_KEYS_BY_GROUP,
)
from mediapipeline_desktop_app.config_keys import (
    KEY_FINAL_LIBRARY_PROMOTION_RULES,
    KEY_LIBRARY_PROFILES,
    KEY_OUTSOURCE,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
)

LIBRARY_PROFILE_SCHEMA_VERSION = "library_profile.v1"
LIBRARY_PROFILE_TRACKING_VERSION = "library_profile_default_tracking.v1"

LIBRARY_DESIGNATIONS: tuple[str, ...] = ("movie", "tv", "auto")
DEFAULT_LIBRARY_IDS: tuple[str, ...] = ("movies", "tv")

LIBRARY_PROFILE_PATH_FIELDS: tuple[str, ...] = (
    "source_path",
    "output_path",
    "promotion_destination",
)

LIBRARY_OVERRIDE_GROUPS: tuple[str, ...] = ("editor", "video", "subtitles", "audio")
LIBRARY_OVERRIDE_KEYS_BY_GROUP: dict[str, tuple[str, ...]] = {
    group: tuple(METADATA_LIBRARY_OVERRIDE_KEYS_BY_GROUP[group])
    for group in LIBRARY_OVERRIDE_GROUPS
}
DEFAULT_EDITOR_KEYS: tuple[str, ...] = LIBRARY_OVERRIDE_KEYS_BY_GROUP["editor"]
DEFAULT_VIDEO_KEYS: tuple[str, ...] = LIBRARY_OVERRIDE_KEYS_BY_GROUP["video"]
DEFAULT_SUBTITLE_KEYS: tuple[str, ...] = LIBRARY_OVERRIDE_KEYS_BY_GROUP["subtitles"]
DEFAULT_AUDIO_KEYS: tuple[str, ...] = LIBRARY_OVERRIDE_KEYS_BY_GROUP["audio"]
DEFAULT_MEDIA_KEYS: tuple[str, ...] = DEFAULT_VIDEO_KEYS + DEFAULT_SUBTITLE_KEYS + DEFAULT_AUDIO_KEYS
LIBRARY_OVERRIDE_GROUP_BY_KEY: dict[str, str] = {
    key: group
    for group, keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.items()
    for key in keys
}
_FIELD_METADATA_BY_KEY: dict[str, dict[str, Any]] = {
    str(field["key"]): field for field in CONFIG_FIELD_DEFINITIONS
}

LIBRARY_PROFILE_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "id",
    "name",
    "enabled",
    "designation",
    "source_path",
    "output_path",
    "promotion_enabled",
    "promotion_destination",
    "overrides",
    "editor_overrides",
    "media_overrides",
    "default_tracking",
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set):
        return [_jsonable(item) for item in value]
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, int | float):
        return value != 0
    text = str(value).strip().casefold()
    if not text:
        return default
    if text in {"1", "true", "yes", "on", "enabled", "enable"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "disable"}:
        return False
    return default


def _slug(value: Any, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().casefold()).strip("-")
    return text or fallback


def _coerce_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if value in (None, "", False):
        return {}
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} must be JSON object data.") from exc
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object.")
    return {str(key): _jsonable(item) for key, item in value.items()}


def empty_library_overrides() -> dict[str, dict[str, Any]]:
    return {group: {} for group in LIBRARY_OVERRIDE_GROUPS}


def _merge_override_group(
    target: dict[str, dict[str, Any]],
    group: str,
    values: Mapping[str, Any],
) -> None:
    normalized_group = "subtitles" if group == "subtitle" else group
    if normalized_group not in target:
        return
    for key, value in values.items():
        target[normalized_group][str(key)] = _jsonable(value)


def _merge_legacy_overrides(
    target: dict[str, dict[str, Any]],
    values: Mapping[str, Any],
    *,
    fallback_group: str,
) -> None:
    for key, value in values.items():
        key_text = str(key)
        group = LIBRARY_OVERRIDE_GROUP_BY_KEY.get(key_text, fallback_group)
        target[group][key_text] = _jsonable(value)


def coerce_library_overrides(profile: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    overrides = empty_library_overrides()
    raw_overrides = profile.get("overrides")
    if raw_overrides not in (None, "", False):
        override_map = _coerce_mapping(raw_overrides, field_name="overrides")
        for group in LIBRARY_OVERRIDE_GROUPS:
            _merge_override_group(
                overrides,
                group,
                _coerce_mapping(override_map.get(group), field_name=f"overrides.{group}"),
            )
        _merge_override_group(
            overrides,
            "subtitles",
            _coerce_mapping(override_map.get("subtitle"), field_name="overrides.subtitle"),
        )

    legacy_editor = _coerce_mapping(profile.get("editor_overrides"), field_name="editor_overrides")
    legacy_media = _coerce_mapping(profile.get("media_overrides"), field_name="media_overrides")
    _merge_legacy_overrides(overrides, legacy_editor, fallback_group="editor")
    _merge_legacy_overrides(overrides, legacy_media, fallback_group="subtitles")
    return overrides


def coerce_library_profiles(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, "", False):
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("LibraryProfiles must be JSON object/array data.") from exc
    if isinstance(raw, Mapping):
        raw = [raw]
    if not isinstance(raw, Iterable) or isinstance(raw, (bytes, bytearray, str)):
        raise TypeError("LibraryProfiles must be a list of profile objects.")
    profiles: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise TypeError("LibraryProfiles entries must be objects.")
        profiles.append({str(key): _jsonable(value) for key, value in item.items()})
    return profiles


def default_tracking_for_profile(profile_id: str, designation: str) -> dict[str, Any]:
    source_default_key = ""
    _ = designation
    if profile_id == "movies":
        source_default_key = KEY_SOURCE_MOVIES
    elif profile_id == "tv":
        source_default_key = KEY_SOURCE_TV

    inherited_fields = ["output_path"]
    field_default_keys = {"output_path": KEY_OUTSOURCE}
    if source_default_key:
        inherited_fields.append("source_path")
        field_default_keys["source_path"] = source_default_key

    return {
        "schema_version": LIBRARY_PROFILE_TRACKING_VERSION,
        "inherited_fields": inherited_fields,
        "field_default_keys": field_default_keys,
        "editor_default_keys": list(DEFAULT_EDITOR_KEYS),
        "video_default_keys": list(DEFAULT_VIDEO_KEYS),
        "subtitle_default_keys": list(DEFAULT_SUBTITLE_KEYS),
        "audio_default_keys": list(DEFAULT_AUDIO_KEYS),
        "media_default_keys": list(DEFAULT_MEDIA_KEYS),
    }


def _tracking_mapping(profile: Mapping[str, Any], profile_id: str, designation: str) -> tuple[dict[str, Any], bool]:
    tracking = profile.get("default_tracking")
    default_tracking = default_tracking_for_profile(profile_id, designation)
    inherited_fields_is_explicit = False
    if isinstance(tracking, Mapping):
        merged = dict(default_tracking)
        raw_tracking = {str(key): _jsonable(value) for key, value in tracking.items()}
        merged.update(raw_tracking)
        field_default_keys = dict(default_tracking["field_default_keys"])
        if isinstance(raw_tracking.get("field_default_keys"), Mapping):
            field_default_keys.update(
                {str(key): _jsonable(value) for key, value in raw_tracking["field_default_keys"].items()}
            )
        merged["field_default_keys"] = field_default_keys
        inherited_fields_is_explicit = isinstance(raw_tracking.get("inherited_fields"), list)
    else:
        merged = dict(default_tracking)

    if isinstance(merged.get("inherited_fields"), list):
        merged["inherited_fields"] = [str(item) for item in merged["inherited_fields"] if item]
    else:
        merged["inherited_fields"] = []
    return merged, inherited_fields_is_explicit


def _normalize_path_inheritance(
    profile: Mapping[str, Any],
    profile_id: str,
    tracking: dict[str, Any],
    *,
    inherited_fields_is_explicit: bool,
) -> set[str]:
    inherited_fields = {str(item) for item in tracking.get("inherited_fields", []) if item}

    # Output inheritance is backend-owned: blank or missing output roots follow
    # Outsource, while explicit nonblank roots stay pinned even if they match it.
    if not _text(profile.get("output_path")):
        inherited_fields.add("output_path")
    elif not inherited_fields_is_explicit:
        inherited_fields.discard("output_path")

    if profile_id in DEFAULT_LIBRARY_IDS:
        if not _text(profile.get("source_path")):
            inherited_fields.add("source_path")
        elif not inherited_fields_is_explicit:
            inherited_fields.discard("source_path")
    else:
        inherited_fields.discard("source_path")

    # Promotion destinations are safety-sensitive and must remain explicit.
    inherited_fields.discard("promotion_destination")
    tracking["inherited_fields"] = [
        field for field in LIBRARY_PROFILE_PATH_FIELDS if field in inherited_fields
    ] + sorted(
        field
        for field in inherited_fields
        if field not in set(LIBRARY_PROFILE_PATH_FIELDS)
    )
    return inherited_fields


def _default_source_for(config: Mapping[str, Any], profile_id: str, designation: str) -> str:
    if profile_id == "tv" or designation == "tv":
        return _text(config.get(KEY_SOURCE_TV))
    if profile_id == "movies" or designation == "movie":
        return _text(config.get(KEY_SOURCE_MOVIES))
    return ""


def _default_name(profile_id: str, designation: str) -> str:
    _ = designation
    if profile_id == "movies":
        return "Movies"
    if profile_id == "tv":
        return "TV"
    return profile_id.replace("-", " ").title() if profile_id else "Library"


def _normalized_designation(value: Any, fallback: str) -> str:
    designation = str(value or "").strip().casefold()
    if designation in {"mixed", "custom"}:
        return "auto"
    if designation in LIBRARY_DESIGNATIONS:
        return designation
    if fallback in {"mixed", "custom"}:
        return "auto"
    return fallback if fallback in LIBRARY_DESIGNATIONS else "auto"


def _profile_id_from_mapping(profile: Mapping[str, Any], index: int) -> str:
    raw_id = _text(profile.get("id") or profile.get("library_id"))
    fallback_id = "library" if index <= 0 else f"library-{index}"
    profile_id = _slug(raw_id or profile.get("name"), fallback_id)
    if profile_id in {"movie", "movies"}:
        return "movies"
    if profile_id in {"show", "shows", "tv"}:
        return "tv"
    return profile_id


def _normalize_profile(profile: Mapping[str, Any], config: Mapping[str, Any], index: int) -> dict[str, Any]:
    profile_id = _profile_id_from_mapping(profile, index)

    fallback_designation = "auto"
    if profile_id == "movies":
        fallback_designation = "movie"
    elif profile_id == "tv":
        fallback_designation = "tv"
    designation = _normalized_designation(profile.get("designation"), fallback_designation)
    name = _text(profile.get("name")) or _default_name(profile_id, designation)
    tracking, inherited_fields_is_explicit = _tracking_mapping(profile, profile_id, designation)
    inherited_fields = _normalize_path_inheritance(
        profile,
        profile_id,
        tracking,
        inherited_fields_is_explicit=inherited_fields_is_explicit,
    )
    field_default_keys = tracking.get("field_default_keys")
    if not isinstance(field_default_keys, Mapping):
        field_default_keys = {}

    source_path = _text(profile.get("source_path"))
    if "source_path" in inherited_fields:
        source_key = _text(field_default_keys.get("source_path"))
        if source_key:
            source_path = _text(config.get(source_key))
        else:
            source_path = _default_source_for(config, profile_id, designation)
    elif not source_path and profile_id in DEFAULT_LIBRARY_IDS:
        source_path = _default_source_for(config, profile_id, designation)

    output_path = _text(profile.get("output_path"))
    if "output_path" in inherited_fields:
        output_key = _text(field_default_keys.get("output_path")) or KEY_OUTSOURCE
        output_path = _text(config.get(output_key))
    elif not output_path and profile_id in DEFAULT_LIBRARY_IDS:
        output_path = _text(config.get(KEY_OUTSOURCE))

    promotion_destination = _text(profile.get("promotion_destination"))
    if "promotion_destination" in inherited_fields:
        promotion_key = _text(field_default_keys.get("promotion_destination"))
        promotion_destination = _text(config.get(promotion_key)) if promotion_key else ""

    overrides = coerce_library_overrides(profile)

    return {
        "id": profile_id,
        "name": name,
        "enabled": _bool_value(profile.get("enabled", True), True),
        "designation": designation,
        "source_path": source_path,
        "output_path": output_path,
        "promotion_enabled": _bool_value(profile.get("promotion_enabled", False), False),
        "promotion_destination": promotion_destination,
        "overrides": overrides,
        "default_tracking": tracking,
    }


def _default_profile(profile_id: str, config: Mapping[str, Any]) -> dict[str, Any]:
    designation = "tv" if profile_id == "tv" else "movie"
    return _normalize_profile(
        {
            "id": profile_id,
            "name": "TV" if profile_id == "tv" else "Movies",
            "designation": designation,
            "enabled": True,
            "default_tracking": default_tracking_for_profile(profile_id, designation),
        },
        config,
        0,
    )


def library_profiles_from_config(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    config_map = dict(config or {})
    raw_profiles = coerce_library_profiles(config_map.get(KEY_LIBRARY_PROFILES))
    normalized: list[dict[str, Any]] = [
        _normalize_profile(profile, config_map, index)
        for index, profile in enumerate(raw_profiles, start=1)
    ]

    by_id: dict[str, dict[str, Any]] = {str(profile["id"]): profile for profile in normalized}
    for default_id in DEFAULT_LIBRARY_IDS:
        if default_id not in by_id:
            by_id[default_id] = _default_profile(default_id, config_map)

    ordered: list[dict[str, Any]] = [by_id["movies"], by_id["tv"]]
    seen = {"movies", "tv"}
    for profile in normalized:
        profile_id = str(profile["id"])
        if profile_id in seen:
            continue
        ordered.append(profile)
        seen.add(profile_id)
    return ordered


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
    profiles = [dict(profile) for profile in library_profiles_from_config(updated)]
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


def default_editor_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(config[key]) for key in DEFAULT_EDITOR_KEYS if key in config}


def default_video_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(config[key]) for key in DEFAULT_VIDEO_KEYS if key in config}


def default_subtitle_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(config[key]) for key in DEFAULT_SUBTITLE_KEYS if key in config}


def default_audio_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(config[key]) for key in DEFAULT_AUDIO_KEYS if key in config}


def default_media_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(config[key]) for key in DEFAULT_MEDIA_KEYS if key in config}


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


def default_library_settings(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "editor": default_editor_values(config),
        "video": default_video_values(config),
        "subtitles": default_subtitle_values(config),
        "audio": default_audio_values(config),
    }


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
    config: Mapping[str, Any],
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


def library_setting_override_field_state(
    global_defaults: Mapping[str, Any],
    library_profile: Mapping[str, Any],
    group: str,
    key: str,
) -> dict[str, Any]:
    defaults = default_library_settings(global_defaults)
    inherited_value = defaults.get(group, {}).get(key)
    overrides = coerce_library_overrides(library_profile)
    group_overrides = overrides.get(group, {})
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


def library_profile_state(
    config: Mapping[str, Any],
    library_profile: Mapping[str, Any],
    *,
    raw_profile: Mapping[str, Any] | None = None,
    synthesized: bool = False,
) -> dict[str, Any]:
    setting_overrides: dict[str, dict[str, Any]] = {}
    for group, keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.items():
        setting_overrides[group] = {
            key: library_setting_override_field_state(config, library_profile, group, key)
            for key in keys
        }
    return {
        "schema_version": "library_profile_state.v1",
        "library_id": str(library_profile.get("id") or ""),
        "library_name": str(library_profile.get("name") or ""),
        "path_fields": {
            field: library_profile_path_field_state(
                config,
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


def _profile_source_path_key(value: Any) -> str:
    return str(value or "").replace("\\", "/").rstrip("/").casefold()


def effective_library_profile_for_source_path(
    config: Mapping[str, Any],
    source_path: str | os.PathLike[str],
) -> dict[str, Any] | None:
    """Return the enabled effective Library profile with the deepest matching source root."""
    candidate = _profile_source_path_key(source_path)
    if not candidate:
        return None
    matches: list[dict[str, Any]] = []
    for profile in effective_library_profiles_from_config(config):
        if not profile.get("enabled", True):
            continue
        root = _profile_source_path_key(profile.get("effective_source_root") or profile.get("source_path"))
        if root and (candidate == root or candidate.startswith(root + "/")):
            matches.append(profile)
    if not matches:
        return None
    return max(
        matches,
        key=lambda profile: len(
            _profile_source_path_key(profile.get("effective_source_root") or profile.get("source_path"))
        ),
    )


def _wizard_designation(row: Mapping[str, Any], profile_id: str) -> str:
    raw = _text(row.get("designation") or row.get("media_kind") or row.get("category")).casefold()
    if raw in {"movies", "movie"}:
        raw = "movie"
    elif raw in {"shows", "show", "television", "tv"}:
        raw = "tv"
    fallback = "movie" if profile_id == "movies" else "tv" if profile_id == "tv" else "auto"
    return _normalized_designation(raw, fallback)


def _wizard_profile_id(row: Mapping[str, Any], index: int) -> str:
    role = _text(row.get("default_source_role")).casefold()
    if role in {"source_movies", "movies"}:
        return "movies"
    if role in {"source_tv", "tv"}:
        return "tv"
    raw_id = _text(row.get("id") or row.get("library_id") or row.get("name"))
    profile_id = _slug(raw_id, f"library-{index}")
    if profile_id in {"movie", "movies"}:
        return "movies"
    if profile_id in {"show", "shows", "tv"}:
        return "tv"
    return profile_id


def _wizard_row_to_profile(
    row: Mapping[str, Any],
    *,
    index: int,
    output_root: str,
    existing_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    profile_id = _wizard_profile_id(row, index)
    existing = existing_by_id.get(profile_id, {})
    designation = _wizard_designation(row, profile_id)
    source_path = _text(row.get("source_path"))
    output_path = _text(row.get("output_path"))
    promotion_destination = _text(row.get("promotion_destination"))
    tracking = row.get("default_tracking")
    if not isinstance(tracking, Mapping) or not tracking:
        tracking = existing.get("default_tracking") if isinstance(existing.get("default_tracking"), Mapping) else None
    if not isinstance(tracking, Mapping):
        tracking = default_tracking_for_profile(profile_id, designation)
    tracking = {str(key): _jsonable(value) for key, value in dict(tracking).items()}
    inherited_fields = {str(item) for item in tracking.get("inherited_fields", []) if item}
    if output_path and output_root and output_path.casefold() != output_root.casefold():
        inherited_fields.discard("output_path")
    elif "output_path" not in inherited_fields and not output_path:
        inherited_fields.add("output_path")
    ordered_inherited = [field for field in LIBRARY_PROFILE_PATH_FIELDS if field in inherited_fields]
    ordered_inherited.extend(sorted(field for field in inherited_fields if field not in set(ordered_inherited)))
    tracking["inherited_fields"] = ordered_inherited

    row_has_override_payload = any(
        row.get(field) not in (None, "", False)
        for field in ("overrides", "editor_overrides", "media_overrides")
    )
    candidate_overrides = coerce_library_overrides(row) if row_has_override_payload else empty_library_overrides()
    if not any(candidate_overrides[group] for group in LIBRARY_OVERRIDE_GROUPS):
        overrides = existing.get("overrides") if isinstance(existing.get("overrides"), Mapping) else candidate_overrides
    else:
        overrides = candidate_overrides

    return {
        "id": profile_id,
        "name": _text(row.get("name")) or _default_name(profile_id, designation),
        "enabled": True if profile_id in DEFAULT_LIBRARY_IDS else _bool_value(row.get("enabled", True), True),
        "designation": designation,
        "source_path": source_path,
        "output_path": output_path,
        "promotion_enabled": _bool_value(row.get("promotion_enabled", existing.get("promotion_enabled", False)), False),
        "promotion_destination": promotion_destination or _text(existing.get("promotion_destination")),
        "overrides": _jsonable(overrides),
        "default_tracking": tracking,
    }


def library_profiles_from_wizard_payload(
    wizard: Mapping[str, Any],
    base_config: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build canonical library profiles from setup-wizard rows.

    The wizard can expose a smaller row editor than the Library Profiles tab.
    This helper keeps the conversion backend-owned and preserves existing
    overrides/default tracking for rows the wizard did not explicitly edit.
    """

    seed = dict(base_config or {})
    output = wizard.get("output", {}) if isinstance(wizard.get("output"), Mapping) else {}
    output_root = _text(output.get("root") or seed.get(KEY_OUTSOURCE))
    if output_root:
        seed[KEY_OUTSOURCE] = output_root

    existing_profiles = library_profiles_from_config(seed)
    existing_by_id = {str(profile.get("id") or ""): profile for profile in existing_profiles}
    rows = wizard.get("libraries", [])
    raw_profiles: list[dict[str, Any]] = []
    if isinstance(rows, Iterable) and not isinstance(rows, (bytes, bytearray, str, Mapping)):
        for index, item in enumerate(rows, start=1):
            if not isinstance(item, Mapping):
                continue
            profile = _wizard_row_to_profile(
                item,
                index=index,
                output_root=output_root,
                existing_by_id=existing_by_id,
            )
            raw_profiles.append(profile)
            source_path = _text(profile.get("source_path"))
            if profile["id"] == "movies" and source_path:
                seed[KEY_SOURCE_MOVIES] = source_path
            elif profile["id"] == "tv" and source_path:
                seed[KEY_SOURCE_TV] = source_path

    seed[KEY_LIBRARY_PROFILES] = raw_profiles
    return library_profiles_from_config(seed)


def promotion_rules_from_library_profiles(
    config: Mapping[str, Any],
    *,
    include_existing: bool = True,
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for profile in library_profiles_from_config(config):
        if not profile.get("enabled") or not profile.get("promotion_enabled"):
            continue
        source_root = _text(profile.get("source_path"))
        destination_root = _text(profile.get("promotion_destination"))
        if not source_root or not destination_root:
            continue
        profile_id = str(profile.get("id") or "")
        rules.append(
            {
                "id": f"library-profile-{profile_id}",
                "label": f"{profile.get('name') or profile_id} promotion",
                "enabled": True,
                "source_root": source_root,
                "output_root": _text(profile.get("output_path")),
                "destination_root": destination_root,
                "library_id": profile_id,
                "designation": str(profile.get("designation") or ""),
            }
        )

    if include_existing:
        existing = config.get(KEY_FINAL_LIBRARY_PROMOTION_RULES)
        try:
            existing_rules = existing if isinstance(existing, list) else json.loads(existing) if isinstance(existing, str) and existing.strip() else []
        except json.JSONDecodeError:
            existing_rules = []
        profile_source_roots = {
            _text(rule.get("source_root")).rstrip("\\/").casefold()
            for rule in rules
            if isinstance(rule, Mapping)
        }
        for rule in existing_rules if isinstance(existing_rules, list) else []:
            if not isinstance(rule, Mapping):
                continue
            source_root_key = _text(rule.get("source_root")).rstrip("\\/").casefold()
            if source_root_key and source_root_key in profile_source_roots:
                continue
            rules.append({str(key): _jsonable(value) for key, value in rule.items()})
    return rules


def normalize_library_profile_config_values(
    values: Mapping[str, Any],
    *,
    require_profiles: bool = False,
) -> dict[str, Any]:
    normalized = dict(values or {})
    if require_profiles and KEY_LIBRARY_PROFILES not in normalized:
        return normalized
    try:
        profiles = library_profiles_from_config(normalized)
    except Exception:
        return normalized
    normalized[KEY_LIBRARY_PROFILES] = profiles
    mirrored = mirror_legacy_keys_from_library_profiles(normalized, require_profiles=True)
    mirrored[KEY_LIBRARY_PROFILES] = profiles
    return mirrored


def mirror_legacy_keys_from_library_profiles(
    values: Mapping[str, Any],
    *,
    require_profiles: bool = False,
) -> dict[str, Any]:
    mirrored = dict(values or {})
    if require_profiles and KEY_LIBRARY_PROFILES not in mirrored:
        return mirrored
    try:
        profiles = library_profiles_from_config(mirrored)
    except Exception:
        return mirrored
    if KEY_LIBRARY_PROFILES not in mirrored and require_profiles:
        return mirrored

    movie = next((profile for profile in profiles if profile.get("designation") == "movie" and profile.get("enabled", True)), None)
    tv = next((profile for profile in profiles if profile.get("designation") == "tv" and profile.get("enabled", True)), None)
    first_enabled = next((profile for profile in profiles if profile.get("enabled", True)), None)

    if movie and _text(movie.get("source_path")):
        mirrored[KEY_SOURCE_MOVIES] = _text(movie.get("source_path"))
    if tv and _text(tv.get("source_path")):
        mirrored[KEY_SOURCE_TV] = _text(tv.get("source_path"))
    output_profile = movie or first_enabled
    if output_profile and _text(output_profile.get("output_path")):
        mirrored[KEY_OUTSOURCE] = _text(output_profile.get("output_path"))

    profile_rules = promotion_rules_from_library_profiles(mirrored, include_existing=True)
    if profile_rules:
        mirrored[KEY_FINAL_LIBRARY_PROMOTION_RULES] = profile_rules
    return mirrored


def _path_key(path: str, normalized_path_key: Any) -> str:
    try:
        return str(normalized_path_key(path))
    except Exception:
        try:
            return os.path.normcase(os.path.abspath(path))
        except (OSError, ValueError):
            return path.strip().casefold()


def _overlap_warning(
    left_label: str,
    left_path: str,
    right_label: str,
    right_path: str,
    *,
    normalized_path_key: Any,
    path_within_root: Any,
) -> str | None:
    if not left_path or not right_path:
        return None
    left = _path_key(left_path, normalized_path_key)
    right = _path_key(right_path, normalized_path_key)
    if not left or not right:
        return None
    if left == right:
        return f"{left_label} and {right_label} point to the same path."
    try:
        if path_within_root(left_path, right_path):
            return f"{left_label} is inside {right_label}. Keep library source, output, and promotion roots separated."
        if path_within_root(right_path, left_path):
            return f"{right_label} is inside {left_label}. Keep library source, output, and promotion roots separated."
    except Exception:
        return None
    return None


def _profile_override_errors(profile: Mapping[str, Any]) -> list[str]:
    profile_id = _profile_id_from_mapping(profile, 0)
    designation = _normalized_designation(profile.get("designation"), "auto")
    label = _text(profile.get("name")) or _default_name(profile_id, designation)
    overrides = coerce_library_overrides(profile)
    errors: list[str] = []
    for group, values in overrides.items():
        for key in values.keys():
            error = _library_override_key_error(label, group, str(key))
            if error:
                errors.append(error)
    return errors


def _library_override_key_error(label: str, group: str, key: str) -> str | None:
    allowed = set(LIBRARY_OVERRIDE_KEYS_BY_GROUP.get(group, ()))
    if key not in allowed:
        return f"Library profile {label} override {group}.{key} is not a supported library override key."

    metadata = _FIELD_METADATA_BY_KEY.get(key)
    if (
        not metadata
        or metadata.get("scope") != "library_overridable"
        or metadata.get("override_group") != group
        or not metadata.get("library_override_allowed")
    ):
        return f"Library profile {label} override {group}.{key} is not library-overridable according to backend metadata."
    return None


def _raw_profile_override_errors(profile: Mapping[str, Any]) -> list[str]:
    raw_overrides = profile.get("overrides")
    if raw_overrides in (None, "", False):
        return []

    profile_id = _profile_id_from_mapping(profile, 0)
    designation = _normalized_designation(profile.get("designation"), "auto")
    label = _text(profile.get("name")) or _default_name(profile_id, designation)
    errors: list[str] = []
    try:
        override_map = _coerce_mapping(raw_overrides, field_name="overrides")
    except Exception as exc:
        return [f"Library profile {label} overrides is invalid: {exc}"]

    for raw_group, raw_values in override_map.items():
        group = "subtitles" if str(raw_group) == "subtitle" else str(raw_group)
        if group not in LIBRARY_OVERRIDE_GROUPS:
            errors.append(f"Library profile {label} override group is unsupported: {raw_group}.")
            continue
        try:
            _coerce_mapping(raw_values, field_name=f"overrides.{raw_group}")
        except Exception as exc:
            errors.append(f"Library profile {label} overrides.{raw_group} is invalid: {exc}")
    return errors


def validate_raw_library_profile_override_groups(values: Mapping[str, Any], errors: list[str]) -> None:
    try:
        raw_profiles = coerce_library_profiles(values.get(KEY_LIBRARY_PROFILES))
    except Exception:
        return
    for raw_profile in raw_profiles:
        errors.extend(_raw_profile_override_errors(raw_profile))


def _validate_profile_effective_settings(
    base_values: Mapping[str, Any],
    profile: Mapping[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    label = str(profile.get("name") or profile.get("id") or "Library").strip()
    overrides = flatten_library_settings(coerce_library_overrides(profile))
    if not overrides:
        return

    candidate = dict(base_values or {})
    candidate.update(overrides)
    override_errors: list[str] = []
    override_warnings: list[str] = []
    validate_required_and_numeric_config(candidate, override_errors)
    validate_option_config(candidate, override_errors, override_warnings)
    for message in override_errors:
        errors.append(f"Library profile {label} override is invalid: {message}")
    for message in override_warnings:
        warnings.append(f"Library profile {label} override review: {message}")


def validate_library_profiles(
    values: Mapping[str, Any],
    errors: list[str],
    warnings: list[str],
    *,
    normalized_path_key: Any,
    path_within_root: Any,
) -> None:
    try:
        raw_profiles = coerce_library_profiles(values.get(KEY_LIBRARY_PROFILES))
    except Exception as exc:
        errors.append(f"LibraryProfiles is invalid: {exc}")
        return
    raw_seen_ids: set[str] = set()
    for index, raw_profile in enumerate(raw_profiles, start=1):
        raw_id = _slug(raw_profile.get("id") or raw_profile.get("library_id") or raw_profile.get("name"), f"library-{index}")
        if raw_id in {"movie", "movies"}:
            raw_id = "movies"
        elif raw_id in {"show", "shows", "tv"}:
            raw_id = "tv"
        raw_designation = str(raw_profile.get("designation") or "").strip().casefold()
        raw_name = _text(raw_profile.get("name"))
        raw_label = raw_name or _default_name(raw_id, raw_designation)
        if raw_designation in {"mixed", "custom"}:
            warnings.append(f"Library profile {raw_label} designation '{raw_designation}' is legacy; use auto.")
        elif raw_designation and raw_designation not in LIBRARY_DESIGNATIONS:
            errors.append(f"Library profile {raw_label} designation must be movie, tv, or auto.")
        if raw_id in raw_seen_ids:
            errors.append(f"Library profile id is duplicated: {raw_id}.")
        raw_seen_ids.add(raw_id)
        errors.extend(_raw_profile_override_errors(raw_profile))

    try:
        profiles = library_profiles_from_config(values)
    except Exception as exc:
        errors.append(f"LibraryProfiles is invalid: {exc}")
        return

    raw_profiles_present = KEY_LIBRARY_PROFILES in values and values.get(KEY_LIBRARY_PROFILES) not in (None, "", False)
    if not raw_profiles_present:
        return

    seen_ids: set[str] = set()
    seen_sources: dict[str, str] = {}
    for profile in profiles:
        profile_id = str(profile.get("id") or "").strip()
        label = str(profile.get("name") or profile_id or "Library").strip()
        if not profile_id:
            errors.append(f"Library profile {label} is missing id.")
        elif profile_id in seen_ids:
            errors.append(f"Library profile id is duplicated: {profile_id}.")
        seen_ids.add(profile_id)

        designation = str(profile.get("designation") or "").strip().casefold()
        if designation not in LIBRARY_DESIGNATIONS:
            errors.append(f"Library profile {label} designation must be movie, tv, or auto.")

        source_path = _text(profile.get("source_path"))
        output_path = _text(profile.get("output_path"))
        promotion_destination = _text(profile.get("promotion_destination"))
        enabled = _bool_value(profile.get("enabled", True), True)
        promotion_enabled = _bool_value(profile.get("promotion_enabled", False), False)

        if profile_id in DEFAULT_LIBRARY_IDS and not enabled:
            errors.append(f"{label} is a required default library and cannot be disabled.")
        if enabled and not source_path:
            errors.append(f"Library profile {label} source_path is required.")
        if enabled and not output_path:
            errors.append(f"Library profile {label} output_path is required.")
        if enabled and promotion_enabled and not promotion_destination:
            errors.append(f"Library profile {label} promotion_destination is required when promotion is enabled.")

        if enabled and source_path:
            source_key = _path_key(source_path, normalized_path_key)
            if source_key in seen_sources:
                errors.append(f"Library profile {label} shares an enabled source root with {seen_sources[source_key]}.")
            else:
                seen_sources[source_key] = label

        for warning in (
            _overlap_warning(
                f"Library profile {label} source_path",
                source_path,
                f"Library profile {label} output_path",
                output_path,
                normalized_path_key=normalized_path_key,
                path_within_root=path_within_root,
            ),
            _overlap_warning(
                f"Library profile {label} source_path",
                source_path,
                f"Library profile {label} promotion_destination",
                promotion_destination,
                normalized_path_key=normalized_path_key,
                path_within_root=path_within_root,
            ),
            _overlap_warning(
                f"Library profile {label} output_path",
                output_path,
                f"Library profile {label} promotion_destination",
                promotion_destination,
                normalized_path_key=normalized_path_key,
                path_within_root=path_within_root,
            ),
        ):
            if warning:
                warnings.append(warning)

        errors.extend(_profile_override_errors(profile))
        _validate_profile_effective_settings(values, profile, errors, warnings)


def library_profile_signature(profile: Mapping[str, Any]) -> str:
    relevant = {key: profile.get(key) for key in LIBRARY_PROFILE_TOP_LEVEL_KEYS}
    raw = json.dumps(_jsonable(relevant), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


__all__ = [
    "DEFAULT_EDITOR_KEYS",
    "DEFAULT_AUDIO_KEYS",
    "DEFAULT_LIBRARY_IDS",
    "DEFAULT_MEDIA_KEYS",
    "DEFAULT_SUBTITLE_KEYS",
    "DEFAULT_VIDEO_KEYS",
    "LIBRARY_DESIGNATIONS",
    "LIBRARY_OVERRIDE_GROUPS",
    "LIBRARY_PROFILE_SCHEMA_VERSION",
    "apply_library_profile_resets",
    "coerce_library_profiles",
    "coerce_library_overrides",
    "default_audio_values",
    "default_editor_values",
    "default_library_settings",
    "default_media_values",
    "default_subtitle_values",
    "default_video_values",
    "effective_library_profile_for_source_path",
    "effective_library_profiles_from_config",
    "empty_library_overrides",
    "flatten_library_settings",
    "library_override_state",
    "library_profile_signature",
    "library_profile_state",
    "library_profile_state_from_config",
    "library_profiles_from_config",
    "library_profiles_from_wizard_payload",
    "library_profile_path_field_state",
    "library_setting_override_field_state",
    "mirror_legacy_keys_from_library_profiles",
    "normalize_library_profile_config_values",
    "promotion_rules_from_library_profiles",
    "resolve_effective_library_settings",
    "validate_raw_library_profile_override_groups",
    "validate_library_profiles",
]
