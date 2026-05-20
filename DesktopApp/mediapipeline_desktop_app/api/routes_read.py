from __future__ import annotations

from .routes_shared import RouteHandlerSpec


GET_ROUTE_HANDLERS: dict[str, RouteHandlerSpec] = {
    "/api/contract": RouteHandlerSpec("_contract_payload"),
    "/api/snapshot": RouteHandlerSpec("_snapshot_payload"),
    "/api/telemetry": RouteHandlerSpec("_telemetry_payload"),
    "/api/diagnostics": RouteHandlerSpec("_diagnostics_payload"),
    "/api/diagnostics/tail": RouteHandlerSpec("_diagnostics_tail_payload", needs_query=True),
    "/api/diagnostics/state-summary": RouteHandlerSpec("_diagnostics_state_summary_payload"),
    "/api/backend/close-readiness": RouteHandlerSpec("_close_readiness_payload"),
    "/api/launch/preflight": RouteHandlerSpec("_launch_preflight_payload", needs_query=True),
    "/api/commands": RouteHandlerSpec("_command_history_payload", needs_query=True),
    "/api/queue": RouteHandlerSpec("_queue_payload"),
    "/api/queue/priority": RouteHandlerSpec("_queue_priority_read_payload"),
    "/api/queue/strategy": RouteHandlerSpec("_queue_strategy_read_payload"),
    "/api/queue/file-overrides": RouteHandlerSpec("_file_overrides_read_payload", needs_query=True),
    "/api/completed": RouteHandlerSpec("_completed_payload", needs_query=True),
    "/api/failures": RouteHandlerSpec("_failures_payload", needs_query=True),
    "/api/audit-results": RouteHandlerSpec("_audit_results_payload", needs_query=True),
    "/api/pending-publish": RouteHandlerSpec("_pending_publish_payload"),
    "/api/publish-reconciliation": RouteHandlerSpec("_publish_reconciliation_payload", needs_query=True),
    "/api/maintenance": RouteHandlerSpec("_maintenance_payload"),
    "/api/maintenance/progress": RouteHandlerSpec("_maintenance_progress_payload"),
    "/api/schedule": RouteHandlerSpec("_schedule_payload"),
    "/api/settings/workspace": RouteHandlerSpec("_settings_workspace_payload"),
    "/api/network/workers": RouteHandlerSpec("_network_workers_payload"),
    "/api/sample-validation": RouteHandlerSpec("_sample_validation_payload", needs_query=True),
}
