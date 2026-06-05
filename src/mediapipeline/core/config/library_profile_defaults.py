from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from mediapipeline.core.config.metadata_parts.field_definitions import (
    CONFIG_FIELD_DEFINITIONS,
    METADATA_LIBRARY_OVERRIDE_KEYS_BY_GROUP,
)
from mediapipeline.desktop.config_keys import (
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
_MISSING_DEFAULT = object()

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

def _metadata_default_for_key(key: str) -> Any:
    metadata = _FIELD_METADATA_BY_KEY.get(str(key))
    if not metadata:
        return _MISSING_DEFAULT
    if metadata.get("default_source") == "field_definition" and "default_value" in metadata:
        return _jsonable(metadata.get("default_value"))
    if "default" in metadata:
        return _jsonable(metadata.get("default"))
    return _MISSING_DEFAULT

def _default_values_for_keys(config: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in keys:
        key_text = str(key)
        if key_text in config:
            values[key_text] = _jsonable(config[key_text])
            continue
        default_value = _metadata_default_for_key(key_text)
        if default_value is not _MISSING_DEFAULT:
            values[key_text] = default_value
    return values

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

def default_editor_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return _default_values_for_keys(config, DEFAULT_EDITOR_KEYS)

def default_video_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return _default_values_for_keys(config, DEFAULT_VIDEO_KEYS)

def default_subtitle_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return _default_values_for_keys(config, DEFAULT_SUBTITLE_KEYS)

def default_audio_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return _default_values_for_keys(config, DEFAULT_AUDIO_KEYS)

def default_media_values(config: Mapping[str, Any]) -> dict[str, Any]:
    return _default_values_for_keys(config, DEFAULT_MEDIA_KEYS)

def default_library_settings(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "editor": default_editor_values(config),
        "video": default_video_values(config),
        "subtitles": default_subtitle_values(config),
        "audio": default_audio_values(config),
    }
