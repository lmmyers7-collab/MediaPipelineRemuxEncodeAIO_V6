from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row_promoted_fields(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    promoted = bool(evidence and evidence.get("success"))
    cleanup = evidence.get("cleanup_result") if isinstance(evidence, Mapping) else {}
    if not isinstance(cleanup, Mapping):
        cleanup = {}
    promoted_cleaned = promoted and bool(cleanup.get("completed"))
    return {
        "promoted": promoted,
        "promoted_cleaned": promoted_cleaned,
        "last_promotion_run_id": str(evidence.get("run_id") or "") if isinstance(evidence, Mapping) else "",
        "last_promotion_completed_at": str(evidence.get("completed_at") or "") if isinstance(evidence, Mapping) else "",
    }


def default_promotion_row_fields() -> dict[str, Any]:
    return {
        "ready_for_promotion": False,
        "no_destination_rule": False,
        "destination_offline": False,
        "promoting": False,
        "paused": False,
        "promotion_failed": False,
        "promoted": False,
        "promoted_cleaned": False,
        "final_library_promotion_status": "not_evaluated",
        "final_library_promotion_status_label": "Not Evaluated",
        "final_library_destination_path": "",
        "final_library_destination_root": "",
        "final_library_rule_id": "",
        "final_library_rule_label": "",
        "library_profile_id": "",
        "library_profile_label": "",
        "library_designation": "",
        "library_output_root": "",
        "last_promotion_run_id": "",
        "last_promotion_completed_at": "",
        "promotion_error": "",
        "promotion_warnings": [],
        "required_pipeline_sidecar_path": "",
        "required_pipeline_sidecar_exists": False,
        "required_pipeline_sidecar_missing": False,
        "missing_sidecars": [],
    }


def status_label(status: str) -> str:
    labels = {
        "disabled": "Promotion Disabled",
        "ready": "Ready",
        "missing_output": "Missing Output",
        "missing_required_sidecar": "Missing Pipeline Sidecar",
        "outside_outsource": "Outside Outsource",
        "no_destination_rule": "No Destination Rule",
        "destination_offline": "Destination Offline",
        "pending_publish_unresolved": "Pending Publish",
        "promoting": "Promoting",
        "paused": "Paused",
        "promotion_failed": "Failed",
        "promoted": "Promoted",
        "promoted_cleaned": "Promoted + Cleaned",
    }
    return labels.get(status, status.replace("_", " ").title())


def promotion_row_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total": len(rows),
        "eligible": sum(1 for row in rows if row.get("ready_for_promotion")),
        "no_destination_rule": sum(1 for row in rows if row.get("no_destination_rule")),
        "destination_offline": sum(1 for row in rows if row.get("destination_offline")),
        "promoting": sum(1 for row in rows if row.get("promoting")),
        "paused": sum(1 for row in rows if row.get("paused")),
        "failed": sum(1 for row in rows if row.get("promotion_failed")),
        "promoted": sum(1 for row in rows if row.get("promoted")),
        "promoted_cleaned": sum(1 for row in rows if row.get("promoted_cleaned")),
    }
    counts["ineligible"] = max(0, counts["total"] - counts["eligible"])
    return counts


def promotion_status_warnings(
    *,
    enabled: bool,
    overwrite_existing: bool,
    cleanup_after_verified: bool,
) -> list[str]:
    warnings: list[str] = []
    if not enabled:
        warnings.append("Final Library Promotion is disabled in Settings.")
    if overwrite_existing:
        warnings.append("Destructive overwrite is enabled: existing final files are replaced only after the staged replacement copy verifies.")
    if cleanup_after_verified:
        warnings.append("Cleanup after verified promotion is enabled for files below Outsource.")
    return warnings


__all__ = [
    "default_promotion_row_fields",
    "promotion_row_counts",
    "promotion_status_warnings",
    "row_promoted_fields",
    "status_label",
    "utc_now_text",
]
