"""Resolution-aware routing size and bitrate helpers."""

from __future__ import annotations

from typing import Any

from mediapipeline.contracts.height_tolerance import height_tolerance_boundaries
from mediapipeline.core.decide.processing_decision import EffectiveDecisionPolicy

def _resolution_size_selection(
    *,
    bucket: str,
    media_type: str,
    effective_media_type: str,
    movie_fallback_size: float,
    tv_fallback_size: float,
    policy: EffectiveDecisionPolicy,
) -> dict[str, Any]:
    normalized_bucket = bucket.strip().lower()
    bucket_sizes: dict[str, tuple[float, float]] = {
        "1080p": (policy.movie_route_1080p_size_limit_gb, policy.tv_route_1080p_size_limit_gb),
        "1440p": (policy.movie_route_1440p_size_limit_gb, policy.tv_route_1440p_size_limit_gb),
        "4k": (policy.movie_route_4k_size_limit_gb, policy.tv_route_4k_size_limit_gb),
    }
    if normalized_bucket in bucket_sizes:
        movie_size, tv_size = bucket_sizes[normalized_bucket]
        source = "source_height_bucket"
        selected_bucket = normalized_bucket
    else:
        movie_size, tv_size = movie_fallback_size, tv_fallback_size
        source = "movie_tv_fallback"
        selected_bucket = normalized_bucket or "unknown_height"

    if media_type == "unknown":
        limit = min(value for value in (movie_size, tv_size) if value > 0) if any((movie_size, tv_size)) else 0.0
        designation = "conservative_movie_tv"
    elif effective_media_type == "tv":
        limit = tv_size
        designation = "tv"
    else:
        limit = movie_size
        designation = "movie"

    return {
        "limit_gb": float(limit),
        "source": f"{source}_{designation}",
        "bucket": selected_bucket,
    }

def _resolution_bitrate_selection(
    *,
    height: int,
    media_type: str,
    movie_bitrate: float,
    tv_bitrate: float,
    policy: EffectiveDecisionPolicy,
) -> dict[str, Any]:
    boundaries = height_tolerance_boundaries(
        {
            "Route1080pUpperHeightTolerancePercent": policy.route_1080p_upper_height_tolerance_percent,
            "Route1440pLowerHeightTolerancePercent": policy.route_1440p_lower_height_tolerance_percent,
            "Route1440pUpperHeightTolerancePercent": policy.route_1440p_upper_height_tolerance_percent,
            "Route4KLowerHeightTolerancePercent": policy.route_4k_lower_height_tolerance_percent,
        }
    )

    if height <= 0:
        if media_type == "unknown":
            cap = min(value for value in (movie_bitrate, tv_bitrate) if value > 0) if any((movie_bitrate, tv_bitrate)) else 0.0
            fallback = "conservative_movie_tv"
        elif media_type == "tv":
            cap = tv_bitrate
            fallback = "tv"
        else:
            cap = movie_bitrate
            fallback = "movie"
        return {
            "cap_mbps": float(cap),
            "source": "movie_tv_fallback",
            "bucket": f"unknown_height_{fallback}",
            "height": int(height),
            "route_1440p_min_height": boundaries.route_1440p_min_height,
            "route_1440p_max_height": boundaries.route_1440p_max_height,
        }

    if height < boundaries.route_1440p_min_height:
        return {
            "cap_mbps": float(policy.route_1080p_max_video_bitrate_mbps),
            "source": "source_height_bucket",
            "bucket": "1080p",
            "height": int(height),
            "route_1440p_min_height": boundaries.route_1440p_min_height,
            "route_1440p_max_height": boundaries.route_1440p_max_height,
        }

    if height < boundaries.route_4k_min_height:
        return {
            "cap_mbps": float(policy.route_1440p_max_video_bitrate_mbps),
            "source": "source_height_bucket",
            "bucket": "1440p",
            "height": int(height),
            "route_1440p_min_height": boundaries.route_1440p_min_height,
            "route_1440p_max_height": boundaries.route_1440p_max_height,
        }

    return {
        "cap_mbps": float(policy.route_4k_max_video_bitrate_mbps),
        "source": "source_height_bucket",
        "bucket": "4k",
        "height": int(height),
        "route_1440p_min_height": boundaries.route_1440p_min_height,
        "route_1440p_max_height": boundaries.route_1440p_max_height,
    }

def _positive_min(*values: float) -> float:
    positive = [float(value) for value in values if float(value) > 0]
    return min(positive) if positive else 0.0
