from __future__ import annotations

from typing import Any, Mapping


ROW_OPERATOR_GUIDANCE = {
    "ready": "Ready-looking row; backend drain still performs final publish validation.",
    "missing_payload": "Parked media file is missing. Open the manifest and destination/source folders before retrying or reprocessing.",
    "missing_sidecar": "One or more sidecars referenced by the manifest are missing. Review the manifest and payload before drain.",
    "orphan_payload": "Payload has no manifest. Confirm whether it is leftover from a failed parking or manual copy before cleanup or retry.",
    "invalid_manifest": "Manifest is invalid. Regenerate or repair from pipeline logs before drain.",
    "unreadable_manifest": "Manifest could not be read. Check file locking, permissions, and JSON validity before drain.",
    "duplicate_target": "Multiple pending manifests reference the same payload or destination. Resolve duplicates before drain.",
    "row_error": "Pending row has a backend-reported error. Inspect manifest, payload, and run logs before drain.",
}

ROW_RECOVERY_CLASSES = {
    "ready": "ready_to_validate",
    "missing_payload": "payload_missing",
    "missing_sidecar": "sidecar_missing",
    "orphan_payload": "orphan_payload_review",
    "invalid_manifest": "manifest_repair",
    "unreadable_manifest": "manifest_repair",
    "duplicate_target": "duplicate_resolution",
    "row_error": "manual_review",
}

ROW_RECOVERY_ACTIONS = {
    "ready": "Use Drain Parked Outputs only after the current pending scan still shows this row ready.",
    "missing_payload": "Open the manifest and destination/source folders, then confirm whether the parked payload was moved, deleted, or never written.",
    "missing_sidecar": "Open the manifest and payload, then compare expected sidecar paths against disk before draining.",
    "orphan_payload": "Open the orphan payload and run logs before deciding whether it is a leftover, manual copy, or failed parking artifact.",
    "invalid_manifest": "Repair or regenerate the pending manifest from logs/sidecar evidence before another drain attempt.",
    "unreadable_manifest": "Check locking, permissions, and JSON validity before another drain attempt.",
    "duplicate_target": "Compare duplicate manifests and destinations before draining; one row may be stale or manually copied.",
    "row_error": "Inspect manifest, payload, destination, Last Stderr, and Run Logs before another drain attempt.",
}

RECOVERY_PLAN_ACTIONS = {
    "ready": "validate_with_backend_drain",
    "missing_payload": "locate_payload_or_reprocess_source",
    "missing_sidecar": "compare_manifest_sidecars_before_drain",
    "orphan_payload": "classify_orphan_payload_before_cleanup_or_rerun",
    "invalid_manifest": "repair_or_regenerate_manifest_from_logs",
    "unreadable_manifest": "unlock_or_repair_manifest_json",
    "duplicate_target": "resolve_duplicate_pending_targets",
    "row_error": "manual_review_with_logs",
}


def row_operator_guidance(status: str) -> str:
    return ROW_OPERATOR_GUIDANCE.get(status, "Review this pending row before drain.")


def row_recovery_class(status: str) -> str:
    return ROW_RECOVERY_CLASSES.get(status, "manual_review")


def row_recovery_action(status: str) -> str:
    return ROW_RECOVERY_ACTIONS.get(status, "Review this row with Pending Publish diagnostics before draining.")


def recovery_plan_action(row: Mapping[str, Any]) -> str:
    status = str(row.get("diagnostic_status") or "").strip().casefold()
    return RECOVERY_PLAN_ACTIONS.get(status, "manual_review_with_pending_diagnostics")


__all__ = [
    "recovery_plan_action",
    "row_operator_guidance",
    "row_recovery_action",
    "row_recovery_class",
]
