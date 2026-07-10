from __future__ import annotations

from dataclasses import dataclass, field

from .dto_base import JsonMap, dto_mapping


@dataclass(frozen=True)
class MaintenanceWorkspaceDto:
    app_version: str
    rows: list[JsonMap] = field(default_factory=list)
    toolchain_evidence: JsonMap = field(default_factory=dict)
    health_progress: JsonMap = field(default_factory=dict)
    progress_bars: list[JsonMap] = field(default_factory=list)
    ok_count: int = 0
    missing_count: int = 0
    warning_count: int = 0
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "desktop_maintenance_workspace.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class RenamePreviewDto:
    rows: list[JsonMap] = field(default_factory=list)
    counts: JsonMap = field(default_factory=dict)
    input_counts: JsonMap = field(default_factory=dict)
    confidence_counts: JsonMap = field(default_factory=dict)
    preview_source_counts: JsonMap = field(default_factory=dict)
    change_kind_counts: JsonMap = field(default_factory=dict)
    active_template: str = ""
    template_catalog: list[JsonMap] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    preview_fingerprint: str = ""
    schema_version: str = "desktop_rename_preview.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class ScheduleWorkspaceDto:
    app_version: str
    enabled: bool = False
    evaluation: JsonMap = field(default_factory=dict)
    day_summaries: list[JsonMap] = field(default_factory=list)
    grid: JsonMap = field(default_factory=dict)
    app_state_path: str = ""
    continuous_watcher: JsonMap = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    read_only: bool = True
    schema_version: str = "desktop_schedule_workspace.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class SettingsWorkspaceDto:
    app_version: str
    config_path: str = ""
    workspace_root: str = ""
    app_root: str = ""
    paths: JsonMap = field(default_factory=dict)
    config_identity: JsonMap = field(default_factory=dict)
    config: JsonMap = field(default_factory=dict)
    field_definitions: list[JsonMap] = field(default_factory=list)
    library_profile_state: list[JsonMap] = field(default_factory=list)
    library_compatibility_presets: list[JsonMap] = field(default_factory=list)
    key_count: int = 0
    profiles: list[str] = field(default_factory=list)
    profile_summary: JsonMap = field(default_factory=dict)
    risk_summary: JsonMap = field(default_factory=dict)
    media_policy_readiness: JsonMap = field(default_factory=dict)
    policy_impact: JsonMap = field(default_factory=dict)
    tool_path_evidence: JsonMap = field(default_factory=dict)
    encoder_capability_report: JsonMap = field(default_factory=dict)
    path_health: JsonMap = field(default_factory=dict)
    persistence_authority: str = ""
    settings_store_status: JsonMap = field(default_factory=dict)
    projection_status: JsonMap = field(default_factory=dict)
    migration_journal: list[str] = field(default_factory=list)
    legacy_extras_count: int = 0
    psd1_drift_status: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    read_only: bool = True
    schema_version: str = "desktop_settings_workspace.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)


@dataclass(frozen=True)
class NetworkWorkersDto:
    app_version: str
    role: str = "standalone"
    source: str = ""
    coordinator_inflight_path: str = ""
    worker_state_path: str = ""
    cluster_log_path: str = ""
    state_files: list[JsonMap] = field(default_factory=list)
    rows: list[JsonMap] = field(default_factory=list)
    active_count: int = 0
    idle_count: int = 0
    total_count: int = 0
    session_completed: int = 0
    session_failed: int = 0
    worker_state: JsonMap = field(default_factory=dict)
    coordinator_connectivity: JsonMap = field(default_factory=dict)
    worker_progress: JsonMap = field(default_factory=dict)
    progress_bars: list[JsonMap] = field(default_factory=list)
    lifecycle_state: JsonMap = field(default_factory=dict)
    runtime_status_label: str = "Unknown"
    runtime_status_severity: str = "unknown"
    operator_summary_lines: list[str] = field(default_factory=list)
    token_posture: JsonMap = field(default_factory=dict)
    running_vs_saved: JsonMap = field(default_factory=dict)
    diagnostic_layers: JsonMap = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    read_only: bool = True
    schema_version: str = "desktop_network_workers.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)

__all__ = [
    "MaintenanceWorkspaceDto",
    "RenamePreviewDto",
    "ScheduleWorkspaceDto",
    "SettingsWorkspaceDto",
    "NetworkWorkersDto",
]
