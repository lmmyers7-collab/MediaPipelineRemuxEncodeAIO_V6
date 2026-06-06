from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from mediapipeline.core.config.numeric_policy import validate_required_and_numeric_config
from mediapipeline.core.config.option_policy import validate_option_config
from mediapipeline.core.kernel.config_keys import KEY_LIBRARY_PROFILES

from .library_profile_defaults import (
    DEFAULT_LIBRARY_IDS,
    LIBRARY_DESIGNATIONS,
    LIBRARY_OVERRIDE_GROUPS,
    LIBRARY_OVERRIDE_KEYS_BY_GROUP,
    _FIELD_METADATA_BY_KEY,
)
from .library_profile_normalization import (
    _bool_value,
    _coerce_mapping,
    _default_name,
    _normalized_designation,
    _profile_id_from_mapping,
    _slug,
    _text,
    coerce_library_overrides,
    coerce_library_profiles,
    library_profiles_from_config,
)
from .library_profile_state import flatten_library_settings

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
