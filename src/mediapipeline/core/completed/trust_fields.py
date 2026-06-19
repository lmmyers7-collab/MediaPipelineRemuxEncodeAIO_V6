"""Pure trust-field builders for completed output DTO rows."""

from __future__ import annotations

from typing import Any


COMPLETED_TRUST_NEUTRAL_SIZE_DELTA_PERCENT = 1.0
COMPLETED_TRUST_RUNTIME_FAILURE_STATUSES = {
    "failed",
    "skipped",
    "stopped",
    "transient_failure",
    "permanent_failure",
    "operator_required_failure",
    "failure_recorded",
}
COMPLETED_TRUST_BENIGN_RUNTIME_ERROR_CODES = {"already_processed"}


def _size_delta_percent(row: dict[str, Any]) -> float | None:
    value = row.get("size_delta_percent")
    if isinstance(value, (int, float)):
        return float(value)
    label = str(row.get("size_delta_label") or "").strip().replace("%", "")
    if not label:
        return None
    try:
        return float(label)
    except ValueError:
        return None


def _runtime_is_successful(row: dict[str, Any]) -> bool:
    runtime_status = str(row.get("runtime_outcome_status") or "").strip().casefold()
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    return runtime_success is True or runtime_success_text == "true" or runtime_status in {
        "ok",
        "success",
        "succeeded",
        "completed",
        "published",
    }


def _runtime_is_failed(row: dict[str, Any]) -> bool:
    runtime_status = str(row.get("runtime_outcome_status") or "").strip().casefold()
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    return (
        runtime_success is False
        or runtime_success_text == "false"
        or runtime_status in COMPLETED_TRUST_RUNTIME_FAILURE_STATUSES
    )


def _benign_trust_flags(row: dict[str, Any]) -> set[str]:
    benign = {"encoded", "remuxed", "size_policy_within_limit", "quality_within_threshold"}
    size_delta = _size_delta_percent(row)
    if size_delta is not None and abs(size_delta) <= COMPLETED_TRUST_NEUTRAL_SIZE_DELTA_PERCENT:
        benign.add("size_growth")
    runtime_status = str(row.get("runtime_outcome_status") or "").strip().casefold()
    runtime_error = str(row.get("runtime_outcome_error_code") or "").strip().casefold()
    if runtime_status and _runtime_is_successful(row) and not _runtime_is_failed(row):
        benign.update({"runtime_outcome", f"runtime_outcome:{runtime_status}"})
        if runtime_error in COMPLETED_TRUST_BENIGN_RUNTIME_ERROR_CODES:
            benign.add(f"runtime_error:{runtime_error}")
    return benign


def build_completed_row_trust_fields(row: dict[str, Any]) -> dict[str, Any]:
    flags = [str(item) for item in row.get("review_flags") or [] if str(item).strip()]
    benign_flags = _benign_trust_flags(row)
    trust_flags = [flag for flag in flags if flag.casefold() not in benign_flags]
    consistency_issues = [str(item) for item in row.get("consistency_issues") or [] if str(item).strip()]
    runtime_status = str(row.get("runtime_outcome_status") or "").strip()
    runtime_freshness = str(row.get("runtime_outcome_freshness_status") or "").strip().casefold()
    runtime_error = str(row.get("runtime_outcome_error_code") or "").strip()
    runtime_recent = bool(runtime_status) and runtime_freshness != "stale"
    runtime_failed = _runtime_is_failed(row)
    missing_output = row.get("output_exists") is False or str(row.get("output_health") or "").strip().casefold() in {
        "missing",
        "missing_output",
        "unavailable",
    }
    missing_sidecar = row.get("sidecar_exists") is False or any("sidecar" in issue.casefold() for issue in consistency_issues)

    if missing_output:
        trust_state = "broken-output"
        concern = "completed manifest row points to a missing or unhealthy output"
        safe_action = "Inspect Completed Manifest, Pending Publish, output folder, Run Logs, and Last Stderr before rerun or cleanup."
    elif missing_sidecar:
        trust_state = "review-before-rerun-or-cleanup"
        concern = "sidecar is missing or inconsistent with the output"
        safe_action = "Inspect sidecar/output consistency before cleanup, Plex library decisions, or rerun."
    elif bool(row.get("size_policy_exceeded")):
        trust_state = "review-before-rerun-or-cleanup"
        concern = "output exceeded the recorded backend size policy threshold"
        safe_action = "Compare sidecar size_policy, route metadata, encoder choice, and Run Logs before accepting this output as intentional compatibility growth."
    elif bool(row.get("size_growth_over_5")) and not bool(row.get("size_policy_available")):
        trust_state = "review-before-rerun-or-cleanup"
        concern = "output grew more than the legacy +5% threshold and no backend size_policy was recorded"
        safe_action = "Compare route metadata, encoder choice, and Run Logs before accepting this output as intentional compatibility growth."
    elif runtime_recent and runtime_failed:
        trust_state = "review-before-rerun-or-cleanup"
        concern = " - ".join(str(item) for item in (runtime_status, runtime_error, row.get("runtime_outcome_reason")) if str(item or "").strip()) or "fresh runtime conflict"
        safe_action = "Inspect Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun or cleanup."
    elif consistency_issues or trust_flags:
        trust_state = "review-before-rerun-or-cleanup"
        concern = ", ".join(consistency_issues or trust_flags)
        safe_action = "Review completed-row consistency, output/sidecar paths, and route evidence before making library or rerun decisions."
    else:
        trust_state = "consistent-looking"
        concern = "row has no output, sidecar, size, or runtime blocker in the loaded completed manifest"
        safe_action = "Treat this row as historical proof only after output/sidecar and route evidence agree."

    diagnostics = ["completed_manifest", "run_logs", "last_stderr_log"]
    if missing_output or missing_sidecar:
        diagnostics.append("pending_publish")
    if missing_output or missing_sidecar or row.get("size_policy_exceeded") or (row.get("size_growth_over_5") and not row.get("size_policy_available")) or runtime_failed:
        diagnostics.append("latest_failure_report")
    proof = [
        f"status={row.get('operator_status') or 'not reported'}",
        f"consistency={row.get('consistency_status') or 'not reported'}",
        f"size={row.get('size_delta_label') or row.get('size_reduction_text') or 'not reported'}",
        f"output={row.get('output_path') or 'not reported'}",
    ]
    if runtime_status:
        proof.append(f"runtime={runtime_status}{f' / {runtime_error}' if runtime_error else ''}")
    return {
        "operator_trust_state": trust_state,
        "primary_concern": concern,
        "safe_next_action": safe_action,
        "unsafe_if_ignored": "Treating stale or inconsistent completed rows as proof can hide missing outputs, stale sidecars, partial publishes, or oversized encodes.",
        "proof_summary": proof,
        "recommended_diagnostics_targets": diagnostics,
    }


__all__ = ["build_completed_row_trust_fields"]
