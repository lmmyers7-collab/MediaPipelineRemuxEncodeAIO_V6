"""Canonical Local API command route registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiCommandRouteSpec:
    method_name: str


COMMAND_ROUTE_METHODS: dict[str, str] = {
    "/api/rename/preview": "_rename_preview_payload",
    "/api/rename/browse": "_rename_browse_payload",
    "/api/rename/apply": "_rename_apply_payload",
    "/api/diagnostics/open": "_diagnostics_open_payload",
    "/api/queue/open": "_queue_open_payload",
    "/api/queue/priority": "_queue_priority_payload",
    "/api/queue/strategy": "_queue_strategy_payload",
    "/api/queue/file-overrides": "_file_overrides_payload",
    "/api/failures/clear": "_failures_clear_payload",
    "/api/pending-publish/open": "_pending_publish_open_payload",
    "/api/pending-publish/recovery-plan": "_pending_publish_recovery_plan_payload",
    "/api/completed/open": "_completed_open_payload",
    "/api/settings/validate": "_settings_validate_payload",
    "/api/settings/browse-path": "_settings_browse_path_payload",
    "/api/settings/preview-patch": "_settings_preview_patch_payload",
    "/api/settings/pipeline-plan-preview": "_settings_pipeline_plan_preview_payload",
    "/api/settings/save-patch": "_settings_save_patch_payload",
    "/api/settings/wizard/validate-paths": "_settings_wizard_validate_paths_payload",
    "/api/settings/wizard/validate-tools": "_settings_wizard_validate_tools_payload",
    "/api/settings/wizard/probe-hardware": "_settings_wizard_probe_hardware_payload",
    "/api/settings/wizard/validate-workers": "_settings_wizard_validate_workers_payload",
    "/api/settings/wizard/preview": "_settings_wizard_preview_payload",
    "/api/settings/wizard/save": "_settings_wizard_save_payload",
    "/api/schedule/preview": "_schedule_preview_payload",
    "/api/schedule/save": "_schedule_save_payload",
    "/api/maintenance/release-dry-run": "_maintenance_release_dry_run_payload",
    "/api/maintenance/release-build": "_maintenance_release_build_payload",
    "/api/maintenance/completed-backfill-dry-run": "_maintenance_completed_backfill_dry_run_payload",
    "/api/maintenance/dependency-atlas": "_maintenance_dependency_atlas_payload",
    "/api/settings/reload": "_settings_reload_payload",
    "/api/sample-validation/preview": "_sample_validation_preview_payload",
    "/api/sample-validation/append": "_sample_validation_append_payload",
    "/api/pipeline/control": "_pipeline_control_payload",
    "/api/pipeline/start": "_pipeline_start_payload",
    "/api/audit/start": "_audit_start_payload",
    "/api/rerun/start": "_rerun_start_payload",
    "/api/backend/shutdown": "_backend_shutdown_payload",
    "/api/ui-preferences": "_ui_preferences_save_payload",
    "/api/final-library-promotion/promote-queue": "_final_library_promote_queue_payload",
    "/api/final-library-promotion/pause": "_final_library_promotion_pause_payload",
    "/api/final-library-promotion/resume": "_final_library_promotion_resume_payload",
}

COMMAND_ROUTE_SPECS: dict[str, ApiCommandRouteSpec] = {
    route: ApiCommandRouteSpec(method_name=method_name)
    for route, method_name in COMMAND_ROUTE_METHODS.items()
}


__all__ = ["ApiCommandRouteSpec", "COMMAND_ROUTE_METHODS", "COMMAND_ROUTE_SPECS"]
