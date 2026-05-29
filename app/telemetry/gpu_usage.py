from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from mediapipeline_desktop_app.models import TelemetrySnapshot

GPU_ENCODER_USAGE_SCHEMA_VERSION = "desktop_gpu_encoder_usage.v1"


def _sample_time(telemetry: TelemetrySnapshot) -> str:
    collected_at = telemetry.collected_at
    if collected_at is None:
        return ""
    if collected_at.tzinfo:
        return collected_at.astimezone().isoformat()
    return collected_at.isoformat()


def _finite_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _finite_int(value: object) -> int | None:
    numeric = _finite_float(value)
    if numeric is None:
        return None
    return int(numeric)


def _memory_mb_from_row(row: Mapping[str, Any], telemetry: TelemetrySnapshot, key: str) -> float | None:
    value = _finite_float(row.get(key))
    if value is not None:
        return value
    if key == "memory_used_mb" and telemetry.gpu_memory_used_gb is not None:
        return float(telemetry.gpu_memory_used_gb) * 1024.0
    if key == "memory_total_mb" and telemetry.gpu_memory_total_gb is not None:
        return float(telemetry.gpu_memory_total_gb) * 1024.0
    return None


def _row_from_mapping(
    row: Mapping[str, Any],
    telemetry: TelemetrySnapshot,
    *,
    sample_time: str,
    synthesized: bool = False,
) -> dict[str, Any]:
    memory_used_mb = _memory_mb_from_row(row, telemetry, "memory_used_mb")
    memory_total_mb = _memory_mb_from_row(row, telemetry, "memory_total_mb")
    memory_percent = None
    if memory_used_mb is not None and memory_total_mb not in (None, 0):
        memory_percent = (float(memory_used_mb) / float(memory_total_mb)) * 100.0
    elif telemetry.gpu_memory_percent is not None:
        memory_percent = float(telemetry.gpu_memory_percent)
    return {
        "adapter": str(row.get("name") or telemetry.gpu_name or "GPU"),
        "adapter_index": str(row.get("index") if row.get("index") not in (None, "") else telemetry.gpu_index),
        "encoder_sessions": _finite_int(row.get("encoder_sessions")),
        "utilization_percent": _finite_float(row.get("encoder_percent", telemetry.gpu_encoder_percent)),
        "memory_used": memory_used_mb,
        "memory_used_mb": memory_used_mb,
        "memory_total_mb": memory_total_mb,
        "memory_percent": memory_percent,
        "temperature_c": _finite_float(row.get("temperature_c", telemetry.gpu_temperature_c)),
        "sample_time": sample_time,
        "read_error": str(telemetry.error or ""),
        "source": str(telemetry.source or ""),
        "synthesized": bool(synthesized),
    }


def _gpu_rows(telemetry: TelemetrySnapshot, sample_time: str) -> list[dict[str, Any]]:
    raw_rows = [row for row in telemetry.gpu_rows if isinstance(row, Mapping)]
    if raw_rows:
        return [_row_from_mapping(row, telemetry, sample_time=sample_time) for row in raw_rows]
    if telemetry.gpu_encoder_percent is None and not str(telemetry.gpu_name or "").strip() and telemetry.gpu_count <= 0:
        return []
    return [
        _row_from_mapping(
            {
                "index": telemetry.gpu_index or "0",
                "name": telemetry.gpu_name or "GPU",
                "encoder_percent": telemetry.gpu_encoder_percent,
            },
            telemetry,
            sample_time=sample_time,
            synthesized=True,
        )
    ]


def gpu_encoder_usage_payload(telemetry: TelemetrySnapshot | None, *, now: datetime | None = None) -> dict[str, Any]:
    """Build a read-only GPU/NVENC usage contract from the current telemetry sample."""
    _ = now
    if not isinstance(telemetry, TelemetrySnapshot):
        return {
            "schema_version": GPU_ENCODER_USAGE_SCHEMA_VERSION,
            "mode": "gpu_encoder_usage",
            "status": "unavailable",
            "row_count": 0,
            "active_encoder_count": 0,
            "rows": [],
            "summary_lines": [
                "GPU/NVENC usage: unavailable",
                "No telemetry sample was available.",
                "Mutation guardrail: GPU/NVENC usage is read-only telemetry and cannot start, stop, or tune encoders.",
            ],
            "read_only": True,
        }
    sample_time = _sample_time(telemetry)
    rows = _gpu_rows(telemetry, sample_time)
    active_encoder_count = sum(1 for row in rows if float(row.get("utilization_percent") or 0.0) > 0.0)
    missing_session_count = sum(1 for row in rows if row.get("encoder_sessions") is None)
    status = "warning" if telemetry.error else "loaded" if rows else "unavailable"
    summary_lines = [
        f"GPU/NVENC usage: {status}",
        f"Rows: {len(rows)}; active_encoders={active_encoder_count}; missing_session_counts={missing_session_count}.",
        f"Sample: {sample_time or 'not reported'}; source={telemetry.source or 'not reported'}.",
    ]
    if missing_session_count:
        summary_lines.append("Encoder sessions are not reported by the current nvidia-smi sampler; utilization and memory are the reliable fields.")
    if telemetry.error:
        summary_lines.append(f"Read warning: {telemetry.error}")
    summary_lines.extend(
        [
            "Data source: cached telemetry sample from the backend sampler.",
            "Mutation guardrail: GPU/NVENC usage is read-only telemetry; encoder policy and process control remain backend-owned.",
        ]
    )
    return {
        "schema_version": GPU_ENCODER_USAGE_SCHEMA_VERSION,
        "mode": "gpu_encoder_usage",
        "status": status,
        "row_count": len(rows),
        "active_encoder_count": active_encoder_count,
        "missing_session_count": missing_session_count,
        "rows": rows,
        "summary_lines": summary_lines,
        "read_only": True,
    }


__all__ = [
    "GPU_ENCODER_USAGE_SCHEMA_VERSION",
    "gpu_encoder_usage_payload",
]
