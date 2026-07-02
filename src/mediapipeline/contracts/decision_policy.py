"""Pure effective-decision policy contract shared by config and decide."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from mediapipeline.contracts.height_tolerance import (
    DEFAULT_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT,
    height_tolerance_boundaries,
    legacy_height_tolerance_defaults,
    validate_height_tolerance_boundaries,
)
from mediapipeline.contracts.verification import OutputSizeCheckAction, output_size_check_action_from_settings

RoutingProfile = Literal["plex_direct_stream", "plex_direct_play", "archive_shrink", "archive_quality", "manual"]
RouteThresholdMode = Literal["compatibility_advisory", "size", "bitrate", "size_or_bitrate"]
SizeGuardMode = Literal["advisory", "strict", "fallback_remux", "off"]
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


def _canonical_audio_language(value: str) -> str:
    if value in {"en", "eng", "english"}:
        return "eng"
    return value


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
    movie_route_1080p_size_limit_gb: float = Field(default=8.0, ge=0)
    movie_route_1440p_size_limit_gb: float = Field(default=8.0, ge=0)
    movie_route_4k_size_limit_gb: float = Field(default=8.0, ge=0)
    tv_route_1080p_size_limit_gb: float = Field(default=3.0, ge=0)
    tv_route_1440p_size_limit_gb: float = Field(default=3.0, ge=0)
    tv_route_4k_size_limit_gb: float = Field(default=3.0, ge=0)
    route_1080p_bucket_max_height: int = Field(default=1200, ge=1, le=4320)
    route_1080p_upper_height_tolerance_percent: float = Field(
        default=DEFAULT_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
    )
    route_1080p_max_video_bitrate_mbps: float = Field(default=20.0, gt=0, le=500)
    route_1440p_lower_height_tolerance_percent: float = Field(
        default=DEFAULT_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
    )
    route_1440p_upper_height_tolerance_percent: float = Field(
        default=DEFAULT_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
    )
    route_1440p_max_video_bitrate_mbps: float = Field(default=35.0, gt=0, le=500)
    route_4k_lower_height_tolerance_percent: float = Field(
        default=DEFAULT_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
    )
    route_4k_bucket_min_height: int = Field(default=1800, ge=1, le=4320)
    route_4k_max_video_bitrate_mbps: float = Field(default=35.0, gt=0, le=500)
    allow_h264_compatible_direct_copy: bool = True
    h264_direct_copy_max_bitrate_mbps: float = Field(default=35.0, ge=0)
    h264_direct_copy_max_height: int = Field(default=1080, ge=0)
    max_direct_copy_height: int = Field(default=2160, ge=0)
    output_container: Literal["mkv", "mp4"] = "mkv"
    force_container_remux: bool = True
    direct_copy_video_codecs: list[str] = Field(default_factory=lambda: ["hevc", "h265", "h.265"])
    mp4_audio_copy_codecs: list[str] = Field(default_factory=lambda: ["eac3"])
    mp4_subtitle_copy_codecs: list[str] = Field(default_factory=list)
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
    preferred_default_audio_languages: list[str] = Field(default_factory=lambda: ["eng"])
    audio_transcode_codec: str = "eac3"
    audio_max_channels: int = Field(default=6, ge=1, le=16)
    audio_force_transcode: bool = False
    allow_no_audio: bool = False
    subtitle_mode: SubtitleMode = "keep"
    subtitle_burn_in_forced: bool = False

    @model_validator(mode="before")
    @classmethod
    def _derive_legacy_policy_fields(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        next_value = dict(value)
        next_value.pop("movie_route_size_limit_gb", None)
        next_value.pop("tv_route_size_limit_gb", None)
        next_value.pop("movie_direct_copy_max_bitrate_mbps", None)
        next_value.pop("tv_direct_copy_max_bitrate_mbps", None)
        percent_fields = (
            "route_1080p_upper_height_tolerance_percent",
            "route_1440p_lower_height_tolerance_percent",
            "route_1440p_upper_height_tolerance_percent",
            "route_4k_lower_height_tolerance_percent",
        )
        if any(field in next_value for field in percent_fields):
            return next_value
        if (
            "route_1080p_bucket_max_height" not in next_value
            and "route_4k_bucket_min_height" not in next_value
        ):
            return next_value
        try:
            route_1080p_max_height = int(next_value.get("route_1080p_bucket_max_height", 1200))
            route_4k_min_height = int(next_value.get("route_4k_bucket_min_height", 1800))
        except (TypeError, ValueError):
            return next_value
        legacy_defaults = legacy_height_tolerance_defaults(
            route_1080p_bucket_max_height=route_1080p_max_height,
            route_4k_bucket_min_height=route_4k_min_height,
        )
        next_value["route_1080p_upper_height_tolerance_percent"] = legacy_defaults[
            "Route1080pUpperHeightTolerancePercent"
        ]
        next_value["route_1440p_lower_height_tolerance_percent"] = legacy_defaults[
            "Route1440pLowerHeightTolerancePercent"
        ]
        next_value["route_1440p_upper_height_tolerance_percent"] = legacy_defaults[
            "Route1440pUpperHeightTolerancePercent"
        ]
        next_value["route_4k_lower_height_tolerance_percent"] = legacy_defaults[
            "Route4KLowerHeightTolerancePercent"
        ]
        return next_value

    @field_validator(
        "direct_copy_video_codecs",
        "mp4_audio_copy_codecs",
        "mp4_subtitle_copy_codecs",
        "video_filter_names",
        "audio_passthrough_codecs",
        "preferred_default_audio_languages",
        mode="before",
    )
    @classmethod
    def _coerce_list(cls, value: Any, info: ValidationInfo) -> list[str]:
        items = _normalized_list(value)
        if info.field_name == "preferred_default_audio_languages":
            return [_canonical_audio_language(item) for item in items]
        return items

    @model_validator(mode="after")
    def _default_output_size_check_action(self) -> EffectiveDecisionPolicy:
        if self.output_size_check_action is None:
            self.output_size_check_action = output_size_check_action_from_settings(self.size_guard_mode)
        if self.output_container == "mp4":
            allowed_video_codecs = {"hevc", "h265", "h.265", "h264", "h.264", "avc", "avc1"}
            self.direct_copy_video_codecs = [
                item for item in self.direct_copy_video_codecs if _normalized_text(item) in allowed_video_codecs
            ] or ["hevc", "h265", "h.265", "h264", "h.264", "avc", "avc1"]
            output_codec = _normalized_text(self.video_output_codec)
            if not any(token in output_codec for token in ("h264", "h265", "hevc", "x264", "x265")):
                self.video_output_codec = "hevc_nvenc"
                self.video_codec_family = "hevc"
                self.video_encoder_backend = "nvenc"
            self.audio_transcode_codec = "eac3"
            self.mp4_audio_copy_codecs = ["eac3"]
            self.mp4_subtitle_copy_codecs = []
        height_tolerances = {
            "Route1080pUpperHeightTolerancePercent": self.route_1080p_upper_height_tolerance_percent,
            "Route1440pLowerHeightTolerancePercent": self.route_1440p_lower_height_tolerance_percent,
            "Route1440pUpperHeightTolerancePercent": self.route_1440p_upper_height_tolerance_percent,
            "Route4KLowerHeightTolerancePercent": self.route_4k_lower_height_tolerance_percent,
        }
        height_errors = validate_height_tolerance_boundaries(height_tolerances)
        if height_errors:
            raise ValueError("; ".join(height_errors))
        boundaries = height_tolerance_boundaries(height_tolerances)
        self.route_1080p_bucket_max_height = boundaries.route_1080p_max_height
        self.route_4k_bucket_min_height = boundaries.route_4k_min_height
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
