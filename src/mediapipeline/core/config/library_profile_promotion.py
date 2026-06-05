from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from mediapipeline.desktop.config_keys import (
    KEY_FINAL_LIBRARY_PROMOTION_RULES,
    KEY_LIBRARY_PROFILES,
    KEY_OUTSOURCE,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
)

from .library_profile_defaults import _jsonable
from .library_profile_normalization import _text, library_profiles_from_config

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
