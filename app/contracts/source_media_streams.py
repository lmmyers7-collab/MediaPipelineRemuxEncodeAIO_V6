"""Stream-level builders for SourceMediaInfo adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.contracts.source_media import (
    HDR_COLOR_TRANSFERS,
    IMAGE_SUBTITLE_CODECS,
    TEXT_SUBTITLE_CODECS,
    SourceAudioStream,
    SourceSubtitleStream,
    SourceVideoStream,
    SubtitleKind,
)
from app.contracts.source_media_values import (
    as_list,
    bool_flag,
    bool_value,
    float_value,
    frame_rate,
    int_value,
    mbps_to_bps,
    model_or_mapping,
    normalize_codec,
    normalize_text,
    ratio,
    ratio_text,
    scan_type,
    text_value,
)


def stream_kind(stream: Mapping[str, Any]) -> str:
    return normalize_text(stream.get("kind") or stream.get("codec_type") or "data")


def video_from_ffprobe_stream(stream: Mapping[str, Any]) -> SourceVideoStream:
    width = int_value(stream.get("width"))
    height = int_value(stream.get("height"))
    display_width, display_height, aspect = display_dimensions(stream, width, height)
    transfer = normalize_text(stream.get("color_transfer"))
    side_data = as_list(stream.get("side_data_list"))
    is_hdr = transfer in HDR_COLOR_TRANSFERS or any("mastering display" in text_value(item).lower() for item in side_data)
    return SourceVideoStream(
        stream_index=int_value(stream.get("index")),
        codec=normalize_codec(stream.get("codec_name")),
        codec_profile=text_value(stream.get("profile")),
        level=text_value(stream.get("level")),
        pixel_format=normalize_text(stream.get("pix_fmt")),
        width=width,
        height=height,
        display_width=display_width,
        display_height=display_height,
        aspect_ratio=aspect,
        frame_rate=frame_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate")),
        scan_type=scan_type(stream.get("field_order")),
        is_hdr=is_hdr,
        hdr_format=transfer,
        bit_depth=bit_depth(stream),
        bitrate_bps=int_value(stream.get("bit_rate")),
    )


def video_from_stream_summary(stream: Mapping[str, Any], *, fallback_bitrate_mbps: float = 0.0) -> SourceVideoStream:
    width = int_value(stream.get("width"))
    height = int_value(stream.get("height"))
    bitrate_bps = int_value(stream.get("bitrate_bps")) or int_value(stream.get("bit_rate"))
    return SourceVideoStream(
        stream_index=int_value(stream.get("index") or stream.get("stream_index")),
        codec=normalize_codec(stream.get("codec") or stream.get("codec_name")),
        width=width,
        height=height,
        display_width=width,
        display_height=height,
        bitrate_bps=bitrate_bps or mbps_to_bps(fallback_bitrate_mbps),
    )


def audio_from_ffprobe_stream(stream: Mapping[str, Any]) -> SourceAudioStream:
    tags = model_or_mapping(stream.get("tags", {}))
    disposition = model_or_mapping(stream.get("disposition", {}))
    return SourceAudioStream(
        stream_index=int_value(stream.get("index")),
        codec=normalize_codec(stream.get("codec_name")),
        channels=int_value(stream.get("channels")),
        channel_layout=normalize_text(stream.get("channel_layout")),
        language=normalize_text(tags.get("language")),
        bitrate_bps=int_value(stream.get("bit_rate")),
        default=bool_flag(disposition.get("default")),
        forced=bool_flag(disposition.get("forced")),
        title=text_value(tags.get("title")),
    )


def audio_from_stream_summary(stream: Mapping[str, Any]) -> SourceAudioStream:
    return SourceAudioStream(
        stream_index=int_value(stream.get("index") or stream.get("stream_index")),
        codec=normalize_codec(stream.get("codec") or stream.get("codec_name")),
        channels=int_value(stream.get("channels")),
        language=normalize_text(stream.get("language")),
        bitrate_bps=int_value(stream.get("bitrate_bps") or stream.get("bit_rate")),
        default=bool_value(stream.get("default")),
        forced=bool_value(stream.get("forced")),
        title=text_value(stream.get("title")),
    )


def subtitle_from_ffprobe_stream(stream: Mapping[str, Any]) -> SourceSubtitleStream:
    tags = model_or_mapping(stream.get("tags", {}))
    disposition = model_or_mapping(stream.get("disposition", {}))
    return subtitle_stream(
        index=int_value(stream.get("index")),
        codec=normalize_codec(stream.get("codec_name")),
        language=normalize_text(tags.get("language")),
        default=bool_flag(disposition.get("default")),
        forced=bool_flag(disposition.get("forced")),
        title=text_value(tags.get("title")),
    )


def subtitle_from_stream_summary(stream: Mapping[str, Any]) -> SourceSubtitleStream:
    return subtitle_stream(
        index=int_value(stream.get("index") or stream.get("stream_index")),
        codec=normalize_codec(stream.get("codec") or stream.get("codec_name")),
        language=normalize_text(stream.get("language")),
        default=bool_value(stream.get("default")),
        forced=bool_value(stream.get("forced")),
        title=text_value(stream.get("title")),
    )


def subtitle_stream(
    *,
    index: int,
    codec: str,
    language: str,
    default: bool,
    forced: bool,
    title: str,
) -> SourceSubtitleStream:
    kind = subtitle_kind(codec)
    text_based = kind == "text"
    image_based = kind == "image"
    return SourceSubtitleStream(
        stream_index=index,
        codec=codec,
        language=language,
        default=default,
        forced=forced,
        title=title,
        subtitle_kind=kind,
        image_based=image_based,
        text_based=text_based,
        passthrough_candidate=kind in ("text", "image"),
        convert_candidate=(text_based and codec not in {"subrip", "srt"}) or image_based,
        burn_candidate=image_based,
    )


def display_dimensions(stream: Mapping[str, Any], width: int, height: int) -> tuple[int, int, str]:
    aspect = text_value(stream.get("display_aspect_ratio"))
    if width <= 0 or height <= 0:
        return width, height, aspect
    display_ratio = ratio(aspect)
    if display_ratio <= 0:
        sample_ratio = ratio(text_value(stream.get("sample_aspect_ratio")))
        if sample_ratio > 0:
            display_ratio = (width * sample_ratio) / height
    if display_ratio > 0 and abs((width / height) - display_ratio) > 0.01:
        return int(round(height * display_ratio)), height, aspect or ratio_text(display_ratio)
    return width, height, aspect or ratio_text(width / height)


def bit_depth(stream: Mapping[str, Any]) -> int:
    explicit = int_value(stream.get("bits_per_raw_sample") or stream.get("bits_per_sample"))
    if explicit > 0:
        return explicit
    pix_fmt = normalize_text(stream.get("pix_fmt"))
    if "p16" in pix_fmt:
        return 16
    if "p12" in pix_fmt:
        return 12
    if "p10" in pix_fmt:
        return 10
    if pix_fmt:
        return 8
    return 0


def subtitle_kind(codec: str) -> SubtitleKind:
    normalized = normalize_codec(codec)
    if normalized in TEXT_SUBTITLE_CODECS:
        return "text"
    if normalized in IMAGE_SUBTITLE_CODECS:
        return "image"
    return "unknown"


__all__ = [
    "stream_kind",
    "video_from_ffprobe_stream",
    "video_from_stream_summary",
    "audio_from_ffprobe_stream",
    "audio_from_stream_summary",
    "subtitle_from_ffprobe_stream",
    "subtitle_from_stream_summary",
]
