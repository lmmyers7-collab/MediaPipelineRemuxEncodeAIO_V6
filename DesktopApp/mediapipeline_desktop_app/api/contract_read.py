from __future__ import annotations

from typing import Any

from .contract_shared import LOCAL_API_CONTRACT_SCHEMA_VERSION


LOCAL_API_STATUS_READ_ROUTE_CONTRACT: tuple[dict[str, Any], ...] = (
    {
        "method": "GET",
        "path": "/api/health",
        "auth_required": False,
        "effect": "none",
        "response_schema": "desktop_backend_health.v1",
        "purpose": "Backend startup/readiness check for shells and operators.",
    },
    {
        "method": "GET",
        "path": "/api/contract",
        "auth_required": True,
        "effect": "none",
        "response_schema": LOCAL_API_CONTRACT_SCHEMA_VERSION,
        "purpose": "Self-describing route and command contract for local frontends.",
    },
    {
        "method": "GET",
        "path": "/api/snapshot",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_app_snapshot.v1",
        "purpose": "Current pipeline/audit status snapshot.",
    },
    {
        "method": "GET",
        "path": "/api/telemetry",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_telemetry.v1",
        "purpose": "Latest cached CPU/RAM/GPU telemetry sample.",
    },
    {
        "method": "GET",
        "path": "/api/diagnostics",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_diagnostics.v1",
        "purpose": "Recent diagnostics, events, errors, and launch-log summary.",
    },
    {
        "method": "GET",
        "path": "/api/diagnostics/tail",
        "auth_required": True,
        "effect": "none",
        "query_keys": ["target", "max_bytes"],
        "response_schema": "desktop_diagnostics_tail.v1",
        "purpose": "Read a bounded text tail from a backend-allowlisted diagnostics file target.",
    },
    {
        "method": "GET",
        "path": "/api/diagnostics/state-summary",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_diagnostics_state_summary.v1",
        "purpose": "Read a bounded backend-owned summary of important diagnostics and state artifacts without accepting arbitrary paths.",
    },
    {
        "method": "GET",
        "path": "/api/backend/close-readiness",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_close_readiness.v1",
        "purpose": "Report whether the local shell can close without hiding active pipeline, audit, or rerun work.",
    },
    {
        "method": "GET",
        "path": "/api/launch/preflight",
        "auth_required": True,
        "effect": "none",
        "query_keys": [
            "target",
            "mode",
            "sleep_seconds",
            "show_config",
            "show_console",
            "schedule_override",
            "library_root",
            "include_sidecars",
            "csv_path",
            "dry_run",
            "stage_mode",
            "original_mode",
            "return_mode",
        ],
        "allowed_targets": ["pipeline", "audit", "rerun"],
        "response_schema": "desktop_launch_preflight.v1",
        "purpose": "Read backend-authored launch preflight checks for pipeline, audit, or CSV rerun without reserving locks, launching processes, writing control flags, mutating config, or touching media files.",
    },
    {
        "method": "GET",
        "path": "/api/commands",
        "auth_required": True,
        "effect": "none",
        "query_keys": ["limit"],
        "response_schema": "desktop_command_history.v1",
        "purpose": "Read recent backend-recorded command results for diagnostics and web shell refresh recovery.",
    },
)

LOCAL_API_INVENTORY_READ_ROUTE_CONTRACT: tuple[dict[str, Any], ...] = (
    {
        "method": "GET",
        "path": "/api/queue",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_queue_preview.v1",
        "purpose": "Read the latest backend-owned queue snapshot without spawning a dry run.",
    },
    {
        "method": "GET",
        "path": "/api/queue/priority",
        "auth_required": True,
        "effect": "none",
        "response_schema": "queue_priority_manifest.v1",
        "purpose": "Read the non-destructive queue priority manifest from backend state without changing queue order or media files.",
    },
    {
        "method": "GET",
        "path": "/api/queue/strategy",
        "auth_required": True,
        "effect": "none",
        "response_schema": "queue_strategy_state.v1",
        "purpose": "Read the active queue ordering strategy and valid backend strategy names without writing queue state.",
    },
    {
        "method": "GET",
        "path": "/api/queue/file-overrides",
        "auth_required": True,
        "effect": "none",
        "query_keys": ["path"],
        "response_schema": "queue_file_overrides.v1",
        "purpose": "Read the per-file override manifest, or a single source-root-contained override entry, without changing queue policy or media files.",
    },
    {
        "method": "GET",
        "path": "/api/completed",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_completed_preview.v1",
        "purpose": "Read recent completed jobs from the local completed-jobs manifest without scanning the output share.",
    },
    {
        "method": "GET",
        "path": "/api/failures",
        "auth_required": True,
        "effect": "none",
        "query_keys": ["source", "limit"],
        "allowed_sources": ["latest_json", "markers"],
        "response_schema": "desktop_failure_preview.v1",
        "purpose": "Read recent failure rows from the latest round failure JSON or failure marker store without clearing, prioritizing, or rerunning anything.",
    },
    {
        "method": "GET",
        "path": "/api/audit-results",
        "auth_required": True,
        "effect": "none",
        "query_keys": ["priority_only", "limit"],
        "response_schema": "desktop_audit_preview.v1",
        "purpose": "Read recent audit rows from the latest audit CSV without exporting rerun CSVs, applying priority, opening files, or mutating reports.",
    },
    {
        "method": "GET",
        "path": "/api/pending-publish",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_pending_publish_preview.v1",
        "purpose": "Read pending-publish manifests, parked payloads, and health rows without draining.",
    },
    {
        "method": "GET",
        "path": "/api/publish-reconciliation",
        "auth_required": True,
        "effect": "none",
        "query_keys": ["limit"],
        "response_schema": "desktop_publish_reconciliation.v1",
        "purpose": "Read a backend-authored Completed/Pending Publish/drain-summary correlation snapshot without draining, repairing, rerunning, publishing, or mutating files.",
    },
)

LOCAL_API_WORKSPACE_READ_ROUTE_CONTRACT: tuple[dict[str, Any], ...] = (
    {
        "method": "GET",
        "path": "/api/maintenance",
        "auth_required": True,
        "effect": "bounded-health-check",
        "response_schema": "desktop_maintenance_workspace.v1",
        "purpose": "Run the existing environment/tool health checks and return structured rows without repairing or changing anything.",
    },
    {
        "method": "GET",
        "path": "/api/maintenance/progress",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_maintenance_health_progress.v1",
        "purpose": "Read the latest backend-authored Maintenance health-check progress surface without running probes, repairing paths, installing tools, draining pending publish, or mutating files.",
    },
    {
        "method": "GET",
        "path": "/api/schedule",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_schedule_workspace.v1",
        "purpose": "Read persisted schedule state and current schedule evaluation without saving or editing the grid.",
    },
    {
        "method": "GET",
        "path": "/api/settings/workspace",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_settings_workspace.v1",
        "purpose": "Read-only, redacted settings workspace snapshot.",
    },
    {
        "method": "GET",
        "path": "/api/network/workers",
        "auth_required": True,
        "effect": "none",
        "response_schema": "desktop_network_workers.v1",
        "purpose": "Read persisted coordinator/worker runtime state for WebView network visibility without lifecycle controls.",
    },
    {
        "method": "GET",
        "path": "/api/sample-validation",
        "auth_required": True,
        "effect": "none",
        "query_keys": ["limit"],
        "response_schema": "desktop_sample_validation_log.v1",
        "purpose": "Read recent backend-owned sample validation records plus read-only validation-readiness and stale-evidence reconciliation from known Queue/Completed/Diagnostics/Pending/Settings evidence without accepting arbitrary paths, scanning output shares, or changing media/pipeline state.",
    },
)

LOCAL_API_READ_ROUTE_CONTRACT: tuple[dict[str, Any], ...] = (
    LOCAL_API_STATUS_READ_ROUTE_CONTRACT
    + LOCAL_API_INVENTORY_READ_ROUTE_CONTRACT
    + LOCAL_API_WORKSPACE_READ_ROUTE_CONTRACT
)


__all__ = [
    "LOCAL_API_INVENTORY_READ_ROUTE_CONTRACT",
    "LOCAL_API_READ_ROUTE_CONTRACT",
    "LOCAL_API_STATUS_READ_ROUTE_CONTRACT",
    "LOCAL_API_WORKSPACE_READ_ROUTE_CONTRACT",
]
