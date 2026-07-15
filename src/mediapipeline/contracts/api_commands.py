"""Pydantic contracts for Local API command request payloads.

The Local API wire shape remains owned by the existing routes. These models
describe the known per-route fields while allowing existing additive fields so
the command-handler migration can proceed without breaking WebView callers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, ValidationError, field_validator, model_validator

from mediapipeline.contracts.source_media import SourceMediaInfo


class ApiCommandPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    def to_wire_payload(self) -> dict[str, Any]:
        return dict(self.model_dump(mode="json", exclude_unset=True))


class StrictApiCommandPayload(ApiCommandPayload):
    model_config = ConfigDict(extra="forbid")


class EmptyCommandPayload(ApiCommandPayload):
    pass


class OpenLocationCommandPayload(ApiCommandPayload):
    path: Any = None
    target: Any = None
    location: Any = None
    relative_path: Any = None
    manifest_path: Any = None


class PendingPublishOpenCommandPayload(StrictApiCommandPayload):
    row_key: Any = None
    target: Literal["play_local_file", "local_file", "manifest", "destination_folder", "source_folder"] | None = None

    @model_validator(mode="after")
    def require_row_key_and_target(self) -> PendingPublishOpenCommandPayload:
        if self.row_key is None or (isinstance(self.row_key, str) and not self.row_key.strip()):
            raise ValueError("row_key is required")
        if self.target is None:
            raise ValueError("target is required")
        return self


class PendingPublishRecoveryPlanCommandPayload(StrictApiCommandPayload):
    scope: Literal["all", "selected"] | None = None
    row_key: Any = None

    @model_validator(mode="after")
    def require_row_key_for_selected_scope(self) -> PendingPublishRecoveryPlanCommandPayload:
        if self.scope is None:
            raise ValueError("scope is required")
        if self.scope == "selected" and (
            self.row_key is None or (isinstance(self.row_key, str) and not self.row_key.strip())
        ):
            raise ValueError("row_key is required when scope is selected")
        return self


class DiagnosticsTdarrMatrixAuditCommandPayload(StrictApiCommandPayload):
    action: Any = None
    confirm_delete_full_matrix: StrictBool | None = None


class DiagnosticsTdarrMatrixEvidenceOpenCommandPayload(StrictApiCommandPayload):
    run_id: Any = None
    finding_key: Any = None
    target: Any = None


class DiagnosticsTdarrMatrixRerunCommandPayload(StrictApiCommandPayload):
    source_run_id: Any = None
    selection: Any = None
    finding_keys: Any = None


class QueuePriorityCommandPayload(ApiCommandPayload):
    path: Any = None
    level: Any = None
    reason: Any = None
    position: Any = None
    items: Any = None
    clear_all: Any = None


class QueueStrategyCommandPayload(ApiCommandPayload):
    strategy: Any = None


class QueueScanCommandPayload(StrictApiCommandPayload):
    mode: Any = None
    force: StrictBool | None = None
    scope: Any = None
    reason: Any = None


class QueueFileOverridesCommandPayload(ApiCommandPayload):
    path: Any = None
    audio: Any = None
    subtitles: Any = None
    routing: Any = None
    video: Any = None
    clear: Any = None
    clear_all: Any = None
    clear_fields: Any = None


class QueueFileOverridesRoutePreviewCommandPayload(StrictApiCommandPayload):
    path: Any = None
    proposed_override: Any = None


class QueueFileOverridesSeriesPreviewCommandPayload(StrictApiCommandPayload):
    path: Any = None
    proposed_override: Any = None


class QueueFileOverridesSeriesApplyCommandPayload(StrictApiCommandPayload):
    path: Any = None
    proposed_override: Any = None
    confirm_apply: StrictBool | None = None
    preview_fingerprint: Any = None


class QueueFileOverridesSeriesClearPreviewCommandPayload(StrictApiCommandPayload):
    path: Any = None


class QueueFileOverridesSeriesClearApplyCommandPayload(StrictApiCommandPayload):
    path: Any = None
    confirm_apply: StrictBool | None = None
    preview_fingerprint: Any = None


class QueueFileOverridesRemuxPilotPromoteCommandPayload(StrictApiCommandPayload):
    pilot_source_paths: Any = None
    confirm_apply: StrictBool | None = None
    reason: Any = None


class QueueFileOverridesFolderPreviewCommandPayload(StrictApiCommandPayload):
    folder_path: Any = None
    proposed_override: Any = None
    options: Any = None


class QueueFileOverridesFolderRuleCommandPayload(StrictApiCommandPayload):
    folder_path: Any = None
    override: Any = None
    confirmation: Any = None
    clear: Any = None


class SettingsCommandPayload(ApiCommandPayload):
    values: Any = None
    patch: Any = None
    changes: Any = None
    removed_keys: Any = None
    profile_name: Any = None
    reload: Any = None


class SettingsPreviewPatchCommandPayload(StrictApiCommandPayload):
    changes: Any = None
    remove_keys: Any = None
    library_profile_resets: Any = None


class SettingsSavePatchCommandPayload(StrictApiCommandPayload):
    changes: Any = None
    remove_keys: Any = None
    library_profile_resets: Any = None
    review_confirmation: Any = None
    confirm_save: StrictBool | None = None


class SettingsImportPsd1PreviewCommandPayload(StrictApiCommandPayload):
    pass


class SettingsImportPsd1CommandPayload(StrictApiCommandPayload):
    confirm_import: StrictBool | None = None


class SettingsPipelinePlanPreviewCommandPayload(StrictApiCommandPayload):
    source_media: SourceMediaInfo
    changes: dict[str, Any] = Field(default_factory=dict)
    remove_keys: list[Any] = Field(default_factory=list)

    def to_wire_payload(self) -> dict[str, Any]:
        return dict(self.model_dump(mode="json"))


class PresetLibraryValidateCommandPayload(StrictApiCommandPayload):
    preset_v2: Any = None


class PresetLibraryCompareCommandPayload(StrictApiCommandPayload):
    left_id: Any = None
    right_id: Any = None
    left_preset_v2: Any = None
    right_preset_v2: Any = None


class PresetLibraryImportPreviewCommandPayload(StrictApiCommandPayload):
    records: Any = None


class PresetLibrarySaveCommandPayload(StrictApiCommandPayload):
    id: Any = None
    name: Any = None
    description: Any = None
    tags: Any = None
    source: Any = None
    imported_from: Any = None
    preset_v2: Any = None
    confirm_save: StrictBool | None = None


class PresetLibraryExportCommandPayload(StrictApiCommandPayload):
    id: Any = None
    preset_v2: Any = None


class PresetLibraryApplyPreviewCommandPayload(StrictApiCommandPayload):
    id: Any = None
    preset_v2: Any = None


class PresetLibraryApplyCommandPayload(StrictApiCommandPayload):
    id: Any = None
    preset_v2: Any = None
    confirm_apply: StrictBool | None = None

    @model_validator(mode="after")
    def require_confirm_apply(self) -> PresetLibraryApplyCommandPayload:
        if self.confirm_apply is not True:
            raise ValueError("confirm_apply must be true")
        return self


class SettingsWizardCommandPayload(StrictApiCommandPayload):
    wizard: Any = None
    confirm_save: StrictBool | None = None
    review_confirmation: Any = None


class SettingsBrowsePathCommandPayload(ApiCommandPayload):
    setting_key: Any = None
    selection_mode: Any = None
    initial_path: Any = None


class ScheduleCommandPayload(StrictApiCommandPayload):
    enabled: StrictBool | None = None
    day_windows: Any = None
    grid: Any = None
    confirm_save: StrictBool | None = None
    days: Any = None
    start_time: Any = None
    stop_time: Any = None
    timezone: Any = None


class RenameCommandPayload(ApiCommandPayload):
    path: Any = None
    paths: Any = None
    media_type: Any = None
    selection_mode: Any = None
    initial_path: Any = None
    confirm_apply: Any = None
    selected_ids: Any = None


class RenameApplyCommandPayload(StrictApiCommandPayload):
    paths: Any = None
    mode: Any = None
    show_name: Any = None
    season: Any = None
    season_value: Any = None
    start_episode: Any = None
    start_episode_value: Any = None
    movie_title: Any = None
    movie_year: Any = None
    remove_terms: Any = None
    remove_terms_text: Any = None
    movie_filter_options: Any = None
    movie_filter_terms: Any = None
    movie_filter_terms_enabled: Any = None
    final_name_overrides: Any = None
    rename_sidecars: StrictBool | None = None
    force_pipeline_name: StrictBool | None = None
    force_pipeline_name_overrides: dict[str, StrictBool] | None = None
    powershell_host: Any = None
    use_pipeline_naming_preview: StrictBool | None = None
    template_preset: Any = None
    selected_sources: Any = None
    confirm_apply: StrictBool | None = None
    allow_outside_configured_roots: StrictBool | None = None
    preview_fingerprint: StrictStr

    @field_validator("preview_fingerprint")
    @classmethod
    def _require_preview_fingerprint(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("preview_fingerprint is required")
        return value


class RenameUndoCommandPayload(StrictApiCommandPayload):
    undo_manifest: Any = None
    confirm_undo: StrictBool | None = None
    rename_undo_manifest_root: Any = Field(default=None, alias="_rename_undo_manifest_root")

    def to_wire_payload(self) -> dict[str, Any]:
        return dict(self.model_dump(mode="json", by_alias=True, exclude_unset=True))


class RenameFilterCaseCommandPayload(StrictApiCommandPayload):
    case_id: Any = None
    source_folder: Any = None
    source_file: Any = None
    expected_name: Any = None
    expected_show: Any = None
    expected_clean_folder: Any = None
    expected_season: Any = None
    season_number: Any = None
    status: Any = None
    notes: Any = None
    confirm_append: StrictBool | None = None


class ProcessControlCommandPayload(ApiCommandPayload):
    action: Any = None
    mode: Any = None
    dry_run: Any = None
    force_active_work_shutdown: Any = None


class RerunScopePayload(StrictApiCommandPayload):
    enabled_only: StrictBool | None = None
    skip_blocked: StrictBool | None = None
    skip_warning_rows: StrictBool | None = None
    first_n: Any = None
    issue_filter: Any = None
    bucket_filter: Any = None
    issue_filters: Any = None
    bucket_filters: Any = None
    status_filters: Any = None
    preview_limit: Any = None


class RerunPreviewCommandPayload(StrictApiCommandPayload):
    csv_path: Any = None
    execution_mode: Any = None
    destination_mode: Any = None
    original_policy: Any = None
    window_size: Any = None
    collision_policy: Any = None
    stage_mode: Any = None
    original_mode: Any = None
    return_mode: Any = None
    confirm_replace_final: StrictBool | None = None
    confirm_source_overwrite: StrictBool | None = None
    confirm_original_policy: StrictBool | None = None
    confirm_delete_original: StrictBool | None = None
    scope: RerunScopePayload | None = None
    preview_limit: Any = None
    enabled_only: StrictBool | None = None
    skip_blocked: StrictBool | None = None
    skip_warning_rows: StrictBool | None = None
    first_n: Any = None
    issue_filter: Any = None
    bucket_filter: Any = None
    issue_filters: Any = None
    bucket_filters: Any = None
    status_filters: Any = None


class RerunStartCommandPayload(RerunPreviewCommandPayload):
    dry_run: StrictBool | None = None
    plan_only: StrictBool | None = None
    show_console: StrictBool | None = None


class RerunNetworkStartDryRunCommandPayload(RerunPreviewCommandPayload):
    reason: Any = None
    minimum_worker_count: Any = None
    min_worker_count: Any = None


class RerunNetworkStartCommandPayload(RerunNetworkStartDryRunCommandPayload):
    dry_run_fingerprint: Any = None
    confirm_start: StrictBool | None = None

    @model_validator(mode="after")
    def require_start_confirmation_fields(self) -> RerunNetworkStartCommandPayload:
        if self.confirm_start is not True:
            raise ValueError("confirm_start must be true")
        if self.dry_run_fingerprint is None or (
            isinstance(self.dry_run_fingerprint, str) and not self.dry_run_fingerprint.strip()
        ):
            raise ValueError("dry_run_fingerprint is required")
        return self


class RerunNetworkRetryCommandPayload(StrictApiCommandPayload):
    batch_id: StrictStr = Field(min_length=1, max_length=200)
    row_key: StrictStr = Field(min_length=1, max_length=300)
    request_id: StrictStr = Field(min_length=1, max_length=200)
    reason: StrictStr = Field(min_length=1, max_length=500)
    confirm_retry: StrictBool

    @field_validator("batch_id", "row_key", "request_id", "reason")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("value must not be blank")
        return text

    @model_validator(mode="after")
    def require_retry_confirmation(self) -> RerunNetworkRetryCommandPayload:
        if self.confirm_retry is not True:
            raise ValueError("confirm_retry must be true")
        return self


class RerunControlCommandPayload(StrictApiCommandPayload):
    action: Literal["stop_after_current", "pause"] | None = None
    confirm_stop: StrictBool | None = None
    confirm_pause: StrictBool | None = None

    @model_validator(mode="after")
    def require_stop_after_current_confirmation(self) -> RerunControlCommandPayload:
        if self.action == "stop_after_current" and self.confirm_stop is not True:
            raise ValueError("confirm_stop must be true")
        if self.action == "pause" and self.confirm_pause is not True:
            raise ValueError("confirm_pause must be true")
        if self.action not in {"stop_after_current", "pause"}:
            raise ValueError("action must be stop_after_current or pause")
        return self


class RerunContinueCommandPayload(StrictApiCommandPayload):
    manifest_key: StrictStr = Field(min_length=1, max_length=200)
    request_id: StrictStr = Field(min_length=1, max_length=200)
    confirm_continue: StrictBool | None = None

    @field_validator("manifest_key", "request_id")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("value must not be blank")
        return text

    @model_validator(mode="after")
    def require_continue_confirmation(self) -> RerunContinueCommandPayload:
        if self.confirm_continue is not True:
            raise ValueError("confirm_continue must be true")
        return self


class RerunOpenCommandPayload(StrictApiCommandPayload):
    target: Any = None
    row_key: Any = None
    csv_key: Any = None


class RerunPromoteDryRunCommandPayload(StrictApiCommandPayload):
    row_key: Any = None


class RerunPromoteCommandPayload(RerunPromoteDryRunCommandPayload):
    dry_run_fingerprint: Any = None
    confirm_promote: StrictBool | None = None


class NetworkLifecycleDryRunCommandPayload(StrictApiCommandPayload):
    reason: Any = None


class RepairReconcileDryRunCommandPayload(StrictApiCommandPayload):
    scope: Literal["all", "selected"] | None = None
    row_key: Any = None
    limit: Any = None
    reason: Any = None

    @model_validator(mode="after")
    def require_row_key_for_selected_scope(self) -> RepairReconcileDryRunCommandPayload:
        if self.scope == "selected" and (
            self.row_key is None or (isinstance(self.row_key, str) and not self.row_key.strip())
        ):
            raise ValueError("row_key is required when scope is selected")
        return self


class RepairReconcileApplyCommandPayload(StrictApiCommandPayload):
    scope: Literal["all", "selected"] | None = None
    row_key: Any = None
    limit: Any = None
    reason: Any = None
    dry_run_fingerprint: Any = None
    confirm_apply: StrictBool | None = None

    @model_validator(mode="after")
    def require_confirmation_fields(self) -> RepairReconcileApplyCommandPayload:
        if self.scope == "selected" and (
            self.row_key is None or (isinstance(self.row_key, str) and not self.row_key.strip())
        ):
            raise ValueError("row_key is required when scope is selected")
        if self.confirm_apply is not True:
            raise ValueError("confirm_apply must be true")
        if self.dry_run_fingerprint is None or (isinstance(self.dry_run_fingerprint, str) and not self.dry_run_fingerprint.strip()):
            raise ValueError("dry_run_fingerprint is required")
        return self


class StartupReconciliationDryRunCommandPayload(StrictApiCommandPayload):
    scope: Literal["all"] | None = None
    limit: Any = None
    reason: Any = None


class NetworkLifecycleStartCommandPayload(StrictApiCommandPayload):
    confirm_start: StrictBool
    reason: Any = None


class NetworkLifecycleStopCommandPayload(StrictApiCommandPayload):
    confirm_stop: StrictBool
    reason: Any = None


class NetworkWorkerTestConnectionCommandPayload(StrictApiCommandPayload):
    timeout_seconds: Any = None


class NetworkWorkerDiscoverCoordinatorsCommandPayload(StrictApiCommandPayload):
    timeout_seconds: Any = None


class NetworkCoordinatorJoinBlobCommandPayload(StrictApiCommandPayload):
    coordinator_url: Any = None
    confirm_create: StrictBool | None = None
    rotate_token: StrictBool | None = None
    confirm_rotate: StrictBool | None = None


class NetworkWorkerJoinClusterCommandPayload(StrictApiCommandPayload):
    join_blob: Any = None
    confirm_import: StrictBool | None = None
    timeout_seconds: Any = None


class PathPickerBrowseCommandPayload(StrictApiCommandPayload):
    target_key: Any = None
    selection_mode: Any = None
    initial_path: Any = None
    file_filter: Any = None


class AuditScorePolicyCommandPayload(StrictApiCommandPayload):
    policy: Any = None
    reset: StrictBool | None = None


class AuditIgnoreCommandPayload(StrictApiCommandPayload):
    action: Any = None
    row_keys: Any = None
    paths: Any = None
    reason: Any = None
    priority_only: StrictBool | None = None
    limit: Any = None


class AuditExportRerunCsvCommandPayload(StrictApiCommandPayload):
    row_keys: Any = None
    priority_only: StrictBool | None = None
    limit: Any = None


class AuditStartCommandPayload(StrictApiCommandPayload):
    library_root: Any = None
    library_roots: Any = None
    source_ids: Any = None
    include_sidecars: StrictBool | None = None
    show_console: StrictBool | None = None


class PipelineControlCommandPayload(StrictApiCommandPayload):
    action: Any = None
    confirm_force_stop: StrictBool | None = None

    @model_validator(mode="after")
    def require_force_stop_confirmation(self) -> PipelineControlCommandPayload:
        if str(self.action or "").strip().casefold() == "kill" and self.confirm_force_stop is not True:
            raise ValueError("confirm_force_stop must be true for action=kill")
        return self


class PipelineBrowseFileCommandPayload(StrictApiCommandPayload):
    selection_mode: Any = None
    initial_path: Any = None


class PipelineStartCommandPayload(StrictApiCommandPayload):
    mode: Literal["once", "continuous", "validate", "drain_pending_pushes"]
    sleep_seconds: StrictInt | None = Field(default=None, ge=1)
    show_config: StrictBool | None = None
    show_console: StrictBool | None = None
    single_file: StrictStr | None = None
    schedule_override: Literal["", "run_once", "ignore"] | None = None


class AuditStopCommandPayload(StrictApiCommandPayload):
    confirm_stop: StrictBool | None = None
    reason: Any = None

    @model_validator(mode="after")
    def require_confirm_stop(self) -> AuditStopCommandPayload:
        if self.confirm_stop is not True:
            raise ValueError("confirm_stop must be true")
        return self


class AuditSourcesCommandPayload(StrictApiCommandPayload):
    action: Any = None
    source_id: Any = None
    path: Any = None
    label: Any = None
    enabled: StrictBool | None = None


class AuditSourcesScanCommandPayload(StrictApiCommandPayload):
    scope: Any = None
    source_id: Any = None
    source_ids: Any = None
    path: Any = None
    max_entries: Any = None


class BackendShutdownCommandPayload(StrictApiCommandPayload):
    reason: Any = None
    force_active_work_shutdown: StrictBool | None = None


class LifecycleReconciliationDryRunCommandPayload(StrictApiCommandPayload):
    reason: Any = None


class LifecycleReconciliationApplyCommandPayload(StrictApiCommandPayload):
    confirm_apply: StrictBool | None = None
    dry_run_fingerprint: Any = None
    reason: Any = None

    @model_validator(mode="after")
    def require_confirmation_fields(self) -> LifecycleReconciliationApplyCommandPayload:
        if self.confirm_apply is not True:
            raise ValueError("confirm_apply must be true")
        if self.dry_run_fingerprint is None or (
            isinstance(self.dry_run_fingerprint, str) and not self.dry_run_fingerprint.strip()
        ):
            raise ValueError("dry_run_fingerprint is required")
        return self


class UiPreferencesCommandPayload(StrictApiCommandPayload):
    storage: Any = None
    source_surface: Any = None


class MaintenanceReleaseDryRunCommandPayload(StrictApiCommandPayload):
    destination_root: Any = None
    zip_package: StrictBool | None = None
    verify: StrictBool | None = None
    include_tests: StrictBool | None = None
    include_dev_docs: StrictBool | None = None
    include_optional_tools: StrictBool | None = None
    include_tool_docs: StrictBool | None = None
    include_tauri_preview_binary: StrictBool | None = None
    keep_personal_config: StrictBool | None = None
    force: StrictBool | None = None
    timeout_seconds: Any = None


class MaintenanceReleaseBuildCommandPayload(StrictApiCommandPayload):
    destination_root: Any = None
    zip_package: StrictBool | None = None
    verify: StrictBool | None = None
    include_tests: StrictBool | None = None
    include_dev_docs: StrictBool | None = None
    include_optional_tools: StrictBool | None = None
    include_tool_docs: StrictBool | None = None
    include_tauri_preview_binary: StrictBool | None = None
    keep_personal_config: StrictBool | None = None
    force: StrictBool | None = None
    confirm_create: StrictBool | None = None
    timeout_seconds: Any = None


class MaintenanceDependencyAtlasCommandPayload(StrictApiCommandPayload):
    timeout_seconds: Any = None
    min_overview_edge_count: Any = None
    min_overview_files: Any = None


class MaintenanceDependencyAtlasOpenFolderCommandPayload(StrictApiCommandPayload):
    pass


class MaintenanceCompletedBackfillDryRunCommandPayload(StrictApiCommandPayload):
    timeout_seconds: Any = None


class MaintenanceRetentionDryRunCommandPayload(StrictApiCommandPayload):
    limit: Any = None
    reason: Any = None


class MaintenanceStateJournalArchiveCommandPayload(StrictApiCommandPayload):
    confirm_archive: StrictBool | None = None
    reason: Any = None


class MaintenanceSupportExportCommandPayload(StrictApiCommandPayload):
    reason: Any = None
    include_recent_logs: StrictBool | None = None
    max_log_bytes: Any = None


class MetricsSourcesCommandPayload(StrictApiCommandPayload):
    action: Any = None
    path: Any = None
    source_id: Any = None
    label: Any = None
    enabled: StrictBool | None = None


class MetricsBackfillCommandPayload(StrictApiCommandPayload):
    scope: Any = None
    source_id: Any = None
    path: Any = None
    max_sidecars: Any = None


class SampleValidationCommandPayload(ApiCommandPayload):
    shell: Any = None
    source_path: Any = None
    output_path: Any = None
    sample_label: Any = None
    sample_category: Any = None
    proof_strength: Any = None
    operator_decision: Any = None
    checks: Any = None
    evidence: Any = None
    operator_notes: Any = None
    sample_path: Any = None
    worksheet_path: Any = None
    result: Any = None
    notes: Any = None


class SubtitleQaPreviewCommandPayload(StrictApiCommandPayload):
    id: Any = None
    row_key: Any = None
    path: Any = None
    source_path: Any = None
    output_path: Any = None
    scope: Any = None
    limit: Any = None


class FailureCommandPayload(StrictApiCommandPayload):
    dry_run: StrictBool | None = None
    confirm: StrictBool | None = None
    confirm_clear: StrictBool | None = None
    scope: Any = None
    marker_path: Any = None
    marker_paths: Any = None
    source_json: Any = None
    journal_key: Any = None


class FailureArchiveEvidenceCommandPayload(StrictApiCommandPayload):
    scope: Any = None
    include_markers: StrictBool | None = None
    include_reports: StrictBool | None = None
    dry_run: StrictBool | None = None
    dry_run_fingerprint: Any = None
    confirm_archive: StrictBool | None = None
    reason: Any = None
    journal_key: Any = None


class FailureOpenCommandPayload(StrictApiCommandPayload):
    row_key: Any = None
    target: Any = None
    source_kind: Any = None


class FailureArtifactCleanupCommandPayload(StrictApiCommandPayload):
    dry_run: StrictBool | None = None
    dry_run_fingerprint: Any = None
    confirm_delete: StrictBool | None = None
    reason: Any = None
    retention_days: Any = None
    target_gb: Any = None
    artifact_paths: Any = None


class FailureLifecycleCommandPayload(StrictApiCommandPayload):
    journal_key: Any = None
    transition: Any = None
    step_id: Any = None
    operator_note: Any = None
    reason: Any = None
    dry_run: StrictBool | None = None
    dry_run_fingerprint: Any = None
    confirm_transition: StrictBool | None = None


class FinalLibraryPromoteQueueCommandPayload(StrictApiCommandPayload):
    confirm_promote: StrictBool | None = None
    row_keys: Any = None


class FinalLibraryPromotionRunCommandPayload(StrictApiCommandPayload):
    run_id: Any = None


COMMAND_ROUTE_PAYLOAD_MODELS: dict[str, type[ApiCommandPayload]] = {
    "/api/rename/preview": RenameCommandPayload,
    "/api/rename/browse": RenameCommandPayload,
    "/api/rename/filter-cases": RenameFilterCaseCommandPayload,
    "/api/rename/apply": RenameApplyCommandPayload,
    "/api/rename/undo": RenameUndoCommandPayload,
    "/api/diagnostics/open": OpenLocationCommandPayload,
    "/api/diagnostics/encoder-capabilities/refresh": EmptyCommandPayload,
    "/api/diagnostics/tdarr-matrix-audit": DiagnosticsTdarrMatrixAuditCommandPayload,
    "/api/diagnostics/tdarr-matrix/evidence/open": DiagnosticsTdarrMatrixEvidenceOpenCommandPayload,
    "/api/diagnostics/tdarr-matrix/rerun": DiagnosticsTdarrMatrixRerunCommandPayload,
    "/api/queue/scan": QueueScanCommandPayload,
    "/api/queue/open": OpenLocationCommandPayload,
    "/api/queue/priority": QueuePriorityCommandPayload,
    "/api/queue/strategy": QueueStrategyCommandPayload,
    "/api/queue/file-overrides": QueueFileOverridesCommandPayload,
    "/api/queue/file-overrides/route-preview": QueueFileOverridesRoutePreviewCommandPayload,
    "/api/queue/file-overrides/series-preview": QueueFileOverridesSeriesPreviewCommandPayload,
    "/api/queue/file-overrides/series-apply": QueueFileOverridesSeriesApplyCommandPayload,
    "/api/queue/file-overrides/series-clear-preview": QueueFileOverridesSeriesClearPreviewCommandPayload,
    "/api/queue/file-overrides/series-clear-apply": QueueFileOverridesSeriesClearApplyCommandPayload,
    "/api/queue/file-overrides/remux-pilot-promote": QueueFileOverridesRemuxPilotPromoteCommandPayload,
    "/api/queue/file-overrides/folder-preview": QueueFileOverridesFolderPreviewCommandPayload,
    "/api/queue/file-overrides/folder-rule": QueueFileOverridesFolderRuleCommandPayload,
    "/api/failures/clear": FailureCommandPayload,
    "/api/failures/archive-evidence": FailureArchiveEvidenceCommandPayload,
    "/api/failures/open": FailureOpenCommandPayload,
    "/api/failures/artifacts/cleanup": FailureArtifactCleanupCommandPayload,
    "/api/failures/lifecycle": FailureLifecycleCommandPayload,
    "/api/pending-publish/open": PendingPublishOpenCommandPayload,
    "/api/pending-publish/recovery-plan": PendingPublishRecoveryPlanCommandPayload,
    "/api/pending-publish/repair-manifest-dry-run": RepairReconcileDryRunCommandPayload,
    "/api/pending-publish/repair-manifest": RepairReconcileApplyCommandPayload,
    "/api/pending-publish/reconcile-orphan-payloads-dry-run": RepairReconcileDryRunCommandPayload,
    "/api/pending-publish/reconcile-orphan-payloads": RepairReconcileApplyCommandPayload,
    "/api/startup/reconcile-dry-run": StartupReconciliationDryRunCommandPayload,
    "/api/completed/open": OpenLocationCommandPayload,
    "/api/completed/reconcile-manifest-dry-run": RepairReconcileDryRunCommandPayload,
    "/api/completed/reconcile-manifest": RepairReconcileApplyCommandPayload,
    "/api/completed/repair-sidecar-metadata-dry-run": RepairReconcileDryRunCommandPayload,
    "/api/completed/repair-sidecar-metadata": RepairReconcileApplyCommandPayload,
    "/api/subtitle-qa/preview": SubtitleQaPreviewCommandPayload,
    "/api/settings/validate": SettingsCommandPayload,
    "/api/settings/preset-library/validate": PresetLibraryValidateCommandPayload,
    "/api/settings/preset-library/compare": PresetLibraryCompareCommandPayload,
    "/api/settings/preset-library/import-preview": PresetLibraryImportPreviewCommandPayload,
    "/api/settings/preset-library/save": PresetLibrarySaveCommandPayload,
    "/api/settings/preset-library/export": PresetLibraryExportCommandPayload,
    "/api/settings/preset-library/apply-preview": PresetLibraryApplyPreviewCommandPayload,
    "/api/settings/preset-library/apply": PresetLibraryApplyCommandPayload,
    "/api/settings/browse-path": SettingsBrowsePathCommandPayload,
    "/api/settings/preview-patch": SettingsPreviewPatchCommandPayload,
    "/api/settings/pipeline-plan-preview": SettingsPipelinePlanPreviewCommandPayload,
    "/api/settings/save-patch": SettingsSavePatchCommandPayload,
    "/api/settings/import-psd1-preview": SettingsImportPsd1PreviewCommandPayload,
    "/api/settings/import-psd1": SettingsImportPsd1CommandPayload,
    "/api/settings/wizard/validate-paths": SettingsWizardCommandPayload,
    "/api/settings/wizard/validate-tools": SettingsWizardCommandPayload,
    "/api/settings/wizard/probe-hardware": SettingsWizardCommandPayload,
    "/api/settings/wizard/validate-workers": SettingsWizardCommandPayload,
    "/api/settings/wizard/preview": SettingsWizardCommandPayload,
    "/api/settings/wizard/save": SettingsWizardCommandPayload,
    "/api/schedule/preview": ScheduleCommandPayload,
    "/api/schedule/save": ScheduleCommandPayload,
    "/api/maintenance/release-dry-run": MaintenanceReleaseDryRunCommandPayload,
    "/api/maintenance/release-build": MaintenanceReleaseBuildCommandPayload,
    "/api/maintenance/completed-backfill-dry-run": MaintenanceCompletedBackfillDryRunCommandPayload,
    "/api/maintenance/retention-dry-run": MaintenanceRetentionDryRunCommandPayload,
    "/api/maintenance/archive-state-journals": MaintenanceStateJournalArchiveCommandPayload,
    "/api/maintenance/dependency-atlas": MaintenanceDependencyAtlasCommandPayload,
    "/api/maintenance/dependency-atlas/open-folder": MaintenanceDependencyAtlasOpenFolderCommandPayload,
    "/api/maintenance/support-export": MaintenanceSupportExportCommandPayload,
    "/api/metrics/sources": MetricsSourcesCommandPayload,
    "/api/metrics/backfill": MetricsBackfillCommandPayload,
    "/api/settings/reload": EmptyCommandPayload,
    "/api/sample-validation/preview": SampleValidationCommandPayload,
    "/api/sample-validation/append": SampleValidationCommandPayload,
    "/api/network/coordinator/start-dry-run": NetworkLifecycleDryRunCommandPayload,
    "/api/network/coordinator/stop-dry-run": NetworkLifecycleDryRunCommandPayload,
    "/api/network/coordinator/join-blob": NetworkCoordinatorJoinBlobCommandPayload,
    "/api/network/coordinator/start": NetworkLifecycleStartCommandPayload,
    "/api/network/coordinator/stop": NetworkLifecycleStopCommandPayload,
    "/api/network/worker/start-dry-run": NetworkLifecycleDryRunCommandPayload,
    "/api/network/worker/stop-dry-run": NetworkLifecycleDryRunCommandPayload,
    "/api/network/worker/test-connection": NetworkWorkerTestConnectionCommandPayload,
    "/api/network/worker/discover-coordinators": NetworkWorkerDiscoverCoordinatorsCommandPayload,
    "/api/network/worker/join-cluster": NetworkWorkerJoinClusterCommandPayload,
    "/api/network/worker/start": NetworkLifecycleStartCommandPayload,
    "/api/network/worker/stop": NetworkLifecycleStopCommandPayload,
    "/api/path-picker/browse": PathPickerBrowseCommandPayload,
    "/api/pipeline/control": PipelineControlCommandPayload,
    "/api/pipeline/browse-file": PipelineBrowseFileCommandPayload,
    "/api/pipeline/start": PipelineStartCommandPayload,
    "/api/audit/start": AuditStartCommandPayload,
    "/api/audit/stop": AuditStopCommandPayload,
    "/api/audit/sources": AuditSourcesCommandPayload,
    "/api/audit/sources/scan": AuditSourcesScanCommandPayload,
    "/api/audit/score-policy": AuditScorePolicyCommandPayload,
    "/api/audit/ignore": AuditIgnoreCommandPayload,
    "/api/audit/export-rerun-csv": AuditExportRerunCsvCommandPayload,
    "/api/rerun/preview": RerunPreviewCommandPayload,
    "/api/rerun/network-preview": RerunPreviewCommandPayload,
    "/api/rerun/network/start-dry-run": RerunNetworkStartDryRunCommandPayload,
    "/api/rerun/network/start": RerunNetworkStartCommandPayload,
    "/api/rerun/network/retry": RerunNetworkRetryCommandPayload,
    "/api/rerun/start": RerunStartCommandPayload,
    "/api/rerun/control": RerunControlCommandPayload,
    "/api/rerun/continue": RerunContinueCommandPayload,
    "/api/rerun/open": RerunOpenCommandPayload,
    "/api/rerun/promote-dry-run": RerunPromoteDryRunCommandPayload,
    "/api/rerun/promote": RerunPromoteCommandPayload,
    "/api/backend/lifecycle/reconcile-dry-run": LifecycleReconciliationDryRunCommandPayload,
    "/api/backend/lifecycle/reconcile": LifecycleReconciliationApplyCommandPayload,
    "/api/backend/shutdown": BackendShutdownCommandPayload,
    "/api/ui-preferences": UiPreferencesCommandPayload,
    "/api/final-library-promotion/promote-queue": FinalLibraryPromoteQueueCommandPayload,
    "/api/final-library-promotion/pause": FinalLibraryPromotionRunCommandPayload,
    "/api/final-library-promotion/resume": FinalLibraryPromotionRunCommandPayload,
}


def command_model_for_route(route: str) -> type[ApiCommandPayload]:
    return COMMAND_ROUTE_PAYLOAD_MODELS.get(route, ApiCommandPayload)


def validate_api_command_payload(route: str, payload: dict[str, Any]) -> dict[str, Any]:
    model = command_model_for_route(route)
    try:
        return model.model_validate(payload).to_wire_payload()
    except ValidationError:
        raise
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid command payload for {route}: {exc}") from exc


__all__ = [
    "ApiCommandPayload",
    "COMMAND_ROUTE_PAYLOAD_MODELS",
    "command_model_for_route",
    "validate_api_command_payload",
]
