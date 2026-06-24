from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ResolvedPaths:
    app_root: Path
    workspace_root: Path
    pipeline_path: Path
    config_path: Path
    audit_script_path: Path
    rerun_script_path: Path
    powershell_host: str | None
    local_base: Path | None = None
    state_root: Path | None = None
    active_jobs_path: Path | None = None
    app_state_path: Path | None = None
    source_movies: Path | None = None
    source_tv: Path | None = None
    log_file: Path | None = None
    progress_file: Path | None = None
    event_file: Path | None = None
    pause_flag: Path | None = None
    stop_flag: Path | None = None
    rescan_flag: Path | None = None
    failed_reports_path: Path | None = None
    failed_markers_path: Path | None = None
    pending_push_path: Path | None = None
    audit_reports_path: Path | None = None
    queue_snapshot_path: Path | None = None
    # Local append-only JSONL of completed jobs; populated by the pipeline
    # at runtime and/or by Backfill-CompletedManifest.ps1.
    completed_manifest_path: Path | None = None
    # Non-destructive priority manifest — written by the DesktopApp API,
    # read by the PS1 pipeline on each round.
    priority_manifest_path: Path | None = None
    # Queue ordering strategy override — written by the DesktopApp API,
    # read by the PS1 pipeline at queue-build time.
    queue_strategy_path: Path | None = None
    # Per-file à-la-carte processing overrides (audio track filter, subtitle
    # track filter, etc.) — written by the DesktopApp API, read by the PS1
    # pipeline at per-file processing time.
    file_overrides_path: Path | None = None
    # Audit-only score weights and ignore state. These affect audit reporting
    # and rerun CSV export only; they are not queue or media-policy inputs.
    audit_score_policy_path: Path | None = None
    audit_ignore_manifest_path: Path | None = None
    priority_markers: list[str] = field(default_factory=lambda: ["!"])
    config_data: dict[str, Any] = field(default_factory=dict)
    config_identity: dict[str, Any] = field(default_factory=dict)
    config_last_good_snapshot_path: Path | None = None
    persistence_authority: str = ""
    settings_store_status: dict[str, Any] = field(default_factory=dict)
    projection_status: dict[str, Any] = field(default_factory=dict)
    migration_journal: list[str] = field(default_factory=list)
    legacy_extras_count: int = 0
    psd1_drift_status: str = ""


@dataclass
class Snapshot:
    resolved: ResolvedPaths
    current_activity: str
    status_summary: str
    log_tail: str
    progress: dict[str, Any] | None
    audit_progress: dict[str, Any] | None
    latest_failure_report: Path | None
    latest_failure_json: Path | None
    latest_audit_csv: Path | None
    latest_priority_csv: Path | None
    pipeline_events: list[dict[str, Any]] = field(default_factory=list)
    last_error: str | None = None


@dataclass
class ConfigPreview:
    merged_config: dict[str, Any]
    preview_text: str
    errors: list[str]
    warnings: list[str]
    preserved_keys: list[str] = field(default_factory=list)


@dataclass
class ConfigSaveResult:
    output_path: Path
    backup_path: Path | None = None


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
