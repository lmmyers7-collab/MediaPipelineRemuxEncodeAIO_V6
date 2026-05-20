from __future__ import annotations

import contextlib
from typing import Any

from .models import TelemetrySnapshot


BYTES_PER_GB = 1024 ** 3


def prime_cpu_sampler(psutil_module: Any | None) -> None:
    if psutil_module is None:
        return
    with contextlib.suppress(Exception):
        psutil_module.cpu_percent(interval=None)


def apply_system_metrics_to_snapshot(snapshot: TelemetrySnapshot, psutil_module: Any | None) -> TelemetrySnapshot:
    if psutil_module is None:
        snapshot.error = "psutil unavailable"
        return snapshot

    try:
        snapshot.cpu_percent = float(psutil_module.cpu_percent(interval=None))
    except Exception as exc:
        snapshot.error = f"psutil error: {exc}"

    try:
        vm = psutil_module.virtual_memory()
        snapshot.memory_percent = float(vm.percent)
        snapshot.memory_used_gb = vm.used / BYTES_PER_GB
        snapshot.memory_total_gb = vm.total / BYTES_PER_GB
    except Exception:
        pass

    return snapshot
