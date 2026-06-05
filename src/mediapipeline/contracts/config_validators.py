"""Reusable validation helpers for the configuration contract."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from mediapipeline.contracts.height_tolerance import (
    DEFAULT_ROUTE_1080P_BUCKET_MAX_HEIGHT,
    DEFAULT_ROUTE_4K_BUCKET_MIN_HEIGHT,
    height_tolerance_boundaries,
    legacy_height_tolerance_defaults,
    validate_height_tolerance_boundaries,
)


def reject_boolean_numeric_fields(value: Any, numeric_config_keys: Iterable[str]) -> Any:
    if isinstance(value, dict):
        for key in numeric_config_keys:
            if isinstance(value.get(key), bool):
                raise ValueError(f"{key} must be numeric, not boolean.")
    return value


def derive_missing_height_tolerance_fields(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    next_value = dict(value)
    tolerance_keys = (
        "Route1080pUpperHeightTolerancePercent",
        "Route1440pLowerHeightTolerancePercent",
        "Route1440pUpperHeightTolerancePercent",
        "Route4KLowerHeightTolerancePercent",
    )
    explicit_tolerance = any(key in next_value for key in tolerance_keys)
    try:
        route_1080p_max = int(
            next_value.get(
                "Route1080pBucketMaxHeight",
                DEFAULT_ROUTE_1080P_BUCKET_MAX_HEIGHT,
            )
        )
        route_4k_min = int(
            next_value.get(
                "Route4KBucketMinHeight",
                DEFAULT_ROUTE_4K_BUCKET_MIN_HEIGHT,
            )
        )
    except (TypeError, ValueError):
        return value
    if (
        not explicit_tolerance
        and (
            "Route1080pBucketMaxHeight" in next_value
            or "Route4KBucketMinHeight" in next_value
        )
        and route_1080p_max >= route_4k_min
    ):
        raise ValueError("Route1080pBucketMaxHeight must be lower than Route4KBucketMinHeight.")
    for key, default_value in legacy_height_tolerance_defaults(
        route_1080p_bucket_max_height=route_1080p_max,
        route_4k_bucket_min_height=route_4k_min,
    ).items():
        next_value.setdefault(key, default_value)
    if explicit_tolerance:
        try:
            boundaries = height_tolerance_boundaries(
                {key: float(next_value[key]) for key in tolerance_keys}
            )
        except (KeyError, TypeError, ValueError):
            return next_value
        next_value["Route1080pBucketMaxHeight"] = boundaries.route_1080p_max_height
        next_value["Route4KBucketMinHeight"] = boundaries.route_4k_min_height
    return next_value


def derive_missing_resolution_size_targets(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    next_value = dict(value)
    movie_size = next_value.get("EncodeThresholdGB", 8)
    tv_size = next_value.get("TVEncodeThresholdGB", 3)
    for key in (
        "MovieRoute1080pTargetSizeGB",
        "MovieRoute1440pTargetSizeGB",
        "MovieRoute4KTargetSizeGB",
    ):
        next_value.setdefault(key, movie_size)
    for key in (
        "TVRoute1080pTargetSizeGB",
        "TVRoute1440pTargetSizeGB",
        "TVRoute4KTargetSizeGB",
    ):
        next_value.setdefault(key, tv_size)
    return next_value


def validate_cross_field_config_policy(config: Any) -> None:
    height_tolerances = {
        "Route1080pUpperHeightTolerancePercent": config.Route1080pUpperHeightTolerancePercent,
        "Route1440pLowerHeightTolerancePercent": config.Route1440pLowerHeightTolerancePercent,
        "Route1440pUpperHeightTolerancePercent": config.Route1440pUpperHeightTolerancePercent,
        "Route4KLowerHeightTolerancePercent": config.Route4KLowerHeightTolerancePercent,
    }
    height_errors = validate_height_tolerance_boundaries(height_tolerances)
    if height_errors:
        raise ValueError("; ".join(height_errors))
    boundaries = height_tolerance_boundaries(height_tolerances)
    if config.Route1080pBucketMaxHeight != boundaries.route_1080p_max_height:
        raise ValueError("Route1080pBucketMaxHeight must match the 1080p upper height tolerance.")
    if config.Route4KBucketMinHeight != boundaries.route_4k_min_height:
        raise ValueError("Route4KBucketMinHeight must match the 4K lower height tolerance.")
    if not config.ConvertTx3gToSrt and config.DropTx3gAfterConversion:
        raise ValueError("DropTx3gAfterConversion requires ConvertTx3gToSrt.")
    if not config.ConvertTx3gToSrt and config.CreateExternalTx3gSrtSidecars:
        raise ValueError("CreateExternalTx3gSrtSidecars requires ConvertTx3gToSrt.")
    if not config.ConvertBdpgsToSrt and config.DropBdpgsAfterConversion:
        raise ValueError("DropBdpgsAfterConversion requires ConvertBdpgsToSrt.")
    if config.ConvertBdpgsToSrt and not config.BdpgsOcrToolPath.strip():
        raise ValueError("ConvertBdpgsToSrt requires BdpgsOcrToolPath.")
    if not config.ConvertVobSubToSrt and config.DropVobSubAfterConversion:
        raise ValueError("DropVobSubAfterConversion requires ConvertVobSubToSrt.")
    if config.ConvertVobSubToSrt and not config.VobSubOcrToolPath.strip():
        raise ValueError("ConvertVobSubToSrt requires VobSubOcrToolPath.")
