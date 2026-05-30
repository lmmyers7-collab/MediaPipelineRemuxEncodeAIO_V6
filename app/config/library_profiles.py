from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping
from typing import Any

from app.config.numeric_policy import validate_required_and_numeric_config
from app.config.option_policy import validate_option_config
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

DEFAULT_EDITOR_KEYS: tuple[str, ...] = (
    "RoutingProfile",
    "RouteThresholdMode",
    "SizeGuardMode",
    "EncodeTuningPreset",
    "EncodeLadder",
    "VideoCodec",
    "OutputContainer",
    "EncodeThresholdGB",
    "TVEncodeThresholdGB",
    "MovieRouteMaxVideoBitrateMbps",
    "TVRouteMaxVideoBitrateMbps",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
)

DEFAULT_VIDEO_KEYS: tuple[str, ...] = (
    "VideoPreset",
    "VideoQuality",
    "AllowH264RemuxIfPlexCompatible",
    "H264RemuxMaxBitrateMbps",
    "H264RemuxMaxHeight",
    "RemuxSafeVideoCodecs",
    "FallbackCpuQuality",
    "CpuEncodePreset",
    "CpuEncodeProcessPriority",
    "CpuEncodeMaxThreads",
    "ExtraVideoFlags",
)

DEFAULT_SUBTITLE_KEYS: tuple[str, ...] = (
    "SubKeepLanguages",
    "ConvertTx3gToSrt",
    "DropTx3gAfterConversion",
    "CreateExternalTx3gSrtSidecars",
    "Tx3gExtractLanguages",
    "Tx3gPreserveExistingSrt",
    "Tx3gTreatForcedAsSeparate",
    "ConvertBdpgsToSrt",
    "DropBdpgsAfterConversion",
    "BdpgsExtractLanguages",
    "BdpgsOcrToolPath",
    "BdpgsOcrTessdataPath",
    "SubtitleExtractTimeoutSeconds",
    "SubtitleProbeTimeoutSeconds",
    "BdpgsOcrTimeoutSeconds",
    "SubSDHTitleKeywords",
    "SubSupplementalKeywords",
    "DropAssAfterConversion",
    "StripFormatting",
    "RemoveKaraoke",
    "MergeAdjacent",
    "MergeThresholdMs",
    "KeepSignsAndSongs",
    "TreatAssSignsSongsAsForced",
    "TreatTx3gSignsSongsAsForced",
    "TreatBdpgsSignsSongsAsForced",
    "ExcludeSubtitleStyles",
    "IncludeSubtitleStyles",
)

DEFAULT_AUDIO_KEYS: tuple[str, ...] = (
    "AudioPassthroughProfile",
    "CompatibleAudioCodecs",
    "PreferredDefaultAudioLanguages",
    "AudioTranscodeCodec",
    "AudioTranscodeBitrate",
    "AudioTranscodeAutoBitrateByChannels",
    "AudioDownmixMode",
    "AudioMaxChannels",
    "AllowNoAudio",
)

DEFAULT_MEDIA_KEYS: tuple[str, ...] = DEFAULT_VIDEO_KEYS + DEFAULT_SUBTITLE_KEYS + DEFAULT_AUDIO_KEYS

LIBRARY_OVERRIDE_GROUPS: tuple[str, ...] = ("editor", "video", "subtitles", "audio")
LIBRARY_OVERRIDE_KEYS_BY_GROUP: dict[str, tuple[str, ...]] = {
    "editor": DEFAULT_EDITOR_KEYS,
    "video": DEFAULT_VIDEO_KEYS,
    "subtitles": DEFAULT_SUBTITLE_KEYS,
    "audio": DEFAULT_AUDIO_KEYS,
}
LIBRARY_OVERRIDE_GROUP_BY_KEY: dict[str, str] = {
    key: group
    for group, keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.items()
    for key in keys
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


def _tracking_mapping(profile: Mapping[str, Any], profile_id: str, designation: str) -> dict[str, Any]:
    tracking = profile.get("default_tracking")
    default_tracking = default_tracking_for_profile(profile_id, designation)
    if isinstance(tracking, Mapping):
        merged = dict(default_tracking)
        merged.update({str(key): _jsonable(value) for key, value in tracking.items()})
        if not isinstance(merged.get("field_default_keys"), Mapping):
            merged["field_default_keys"] = default_tracking["field_default_keys"]
        if not isinstance(merged.get("inherited_fields"), list):
            merged["inherited_fields"] = []
        return merged
    default_tracking["inherited_fields"] = []
    return default_tracking


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


def _normalize_profile(profile: Mapping[str, Any], config: Mapping[str, Any], index: int) -> dict[str, Any]:
    raw_id = _text(profile.get("id") or profile.get("library_id"))
    fallback_id = "library" if index <= 0 else f"library-{index}"
    profile_id = _slug(raw_id or profile.get("name"), fallback_id)
    if profile_id in {"movie", "movies"}:
        profile_id = "movies"
    elif profile_id in {"show", "shows", "tv"}:
        profile_id = "tv"

    fallback_designation = "auto"
    if profile_id == "movies":
        fallback_designation = "movie"
    elif profile_id == "tv":
        fallback_designation = "tv"
    designation = _normalized_designation(profile.get("designation"), fallback_designation)
    name = _text(profile.get("name")) or _default_name(profile_id, designation)
    tracking = _tracking_mapping(profile, profile_id, designation)
    inherited_fields = {str(item) for item in tracking.get("inherited_fields", []) if item}
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


def effective_library_profiles_from_config(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    effective: list[dict[str, Any]] = []
    for profile in library_profiles_from_config(config):
        settings = resolve_effective_library_settings(config, profile)
        overrides = coerce_library_overrides(profile)
        row = dict(profile)
        row["overrides"] = overrides
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
        seen = {
            (
                _text(rule.get("source_root")).casefold(),
                _text(rule.get("destination_root")).casefold(),
            )
            for rule in rules
            if isinstance(rule, Mapping)
        }
        for rule in existing_rules if isinstance(existing_rules, list) else []:
            if not isinstance(rule, Mapping):
                continue
            key = (_text(rule.get("source_root")).casefold(), _text(rule.get("destination_root")).casefold())
            if key in seen:
                continue
            rules.append({str(key): _jsonable(value) for key, value in rule.items()})
    return rules


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
    label = str(profile.get("name") or profile.get("id") or "Library").strip()
    overrides = coerce_library_overrides(profile)
    errors: list[str] = []
    for group, values in overrides.items():
        allowed = set(LIBRARY_OVERRIDE_KEYS_BY_GROUP.get(group, ()))
        for key in values.keys():
            if key not in allowed:
                errors.append(f"Library profile {label} override {group}.{key} is not a supported library override key.")
    return errors


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

        if source_path:
            source_key = _path_key(source_path, normalized_path_key)
            if source_key in seen_sources:
                warnings.append(f"Library profile {label} shares a source root with {seen_sources[source_key]}.")
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
    "coerce_library_profiles",
    "coerce_library_overrides",
    "default_audio_values",
    "default_editor_values",
    "default_library_settings",
    "default_media_values",
    "default_subtitle_values",
    "default_video_values",
    "effective_library_profiles_from_config",
    "empty_library_overrides",
    "flatten_library_settings",
    "library_override_state",
    "library_profile_signature",
    "library_profiles_from_config",
    "mirror_legacy_keys_from_library_profiles",
    "promotion_rules_from_library_profiles",
    "resolve_effective_library_settings",
    "validate_library_profiles",
]
