from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from app.config.library_profiles import effective_library_profile_for_source_path
from app.queue.file_overrides import (
    _empty_manifest,
    file_overrides_to_api_payload,
    normalize_file_override_path,
    read_file_overrides,
    resolve_file_override_match,
    validate_file_override_payload,
)

from .effective_fields import _library_response
from .results import (
    FOLDER_RULE_COMMAND,
    _fo_command_result_payload,
    _folder_preview_base_payload,
    _mapping,
)
from .selectors import _track_selection_section, _track_stream_index
from .tracks import (
    IMAGE_SUBTITLE_CODEC_NAMES,
    _audio_track_display,
    _is_hearing_impaired_track,
    _subtitle_track_display,
    _track_language,
    _track_title_contains,
    _track_warning,
)


FOLDER_PREVIEW_DEFAULT_SAMPLE_LIMIT = 25
FOLDER_PREVIEW_MAX_SAMPLE_LIMIT = 100
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


def queue_source_roots(resolved: Any):
    from mediapipeline_desktop_app.api.queue_source_path_policy import queue_source_roots as _queue_source_roots

    return _queue_source_roots(resolved)


def validate_queue_source_path(resolved: Any, raw_path: Any, **kwargs: Any):
    from mediapipeline_desktop_app.api.queue_source_path_policy import (
        validate_queue_source_path as _validate_queue_source_path,
    )

    return _validate_queue_source_path(resolved, raw_path, **kwargs)


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
