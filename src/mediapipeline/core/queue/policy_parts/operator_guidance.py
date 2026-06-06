"""Queue operator status, guidance, and trust helpers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .route_evidence import queue_row_route_decision_summary, queue_row_route_evidence_lines


def _runtime_outcome_is_operator_stop(row: Mapping[str, Any]) -> bool:
    runtime_status = str(row.get("runtime_outcome_status") or "").strip().casefold()
    if runtime_status != "stopped":
        return False
    runtime_error = str(row.get("runtime_outcome_error_code") or "").strip().casefold()
    runtime_reason = str(row.get("runtime_outcome_reason") or "").strip().casefold()
    return runtime_error == "stop_requested" or ("stop" in runtime_reason and "operator" in runtime_reason)


def _runtime_publish_state(row: Mapping[str, Any]) -> str:
    return str(row.get("runtime_outcome_publish_state") or "").strip().casefold()


def _runtime_operator_stop_label_and_guidance(row: Mapping[str, Any]) -> tuple[str, str]:
    publish_state = _runtime_publish_state(row)
    if publish_state in {"parked", "parked_recovered", "pending_move", "deferred"} or "retry" in publish_state:
        return (
            "Waiting for push",
            "The previous run stopped after the current item and left output in Pending Publish. Drain Pending Publish when the final output root is safe.",
        )
    if publish_state in {"published", "already_published", "succeeded"}:
        return (
            "Recently completed",
            "The previous run stopped after the current item and publish evidence says this output is complete. Refresh Completed, then use Launch when ready to continue queued work.",
        )
    return (
        "Check publish state",
        "Stop After Current was requested. Check Completed and Pending Publish for the last item, then use Launch when ready to continue queued work.",
    )


def queue_row_operator_status_state(
    row: Mapping[str, Any],
    *,
    severity: str = "",
    review_flags: Iterable[str] | None = None,
) -> str:
    status = str(row.get("status") or "").strip().casefold()
    operator_severity = str(severity or row.get("operator_severity") or "").strip().casefold()
    flags = {str(flag or "").strip().casefold() for flag in (review_flags or row.get("review_flags") or []) if str(flag or "").strip()}
    runtime_status = str(row.get("runtime_outcome_status") or "").strip().casefold()
    runtime_freshness = str(row.get("runtime_outcome_freshness_status") or "").strip().casefold()
    runtime_recent = bool(runtime_status) and runtime_freshness != "stale"
    runtime_operator_stop = runtime_recent and _runtime_outcome_is_operator_stop(row)
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    if status == "invalid" or operator_severity in {"error", "critical"}:
        return "blocked"
    if row.get("blocked_reason") or row.get("blocked_reason_code") or "blocked" in flags:
        return "blocked"
    if runtime_recent:
        if runtime_operator_stop:
            return "warning"
        if runtime_status in {
            "failed",
            "stopped",
            "transient_failure",
            "permanent_failure",
            "operator_required_failure",
            "failure_recorded",
        }:
            return "failed"
        if (
            runtime_status == "skipped"
            or runtime_success is False
            or runtime_success_text == "false"
            or runtime_success is True
            or runtime_success_text == "true"
        ):
            return "warning"
    if bool(row.get("runtime_checks_deferred")) or operator_severity == "warning" or flags:
        return "warning"
    return "ready"

def queue_row_operator_guidance(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "").strip().casefold()
    blocked_reason = str(row.get("blocked_reason") or "").strip()
    blocked_reason_code = str(row.get("blocked_reason_code") or "").strip()
    route_name = str(row.get("route_name") or "").strip()
    route_reason = str(row.get("route_reason") or "").strip()
    route_reason_code = str(row.get("route_reason_code") or "").strip()
    source_path = str(row.get("source_path") or "").strip()
    is_priority = bool(row.get("is_priority"))
    flags: list[str] = []
    severity = "ok"

    if status == "invalid":
        flags.append("invalid_snapshot_row")
        guidance = "Refresh Queue and open Diagnostics > Queue Snapshot. The backend ignored this row because it could not be parsed safely."
        return {
            "operator_status": "Invalid snapshot row",
            "operator_status_state": "blocked",
            "operator_severity": "error",
            "operator_guidance": guidance,
            "review_flags": flags,
            **queue_row_trust_fields(row, flags, label="Invalid snapshot row", guidance=guidance),
        }
    if blocked_reason:
        flags.append("blocked")
        if blocked_reason_code:
            flags.append(f"blocked:{blocked_reason_code}")
        severity = "warning"
    if not source_path:
        flags.append("missing_source_path")
        severity = "warning"
    if not route_name:
        flags.append("missing_route")
        severity = "warning"
    if route_name and "encode" in route_name.casefold():
        flags.append("encode_route")
    elif route_name and "remux" in route_name.casefold():
        flags.append("remux_route")
    if bool(row.get("runtime_checks_deferred")):
        flags.append("runtime_checks_deferred")
        for code in row.get("runtime_check_codes") or []:
            text = str(code or "").strip()
            if text:
                flags.append(f"runtime:{text}")
    runtime_outcome_status = str(row.get("runtime_outcome_status") or "").strip()
    runtime_outcome_freshness = str(row.get("runtime_outcome_freshness_status") or "").strip().casefold()
    runtime_error_code = str(row.get("runtime_outcome_error_code") or "").strip()
    runtime_recent = bool(runtime_outcome_status) and runtime_outcome_freshness != "stale"
    runtime_operator_stop = runtime_recent and _runtime_outcome_is_operator_stop(row)
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    runtime_failed = not runtime_operator_stop and (
        runtime_success is False or runtime_success_text == "false" or runtime_outcome_status.casefold() in {
            "failed",
            "skipped",
            "stopped",
            "transient_failure",
            "permanent_failure",
            "operator_required_failure",
            "failure_recorded",
        }
    )
    if runtime_outcome_status:
        flags.append("runtime_outcome")
        flags.append(f"runtime_outcome:{runtime_outcome_status.casefold()}")
        if runtime_error_code:
            flags.append(f"runtime_error:{runtime_error_code}")
        if runtime_outcome_freshness == "stale":
            flags.append("runtime_outcome_stale")
        elif runtime_failed:
            severity = "warning"
        elif runtime_success is True or runtime_success_text == "true":
            severity = "warning"
    if not route_reason and not route_reason_code:
        flags.append("missing_route_reason")
    if is_priority:
        flags.append("priority")

    if blocked_reason:
        label = "Blocked"
        guidance = "Do not launch this row until the block is understood. Refresh Queue and inspect the blocked reason plus recent run logs."
    elif not route_name or not source_path:
        label = "Review before launch"
        guidance = "This row is missing source or routing metadata. Refresh Queue and inspect Diagnostics before starting unattended work."
    elif runtime_operator_stop:
        label, guidance = _runtime_operator_stop_label_and_guidance(row)
    elif runtime_recent and runtime_failed:
        label = "Recent runtime failure"
        guidance = "This row is runnable in the latest snapshot, but recent backend runtime history for the same source path failed or skipped. Inspect the runtime outcome and logs before relaunching."
    elif runtime_recent and (runtime_success is True or runtime_success_text == "true"):
        label = "Recently completed"
        guidance = "This row is runnable in the latest snapshot, but recent backend runtime history for the same source path succeeded. Refresh completed history and pending publish state before relaunching."
    elif is_priority:
        label = "Priority ready"
        guidance = "Priority row is visible in the queue. Verify route and source path, then use Launch for backend-owned processing."
    else:
        label = "Ready"
        guidance = "Row is runnable in the loaded snapshot. Use Launch for backend-owned processing after confirming the snapshot is fresh."
    return {
        "operator_status": label,
        "operator_status_state": queue_row_operator_status_state(row, severity=severity, review_flags=flags),
        "operator_severity": severity,
        "operator_guidance": guidance,
        "review_flags": flags,
        "route_decision_summary": queue_row_route_decision_summary(row),
        "route_evidence_lines": queue_row_route_evidence_lines(row),
        **queue_row_trust_fields(row, flags, label=label, guidance=guidance),
    }

def queue_row_trust_fields(row: dict[str, Any], flags: list[str], *, label: str, guidance: str) -> dict[str, Any]:
    status = str(row.get("status") or "").strip().casefold()
    blocked = bool(row.get("blocked_reason") or row.get("blocked_reason_code") or status == "invalid")
    route_missing = not str(row.get("route_name") or "").strip()
    source_missing = not str(row.get("source_path") or "").strip()
    deferred = bool(row.get("runtime_checks_deferred"))
    runtime_status = str(row.get("runtime_outcome_status") or "").strip()
    runtime_freshness = str(row.get("runtime_outcome_freshness_status") or "").strip().casefold()
    runtime_error = str(row.get("runtime_outcome_error_code") or "").strip()
    runtime_recent = bool(runtime_status) and runtime_freshness != "stale"
    runtime_operator_stop = runtime_recent and _runtime_outcome_is_operator_stop(row)
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    runtime_failed = not runtime_operator_stop and (
        runtime_success is False or runtime_success_text == "false" or runtime_status.casefold() in {
            "failed",
            "skipped",
            "stopped",
            "transient_failure",
            "permanent_failure",
            "operator_required_failure",
            "failure_recorded",
        }
    )

    if status == "invalid":
        trust_state = "invalid-snapshot-row"
        concern = str(row.get("error") or "queue snapshot row could not be parsed safely")
        safe_action = "Refresh Queue, then inspect Diagnostics > Queue Snapshot and Run Logs before launch."
    elif blocked:
        trust_state = "blocked"
        concern = " - ".join(str(item) for item in (row.get("blocked_reason_code"), row.get("blocked_reason"), row.get("error")) if str(item or "").strip()) or "row is blocked"
        safe_action = "Do not launch this row; inspect Queue Snapshot, Last Stderr, Run Logs, and Latest Failure first."
    elif source_missing or route_missing:
        trust_state = "review-before-launch"
        concern = "row is missing source or routing metadata"
        safe_action = "Refresh Queue and inspect Queue Snapshot before starting unattended processing."
    elif runtime_operator_stop:
        publish_state = _runtime_publish_state(row)
        if publish_state in {"parked", "parked_recovered", "pending_move", "deferred"} or "retry" in publish_state:
            trust_state = "pending-publish"
            concern = "output is waiting for pending publish drain"
            safe_action = "Drain Pending Publish when the final output root is safe; otherwise leave it parked."
        elif publish_state in {"published", "already_published", "succeeded"}:
            trust_state = "review-before-launch"
            concern = "recent backend runtime history says this source already completed"
            safe_action = "Refresh Completed and Pending Publish state before relaunching this source."
        else:
            trust_state = "review-before-launch"
            concern = "operator Stop After Current was requested; publish state needs confirmation"
            safe_action = "Check Completed and Pending Publish for the last item, then use Launch when ready to continue queued work."
    elif runtime_recent and runtime_failed:
        trust_state = "review-before-launch"
        concern = " - ".join(str(item) for item in (runtime_status, runtime_error, row.get("runtime_outcome_reason")) if str(item or "").strip()) or "fresh runtime failure"
        safe_action = "Inspect Queue Snapshot, Last Stderr, Run Logs, and Latest Failure before relaunching this source."
    elif runtime_recent and (runtime_success is True or runtime_success_text == "true"):
        trust_state = "review-before-launch"
        concern = "recent backend runtime history says this source already completed"
        safe_action = "Refresh Completed and Pending Publish state before relaunching this source."
    elif deferred:
        trust_state = "launch-check-needed"
        concern = "source stability and output-path checks are deferred until backend launch"
        safe_action = "Use Launch only after page-level readiness and schedule checks agree; expect final source/output validation during processing."
    else:
        trust_state = "ready-looking"
        concern = "row has no blocker in the loaded queue snapshot"
        safe_action = "Use Launch only after page-level readiness, schedule, Completed, and Pending Publish checks agree."

    diagnostics = ["queue_snapshot", "run_logs", "last_stderr_log"]
    if blocked or runtime_failed:
        diagnostics.append("latest_failure_report")
    if deferred:
        diagnostics.append("active_jobs")
    proof = [
        f"status={label}",
        f"route={queue_row_route_decision_summary(row)}",
        f"source={row.get('source_path') or 'not reported'}",
    ]
    if runtime_status:
        proof.append(f"runtime={runtime_status}{f' / {runtime_error}' if runtime_error else ''}")
    if flags:
        proof.append(f"flags={', '.join(flags[:8])}")
    return {
        "operator_trust_state": trust_state,
        "primary_concern": concern,
        "safe_next_action": safe_action,
        "unsafe_if_ignored": "Launching stale, blocked, or recently-completed queue rows can duplicate work, miss changed source files, or fail after scratch-copy setup.",
        "proof_summary": proof,
        "recommended_diagnostics_targets": diagnostics,
        "operator_guidance": guidance,
    }
