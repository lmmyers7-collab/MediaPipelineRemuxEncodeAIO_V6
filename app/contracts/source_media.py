"""Normalized read-only source media facts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SOURCE_MEDIA_SCHEMA_VERSION: Literal["source_media.v1"] = "source_media.v1"

MediaType = Literal["movie", "tv", "unknown"]
DimensionBucket = Literal["unknown", "sd", "480p", "720p", "1080p", "1440p", "4k", "8k"]
BitrateBucket = Literal["unknown", "low", "medium", "high", "very_high"]
ScanType = Literal["progressive", "interlaced", "unknown"]
SubtitleKind = Literal["text", "image", "unknown"]

HDR_COLOR_TRANSFERS: frozenset[str] = frozenset({"smpte2084", "arib-std-b67"})
TEXT_SUBTITLE_CODECS: frozenset[str] = frozenset(
    {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}
)
IMAGE_SUBTITLE_CODECS: frozenset[str] = frozenset(
    {"hdmv_pgs_subtitle", "pgs", "dvd_subtitle", "dvdsub", "vobsub", "xsub"}
)


def _policy_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


class SourceMediaModel(BaseModel):
    """Strict base for normalized source-media contracts."""

    model_config = ConfigDict(extra="forbid")


class SourceCompatibilityPolicy(SourceMediaModel):
    """Policy inputs used only to annotate source facts, not to choose a route."""

    direct_play_video_codecs: list[str] = Field(default_factory=lambda: ["h264", "hevc", "h265"])
    remux_safe_video_codecs: list[str] = Field(default_factory=lambda: ["hevc", "h265", "h.265"])
    audio_passthrough_codecs: list[str] = Field(
        default_factory=lambda: ["aac", "ac3", "eac3", "mp3", "opus", "vorbis", "truehd", "mlp"]
    )
    remux_container_formats: list[str] = Field(default_factory=lambda: ["matroska", "mkv", "mp4"])
    allow_h264_direct_copy: bool = True
    h264_direct_copy_max_bitrate_mbps: float = Field(default=35.0, ge=0)
    h264_direct_copy_max_height: int = Field(default=1080, ge=0)
    max_direct_play_height: int = Field(default=2160, ge=0)

    @field_validator(
        "direct_play_video_codecs",
        "remux_safe_video_codecs",
        "audio_passthrough_codecs",
        "remux_container_formats",
        mode="before",
    )
    @classmethod
    def _coerce_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [_policy_text(value)]
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [_policy_text(item) for item in value]
        return [_policy_text(value)]


class SourceContainerInfo(SourceMediaModel):
    path: str = ""
    source_id: str = ""
    file_size_bytes: int = Field(default=0, ge=0)
    format_name: str = ""
    duration_seconds: float = Field(default=0.0, ge=0)
    overall_bitrate_bps: int = Field(default=0, ge=0)
    title: str = ""
    media_type: MediaType = "unknown"


class SourceVideoStream(SourceMediaModel):
    stream_index: int = Field(default=0, ge=0)
    codec: str = "unknown"
    codec_profile: str = ""
    level: str = ""
    pixel_format: str = ""
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    display_width: int = Field(default=0, ge=0)
    display_height: int = Field(default=0, ge=0)
    aspect_ratio: str = ""
    frame_rate: float = Field(default=0.0, ge=0)
    scan_type: ScanType = "unknown"
    is_hdr: bool = False
    hdr_format: str = ""
    bit_depth: int = Field(default=0, ge=0)
    bitrate_bps: int = Field(default=0, ge=0)


class SourceAudioStream(SourceMediaModel):
    stream_index: int = Field(default=0, ge=0)
    codec: str = "unknown"
    channels: int = Field(default=0, ge=0)
    channel_layout: str = ""
    language: str = ""
    bitrate_bps: int = Field(default=0, ge=0)
    default: bool = False
    forced: bool = False
    title: str = ""
    passthrough_safe: bool | None = None


class SourceSubtitleStream(SourceMediaModel):
    stream_index: int = Field(default=0, ge=0)
    codec: str = "unknown"
    language: str = ""
    default: bool = False
    forced: bool = False
    title: str = ""
    subtitle_kind: SubtitleKind = "unknown"
    image_based: bool = False
    text_based: bool = False
    passthrough_candidate: bool = False
    convert_candidate: bool = False
    burn_candidate: bool = False
    drop_candidate: bool = True


class SourceDerivedFacts(SourceMediaModel):
    primary_video_codec_allowed: bool | None = None
    audio_passthrough_safe: bool | None = None
    subtitle_passthrough_candidates: list[int] = Field(default_factory=list)
    subtitle_convert_candidates: list[int] = Field(default_factory=list)
    subtitle_burn_candidates: list[int] = Field(default_factory=list)
    dimensions_bucket: DimensionBucket = "unknown"
    bitrate_bucket: BitrateBucket = "unknown"
    already_remux_compatible: bool | None = None
    unknown_metadata: list[str] = Field(default_factory=list)


class SourceMediaInfo(SourceMediaModel):
    schema_version: Literal["source_media.v1"] = SOURCE_MEDIA_SCHEMA_VERSION
    container: SourceContainerInfo = Field(default_factory=SourceContainerInfo)
    video_streams: list[SourceVideoStream] = Field(default_factory=list)
    audio_streams: list[SourceAudioStream] = Field(default_factory=list)
    subtitle_streams: list[SourceSubtitleStream] = Field(default_factory=list)
    derived: SourceDerivedFacts = Field(default_factory=SourceDerivedFacts)

    @model_validator(mode="after")
    def _source_id_or_path(self) -> SourceMediaInfo:
        if not self.container.source_id and self.container.path:
            self.container.source_id = self.container.path
        return self


from app.contracts.source_media_adapters import (  # noqa: E402
    source_media_from_ffprobe,
    source_media_from_mapping,
    source_media_from_probe_result,
)


__all__ = [
    "SOURCE_MEDIA_SCHEMA_VERSION",
    "MediaType",
    "DimensionBucket",
    "BitrateBucket",
    "ScanType",
    "SubtitleKind",
    "HDR_COLOR_TRANSFERS",
    "TEXT_SUBTITLE_CODECS",
    "IMAGE_SUBTITLE_CODECS",
    "SourceCompatibilityPolicy",
    "SourceContainerInfo",
    "SourceVideoStream",
    "SourceAudioStream",
    "SourceSubtitleStream",
    "SourceDerivedFacts",
    "SourceMediaInfo",
    "source_media_from_mapping",
    "source_media_from_probe_result",
    "source_media_from_ffprobe",
]
