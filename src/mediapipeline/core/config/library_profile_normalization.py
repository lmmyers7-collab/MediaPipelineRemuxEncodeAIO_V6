from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from mediapipeline.desktop.config_keys import (
    KEY_LIBRARY_PROFILES,
    KEY_OUTSOURCE,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
)

from .library_profile_defaults import (
    DEFAULT_LIBRARY_IDS,
    LIBRARY_DESIGNATIONS,
    LIBRARY_OVERRIDE_GROUP_BY_KEY,
    LIBRARY_OVERRIDE_GROUPS,
    LIBRARY_OVERRIDE_KEYS_BY_GROUP,
    LIBRARY_PROFILE_PATH_FIELDS,
    LIBRARY_PROFILE_SCHEMA_VERSION,
    LIBRARY_PROFILE_TOP_LEVEL_KEYS,
    _jsonable,
    default_tracking_for_profile,
)

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

def library_profile_signature(profile: Mapping[str, Any]) -> str:
    relevant = {key: profile.get(key) for key in LIBRARY_PROFILE_TOP_LEVEL_KEYS}
    raw = json.dumps(_jsonable(relevant), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]
