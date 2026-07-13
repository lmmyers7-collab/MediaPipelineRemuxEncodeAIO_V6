from __future__ import annotations

# ==============================================================================
# src/mediapipeline/core/queue/file_overrides.py
# ==============================================================================
# Per-file (and per-folder) à-la-carte processing overrides.
#
# The overrides manifest lives at:   state_root / "file_overrides.json"
#
# Entries may be file-level or folder-level.  A folder-level entry applies to
# every source path whose normalised string starts with the folder key + "/".
# File-level entries take precedence over folder entries; deepest folder wins
# among folder entries.
#
# Schema (file_overrides.json):
#   {
#     "version": 1,
#     "entries": {
#       "<normalised-path>": {
#         "set_at":  "<ISO-8601>",
#         "audio": {
#           "keepTracks":           [{"language":"eng"}, {"language":"jpn"}],
#           "dropTracks":           [{"language":"und"}],
#           "renameTracks":         [{"language":"eng","channels":6,"newTitle":"English 5.1"}],
#           "maxChannels":          6,
#           "downmixMode":          "max_channels",
#           "transcodeCodec":       "eac3",
#           "transcodeBitrate":     "640k",
#           "preferDefaultLanguage":"eng"
#         },
#         "subtitles": {
#           "keepTracks":           [{"language":"eng","forced":false}],
#           "dropTracks":           [{"language":"und"}],
#           "burnTrack":            {"streamIndex":4,"language":"eng","codec":"subrip","forced":false},
#           "renameTracks":         [{"language":"eng","forced":false,"newTitle":"English"}],
#           "correctLanguageTags":  {"und":"eng"},
#           "stripAll":             false
#         },
#         "routing": {
#           "profile":              "transcode",
#           "routeThresholdMode":   "bitrate"
#         },
#         "video": {
#           "codec":                "h264_nvenc",
#           "container":            "mp4",
#           "encodePreset":         "balanced_nvenc",
#           "encodeLadder":         "plex_compat"
#         }
#       }
#     }
#   }
# ==============================================================================

import json
import os
import re
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, get_args
from collections.abc import Iterable

from mediapipeline.core.config.constants import ROUTE_THRESHOLD_MODE_NAMES
from mediapipeline.contracts.config import Config

FILE_OVERRIDES_VERSION = 1
_EMPTY: dict = {"version": FILE_OVERRIDES_VERSION, "entries": {}}
FILE_OVERRIDE_BATCH_METADATA_KEY = "_batch"
FILE_OVERRIDE_TRACK_TITLE_PATTERN_MAX_LENGTH = 256
FILE_OVERRIDE_TRACK_TITLE_VALUE_MAX_LENGTH = 1024
CLEARABLE_FILE_OVERRIDE_FIELDS: frozenset[str] = frozenset(
    {
        "audio.keepTracks",
        "audio.dropTracks",
        "audio.renameTracks",
        "audio.maxChannels",
        "audio.downmixMode",
        "audio.transcodeCodec",
        "audio.transcodeBitrate",
        "audio.preferDefaultLanguage",
        "subtitles.keepTracks",
        "subtitles.dropTracks",
        "subtitles.burnTrack",
        "subtitles.stripAll",
        "routing.profile",
        "routing.routeThresholdMode",
        "video.codec",
        "video.container",
        "video.encodePreset",
        "video.encodeLadder",
    }
)
_CLEARABLE_FIELD_KEYS: dict[str, tuple[str, str]] = {
    "audio.keepTracks": ("audio", "keepTracks"),
    "audio.dropTracks": ("audio", "dropTracks"),
    "audio.renameTracks": ("audio", "renameTracks"),
    "audio.maxChannels": ("audio", "maxChannels"),
    "audio.downmixMode": ("audio", "downmixMode"),
    "audio.transcodeCodec": ("audio", "transcodeCodec"),
    "audio.transcodeBitrate": ("audio", "transcodeBitrate"),
    "audio.preferDefaultLanguage": ("audio", "preferDefaultLanguage"),
    "subtitles.keepTracks": ("subtitles", "keepTracks"),
    "subtitles.dropTracks": ("subtitles", "dropTracks"),
    "subtitles.burnTrack": ("subtitles", "burnTrack"),
    "subtitles.stripAll": ("subtitles", "stripAll"),
    "routing.profile": ("routing", "profile"),
    "routing.routeThresholdMode": ("routing", "routeThresholdMode"),
    "video.codec": ("video", "codec"),
    "video.container": ("video", "container"),
    "video.encodePreset": ("video", "encodePreset"),
    "video.encodeLadder": ("video", "encodeLadder"),
}
SUPPORTED_FILE_OVERRIDE_TOP_LEVEL_KEYS: frozenset[str] = frozenset({"audio", "subtitles", "routing", "video"})
SUPPORTED_FILE_OVERRIDE_AUDIO_KEYS: frozenset[str] = frozenset(
    {
        "keepTracks",
        "dropTracks",
        "renameTracks",
        "maxChannels",
        "downmixMode",
        "transcodeCodec",
        "transcodeBitrate",
        "preferDefaultLanguage",
    }
)
SUPPORTED_FILE_OVERRIDE_SUBTITLE_KEYS: frozenset[str] = frozenset(
    {"keepTracks", "dropTracks", "burnTrack", "stripAll"}
)
SUPPORTED_FILE_OVERRIDE_ROUTING_KEYS: frozenset[str] = frozenset({"profile", "routeThresholdMode"})
SUPPORTED_FILE_OVERRIDE_VIDEO_KEYS: frozenset[str] = frozenset(
    {"codec", "container", "encodePreset", "encodeLadder"}
)
SUPPORTED_FILE_OVERRIDE_MAX_CHANNELS: frozenset[int] = frozenset({2, 6, 8})
SUPPORTED_FILE_OVERRIDE_ROUTE_PROFILES: frozenset[str] = frozenset(
    {
        "auto",
        "encode",
        "remux",
        "transcode",
        "plex_direct_stream",
        "plex_direct_play",
        "archive_shrink",
        "archive_quality",
        "manual",
    }
)
SAFE_OVERRIDE_SCALAR_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
AUDIO_TRANSCODE_BITRATE_RE = re.compile(r"^[1-9]\d*k$")


class FileOverrideValidationError(ValueError):
    """Validation failure for a complete file override entry."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class FileOverrideManifestReadError(ValueError):
    """Existing file-overrides state is present but cannot be trusted."""


def _literal_choices(field_name: str) -> frozenset[str]:
    field = Config.model_fields.get(field_name)
    return frozenset(str(item) for item in get_args(field.annotation)) if field is not None else frozenset()


SUPPORTED_FILE_OVERRIDE_VIDEO_CODECS: frozenset[str] = _literal_choices("VideoCodec")
SUPPORTED_FILE_OVERRIDE_OUTPUT_CONTAINERS: frozenset[str] = _literal_choices("OutputContainer")
SUPPORTED_FILE_OVERRIDE_ENCODE_PRESETS: frozenset[str] = _literal_choices("EncodeTuningPreset")
SUPPORTED_FILE_OVERRIDE_ENCODE_LADDERS: frozenset[str] = _literal_choices("EncodeLadder")
SUPPORTED_FILE_OVERRIDE_AUDIO_TRANSCODE_CODECS: frozenset[str] = _literal_choices("AudioTranscodeCodec")
SUPPORTED_FILE_OVERRIDE_AUDIO_DOWNMIX_MODES: frozenset[str] = _literal_choices("AudioDownmixMode")
SUPPORTED_AUDIO_TRACK_SELECTOR_KEYS: frozenset[str] = frozenset(
    {"streamIndex", "language", "codec", "channels", "title"}
)
SUPPORTED_AUDIO_RENAME_TRACK_KEYS: frozenset[str] = frozenset({"language", "channels", "newTitle"})
SUPPORTED_SUBTITLE_TRACK_SELECTOR_KEYS: frozenset[str] = frozenset(
    {"streamIndex", "language", "codec", "forced", "title"}
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def file_overrides_path(state_root: Path) -> Path:
    """Return the canonical path to file_overrides.json."""
    return state_root / "file_overrides.json"


def _normalise(path: str | Path) -> str:
    return str(path).replace("\\", "/").lower().rstrip("/")


def normalize_file_override_path(path: str | Path) -> str:
    """Return the manifest path key used by file_overrides.json."""
    return _normalise(path)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_file_overrides(path: Path) -> dict:
    """Load a manifest; absence is empty while malformed persisted state fails closed."""
    if not path.exists():
        return _empty_manifest()
    try:
        text = path.read_text(encoding="utf-8-sig")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise FileOverrideManifestReadError("file_overrides.json root must be an object")
        if data.get("version") != FILE_OVERRIDES_VERSION:
            raise FileOverrideManifestReadError(
                f"file_overrides.json version must be {FILE_OVERRIDES_VERSION}"
            )
        entries = data.get("entries")
        if not isinstance(entries, dict):
            raise FileOverrideManifestReadError("file_overrides.json entries must be an object")
        return {**data, "entries": _manifest_object_entries(entries)}
    except json.JSONDecodeError as exc:
        raise FileOverrideManifestReadError(
            f"file_overrides.json contains invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    except UnicodeDecodeError as exc:
        raise FileOverrideManifestReadError("file_overrides.json is not valid UTF-8") from exc
    except OSError as exc:
        raise FileOverrideManifestReadError(f"file_overrides.json could not be read: {exc}") from exc


def _manifest_object_entries(entries: dict) -> dict:
    return {
        str(key): value
        for key, value in entries.items()
        if isinstance(value, dict)
    }


def _empty_manifest() -> dict:
    return {"version": FILE_OVERRIDES_VERSION, "entries": {}}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def get_file_override_entry(manifest: dict, source_path: str | Path) -> dict | None:
    """
    Resolve the effective override object for *source_path*.

    Resolution order (first match wins):
      1. Exact file-level entry
      2. Deepest ancestor folder entry
      3. None — no override

    Returns a copy of the entry dict (without "set_at") or None.
    """
    match = resolve_file_override_match(manifest, source_path)
    entry = match.get("entry")
    return dict(entry) if isinstance(entry, dict) else None


def resolve_file_override_match(manifest: dict, source_path: str | Path) -> dict:
    """Resolve override entry metadata for *source_path* without changing semantics."""
    entries = manifest.get("entries", {}) if isinstance(manifest, dict) else {}
    if not isinstance(entries, dict) or not entries:
        return {"entry": None, "matched_path": None, "scope": None, "is_exact": False}

    norm = _normalise(source_path)

    if norm in entries and isinstance(entries[norm], dict):
        entry = dict(entries[norm])
        entry.pop("set_at", None)
        return {"entry": entry, "matched_path": norm, "scope": "file", "is_exact": True}

    best_len = -1
    best_key = None
    best_entry = None
    for key, entry in entries.items():
        key_text = str(key)
        if norm.startswith(key_text + "/") and len(key_text) > best_len and isinstance(entry, dict):
            best_len = len(key_text)
            best_key = key_text
            best_entry = entry

    if best_entry is not None:
        result = dict(best_entry)
        result.pop("set_at", None)
        return {"entry": result, "matched_path": best_key, "scope": "folder", "is_exact": False}

    return {"entry": None, "matched_path": None, "scope": None, "is_exact": False}


def list_override_entries(manifest: dict) -> list[dict]:
    """Return a list of all entries with their path and content."""
    return [
        {"path": k, **v}
        for k, v in manifest.get("entries", {}).items()
    ]


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def set_file_override_entry(
    manifest_path: Path,
    source_path: str | Path,
    override_data: dict,
    *,
    batch_metadata: dict[str, Any] | None = None,
    replace_existing: bool = False,
) -> dict:
    """
    Atomically set or update the override for *source_path*.

    Pass an empty dict {} to clear the entry (same as calling
    ``clear_file_override_entry``).  Returns the updated manifest.
    """
    manifest = read_file_overrides(manifest_path)
    _apply_file_override_entry(
        manifest.setdefault("entries", {}),
        source_path,
        override_data,
        batch_metadata=batch_metadata,
        replace_existing=replace_existing,
        set_at=datetime.now(UTC).isoformat(),
    )

    _write_atomic(manifest_path, manifest)
    return manifest


def set_file_override_entries(
    manifest_path: Path,
    updates: Iterable[tuple[str | Path, dict]],
    *,
    batch_metadata: dict[str, Any] | None = None,
    replace_existing: bool = False,
) -> dict:
    """Atomically apply multiple override updates in one manifest write."""
    manifest = read_file_overrides(manifest_path)
    entries: dict = manifest.setdefault("entries", {})
    set_at = datetime.now(UTC).isoformat()
    for source_path, override_data in updates:
        _apply_file_override_entry(
            entries,
            source_path,
            override_data,
            batch_metadata=batch_metadata,
            replace_existing=replace_existing,
            set_at=set_at,
        )
    _write_atomic(manifest_path, manifest)
    return manifest


def _apply_file_override_entry(
    entries: dict,
    source_path: str | Path,
    override_data: dict,
    *,
    batch_metadata: dict[str, Any] | None,
    replace_existing: bool,
    set_at: str,
) -> None:
    norm = _normalise(source_path)
    if not override_data:
        entries.pop(norm, None)
        return

    errors = validate_file_override_payload(override_data)
    if errors:
        raise FileOverrideValidationError(errors)
    existing = {} if replace_existing else entries.get(norm, {})
    sanitized = _sanitise_override(override_data)
    # Existing audio/subtitle save semantics replace their section. New
    # route/video sections are sparse patches, so merge them by field.
    merged = dict(existing)
    for key, value in sanitized.items():
        if (
            key in {"routing", "video"}
            and isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    merged_view = {
        key: value
        for key, value in merged.items()
        if key in SUPPORTED_FILE_OVERRIDE_TOP_LEVEL_KEYS
    }
    merged_errors = validate_file_override_payload(merged_view)
    if merged_errors:
        raise FileOverrideValidationError(merged_errors)
    merged["set_at"] = set_at
    if batch_metadata is None:
        merged.pop(FILE_OVERRIDE_BATCH_METADATA_KEY, None)
    else:
        merged[FILE_OVERRIDE_BATCH_METADATA_KEY] = _sanitise_batch_metadata(batch_metadata)
    entries[norm] = merged


def clear_file_override_entry(manifest_path: Path, source_path: str | Path) -> dict:
    """Remove the override entry for *source_path*. Returns updated manifest."""
    return set_file_override_entry(manifest_path, source_path, {})


def validate_file_override_payload(data: dict) -> list[str]:
    """Return validation errors for current per-file override fields."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["File override payload must be an object."]

    _append_unknown_key_errors(
        errors,
        path="override",
        keys=data.keys(),
        supported=SUPPORTED_FILE_OVERRIDE_TOP_LEVEL_KEYS,
    )
    for section_name, supported_keys in (
        ("audio", SUPPORTED_FILE_OVERRIDE_AUDIO_KEYS),
        ("subtitles", SUPPORTED_FILE_OVERRIDE_SUBTITLE_KEYS),
        ("routing", SUPPORTED_FILE_OVERRIDE_ROUTING_KEYS),
        ("video", SUPPORTED_FILE_OVERRIDE_VIDEO_KEYS),
    ):
        if section_name not in data:
            continue
        section = data.get(section_name)
        if not isinstance(section, dict):
            errors.append(f"'{section_name}' must be an object.")
            continue
        if not section:
            errors.append(f"'{section_name}' must contain at least one supported override field; omit it to inherit.")
            continue
        _append_unknown_key_errors(
            errors,
            path=section_name,
            keys=section.keys(),
            supported=supported_keys,
        )

    audio = data.get("audio") if isinstance(data.get("audio"), dict) else {}
    if isinstance(audio, dict):
        for key in ("keepTracks", "dropTracks"):
            if key in audio:
                _validate_track_selector_list(errors, f"audio.{key}", audio.get(key), kind="audio")
        if "renameTracks" in audio:
            _validate_audio_rename_track_list(errors, audio.get("renameTracks"))
        if "maxChannels" in audio:
            _validate_audio_max_channels(errors, audio.get("maxChannels"))
        if "downmixMode" in audio:
            _validate_enum_scalar(
                errors,
                "audio.downmixMode",
                audio.get("downmixMode"),
                SUPPORTED_FILE_OVERRIDE_AUDIO_DOWNMIX_MODES,
            )
        if "transcodeCodec" in audio:
            _validate_enum_scalar(
                errors,
                "audio.transcodeCodec",
                audio.get("transcodeCodec"),
                SUPPORTED_FILE_OVERRIDE_AUDIO_TRANSCODE_CODECS,
            )
        if "transcodeBitrate" in audio:
            _validate_audio_transcode_bitrate(errors, audio.get("transcodeBitrate"))
        if "preferDefaultLanguage" in audio:
            _validate_language_scalar(errors, "audio.preferDefaultLanguage", audio.get("preferDefaultLanguage"))

    subtitles = data.get("subtitles") if isinstance(data.get("subtitles"), dict) else {}
    burn_track_present = False
    if isinstance(subtitles, dict):
        for key in ("keepTracks", "dropTracks"):
            if key in subtitles:
                _validate_track_selector_list(errors, f"subtitles.{key}", subtitles.get(key), kind="subtitle")
        if "burnTrack" in subtitles:
            burn_track_present = True
            _validate_track_selector_object(errors, "subtitles.burnTrack", subtitles.get("burnTrack"), kind="subtitle")
            if isinstance(subtitles.get("burnTrack"), dict) and "streamIndex" not in subtitles.get("burnTrack", {}):
                errors.append("'subtitles.burnTrack.streamIndex' is required for subtitle burn-in.")
        if "stripAll" in subtitles and not isinstance(subtitles.get("stripAll"), bool):
            errors.append("'subtitles.stripAll' must be a boolean.")

    routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
    if isinstance(routing, dict):
        if "profile" in routing:
            _validate_enum_scalar(
                errors,
                "routing.profile",
                routing.get("profile"),
                SUPPORTED_FILE_OVERRIDE_ROUTE_PROFILES,
            )
        if "routeThresholdMode" in routing:
            _validate_enum_scalar(
                errors,
                "routing.routeThresholdMode",
                routing.get("routeThresholdMode"),
                frozenset(ROUTE_THRESHOLD_MODE_NAMES),
            )

    video = data.get("video") if isinstance(data.get("video"), dict) else {}
    if isinstance(video, dict):
        if "codec" in video:
            _validate_enum_scalar(errors, "video.codec", video.get("codec"), SUPPORTED_FILE_OVERRIDE_VIDEO_CODECS)
        if "container" in video:
            _validate_enum_scalar(
                errors,
                "video.container",
                video.get("container"),
                SUPPORTED_FILE_OVERRIDE_OUTPUT_CONTAINERS,
            )
        if "encodePreset" in video:
            _validate_enum_scalar(
                errors,
                "video.encodePreset",
                video.get("encodePreset"),
                SUPPORTED_FILE_OVERRIDE_ENCODE_PRESETS,
            )
        if "encodeLadder" in video:
            _validate_enum_scalar(
                errors,
                "video.encodeLadder",
                video.get("encodeLadder"),
                SUPPORTED_FILE_OVERRIDE_ENCODE_LADDERS,
            )

    route_profile = str(routing.get("profile") or "").strip().casefold() if isinstance(routing, dict) else ""
    video_forces_encode = False
    if isinstance(video, dict):
        video_forces_encode = any(key in video for key in ("codec", "encodePreset", "encodeLadder"))
        if str(video.get("container") or "").strip().casefold() in {"mp4", "m4v", "mov"}:
            video_forces_encode = True
    if route_profile == "remux" and video_forces_encode:
        errors.append(
            "'routing.profile' remux cannot be combined with video encode/container fields "
            "that require transcode."
        )
    if route_profile == "remux" and burn_track_present:
        errors.append(
            "'routing.profile' remux cannot be combined with subtitles.burnTrack because subtitle burn-in requires encode."
        )

    return errors


def _append_unknown_key_errors(
    errors: list[str],
    *,
    path: str,
    keys,
    supported: frozenset[str],
) -> None:
    unknown = sorted(str(key) for key in keys if str(key) not in supported)
    if unknown:
        errors.append(
            f"Unsupported {path} field(s): {', '.join(unknown)}. "
            f"Allowed fields: {', '.join(sorted(supported))}."
        )


def _validate_track_selector_list(errors: list[str], field_path: str, value: Any, *, kind: str) -> None:
    if not isinstance(value, list):
        errors.append(f"'{field_path}' must be a list of track selector objects.")
        return
    if not value:
        errors.append(f"'{field_path}' must contain at least one track selector; omit the field to inherit.")
        return
    for index, selector in enumerate(value):
        selector_path = f"{field_path}[{index}]"
        _validate_track_selector_object(errors, selector_path, selector, kind=kind)


def _validate_audio_rename_track_list(errors: list[str], value: Any) -> None:
    field_path = "audio.renameTracks"
    if not isinstance(value, list):
        errors.append(f"'{field_path}' must be a list of audio rename rule objects.")
        return
    if not value:
        errors.append(f"'{field_path}' must contain at least one audio rename rule; omit the field to inherit.")
        return
    for index, rule in enumerate(value):
        rule_path = f"{field_path}[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"'{rule_path}' must be an object with supported audio rename fields.")
            continue
        _append_unknown_key_errors(
            errors,
            path=rule_path,
            keys=rule.keys(),
            supported=SUPPORTED_AUDIO_RENAME_TRACK_KEYS,
        )
        if not any(key in rule for key in ("language", "channels")):
            errors.append(f"'{rule_path}' must contain language or channels so the runtime can resolve the target track.")
        _validate_optional_track_selector_string(errors, rule_path, rule, "language")
        if "channels" in rule:
            _validate_selector_channels(errors, f"{rule_path}.channels", rule.get("channels"))
        if "newTitle" not in rule:
            errors.append(f"'{rule_path}.newTitle' is required for audio rename rules.")
        else:
            _validate_optional_track_selector_string(errors, rule_path, rule, "newTitle")


def _validate_track_selector_object(errors: list[str], selector_path: str, selector: Any, *, kind: str) -> None:
    supported = SUPPORTED_AUDIO_TRACK_SELECTOR_KEYS if kind == "audio" else SUPPORTED_SUBTITLE_TRACK_SELECTOR_KEYS
    if not isinstance(selector, dict):
        errors.append(f"'{selector_path}' must be an object with supported track selector fields.")
        return
    _append_unknown_key_errors(
        errors,
        path=selector_path,
        keys=selector.keys(),
        supported=supported,
    )
    if not any(key in selector for key in supported):
        errors.append(f"'{selector_path}' must contain at least one supported track selector field.")
        return
    _validate_optional_track_selector_string(errors, selector_path, selector, "language")
    _validate_optional_track_selector_string(errors, selector_path, selector, "codec", scalar_safe=True)
    _validate_optional_track_selector_string(
        errors,
        selector_path,
        selector,
        "title",
        max_length=FILE_OVERRIDE_TRACK_TITLE_PATTERN_MAX_LENGTH,
    )
    if "streamIndex" in selector:
        _validate_stream_index(errors, f"{selector_path}.streamIndex", selector.get("streamIndex"))
    if kind == "audio" and "channels" in selector:
        _validate_selector_channels(errors, f"{selector_path}.channels", selector.get("channels"))
    if kind == "subtitle" and "forced" in selector and not isinstance(selector.get("forced"), bool):
        errors.append(f"'{selector_path}.forced' must be a boolean.")


def _validate_optional_track_selector_string(
    errors: list[str],
    selector_path: str,
    selector: dict,
    key: str,
    *,
    scalar_safe: bool = False,
    max_length: int | None = None,
) -> None:
    if key not in selector:
        return
    value = selector.get(key)
    if not isinstance(value, str):
        errors.append(f"'{selector_path}.{key}' must be a string.")
        return
    text = value.strip()
    if not text:
        errors.append(f"'{selector_path}.{key}' must not be empty; omit the selector field to inherit.")
        return
    if max_length is not None and len(text) > max_length:
        errors.append(f"'{selector_path}.{key}' must be {max_length} characters or fewer.")
        return
    if scalar_safe and not SAFE_OVERRIDE_SCALAR_RE.fullmatch(text):
        errors.append(f"'{selector_path}.{key}' contains unsupported characters.")


def _validate_stream_index(errors: list[str], field_path: str, value: Any) -> None:
    if type(value) is not int:
        errors.append(f"'{field_path}' must be an integer.")
        return
    if value < 0:
        errors.append(f"'{field_path}' must be zero or greater.")


def _validate_selector_channels(errors: list[str], field_path: str, value: Any) -> None:
    if type(value) is not int:
        errors.append(f"'{field_path}' must be an integer.")
        return
    if value <= 0:
        errors.append(f"'{field_path}' must be greater than zero.")


def _validate_audio_max_channels(errors: list[str], value) -> None:
    if type(value) is not int:
        errors.append("'audio.maxChannels' must be an integer.")
        return
    if value not in SUPPORTED_FILE_OVERRIDE_MAX_CHANNELS:
        allowed = ", ".join(str(item) for item in sorted(SUPPORTED_FILE_OVERRIDE_MAX_CHANNELS))
        errors.append(f"'audio.maxChannels' must be one of: {allowed}.")


def _validate_audio_transcode_bitrate(errors: list[str], value) -> None:
    if not isinstance(value, str):
        errors.append("'audio.transcodeBitrate' must be a string.")
        return
    text = value.strip()
    if not text:
        errors.append("'audio.transcodeBitrate' must not be empty; omit the field to inherit.")
        return
    if not AUDIO_TRANSCODE_BITRATE_RE.fullmatch(text):
        errors.append("'audio.transcodeBitrate' must match /^[1-9]\\d*k$/.")


def _validate_language_scalar(errors: list[str], field_path: str, value) -> None:
    if not isinstance(value, str):
        errors.append(f"'{field_path}' must be a string.")
        return
    if not value.strip():
        errors.append(f"'{field_path}' must not be empty; omit the field to inherit.")


def _validate_enum_scalar(errors: list[str], field_path: str, value, allowed: frozenset[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"'{field_path}' must be a string.")
        return
    text = value.strip()
    if not text:
        errors.append(f"'{field_path}' must not be empty; omit the field to inherit.")
        return
    if not SAFE_OVERRIDE_SCALAR_RE.fullmatch(text):
        errors.append(f"'{field_path}' contains unsupported characters.")
        return
    normalized = text.casefold()
    if normalized not in allowed:
        errors.append(f"'{field_path}' must be one of: {', '.join(sorted(allowed))}.")


def file_override_payload_warnings(data: dict) -> list[str]:
    """Return advisory warnings for valid but risky route/video override values."""
    warnings: list[str] = []
    if not isinstance(data, dict):
        return warnings
    routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
    route_profile = str(routing.get("profile") or "").strip().casefold() if isinstance(routing, dict) else ""
    if route_profile in {"encode", "transcode"}:
        warnings.append("routing.profile may force a full video transcode for this file.")
    elif route_profile == "remux":
        warnings.append("routing.profile remux forces remux unless processing rejects the source codec as unsafe.")
    video = data.get("video") if isinstance(data.get("video"), dict) else {}
    if isinstance(video, dict) and "container" in video:
        container = str(video.get("container") or "").strip().casefold()
        if container in {"mp4", "m4v", "mov"}:
            warnings.append("video.container may force a full video transcode for MP4-family output.")
    if isinstance(video, dict) and any(key in video for key in ("codec", "encodePreset", "encodeLadder")):
        warnings.append("video encode settings may force a full video transcode for this file.")
    subtitles = data.get("subtitles") if isinstance(data.get("subtitles"), dict) else {}
    if isinstance(subtitles, dict) and isinstance(subtitles.get("burnTrack"), dict):
        warnings.append("subtitles.burnTrack forces encode using the subtitle-burn encode profile.")
        warnings.append("subtitles.burnTrack drops all selectable output subtitle streams for this file.")
        warnings.append("subtitles.burnTrack is a destructive output change because the selected subtitle is rendered into video pixels.")
    _append_exact_selector_warnings(warnings, data)
    return warnings


def _append_exact_selector_warnings(warnings: list[str], data: dict) -> None:
    for section_name in ("audio", "subtitles"):
        section = data.get(section_name)
        if not isinstance(section, dict):
            continue
        for key in ("keepTracks", "dropTracks"):
            selectors = section.get(key)
            if not isinstance(selectors, list):
                continue
            for index, selector in enumerate(selectors):
                if not isinstance(selector, dict) or "streamIndex" not in selector:
                    continue
                signature_keys = ("language", "codec", "channels") if section_name == "audio" else ("language", "codec", "forced")
                if not any(sig_key in selector for sig_key in signature_keys):
                    warnings.append(
                        f"{section_name}.{key}[{index}] uses streamIndex without signature fields; "
                        "track metadata should be rechecked before processing."
                    )
        if section_name == "subtitles":
            selector = section.get("burnTrack")
            if not isinstance(selector, dict) or "streamIndex" not in selector:
                continue
            if not any(sig_key in selector for sig_key in ("language", "codec", "forced")):
                warnings.append(
                    "subtitles.burnTrack uses streamIndex without signature fields; "
                    "track metadata should be rechecked before processing."
                )


def clear_file_override_fields(
    manifest_path: Path,
    source_path: str | Path,
    field_paths: list[str] | tuple[str, ...],
) -> dict:
    """Clear whitelisted nested fields from an exact file-level override entry."""
    requested_fields = [str(field).strip() for field in field_paths if str(field).strip()]
    invalid_fields = [field for field in requested_fields if field not in CLEARABLE_FILE_OVERRIDE_FIELDS]
    if invalid_fields:
        raise ValueError(f"Unsupported file override field path(s): {', '.join(invalid_fields)}")

    manifest = read_file_overrides(manifest_path)
    entries: dict = manifest.setdefault("entries", {})
    norm = _normalise(source_path)
    if not _source_path_looks_like_file(source_path):
        return manifest

    entry = entries.get(norm)
    if not isinstance(entry, dict):
        return manifest

    changed = False
    for field_path in requested_fields:
        parent_key, child_key = _CLEARABLE_FIELD_KEYS[field_path]
        parent = entry.get(parent_key)
        if not isinstance(parent, dict) or child_key not in parent:
            continue
        parent.pop(child_key, None)
        changed = True
        if not parent:
            entry.pop(parent_key, None)

    if not changed:
        return manifest

    entry.pop(FILE_OVERRIDE_BATCH_METADATA_KEY, None)

    if not any(key not in {"set_at", FILE_OVERRIDE_BATCH_METADATA_KEY} for key in entry):
        entries.pop(norm, None)
    else:
        entry["set_at"] = datetime.now(UTC).isoformat()

    _write_atomic(manifest_path, manifest)
    return manifest


def _source_path_looks_like_file(source_path: str | Path) -> bool:
    path = Path(str(source_path))
    try:
        if path.exists():
            return path.is_file()
    except OSError:
        pass
    return bool(path.suffix)


def _sanitise_override(data: dict) -> dict:
    """Remove top-level keys that are reserved / managed by the service."""
    reserved = {"set_at", "version", FILE_OVERRIDE_BATCH_METADATA_KEY}
    sanitized: dict = {}
    for key, value in data.items():
        if key in reserved:
            continue
        if key == "routing" and isinstance(value, dict):
            routing = _sanitise_scalar_section(value, SUPPORTED_FILE_OVERRIDE_ROUTING_KEYS)
            if routing:
                sanitized[key] = routing
            continue
        if key == "video" and isinstance(value, dict):
            video = _sanitise_scalar_section(value, SUPPORTED_FILE_OVERRIDE_VIDEO_KEYS)
            if video:
                sanitized[key] = video
            continue
        if key == "subtitles" and isinstance(value, dict):
            subtitles = dict(value)
            burn_track = subtitles.get("burnTrack")
            if isinstance(burn_track, dict):
                # Burning makes every selectable subtitle output disappear. Keep
                # only the singular burn selector so prior keep/drop/strip
                # values cannot accidentally leak into processing.
                sanitized[key] = {"burnTrack": dict(burn_track)}
            else:
                sanitized[key] = value
            continue
        sanitized[key] = value
    return sanitized


def _sanitise_batch_metadata(data: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "origin",
        "batch_id",
        "batch_label",
        "batch_scope",
        "batch_source_path",
        "batch_detected_root",
        "batch_detected_name",
        "created_at",
    }
    sanitized: dict[str, Any] = {}
    for key in allowed:
        value = data.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    sanitized.setdefault("origin", "series_batch")
    return sanitized


def _sanitise_scalar_section(data: dict, supported: frozenset[str]) -> dict:
    result: dict = {}
    for key, value in data.items():
        key_text = str(key)
        if key_text not in supported:
            continue
        if isinstance(value, str):
            text = value.strip()
            if text:
                result[key_text] = text.casefold()
        else:
            result[key_text] = value
    return result


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

def _write_atomic(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex
    tmp = path.parent / f".{path.name}.{uid}.tmp"
    try:
        tmp.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# API serialisation helper
# ---------------------------------------------------------------------------

def file_overrides_to_api_payload(manifest: dict, manifest_path: Path) -> dict:
    """Convert the manifest to a stable API-safe dict."""
    entries = manifest.get("entries", {})
    return {
        "ok":             True,
        "version":        manifest.get("version", FILE_OVERRIDES_VERSION),
        "manifest_path":  str(manifest_path),
        "entry_count":    len(entries),
        "entries": {
            k: {
                "set_at":    v.get("set_at", ""),
                "audio":     v.get("audio"),
                "subtitles": v.get("subtitles"),
                "routing":   v.get("routing"),
                "video":     v.get("video"),
                "_batch":    v.get(FILE_OVERRIDE_BATCH_METADATA_KEY),
            }
            for k, v in entries.items()
        },
    }
