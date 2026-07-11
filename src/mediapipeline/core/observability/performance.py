"""Small, append-only performance records shared by benchmark tools."""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


PERFORMANCE_RECORD_SCHEMA_VERSION = "mediapipeline_performance_record.v1"


def summarize_duration_samples(samples_ms: Iterable[float]) -> dict[str, float | int]:
    """Return stable summary statistics for non-negative millisecond samples."""

    samples = sorted(max(0.0, float(value)) for value in samples_ms)
    if not samples:
        return {"count": 0, "min_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    p95_index = max(0, math.ceil(len(samples) * 0.95) - 1)
    return {
        "count": len(samples),
        "min_ms": round(samples[0], 3),
        "median_ms": round(float(median(samples)), 3),
        "p95_ms": round(samples[p95_index], 3),
        "max_ms": round(samples[-1], 3),
    }


def performance_record(
    *,
    operation: str,
    metric: str,
    value: float | int,
    unit: str,
    correct: bool,
    variant: str = "baseline",
    tags: Mapping[str, Any] | None = None,
    measured_at: str | None = None,
) -> dict[str, Any]:
    """Build one schema-versioned record without writing it anywhere."""

    return {
        "schema_version": PERFORMANCE_RECORD_SCHEMA_VERSION,
        "measured_at": measured_at or datetime.now(UTC).isoformat(),
        "operation": str(operation).strip(),
        "metric": str(metric).strip(),
        "value": value,
        "unit": str(unit).strip(),
        "correct": bool(correct),
        "variant": str(variant or "baseline").strip(),
        "tags": dict(tags or {}),
    }


def append_performance_records(path: Path, records: Iterable[Mapping[str, Any]]) -> int:
    """Append records as durable JSONL; callers explicitly choose the ledger path."""

    rows = [dict(record) for record in records]
    if not rows:
        return 0
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return len(rows)


__all__ = [
    "PERFORMANCE_RECORD_SCHEMA_VERSION",
    "append_performance_records",
    "performance_record",
    "summarize_duration_samples",
]
