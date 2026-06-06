"""Routing trace and source fact helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mediapipeline.contracts.source_media import SourceMediaInfo, SourceVideoStream
from mediapipeline.core.decide.processing_decision import DecisionReason, EffectiveDecisionPolicy, StreamActionSet
from mediapipeline.core.decide.routing_facts import estimated_bitrate_mbps, normalize_codec
from mediapipeline.core.decide.routing_size_policy import _positive_min, _resolution_bitrate_selection, _resolution_size_selection

class _DecisionBuilder:
    def __init__(self) -> None:
        self.reasons: list[DecisionReason] = []

    def add(
        self,
        code: str,
        text: str,
        *,
        enforcement: str = "derived",
        legacy_code: str = "",
        facts: Mapping[str, Any] | None = None,
    ) -> DecisionReason:
        normalized = code.strip().upper()
        existing = next((reason for reason in self.reasons if reason.code == normalized), None)
        if existing is not None:
            return existing
        reason = DecisionReason(
            code=normalized,
            text=text,
            enforcement=enforcement,  # type: ignore[arg-type]
            legacy_code=legacy_code,
            facts=dict(facts or {}),
        )
        self.reasons.append(reason)
        return reason

def _source_facts(
    source: SourceMediaInfo,
    video: SourceVideoStream,
    policy: EffectiveDecisionPolicy,
    builder: _DecisionBuilder,
) -> dict[str, Any]:
    media_type = source.container.media_type
    conservative_media_type = media_type
    if media_type == "unknown":
        conservative_media_type = "tv"
        builder.add(
            "MEDIA_TYPE_UNKNOWN_CONSERVATIVE_CAP",
            "media type is unknown; using conservative 1080p size target when needed",
            enforcement="advisory",
            legacy_code="media_type_unknown_conservative_cap",
        )

    bitrate_selection = _resolution_bitrate_selection(
        height=video.height,
        media_type=media_type,
        policy=policy,
    )
    size_selection = _resolution_size_selection(
        bucket="unknown" if int(bitrate_selection.get("height", 0)) <= 0 else str(bitrate_selection["bucket"]),
        media_type=media_type,
        effective_media_type=conservative_media_type,
        policy=policy,
    )
    size_limit = float(size_selection["limit_gb"])
    route_bitrate_cap = float(bitrate_selection["cap_mbps"])
    bitrate_cap = route_bitrate_cap
    h264_cap_applied = False

    if policy.allow_h264_compatible_direct_copy and normalize_codec(video.codec) in {"h264", "avc"}:
        bitrate_cap = _positive_min(bitrate_cap, policy.h264_direct_copy_max_bitrate_mbps)
        h264_cap_applied = bool(bitrate_cap != route_bitrate_cap)

    estimated = estimated_bitrate_mbps(source, video)
    size_gb = source.container.file_size_bytes / (1024.0**3) if source.container.file_size_bytes > 0 else 0.0
    bitrate_over = bool(estimated > 0 and bitrate_cap > 0 and estimated > bitrate_cap)
    size_over = bool(size_gb > 0 and size_limit > 0 and size_gb > size_limit)
    return {
        "media_type": media_type,
        "effective_media_type": conservative_media_type,
        "codec": normalize_codec(video.codec),
        "height": video.height,
        "duration_seconds": source.container.duration_seconds,
        "source_size_bytes": source.container.file_size_bytes,
        "source_size_gb": round(size_gb, 3),
        "route_size_limit_gb": size_limit,
        "route_size_limit_source": size_selection["source"],
        "route_size_limit_bucket": size_selection["bucket"],
        "movie_route_1080p_size_limit_gb": policy.movie_route_1080p_size_limit_gb,
        "movie_route_1440p_size_limit_gb": policy.movie_route_1440p_size_limit_gb,
        "movie_route_4k_size_limit_gb": policy.movie_route_4k_size_limit_gb,
        "tv_route_1080p_size_limit_gb": policy.tv_route_1080p_size_limit_gb,
        "tv_route_1440p_size_limit_gb": policy.tv_route_1440p_size_limit_gb,
        "tv_route_4k_size_limit_gb": policy.tv_route_4k_size_limit_gb,
        "estimated_video_bitrate_mbps": round(estimated, 3),
        "direct_copy_bitrate_cap_mbps": bitrate_cap,
        "route_direct_copy_bitrate_cap_mbps": route_bitrate_cap,
        "direct_copy_bitrate_cap_source": bitrate_selection["source"],
        "direct_copy_bitrate_bucket": bitrate_selection["bucket"],
        "direct_copy_bitrate_bucket_height": bitrate_selection["height"],
        "route_1080p_bucket_max_height": policy.route_1080p_bucket_max_height,
        "route_1080p_upper_height_tolerance_percent": policy.route_1080p_upper_height_tolerance_percent,
        "route_1080p_max_video_bitrate_mbps": policy.route_1080p_max_video_bitrate_mbps,
        "route_1440p_bucket_min_height": bitrate_selection.get("route_1440p_min_height", 0),
        "route_1440p_bucket_max_height": bitrate_selection.get("route_1440p_max_height", 0),
        "route_1440p_lower_height_tolerance_percent": policy.route_1440p_lower_height_tolerance_percent,
        "route_1440p_upper_height_tolerance_percent": policy.route_1440p_upper_height_tolerance_percent,
        "route_1440p_max_video_bitrate_mbps": policy.route_1440p_max_video_bitrate_mbps,
        "route_4k_lower_height_tolerance_percent": policy.route_4k_lower_height_tolerance_percent,
        "route_4k_bucket_min_height": policy.route_4k_bucket_min_height,
        "route_4k_max_video_bitrate_mbps": policy.route_4k_max_video_bitrate_mbps,
        "unknown_height_bucket": "1080p",
        "h264_direct_copy_bitrate_cap_applied": h264_cap_applied,
        "h264_direct_copy_max_bitrate_mbps": policy.h264_direct_copy_max_bitrate_mbps,
        "source_size_over_route_limit": size_over,
        "video_bitrate_over_direct_copy_cap": bitrate_over,
        "routing_profile": policy.routing_profile,
        "route_threshold_mode": policy.route_threshold_mode,
    }

def _legacy_reason_for_actions(actions: StreamActionSet, builder: _DecisionBuilder) -> str:
    if actions.video.action == "reject":
        return "source_unprobeable_reject"
    if actions.video.action == "encode":
        for code in (
            "VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP",
            "FILTERS_ENABLED_ENCODE_REQUIRED",
            "RESOLUTION_EXCEEDS_LIMIT",
            "SOURCE_SIZE_EXCEEDS_ROUTE_LIMIT",
            "SOURCE_CODEC_INCOMPATIBLE",
            "SUBTITLE_BURN_IN_REQUIRES_ENCODE",
        ):
            reason = next((item for item in builder.reasons if item.code == code and item.legacy_code), None)
            if reason:
                return reason.legacy_code
        return "encode_required"
    for code in ("SOURCE_SIZE_EXCEEDS_ROUTE_LIMIT", "SOURCE_CODEC_COMPATIBLE", "CONTAINER_REMUX_ONLY"):
        reason = next((item for item in builder.reasons if item.code == code and item.legacy_code), None)
        if reason:
            return reason.legacy_code
    return "size_within_threshold"
