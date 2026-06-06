from __future__ import annotations

from typing import Any

from mediapipeline.desktop.models import TelemetrySnapshot


def _parse_percent_text(value: object, *, default_for_na: float | None = None) -> float | None:
    text = str(value if value is not None else "").strip()
    if text.casefold() in {"n/a", "na", "[n/a]", ""}:
        return default_for_na
    return float(text)


def parse_nvidia_smi_encoder_rows(output: str) -> tuple[list[dict[str, float | str | None]], int]:
    gpu_rows: list[dict[str, float | str | None]] = []
    parse_failures = 0
    for line in str(output or "").splitlines():
        parts = [item.strip() for item in line.split(",")]
        if len(parts) < 3:
            parse_failures += 1
            continue
        index_text = parts[0]
        name_text = parts[1]
        try:
            encoder_percent = _parse_percent_text(parts[2], default_for_na=0.0)
        except ValueError:
            parse_failures += 1
            continue
        if encoder_percent is None:
            encoder_percent = 0.0
        gpu_percent = None
        metric_offset = 3
        if len(parts) >= 7:
            try:
                gpu_percent = _parse_percent_text(parts[3], default_for_na=None)
            except ValueError:
                gpu_percent = None
            metric_offset = 4
        row: dict[str, float | str | None] = {
            "index": index_text,
            "name": name_text,
            "encoder_percent": encoder_percent,
            "gpu_percent": gpu_percent,
            "temperature_c": None,
            "memory_used_mb": None,
            "memory_total_mb": None,
        }
        if len(parts) >= metric_offset + 1:
            try:
                row["temperature_c"] = float(parts[metric_offset])
            except ValueError:
                pass
        if len(parts) >= metric_offset + 3:
            try:
                row["memory_used_mb"] = float(parts[metric_offset + 1])
                row["memory_total_mb"] = float(parts[metric_offset + 2])
            except ValueError:
                pass
        gpu_rows.append(row)
    return gpu_rows, parse_failures


def select_active_gpu_row(gpu_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not gpu_rows:
        return None
    return max(
        gpu_rows,
        key=lambda row: (
            float(row.get("encoder_percent") or 0.0),
            float(row.get("gpu_percent") or 0.0),
        ),
    )


def apply_nvidia_smi_rows_to_snapshot(snapshot: TelemetrySnapshot, gpu_rows: list[dict[str, Any]]) -> None:
    active = select_active_gpu_row(gpu_rows)
    if active is None:
        return
    gpu_count = len(gpu_rows)
    active_name = str(active.get("name") or "GPU")
    active_index = str(active.get("index") or "")
    snapshot.gpu_name = active_name if gpu_count == 1 else f"{active_name} (GPU {active_index}, max of {gpu_count})"
    snapshot.gpu_index = active_index
    snapshot.gpu_count = gpu_count
    snapshot.gpu_rows = [dict(row) for row in gpu_rows]
    snapshot.gpu_encoder_percent = float(active.get("encoder_percent") or 0.0)
    snapshot.gpu_percent = (
        float(active["gpu_percent"]) if active.get("gpu_percent") is not None else snapshot.gpu_encoder_percent
    )
    snapshot.source = "nvidia-smi"
    if active.get("temperature_c") is not None:
        snapshot.gpu_temperature_c = float(active["temperature_c"])
    used_mb = active.get("memory_used_mb")
    total_mb = active.get("memory_total_mb")
    if used_mb is not None and total_mb is not None:
        snapshot.gpu_memory_used_gb = float(used_mb) / 1024.0
        snapshot.gpu_memory_total_gb = float(total_mb) / 1024.0
        if float(total_mb) > 0:
            snapshot.gpu_memory_percent = (float(used_mb) / float(total_mb)) * 100.0
