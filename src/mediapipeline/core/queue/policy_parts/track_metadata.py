"""Queue preview stream and track metadata helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .row_identity import _bool_value

def _mapping_value(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            dumped = dump(mode="json")
        except TypeError:
            dumped = dump()
        return dumped if isinstance(dumped, Mapping) else {}
    if hasattr(value, "__dict__"):
        data = vars(value)
        return data if isinstance(data, Mapping) else {}
    return {}

def _list_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []

def _int_metadata_value(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0

def _track_language_value(value: Any) -> str:
    language = str(value or "").strip().casefold()
    return language

def _track_language_list(value: Any) -> list[str]:
    languages: list[str] = []
    seen: set[str] = set()
    for item in _list_value(value):
        language = _track_language_value(item)
        if language and language not in seen:
            languages.append(language)
            seen.add(language)
    return languages

def _stream_language(row: Mapping[str, Any]) -> str:
    tags = _mapping_value(row.get("tags"))
    return _track_language_value(row.get("language") or row.get("lang") or tags.get("language"))

def _stream_forced(row: Mapping[str, Any]) -> bool:
    if "forced" in row:
        return _bool_value(row.get("forced"))
    disposition = _mapping_value(row.get("disposition"))
    return _bool_value(disposition.get("forced"))

def _stream_kind(row: Mapping[str, Any], fallback: str = "") -> str:
    value = str(row.get("kind") or row.get("codec_type") or row.get("stream_type") or row.get("type") or fallback)
    kind = value.strip().casefold()
    if kind in {"subtitles", "subtitle_stream", "s"}:
        return "subtitle"
    if kind in {"audio_stream", "a"}:
        return "audio"
    return kind

def _append_track_rows(target: list[Mapping[str, Any]], value: Any, *, fallback_kind: str = "") -> bool:
    rows = _list_value(value)
    for item in rows:
        row = _mapping_value(item)
        if row and (fallback_kind or _stream_kind(row) in {"audio", "subtitle"}):
            target.append(row if not fallback_kind else {**dict(row), "_queue_track_kind": fallback_kind})
    return isinstance(value, (list, tuple))

def _embedded_track_rows(raw_row: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], bool]:
    rows: list[Mapping[str, Any]] = []
    metadata_present = False
    metadata_present = _append_track_rows(rows, raw_row.get("streams")) or metadata_present
    metadata_present = _append_track_rows(rows, raw_row.get("probe_streams")) or metadata_present

    for key in ("probe", "probe_result", "source_media", "source_media_info", "source_media_profile", "ffprobe"):
        nested = _mapping_value(raw_row.get(key))
        if not nested:
            continue
        metadata_present = _append_track_rows(rows, nested.get("streams")) or metadata_present
        metadata_present = _append_track_rows(rows, nested.get("audio_streams"), fallback_kind="audio") or metadata_present
        metadata_present = _append_track_rows(rows, nested.get("subtitle_streams"), fallback_kind="subtitle") or metadata_present
        metadata_present = _append_track_rows(rows, nested.get("audio_tracks"), fallback_kind="audio") or metadata_present
        metadata_present = _append_track_rows(rows, nested.get("subtitle_tracks"), fallback_kind="subtitle") or metadata_present

    metadata_present = _append_track_rows(rows, raw_row.get("audio_streams"), fallback_kind="audio") or metadata_present
    metadata_present = _append_track_rows(rows, raw_row.get("subtitle_streams"), fallback_kind="subtitle") or metadata_present
    metadata_present = _append_track_rows(rows, raw_row.get("audio_tracks"), fallback_kind="audio") or metadata_present
    metadata_present = _append_track_rows(rows, raw_row.get("subtitle_tracks"), fallback_kind="subtitle") or metadata_present

    audio = [row for row in rows if _stream_kind(row, str(row.get("_queue_track_kind") or "")) == "audio"]
    subtitles = [row for row in rows if _stream_kind(row, str(row.get("_queue_track_kind") or "")) == "subtitle"]
    return audio, subtitles, metadata_present

def _track_metadata_summary_from_fields(raw_row: Mapping[str, Any]) -> dict[str, Any] | None:
    summary_keys = {
        "audio_track_count",
        "subtitle_track_count",
        "audio_languages",
        "subtitle_languages",
        "has_forced_subtitles",
    }
    if "track_metadata_available" in raw_row and not _bool_value(raw_row.get("track_metadata_available")):
        return {"track_metadata_available": False}
    if "probe_available" in raw_row and not _bool_value(raw_row.get("probe_available")):
        return {"track_metadata_available": False}
    if "track_metadata_available" not in raw_row and not any(key in raw_row for key in summary_keys):
        return None
    return {
        "track_metadata_available": True,
        "audio_track_count": _int_metadata_value(raw_row.get("audio_track_count")),
        "subtitle_track_count": _int_metadata_value(raw_row.get("subtitle_track_count")),
        "audio_languages": _track_language_list(raw_row.get("audio_languages")),
        "subtitle_languages": _track_language_list(raw_row.get("subtitle_languages")),
        "has_forced_subtitles": _bool_value(raw_row.get("has_forced_subtitles")),
    }

def queue_preview_track_metadata_summary(raw_row: Mapping[str, Any]) -> dict[str, Any]:
    field_summary = _track_metadata_summary_from_fields(raw_row)
    if field_summary is not None:
        return field_summary

    audio, subtitles, metadata_present = _embedded_track_rows(raw_row)
    if not metadata_present:
        return {"track_metadata_available": False}

    return {
        "track_metadata_available": True,
        "audio_track_count": len(audio),
        "subtitle_track_count": len(subtitles),
        "audio_languages": _track_language_list([_stream_language(row) for row in audio]),
        "subtitle_languages": _track_language_list([_stream_language(row) for row in subtitles]),
        "has_forced_subtitles": any(_stream_forced(row) for row in subtitles),
    }
