from __future__ import annotations

from dataclasses import dataclass, field

from .dto_base import JsonMap, dto_mapping


@dataclass(frozen=True)
class HealthDto:
    app_name: str
    app_version: str
    status: str
    backend: str = "python"
    app_root: str = ""
    workspace_root: str = ""
    capabilities: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "desktop_backend_health.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class AppSnapshotDto:
    app_version: str
    activity: str
    pipeline_state: str
    status_summary: str
    current_work: JsonMap = field(default_factory=dict)
    counts: JsonMap = field(default_factory=dict)
    progress: JsonMap = field(default_factory=dict)
    progress_health: JsonMap = field(default_factory=dict)
    audit_progress: JsonMap = field(default_factory=dict)
    worker_progress: JsonMap = field(default_factory=dict)
    ffmpeg_progress: JsonMap = field(default_factory=dict)
    eta: JsonMap = field(default_factory=dict)
    progress_bars: list[JsonMap] = field(default_factory=list)
    recent_events: list[JsonMap] = field(default_factory=list)
    latest_paths: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    csv_rerun_summary: JsonMap = field(default_factory=dict)
    schema_version: str = "desktop_app_snapshot.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class TelemetryDto:
    sampled_at: str = ""
    cpu_percent: float | None = None
    cpu_utility_percent: float | None = None
    memory_percent: float | None = None
    memory_used_gb: float | None = None
    memory_total_gb: float | None = None
    gpu_present: bool = False
    gpu_percent: float | None = None
    gpu_encoder_percent: float | None = None
    gpu_name: str = ""
    gpu_index: str = ""
    gpu_count: int = 0
    gpu_rows: list[JsonMap] = field(default_factory=list)
    gpu_temperature_c: float | None = None
    gpu_memory_percent: float | None = None
    gpu_memory_used_gb: float | None = None
    gpu_memory_total_gb: float | None = None
    gpu_encoder_usage: JsonMap = field(default_factory=dict)
    source: str = ""
    error: str = ""
    schema_version: str = "desktop_telemetry.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class DiagnosticsDto:
    app_version: str
    active_jobs: list[str] = field(default_factory=list)
    active_job_rows: list[JsonMap] = field(default_factory=list)
    worker_progress: JsonMap = field(default_factory=dict)
    ffmpeg_progress: JsonMap = field(default_factory=dict)
    eta: JsonMap = field(default_factory=dict)
    recent_errors: list[str] = field(default_factory=list)
    recent_events: list[str] = field(default_factory=list)
    status_summary: str = ""
    log_tail: str = ""
    launch_logs: str = ""
    autonomy_health: JsonMap = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "desktop_diagnostics.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class CloseReadinessDto:
    safe_to_close: bool
    state: str
    reason: str
    active_work: bool = False
    continuous_watcher: JsonMap = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "desktop_close_readiness.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)

__all__ = [
    "HealthDto",
    "AppSnapshotDto",
    "TelemetryDto",
    "DiagnosticsDto",
    "CloseReadinessDto",
]
