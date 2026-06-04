from __future__ import annotations

from collections.abc import Mapping
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from .results import _mapping
from .tracks import _normalize_media_language, _probe_tracks_for_source_path, _track_warning


EXACT_TRACK_SELECTOR_KEYS = ("streamIndex", "stream_index", "trackIndex", "track_index", "index")
_SUBTITLE_TEXT_CODECS = frozenset({"subrip", "srt", "webvtt"})
_SUBTITLE_ASS_CODECS = frozenset({"ass", "ssa"})
_SUBTITLE_TX3G_CODECS = frozenset({"mov_text", "tx3g", "text"})
_SUBTITLE_BDPGS_CODECS = frozenset({"hdmv_pgs_subtitle", "pgs"})
_SUBTITLE_VOBSUB_CODECS = frozenset({"dvd_subtitle", "dvdsub", "vobsub"})
_TRUTHY_TEXT = frozenset({"1", "true", "yes", "y", "on"})
_FALSEY_TEXT = frozenset({"0", "false", "no", "n", "off"})


def _effective_track_metadata(track_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _mapping(track_payload)
    available = bool(payload.get("probe_available"))
    probe_source = str(payload.get("probe_source") or ("stage_probe" if available else "unavailable"))
    source_info = _mapping(payload.get("source_info"))
    if source_info:
        source_info = {**source_info, "probe_source": str(source_info.get("probe_source") or probe_source)}
    else:
        source_info = {"available": False, "probe_source": probe_source}
    return {
        "available":       available,
        "probe_available": available,
        "probe_source":    probe_source,
        "source_info":     source_info,
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


def _selector_rule(value: Any) -> list[Mapping[str, Any]]:
    return [value] if isinstance(value, Mapping) else []


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
    burn_path = "subtitles.burnTrack"
    strip_path = "subtitles.stripAll"
    keep_rules = _selector_rules(section.get("keepTracks"))
    drop_rules = _selector_rules(section.get("dropTracks"))
    burn_rules = _selector_rule(section.get("burnTrack")) if kind == "subtitle" else []
    warnings: list[dict[str, str]] = []

    _append_selector_warnings(warnings, field_path=keep_path, selectors=keep_rules, tracks=tracks, kind=kind)
    _append_selector_warnings(warnings, field_path=drop_path, selectors=drop_rules, tracks=tracks, kind=kind)
    if burn_rules:
        _append_selector_warnings(warnings, field_path=burn_path, selectors=burn_rules, tracks=tracks, kind=kind)

    applied_fields: list[str] = []
    for path, rules in ((keep_path, keep_rules), (drop_path, drop_rules)):
        if rules:
            applied_fields.append(path)
    if burn_rules:
        applied_fields.append(burn_path)
    if kind == "subtitle" and section.get("stripAll") is True:
        applied_fields.append(strip_path)

    kept: list[int] = []
    dropped: list[int] = []
    burned: list[int] = []
    kept_sources: dict[str, dict[str, str]] = {}
    dropped_sources: dict[str, dict[str, str]] = {}
    burned_sources: dict[str, dict[str, str]] = {}

    for track in tracks:
        index = _track_stream_index(track)
        if index is None:
            continue
        index_key = str(index)
        if kind == "subtitle" and burn_rules:
            if any(_track_matches_selector(track, rule, kind=kind) for rule in burn_rules):
                burned.append(index)
                burned_sources[index_key] = _source_marker(source, burn_path)
            else:
                dropped.append(index)
                dropped_sources[index_key] = _source_marker(source, burn_path)
            continue
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
        "burned_stream_indexes":   burned,
        "kept_stream_sources":     kept_sources,
        "dropped_stream_sources":  dropped_sources,
        "burned_stream_sources":   burned_sources,
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
                "burned_stream_indexes":  [],
                "kept_stream_sources":    {},
                "dropped_stream_sources": {},
                "burned_stream_sources":  {},
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


def _settings_bool(settings: Mapping[str, Any], key: str, default: bool) -> bool:
    value = settings.get(key, default)
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    if text in _TRUTHY_TEXT:
        return True
    if text in _FALSEY_TEXT:
        return False
    return default


def _settings_languages(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_normalize_media_language(item) for item in value.split(",") if str(item or "").strip()]
    if not isinstance(value, list):
        return []
    languages: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            raw = item.get("language") or item.get("value") or item.get("id")
        else:
            raw = item
        text = str(raw or "").strip()
        if text:
            languages.append(_normalize_media_language(text))
    return languages


def _resolved_source_label(source: str, *, policy_label: str = "normal pipeline policy") -> str:
    if source == "file_override":
        return "file override"
    if source == "folder_override":
        return "folder override"
    if source == "library":
        return "library setting"
    if source == "global_default":
        return "global setting"
    if source in {"pipeline_policy", "default"}:
        return policy_label
    return policy_label


def _resolved_label(action: str, source: str, *, policy_label: str = "normal pipeline policy") -> str:
    return f"Resolved: {action} by {_resolved_source_label(source, policy_label=policy_label)}"


def _resolved_row(
    *,
    kind: str,
    track: Mapping[str, Any],
    action: str,
    source: str,
    field: str,
    label: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "kind":         kind,
        "stream_index": _track_stream_index(track),
        "action":       action,
        "source":       source,
        "field":        field,
        "label":        label,
        "reason":       reason,
    }


def _preview_track_resolution(section: Mapping[str, Any], stream_index: int | None) -> tuple[str, dict[str, str]]:
    if stream_index is None:
        return "", {}
    kept = {int(value) for value in section.get("kept_stream_indexes") or []}
    dropped = {int(value) for value in section.get("dropped_stream_indexes") or []}
    burned = {int(value) for value in section.get("burned_stream_indexes") or []}
    index_key = str(stream_index)
    if stream_index in burned:
        marker = _mapping(section.get("burned_stream_sources")).get(index_key)
        return "burn", _mapping(marker)
    if stream_index in dropped:
        marker = _mapping(section.get("dropped_stream_sources")).get(index_key)
        return "drop", _mapping(marker)
    if stream_index in kept:
        marker = _mapping(section.get("kept_stream_sources")).get(index_key)
        return "keep", _mapping(marker)
    return "", {}


def _subtitle_language_policy_allows(
    track: Mapping[str, Any],
    settings: Mapping[str, Any],
) -> tuple[bool, str, str]:
    languages = _settings_languages(settings.get("SubKeepLanguages"))
    if not languages:
        return True, "", ""
    language = _track_language_for_match(track)
    title = _track_title_for_match(track).casefold()
    is_sdh = bool(track.get("hearing_impaired")) or "sdh" in title or "hearing" in title
    is_forced = bool(track.get("forced"))
    if language in languages or (is_sdh and "und" not in languages) or is_sdh or is_forced:
        return True, "", ""
    languages_text = ", ".join(languages)
    reason = f"Subtitle language {language or 'und'} is outside saved subtitle keep languages ({languages_text})."
    return False, "SubKeepLanguages", reason


def _subtitle_codec_resolution(
    track: Mapping[str, Any],
    settings: Mapping[str, Any],
    retained_marker: Mapping[str, str],
) -> tuple[str, str, str, str, str]:
    codec = str(track.get("codec") or "").strip().casefold()
    retained_source = str(retained_marker.get("source") or "")
    retained_field = str(retained_marker.get("field") or "")
    retained_by_override = retained_source in {"file_override", "folder_override"} and bool(retained_field)
    retained_reason = ""
    if retained_by_override:
        retained_reason = f" Retained first by {_resolved_source_label(retained_source)} selector {retained_field}."

    if codec in _SUBTITLE_TEXT_CODECS:
        source = retained_source if retained_by_override else "pipeline_policy"
        field = retained_field if retained_by_override else "subtitle.codecRouting"
        reason = "Text subtitle is retained without conversion by normal subtitle policy." + retained_reason
        return "keep", source, field, _resolved_label("keep", source, policy_label="normal subtitle policy"), reason

    if codec in _SUBTITLE_ASS_CODECS:
        if _settings_bool(settings, "ConvertAssToSrt", True):
            reason = "ASS subtitle is retained and routed through saved ASS-to-SRT conversion policy." + retained_reason
            return "convert", "pipeline_policy", "ConvertAssToSrt", _resolved_label("convert", "pipeline_policy", policy_label="normal subtitle policy"), reason
        source = retained_source if retained_by_override else "pipeline_policy"
        field = retained_field if retained_by_override else "ConvertAssToSrt"
        reason = "ASS subtitle is retained because ASS-to-SRT conversion is disabled." + retained_reason
        return "keep", source, field, _resolved_label("keep", source, policy_label="normal subtitle policy"), reason

    if codec in _SUBTITLE_TX3G_CODECS:
        if _settings_bool(settings, "ConvertTx3gToSrt", True):
            reason = "TX3G subtitle is retained and routed through saved TX3G-to-SRT conversion policy." + retained_reason
            return "convert", "pipeline_policy", "ConvertTx3gToSrt", _resolved_label("convert", "pipeline_policy", policy_label="normal subtitle policy"), reason
        if _settings_bool(settings, "DropTx3gAfterConversion", False):
            reason = "TX3G conversion is disabled and saved TX3G cleanup policy drops the original track." + retained_reason
            return "drop", "pipeline_policy", "DropTx3gAfterConversion", _resolved_label("drop", "pipeline_policy", policy_label="normal subtitle policy"), reason
        source = retained_source if retained_by_override else "pipeline_policy"
        field = retained_field if retained_by_override else "ConvertTx3gToSrt"
        reason = "TX3G subtitle is retained because TX3G-to-SRT conversion is disabled." + retained_reason
        return "keep", source, field, _resolved_label("keep", source, policy_label="normal subtitle policy"), reason

    if codec in _SUBTITLE_BDPGS_CODECS:
        if _settings_bool(settings, "ConvertBdpgsToSrt", False):
            reason = "Image subtitle is retained and routed through saved BDPGS OCR conversion policy." + retained_reason
            return "convert", "pipeline_policy", "ConvertBdpgsToSrt", _resolved_label("convert", "pipeline_policy", policy_label="normal subtitle policy"), reason
        source = retained_source if retained_by_override else "pipeline_policy"
        field = retained_field if retained_by_override else "ConvertBdpgsToSrt"
        reason = "Image subtitle is retained because BDPGS OCR conversion is disabled." + retained_reason
        return "keep", source, field, _resolved_label("keep", source, policy_label="normal subtitle policy"), reason

    if codec in _SUBTITLE_VOBSUB_CODECS:
        if _settings_bool(settings, "ConvertVobSubToSrt", False):
            reason = "VobSub subtitle is retained and routed through saved VobSub OCR conversion policy." + retained_reason
            return "convert", "pipeline_policy", "ConvertVobSubToSrt", _resolved_label("convert", "pipeline_policy", policy_label="normal subtitle policy"), reason
        source = retained_source if retained_by_override else "pipeline_policy"
        field = retained_field if retained_by_override else "ConvertVobSubToSrt"
        reason = "VobSub subtitle is retained because VobSub OCR conversion is disabled." + retained_reason
        return "keep", source, field, _resolved_label("keep", source, policy_label="normal subtitle policy"), reason

    reason = f"Subtitle codec {codec or 'unknown'} is unsupported by normal subtitle policy."
    return "drop", "pipeline_policy", "subtitle.codecRouting", _resolved_label("drop", "pipeline_policy", policy_label="normal subtitle policy"), reason


def _resolved_audio_action(
    track: Mapping[str, Any],
    preview_section: Mapping[str, Any],
) -> dict[str, Any]:
    stream_index = _track_stream_index(track)
    preview_action, marker = _preview_track_resolution(preview_section, stream_index)
    source = str(marker.get("source") or "")
    field = str(marker.get("field") or "")
    if preview_action == "drop":
        resolved_source = source if source in {"file_override", "folder_override"} else "pipeline_policy"
        reason = "Audio selector policy drops this detected audio track." if field else "Saved audio policy does not select this detected audio track."
        return _resolved_row(
            kind="audio",
            track=track,
            action="drop",
            source=resolved_source,
            field=field,
            label=_resolved_label("drop", resolved_source),
            reason=reason,
        )
    if preview_action == "keep" and source in {"file_override", "folder_override"} and field:
        return _resolved_row(
            kind="audio",
            track=track,
            action="keep",
            source=source,
            field=field,
            label=_resolved_label("keep", source),
            reason="Exact or language audio selector retains this detected audio track.",
        )
    return _resolved_row(
        kind="audio",
        track=track,
        action="keep",
        source="pipeline_policy",
        field="audio.savedPolicy",
        label="Resolved: use saved audio policy",
        reason="No file or folder audio selector changes this track; saved audio policy remains in effect.",
    )


def _resolved_subtitle_action(
    track: Mapping[str, Any],
    preview_section: Mapping[str, Any],
    settings: Mapping[str, Any],
    inherited_source: str,
) -> dict[str, Any]:
    stream_index = _track_stream_index(track)
    preview_action, marker = _preview_track_resolution(preview_section, stream_index)
    source = str(marker.get("source") or "")
    field = str(marker.get("field") or "")
    if preview_action == "burn":
        return _resolved_row(
            kind="subtitle",
            track=track,
            action="burn",
            source=source or "file_override",
            field=field or "subtitles.burnTrack",
            label=_resolved_label("burn", source or "file_override", policy_label="subtitle burn override"),
            reason="File override renders this exact subtitle stream into video pixels and drops all selectable output subtitle streams.",
        )

    allowed, language_field, language_reason = _subtitle_language_policy_allows(track, settings)
    if not allowed:
        source = inherited_source if inherited_source in {"library", "global_default"} else "pipeline_policy"
        return _resolved_row(
            kind="subtitle",
            track=track,
            action="drop",
            source=source,
            field=language_field,
            label="Resolved: drop by normal subtitle policy",
            reason=language_reason,
        )

    if preview_action == "drop":
        resolved_source = source if source in {"file_override", "folder_override"} else "pipeline_policy"
        reason = "Subtitle selector policy drops this retained subtitle track." if field else "Normal subtitle policy drops this subtitle track."
        return _resolved_row(
            kind="subtitle",
            track=track,
            action="drop",
            source=resolved_source,
            field=field,
            label=_resolved_label("drop", resolved_source, policy_label="normal subtitle policy"),
            reason=reason,
        )

    action, action_source, action_field, label, reason = _subtitle_codec_resolution(track, settings, marker)
    return _resolved_row(
        kind="subtitle",
        track=track,
        action=action,
        source=action_source,
        field=action_field,
        label=label,
        reason=reason,
    )


def _resolved_track_actions(
    *,
    track_metadata: Mapping[str, Any],
    track_selection: Mapping[str, Any],
    library_effective_settings: Mapping[str, Any],
    inherited_source: str,
) -> dict[str, Any]:
    if not track_metadata.get("available"):
        warnings = list(track_metadata.get("warnings") or [])
        unavailable = {"available": False, "tracks": [], "warnings": warnings}
        return {"audio": dict(unavailable), "subtitles": dict(unavailable)}

    audio_preview = _mapping(track_selection.get("audio"))
    subtitle_preview = _mapping(track_selection.get("subtitles"))
    settings = _mapping(library_effective_settings)
    audio_rows = [
        _resolved_audio_action(_mapping(track), audio_preview)
        for track in track_metadata.get("audio_tracks") or []
        if isinstance(track, Mapping)
    ]
    subtitle_rows = [
        _resolved_subtitle_action(_mapping(track), subtitle_preview, settings, inherited_source)
        for track in track_metadata.get("subtitle_tracks") or []
        if isinstance(track, Mapping)
    ]
    return {
        "audio": {
            "available": True,
            "tracks":    audio_rows,
            "warnings":  list(audio_preview.get("warnings") or []),
        },
        "subtitles": {
            "available": True,
            "tracks":    subtitle_rows,
            "warnings":  list(subtitle_preview.get("warnings") or []),
        },
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
        selector_path = field_path if selector_index < 0 else f"{field_path}[{selector_index}]"
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
        if section_name == "subtitles":
            selector = section.get("burnTrack")
            if isinstance(selector, Mapping) and _selector_exact_stream_index(selector) is not None:
                selectors.append(("subtitles.burnTrack", -1, selector, kind))
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
