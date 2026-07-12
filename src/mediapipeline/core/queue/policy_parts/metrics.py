"""Queue preview counting, sizing, and formatting helpers."""

from __future__ import annotations

from typing import Any
from collections.abc import Iterable


def queue_snapshot_int(snapshot: dict[str, Any], key: str) -> int:
    try:
        return max(0, int(snapshot.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def queue_safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def queue_safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def queue_media_type_label(value: Any) -> str:
    media_kind = str(value or "").strip().casefold()
    if media_kind == "tv":
        return "TV"
    if media_kind == "movie":
        return "Movie"
    return "Unknown"


def queue_count_by_key(rows: Iterable[dict[str, Any]], key: str, *, default: str = "unknown") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or default).strip() or default
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def queue_counts_text(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={count}" for key, count in sorted(counts.items())) or "none"


def queue_count_list_values(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = row.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            text = str(value or "").strip()
            if text:
                counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))


def queue_priority_reason_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reasons = row.get("priority_reasons")
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            key = str(reason or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def queue_season_key(row: dict[str, Any]) -> str:
    media_type = str(row.get("media_type") or "").casefold()
    if media_type != "tv":
        return "not_tv"
    try:
        season = int(row.get("season_number") or 0)
    except (TypeError, ValueError):
        season = 0
    return f"S{season:02d}" if season >= 0 else "unknown"


def queue_season_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = queue_season_key(row)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def queue_total_size_gb(rows: Iterable[dict[str, Any]]) -> float:
    total = 0.0
    for row in rows:
        try:
            total += max(0.0, float(row.get("size_gb") or 0.0))
        except (TypeError, ValueError):
            continue
    return round(total, 3)


def format_queue_size_gb(value: float) -> str:
    return f"{max(0.0, float(value or 0.0)):.2f} GB"


__all__ = [
    "queue_snapshot_int",
    "queue_safe_int",
    "queue_safe_float",
    "queue_media_type_label",
    "queue_count_by_key",
    "queue_counts_text",
    "queue_count_list_values",
    "queue_priority_reason_counts",
    "queue_season_key",
    "queue_season_counts",
    "queue_total_size_gb",
    "format_queue_size_gb",
]
