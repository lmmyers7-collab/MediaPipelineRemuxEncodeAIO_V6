"""Derived read-only source facts for SourceMediaInfo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.contracts.source_media_models import (
    BitrateBucket,
    DimensionBucket,
    SourceAudioStream,
    SourceCompatibilityPolicy,
    SourceContainerInfo,
    SourceDerivedFacts,
    SourceMediaInfo,
    SourceSubtitleStream,
    SourceVideoStream,
)
from app.contracts.source_media_values import normalize_codec, normalize_text


def build_source_media(
    container: SourceContainerInfo,
    videos: list[SourceVideoStream],
    audio: list[SourceAudioStream],
    subtitles: list[SourceSubtitleStream],
    policy: SourceCompatibilityPolicy | Mapping[str, Any] | None,
) -> SourceMediaInfo:
    typed_policy = normalize_policy(policy)
    annotated_audio = [
        stream.model_copy(
            update={"passthrough_safe": normalize_codec(stream.codec) in typed_policy.audio_passthrough_codecs}
        )
        for stream in audio
    ]
    derived = derive_facts(container, videos, annotated_audio, subtitles, typed_policy)
    return SourceMediaInfo(
        container=container,
        video_streams=videos,
        audio_streams=annotated_audio,
        subtitle_streams=subtitles,
        derived=derived,
    )


def derive_facts(
    container: SourceContainerInfo,
    videos: list[SourceVideoStream],
    audio: list[SourceAudioStream],
    subtitles: list[SourceSubtitleStream],
    policy: SourceCompatibilityPolicy,
) -> SourceDerivedFacts:
    primary = videos[0] if videos else None
    estimated_bitrate_mbps = estimated_bitrate_mbps_for(container, primary)
    codec_allowed = None
    remux_compatible = None
    if primary is not None:
        codec = normalize_codec(primary.codec)
        codec_allowed = codec in policy.direct_play_video_codecs and (
            policy.max_direct_play_height <= 0 or primary.height <= policy.max_direct_play_height
        )
        container_ok = format_matches(container.format_name, policy.remux_container_formats)
        remux_codec_ok = codec in policy.remux_safe_video_codecs
        h264_ok = (
            codec == "h264"
            and policy.allow_h264_direct_copy
            and (policy.h264_direct_copy_max_height <= 0 or primary.height <= policy.h264_direct_copy_max_height)
            and (
                policy.h264_direct_copy_max_bitrate_mbps <= 0
                or (estimated_bitrate_mbps > 0 and estimated_bitrate_mbps <= policy.h264_direct_copy_max_bitrate_mbps)
            )
        )
        remux_compatible = bool(container_ok and (remux_codec_ok or h264_ok))

    audio_safe = None if not audio else all(stream.passthrough_safe is True for stream in audio)
    return SourceDerivedFacts(
        primary_video_codec_allowed=codec_allowed,
        audio_passthrough_safe=audio_safe,
        subtitle_passthrough_candidates=[stream.stream_index for stream in subtitles if stream.passthrough_candidate],
        subtitle_convert_candidates=[stream.stream_index for stream in subtitles if stream.convert_candidate],
        subtitle_burn_candidates=[stream.stream_index for stream in subtitles if stream.burn_candidate],
        dimensions_bucket=dimension_bucket(primary.height if primary else 0),
        bitrate_bucket=bitrate_bucket(estimated_bitrate_mbps),
        already_remux_compatible=remux_compatible,
        unknown_metadata=unknown_metadata(container, primary),
    )


def normalize_policy(value: SourceCompatibilityPolicy | Mapping[str, Any] | None) -> SourceCompatibilityPolicy:
    if isinstance(value, SourceCompatibilityPolicy):
        policy = value
    elif value is None:
        policy = SourceCompatibilityPolicy()
    else:
        policy = SourceCompatibilityPolicy.model_validate(value)
    return policy.model_copy(
        update={
            "direct_play_video_codecs": [normalize_codec(item) for item in policy.direct_play_video_codecs],
            "remux_safe_video_codecs": [normalize_codec(item) for item in policy.remux_safe_video_codecs],
            "audio_passthrough_codecs": [normalize_codec(item) for item in policy.audio_passthrough_codecs],
            "remux_container_formats": [normalize_text(item) for item in policy.remux_container_formats],
        }
    )


def unknown_metadata(container: SourceContainerInfo, primary: SourceVideoStream | None) -> list[str]:
    missing: list[str] = []
    if not container.format_name:
        missing.append("container.format_name")
    if container.duration_seconds <= 0:
        missing.append("container.duration_seconds")
    if container.file_size_bytes <= 0:
        missing.append("container.file_size_bytes")
    if container.overall_bitrate_bps <= 0 and (primary is None or primary.bitrate_bps <= 0):
        missing.append("container.overall_bitrate_bps")
    if primary is None:
        missing.append("video_streams")
    else:
        if primary.codec == "unknown":
            missing.append("video.codec")
        if primary.width <= 0 or primary.height <= 0:
            missing.append("video.dimensions")
    return missing


def estimated_bitrate_mbps_for(container: SourceContainerInfo, primary: SourceVideoStream | None) -> float:
    if primary and primary.bitrate_bps > 0:
        return primary.bitrate_bps / 1_000_000.0
    if container.overall_bitrate_bps > 0:
        return container.overall_bitrate_bps / 1_000_000.0
    if container.file_size_bytes > 0 and container.duration_seconds > 0:
        return (container.file_size_bytes * 8.0) / container.duration_seconds / 1_000_000.0
    return 0.0


def format_matches(format_name: str, allowed: Sequence[str]) -> bool:
    parts = {normalize_text(part) for part in format_name.replace(";", ",").split(",") if part.strip()}
    if not parts and format_name:
        parts = {normalize_text(format_name)}
    return any(allowed_part in parts or allowed_part in format_name for allowed_part in allowed)


def dimension_bucket(height: int) -> DimensionBucket:
    if height <= 0:
        return "unknown"
    if height >= 4320:
        return "8k"
    if height >= 2160:
        return "4k"
    if height >= 1440:
        return "1440p"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    if height >= 480:
        return "480p"
    return "sd"


def bitrate_bucket(mbps: float) -> BitrateBucket:
    if mbps <= 0:
        return "unknown"
    if mbps < 10:
        return "low"
    if mbps < 20:
        return "medium"
    if mbps < 35:
        return "high"
    return "very_high"


__all__ = ["build_source_media", "derive_facts"]
