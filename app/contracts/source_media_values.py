"""Scalar normalization helpers for SourceMediaInfo adapters."""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from app.contracts.source_media_models import MediaType, ScanType


def model_or_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def normalize_codec(value: Any) -> str:
    text = normalize_text(value)
    aliases = {
        "h.264": "h264",
        "avc": "h264",
        "avc1": "h264",
        "h.265": "hevc",
        "h265": "hevc",
    }
    return aliases.get(text, text or "unknown")


def normalize_text(value: Any) -> str:
    return text_value(value).strip().lower()


def text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def int_value(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return max(0, int(float(str(value))))
    except (TypeError, ValueError):
        return 0


def float_value(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return max(0.0, float(str(value)))
    except (TypeError, ValueError):
        return 0.0


def bool_flag(value: Any) -> bool:
    return int_value(value) == 1 or bool_value(value)


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def media_type(value: Any) -> MediaType:
    text = normalize_text(value)
    if text in {"movie", "movies"}:
        return "movie"
    if text in {"tv", "episode", "show"}:
        return "tv"
    return "unknown"


def mbps_to_bps(value: float) -> int:
    return int(round(value * 1_000_000))


def frame_rate(value: Any) -> float:
    text = text_value(value)
    if not text or text == "0/0":
        return 0.0
    try:
        if "/" in text:
            return round(float(Fraction(text)), 3)
        return round(float(text), 3)
    except (ValueError, ZeroDivisionError):
        return 0.0


def ratio(value: str) -> float:
    try:
        if ":" in value:
            left, right = value.split(":", 1)
            denominator = float(right)
            return 0.0 if denominator == 0 else float(left) / denominator
        if "/" in value:
            return float(Fraction(value))
        return float(value) if value else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def ratio_text(value: float) -> str:
    if value <= 0:
        return ""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def scan_type(value: Any) -> ScanType:
    text = normalize_text(value)
    if text in {"progressive", "prog"}:
        return "progressive"
    if text in {"tt", "bb", "tb", "bt", "interlaced"}:
        return "interlaced"
    return "unknown"


__all__ = [
    "model_or_mapping",
    "as_list",
    "normalize_codec",
    "normalize_text",
    "text_value",
    "int_value",
    "float_value",
    "bool_flag",
    "bool_value",
    "media_type",
    "mbps_to_bps",
    "frame_rate",
    "ratio",
    "ratio_text",
    "scan_type",
]
