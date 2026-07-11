from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


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
    # Service-owned mutable roots. Productized launches keep these outside the
    # portable bundle while development launches retain their local layout.
    runtime_state_root: Path | None = None
    run_logs_root: Path | None = None
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
    # Non-destructive priority manifest; written by the DesktopApp API and
    # read by the PS1 pipeline on each round.
    priority_manifest_path: Path | None = None
    # Queue ordering strategy override; written by the DesktopApp API and read
    # by the PS1 pipeline at queue-build time.
    queue_strategy_path: Path | None = None
    # Per-file a la carte processing overrides; written by the DesktopApp API
    # and read by the PS1 pipeline at per-file processing time.
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


class PowerShellHostServiceProtocol(Protocol):
    app_root: Path
    workspace_root: Path


class PathResolutionServiceProtocol(PowerShellHostServiceProtocol, Protocol):
    def default_audit_script_path(self) -> Path: ...
    def default_rerun_script_path(self) -> Path: ...
    def resolve_powershell_host(self) -> str | None: ...
    def load_config_data(self, config_path: Path, powershell_host: str | None) -> dict[str, Any]: ...
    def settings_store_metadata(self, config_path: Path) -> dict[str, Any]: ...
    def _first_existing(self, *paths: Path) -> Path: ...
    def _migrate_app_state_path(self, preferred_path: Path) -> None: ...
    def _path_or_none(self, value: Any) -> Path | None: ...
    def _state_root_for_local_base(self, local_base: Path) -> Path: ...
