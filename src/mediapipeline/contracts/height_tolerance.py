from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


HEIGHT_1080P_BASE = 1080
HEIGHT_1440P_BASE = 1440
HEIGHT_4K_BASE = 2160

DEFAULT_ROUTE_1080P_BUCKET_MAX_HEIGHT = 1200
DEFAULT_ROUTE_4K_BUCKET_MIN_HEIGHT = 1800


def _round_percent(value: float) -> float:
    return round(float(value), 6)


def upper_tolerance_percent(base_height: int, max_height: int) -> float:
    return _round_percent(((float(max_height) / float(base_height)) - 1.0) * 100.0)


def lower_tolerance_percent(base_height: int, min_height: int) -> float:
    return _round_percent((1.0 - (float(min_height) / float(base_height))) * 100.0)


DEFAULT_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT = upper_tolerance_percent(
    HEIGHT_1080P_BASE,
    DEFAULT_ROUTE_1080P_BUCKET_MAX_HEIGHT,
)
DEFAULT_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT = lower_tolerance_percent(
    HEIGHT_1440P_BASE,
    DEFAULT_ROUTE_1080P_BUCKET_MAX_HEIGHT + 1,
)
DEFAULT_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT = upper_tolerance_percent(
    HEIGHT_1440P_BASE,
    DEFAULT_ROUTE_4K_BUCKET_MIN_HEIGHT - 1,
)
DEFAULT_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT = lower_tolerance_percent(
    HEIGHT_4K_BASE,
    DEFAULT_ROUTE_4K_BUCKET_MIN_HEIGHT,
)


@dataclass(frozen=True)
class HeightToleranceBoundaries:
    route_1080p_max_height: int
    route_1440p_min_height: int
    route_1440p_max_height: int
    route_4k_min_height: int


def max_height_from_upper_tolerance(base_height: int, tolerance_percent: float) -> int:
    return int(round(float(base_height) * (1.0 + (float(tolerance_percent) / 100.0))))


def min_height_from_lower_tolerance(base_height: int, tolerance_percent: float) -> int:
    return int(round(float(base_height) * (1.0 - (float(tolerance_percent) / 100.0))))


def legacy_height_tolerance_defaults(
    *,
    route_1080p_bucket_max_height: int = DEFAULT_ROUTE_1080P_BUCKET_MAX_HEIGHT,
    route_4k_bucket_min_height: int = DEFAULT_ROUTE_4K_BUCKET_MIN_HEIGHT,
) -> dict[str, float]:
    return {
        "Route1080pUpperHeightTolerancePercent": upper_tolerance_percent(
            HEIGHT_1080P_BASE,
            int(route_1080p_bucket_max_height),
        ),
        "Route1440pLowerHeightTolerancePercent": lower_tolerance_percent(
            HEIGHT_1440P_BASE,
            int(route_1080p_bucket_max_height) + 1,
        ),
        "Route1440pUpperHeightTolerancePercent": upper_tolerance_percent(
            HEIGHT_1440P_BASE,
            int(route_4k_bucket_min_height) - 1,
        ),
        "Route4KLowerHeightTolerancePercent": lower_tolerance_percent(
            HEIGHT_4K_BASE,
            int(route_4k_bucket_min_height),
        ),
    }


def height_tolerance_boundaries(values: Mapping[str, float]) -> HeightToleranceBoundaries:
    route_1080p_max = max_height_from_upper_tolerance(
        HEIGHT_1080P_BASE,
        float(values["Route1080pUpperHeightTolerancePercent"]),
    )
    route_1440p_min = min_height_from_lower_tolerance(
        HEIGHT_1440P_BASE,
        float(values["Route1440pLowerHeightTolerancePercent"]),
    )
    route_1440p_max = max_height_from_upper_tolerance(
        HEIGHT_1440P_BASE,
        float(values["Route1440pUpperHeightTolerancePercent"]),
    )
    route_4k_min = min_height_from_lower_tolerance(
        HEIGHT_4K_BASE,
        float(values["Route4KLowerHeightTolerancePercent"]),
    )
    return HeightToleranceBoundaries(
        route_1080p_max_height=route_1080p_max,
        route_1440p_min_height=route_1440p_min,
        route_1440p_max_height=route_1440p_max,
        route_4k_min_height=route_4k_min,
    )


def validate_height_tolerance_boundaries(values: Mapping[str, float]) -> list[str]:
    boundaries = height_tolerance_boundaries(values)
    errors: list[str] = []
    if boundaries.route_1440p_min_height != boundaries.route_1080p_max_height + 1:
        errors.append(
            "Height tolerance must make 1440p start exactly one pixel above the 1080p upper boundary."
        )
    if boundaries.route_4k_min_height != boundaries.route_1440p_max_height + 1:
        errors.append(
            "Height tolerance must make 4K start exactly one pixel above the 1440p upper boundary."
        )
    return errors


__all__ = [
    "DEFAULT_ROUTE_1080P_BUCKET_MAX_HEIGHT",
    "DEFAULT_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT",
    "DEFAULT_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT",
    "DEFAULT_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT",
    "DEFAULT_ROUTE_4K_BUCKET_MIN_HEIGHT",
    "DEFAULT_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT",
    "HEIGHT_1080P_BASE",
    "HEIGHT_1440P_BASE",
    "HEIGHT_4K_BASE",
    "HeightToleranceBoundaries",
    "height_tolerance_boundaries",
    "legacy_height_tolerance_defaults",
    "lower_tolerance_percent",
    "max_height_from_upper_tolerance",
    "min_height_from_lower_tolerance",
    "upper_tolerance_percent",
    "validate_height_tolerance_boundaries",
]
