from __future__ import annotations

import ctypes
import contextlib
import sys
import threading
from typing import Any

from mediapipeline.desktop.models import TelemetrySnapshot


BYTES_PER_GB = 1024**3
PDH_SUCCESS = 0
PDH_FMT_DOUBLE = 0x00000200
# Sample "% Processor Time": the true 0-100% utilization that matches psutil and
# the classic Windows CPU-usage number. Do NOT use "% Processor Utility" here: it
# is scaled by the turbo frequency ratio, so on turbo-capable CPUs (e.g. Ryzen
# 7800X3D ~4.77/4.20 GHz) it reads ~110% under load and saturates the 0-100%
# telemetry bar at a flat 100% even when actual utilization is far lower.
WINDOWS_PROCESSOR_TIME_COUNTER = r"\Processor Information(_Total)\% Processor Time"


class _PdhFormattedCounterValue(ctypes.Structure):
    _fields_ = [
        ("CStatus", ctypes.c_uint32),
        ("doubleValue", ctypes.c_double),
    ]


def _append_snapshot_error(snapshot: TelemetrySnapshot, message: str) -> None:
    if snapshot.error:
        snapshot.error = f"{snapshot.error}; {message}"
    else:
        snapshot.error = message


def _bounded_percent(value: object) -> float:
    numeric = float(value)
    if numeric < 0.0:
        return 0.0
    if numeric > 100.0:
        return 100.0
    return numeric


class WindowsProcessorUtilitySampler:
    """Reusable PDH sampler for total CPU utilization (% Processor Time, 0-100%)."""

    def __init__(self, counter_path: str = WINDOWS_PROCESSOR_TIME_COUNTER) -> None:
        self._counter_path = counter_path
        self._lock = threading.Lock()
        self._disabled = sys.platform != "win32"
        self._pdh: Any | None = None
        self._query: ctypes.c_void_p | None = None
        self._counter: ctypes.c_void_p | None = None

    def prime(self) -> None:
        self.sample()

    def sample(self) -> float | None:
        if self._disabled:
            return None
        with self._lock:
            if not self._ensure_query():
                return None
            assert self._pdh is not None
            assert self._query is not None
            assert self._counter is not None
            if self._pdh.PdhCollectQueryData(self._query) != PDH_SUCCESS:
                return None
            value = _PdhFormattedCounterValue()
            counter_type = ctypes.c_uint32()
            status = self._pdh.PdhGetFormattedCounterValue(
                self._counter,
                PDH_FMT_DOUBLE,
                ctypes.byref(counter_type),
                ctypes.byref(value),
            )
            if status != PDH_SUCCESS or value.CStatus != PDH_SUCCESS:
                return None
            return float(value.doubleValue)

    def _ensure_query(self) -> bool:
        if self._query is not None and self._counter is not None:
            return True
        try:
            pdh = ctypes.WinDLL("pdh.dll")
            add_counter = getattr(pdh, "PdhAddEnglishCounterW")
        except Exception:
            self._disabled = True
            return False
        pdh.PdhOpenQueryW.argtypes = [ctypes.c_wchar_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
        pdh.PdhOpenQueryW.restype = ctypes.c_uint32
        add_counter.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
        add_counter.restype = ctypes.c_uint32
        pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
        pdh.PdhCollectQueryData.restype = ctypes.c_uint32
        pdh.PdhGetFormattedCounterValue.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(_PdhFormattedCounterValue),
        ]
        pdh.PdhGetFormattedCounterValue.restype = ctypes.c_uint32

        query = ctypes.c_void_p()
        counter = ctypes.c_void_p()
        if pdh.PdhOpenQueryW(None, 0, ctypes.byref(query)) != PDH_SUCCESS:
            self._disabled = True
            return False
        if add_counter(query, self._counter_path, 0, ctypes.byref(counter)) != PDH_SUCCESS:
            close_query = getattr(pdh, "PdhCloseQuery", None)
            if close_query is not None:
                close_query(query)
            self._disabled = True
            return False
        self._pdh = pdh
        self._query = query
        self._counter = counter
        return True


def create_cpu_sampler() -> WindowsProcessorUtilitySampler | None:
    if sys.platform != "win32":
        return None
    return WindowsProcessorUtilitySampler()


def prime_cpu_sampler(psutil_module: Any | None, cpu_sampler: Any | None = None) -> None:
    if cpu_sampler is not None:
        with contextlib.suppress(Exception):
            cpu_sampler.prime()
    if psutil_module is None:
        return
    with contextlib.suppress(Exception):
        psutil_module.cpu_percent(interval=None)


def _sample_cpu_percent(psutil_module: Any | None, cpu_sampler: Any | None) -> float | None:
    if cpu_sampler is not None:
        with contextlib.suppress(Exception):
            sampled = cpu_sampler.sample()
            if sampled is not None:
                return _bounded_percent(sampled)
    if psutil_module is None:
        return None
    return _bounded_percent(psutil_module.cpu_percent(interval=None))


def apply_system_metrics_to_snapshot(
    snapshot: TelemetrySnapshot,
    psutil_module: Any | None,
    cpu_sampler: Any | None = None,
) -> TelemetrySnapshot:
    if psutil_module is None:
        cpu_percent = _sample_cpu_percent(psutil_module, cpu_sampler)
        if cpu_percent is not None:
            snapshot.cpu_percent = cpu_percent
        snapshot.error = "psutil unavailable"
        return snapshot

    try:
        snapshot.cpu_percent = _sample_cpu_percent(psutil_module, cpu_sampler)
    except Exception as exc:
        _append_snapshot_error(snapshot, f"psutil error: {exc}")

    try:
        vm = psutil_module.virtual_memory()
        snapshot.memory_percent = float(vm.percent)
        snapshot.memory_used_gb = vm.used / BYTES_PER_GB
        snapshot.memory_total_gb = vm.total / BYTES_PER_GB
    except Exception as exc:
        _append_snapshot_error(snapshot, f"psutil memory error: {exc}")

    return snapshot
