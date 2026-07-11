from __future__ import annotations



REPAIR_RECONCILE_DRY_RUN_SCHEMA_VERSION = "desktop_repair_reconcile_dry_run.v1"
STARTUP_RECONCILIATION_DRY_RUN_SCHEMA_VERSION = "desktop_startup_reconciliation_dry_run.v1"
REPAIR_RECONCILE_EFFECT_NONE = "none"

STARTUP_RECONCILE_STATE_COMMAND = "startup.reconcile_state"
COMPLETED_RECONCILE_MANIFEST_COMMAND = "completed.reconcile_manifest"
COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND = "completed.repair_sidecar_metadata"
PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND = "pending_publish.repair_manifest"
PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND = "pending_publish.reconcile_orphan_payloads"
CSV_RERUN_REPAIR_PIPELINE_VERSION = "csv_rerun_repair.v1"

DRY_RUN_COMMAND_BY_CANDIDATE = {
    STARTUP_RECONCILE_STATE_COMMAND: "startup.reconcile_state_dry_run",
    COMPLETED_RECONCILE_MANIFEST_COMMAND: "completed.reconcile_manifest_dry_run",
    COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND: "completed.repair_sidecar_metadata_dry_run",
    PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND: "pending_publish.repair_manifest_dry_run",
    PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND: "pending_publish.reconcile_orphan_payloads_dry_run",
}

