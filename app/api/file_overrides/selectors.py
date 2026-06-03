from __future__ import annotations

from collections.abc import Mapping
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from .results import _mapping
from .tracks import _normalize_media_language, _probe_tracks_for_source_path, _track_warning


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
