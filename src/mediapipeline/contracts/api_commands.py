"""Pydantic contracts for Local API command request payloads.

The Local API wire shape remains owned by the existing routes. These models
describe the known per-route fields while allowing existing additive fields so
the command-handler migration can proceed without breaking WebView callers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

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


class DiagnosticsTdarrMatrixAuditCommandPayload(StrictApiCommandPayload):
    action: Any = None


class DiagnosticsTdarrMatrixEvidenceOpenCommandPayload(StrictApiCommandPayload):
    run_id: Any = None
    finding_key: Any = None
    target: Any = None


class DiagnosticsTdarrMatrixRerunCommandPayload(StrictApiCommandPayload):
    source_run_id: Any = None
    selection: Any = None
    finding_keys: Any = None


class QueuePriorityItemPayload(ApiCommandPayload):
    path: Any = None
    level: Any = None
    reason: Any = None
    position: Any = None


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
    confirm_save: StrictBool | None = None


class SettingsPipelinePlanPreviewCommandPayload(StrictApiCommandPayload):
    source_media: SourceMediaInfo
    changes: dict[str, Any] = Field(default_factory=dict)
    remove_keys: list[Any] = Field(default_factory=list)

    def to_wire_payload(self) -> dict[str, Any]:
        return dict(self.model_dump(mode="json"))


class SettingsWizardCommandPayload(StrictApiCommandPayload):
    wizard: Any = None
    confirm_save: StrictBool | None = None


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
    rename_sidecars: Any = None
    force_pipeline_name: Any = None
    force_pipeline_name_overrides: Any = None
    powershell_host: Any = None
    use_pipeline_naming_preview: Any = None
    template_preset: Any = None
    selected_sources: Any = None
    confirm_apply: Any = None
    allow_outside_configured_roots: Any = None


class ProcessControlCommandPayload(ApiCommandPayload):
    action: Any = None
    mode: Any = None
    dry_run: Any = None
    force_active_work_shutdown: Any = None


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


class PipelineControlCommandPayload(StrictApiCommandPayload):
    action: Any = None


class PipelineBrowseFileCommandPayload(StrictApiCommandPayload):
    selection_mode: Any = None
    initial_path: Any = None


class PipelineStartCommandPayload(StrictApiCommandPayload):
    mode: Any = None
    sleep_seconds: Any = None
    show_config: Any = None
    show_console: Any = None
    single_file: Any = None
    schedule_override: Any = None


class BackendShutdownCommandPayload(StrictApiCommandPayload):
    reason: Any = None
    force_active_work_shutdown: StrictBool | None = None


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
    keep_personal_config: StrictBool | None = None
    timeout_seconds: Any = None


class MaintenanceReleaseBuildCommandPayload(StrictApiCommandPayload):
    destination_root: Any = None
    zip_package: StrictBool | None = None
    verify: StrictBool | None = None
    include_tests: StrictBool | None = None
    include_dev_docs: StrictBool | None = None
    include_optional_tools: StrictBool | None = None
    include_tool_docs: StrictBool | None = None
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


class FinalLibraryPromoteQueueCommandPayload(StrictApiCommandPayload):
    confirm_promote: Any = None
    row_keys: Any = None


class FinalLibraryPromotionRunCommandPayload(StrictApiCommandPayload):
    run_id: Any = None


COMMAND_ROUTE_PAYLOAD_MODELS: dict[str, type[ApiCommandPayload]] = {
    "/api/rename/preview": RenameCommandPayload,
    "/api/rename/browse": RenameCommandPayload,
    "/api/rename/apply": RenameApplyCommandPayload,
    "/api/diagnostics/open": OpenLocationCommandPayload,
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
    "/api/queue/file-overrides/folder-preview": QueueFileOverridesFolderPreviewCommandPayload,
    "/api/queue/file-overrides/folder-rule": QueueFileOverridesFolderRuleCommandPayload,
    "/api/failures/clear": FailureCommandPayload,
    "/api/pending-publish/open": OpenLocationCommandPayload,
    "/api/pending-publish/recovery-plan": OpenLocationCommandPayload,
    "/api/completed/open": OpenLocationCommandPayload,
    "/api/subtitle-qa/preview": SubtitleQaPreviewCommandPayload,
    "/api/settings/validate": SettingsCommandPayload,
    "/api/settings/browse-path": SettingsBrowsePathCommandPayload,
    "/api/settings/preview-patch": SettingsPreviewPatchCommandPayload,
    "/api/settings/pipeline-plan-preview": SettingsPipelinePlanPreviewCommandPayload,
    "/api/settings/save-patch": SettingsSavePatchCommandPayload,
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
    "/api/maintenance/dependency-atlas": MaintenanceDependencyAtlasCommandPayload,
    "/api/maintenance/dependency-atlas/open-folder": MaintenanceDependencyAtlasOpenFolderCommandPayload,
    "/api/metrics/sources": MetricsSourcesCommandPayload,
    "/api/metrics/backfill": MetricsBackfillCommandPayload,
    "/api/settings/reload": EmptyCommandPayload,
    "/api/sample-validation/preview": SampleValidationCommandPayload,
    "/api/sample-validation/append": SampleValidationCommandPayload,
    "/api/pipeline/control": PipelineControlCommandPayload,
    "/api/pipeline/browse-file": PipelineBrowseFileCommandPayload,
    "/api/pipeline/start": PipelineStartCommandPayload,
    "/api/audit/start": ProcessControlCommandPayload,
    "/api/audit/score-policy": AuditScorePolicyCommandPayload,
    "/api/audit/ignore": AuditIgnoreCommandPayload,
    "/api/audit/export-rerun-csv": AuditExportRerunCsvCommandPayload,
    "/api/rerun/start": ProcessControlCommandPayload,
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
