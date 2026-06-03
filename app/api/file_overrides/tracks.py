from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any

from app.contracts.source_media import SourceAudioStream, SourceSubtitleStream, source_media_from_probe_result
from app.contracts.stages import ProbeResult
from app.orchestration.runner import RunnerOptions, run_probe_stage as _default_run_probe_stage
from app.queue.file_overrides import normalize_file_override_path

from .results import TRACKS_COMMAND, TRACKS_SCHEMA_VERSION


TRACKS_PROBE_TIMEOUT_SECONDS = 55.0
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


def _run_probe_stage_compat(payload: dict[str, Any], options: RunnerOptions):
    legacy_module = sys.modules.get("app.api.commands_file_overrides")
    runner = getattr(legacy_module, "run_probe_stage", None) if legacy_module is not None else None
    return (runner or _default_run_probe_stage)(payload, options)


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

    result = _run_probe_stage_compat(
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
