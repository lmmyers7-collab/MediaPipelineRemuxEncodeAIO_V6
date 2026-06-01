"""Adapters that normalize probe metadata into SourceMediaInfo."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.contracts.source_media_models import (
    MediaType,
    SourceCompatibilityPolicy,
    SourceContainerInfo,
    SourceMediaInfo,
    SourceVideoStream,
)
from app.contracts.source_media_derived import build_source_media
from app.contracts.source_media_streams import (
    audio_from_ffprobe_stream,
    audio_from_stream_summary,
    stream_kind,
    subtitle_from_ffprobe_stream,
    subtitle_from_stream_summary,
    video_from_ffprobe_stream,
    video_from_stream_summary,
)
from app.contracts.source_media_values import (
    as_list,
    bool_value,
    float_value,
    int_value,
    mbps_to_bps,
    media_type as normalize_media_type,
    model_or_mapping,
    normalize_codec,
    normalize_text,
    text_value,
)


def source_media_from_mapping(
    data: Mapping[str, Any],
    *,
    source_path: str = "",
    file_size_bytes: int = 0,
    media_type: MediaType = "unknown",
    policy: SourceCompatibilityPolicy | Mapping[str, Any] | None = None,
) -> SourceMediaInfo:
    """Normalize either raw ffprobe JSON or the existing ProbeResult shape."""

    if "probe_ok" in data or ("streams" in data and not isinstance(data.get("format"), Mapping)):
        return source_media_from_probe_result(
            data,
            source_path=source_path,
            file_size_bytes=file_size_bytes,
            media_type=media_type,
            policy=policy,
        )
    return source_media_from_ffprobe(
        data,
        source_path=source_path,
        file_size_bytes=file_size_bytes,
        media_type=media_type,
        policy=policy,
    )


def source_media_from_probe_result(
    probe_result: Any,
    *,
    source_path: str = "",
    source_id: str = "",
    file_size_bytes: int = 0,
    media_type: MediaType = "unknown",
    policy: SourceCompatibilityPolicy | Mapping[str, Any] | None = None,
) -> SourceMediaInfo:
    """Adapt the existing stage ProbeResult/StreamSummary shape."""

    data = model_or_mapping(probe_result)
    stream_rows = [model_or_mapping(row) for row in as_list(data.get("streams"))]
    videos = [
        video_from_stream_summary(row, fallback_bitrate_mbps=float_value(data.get("estimated_bitrate_mbps")))
        for row in stream_rows
        if stream_kind(row) == "video"
    ]
    if not videos and normalize_codec(data.get("video_codec")) != "unknown":
        videos.append(
            SourceVideoStream(
                stream_index=0,
                codec=normalize_codec(data.get("video_codec")),
                width=int_value(data.get("width")),
                height=int_value(data.get("height")),
                display_width=int_value(data.get("width")),
                display_height=int_value(data.get("height")),
                is_hdr=bool_value(data.get("is_hdr")),
                hdr_format=normalize_text(data.get("color_transfer")),
                bitrate_bps=mbps_to_bps(float_value(data.get("estimated_bitrate_mbps"))),
            )
        )
    audio = [audio_from_stream_summary(row) for row in stream_rows if stream_kind(row) == "audio"]
    subtitles = [subtitle_from_stream_summary(row) for row in stream_rows if stream_kind(row) == "subtitle"]
    container = SourceContainerInfo(
        path=source_path,
        source_id=source_id or source_path,
        file_size_bytes=file_size_bytes or int_value(data.get("size_bytes")),
        format_name=normalize_text(data.get("container")),
        duration_seconds=float_value(data.get("duration_seconds")),
        overall_bitrate_bps=int_value(data.get("bitrate_bps")),
        media_type=media_type,
    )
    return build_source_media(container, videos, audio, subtitles, policy)


def source_media_from_ffprobe(
    ffprobe_json: Mapping[str, Any],
    *,
    source_path: str = "",
    source_id: str = "",
    file_size_bytes: int = 0,
    media_type: MediaType = "unknown",
    policy: SourceCompatibilityPolicy | Mapping[str, Any] | None = None,
) -> SourceMediaInfo:
    """Normalize raw ffprobe-style JSON plus optional fixture source metadata."""

    raw = dict(ffprobe_json.get("ffprobe") or ffprobe_json)
    source = model_or_mapping(ffprobe_json.get("source", {}))
    if "ffprobe" in ffprobe_json:
        source = {**model_or_mapping(raw.get("source", {})), **source}
    format_info = model_or_mapping(raw.get("format", {}))
    streams = [model_or_mapping(row) for row in as_list(raw.get("streams"))]

    path = source_path or text_value(source.get("path"))
    source_size = file_size_bytes or int_value(source.get("file_size_bytes")) or int_value(format_info.get("size"))
    media_kind = normalize_media_type(media_type if media_type != "unknown" else source.get("media_type"))
    container = SourceContainerInfo(
        path=path,
        source_id=source_id or text_value(source.get("source_id")) or path,
        file_size_bytes=source_size,
        format_name=normalize_text(format_info.get("format_name")),
        duration_seconds=float_value(format_info.get("duration")),
        overall_bitrate_bps=int_value(format_info.get("bit_rate")),
        title=text_value(model_or_mapping(format_info.get("tags", {})).get("title")),
        media_type=media_kind,
    )
    videos = [video_from_ffprobe_stream(row) for row in streams if stream_kind(row) == "video"]
    audio = [audio_from_ffprobe_stream(row) for row in streams if stream_kind(row) == "audio"]
    subtitles = [subtitle_from_ffprobe_stream(row) for row in streams if stream_kind(row) == "subtitle"]
    return build_source_media(container, videos, audio, subtitles, policy)


__all__ = [
    "source_media_from_mapping",
    "source_media_from_probe_result",
    "source_media_from_ffprobe",
]
