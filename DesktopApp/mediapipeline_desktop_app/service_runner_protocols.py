from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any, Protocol

from .models_core import ConfigSaveResult, ResolvedPaths
from .subprocess_runner import CapturedCommandResult, KillTreeCallback


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


class InfoWarningLogger(WarningLogger, Protocol):
    def info(self, message: object, *args: object, **kwargs: object) -> None: ...


class ExceptionWarningLogger(WarningLogger, Protocol):
    def exception(self, message: object, *args: object, **kwargs: object) -> None: ...


class RunCaptureFunc(Protocol):
    def __call__(
        self,
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        extra_popen_kwargs: Mapping[str, Any] | None = None,
        encoding: str | None = None,
        errors: str | None = None,
        hidden: bool = True,
        label: str = "process",
        kill_tree: KillTreeCallback | None = None,
    ) -> CapturedCommandResult: ...


class AppStateMigrationServiceProtocol(Protocol):
    app_root: Path
    app_state_path: Path | None
    logger: WarningLogger


class PowerShellHostServiceProtocol(Protocol):
    app_root: Path
    workspace_root: Path


class PathResolutionServiceProtocol(PowerShellHostServiceProtocol, Protocol):
    def default_audit_script_path(self) -> Path: ...
    def default_rerun_script_path(self) -> Path: ...
    def resolve_powershell_host(self) -> str | None: ...
    def load_config_data(self, config_path: Path, powershell_host: str | None) -> dict[str, Any]: ...
    def _first_existing(self, *paths: Path) -> Path: ...
    def _migrate_app_state_path(self, preferred_path: Path) -> None: ...
    def _path_or_none(self, value: Any) -> Path | None: ...
    def _state_root_for_local_base(self, local_base: Path) -> Path: ...


class ConfigDocumentServiceProtocol(Protocol):
    logger: WarningLogger

    def _subprocess_kwargs_hidden(self) -> Mapping[str, Any]: ...
    def resolve_powershell_host(self) -> str | None: ...
    def validate_config_values(self, values: dict[str, Any]) -> tuple[list[str], list[str]]: ...


class ConfigSaveServiceProtocol(Protocol):
    logger: WarningLogger

    def _config_backup_path(self, output_path: Path) -> Path: ...
    def config_profile_path(self, config_path: Path, profile_name: str) -> tuple[str, Path]: ...
    def config_profiles_dir(self, config_path: Path) -> Path: ...
    def load_config_data(self, config_path: Path, powershell_host: str | None) -> dict[str, Any]: ...
    def normalize_profile_name(self, raw_name: str) -> str: ...
    def save_config_document(
        self,
        output_path: Path,
        document_text: str,
        create_backup: bool,
        *,
        config_values: dict[str, Any] | None = None,
        powershell_host: str | None = None,
    ) -> ConfigSaveResult: ...
    def validate_config_document_for_save(
        self,
        document_text: str,
        *,
        config_values: dict[str, Any] | None = None,
        powershell_host: str | None = None,
    ) -> tuple[list[str], list[str]]: ...


class RerunMetadataServiceProtocol(PowerShellHostServiceProtocol, Protocol):
    logger: WarningLogger

    def _build_launch_environment(self) -> Mapping[str, str]: ...
    def _first_existing(self, *paths: Path) -> Path: ...
    def _rerun_source_metadata_script_path(self, resolved: ResolvedPaths) -> Path: ...
    def _subprocess_kwargs_hidden(self) -> Mapping[str, Any]: ...


class RerunCsvExportServiceProtocol(Protocol):
    def _load_rerun_source_metadata(
        self,
        resolved: ResolvedPaths,
        source_paths: list[Path],
    ) -> dict[str, dict[str, Any]]: ...


class ProcessControlPayloadReadServiceProtocol(Protocol):
    logger: WarningLogger


class ProcessControlFlagAgeServiceProtocol(Protocol):
    def _parse_progress_datetime(self, raw: str) -> datetime | None: ...


class ProcessControlLaunchServiceProtocol(Protocol):
    logger: WarningLogger

    def _read_control_flag_payload(self, flag_path: Path) -> dict[str, Any] | None: ...
    def _control_flag_age_seconds(self, flag_path: Path, payload: dict[str, Any] | None) -> float | None: ...
    def _remove_control_flag(self, flag_path: Path, label: str) -> None: ...
    def _write_control_flag(self, flag_path: Path, label: str) -> dict[str, Any]: ...


class ProcessControlWriteServiceProtocol(Protocol):
    def _remove_control_flag(self, flag_path: Path, label: str) -> None: ...
    def _write_control_flag(self, flag_path: Path, label: str) -> dict[str, Any]: ...


class ActiveJobLaunchRecordServiceProtocol(Protocol):
    logger: WarningLogger
    _last_spawn_stdout_log: Path | None
    _last_spawn_stderr_log: Path | None


class ActiveJobLoggedServiceProtocol(Protocol):
    logger: WarningLogger


class ProcessLaunchServiceProtocol(Protocol):
    app_root: Path

    def _spawn(
        self,
        args: list[str],
        show_console: bool,
        *,
        resolved: ResolvedPaths | None = None,
        job_kind: str = "process",
        mode: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> subprocess.Popen[Any]: ...


class RuntimeArtifactServiceProtocol(Protocol):
    def _state_root_for_local_base(self, local_base: Path) -> Path: ...
    def _normalized_path_key(self, path: Path) -> str: ...


class RuntimeCleanupServiceProtocol(RuntimeArtifactServiceProtocol, Protocol):
    logger: WarningLogger

    def _runtime_artifact_specs(
        self,
        resolved: ResolvedPaths,
        *,
        include_pipeline: bool,
        include_audit: bool,
    ) -> list[tuple[str, Path | None, list[Path]]]: ...
    def _clear_pipeline_progress_artifacts(self, resolved: ResolvedPaths) -> list[str]: ...
    def _clear_audit_progress_artifacts(self, resolved: ResolvedPaths) -> list[str]: ...
    def read_progress(self, resolved: ResolvedPaths) -> dict[str, Any] | None: ...
    def read_audit_progress(self, resolved: ResolvedPaths) -> dict[str, Any] | None: ...
    def is_progress_stale(self, progress: dict[str, Any] | None, *, stale_after_seconds: float) -> bool: ...
    def is_audit_progress_stale(self, audit_progress: dict[str, Any] | None, *, stale_after_seconds: float) -> bool: ...
    def find_related_pipeline_processes(self, resolved: ResolvedPaths) -> list[Any]: ...


class ProcessSpawnServiceProtocol(PowerShellHostServiceProtocol, Protocol):
    logger: InfoWarningLogger
    _last_spawn_stdout_log: Path | None
    _last_spawn_stderr_log: Path | None

    def _build_launch_environment(self) -> Mapping[str, str]: ...
    def _write_active_job_launch_record(
        self,
        proc: subprocess.Popen[Any],
        *,
        resolved: ResolvedPaths | None,
        job_kind: str,
        mode: str,
        command_line: str,
        args: list[str],
        launch_cwd: Path,
        show_console: bool,
        metadata: dict[str, Any],
    ) -> Path | None: ...
    def _verify_spawn_readiness(self, proc: subprocess.Popen[Any], command_line: str) -> None: ...


class QueuePreviewServiceProtocol(Protocol):
    QUEUE_SNAPSHOT_FRESH_SECONDS: float
    _queue_completed_excluded: int
    _queue_source_candidates: int
    _queue_completed_size_mismatches: int
    _queue_completed_identity_mismatches: int
    _queue_completed_unverified: int
    _queue_scan_limited: bool
    _queue_completed_cache_status: str

    def _queue_snapshot_path(self, resolved: ResolvedPaths) -> Path | None: ...
    def _read_queue_snapshot(self, path: Path) -> dict[str, Any] | None: ...
    def _run_queue_dry_run(self, resolved: ResolvedPaths, *, allow_cached_fallback: bool = False) -> dict[str, Any] | None: ...
    def _queue_record_from_snapshot_row(self, row: dict[str, Any]) -> Any: ...


class QueueDryRunServiceProtocol(PowerShellHostServiceProtocol, Protocol):
    QUEUE_DRY_RUN_TIMEOUT_SECONDS: float
    QUEUE_DRY_RUN_OUTPUT_TAIL_LINES: int
    _queue_completed_cache_status: str

    def _queue_snapshot_write_path(self, resolved: ResolvedPaths) -> Path | None: ...
    def _read_queue_snapshot(self, path: Path) -> dict[str, Any] | None: ...
    def _queue_snapshot_is_current_for_request(self, path: Path, snapshot: dict[str, Any], started_at: float) -> bool: ...
    def _build_launch_environment(self) -> Mapping[str, str]: ...
    def _subprocess_kwargs_hidden(self) -> Mapping[str, Any]: ...


class RenamePreviewScriptServiceProtocol(PowerShellHostServiceProtocol, Protocol):
    pass


class RenamePreviewLoadServiceProtocol(Protocol):
    logger: WarningLogger

    def _naming_preview_script_path(self) -> Path | None: ...
    def _subprocess_kwargs_hidden(self) -> Mapping[str, Any]: ...


class RenamePlannerServiceProtocol(Protocol):
    def parse_rename_number(
        self,
        raw: str | int,
        *,
        label: str,
        prefix_pattern: str,
        minimum: int,
        maximum: int,
    ) -> int: ...
    def _movie_filter_options_are_default(self, options: dict[str, bool] | None) -> bool: ...
    def _load_pipeline_movie_name_previews(
        self,
        paths: list[Path],
        *,
        powershell_host: str | None = None,
    ) -> tuple[dict[str, str], str]: ...
    def _load_pipeline_tv_name_previews(
        self,
        paths: list[Path],
        *,
        powershell_host: str | None = None,
    ) -> tuple[dict[str, str], str]: ...
    def _casefold_path(self, path: Path) -> str: ...
    def normalize_plex_filename_component(self, value: str, remove_terms: list[str] | None = None) -> str: ...
    def _apply_tv_episode_title_template(self, file_name: str, *, include_episode_title: bool) -> str: ...
    def _build_tv_rename_name(
        self,
        source: Path,
        *,
        show_name: str,
        season_number: int,
        episode_number: int,
        remove_terms: list[str] | None,
        include_episode_title: bool,
    ) -> str: ...
    def _build_auto_tv_rename_name(
        self,
        source: Path,
        *,
        season_number: int,
        remove_terms: list[str] | None,
        include_episode_title: bool,
    ) -> str: ...
    def _clean_pipeline_movie_name(
        self,
        file_name: str,
        remove_terms: list[str] | None,
        movie_filter_options: dict[str, bool] | None,
        movie_filter_terms: dict[str, list[str]] | None = None,
    ) -> str: ...
    def _build_movie_rename_name(
        self,
        source: Path,
        *,
        movie_title: str,
        movie_year: str,
        remove_terms: list[str] | None,
        movie_filter_options: dict[str, bool] | None,
        movie_filter_terms: dict[str, list[str]] | None = None,
    ) -> str: ...
    def _normalise_manual_final_name(self, source: Path, manual_name: str) -> str: ...
    def _resolve_same_file(self, left: Path, right: Path) -> bool: ...
    def _plan_sidecar_moves(self, source: Path, destination: Path) -> list[dict[str, str]]: ...


class RenameApplyServiceProtocol(Protocol):
    logger: ExceptionWarningLogger

    def _build_rename_operations(self, plan: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def _write_rename_undo_manifest(self, manifest: dict[str, Any], *, root: Path | None = None) -> Path: ...
    def _rename_path_case_safe(self, source: Path, destination: Path) -> None: ...
    def _resolve_same_file(self, left: Path, right: Path) -> bool: ...
    def _pipeline_sidecar_paths_for_destination(self, destination: Path) -> list[Path]: ...
    def _update_pipeline_sidecar_after_rename(self, path: Path, payload: dict[str, Any], destination: Path) -> None: ...
    def rename_override_sidecar_path(self, destination: Path) -> Path: ...
    def _update_rename_sidecar_metadata(self, path: Path, payload: dict[str, Any]) -> None: ...
    def _rollback_rename_operations(self, operations: list[dict[str, Path | str]]) -> list[str]: ...


class StatusSnapshotServiceProtocol(Protocol):
    logger: WarningLogger

    def read_progress(self, resolved: ResolvedPaths) -> dict[str, Any] | None: ...
    def read_audit_progress(self, resolved: ResolvedPaths) -> dict[str, Any] | None: ...
    def latest_matching_file(self, folder: Path | None, pattern: str) -> Path | None: ...
    def latest_failure_json(self, resolved: ResolvedPaths) -> Path | None: ...
    def latest_audit_csv(self, resolved: ResolvedPaths, priority_only: bool) -> Path | None: ...
    def read_log_tail(self, resolved: ResolvedPaths) -> str: ...
    def read_pipeline_events_tail(self, resolved: ResolvedPaths) -> list[dict[str, Any]]: ...
    def _build_status_summary(
        self,
        *,
        resolved: ResolvedPaths,
        progress: dict[str, Any] | None,
        audit_progress: dict[str, Any] | None,
        pipeline_events: list[dict[str, Any]],
        audit_root: str,
        latest_failure_report: Path | None,
        latest_failure_json: Path | None,
        latest_audit_csv: Path | None,
        latest_priority_csv: Path | None,
    ) -> str: ...
    def is_progress_stale(self, progress: dict[str, Any] | None) -> bool: ...
    def _build_current_activity(
        self,
        resolved: ResolvedPaths,
        progress: dict[str, Any] | None,
        log_tail: str,
        pipeline_events: list[dict[str, Any]],
    ) -> str: ...
