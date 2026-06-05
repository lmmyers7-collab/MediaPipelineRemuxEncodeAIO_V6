from __future__ import annotations

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
    LIBRARY_OVERRIDE_GROUPS,
    LIBRARY_PROFILE_PATH_FIELDS,
    _jsonable,
    default_tracking_for_profile,
)
from .library_profile_normalization import (
    _bool_value,
    _default_name,
    _normalized_designation,
    _slug,
    _text,
    coerce_library_overrides,
    empty_library_overrides,
    library_profiles_from_config,
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
