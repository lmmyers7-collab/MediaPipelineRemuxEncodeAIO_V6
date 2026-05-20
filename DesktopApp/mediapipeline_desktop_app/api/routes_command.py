from __future__ import annotations

from .routes_shared import RouteHandlerSpec


POST_ROUTE_HANDLERS: dict[str, RouteHandlerSpec] = {
    "/api/rename/preview": RouteHandlerSpec("_rename_preview_payload"),
    "/api/rename/browse": RouteHandlerSpec("_rename_browse_payload"),
    "/api/rename/apply": RouteHandlerSpec("_rename_apply_payload"),
    "/api/diagnostics/open": RouteHandlerSpec("_diagnostics_open_payload"),
    "/api/queue/open": RouteHandlerSpec("_queue_open_payload"),
    "/api/queue/priority": RouteHandlerSpec("_queue_priority_payload"),
    "/api/queue/strategy": RouteHandlerSpec("_queue_strategy_payload"),
    "/api/queue/file-overrides": RouteHandlerSpec("_file_overrides_payload"),
    "/api/failures/clear": RouteHandlerSpec("_failures_clear_payload"),
    "/api/pending-publish/open": RouteHandlerSpec("_pending_publish_open_payload"),
    "/api/pending-publish/recovery-plan": RouteHandlerSpec("_pending_publish_recovery_plan_payload"),
    "/api/completed/open": RouteHandlerSpec("_completed_open_payload"),
    "/api/settings/validate": RouteHandlerSpec("_settings_validate_payload"),
    "/api/settings/preview-patch": RouteHandlerSpec("_settings_preview_patch_payload"),
    "/api/settings/save-patch": RouteHandlerSpec("_settings_save_patch_payload"),
    "/api/schedule/preview": RouteHandlerSpec("_schedule_preview_payload"),
    "/api/schedule/save": RouteHandlerSpec("_schedule_save_payload"),
    "/api/maintenance/release-dry-run": RouteHandlerSpec("_maintenance_release_dry_run_payload"),
    "/api/maintenance/release-build": RouteHandlerSpec("_maintenance_release_build_payload"),
    "/api/maintenance/completed-backfill-dry-run": RouteHandlerSpec("_maintenance_completed_backfill_dry_run_payload"),
    "/api/settings/reload": RouteHandlerSpec("_settings_reload_payload"),
    "/api/sample-validation/preview": RouteHandlerSpec("_sample_validation_preview_payload"),
    "/api/sample-validation/append": RouteHandlerSpec("_sample_validation_append_payload"),
    "/api/pipeline/control": RouteHandlerSpec("_pipeline_control_payload"),
    "/api/pipeline/start": RouteHandlerSpec("_pipeline_start_payload"),
    "/api/audit/start": RouteHandlerSpec("_audit_start_payload"),
    "/api/rerun/start": RouteHandlerSpec("_rerun_start_payload"),
    "/api/backend/shutdown": RouteHandlerSpec("_backend_shutdown_payload"),
}
