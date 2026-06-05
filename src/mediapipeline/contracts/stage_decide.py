"""Decide-stage request and result models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import Field, model_validator

from mediapipeline.contracts.height_tolerance import (
    DEFAULT_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT,
    height_tolerance_boundaries,
    legacy_height_tolerance_defaults,
    validate_height_tolerance_boundaries,
)

from .stage_base import StageData, StagePayload

class DecidePayload(StagePayload):
    file_size_bytes: int = Field(ge=0)
    is_tv: bool = False
    duration_seconds: float = Field(default=0.0, ge=0)
    video_codec: str = ""
    video_height: int = Field(default=0, ge=0, le=4320)
    is_hdr: bool = False
    routing_profile: Literal[
        "plex_direct_stream",
        "plex_direct_play",
        "archive_shrink",
        "archive_quality",
        "manual",
    ] = "plex_direct_stream"
    route_threshold_mode: Literal[
        "compatibility_advisory",
        "size",
        "bitrate",
        "size_or_bitrate",
    ] = "compatibility_advisory"
    size_guard_mode: Literal["advisory", "strict", "off"] = "advisory"
    encode_threshold_gb: float = Field(default=8, gt=0)
    tv_encode_threshold_gb: float = Field(default=3, gt=0)
    movie_route_1080p_size_limit_gb: float = Field(default=8, gt=0)
    movie_route_1440p_size_limit_gb: float = Field(default=8, gt=0)
    movie_route_4k_size_limit_gb: float = Field(default=8, gt=0)
    tv_route_1080p_size_limit_gb: float = Field(default=3, gt=0)
    tv_route_1440p_size_limit_gb: float = Field(default=3, gt=0)
    tv_route_4k_size_limit_gb: float = Field(default=3, gt=0)
    movie_route_max_video_bitrate_mbps: float = Field(default=35.0, gt=0, le=500)
    tv_route_max_video_bitrate_mbps: float = Field(default=18.0, gt=0, le=500)
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
    allow_h264_remux_if_plex_compatible: bool = True
    h264_remux_max_bitrate_mbps: float = Field(default=35.0, gt=0)
    h264_remux_max_height: int = Field(default=1080, ge=1, le=4320)
    route_hints: dict[str, Any] = Field(default_factory=dict)
    source_media_profile: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _derive_legacy_policy_fields(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        next_value = dict(value)
        movie_size = next_value.get("encode_threshold_gb", 8.0)
        tv_size = next_value.get("tv_encode_threshold_gb", 3.0)
        for field in (
            "movie_route_1080p_size_limit_gb",
            "movie_route_1440p_size_limit_gb",
            "movie_route_4k_size_limit_gb",
        ):
            next_value.setdefault(field, movie_size)
        for field in (
            "tv_route_1080p_size_limit_gb",
            "tv_route_1440p_size_limit_gb",
            "tv_route_4k_size_limit_gb",
        ):
            next_value.setdefault(field, tv_size)
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

    @model_validator(mode="after")
    def _validate_bucket_order(self) -> DecidePayload:
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

class DecideResult(StageData):
    route: Literal["remux", "encode", "skip"]
    should_encode: bool = False
    reason_code: str = ""
    reason: str = ""
    display_route: str = ""
    source_codec: str = ""
    size_gb: float = Field(default=0.0, ge=0)
    threshold_gb: float = Field(default=0.0, ge=0)
    requires_codec_probe: bool = False
    fallback_from_remux: bool = False
    estimated_bitrate_mbps: float = Field(default=0.0, ge=0)
    bitrate_threshold_mbps: float = Field(default=0.0, ge=0)
    size_over_threshold: bool = False
    bitrate_over_threshold: bool = False
    plex_compatibility_score: float = Field(default=0.0, ge=0, le=100)
    routing_profile: str = ""
    route_threshold_mode: str = ""
    size_guard_mode: str = ""
    encoder_profile: str = ""
    actions: dict[str, Any] = Field(default_factory=dict)
    decision_trace: list[dict[str, Any]] = Field(default_factory=list)
    route_hints: dict[str, Any] = Field(default_factory=dict)
    source_media_profile: dict[str, Any] = Field(default_factory=dict)
