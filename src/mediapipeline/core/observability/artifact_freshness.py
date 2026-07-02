"""Freshness fields for files and timestamped runtime artifacts."""

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
from typing import Any


def format_age_seconds(seconds: int | None) -> str:
    if seconds is None:
        return ""
    value = max(0, int(seconds))
    if value < 60:
        return f"{value}s"
    minutes = value // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"


def iso_from_timestamp(raw: float) -> str:
    return datetime.fromtimestamp(raw, UTC).isoformat(timespec="seconds")


def parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def age_seconds_from_datetime(value: datetime, *, now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return max(0, int((current.astimezone(UTC) - value.astimezone(UTC)).total_seconds()))


def datetime_freshness_fields(
    value: Any,
    *,
    prefix: str,
    stale_after_seconds: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    parsed = parse_iso_datetime(value)
    if parsed is None:
        return {
            f"{prefix}_age_seconds": None,
            f"{prefix}_age_text": "",
            f"{prefix}_freshness_status": "unknown",
            f"{prefix}_stale_after_seconds": stale_after_seconds,
        }
    age_seconds = age_seconds_from_datetime(parsed, now=now)
    return {
        f"{prefix}_age_seconds": age_seconds,
        f"{prefix}_age_text": format_age_seconds(age_seconds),
        f"{prefix}_freshness_status": "stale" if age_seconds > stale_after_seconds else "fresh",
        f"{prefix}_stale_after_seconds": stale_after_seconds,
    }


def file_freshness_fields(
    path: Path | None,
    *,
    prefix: str,
    stale_after_seconds: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        f"{prefix}_mtime_utc": "",
        f"{prefix}_age_seconds": None,
        f"{prefix}_age_text": "",
        f"{prefix}_freshness_status": "missing",
        f"{prefix}_stale_after_seconds": stale_after_seconds,
        f"{prefix}_error": "",
    }
    if path is None:
        fields[f"{prefix}_freshness_status"] = "unresolved"
        return fields
    try:
        stat = path.stat()
    except FileNotFoundError:
        return fields
    except OSError as exc:
        fields[f"{prefix}_freshness_status"] = "unavailable"
        fields[f"{prefix}_error"] = str(exc)
        return fields
    modified = datetime.fromtimestamp(stat.st_mtime, UTC)
    age_seconds = age_seconds_from_datetime(modified, now=now)
    fields.update(
        {
            f"{prefix}_mtime_utc": iso_from_timestamp(stat.st_mtime),
            f"{prefix}_age_seconds": age_seconds,
            f"{prefix}_age_text": format_age_seconds(age_seconds),
            f"{prefix}_freshness_status": "stale" if age_seconds > stale_after_seconds else "fresh",
        }
    )
    return fields


__all__ = [
    "format_age_seconds",
    "iso_from_timestamp",
    "parse_iso_datetime",
    "age_seconds_from_datetime",
    "datetime_freshness_fields",
    "file_freshness_fields",
]
