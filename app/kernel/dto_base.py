from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
import math
from pathlib import Path
from typing import Any


JsonMap = dict[str, Any]


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone().isoformat() if value.tzinfo else value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [json_safe(item) for item in value]
    if isinstance(value, set):
        return [json_safe(item) for item in sorted(value, key=str)]
    return value


def dto_mapping(instance: Any) -> JsonMap:
    return json_safe(asdict(instance))


def split_summary_lines(value: object) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [str(item) for item in value if str(item).strip()]
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]

__all__ = [
    "json_safe",
    "dto_mapping",
    "split_summary_lines",
]
