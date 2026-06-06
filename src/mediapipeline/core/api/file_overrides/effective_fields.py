from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mediapipeline.core.config.constants import (
    ROUTE_THRESHOLD_MODE_NAMES,
)
from mediapipeline.core.config.library_profiles import (
    default_library_settings,
    effective_library_profile_for_source_path,
    flatten_library_settings,
)
from mediapipeline.core.queue.file_overrides import (
    SUPPORTED_FILE_OVERRIDE_ENCODE_LADDERS,
    SUPPORTED_FILE_OVERRIDE_ENCODE_PRESETS,
    SUPPORTED_FILE_OVERRIDE_OUTPUT_CONTAINERS,
    SUPPORTED_FILE_OVERRIDE_ROUTE_PROFILES,
    SUPPORTED_FILE_OVERRIDE_VIDEO_CODECS,
    normalize_file_override_path,
    resolve_file_override_match,
)
from mediapipeline.core.kernel.config_keys import (
    KEY_AUDIO_MAX_CHANNELS,
    KEY_ENCODE_LADDER,
    KEY_ENCODE_TUNING_PRESET,
    KEY_OUTPUT_CONTAINER,
    KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES,
    KEY_ROUTE_THRESHOLD_MODE,
    KEY_ROUTING_PROFILE,
    KEY_SUB_KEEP_LANGUAGES,
    KEY_VIDEO_CODEC,
)

from .results import _mapping
from .selectors import _effective_track_metadata, _resolved_track_actions, _track_selection_preview
from .tracks import _probe_tracks_for_source_path


def _language_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            text = str(item.get("language") or item.get("value") or item.get("id") or "").strip().lower()
        else:
            text = str(item or "").strip().lower()
        if text:
            values.append(text)
    return values


def _channel_value(value: Any) -> int | str | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or None


def _display_list(values: list[str]) -> str:
    return ", ".join(values) if values else "not set"


def _display_scalar(value: Any, *, unit: str = "") -> str:
    if isinstance(value, list):
        return _display_list([str(item) for item in value if str(item).strip()])
    if isinstance(value, bool):
        return "true" if value else "false"
    if value in (None, ""):
        return "not set"
    return f"{value} {unit}".strip() if unit else str(value)


def _display_choice_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("_", " ").replace("-", " ").title()


def _choice_options(values: list[Any] | tuple[Any, ...] | frozenset[Any]) -> list[dict[str, str]]:
    return [
        {"value": text, "label": _display_choice_label(text)}
        for text in sorted(str(value) for value in values if str(value or "").strip())
    ]


def _display_language_scalar(value: Any) -> str:
    if isinstance(value, list):
        values = [str(item or "").strip().lower() for item in value if str(item or "").strip()]
        return values[0] if values else "not set"
    text = str(value or "").strip().lower()
    return text or "not set"


def _language_scalar_value(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            text = str(item or "").strip().lower()
            if text:
                return text
        return None
    text = str(value or "").strip().lower()
    return text or None


def _unavailable_field() -> dict[str, Any]:
    return {
        "available":  False,
        "value":      None,
        "display":    "",
        "source":     "unavailable",
        "source_key": None,
    }


def _profile_effective_media(profile: Mapping[str, Any] | None, config: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    if isinstance(profile, Mapping):
        media = _mapping(profile.get("effective_media"))
        if not media:
            media = flatten_library_settings(_mapping(profile.get("effective_settings")))
        return media, "library"
    defaults = flatten_library_settings(default_library_settings(config))
    return defaults, "global_default" if defaults else "unavailable"


def _profile_effective_route_settings(profile: Mapping[str, Any] | None, config: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    if isinstance(profile, Mapping):
        settings = flatten_library_settings(_mapping(profile.get("effective_settings")))
        return settings, "library"
    defaults = flatten_library_settings(default_library_settings(config))
    return defaults, "global_default" if defaults else "unavailable"


def _library_response(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(profile, Mapping):
        return {"available": False, "id": "", "name": "", "source_path": ""}
    return {
        "available":   True,
        "id":          str(profile.get("id") or profile.get("library_id") or ""),
        "name":        str(profile.get("name") or profile.get("library_name") or ""),
        "source_path": str(profile.get("effective_source_root") or profile.get("source_path") or ""),
    }


def _inherited_drawer_fields(settings: Mapping[str, Any], source: str) -> dict[str, dict[str, Any]]:
    key_specs = {
        "audioKeepLanguages":    (KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES, "language", ""),
        "audioDropLanguages":    ("", "", ""),
        "audioMaxChannels":      (KEY_AUDIO_MAX_CHANNELS, "channel", "channels"),
        "subtitleKeepLanguages": (KEY_SUB_KEEP_LANGUAGES, "language", ""),
        "subtitleDropLanguages": ("", "", ""),
        "subtitleBurnTrack":     ("", "", ""),
        "subtitleStripAll":      ("", "", ""),
    }
    inherited: dict[str, dict[str, Any]] = {}
    for field, (setting_key, value_kind, unit) in key_specs.items():
        if not setting_key or source == "unavailable" or setting_key not in settings:
            inherited[field] = _unavailable_field()
            continue
        raw_value = settings.get(setting_key)
        if value_kind == "language":
            value: Any = _language_values(raw_value)
            display = _display_list(value)
        elif value_kind == "channel":
            value = _channel_value(raw_value)
            display = _display_scalar(value, unit=unit)
        else:
            value = raw_value
            display = _display_scalar(value, unit=unit)
        inherited[field] = {
            "available":  True,
            "value":      value,
            "display":    display,
            "source":     source,
            "source_key": setting_key,
        }
    return inherited


def _override_drawer_fields(entry: Mapping[str, Any], source: str) -> dict[str, dict[str, Any]]:
    audio = _mapping(entry.get("audio"))
    subtitles = _mapping(entry.get("subtitles"))
    fields: dict[str, dict[str, Any]] = {}

    keep_audio = _language_values(audio.get("keepTracks"))
    if keep_audio:
        fields["audioKeepLanguages"] = {"value": keep_audio, "display": _display_list(keep_audio), "source": source}

    drop_audio = _language_values(audio.get("dropTracks"))
    if drop_audio:
        fields["audioDropLanguages"] = {"value": drop_audio, "display": _display_list(drop_audio), "source": source}

    if "maxChannels" in audio:
        max_channels = _channel_value(audio.get("maxChannels"))
        if max_channels is not None:
            fields["audioMaxChannels"] = {
                "value":   max_channels,
                "display": _display_scalar(max_channels, unit="channels"),
                "source":  source,
            }

    keep_subs = _language_values(subtitles.get("keepTracks"))
    if keep_subs:
        fields["subtitleKeepLanguages"] = {"value": keep_subs, "display": _display_list(keep_subs), "source": source}

    drop_subs = _language_values(subtitles.get("dropTracks"))
    if drop_subs:
        fields["subtitleDropLanguages"] = {"value": drop_subs, "display": _display_list(drop_subs), "source": source}

    if "stripAll" in subtitles:
        strip_all = bool(subtitles.get("stripAll"))
        fields["subtitleStripAll"] = {
            "value":   strip_all,
            "display": _display_scalar(strip_all),
            "source":  source,
        }

    burn_track = subtitles.get("burnTrack")
    if isinstance(burn_track, Mapping):
        stream_index = burn_track.get("streamIndex")
        display = f"stream {stream_index}" if stream_index is not None else "selected subtitle"
        fields["subtitleBurnTrack"] = {
            "value":   dict(burn_track),
            "display": display,
            "source":  source,
        }

    return fields


def _effective_drawer_fields(
    inherited: Mapping[str, Mapping[str, Any]],
    override_fields: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    source_paths = {
        "audioKeepLanguages":    "audio.keepTracks",
        "audioDropLanguages":    "audio.dropTracks",
        "audioMaxChannels":      "audio.maxChannels",
        "subtitleKeepLanguages": "subtitles.keepTracks",
        "subtitleDropLanguages": "subtitles.dropTracks",
        "subtitleBurnTrack":     "subtitles.burnTrack",
        "subtitleStripAll":      "subtitles.stripAll",
    }
    effective: dict[str, dict[str, Any]] = {}
    sources: dict[str, str] = {}
    for field, source_path in source_paths.items():
        override_value = override_fields.get(field)
        if isinstance(override_value, Mapping):
            effective[field] = dict(override_value)
            sources[source_path] = str(override_value.get("source") or "file_override")
            continue
        inherited_value = inherited.get(field)
        if isinstance(inherited_value, Mapping) and inherited_value.get("available"):
            effective[field] = {
                "value":   inherited_value.get("value"),
                "display": inherited_value.get("display") or "",
                "source":  inherited_value.get("source") or "library",
            }
            sources[source_path] = str(inherited_value.get("source") or "library")
            continue
        effective[field] = {"value": None, "display": "", "source": "unavailable"}
        sources[source_path] = "unavailable"
    return effective, sources


def _expanded_field_metadata(
    *,
    field_path: str,
    inherited_available: bool,
    inherited_value: Any,
    inherited_source: str,
    inherited_source_key: str | None,
    override_present: bool,
    override_value: Any,
    override_source: str,
    override_source_key: str | None,
    can_clear_file_field: bool,
) -> dict[str, Any]:
    inherited_display = _display_language_scalar(inherited_value) if inherited_available else ""
    if override_present:
        effective_value = override_value
        effective_display = _display_language_scalar(override_value)
        effective_source = override_source
        effective_source_key = override_source_key
        available = True
    elif inherited_available:
        effective_value = inherited_value
        effective_display = inherited_display
        effective_source = inherited_source
        effective_source_key = inherited_source_key
        available = True
    else:
        effective_value = None
        effective_display = ""
        effective_source = "unavailable"
        effective_source_key = None
        available = False
    return {
        "field_path":           field_path,
        "available":            available,
        "value":                effective_value,
        "display":              effective_display,
        "source":               effective_source,
        "source_key":           effective_source_key,
        "can_clear_file_field": can_clear_file_field,
        "inherited": {
            "available":  inherited_available,
            "value":      inherited_value if inherited_available else None,
            "display":    inherited_display,
            "source":     inherited_source if inherited_available else "unavailable",
            "source_key": inherited_source_key if inherited_available else None,
        },
        "effective": {
            "available":            available,
            "value":                effective_value,
            "display":              effective_display,
            "source":               effective_source,
            "source_key":           effective_source_key,
            "can_clear_file_field": can_clear_file_field,
        },
    }


def _expanded_effective_fields(
    *,
    entry: Mapping[str, Any],
    library_effective_settings: Mapping[str, Any],
    inherited_source: str,
    override_source: str,
    is_exact_file_override: bool,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    audio = _mapping(entry.get("audio"))
    inherited_raw = library_effective_settings.get(KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES)
    inherited_value = _language_scalar_value(inherited_raw)
    inherited_available = inherited_source != "unavailable" and inherited_value is not None
    override_present = "preferDefaultLanguage" in audio
    override_value = _language_scalar_value(audio.get("preferDefaultLanguage")) if override_present else None
    field_path = "audio.preferDefaultLanguage"
    fields = {
        "audioPreferDefaultLanguage": _expanded_field_metadata(
            field_path=field_path,
            inherited_available=inherited_available,
            inherited_value=inherited_value,
            inherited_source=inherited_source,
            inherited_source_key=KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES,
            override_present=override_present and override_value is not None,
            override_value=override_value,
            override_source=override_source,
            override_source_key=field_path,
            can_clear_file_field=bool(is_exact_file_override and override_present and override_value is not None),
        )
    }
    return fields, {field_path: fields["audioPreferDefaultLanguage"]["source"]}


def _expanded_scalar_field_metadata(
    *,
    field_path: str,
    inherited_available: bool,
    inherited_value: Any,
    inherited_source: str,
    inherited_source_key: str | None,
    override_present: bool,
    override_value: Any,
    override_source: str,
    override_source_key: str | None,
    can_clear_file_field: bool,
    warnings: list[str] | None = None,
    choices: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    inherited_display = _display_scalar(inherited_value) if inherited_available else ""
    if override_present:
        effective_value = override_value
        effective_display = _display_scalar(override_value)
        effective_source = override_source
        effective_source_key = override_source_key
        available = True
    elif inherited_available:
        effective_value = inherited_value
        effective_display = inherited_display
        effective_source = inherited_source
        effective_source_key = inherited_source_key
        available = True
    else:
        effective_value = None
        effective_display = ""
        effective_source = "unavailable"
        effective_source_key = None
        available = False
    return {
        "field_path":           field_path,
        "available":            available,
        "value":                effective_value,
        "display":              effective_display,
        "source":               effective_source,
        "source_key":           effective_source_key,
        "can_clear_file_field": can_clear_file_field,
        "warnings":             list(warnings or []),
        "choices":              list(choices or []),
        "inherited": {
            "available":  inherited_available,
            "value":      inherited_value if inherited_available else None,
            "display":    inherited_display,
            "source":     inherited_source if inherited_available else "unavailable",
            "source_key": inherited_source_key if inherited_available else None,
        },
        "file_override": {
            "available":  override_present,
            "value":      override_value if override_present else None,
            "display":    _display_scalar(override_value) if override_present else "",
            "source":     override_source if override_present else "unavailable",
            "source_key": override_source_key if override_present else None,
        },
        "effective": {
            "available":            available,
            "value":                effective_value,
            "display":              effective_display,
            "source":               effective_source,
            "source_key":           effective_source_key,
            "can_clear_file_field": can_clear_file_field,
            "warnings":             list(warnings or []),
            "choices":              list(choices or []),
        },
    }


def _expanded_route_video_fields(
    *,
    entry: Mapping[str, Any],
    library_effective_settings: Mapping[str, Any],
    inherited_source: str,
    override_source: str,
    is_exact_file_override: bool,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    routing = _mapping(entry.get("routing"))
    video = _mapping(entry.get("video"))
    specs = {
        "routeProfile":              ("routing.profile", "routing", "profile", KEY_ROUTING_PROFILE, SUPPORTED_FILE_OVERRIDE_ROUTE_PROFILES),
        "routingRouteThresholdMode": ("routing.routeThresholdMode", "routing", "routeThresholdMode", KEY_ROUTE_THRESHOLD_MODE, ROUTE_THRESHOLD_MODE_NAMES),
        "videoCodec":                ("video.codec", "video", "codec", KEY_VIDEO_CODEC, SUPPORTED_FILE_OVERRIDE_VIDEO_CODECS),
        "videoContainer":            ("video.container", "video", "container", KEY_OUTPUT_CONTAINER, SUPPORTED_FILE_OVERRIDE_OUTPUT_CONTAINERS),
        "videoEncodePreset":         ("video.encodePreset", "video", "encodePreset", KEY_ENCODE_TUNING_PRESET, SUPPORTED_FILE_OVERRIDE_ENCODE_PRESETS),
        "videoEncodeLadder":         ("video.encodeLadder", "video", "encodeLadder", KEY_ENCODE_LADDER, SUPPORTED_FILE_OVERRIDE_ENCODE_LADDERS),
    }
    sections = {"routing": routing, "video": video}
    fields: dict[str, dict[str, Any]] = {}
    sources: dict[str, str] = {}
    for field_name, (field_path, section_name, child_key, inherited_key, choices) in specs.items():
        section = sections.get(section_name, {})
        override_present = child_key in section and section.get(child_key) not in (None, "")
        override_value = section.get(child_key) if override_present else None
        inherited_value = library_effective_settings.get(inherited_key)
        inherited_available = (
            inherited_source != "unavailable"
            and inherited_key in library_effective_settings
            and inherited_value not in (None, "")
        )
        field_warnings: list[str] = []
        effective_value = override_value if override_present else inherited_value if inherited_available else None
        if field_path == "routing.profile" and str(effective_value or "").strip().casefold() in {"encode", "transcode"}:
            field_warnings.append("Effective routing profile may force a full video transcode.")
        if field_path == "video.container" and str(effective_value or "").strip().casefold() in {"mp4", "m4v", "mov"}:
            field_warnings.append("Effective MP4-family output may force a full video transcode.")
        metadata = _expanded_scalar_field_metadata(
            field_path=field_path,
            inherited_available=inherited_available,
            inherited_value=inherited_value,
            inherited_source=inherited_source,
            inherited_source_key=inherited_key,
            override_present=override_present,
            override_value=override_value,
            override_source=override_source,
            override_source_key=field_path,
            can_clear_file_field=bool(is_exact_file_override and override_present),
            warnings=field_warnings,
            choices=_choice_options(choices),
        )
        fields[field_name] = metadata
        sources[field_path] = str(metadata.get("source") or "unavailable")
    return fields, sources


def _route_video_processing_projection(
    route_video_fields: Mapping[str, Mapping[str, Any]],
    entry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    def effective(field_name: str) -> dict[str, Any]:
        return _mapping(_mapping(route_video_fields.get(field_name)).get("effective"))

    route_profile = str(effective("routeProfile").get("value") or "").strip().casefold()
    container = str(effective("videoContainer").get("value") or "").strip().casefold()
    video_codec = str(effective("videoCodec").get("value") or "").strip()
    encode_preset = str(effective("videoEncodePreset").get("value") or "").strip()
    encode_ladder = str(effective("videoEncodeLadder").get("value") or "").strip()
    subtitles = _mapping(_mapping(entry or {}).get("subtitles"))
    has_burn_track = isinstance(subtitles.get("burnTrack"), Mapping)
    def override_sourced(field_name: str) -> bool:
        return str(effective(field_name).get("source") or "") in {"file_override", "folder_override"}

    video_requires_transcode = any(
        value
        for field_name, value in (
            ("videoCodec", video_codec),
            ("videoEncodePreset", encode_preset),
            ("videoEncodeLadder", encode_ladder),
        )
        if override_sourced(field_name)
    ) or (override_sourced("videoContainer") and container in {"mp4", "m4v", "mov"})

    if route_profile in {"encode", "transcode"} or video_requires_transcode or has_burn_track:
        route = "transcode"
    elif route_profile == "remux":
        route = "remux"
    else:
        route = ""

    warnings: list[str] = []
    if route == "transcode":
        warnings.append("Effective route/video override may force a full video transcode during processing.")
    if has_burn_track:
        warnings.append("Subtitle burn-in forces ENCODE, drops all selectable output subtitles, and uses the subtitle-burn encode profile.")
    if route_profile == "remux" and video_requires_transcode:
        warnings.append("routing.profile=remux is incompatible with video fields that require transcode.")
    if route_profile == "remux" and has_burn_track:
        warnings.append("routing.profile=remux is incompatible with subtitles.burnTrack.")

    return {
        "route":                  route,
        "videoCodec":             "copy" if route == "remux" else video_codec,
        "container":              container,
        "encodePreset":           encode_preset,
        "encodeLadder":           encode_ladder,
        "will_force_transcode":   route == "transcode",
        "subtitle_burn_in":       has_burn_track,
        "drops_selectable_subtitles": has_burn_track,
        "subtitle_burn_encode_profile": "current_encode_style" if has_burn_track else "",
        "source":                 "effective_route_video_fields",
        "warnings":               warnings,
        "processing_integration": "engine_active_overrides",
    }


def _file_override_effective_payload(
    *,
    manifest: dict,
    manifest_path: Any,
    source_path: str,
    config: Mapping[str, Any],
    track_payload: Mapping[str, Any] | None = None,
    state_db_root: Path | None = None,
) -> dict[str, Any]:
    match = resolve_file_override_match(manifest, source_path)
    entry = _mapping(match.get("entry"))
    has_override = bool(entry)
    scope = str(match.get("scope") or "")
    override_source = "folder_override" if scope == "folder" else "file_override"
    profile = effective_library_profile_for_source_path(config, source_path)
    library_effective_settings, inherited_source = _profile_effective_media(profile, config)
    inherited = _inherited_drawer_fields(library_effective_settings, inherited_source)
    override_fields = _override_drawer_fields(entry, override_source) if has_override else {}
    effective_fields, sources = _effective_drawer_fields(inherited, override_fields)
    expanded_fields, expanded_sources = _expanded_effective_fields(
        entry=entry,
        library_effective_settings=library_effective_settings,
        inherited_source=inherited_source,
        override_source=override_source,
        is_exact_file_override=scope == "file",
    )
    route_effective_settings, route_inherited_source = _profile_effective_route_settings(profile, config)
    route_video_fields, route_video_sources = _expanded_route_video_fields(
        entry=entry,
        library_effective_settings=route_effective_settings,
        inherited_source=route_inherited_source,
        override_source=override_source,
        is_exact_file_override=scope == "file",
    )
    route_video_processing = _route_video_processing_projection(route_video_fields, entry=entry)
    track_metadata = _effective_track_metadata(
        track_payload or _probe_tracks_for_source_path(source_path, state_db_root=state_db_root)
    )
    track_selection = _track_selection_preview(
        track_metadata=track_metadata,
        entry=entry,
        override_source=override_source,
        has_override=has_override,
    )
    resolved_track_actions = _resolved_track_actions(
        track_metadata=track_metadata,
        track_selection=track_selection,
        library_effective_settings=library_effective_settings,
        inherited_source=inherited_source,
    )
    expanded_fields.update(route_video_fields)
    sources.update(expanded_sources)
    sources.update(route_video_sources)
    return {
        "ok":                         True,
        "command":                    "queue.file_overrides.effective",
        "severity":                   "ok",
        "schema_version":             "queue_file_overrides_effective.v1",
        "message":                    f"Effective file override settings for: {source_path}",
        "manifest_path":              str(manifest_path),
        "path":                       source_path,
        "normalized_path":            normalize_file_override_path(source_path),
        "has_file_override":          has_override,
        "file_override_path":         match.get("matched_path") or "",
        "file_override_scope":        scope,
        "file_override":              entry if has_override else None,
        "library":                    _library_response(profile),
        "library_effective_settings": library_effective_settings if isinstance(profile, Mapping) else {},
        "inherited":                  inherited,
        "effective_drawer_fields":    effective_fields,
        "expanded_effective_fields":  expanded_fields,
        "route_video_effective_fields": route_video_fields,
        "route_video_processing":      route_video_processing,
        "track_metadata":              track_metadata,
        "track_selection_preview":     track_selection,
        "resolved_track_actions":      resolved_track_actions,
        "sources":                    sources,
    }
