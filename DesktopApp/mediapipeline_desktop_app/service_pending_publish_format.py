from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any


def int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_bytes_compact(raw_bytes: int) -> str:
    value = max(0.0, float(raw_bytes or 0))
    if value >= 1024 ** 3:
        return f"{value / (1024 ** 3):.2f} GB"
    if value >= 1024 ** 2:
        return f"{value / (1024 ** 2):.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{int(value)} B"


def format_pending_timestamp(timestamp: float) -> str:
    if timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def format_pending_datetime_text(value: str) -> str:
    parsed = parse_pending_datetime(value)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d %H:%M")
    text = str(value or "").strip()
    return text[:16].replace("T", " ") if text else ""


def pending_age_text(value: str) -> str:
    parsed = parse_pending_datetime(value)
    if parsed is None:
        return ""
    now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
    seconds = max(0, int((now - parsed).total_seconds()))
    if seconds >= 86400:
        return f"{seconds // 86400}d"
    if seconds >= 3600:
        return f"{seconds // 3600}h"
    if seconds >= 60:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def parse_pending_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    with contextlib.suppress(ValueError):
        return datetime.fromisoformat(text)
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p"):
        with contextlib.suppress(ValueError):
            return datetime.strptime(text, fmt)
    return None
