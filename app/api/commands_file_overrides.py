from __future__ import annotations

# ==============================================================================
# app/api/commands_file_overrides.py
# ==============================================================================
# POST /api/queue/file-overrides  — set or clear per-file processing overrides.
# GET  /api/queue/file-overrides  — read current override manifest or a single entry.
#
# POST request body (set/update):
#   {
#     "path":  "<source path or folder>",   // required
#     "audio": { ... },                     // optional audio section
#     "subtitles": { ... }                  // optional subtitle section
#   }
#
# POST request body (clear one entry):
#   { "path": "<source path>", "clear": true }
#
# POST request body (clear all entries):
#   { "clear_all": true }
#
# GET query params:
#   ?path=<source path>  — return the resolved override for a single path
#   (no params)          — return the entire manifest
#
# Response:
#   {
#     "ok":          true | false,
#     "command":     "queue.file_overrides" | "queue.file_overrides.read",
#     "severity":    "ok" | "error",
#     "message":     "...",
#     "manifest_path": "...",
#     "entry_count": <int>,
#     "entries":     { ... },     // full manifest (GET without ?path)
#     "entry":       { ... }      // resolved entry for ?path  (GET with ?path)
#   }
# ==============================================================================

from collections.abc import Mapping
from fnmatch import fnmatchcase
import json
from pathlib import Path
from typing import Any

from app.config.constants import (
    ROUTE_THRESHOLD_MODE_NAMES,
    ROUTING_PROFILE_NAMES,
    SIZE_GUARD_MODE_NAMES,
)
from app.config.library_profiles import (
    default_library_settings,
    effective_library_profile_for_source_path,
    flatten_library_settings,
)
from app.config.metadata_choices import CONFIG_LIST_CHOICES
from app.contracts.config import Config
from app.contracts.source_media import SourceAudioStream, SourceSubtitleStream, source_media_from_probe_result
from app.contracts.stages import ProbeResult
from app.orchestration.runner import RunnerOptions, run_probe_stage
from app.queue.file_overrides import (
    CLEARABLE_FILE_OVERRIDE_FIELDS,
    SUPPORTED_FILE_OVERRIDE_ENCODE_LADDERS,
    SUPPORTED_FILE_OVERRIDE_ENCODE_PRESETS,
    SUPPORTED_FILE_OVERRIDE_OUTPUT_CONTAINERS,
    SUPPORTED_FILE_OVERRIDE_ROUTE_PROFILES,
    SUPPORTED_FILE_OVERRIDE_VIDEO_CODECS,
    _empty_manifest,
    _write_atomic,
    clear_file_override_entry,
    clear_file_override_fields,
    file_override_payload_warnings,
    file_overrides_to_api_payload,
    get_file_override_entry,
    normalize_file_override_path,
    read_file_overrides,
    resolve_file_override_match,
    set_file_override_entry,
    validate_file_override_payload,
)
from mediapipeline_desktop_app.config_keys import (
    KEY_AUDIO_MAX_CHANNELS,
    KEY_ENCODE_LADDER,
    KEY_ENCODE_TUNING_PRESET,
    KEY_OUTPUT_CONTAINER,
    KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES,
    KEY_REMUX_SAFE_VIDEO_CODECS,
    KEY_ROUTE_THRESHOLD_MODE,
    KEY_ROUTING_PROFILE,
    KEY_SIZE_GUARD_MODE,
    KEY_SUB_KEEP_LANGUAGES,
    KEY_VIDEO_CODEC,
)
from mediapipeline_desktop_app.api.queue_source_path_policy import queue_source_roots, validate_queue_source_path

from .command_results import resolved_paths_unavailable_payload


def _fo_command_result_payload(payload: dict) -> dict:
    result = dict(payload)
    result["schema_version"] = "desktop_command_result.v1"
    result.setdefault("refresh_hint", "queue")
    if not result.get("ok") and "errors" not in result:
        result["errors"] = [str(result.get("message") or "File override command failed.")]
    return result


def _fo_unavailable(reason: str, *, command_result: bool = False) -> dict:
    payload = {
        "ok":       False,
        "command":  "queue.file_overrides",
        "severity": "error",
        "message":  f"File overrides service unavailable: {reason}",
    }
    return _fo_command_result_payload(payload) if command_result else payload


def _fo_error(message: str) -> dict:
    return _fo_command_result_payload({
        "ok":       False,
        "command":  "queue.file_overrides",
        "severity": "error",
        "message":  message,
    })


def _fo_validation_error(errors: list[str]) -> dict:
    return _fo_command_result_payload({
        "ok":       False,
        "command":  "queue.file_overrides",
        "severity": "error",
        "message":  "Invalid file override payload.",
        "errors":   errors,
    })


def _fo_read_error(command: str, message: str) -> dict:
    return {
        "ok":       False,
        "command":  command,
        "severity": "error",
        "message":  message,
    }


FILE_OVERRIDE_POST_KEYS = frozenset(
    {"path", "audio", "subtitles", "routing", "video", "clear", "clear_all", "clear_fields"}
)
ROUTE_PREVIEW_POST_KEYS = frozenset({"path", "proposed_override"})
ROUTE_PREVIEW_SCHEMA_VERSION = "queue_file_override_route_preview.v1"
ROUTE_PREVIEW_COMMAND = "queue.file_overrides.route_preview"
FOLDER_PREVIEW_POST_KEYS = frozenset({"folder_path", "proposed_override", "options"})
FOLDER_PREVIEW_SCHEMA_VERSION = "queue_file_override_folder_preview.v1"
FOLDER_PREVIEW_COMMAND = "queue.file_overrides.folder_preview"
FOLDER_RULE_POST_KEYS = frozenset({"folder_path", "override", "confirmation", "clear"})
FOLDER_RULE_COMMAND = "queue.file_overrides.folder_rule"
FOLDER_PREVIEW_DEFAULT_SAMPLE_LIMIT = 25
FOLDER_PREVIEW_MAX_SAMPLE_LIMIT = 100
TRACKS_SCHEMA_VERSION = "queue_file_override_tracks.v1"
TRACKS_COMMAND = "queue.file_overrides.tracks"
TRACKS_PROBE_TIMEOUT_SECONDS = 55.0
ROUTE_FORCE_VALUES = {
    "auto":      "auto",
    "encode":    "transcode",
    "transcode": "transcode",
    "remux":     "remux",
}
ROUTE_PREVIEW_ROUTING_KEYS = frozenset(
    {
        "forceRoute",
        "route",
        "routingProfile",
        "routeThresholdMode",
        "sizeGuardMode",
        "maxVideoBitrateMbps",
        "maxResolutionHeight",
        "allowedVideoCodecs",
        "plexStrictMode",
        "reason",
    }
)
ROUTE_PREVIEW_VIDEO_KEYS = frozenset(
    {
        "codec",
        "videoCodec",
        "encodeTuningPreset",
        "encodePreset",
        "encodeLadder",
        "container",
        "outputContainer",
    }
)
ROUTE_PREVIEW_TOP_LEVEL_KEYS = frozenset({"routing", "video"})
FOLDER_PREVIEW_TOP_LEVEL_KEYS = frozenset({"audio", "subtitles"})
FOLDER_PREVIEW_SECTION_KEYS = {
    "audio": frozenset({"keepTracks", "dropTracks"}),
    "subtitles": frozenset({"keepTracks", "dropTracks"}),
}
FOLDER_PREVIEW_SELECTOR_KEYS = {
    "audio": frozenset({"language", "codec", "title", "channels"}),
    "subtitles": frozenset({"language", "codec", "title", "forced"}),
}
FOLDER_PREVIEW_REJECTED_SELECTOR_KEYS = frozenset(
    {"streamIndex", "stream_index", "trackIndex", "track_index", "index", "map", "ffmpegMap", "ffmpeg_map", "titleContains"}
)
FOLDER_PREVIEW_UNSAFE_TEXT_CHARS = frozenset("\r\n;&|<>`$(){}[]")
LANGUAGE_DISPLAY_NAMES: dict[str, str] = {
    "": "Undefined",
    "und": "Undefined",
    "eng": "English",
    "en": "English",
    "jpn": "Japanese",
    "ja": "Japanese",
    "spa": "Spanish",
    "es": "Spanish",
    "fre": "French",
    "fra": "French",
    "fr": "French",
    "ger": "German",
    "deu": "German",
    "de": "German",
    "ita": "Italian",
    "it": "Italian",
    "por": "Portuguese",
    "pt": "Portuguese",
    "rus": "Russian",
    "ru": "Russian",
    "chi": "Chinese",
    "zho": "Chinese",
    "zh": "Chinese",
    "kor": "Korean",
    "ko": "Korean",
}
LANGUAGE_NORMALIZATION_ALIASES: dict[str, str] = {
    "": "und",
    "und": "und",
    "unknown": "und",
    "undefined": "und",
    "eng": "eng",
    "en": "eng",
    "english": "eng",
    "jpn": "jpn",
    "ja": "jpn",
    "japanese": "jpn",
    "spa": "spa",
    "es": "spa",
    "spanish": "spa",
    "fre": "fra",
    "fra": "fra",
    "fr": "fra",
    "french": "fra",
    "ger": "deu",
    "deu": "deu",
    "de": "deu",
    "german": "deu",
    "ita": "ita",
    "it": "ita",
    "italian": "ita",
    "por": "por",
    "pt": "por",
    "portuguese": "por",
    "rus": "rus",
    "ru": "rus",
    "russian": "rus",
    "kor": "kor",
    "ko": "kor",
    "korean": "kor",
    "chi": "zho",
    "zho": "zho",
    "zh": "zho",
    "chinese": "zho",
}
CODEC_DISPLAY_NAMES: dict[str, str] = {
    "aac": "AAC",
    "ac3": "AC-3",
    "eac3": "E-AC-3",
    "truehd": "TrueHD",
    "mlp": "TrueHD",
    "dts": "DTS",
    "dca": "DTS",
    "flac": "FLAC",
    "opus": "Opus",
    "vorbis": "Vorbis",
    "mp3": "MP3",
    "pcm_s16le": "PCM",
    "pcm_s24le": "PCM",
    "subrip": "SRT",
    "srt": "SRT",
    "ass": "ASS",
    "ssa": "SSA",
    "mov_text": "TX3G",
    "webvtt": "WebVTT",
    "hdmv_pgs_subtitle": "PGS",
    "pgs": "PGS",
    "dvd_subtitle": "VobSub",
    "dvdsub": "VobSub",
    "vobsub": "VobSub",
}
IMAGE_SUBTITLE_CODEC_NAMES = frozenset({"hdmv_pgs_subtitle", "pgs", "dvd_subtitle", "dvdsub", "vobsub", "xsub"})


def _unsupported_post_key_errors(request: Mapping[str, Any]) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in FILE_OVERRIDE_POST_KEYS)
    if not unknown:
        return []
    return [
        "Unsupported file override request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(FILE_OVERRIDE_POST_KEYS))}."
    ]


def _unsupported_route_preview_key_errors(request: Mapping[str, Any]) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in ROUTE_PREVIEW_POST_KEYS)
    if not unknown:
        return []
    return [
        "Unsupported route preview request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(ROUTE_PREVIEW_POST_KEYS))}."
    ]


def _unsupported_folder_preview_key_errors(request: Mapping[str, Any]) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in FOLDER_PREVIEW_POST_KEYS)
    if not unknown:
        return []
    return [
        "Unsupported folder preview request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(FOLDER_PREVIEW_POST_KEYS))}."
    ]


def _unsupported_folder_rule_key_errors(request: Mapping[str, Any]) -> list[str]:
    unknown = sorted(str(key) for key in request.keys() if str(key) not in FOLDER_RULE_POST_KEYS)
    if not unknown:
        return []
    return [
        "Unsupported folder rule request field(s): "
        f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(FOLDER_RULE_POST_KEYS))}."
    ]


def _query_text(query: dict[str, Any] | None, key: str) -> str:
    if not query or not isinstance(query, dict):
        return ""
    value = query.get(key, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _literal_choices(field_name: str) -> tuple[str, ...]:
    from typing import get_args

    field = Config.model_fields.get(field_name)
    return tuple(str(item) for item in get_args(field.annotation)) if field is not None else ()


def _route_preview_base_payload(*, ok: bool, severity: str, message: str) -> dict[str, Any]:
    return {
        "ok":             ok,
        "command":        ROUTE_PREVIEW_COMMAND,
        "severity":       severity,
        "schema_version": ROUTE_PREVIEW_SCHEMA_VERSION,
        "message":        message,
    }


def _route_preview_error(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    payload = _route_preview_base_payload(ok=False, severity="error", message=message)
    payload["errors"] = errors or [message]
    return payload


def _route_preview_validation_error(errors: list[str]) -> dict[str, Any]:
    return _route_preview_error("Invalid route preview payload.", errors)


def _folder_preview_base_payload(*, ok: bool, severity: str, message: str) -> dict[str, Any]:
    return {
        "ok":             ok,
        "command":        FOLDER_PREVIEW_COMMAND,
        "severity":       severity,
        "schema_version": FOLDER_PREVIEW_SCHEMA_VERSION,
        "message":        message,
        "preview_only":   True,
    }


def _folder_preview_error(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    payload = _folder_preview_base_payload(ok=False, severity="error", message=message)
    payload["errors"] = errors or [message]
    return payload


def _folder_preview_validation_error(errors: list[str]) -> dict[str, Any]:
    return _folder_preview_error("Invalid folder preview payload.", errors)


def _folder_rule_error(message: str, errors: list[str] | None = None) -> dict[str, Any]:
    payload = {
        "ok":       False,
        "command":  FOLDER_RULE_COMMAND,
        "severity": "error",
        "message":  message,
    }
    if errors:
        payload["errors"] = errors
    return _fo_command_result_payload(payload)


def _folder_rule_validation_error(errors: list[str]) -> dict[str, Any]:
    return _folder_rule_error("Invalid folder rule payload.", errors)


def _normalize_route_name(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if not text:
        return "unknown"
    if "remux" in text:
        return "remux"
    if "transcode" in text or "encode" in text:
        return "transcode"
    return text


def _route_preview_source_key(value: Any) -> str:
    return normalize_file_override_path(value)


def _load_route_preview_snapshot_row(resolved: Any, source_path: str) -> tuple[dict[str, Any] | None, str]:
    snapshot_path = getattr(resolved, "queue_snapshot_path", None)
    if snapshot_path is None:
        return None, "Queue snapshot path is not configured; route preview is unavailable."
    path = Path(snapshot_path)
    if not path.exists():
        return None, f"Queue snapshot was not found: {path}"
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"Queue snapshot could not be read: {exc}"
    rows = snapshot.get("rows") if isinstance(snapshot, Mapping) else None
    if not isinstance(rows, list):
        return None, "Queue snapshot does not contain route preview rows."
    source_key = _route_preview_source_key(source_path)
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _route_preview_source_key(row.get("source_path")) == source_key:
            return dict(row), ""
    return None, "Source path is not present in the latest queue snapshot; refresh Queue before route preview."


def _choice_error(field_path: str, value: Any, choices: tuple[str, ...]) -> str | None:
    text = str(value or "").strip().casefold()
    if not text or text not in choices:
        return f"'{field_path}' must be one of: {', '.join(choices)}."
    return None


def _positive_int_value(errors: list[str], field_path: str, value: Any, *, minimum: int, maximum: int) -> int | None:
    if type(value) is not int:
        errors.append(f"'{field_path}' must be an integer.")
        return None
    if value < minimum or value > maximum:
        errors.append(f"'{field_path}' must be between {minimum} and {maximum}.")
        return None
    return int(value)


def _route_video_requires_transcode(video: Mapping[str, Any]) -> bool:
    if any(key in video and video.get(key) not in (None, "") for key in ("codec", "encodeTuningPreset", "encodePreset", "encodeLadder")):
        return True
    container = str(video.get("container") or video.get("outputContainer") or "").strip().casefold()
    return container in {"mp4", "m4v", "mov"}


def _validate_route_preview_proposal(value: Any) -> tuple[dict[str, Any], list[str], list[dict[str, str]]]:
    if value in (None, ""):
        return {}, [], []
    if not isinstance(value, Mapping):
        return {}, ["'proposed_override' must be an object when provided."], []

    proposed = _mapping(value)
    errors: list[str] = []
    warnings: list[dict[str, str]] = []
    unknown_sections = sorted(str(key) for key in proposed.keys() if str(key) not in ROUTE_PREVIEW_TOP_LEVEL_KEYS)
    if unknown_sections:
        errors.append(
            "Unsupported proposed_override section(s): "
            f"{', '.join(unknown_sections)}. Allowed sections: {', '.join(sorted(ROUTE_PREVIEW_TOP_LEVEL_KEYS))}."
        )

    normalized: dict[str, Any] = {}
    routing = proposed.get("routing")
    if routing is not None:
        if not isinstance(routing, Mapping):
            errors.append("'proposed_override.routing' must be an object.")
        else:
            routing_map = _mapping(routing)
            unknown = sorted(str(key) for key in routing_map.keys() if str(key) not in ROUTE_PREVIEW_ROUTING_KEYS)
            if unknown:
                errors.append(
                    "Unsupported proposed_override.routing field(s): "
                    f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(ROUTE_PREVIEW_ROUTING_KEYS))}."
                )
            normalized_routing: dict[str, Any] = {}
            force_value = routing_map.get("forceRoute", routing_map.get("route"))
            if force_value not in (None, ""):
                force_text = str(force_value or "").strip().casefold()
                if force_text not in ROUTE_FORCE_VALUES:
                    errors.append("'routing.forceRoute' must be one of: auto, encode, remux, transcode.")
                else:
                    normalized_routing["forceRoute"] = ROUTE_FORCE_VALUES[force_text]
                    normalized_routing["forceRouteInput"] = force_text
            if "routingProfile" in routing_map:
                error = _choice_error("routing.routingProfile", routing_map.get("routingProfile"), ROUTING_PROFILE_NAMES)
                if error:
                    errors.append(error)
                else:
                    normalized_routing["routingProfile"] = str(routing_map.get("routingProfile")).strip().casefold()
            if "routeThresholdMode" in routing_map:
                error = _choice_error(
                    "routing.routeThresholdMode",
                    routing_map.get("routeThresholdMode"),
                    ROUTE_THRESHOLD_MODE_NAMES,
                )
                if error:
                    errors.append(error)
                else:
                    normalized_routing["routeThresholdMode"] = str(routing_map.get("routeThresholdMode")).strip().casefold()
            if "sizeGuardMode" in routing_map:
                error = _choice_error("routing.sizeGuardMode", routing_map.get("sizeGuardMode"), SIZE_GUARD_MODE_NAMES)
                if error:
                    errors.append(error)
                else:
                    normalized_routing["sizeGuardMode"] = str(routing_map.get("sizeGuardMode")).strip().casefold()
            if "maxVideoBitrateMbps" in routing_map:
                bitrate = _positive_int_value(
                    errors,
                    "routing.maxVideoBitrateMbps",
                    routing_map.get("maxVideoBitrateMbps"),
                    minimum=1,
                    maximum=500,
                )
                if bitrate is not None:
                    normalized_routing["maxVideoBitrateMbps"] = bitrate
            if "maxResolutionHeight" in routing_map:
                height = _positive_int_value(
                    errors,
                    "routing.maxResolutionHeight",
                    routing_map.get("maxResolutionHeight"),
                    minimum=1,
                    maximum=4320,
                )
                if height is not None:
                    normalized_routing["maxResolutionHeight"] = height
            if "allowedVideoCodecs" in routing_map:
                raw_codecs = routing_map.get("allowedVideoCodecs")
                allowed = {str(choice[0]).casefold() for choice in CONFIG_LIST_CHOICES.get(KEY_REMUX_SAFE_VIDEO_CODECS, ())}
                if not isinstance(raw_codecs, list) or not raw_codecs:
                    errors.append("'routing.allowedVideoCodecs' must be a non-empty list of codec strings.")
                else:
                    values: list[str] = []
                    for item in raw_codecs:
                        codec = str(item or "").strip().casefold()
                        if not codec or codec not in allowed:
                            errors.append(
                                "'routing.allowedVideoCodecs' entries must be one of: "
                                f"{', '.join(sorted(allowed))}."
                            )
                            break
                        values.append(codec)
                    if values:
                        normalized_routing["allowedVideoCodecs"] = values
            if "plexStrictMode" in routing_map:
                if not isinstance(routing_map.get("plexStrictMode"), bool):
                    errors.append("'routing.plexStrictMode' must be a boolean.")
                else:
                    normalized_routing["plexStrictMode"] = bool(routing_map.get("plexStrictMode"))
            if "reason" in routing_map:
                reason = str(routing_map.get("reason") or "").strip()
                if len(reason) > 240:
                    errors.append("'routing.reason' must be 240 characters or fewer.")
                elif reason:
                    normalized_routing["reason"] = reason
            if normalized_routing:
                normalized["routing"] = normalized_routing

    video = proposed.get("video")
    if video is not None:
        if not isinstance(video, Mapping):
            errors.append("'proposed_override.video' must be an object.")
        else:
            video_map = _mapping(video)
            unknown = sorted(str(key) for key in video_map.keys() if str(key) not in ROUTE_PREVIEW_VIDEO_KEYS)
            if unknown:
                errors.append(
                    "Unsupported proposed_override.video field(s): "
                    f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(ROUTE_PREVIEW_VIDEO_KEYS))}."
                )
            normalized_video: dict[str, Any] = {}
            codec_value = video_map.get("codec", video_map.get("videoCodec"))
            if codec_value not in (None, ""):
                error = _choice_error("video.codec", codec_value, _literal_choices(KEY_VIDEO_CODEC))
                if error:
                    errors.append(error)
                else:
                    normalized_video["codec"] = str(codec_value).strip().casefold()
            preset_value = video_map.get("encodeTuningPreset", video_map.get("encodePreset"))
            if preset_value not in (None, ""):
                error = _choice_error("video.encodeTuningPreset", preset_value, _literal_choices(KEY_ENCODE_TUNING_PRESET))
                if error:
                    errors.append(error)
                else:
                    normalized_video["encodeTuningPreset"] = str(preset_value).strip().casefold()
            if "encodeLadder" in video_map:
                error = _choice_error("video.encodeLadder", video_map.get("encodeLadder"), _literal_choices(KEY_ENCODE_LADDER))
                if error:
                    errors.append(error)
                else:
                    normalized_video["encodeLadder"] = str(video_map.get("encodeLadder")).strip().casefold()
            container_value = video_map.get("container", video_map.get("outputContainer"))
            if container_value not in (None, ""):
                error = _choice_error("video.container", container_value, _literal_choices(KEY_OUTPUT_CONTAINER))
                if error:
                    errors.append(error)
                else:
                    normalized_video["container"] = str(container_value).strip().casefold()
            if normalized_video:
                normalized["video"] = normalized_video

    normalized_routing = _mapping(normalized.get("routing"))
    normalized_video = _mapping(normalized.get("video"))
    if normalized_routing.get("forceRoute") == "remux" and _route_video_requires_transcode(normalized_video):
        errors.append(
            "'routing.forceRoute' remux cannot be combined with video encode/container fields "
            "that require transcode."
        )
    if normalized.get("video") and not _mapping(normalized.get("routing")).get("forceRoute"):
        warnings.append({
            "field":   "video",
            "message": "Video encode/container settings may force transcode during processing.",
        })
    return normalized, errors, warnings


def _route_preview_settings_value(settings: Mapping[str, Any], key: str, default: str = "") -> str:
    return str(settings.get(key) or default).strip()


def _route_preview_current_payload(
    row: Mapping[str, Any],
    settings: Mapping[str, Any],
    settings_source: str,
) -> dict[str, Any]:
    route = _normalize_route_name(row.get("route") or row.get("route_name"))
    configured_video_codec = _route_preview_settings_value(settings, KEY_VIDEO_CODEC)
    return {
        "route":             route,
        "routeRaw":          str(row.get("route") or row.get("route_name") or "").strip(),
        "routeReason":       str(row.get("route_reason") or "").strip(),
        "routeReasonCode":   str(row.get("route_reason_code") or "").strip(),
        "videoCodec":        "copy" if route == "remux" else configured_video_codec,
        "configuredVideoCodec": configured_video_codec,
        "container":         _route_preview_settings_value(settings, KEY_OUTPUT_CONTAINER),
        "routingProfile":    _route_preview_settings_value(settings, KEY_ROUTING_PROFILE),
        "routeThresholdMode": _route_preview_settings_value(settings, KEY_ROUTE_THRESHOLD_MODE),
        "sizeGuardMode":     _route_preview_settings_value(settings, KEY_SIZE_GUARD_MODE),
        "source":            "queue_snapshot",
        "settingsSource":    settings_source,
    }


def _route_preview_proposed_payload(
    current: Mapping[str, Any],
    proposed_override: Mapping[str, Any],
) -> dict[str, Any]:
    routing = _mapping(proposed_override.get("routing"))
    video = _mapping(proposed_override.get("video"))
    force_route = str(routing.get("forceRoute") or "").strip()
    video_requires_transcode = _route_video_requires_transcode(video)
    if force_route and force_route != "auto":
        route = force_route
    elif video_requires_transcode:
        route = "transcode"
    else:
        route = str(current.get("route") or "unknown")
    source = "proposed_file_override" if (force_route and force_route != "auto") or video_requires_transcode else str(current.get("source") or "queue_snapshot")
    if force_route and force_route != "auto":
        decision_source = "forced_route_preview"
    elif video_requires_transcode:
        decision_source = "proposed_file_override"
    else:
        decision_source = "current_queue_snapshot"
    codec = "copy" if route == "remux" else str(video.get("codec") or current.get("configuredVideoCodec") or current.get("videoCodec") or "")
    return {
        "route":             route,
        "videoCodec":        codec,
        "container":         str(video.get("container") or current.get("container") or ""),
        "routingProfile":    str(routing.get("routingProfile") or current.get("routingProfile") or ""),
        "routeThresholdMode": str(routing.get("routeThresholdMode") or current.get("routeThresholdMode") or ""),
        "sizeGuardMode":     str(routing.get("sizeGuardMode") or current.get("sizeGuardMode") or ""),
        "source":            source,
        "decisionSource":    decision_source,
    }


def _route_preview_impact(
    current: Mapping[str, Any],
    proposed: Mapping[str, Any],
    proposed_override: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    current_route = str(current.get("route") or "unknown")
    proposed_route = str(proposed.get("route") or "unknown")
    routing = _mapping(proposed_override.get("routing"))
    video = _mapping(proposed_override.get("video"))
    force_route = str(routing.get("forceRoute") or "").strip()
    video_requires_transcode = _route_video_requires_transcode(video)

    will_force_transcode = force_route == "transcode" or video_requires_transcode or (current_route != "transcode" and proposed_route == "transcode")
    will_prevent_remux = current_route == "remux" and proposed_route == "transcode"
    forced_remux_change = force_route == "remux" and current_route != "remux"

    if will_force_transcode:
        warnings.append({
            "field":   "video" if video_requires_transcode and force_route != "transcode" else "routing.forceRoute",
            "message": "This route preview would force a full video transcode for this file.",
        })
    if forced_remux_change:
        warnings.append({
            "field":   "routing.forceRoute",
            "message": "Forced remux cannot be proven safe by this advisory endpoint without the processing route helper accepting proposed file overrides.",
        })
    if video and proposed_route == "remux":
        warnings.append({
            "field":   "video",
            "message": "Video encode settings do not apply while the proposed route is remux.",
        })
    non_force_routing = any(key != "forceRoute" and key != "forceRouteInput" for key in routing)
    if non_force_routing:
        warnings.append({
            "field":   "routing",
            "message": "Non-forcing routing fields are validated, but full route recomputation for proposed per-file overrides is not available yet.",
        })

    if will_force_transcode:
        risk = "high"
    elif forced_remux_change:
        risk = "high"
    elif force_route == "remux" and current_route == "remux" and not video:
        risk = "low"
    elif force_route or video or non_force_routing:
        risk = "medium"
    else:
        risk = "low"

    return {
        "will_force_transcode":   will_force_transcode,
        "will_prevent_remux":     will_prevent_remux,
        "estimated_risk":         risk,
        "requires_confirmation":  risk in {"medium", "high"},
        "route_decision_helper":  "queue_snapshot_current_route",
        "full_recompute":         False,
        "advisory_only":          True,
    }, warnings


def _file_override_route_preview_payload(
    *,
    resolved: Any,
    source_path: str,
    proposed_override: Mapping[str, Any],
) -> dict[str, Any]:
    row, route_error = _load_route_preview_snapshot_row(resolved, source_path)
    if row is None:
        return _route_preview_error(
            "Route preview unavailable.",
            [
                route_error,
                "Stage 5 route override UI cannot proceed safely until a queue snapshot row provides backend route evidence for this path.",
            ],
        )

    config = getattr(resolved, "config_data", {}) or {}
    config_map = config if isinstance(config, Mapping) else {}
    profile = effective_library_profile_for_source_path(config_map, source_path)
    library_effective_settings, settings_source = _profile_effective_route_settings(profile, config_map)
    current = _route_preview_current_payload(row, library_effective_settings, settings_source)
    proposed = _route_preview_proposed_payload(current, proposed_override)
    impact, impact_warnings = _route_preview_impact(current, proposed, proposed_override)
    warnings = list(impact_warnings)
    if impact.get("advisory_only"):
        warnings.append({
            "field":   "route_preview",
            "message": "Preview uses current queue snapshot route evidence and does not write or process media.",
        })
    payload = _route_preview_base_payload(
        ok=True,
        severity="ok",
        message=f"Route impact preview for: {source_path}",
    )
    payload.update({
        "path":                       source_path,
        "normalized_path":            normalize_file_override_path(source_path),
        "current":                    current,
        "proposed":                   proposed,
        "impact":                     impact,
        "warnings":                   warnings,
        "errors":                     [],
        "accepted_fields": {
            "routing": sorted(ROUTE_PREVIEW_ROUTING_KEYS),
            "video":   sorted(ROUTE_PREVIEW_VIDEO_KEYS),
        },
    })
    return payload


def _folder_preview_safe_scalar(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and all(char.isalnum() or char in "_.-" for char in text)


def _folder_preview_safe_title(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and len(text) <= 160 and not any(char in FOLDER_PREVIEW_UNSAFE_TEXT_CHARS for char in text)


def _validate_folder_preview_options(value: Any) -> tuple[dict[str, Any], list[str]]:
    if value in (None, ""):
        return {"sample_limit": FOLDER_PREVIEW_DEFAULT_SAMPLE_LIMIT, "use_cached_track_metadata_only": True}, []
    if not isinstance(value, Mapping):
        return {}, ["'options' must be an object when provided."]
    options = _mapping(value)
    unknown = sorted(str(key) for key in options.keys() if str(key) not in {"sample_limit", "use_cached_track_metadata_only"})
    errors: list[str] = []
    if unknown:
        errors.append(
            "Unsupported folder preview option(s): "
            f"{', '.join(unknown)}. Allowed options: sample_limit, use_cached_track_metadata_only."
        )
    sample_limit = options.get("sample_limit", FOLDER_PREVIEW_DEFAULT_SAMPLE_LIMIT)
    if type(sample_limit) is not int:
        errors.append("'options.sample_limit' must be an integer.")
        sample_limit = FOLDER_PREVIEW_DEFAULT_SAMPLE_LIMIT
    elif sample_limit < 1 or sample_limit > FOLDER_PREVIEW_MAX_SAMPLE_LIMIT:
        errors.append(f"'options.sample_limit' must be between 1 and {FOLDER_PREVIEW_MAX_SAMPLE_LIMIT}.")
    cached_only = options.get("use_cached_track_metadata_only", True)
    if not isinstance(cached_only, bool):
        errors.append("'options.use_cached_track_metadata_only' must be a boolean.")
        cached_only = True
    return {"sample_limit": int(sample_limit), "use_cached_track_metadata_only": bool(cached_only)}, errors


def _validate_folder_preview_proposal(value: Any) -> tuple[dict[str, Any], list[str]]:
    if value in (None, ""):
        return {}, []
    if not isinstance(value, Mapping):
        return {}, ["'proposed_override' must be an object when provided."]
    proposed = _mapping(value)
    errors: list[str] = []
    unknown_sections = sorted(str(key) for key in proposed.keys() if str(key) not in FOLDER_PREVIEW_TOP_LEVEL_KEYS)
    if unknown_sections:
        errors.append(
            "Unsupported proposed_override section(s): "
            f"{', '.join(unknown_sections)}. Allowed sections: {', '.join(sorted(FOLDER_PREVIEW_TOP_LEVEL_KEYS))}."
        )

    normalized: dict[str, Any] = {}
    for section_name in ("audio", "subtitles"):
        if section_name not in proposed:
            continue
        section = proposed.get(section_name)
        if not isinstance(section, Mapping):
            errors.append(f"'proposed_override.{section_name}' must be an object.")
            continue
        section_map = _mapping(section)
        allowed_section_keys = FOLDER_PREVIEW_SECTION_KEYS[section_name]
        unknown_fields = sorted(str(key) for key in section_map.keys() if str(key) not in allowed_section_keys)
        if unknown_fields:
            errors.append(
                f"Unsupported proposed_override.{section_name} field(s): {', '.join(unknown_fields)}. "
                f"Allowed fields: {', '.join(sorted(allowed_section_keys))}."
            )
        normalized_section: dict[str, Any] = {}
        kind = "audio" if section_name == "audio" else "subtitle"
        allowed_selector_keys = FOLDER_PREVIEW_SELECTOR_KEYS[section_name]
        for field_name in ("keepTracks", "dropTracks"):
            if field_name not in section_map:
                continue
            selectors = section_map.get(field_name)
            field_path = f"{section_name}.{field_name}"
            if not isinstance(selectors, list):
                errors.append(f"'{field_path}' must be a list of folder-safe track selector objects.")
                continue
            if not selectors:
                errors.append(f"'{field_path}' must contain at least one selector; omit the field to inherit.")
                continue
            normalized_selectors: list[dict[str, Any]] = []
            for index, selector in enumerate(selectors):
                selector_path = f"{field_path}[{index}]"
                if not isinstance(selector, Mapping):
                    errors.append(f"'{selector_path}' must be an object with folder-safe selector fields.")
                    continue
                selector_map = _mapping(selector)
                rejected = sorted(str(key) for key in selector_map.keys() if str(key) in FOLDER_PREVIEW_REJECTED_SELECTOR_KEYS)
                if rejected:
                    errors.append(
                        f"Unsupported folder-rule selector field(s) at '{selector_path}': {', '.join(rejected)}. "
                        "Exact stream selectors and raw ffmpeg map fields are file-only."
                    )
                unknown_selector_fields = sorted(
                    str(key)
                    for key in selector_map.keys()
                    if str(key) not in allowed_selector_keys and str(key) not in FOLDER_PREVIEW_REJECTED_SELECTOR_KEYS
                )
                if unknown_selector_fields:
                    errors.append(
                        f"Unsupported {selector_path} field(s): {', '.join(unknown_selector_fields)}. "
                        f"Allowed fields: {', '.join(sorted(allowed_selector_keys))}."
                    )
                if not any(str(key) in allowed_selector_keys for key in selector_map.keys()):
                    errors.append(f"'{selector_path}' must contain at least one folder-safe selector field.")
                    continue
                clean_selector: dict[str, Any] = {}
                for key in ("language", "codec"):
                    if key not in selector_map:
                        continue
                    value = selector_map.get(key)
                    if not isinstance(value, str):
                        errors.append(f"'{selector_path}.{key}' must be a string.")
                        continue
                    text = value.strip().casefold()
                    if not _folder_preview_safe_scalar(text):
                        errors.append(f"'{selector_path}.{key}' contains unsupported characters.")
                        continue
                    clean_selector[key] = text
                if "title" in selector_map:
                    value = selector_map.get("title")
                    if not isinstance(value, str):
                        errors.append(f"'{selector_path}.title' must be a string.")
                    elif not _folder_preview_safe_title(value):
                        errors.append(f"'{selector_path}.title' is empty, too long, or contains unsupported characters.")
                    else:
                        clean_selector["title"] = value.strip()
                if kind == "audio" and "channels" in selector_map:
                    try:
                        channels = int(selector_map.get("channels"))
                    except (TypeError, ValueError):
                        errors.append(f"'{selector_path}.channels' must be an integer.")
                    else:
                        if channels <= 0:
                            errors.append(f"'{selector_path}.channels' must be greater than zero.")
                        else:
                            clean_selector["channels"] = channels
                if kind == "subtitle" and "forced" in selector_map:
                    if not isinstance(selector_map.get("forced"), bool):
                        errors.append(f"'{selector_path}.forced' must be a boolean.")
                    else:
                        clean_selector["forced"] = bool(selector_map.get("forced"))
                if clean_selector:
                    normalized_selectors.append(clean_selector)
            if normalized_selectors:
                normalized_section[field_name] = normalized_selectors
        if normalized_section:
            normalized[section_name] = normalized_section

    if normalized:
        file_override_validation = validate_file_override_payload(normalized)
        if file_override_validation:
            errors.extend(file_override_validation)
    return normalized, errors


def _validate_folder_rule_override(value: Any) -> tuple[dict[str, Any], list[str]]:
    if value in (None, ""):
        return {}, ["'override' is required unless 'clear': true is provided."]
    normalized, errors = _validate_folder_preview_proposal(value)
    errors = [error.replace("proposed_override", "override") for error in errors]
    if not normalized and not errors:
        errors.append("'override' must contain at least one folder-safe audio/subtitle keep/drop rule.")
    return normalized, errors


def _validate_folder_rule_confirmation(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["'confirmation' is required when saving a folder rule."]
    confirmation = _mapping(value)
    errors: list[str] = []
    if confirmation.get("acknowledged_future_files") is not True:
        errors.append("'confirmation.acknowledged_future_files' must be true before saving a folder rule.")
    if confirmation.get("acknowledged_file_overrides_win") is not True:
        errors.append("'confirmation.acknowledged_file_overrides_win' must be true before saving a folder rule.")
    unknown = sorted(
        str(key)
        for key in confirmation.keys()
        if str(key) not in {"acknowledged_future_files", "acknowledged_file_overrides_win"}
    )
    if unknown:
        errors.append(
            "Unsupported confirmation field(s): "
            f"{', '.join(unknown)}. Allowed fields: acknowledged_future_files, acknowledged_file_overrides_win."
        )
    return errors


def _validate_folder_source_path(resolved: Any, raw_path: Any) -> tuple[str | None, str | None]:
    folder_path, error = validate_queue_source_path(resolved, raw_path, field_name="folder_path")
    if error:
        return None, error if str(raw_path or "").strip() else "'folder_path' is required."
    path = Path(str(folder_path or ""))
    try:
        if path.exists() and not path.is_dir():
            return None, "'folder_path' must point to a source folder, not a media file."
    except OSError as exc:
        return None, f"Folder path could not be inspected: {exc}"
    if not path.exists() and path.suffix:
        return None, "'folder_path' must be a folder path selected under a configured source root."
    return str(path), None


def _folder_rule_library_root_error(resolved: Any, folder_path: str) -> str | None:
    folder_key = normalize_file_override_path(folder_path)
    if not folder_key:
        return "'folder_path' is required."
    for root in queue_source_roots(resolved):
        root_key = normalize_file_override_path(root)
        if root_key and root_key == folder_key:
            return (
                "Folder rules cannot be saved at a library/source root. "
                "Change library-wide defaults in Library settings instead."
            )
    return None


def _folder_preview_load_snapshot_rows(resolved: Any) -> tuple[list[dict[str, Any]], list[dict[str, str]], bool]:
    snapshot_path = getattr(resolved, "queue_snapshot_path", None)
    if snapshot_path is None:
        return [], [_track_warning("Queue snapshot path is not configured; known-file preview is partial.", field="queue_snapshot")], True
    path = Path(snapshot_path)
    if not path.exists():
        return [], [_track_warning(f"Queue snapshot was not found: {path}", field="queue_snapshot")], True
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [], [_track_warning(f"Queue snapshot could not be read: {exc}", field="queue_snapshot")], True
    rows = data.get("rows") if isinstance(data, Mapping) else None
    if not isinstance(rows, list):
        return [], [_track_warning("Queue snapshot does not contain rows; known-file preview is partial.", field="queue_snapshot")], True
    return [dict(row) for row in rows if isinstance(row, Mapping)], [], False


def _folder_preview_path_under(folder_key: str, value: Any) -> bool:
    path_key = normalize_file_override_path(value)
    return bool(path_key) and path_key.startswith(folder_key + "/")


def _folder_preview_is_override_artifact_row(row: Mapping[str, Any]) -> bool:
    for key in ("source_path", "relative_path", "display_name", "name"):
        value = normalize_file_override_path(row.get(key) or "")
        if value.endswith(".override.json") or value.endswith("/override.json") or value == "override.json":
            return True
    return False


def _folder_preview_source_rows(rows: list[dict[str, Any]], folder_path: str) -> list[dict[str, Any]]:
    folder_key = normalize_file_override_path(folder_path)
    result: list[dict[str, Any]] = []
    for row in rows:
        if _folder_preview_is_override_artifact_row(row):
            continue
        source_path = str(row.get("source_path") or "").strip()
        if not source_path or not _folder_preview_path_under(folder_key, source_path):
            continue
        result.append(row)
    return result


def _bool_track_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _folder_preview_nested_mapping(row: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _folder_preview_track_language(row: Mapping[str, Any]) -> str:
    tags = _folder_preview_nested_mapping(row, "tags")
    return _track_language(row.get("language") or row.get("lang") or tags.get("language"))


def _folder_preview_track_title(row: Mapping[str, Any]) -> str:
    tags = _folder_preview_nested_mapping(row, "tags")
    return str(row.get("title") or tags.get("title") or "").strip()


def _folder_preview_track_kind(row: Mapping[str, Any], fallback: str = "") -> str:
    value = str(row.get("kind") or row.get("codec_type") or row.get("stream_type") or row.get("type") or fallback)
    kind = value.strip().casefold()
    if kind in {"subtitles", "subtitle_stream", "s"}:
        return "subtitle"
    if kind in {"audio_stream", "a"}:
        return "audio"
    return kind


def _folder_preview_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _folder_preview_append_track_rows(
    target: list[tuple[str, Mapping[str, Any]]],
    value: Any,
    *,
    fallback_kind: str = "",
) -> bool:
    rows = _folder_preview_list(value)
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        kind = _folder_preview_track_kind(item, fallback_kind)
        if kind in {"audio", "subtitle"}:
            target.append((kind, dict(item)))
    return isinstance(value, (list, tuple))


def _folder_preview_normalize_audio_track(row: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    title = _folder_preview_track_title(row)
    codec = str(row.get("codec") or row.get("codec_name") or "").strip().casefold()
    disposition = _folder_preview_nested_mapping(row, "disposition")
    track = {
        "stream_index":     _track_stream_index(row),
        "language":         _folder_preview_track_language(row),
        "title":            title,
        "codec":            codec,
        "channels":         int(row.get("channels") or 0),
        "channel_layout":   str(row.get("channel_layout") or "").strip(),
        "default":          _bool_track_value(row.get("default", disposition.get("default"))),
        "forced":           _bool_track_value(row.get("forced", disposition.get("forced"))),
        "commentary":       bool(row.get("commentary")) or _track_title_contains(title, ("commentary", "director", "cast")),
        "hearing_impaired": bool(row.get("hearing_impaired")) or _is_hearing_impaired_track(title),
    }
    track["display"] = str(row.get("display") or _audio_track_display(ordinal, track))
    return track


def _folder_preview_normalize_subtitle_track(row: Mapping[str, Any]) -> dict[str, Any]:
    title = _folder_preview_track_title(row)
    codec = str(row.get("codec") or row.get("codec_name") or "").strip().casefold()
    disposition = _folder_preview_nested_mapping(row, "disposition")
    track = {
        "stream_index":     _track_stream_index(row),
        "language":         _folder_preview_track_language(row),
        "title":            title,
        "codec":            codec,
        "default":          _bool_track_value(row.get("default", disposition.get("default"))),
        "forced":           _bool_track_value(row.get("forced", disposition.get("forced"))),
        "hearing_impaired": bool(row.get("hearing_impaired")) or _is_hearing_impaired_track(title),
        "image_based":      bool(row.get("image_based")) or codec in IMAGE_SUBTITLE_CODEC_NAMES,
    }
    track["display"] = str(row.get("display") or _subtitle_track_display(track))
    return track


def _folder_preview_cached_tracks_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    collected: list[tuple[str, Mapping[str, Any]]] = []
    metadata_present = False

    for key in ("streams", "probe_streams"):
        metadata_present = _folder_preview_append_track_rows(collected, row.get(key)) or metadata_present
    for key in ("probe", "probe_result", "source_media", "source_media_info", "source_media_profile", "ffprobe", "track_metadata"):
        nested = row.get(key)
        if not isinstance(nested, Mapping):
            continue
        metadata_present = _folder_preview_append_track_rows(collected, nested.get("streams")) or metadata_present
        metadata_present = _folder_preview_append_track_rows(collected, nested.get("audio_streams"), fallback_kind="audio") or metadata_present
        metadata_present = _folder_preview_append_track_rows(collected, nested.get("subtitle_streams"), fallback_kind="subtitle") or metadata_present
        metadata_present = _folder_preview_append_track_rows(collected, nested.get("audio_tracks"), fallback_kind="audio") or metadata_present
        metadata_present = _folder_preview_append_track_rows(collected, nested.get("subtitle_tracks"), fallback_kind="subtitle") or metadata_present
    metadata_present = _folder_preview_append_track_rows(collected, row.get("audio_streams"), fallback_kind="audio") or metadata_present
    metadata_present = _folder_preview_append_track_rows(collected, row.get("subtitle_streams"), fallback_kind="subtitle") or metadata_present
    metadata_present = _folder_preview_append_track_rows(collected, row.get("audio_tracks"), fallback_kind="audio") or metadata_present
    metadata_present = _folder_preview_append_track_rows(collected, row.get("subtitle_tracks"), fallback_kind="subtitle") or metadata_present

    audio_raw = [track for kind, track in collected if kind == "audio"]
    subtitle_raw = [track for kind, track in collected if kind == "subtitle"]
    audio_tracks = [_folder_preview_normalize_audio_track(track, ordinal) for ordinal, track in enumerate(audio_raw, start=1)]
    subtitle_tracks = [_folder_preview_normalize_subtitle_track(track) for track in subtitle_raw]
    available = bool(metadata_present and (audio_tracks or subtitle_tracks))
    return {
        "available":       available,
        "probe_available": available,
        "probe_source":    "queue_snapshot_cache" if available else "unavailable",
        "audio_tracks":    audio_tracks if available else [],
        "subtitle_tracks": subtitle_tracks if available else [],
        "warnings":        [] if available else [_track_warning("Cached track metadata is unavailable for this queue row.")],
    }


def _folder_preview_track_matches(selection: Mapping[str, Any], tracks: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for action, indexes_key, sources_key in (
        ("keep", "kept_stream_indexes", "kept_stream_sources"),
        ("drop", "dropped_stream_indexes", "dropped_stream_sources"),
    ):
        sources = _mapping(selection.get(sources_key))
        for stream_index in selection.get(indexes_key) or []:
            source = _mapping(sources.get(str(stream_index)))
            field = str(source.get("field") or "")
            if not field:
                continue
            track = next((item for item in tracks if _track_stream_index(item) == stream_index), {})
            matched.append({
                "stream_index": stream_index,
                "action":       action,
                "field":        field,
                "source":       str(source.get("source") or ""),
                "display":      str(_mapping(track).get("display") or ""),
            })
    return matched


def _folder_preview_track_characteristic_warnings(
    *,
    audio_tracks: list[Mapping[str, Any]],
    subtitle_tracks: list[Mapping[str, Any]],
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if any(bool(track.get("commentary")) for track in audio_tracks):
        warnings.append(_track_warning("Commentary audio tracks are present in cached metadata.", field="audio"))
    if any(bool(track.get("hearing_impaired")) for track in subtitle_tracks):
        warnings.append(_track_warning("SDH/hearing-impaired subtitle tracks are present in cached metadata.", field="subtitles"))
    if any(bool(track.get("forced")) for track in subtitle_tracks):
        warnings.append(_track_warning("Forced subtitle tracks are present in cached metadata.", field="subtitles"))
    if any(bool(track.get("image_based")) for track in subtitle_tracks):
        warnings.append(_track_warning("Image-based subtitle tracks are present and may require special handling.", field="subtitles"))
    return warnings


def _folder_preview_sample_row(row: Mapping[str, Any], proposed_override: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    source_path = str(row.get("source_path") or "").strip()
    track_metadata = _folder_preview_cached_tracks_from_row(row)
    if not track_metadata.get("available"):
        return {
            "path":                   source_path,
            "track_metadata_available": False,
            "audio_track_count":      0,
            "subtitle_track_count":   0,
            "matched_audio_tracks":   [],
            "matched_subtitle_tracks": [],
            "warnings":               list(track_metadata.get("warnings") or []),
        }, True

    audio_tracks = [_mapping(track) for track in track_metadata.get("audio_tracks") or []]
    subtitle_tracks = [_mapping(track) for track in track_metadata.get("subtitle_tracks") or []]
    audio_selection = _track_selection_section(
        kind="audio",
        tracks=audio_tracks,
        section=_mapping(proposed_override.get("audio")),
        source="proposed_folder_rule",
    )
    subtitle_selection = _track_selection_section(
        kind="subtitle",
        tracks=subtitle_tracks,
        section=_mapping(proposed_override.get("subtitles")),
        source="proposed_folder_rule",
    )
    warnings = (
        list(audio_selection.get("warnings") or [])
        + list(subtitle_selection.get("warnings") or [])
        + _folder_preview_track_characteristic_warnings(audio_tracks=audio_tracks, subtitle_tracks=subtitle_tracks)
    )
    return {
        "path":                     source_path,
        "track_metadata_available": True,
        "audio_track_count":        len(audio_tracks),
        "subtitle_track_count":     len(subtitle_tracks),
        "matched_audio_tracks":     _folder_preview_track_matches(audio_selection, audio_tracks),
        "matched_subtitle_tracks":  _folder_preview_track_matches(subtitle_selection, subtitle_tracks),
        "warnings":                 warnings,
    }, False


def _folder_preview_aggregate_warnings(sample_rows: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    counts: dict[tuple[str, str], int] = {}
    for row in sample_rows:
        for warning in row.get("warnings") or []:
            if not isinstance(warning, Mapping):
                continue
            field = str(warning.get("field") or "folder_preview")
            message = str(warning.get("message") or "").strip()
            if not message:
                continue
            counts[(field, message)] = counts.get((field, message), 0) + 1
    aggregated: list[dict[str, str]] = []
    for (field, message), count in sorted(counts.items()):
        suffix = f" in {count} sampled file{'s' if count != 1 else ''}."
        if message.endswith("."):
            message = message[:-1]
        aggregated.append({"field": field, "message": message + suffix})
    return aggregated


def _folder_preview_conflicts(
    *,
    manifest: Mapping[str, Any],
    source_rows: list[Mapping[str, Any]],
    folder_path: str,
) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    folder_key = normalize_file_override_path(folder_path)
    for row in source_rows:
        source_path = str(row.get("source_path") or "").strip()
        if not source_path:
            continue
        match = resolve_file_override_match(dict(manifest), source_path)
        entry = match.get("entry")
        if not isinstance(entry, dict):
            continue
        matched_path = str(match.get("matched_path") or "")
        scope = str(match.get("scope") or "")
        if scope == "file":
            conflicts.append({
                "path":                source_path,
                "reason":              "exact_file_override_wins",
                "file_override_path":   matched_path,
                "file_override_scope":  scope,
            })
        elif scope == "folder" and matched_path.startswith(folder_key + "/"):
            conflicts.append({
                "path":                source_path,
                "reason":              "deeper_folder_override_wins",
                "file_override_path":   matched_path,
                "file_override_scope":  scope,
            })
        elif scope == "folder" and matched_path == folder_key:
            conflicts.append({
                "path":                source_path,
                "reason":              "existing_same_folder_override",
                "file_override_path":   matched_path,
                "file_override_scope":  scope,
            })
    return conflicts


def _folder_preview_scope_payload(config: Mapping[str, Any], folder_path: str) -> dict[str, Any]:
    profile = effective_library_profile_for_source_path(config, folder_path)
    library = _library_response(profile)
    source_root = normalize_file_override_path(library.get("source_path") or "")
    folder_key = normalize_file_override_path(folder_path)
    return {
        "kind":            "folder",
        "library_id":      str(library.get("id") or ""),
        "library_name":    str(library.get("name") or ""),
        "library_source_path": str(library.get("source_path") or ""),
        "is_library_root": bool(source_root and source_root == folder_key),
    }


def _file_override_folder_preview_payload(
    *,
    resolved: Any,
    folder_path: str,
    proposed_override: Mapping[str, Any],
    options: Mapping[str, Any],
) -> dict[str, Any]:
    rows, snapshot_warnings, snapshot_partial = _folder_preview_load_snapshot_rows(resolved)
    source_rows = _folder_preview_source_rows(rows, folder_path)
    sample_limit = int(options.get("sample_limit") or FOLDER_PREVIEW_DEFAULT_SAMPLE_LIMIT)
    sampled_rows = source_rows[:sample_limit]
    sample_payloads: list[dict[str, Any]] = []
    metadata_partial = False
    for row in sampled_rows:
        sample, partial = _folder_preview_sample_row(row, proposed_override)
        sample_payloads.append(sample)
        metadata_partial = metadata_partial or partial

    fo_path = getattr(resolved, "file_overrides_path", None)
    manifest = read_file_overrides(fo_path) if fo_path is not None else _empty_manifest()
    conflicts = _folder_preview_conflicts(
        manifest=manifest,
        source_rows=source_rows,
        folder_path=folder_path,
    )
    warnings = list(snapshot_warnings)
    warnings.extend(_folder_preview_aggregate_warnings(sample_payloads))
    if options.get("use_cached_track_metadata_only") is not True:
        warnings.append(_track_warning(
            "Folder preview does not run per-file probes; cached queue metadata was used only.",
            field="options.use_cached_track_metadata_only",
        ))
    if not source_rows:
        warnings.append(_track_warning(
            "No known queue rows currently fall under this folder; future files under the folder would still match a saved folder rule.",
            field="folder_path",
        ))

    known_count = len(source_rows)
    previewed_count = len(sample_payloads)
    partial = bool(snapshot_partial or metadata_partial or known_count > previewed_count)
    config = getattr(resolved, "config_data", {}) or {}
    payload = _folder_preview_base_payload(
        ok=True,
        severity="ok",
        message=f"Folder override impact preview for: {folder_path}",
    )
    payload.update({
        "folder_path":             folder_path,
        "normalized_folder_path":  normalize_file_override_path(folder_path),
        "scope":                   _folder_preview_scope_payload(config if isinstance(config, Mapping) else {}, folder_path),
        "impact": {
            "known_file_count":          known_count,
            "previewed_file_count":      previewed_count,
            "partial":                   partial,
            "future_files_would_match":  True,
            "cached_track_metadata_only": True,
        },
        "conflicts":              conflicts,
        "warnings":               warnings,
        "sample_rows":            sample_payloads,
        "can_save_folder_rule":   True,
        "requires_confirmation":  True,
        "accepted_fields": {
            "audio":     sorted(FOLDER_PREVIEW_SECTION_KEYS["audio"]),
            "subtitles": sorted(FOLDER_PREVIEW_SECTION_KEYS["subtitles"]),
            "audio_selectors": sorted(FOLDER_PREVIEW_SELECTOR_KEYS["audio"]),
            "subtitle_selectors": sorted(FOLDER_PREVIEW_SELECTOR_KEYS["subtitles"]),
        },
        "rejected_selector_fields": sorted(FOLDER_PREVIEW_REJECTED_SELECTOR_KEYS),
    })
    return payload


def _folder_rule_manifest_entry(manifest: Mapping[str, Any], folder_path: str) -> dict[str, Any]:
    entries = manifest.get("entries") if isinstance(manifest, Mapping) else {}
    entry = _mapping(_mapping(entries).get(normalize_file_override_path(folder_path)))
    return {
        "set_at":    str(entry.get("set_at") or ""),
        "audio":     entry.get("audio"),
        "subtitles": entry.get("subtitles"),
        "routing":   entry.get("routing"),
        "video":     entry.get("video"),
    }


def _folder_rule_command_payload(
    *,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    resolved: Any,
    folder_path: str,
    message: str,
    cleared: bool = False,
) -> dict[str, Any]:
    payload = file_overrides_to_api_payload(dict(manifest), manifest_path)
    payload["command"] = FOLDER_RULE_COMMAND
    payload["severity"] = "ok"
    payload["message"] = message
    payload["folder_rule"] = {
        "folder_path":             folder_path,
        "normalized_folder_path":  normalize_file_override_path(folder_path),
        "scope":                   _folder_preview_scope_payload(
            getattr(resolved, "config_data", {}) if isinstance(getattr(resolved, "config_data", {}), Mapping) else {},
            folder_path,
        ),
        "cleared":                 cleared,
    }
    if not cleared:
        payload["folder_rule"]["entry"] = _folder_rule_manifest_entry(manifest, folder_path)
    return _fo_command_result_payload(payload)


def _track_warning(message: str, *, field: str = "track_metadata") -> dict[str, str]:
    return {"field": field, "message": message}


def _file_override_tracks_unavailable(
    *,
    source_path: str,
    message: str,
    probe_source: str = "unavailable",
) -> dict[str, Any]:
    return {
        "ok":              True,
        "command":         TRACKS_COMMAND,
        "schema_version":  TRACKS_SCHEMA_VERSION,
        "severity":        "warning",
        "message":         message,
        "path":            source_path,
        "normalized_path": normalize_file_override_path(source_path) if source_path else "",
        "probe_available": False,
        "probe_source":    probe_source,
        "audio_tracks":    [],
        "subtitle_tracks": [],
        "warnings":        [_track_warning(message)],
    }


def _track_language(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "und"


def _normalize_media_language(value: Any) -> str:
    language = _track_language(value)
    return LANGUAGE_NORMALIZATION_ALIASES.get(language, language)


def _language_display(value: Any) -> str:
    language = _normalize_media_language(value)
    return LANGUAGE_DISPLAY_NAMES.get(language, language.upper())


def _codec_display(value: Any) -> str:
    codec = str(value or "").strip().lower()
    if not codec:
        return "Unknown codec"
    return CODEC_DISPLAY_NAMES.get(codec, codec.replace("_", " ").replace("-", " ").upper())


def _track_title_contains(value: Any, fragments: tuple[str, ...]) -> bool:
    title = str(value or "").casefold()
    return any(fragment in title for fragment in fragments)


def _is_commentary_audio_track(track: SourceAudioStream) -> bool:
    return _track_title_contains(
        track.title,
        (
            "commentary",
            "director",
            "cast",
            "audio description",
            "descriptive",
            "behind the scenes",
            "isolated score",
        ),
    )


def _is_hearing_impaired_track(title: Any) -> bool:
    return _track_title_contains(title, ("sdh", "hearing impaired", "hearing-impaired", "hearing"))


def _audio_channel_layout(track: SourceAudioStream) -> str:
    layout = str(getattr(track, "channel_layout", "") or "").strip()
    if layout:
        return layout
    channels = int(track.channels or 0)
    if channels == 1:
        return "mono"
    if channels == 2:
        return "stereo"
    if channels == 6:
        return "5.1"
    if channels == 8:
        return "7.1"
    return f"{channels} channels" if channels > 0 else ""


def _audio_track_display(ordinal: int, row: Mapping[str, Any]) -> str:
    parts = [f"Audio {ordinal}", _language_display(row.get("language")), _codec_display(row.get("codec"))]
    layout = str(row.get("channel_layout") or "").strip()
    if layout:
        parts.append(layout)
    if row.get("default"):
        parts.append("Default")
    if row.get("forced"):
        parts.append("Forced")
    if row.get("commentary"):
        parts.append("Commentary")
    return " · ".join(part for part in parts if part)


def _subtitle_track_display(row: Mapping[str, Any]) -> str:
    stream_index = row.get("stream_index")
    parts = [f"Subtitle {stream_index}", _language_display(row.get("language"))]
    if row.get("default"):
        parts.append("Default")
    if row.get("forced"):
        parts.append("Forced")
    if row.get("hearing_impaired"):
        parts.append("SDH")
    parts.append(_codec_display(row.get("codec")))
    if row.get("image_based"):
        parts.append("Image")
    return " · ".join(part for part in parts if part)


def _audio_track_payload(track: SourceAudioStream, ordinal: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "stream_index":     int(track.stream_index),
        "language":         _track_language(track.language),
        "title":            str(track.title or ""),
        "codec":            str(track.codec or "").strip().lower(),
        "channels":         int(track.channels or 0),
        "channel_layout":   _audio_channel_layout(track),
        "default":          bool(track.default),
        "forced":           bool(track.forced),
        "commentary":       _is_commentary_audio_track(track),
        "hearing_impaired": _is_hearing_impaired_track(track.title),
    }
    row["display"] = _audio_track_display(ordinal, row)
    return row


def _subtitle_track_payload(track: SourceSubtitleStream) -> dict[str, Any]:
    codec = str(track.codec or "").strip().lower()
    row: dict[str, Any] = {
        "stream_index":     int(track.stream_index),
        "language":         _track_language(track.language),
        "title":            str(track.title or ""),
        "codec":            codec,
        "default":          bool(track.default),
        "forced":           bool(track.forced),
        "hearing_impaired": _is_hearing_impaired_track(track.title),
        "image_based":      bool(track.image_based or codec in IMAGE_SUBTITLE_CODEC_NAMES),
        "text_based":       bool(track.text_based),
        "subtitle_kind":    str(track.subtitle_kind or "unknown"),
    }
    row["display"] = _subtitle_track_display(row)
    return row


def _file_override_tracks_payload_from_probe_result(
    *,
    source_path: str,
    probe_result: ProbeResult,
    probe_source: str,
) -> dict[str, Any]:
    source_media = source_media_from_probe_result(probe_result, source_path=source_path)
    audio_tracks = [
        _audio_track_payload(track, ordinal)
        for ordinal, track in enumerate(source_media.audio_streams, start=1)
    ]
    subtitle_tracks = [_subtitle_track_payload(track) for track in source_media.subtitle_streams]
    return {
        "ok":              True,
        "command":         TRACKS_COMMAND,
        "schema_version":  TRACKS_SCHEMA_VERSION,
        "severity":        "ok",
        "message":         f"Track metadata for: {source_path}",
        "path":            source_path,
        "normalized_path": normalize_file_override_path(source_path),
        "probe_available": True,
        "probe_source":    probe_source,
        "audio_tracks":    audio_tracks,
        "subtitle_tracks": subtitle_tracks,
        "warnings":        [],
    }


def _probe_tracks_for_source_path(source_path: str, *, state_db_root: Path | None = None) -> dict[str, Any]:
    source = Path(source_path)
    try:
        if not source.exists() or not source.is_file():
            return _file_override_tracks_unavailable(
                source_path=source_path,
                message="Track metadata is not available because the source file could not be found.",
            )
    except OSError as exc:
        return _file_override_tracks_unavailable(
            source_path=source_path,
            message=f"Track metadata is not available because the source file could not be inspected: {exc}",
        )

    result = run_probe_stage(
        {"scratch_path": source_path},
        RunnerOptions(timeout_seconds=TRACKS_PROBE_TIMEOUT_SECONDS, state_db_root=state_db_root),
    )
    if not result.ok:
        message = result.error.message if result.error else "Track metadata probe failed."
        return _file_override_tracks_unavailable(
            source_path=source_path,
            message=message,
            probe_source="stage_probe",
        )

    try:
        probe_result = ProbeResult.model_validate(result.data or {})
    except Exception as exc:
        return _file_override_tracks_unavailable(
            source_path=source_path,
            message=f"Track metadata probe returned an invalid result: {exc}",
            probe_source="stage_probe",
        )

    if not probe_result.probe_ok:
        return _file_override_tracks_unavailable(
            source_path=source_path,
            message=f"Track metadata is not available for this source: {probe_result.probe_error or 'probe failed'}.",
            probe_source="stage_probe",
        )

    return _file_override_tracks_payload_from_probe_result(
        source_path=source_path,
        probe_result=probe_result,
        probe_source="stage_probe",
    )


EXACT_TRACK_SELECTOR_KEYS = ("streamIndex", "stream_index", "trackIndex", "track_index", "index")


def _effective_track_metadata(track_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _mapping(track_payload)
    available = bool(payload.get("probe_available"))
    return {
        "available":       available,
        "probe_available": available,
        "probe_source":    str(payload.get("probe_source") or ("stage_probe" if available else "unavailable")),
        "audio_tracks":    list(payload.get("audio_tracks") or []) if available else [],
        "subtitle_tracks": list(payload.get("subtitle_tracks") or []) if available else [],
        "warnings":        list(payload.get("warnings") or []),
    }


def _track_stream_index(track: Mapping[str, Any]) -> int | None:
    value = track.get("stream_index", track.get("index"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _selector_exact_stream_index(selector: Mapping[str, Any]) -> int | None:
    for key in EXACT_TRACK_SELECTOR_KEYS:
        if key not in selector:
            continue
        try:
            return int(selector.get(key))
        except (TypeError, ValueError):
            return None
    return None


def _selector_language(selector: Mapping[str, Any]) -> str:
    return _normalize_media_language(selector.get("language"))


def _selector_title(selector: Mapping[str, Any]) -> str:
    return str(selector.get("title") or "").strip()


def _selector_channels(selector: Mapping[str, Any]) -> int | None:
    if "channels" not in selector:
        return None
    try:
        channels = int(selector.get("channels"))
    except (TypeError, ValueError):
        return None
    return channels if channels > 0 else None


def _selector_forced(selector: Mapping[str, Any]) -> bool | None:
    if "forced" not in selector:
        return None
    value = selector.get("forced")
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _track_language_for_match(track: Mapping[str, Any]) -> str:
    return _normalize_media_language(track.get("language"))


def _track_title_for_match(track: Mapping[str, Any]) -> str:
    return str(track.get("title") or "").strip()


def _title_matches_glob(title: str, pattern: str) -> bool:
    return fnmatchcase(title.casefold(), pattern.casefold())


def _track_matches_selector(track: Mapping[str, Any], selector: Mapping[str, Any], *, kind: str) -> bool:
    exact_index = _selector_exact_stream_index(selector)
    if exact_index is not None and _track_stream_index(track) != exact_index:
        return False
    language = _selector_language(selector) if "language" in selector else ""
    if language and _track_language_for_match(track) != language:
        return False
    codec = str(selector.get("codec") or "").strip().casefold()
    if codec and str(track.get("codec") or "").strip().casefold() != codec:
        return False
    if kind == "audio":
        channels = _selector_channels(selector)
        if channels is not None and int(track.get("channels") or 0) != channels:
            return False
    if kind == "subtitle":
        forced = _selector_forced(selector)
        if forced is not None and bool(track.get("forced")) is not forced:
            return False
    title = _selector_title(selector)
    if title and not _title_matches_glob(_track_title_for_match(track), title):
        return False
    return True


def _selector_rules(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _selector_has_engine_consumed_key(selector: Mapping[str, Any], *, kind: str) -> bool:
    if _selector_exact_stream_index(selector) is not None:
        return True
    if "language" in selector and _selector_language(selector):
        return True
    if "codec" in selector and str(selector.get("codec") or "").strip():
        return True
    if "title" in selector and _selector_title(selector):
        return True
    if kind == "audio" and _selector_channels(selector) is not None:
        return True
    if kind == "subtitle" and _selector_forced(selector) is not None:
        return True
    return False


def _append_selector_warnings(
    warnings: list[dict[str, str]],
    *,
    field_path: str,
    selectors: list[Mapping[str, Any]],
    tracks: list[Mapping[str, Any]],
    kind: str,
) -> None:
    language_counts: dict[str, int] = {}
    indexes = {_track_stream_index(track) for track in tracks}
    for track in tracks:
        language = _track_language_for_match(track)
        if language:
            language_counts[language] = language_counts.get(language, 0) + 1

    for selector in selectors:
        exact_index = _selector_exact_stream_index(selector)
        language = _selector_language(selector) if "language" in selector else ""
        if exact_index is None and language:
            count = language_counts.get(language, 0)
            if count == 0:
                warnings.append(_track_warning(
                    f"Language '{language}' matches no {kind} tracks.",
                    field=field_path,
                ))
            elif count > 1:
                warnings.append(_track_warning(
                    f"Language '{language}' matches multiple {kind} tracks.",
                    field=field_path,
                ))

        if exact_index is not None:
            exact_track = next((track for track in tracks if _track_stream_index(track) == exact_index), None)
            if exact_index not in indexes:
                warnings.append(_track_warning(
                    f"Stream index {exact_index} is not available in detected {kind} tracks.",
                    field=field_path,
                ))
            elif exact_track is not None and not _track_matches_selector(exact_track, selector, kind=kind):
                warnings.append(_track_warning(
                    f"Stream index {exact_index} exists, but its detected metadata does not match the selector.",
                    field=field_path,
                ))

        if kind == "subtitle" and exact_index is None and _selector_forced(selector) is True:
            forced_matches = [
                track
                for track in tracks
                if bool(track.get("forced")) and _track_matches_selector(track, selector, kind=kind)
            ]
            if not forced_matches:
                warnings.append(_track_warning(
                    "Forced subtitle selector matches no detected forced subtitle tracks.",
                    field=field_path,
                ))


def _source_marker(source: str, field_path: str) -> dict[str, str]:
    return {"source": source, "field": field_path}


def _track_selection_section(
    *,
    kind: str,
    tracks: list[Mapping[str, Any]],
    section: Mapping[str, Any],
    source: str,
) -> dict[str, Any]:
    prefix = "audio" if kind == "audio" else "subtitles"
    keep_path = f"{prefix}.keepTracks"
    drop_path = f"{prefix}.dropTracks"
    strip_path = "subtitles.stripAll"
    keep_rules = _selector_rules(section.get("keepTracks"))
    drop_rules = _selector_rules(section.get("dropTracks"))
    warnings: list[dict[str, str]] = []

    _append_selector_warnings(warnings, field_path=keep_path, selectors=keep_rules, tracks=tracks, kind=kind)
    _append_selector_warnings(warnings, field_path=drop_path, selectors=drop_rules, tracks=tracks, kind=kind)

    applied_fields: list[str] = []
    for path, rules in ((keep_path, keep_rules), (drop_path, drop_rules)):
        if rules:
            applied_fields.append(path)
    if kind == "subtitle" and section.get("stripAll") is True:
        applied_fields.append(strip_path)

    kept: list[int] = []
    dropped: list[int] = []
    kept_sources: dict[str, dict[str, str]] = {}
    dropped_sources: dict[str, dict[str, str]] = {}

    for track in tracks:
        index = _track_stream_index(track)
        if index is None:
            continue
        index_key = str(index)
        if kind == "subtitle" and section.get("stripAll") is True:
            dropped.append(index)
            dropped_sources[index_key] = _source_marker(source, strip_path)
            continue
        if any(_track_matches_selector(track, rule, kind=kind) for rule in drop_rules):
            dropped.append(index)
            dropped_sources[index_key] = _source_marker(source, drop_path)
            continue
        if keep_rules:
            if any(_track_matches_selector(track, rule, kind=kind) for rule in keep_rules):
                kept.append(index)
                kept_sources[index_key] = _source_marker(source, keep_path)
            else:
                dropped.append(index)
                dropped_sources[index_key] = _source_marker(source, keep_path)
            continue
        kept.append(index)
        kept_sources[index_key] = _source_marker("default", "")

    return {
        "available":               True,
        "source":                  source if applied_fields else "default",
        "applied_fields":          applied_fields,
        "kept_stream_indexes":     kept,
        "dropped_stream_indexes":  dropped,
        "kept_stream_sources":     kept_sources,
        "dropped_stream_sources":  dropped_sources,
        "warnings":                warnings,
    }


def _track_selection_preview(
    *,
    track_metadata: Mapping[str, Any],
    entry: Mapping[str, Any],
    override_source: str,
    has_override: bool,
) -> dict[str, Any]:
    if not track_metadata.get("available"):
        warnings = list(track_metadata.get("warnings") or [])
        return {
            "audio": {
                "available":              False,
                "source":                 "unavailable",
                "applied_fields":         [],
                "kept_stream_indexes":    [],
                "dropped_stream_indexes": [],
                "kept_stream_sources":    {},
                "dropped_stream_sources": {},
                "warnings":               warnings,
            },
            "subtitles": {
                "available":              False,
                "source":                 "unavailable",
                "applied_fields":         [],
                "kept_stream_indexes":    [],
                "dropped_stream_indexes": [],
                "kept_stream_sources":    {},
                "dropped_stream_sources": {},
                "warnings":               warnings,
            },
        }

    audio_section = _mapping(entry.get("audio")) if has_override else {}
    subtitle_section = _mapping(entry.get("subtitles")) if has_override else {}
    return {
        "audio": _track_selection_section(
            kind="audio",
            tracks=[_mapping(track) for track in track_metadata.get("audio_tracks") or []],
            section=audio_section,
            source=override_source if audio_section else "default",
        ),
        "subtitles": _track_selection_section(
            kind="subtitle",
            tracks=[_mapping(track) for track in track_metadata.get("subtitle_tracks") or []],
            section=subtitle_section,
            source=override_source if subtitle_section else "default",
        ),
    }


def _override_exact_selector_validation(
    override_data: Mapping[str, Any],
    source_path: str,
    *,
    state_db_root: Path | None = None,
) -> tuple[list[str], list[str]]:
    selectors = _override_exact_selectors(override_data)
    if not selectors:
        return [], []

    track_payload = _probe_tracks_for_source_path(source_path, state_db_root=state_db_root)
    track_metadata = _effective_track_metadata(track_payload)
    if not track_metadata.get("available"):
        message = "Track metadata is unavailable; exact stream selectors will be checked again during processing."
        warnings = [message]
        for warning in track_metadata.get("warnings") or []:
            warning_message = str(_mapping(warning).get("message") or warning or "").strip()
            if warning_message:
                warnings.append(warning_message)
        return [], list(dict.fromkeys(warnings))

    audio_tracks = [_mapping(track) for track in track_metadata.get("audio_tracks") or []]
    subtitle_tracks = [_mapping(track) for track in track_metadata.get("subtitle_tracks") or []]
    errors: list[str] = []

    for field_path, selector_index, selector, kind in selectors:
        exact_index = _selector_exact_stream_index(selector)
        if exact_index is None:
            continue
        same_kind_tracks = audio_tracks if kind == "audio" else subtitle_tracks
        other_kind_tracks = subtitle_tracks if kind == "audio" else audio_tracks
        same_kind = next((track for track in same_kind_tracks if _track_stream_index(track) == exact_index), None)
        other_kind = next((track for track in other_kind_tracks if _track_stream_index(track) == exact_index), None)
        selector_path = f"{field_path}[{selector_index}]"
        if same_kind is None and other_kind is not None:
            article = "an" if kind == "audio" else "a"
            errors.append(f"'{selector_path}.streamIndex' does not target {article} {kind} stream.")
            continue
        if same_kind is None:
            errors.append(f"'{selector_path}.streamIndex' is not available in detected {kind} streams.")
            continue
        signature_errors = _exact_selector_signature_errors(selector_path, selector, same_kind, kind=kind)
        errors.extend(signature_errors)

    return errors, []


def _override_exact_selectors(override_data: Mapping[str, Any]) -> list[tuple[str, int, Mapping[str, Any], str]]:
    selectors: list[tuple[str, int, Mapping[str, Any], str]] = []
    for section_name, kind in (("audio", "audio"), ("subtitles", "subtitle")):
        section = _mapping(override_data.get(section_name))
        for key in ("keepTracks", "dropTracks"):
            rules = section.get(key)
            if not isinstance(rules, list):
                continue
            field_path = f"{section_name}.{key}"
            for index, selector in enumerate(rules):
                if isinstance(selector, Mapping) and _selector_exact_stream_index(selector) is not None:
                    selectors.append((field_path, index, selector, kind))
    return selectors


def _exact_selector_signature_errors(
    selector_path: str,
    selector: Mapping[str, Any],
    track: Mapping[str, Any],
    *,
    kind: str,
) -> list[str]:
    errors: list[str] = []
    language = _selector_language(selector) if "language" in selector else ""
    if language and _track_language_for_match(track) != language:
        errors.append(
            f"'{selector_path}.language' does not match detected stream "
            f"{_track_stream_index(track)} language '{_track_language_for_match(track)}'."
        )
    codec = str(selector.get("codec") or "").strip().casefold()
    detected_codec = str(track.get("codec") or "").strip().casefold()
    if codec and detected_codec != codec:
        errors.append(
            f"'{selector_path}.codec' does not match detected stream "
            f"{_track_stream_index(track)} codec '{detected_codec}'."
        )
    if kind == "audio":
        channels = _selector_channels(selector)
        detected_channels = int(track.get("channels") or 0)
        if channels is not None and detected_channels != channels:
            errors.append(
                f"'{selector_path}.channels' does not match detected stream "
                f"{_track_stream_index(track)} channel count {detected_channels}."
            )
    else:
        forced = _selector_forced(selector)
        if forced is not None and bool(track.get("forced")) is not forced:
            errors.append(
                f"'{selector_path}.forced' does not match detected stream "
                f"{_track_stream_index(track)} forced flag {bool(track.get('forced'))}."
            )
    return errors


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


def _route_video_processing_projection(route_video_fields: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    def effective(field_name: str) -> dict[str, Any]:
        return _mapping(_mapping(route_video_fields.get(field_name)).get("effective"))

    route_profile = str(effective("routeProfile").get("value") or "").strip().casefold()
    container = str(effective("videoContainer").get("value") or "").strip().casefold()
    video_codec = str(effective("videoCodec").get("value") or "").strip()
    encode_preset = str(effective("videoEncodePreset").get("value") or "").strip()
    encode_ladder = str(effective("videoEncodeLadder").get("value") or "").strip()
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

    if route_profile in {"encode", "transcode"} or video_requires_transcode:
        route = "transcode"
    elif route_profile == "remux":
        route = "remux"
    else:
        route = ""

    warnings: list[str] = []
    if route == "transcode":
        warnings.append("Effective route/video override may force a full video transcode during processing.")
    if route_profile == "remux" and video_requires_transcode:
        warnings.append("routing.profile=remux is incompatible with video fields that require transcode.")

    return {
        "route":                  route,
        "videoCodec":             "copy" if route == "remux" else video_codec,
        "container":              container,
        "encodePreset":           encode_preset,
        "encodeLadder":           encode_ladder,
        "will_force_transcode":   route == "transcode",
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
    route_video_processing = _route_video_processing_projection(route_video_fields)
    track_metadata = _effective_track_metadata(
        track_payload or _probe_tracks_for_source_path(source_path, state_db_root=state_db_root)
    )
    track_selection = _track_selection_preview(
        track_metadata=track_metadata,
        entry=entry,
        override_source=override_source,
        has_override=has_override,
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
        "sources":                    sources,
    }


class LocalApiFileOverridesCommandPayloadMixin:

    def _file_overrides_folder_rule_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides/folder-rule — save/clear validated folder-prefix rules."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(FOLDER_RULE_COMMAND, "queue")

        fo_path = getattr(resolved, "file_overrides_path", None)
        if fo_path is None:
            return _folder_rule_error("state_root is not configured (LocalBase may be missing from config)")

        top_level_errors = _unsupported_folder_rule_key_errors(request)
        if top_level_errors:
            return _folder_rule_validation_error(top_level_errors)

        folder_path, path_error = _validate_folder_source_path(resolved, request.get("folder_path", ""))
        if path_error:
            return _folder_rule_error(path_error)

        library_root_error = _folder_rule_library_root_error(resolved, folder_path or "")
        if library_root_error:
            return _folder_rule_error(library_root_error)

        if request.get("clear"):
            try:
                manifest = clear_file_override_entry(fo_path, folder_path or "")
            except Exception as exc:
                self.logger.exception("queue.file_overrides.folder_rule clear failed: %s", exc)
                return _folder_rule_error(f"Failed to clear folder override for '{folder_path}': {exc}")
            return _folder_rule_command_payload(
                manifest=manifest,
                manifest_path=fo_path,
                resolved=resolved,
                folder_path=folder_path or "",
                message=f"Folder override cleared for: {folder_path}",
                cleared=True,
            )

        confirmation_errors = _validate_folder_rule_confirmation(request.get("confirmation"))
        override_data, override_errors = _validate_folder_rule_override(request.get("override"))
        errors = confirmation_errors + override_errors
        if errors:
            return _folder_rule_validation_error(errors)

        try:
            manifest = set_file_override_entry(fo_path, folder_path or "", override_data)
        except Exception as exc:
            self.logger.exception("queue.file_overrides.folder_rule save failed: %s", exc)
            return _folder_rule_error(f"Failed to write folder override for '{folder_path}': {exc}")

        return _folder_rule_command_payload(
            manifest=manifest,
            manifest_path=fo_path,
            resolved=resolved,
            folder_path=folder_path or "",
            message=f"Folder override saved for: {folder_path}",
        )

    def _file_overrides_folder_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides/folder-preview — read-only folder rule impact preview."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(FOLDER_PREVIEW_COMMAND, "queue")

        top_level_errors = _unsupported_folder_preview_key_errors(request)
        if top_level_errors:
            return _folder_preview_validation_error(top_level_errors)

        folder_path, path_error = _validate_folder_source_path(resolved, request.get("folder_path", ""))
        if path_error:
            return _folder_preview_error(path_error)

        proposed_override, proposal_errors = _validate_folder_preview_proposal(request.get("proposed_override", {}))
        options, option_errors = _validate_folder_preview_options(request.get("options", {}))
        errors = proposal_errors + option_errors
        if errors:
            return _folder_preview_validation_error(errors)

        return _file_override_folder_preview_payload(
            resolved=resolved,
            folder_path=folder_path or "",
            proposed_override=proposed_override,
            options=options,
        )

    def _file_overrides_route_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides/route-preview — read-only route impact preview."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(ROUTE_PREVIEW_COMMAND, "queue")

        top_level_errors = _unsupported_route_preview_key_errors(request)
        if top_level_errors:
            return _route_preview_validation_error(top_level_errors)

        path_raw = str(request.get("path", "")).strip()
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return _route_preview_error(error if path_raw else "'path' is required.")

        proposed_override, validation_errors, validation_warnings = _validate_route_preview_proposal(
            request.get("proposed_override", {})
        )
        if validation_errors:
            payload = _route_preview_validation_error(validation_errors)
            payload["warnings"] = validation_warnings
            return payload

        payload = _file_override_route_preview_payload(
            resolved=resolved,
            source_path=source_path or "",
            proposed_override=proposed_override,
        )
        if payload.get("ok") and validation_warnings:
            payload["warnings"] = validation_warnings + list(payload.get("warnings") or [])
        return payload

    def _file_overrides_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides — set / update / clear overrides."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.file_overrides", "queue")

        fo_path = getattr(resolved, "file_overrides_path", None)
        if fo_path is None:
            return _fo_unavailable("state_root is not configured (LocalBase may be missing from config)", command_result=True)

        top_level_errors = _unsupported_post_key_errors(request)
        if top_level_errors:
            return _fo_validation_error(top_level_errors)

        # ── Clear all ──────────────────────────────────────────────────────
        if request.get("clear_all"):
            try:
                manifest = _empty_manifest()
                _write_atomic(fo_path, manifest)
            except Exception as exc:
                self.logger.exception("queue.file_overrides clear_all failed: %s", exc)
                return _fo_error(f"Failed to clear overrides: {exc}")
            payload = file_overrides_to_api_payload({"version": 1, "entries": {}}, fo_path)
            payload["command"]  = "queue.file_overrides"
            payload["severity"] = "ok"
            payload["message"]  = "All file overrides cleared."
            return _fo_command_result_payload(payload)

        # ── Require path for all other operations ──────────────────────────
        path_raw = str(request.get("path", "")).strip()
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return _fo_error(error if path_raw else "'path' is required (or use 'clear_all': true to clear everything).")

        # ── Clear single entry ─────────────────────────────────────────────
        if request.get("clear"):
            try:
                manifest = clear_file_override_entry(fo_path, source_path or "")
            except Exception as exc:
                self.logger.exception("queue.file_overrides clear failed: %s", exc)
                return _fo_error(f"Failed to clear override for '{source_path}': {exc}")
            payload = file_overrides_to_api_payload(manifest, fo_path)
            payload["command"]  = "queue.file_overrides"
            payload["severity"] = "ok"
            payload["message"]  = f"Override cleared for: {source_path}"
            return _fo_command_result_payload(payload)

        # ── Clear selected fields from exact file entry ────────────────────
        if "clear_fields" in request:
            raw_clear_fields = request.get("clear_fields")
            if not isinstance(raw_clear_fields, list) or not raw_clear_fields:
                return _fo_error("'clear_fields' must be a non-empty list of field paths.")
            clear_fields: list[str] = []
            for value in raw_clear_fields:
                if not isinstance(value, str) or not value.strip():
                    return _fo_error("'clear_fields' must contain non-empty field path strings.")
                clear_fields.append(value.strip())
            invalid_fields = [field for field in clear_fields if field not in CLEARABLE_FILE_OVERRIDE_FIELDS]
            if invalid_fields:
                allowed = ", ".join(sorted(CLEARABLE_FILE_OVERRIDE_FIELDS))
                return _fo_error(
                    "Unsupported clear_fields path(s): "
                    f"{', '.join(invalid_fields)}. Allowed fields: {allowed}."
                )
            try:
                manifest = clear_file_override_fields(fo_path, source_path or "", clear_fields)
            except Exception as exc:
                self.logger.exception("queue.file_overrides clear_fields failed: %s", exc)
                return _fo_error(f"Failed to clear override fields for '{source_path}': {exc}")
            payload = file_overrides_to_api_payload(manifest, fo_path)
            payload["command"]  = "queue.file_overrides"
            payload["severity"] = "ok"
            payload["message"]  = f"Override fields cleared for: {source_path}"
            return _fo_command_result_payload(payload)

        # ── Set / update entry ─────────────────────────────────────────────
        override_data: dict[str, Any] = {}
        for key in ("audio", "subtitles", "routing", "video"):
            val = request.get(key)
            if val is not None:
                if not isinstance(val, dict):
                    return _fo_error(f"'{key}' must be an object.")
                if key in {"routing", "video"} and not val:
                    continue
                override_data[key] = val

        if not override_data:
            return _fo_error(
                "No override fields provided. "
                "Include at least one of: audio, subtitles, routing, video. "
                "To clear an entry use 'clear': true."
            )

        validation_errors = validate_file_override_payload(override_data)
        if validation_errors:
            return _fo_validation_error(validation_errors)
        exact_errors, exact_warnings = _override_exact_selector_validation(
            override_data,
            source_path or "",
            state_db_root=getattr(resolved, "state_root", None),
        )
        if exact_errors:
            return _fo_validation_error(exact_errors)
        validation_warnings = file_override_payload_warnings(override_data) + exact_warnings

        try:
            manifest = set_file_override_entry(fo_path, source_path or "", override_data)
        except Exception as exc:
            self.logger.exception("queue.file_overrides set failed: %s", exc)
            return _fo_error(f"Failed to write override for '{source_path}': {exc}")

        payload = file_overrides_to_api_payload(manifest, fo_path)
        payload["command"]  = "queue.file_overrides"
        payload["severity"] = "ok"
        payload["message"]  = f"Override saved for: {source_path}"
        if validation_warnings:
            payload["warnings"] = validation_warnings
        return _fo_command_result_payload(payload)

    def _file_overrides_read_payload(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET /api/queue/file-overrides — read manifest or single entry."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.file_overrides.read", "queue")

        fo_path = getattr(resolved, "file_overrides_path", None)
        if fo_path is None:
            return _fo_unavailable("state_root is not configured")

        manifest = read_file_overrides(fo_path)

        # Single-path query: return resolved entry for one source path
        path_raw = _query_text(query, "path")
        if path_raw:
            source_path, error = validate_queue_source_path(resolved, path_raw)
            if error:
                return _fo_unavailable(error)
            entry = get_file_override_entry(manifest, source_path or "")
            return {
                "ok":           True,
                "command":      "queue.file_overrides.read",
                "severity":     "ok",
                "message":      f"Override entry for: {source_path}",
                "manifest_path": str(fo_path),
                "path":         source_path,
                "entry":        entry,
                "has_override": entry is not None,
            }

        # Full manifest
        payload = file_overrides_to_api_payload(manifest, fo_path)
        payload["command"]  = "queue.file_overrides.read"
        payload["severity"] = "ok"
        payload["message"]  = f"{len(manifest.get('entries', {}))} file override entries."
        return payload

    def _file_overrides_effective_read_payload(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET /api/queue/file-overrides/effective — inspect resolved drawer settings."""
        command = "queue.file_overrides.effective"
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(command, "queue")

        fo_path = getattr(resolved, "file_overrides_path", None)
        if fo_path is None:
            return _fo_read_error(command, "File overrides service unavailable: state_root is not configured")

        path_raw = _query_text(query, "path")
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return _fo_read_error(command, error if path_raw else "'path' is required.")

        manifest = read_file_overrides(fo_path)
        config = getattr(resolved, "config_data", {}) or {}
        return _file_override_effective_payload(
            manifest=manifest,
            manifest_path=fo_path,
            source_path=source_path or "",
            config=config if isinstance(config, Mapping) else {},
            state_db_root=getattr(resolved, "state_root", None),
        )

    def _file_overrides_tracks_read_payload(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET /api/queue/file-overrides/tracks — read normalized track metadata."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(TRACKS_COMMAND, "queue")

        path_raw = _query_text(query, "path")
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return _fo_read_error(TRACKS_COMMAND, error if path_raw else "'path' is required.")

        return _probe_tracks_for_source_path(source_path or "", state_db_root=getattr(resolved, "state_root", None))
