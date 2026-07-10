from __future__ import annotations

from typing import TYPE_CHECKING, Any
from collections.abc import Mapping

from .pending_open_policy import normalize_pending_publish_row_key
from .pending_policy_parts.status_rules import recovery_plan_action as _recovery_plan_action
from .pending_contracts import (
    PENDING_PUBLISH_INVALID_RESULT_MESSAGE,
    PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
    PENDING_PUBLISH_RECOVERY_PLAN_SCHEMA_VERSION,
    PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
    _command_result,
    _json_safe,
)
from .pending_rows import (
    int_value,
    pending_publish_row_is_recovery_blocker,
    pending_publish_row_key,
)

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult

def normalize_pending_publish_recovery_scope(value: Any, row_key: str = "") -> str:
    text = str(value or "").strip().casefold()
    if text in {"all", "selected"}:
        return text
    return "selected" if row_key else "all"


def pending_publish_recovery_plan_action(row: Mapping[str, Any]) -> str:
    return _recovery_plan_action(row)


def pending_publish_recovery_plan_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "row_key": str(row.get("row_key") or pending_publish_row_key(row)),
        "state": str(row.get("state") or ""),
        "diagnostic_status": str(row.get("diagnostic_status") or "unknown"),
        "diagnostic_severity": str(row.get("diagnostic_severity") or "unknown"),
        "drain_recommendation": str(row.get("drain_recommendation") or "review"),
        "operator_trust_state": str(row.get("operator_trust_state") or "review-before-drain"),
        "recovery_class": str(row.get("recovery_class") or "manual_review"),
        "planned_action": pending_publish_recovery_plan_action(row),
        "dry_run_only": True,
        "would_mutate": False,
        "safe_next_action": str(row.get("safe_next_action") or row.get("operator_guidance") or "Review pending publish diagnostics before drain."),
        "unsafe_if_ignored": str(row.get("unsafe_if_ignored") or "Running drain without evidence review can strand payloads or publish the wrong target."),
        "primary_concern": str(row.get("primary_concern") or row.get("issue_summary") or ""),
        "issue_summary": str(row.get("issue_summary") or row.get("error") or ""),
        "proof_summary": _json_safe(row.get("proof_summary") or []),
        "evidence_fields": _json_safe(row.get("evidence_fields") or []),
        "recommended_open_targets": _json_safe(row.get("recommended_open_targets") or []),
        "recommended_diagnostics_targets": _json_safe(row.get("recommended_diagnostics_targets") or ["pending_publish", "run_logs", "last_stderr_log"]),
        "local_file": str(row.get("local_file") or ""),
        "manifest_path": str(row.get("manifest_path") or ""),
        "server_out": str(row.get("server_out") or ""),
        "source_path": str(row.get("source_path") or ""),
    }


def pending_publish_recovery_plan_action_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        action = str(row.get("planned_action") or "manual_review_with_pending_diagnostics")
        counts[action] = counts.get(action, 0) + 1
    return dict(sorted(counts.items()))


def pending_publish_recovery_plan_summary_lines(data: Mapping[str, Any]) -> list[str]:
    rows = int_value(data.get("row_count"))
    blockers = int_value(data.get("blocker_count"))
    reviews = int_value(data.get("review_count"))
    ready = int_value(data.get("ready_count"))
    lines = [
        f"Dry-run recovery plan scope: {data.get('scope') or 'all'}",
        f"Rows planned: {rows}",
        f"Blockers/review/ready: {blockers} / {reviews} / {ready}",
        "Mutation guardrail: this plan does not move, delete, drain, repair, rewrite, or publish files.",
    ]
    if blockers:
        lines.append("Safe next action: do not drain; inspect blocker rows and diagnostics evidence first.")
    elif reviews:
        lines.append("Safe next action: review warning rows before using backend-owned Drain Parked Outputs.")
    elif ready:
        lines.append("Safe next action: rows look ready; Drain Parked Outputs remains the authoritative backend validation path.")
    else:
        lines.append("Safe next action: no parked rows were included in this plan.")
    return lines


def pending_publish_recovery_plan_data(rows: list[dict[str, Any]], *, scope: str, row_key: str) -> dict[str, Any]:
    plan_rows = [pending_publish_recovery_plan_row(row) for row in rows]
    blocker_count = sum(1 for row in rows if pending_publish_row_is_recovery_blocker(row))
    review_count = sum(
        1
        for row in rows
        if not pending_publish_row_is_recovery_blocker(row)
        and str(row.get("operator_trust_state") or "").casefold() != "ready-looking"
        and str(row.get("recovery_class") or "").casefold() != "ready_to_validate"
    )
    ready_count = max(0, len(rows) - blocker_count - review_count)
    data: dict[str, Any] = {
        "schema_version": PENDING_PUBLISH_RECOVERY_PLAN_SCHEMA_VERSION,
        "scope": scope,
        "selected_row_key": row_key,
        "row_count": len(rows),
        "blocker_count": blocker_count,
        "review_count": review_count,
        "ready_count": ready_count,
        "action_counts": pending_publish_recovery_plan_action_counts(plan_rows),
        "rows": plan_rows,
        "dry_run_only": True,
        "would_mutate": False,
        "mutation_guardrail": "This plan does not move, delete, drain, repair, rewrite, or publish files.",
    }
    data["summary_lines"] = pending_publish_recovery_plan_summary_lines(data)
    return data


def pending_publish_recovery_plan_result(rows: list[dict[str, Any]], request: Mapping[str, Any]) -> CommandResult:
    row_key = normalize_pending_publish_row_key(request.get("row_key"))
    scope = normalize_pending_publish_recovery_scope(request.get("scope"), row_key)
    selected_rows = rows
    if scope == "selected":
        if not row_key:
            return pending_publish_recovery_plan_missing_row_result(row_key)
        selected_rows = [row for row in rows if pending_publish_row_key(row) == row_key]
        if not selected_rows:
            return pending_publish_recovery_plan_missing_row_result(row_key)
    data = pending_publish_recovery_plan_data(selected_rows, scope=scope, row_key=row_key)
    severity = "info"
    message = "Pending publish recovery plan built. No files were changed."
    warnings: list[str] = []
    if data["blocker_count"]:
        severity = "warning"
        warnings.append("One or more pending publish rows are do-not-drain blockers.")
        message = "Pending publish recovery plan found blocker rows. No files were changed."
    elif data["review_count"]:
        severity = "warning"
        warnings.append("One or more pending publish rows require review before drain.")
        message = "Pending publish recovery plan found review rows. No files were changed."
    elif data["row_count"] == 0:
        message = "Pending publish recovery plan found no parked rows. No files were changed."
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=True,
        message=message,
        severity=severity,
        warnings=warnings,
        data=data,
        refresh_hint="pending_publish",
    )


def pending_publish_recovery_plan_missing_row_result(row_key: str) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=False,
        message="Pending publish recovery plan row was not found in the current backend scan.",
        severity="warning",
        warnings=["Refresh pending publish and select the row again, or build an all-rows dry-run plan."],
        data={"row_key": row_key, "dry_run_only": True, "would_mutate": False},
        refresh_hint="pending_publish",
    )


def pending_publish_recovery_plan_service_unavailable_result() -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=False,
        message=PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
        severity="error",
        errors=[PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE],
        data={"dry_run_only": True, "would_mutate": False},
        refresh_hint="pending_publish",
    )


def pending_publish_recovery_plan_invalid_scan_result() -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=False,
        message=PENDING_PUBLISH_INVALID_RESULT_MESSAGE,
        severity="error",
        errors=[PENDING_PUBLISH_INVALID_RESULT_MESSAGE],
        data={"dry_run_only": True, "would_mutate": False},
        refresh_hint="pending_publish",
    )


def pending_publish_recovery_plan_scan_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
        ok=False,
        message=f"Pending publish scan failed before recovery plan: {exc}",
        severity="error",
        errors=[str(exc)],
        data={"dry_run_only": True, "would_mutate": False},
        refresh_hint="pending_publish",
    )


__all__ = [
    "normalize_pending_publish_recovery_scope",
    "pending_publish_recovery_plan_action",
    "pending_publish_recovery_plan_row",
    "pending_publish_recovery_plan_action_counts",
    "pending_publish_recovery_plan_summary_lines",
    "pending_publish_recovery_plan_data",
    "pending_publish_recovery_plan_result",
    "pending_publish_recovery_plan_missing_row_result",
    "pending_publish_recovery_plan_service_unavailable_result",
    "pending_publish_recovery_plan_invalid_scan_result",
    "pending_publish_recovery_plan_scan_exception_result",
]
