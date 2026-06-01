"""Pure effective-decision policy contract shared by config and decide."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.verification import OutputSizeCheckAction, output_size_check_action_from_settings

RoutingProfile = Literal["plex_direct_stream", "plex_direct_play", "archive_shrink", "archive_quality", "manual"]
RouteThresholdMode = Literal["compatibility_advisory", "size", "bitrate", "size_or_bitrate"]
SizeGuardMode = Literal["advisory", "strict", "off"]
ResolutionLimit = Literal["source", "480p", "720p", "1080p", "2160p", "custom"]
ScalingPolicy = Literal["never_upscale", "allow_upscale", "preserve_source"]
VideoTargetMode = Literal["auto", "constant_quality", "average_bitrate", "max_bitrate"]
SubtitleMode = Literal["keep", "drop", "convert_preferred", "burn_forced"]


def _normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalized_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_normalized_text(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalized_text(item) for item in value if _normalized_text(item)]
    text = _normalized_text(value)
    return [text] if text else []


class DecisionPolicyModel(BaseModel):
    """Strict base for pure decision policy contracts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EffectiveDecisionPolicy(DecisionPolicyModel):
    """Abstract effective settings consumed by the decision engine."""

    routing_profile: RoutingProfile = "plex_direct_stream"
    route_threshold_mode: RouteThresholdMode = "compatibility_advisory"
    size_guard_mode: SizeGuardMode = "advisory"
    output_size_check_action: OutputSizeCheckAction | None = None
    quality_encode_growth_tolerance_percent: float = Field(default=5.0, ge=0)
    compatibility_encode_growth_tolerance_percent: float = Field(default=15.0, ge=0)
    movie_route_size_limit_gb: float = Field(default=8.0, ge=0)
    tv_route_size_limit_gb: float = Field(default=3.0, ge=0)
    movie_direct_copy_max_bitrate_mbps: float = Field(default=35.0, ge=0)
    tv_direct_copy_max_bitrate_mbps: float = Field(default=18.0, ge=0)
    allow_h264_compatible_direct_copy: bool = True
    h264_direct_copy_max_bitrate_mbps: float = Field(default=35.0, ge=0)
    h264_direct_copy_max_height: int = Field(default=1080, ge=0)
    max_direct_copy_height: int = Field(default=2160, ge=0)
    output_container: Literal["mkv", "mp4"] = "mkv"
    force_container_remux: bool = True
    direct_copy_video_codecs: list[str] = Field(default_factory=lambda: ["hevc", "h265", "h.265"])
    mp4_audio_copy_codecs: list[str] = Field(default_factory=lambda: ["aac", "ac3", "eac3", "mp3", "alac"])
    mp4_subtitle_copy_codecs: list[str] = Field(default_factory=lambda: ["mov_text", "tx3g"])
    resolution_limit: ResolutionLimit = "source"
    custom_max_height: int | None = Field(default=None, ge=1)
    scaling_policy: ScalingPolicy = "never_upscale"
    crop_mode: Literal["off", "auto", "custom"] = "off"
    video_filter_names: list[str] = Field(default_factory=list)
    video_output_codec: str = "hevc_nvenc"
    video_codec_family: str = "hevc"
    video_encoder_backend: str = "nvenc"
    video_target_mode: VideoTargetMode = "auto"
    video_quality_target: int | None = Field(default=22, ge=0)
    video_target_bitrate_mbps: float | None = Field(default=None, gt=0)
    video_max_bitrate_mbps: float | None = Field(default=None, gt=0)
    audio_passthrough_profile: str = "plex_balanced"
    audio_passthrough_codecs: list[str] = Field(
        default_factory=lambda: ["aac", "ac3", "eac3", "mp3", "opus", "vorbis", "truehd", "mlp"]
    )
    audio_transcode_codec: str = "eac3"
    audio_max_channels: int = Field(default=6, ge=1, le=16)
    audio_force_transcode: bool = False
    subtitle_mode: SubtitleMode = "keep"
    subtitle_burn_in_forced: bool = False

    @field_validator(
        "direct_copy_video_codecs",
        "mp4_audio_copy_codecs",
        "mp4_subtitle_copy_codecs",
        "video_filter_names",
        "audio_passthrough_codecs",
        mode="before",
    )
    @classmethod
    def _coerce_list(cls, value: Any) -> list[str]:
        return _normalized_list(value)

    @model_validator(mode="after")
    def _default_output_size_check_action(self) -> "EffectiveDecisionPolicy":
        if self.output_size_check_action is None:
            self.output_size_check_action = output_size_check_action_from_settings(self.size_guard_mode)
        return self


__all__ = [
    "DecisionPolicyModel",
    "EffectiveDecisionPolicy",
    "ResolutionLimit",
    "RouteThresholdMode",
    "RoutingProfile",
    "ScalingPolicy",
    "SizeGuardMode",
    "SubtitleMode",
    "VideoTargetMode",
]
