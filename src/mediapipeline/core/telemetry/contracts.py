from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TelemetrySnapshot:
    collected_at: datetime | None = None
    cpu_percent: float | None = None
    cpu_utility_percent: float | None = None
    memory_percent: float | None = None
    memory_used_gb: float | None = None
    memory_total_gb: float | None = None
    gpu_percent: float | None = None
    gpu_encoder_percent: float | None = None
    gpu_name: str = ""
    gpu_temperature_c: float | None = None
    gpu_memory_percent: float | None = None
    gpu_memory_used_gb: float | None = None
    gpu_memory_total_gb: float | None = None
    gpu_index: str = ""
    gpu_count: int = 0
    gpu_rows: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""
    error: str = ""
