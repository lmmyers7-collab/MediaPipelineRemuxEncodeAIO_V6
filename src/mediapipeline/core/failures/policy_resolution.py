"""Failure preview policy and result helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.failures.retry_state import retry_state_for_failure_row, retry_state_payload
from mediapipeline.core.failures.contracts import FailureRecord

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_inventory import FailurePreviewDto


FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE = "Failure marker service is not available."
FAILURE_MARKERS_EMPTY_MESSAGE = "No failure markers are available from the state store."
FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE = "Failure report service is not available."
FAILURE_NO_JSON_REPORT_MESSAGE = "No failure JSON report is available yet."
FAILURE_LOADER_UNAVAILABLE_MESSAGE = "Failure report loader is not available."
FAILURE_JSON_EMPTY_MESSAGE = "Latest failure JSON contains no rows."


FAILURE_RESOLUTION_SCHEMA_VERSION = "desktop_failure_resolution.v1"
FAILURE_RESOLUTION_GROUP_SCHEMA_VERSION = "desktop_failure_resolution_group.v1"
FAILURE_EVIDENCE_DETAILS_SCHEMA_VERSION = "desktop_failure_evidence_details.v1"
FAILURE_EVIDENCE_MAX_LINES = 10
FAILURE_EVIDENCE_MAX_STREAM_ROWS = 16
FAILURE_EVIDENCE_MAX_PROOF_FIELDS = 16
FAILURE_OPEN_TARGETS = {
    "artifact": "failure artifact",
    "repro": "reproduction file",
    "record_file": "failure record file",
    "record_folder": "failure record folder",
}
FAILURE_RESOLUTION_OWNER_PAGES = {
    "Pending Publish": "pending",
    "Queue": "queue",
    "Settings": "settings",
    "Completed": "completed",
    "Diagnostics": "diagnostics",
    "Manual review": "diagnostics",
    "Backend retry": "",
}
FAILURE_LIFECYCLE_LABELS = {
    "new": "New",
    "acknowledged": "Acknowledged",
    "working": "Working",
    "waiting_backend": "Waiting retry",
    "ready_to_clear": "Ready to clear",
    "resolved": "Resolved",
    "reopened": "Reopened",
}
FAILURE_LIFECYCLE_TRANSITION_LABELS = {
    "acknowledge": "Acknowledge",
    "start_work": "Start work",
    "complete_step": "Complete step",
    "waive_step": "Waive step",
    "mark_resolved": "Mark resolved",
    "reopen": "Reopen",
}



from mediapipeline.core.failures.policy_support import *  # noqa: F403

from mediapipeline.core.failures.policy_evidence import *  # noqa: F403

from mediapipeline.core.failures.policy_markers import *  # noqa: F403

def _failure_suggested_fix(row: dict[str, object]) -> str:
    explicit = _failure_text(row.get("suggested_action"))
    if explicit:
        return explicit
    classification = _failure_text(row.get("classification")).casefold()
    if classification == "transient":
        return "Backend will retry this transient failure on the next backend queue pass. Compare logs first."
    if classification in {"operator_required", "permanent"}:
        return "Open diagnostics and review the source before retry."
    return "Review diagnostics before retry."


def _failure_resolution_search_text(row: dict[str, object]) -> str:
    evidence_lines = _failure_evidence_display_lines(
        row.get("evidence_details") if isinstance(row.get("evidence_details"), dict) else {},
        include_fallback=False,
    )
    values = [
        row.get("stage"),
        row.get("error_code"),
        row.get("classification"),
        row.get("reason"),
        row.get("suggested_action"),
        row.get("retry_safe_next_action"),
        row.get("lookup_title"),
        row.get("source_path"),
        row.get("media_type"),
        *evidence_lines,
    ]
    return " ".join(_failure_text(value) for value in values if _failure_text(value)).casefold()


def _failure_resolution_owner(row: dict[str, object]) -> str:
    text = _failure_resolution_search_text(row)
    classification = _failure_text(row.get("classification")).casefold()
    if "publish" in text or "pending" in text:
        return "Pending Publish"
    if "queue" in text:
        return "Queue"
    if any(token in text for token in ("subtitle", "bdpgs", "tx3g", "vobsub", "ocr")):
        return "Settings"
    if any(token in text for token in ("audio", "commentary", "language")):
        return "Settings"
    if any(token in text for token in ("setting", "policy", "config", "profile")):
        return "Settings"
    if any(token in text for token in ("completed", "output", "manifest")):
        return "Completed"
    if row.get("retry_allowed") is True or classification == "transient":
        return "Backend retry"
    if classification in {"operator_required", "permanent"}:
        return "Manual review"
    return "Diagnostics"


def _failure_resolution_diagnostic_targets(row: dict[str, object], owner: str) -> list[dict[str, str]]:
    targets = [
        {
            "kind": "tail",
            "target": "latest_failure_report",
            "label": "Read Latest Failure",
            "reason": "Read the bounded latest failure text before deciding on cleanup or retry.",
        },
        {
            "kind": "open",
            "target": "latest_failure_json",
            "label": "Open Failure JSON",
            "reason": "Inspect the structured failure payload behind the group.",
        },
        {
            "kind": "open",
            "target": "failed_reports",
            "label": "Open Failure Reports",
            "reason": "Open backend-selected failure report evidence.",
        },
        {
            "kind": "open",
            "target": "run_logs",
            "label": "Open Run Logs",
            "reason": "Compare the issue with recent runtime logs before retry.",
        },
    ]
    classification = _failure_text(row.get("classification")).casefold()
    stage = _failure_text(row.get("stage")).casefold()
    if classification in {"operator_required", "permanent"}:
        targets.append(
            {
                "kind": "open",
                "target": "failed_markers",
                "label": "Open Failure Markers",
                "reason": "Inspect active failure markers before clearing blockers.",
            }
        )
    if owner == "Pending Publish" or "publish" in stage:
        targets.append(
            {
                "kind": "open",
                "target": "pending_publish",
                "label": "Open Pending Publish",
                "reason": "Compare the failure with parked output state.",
            }
        )
    if owner in {"Queue", "Backend retry"} or "queue" in stage:
        targets.append(
            {
                "kind": "open",
                "target": "queue_snapshot",
                "label": "Open Queue Snapshot",
                "reason": "Compare the failure with current queue visibility.",
            }
        )
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for target in targets:
        key = (target["kind"], target["target"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(target)
    return unique


def _failure_resolution_primary_action(
    *,
    owner: str,
    clearable: bool,
    retry_allowed: bool,
) -> dict[str, object]:
    if retry_allowed:
        return {
            "kind": "wait_for_backend_retry",
            "label": "Wait for backend retry",
            "safe": True,
            "page": "",
        }
    owner_page = FAILURE_RESOLUTION_OWNER_PAGES.get(owner, "")
    if owner_page:
        label = "Review in Diagnostics" if owner_page == "diagnostics" else f"Open {owner}"
        return {
            "kind": "open_owner_page",
            "label": label,
            "owner": owner,
            "page": owner_page,
            "safe": True,
        }
    if clearable:
        return {
            "kind": "preview_marker_clear",
            "label": "Preview marker clear",
            "safe": True,
            "page": "",
        }
    return {
        "kind": "review_details",
        "label": "Review details",
        "owner": owner or "Diagnostics",
        "page": "diagnostics",
        "safe": True,
    }


def _failure_resolution_action_step(owner: str, action: dict[str, object]) -> tuple[str, str]:
    label = _failure_text(action.get("label") if isinstance(action, dict) else "") or "Review details"
    if _failure_text(action.get("kind") if isinstance(action, dict) else "") == "wait_for_backend_retry":
        return "wait_backend_retry", "Backend will retry this transient failure; keep evidence visible and do not clear markers yet."
    if owner == "Pending Publish":
        return "open_owner", "Open Pending Publish and compare parked output, destination, and drain evidence."
    if owner == "Queue":
        return "open_owner", "Open Queue and compare current row, hold, retry, and queue snapshot evidence."
    if owner == "Settings":
        return "open_owner", "Open Settings and correct the profile, subtitle, audio, config, or policy input that caused the stop."
    if owner == "Completed":
        return "open_owner", "Open Completed and compare manifest/output evidence before accepting or rerunning."
    if owner in {"Diagnostics", "Manual review"}:
        return "open_owner", "Open Diagnostics and inspect failure JSON, reports, markers, and run logs."
    return "primary_action", label


def _failure_resolution_group_key(row: dict[str, object], owner: str, suggested_action: str) -> str:
    parts = [
        _failure_text(row.get("error_code")).casefold() or "no-code",
        _failure_text(row.get("stage")).casefold() or "unknown-stage",
        owner.casefold() or "unknown-owner",
        suggested_action.casefold() or "review",
    ]
    return "\u001f".join(parts)


def _failure_resolution_severity_priority(severity: str) -> int:
    value = str(severity or "").casefold()
    if value in {"blocked", "error", "failed", "critical", "danger", "fatal"}:
        return 0
    if value in {"warning", "warn", "retrying", "review", "stale"}:
        return 1
    if value in {"info", "unknown"}:
        return 2
    return 3


def _failure_resolution_status_label(severity: str) -> str:
    if _failure_resolution_severity_priority(severity) == 0:
        return "Needs operator"
    if _failure_resolution_severity_priority(severity) == 1:
        return "Review"
    return "Recorded"


def _failure_journal_events_for_group(group: dict[str, object], journal_state: dict[str, object] | None) -> list[dict[str, object]]:
    journal_key = _failure_text(group.get("journal_key")) or _failure_text(group.get("group_key"))
    if not journal_key or not isinstance(journal_state, dict):
        return []
    events = [event for event in journal_state.get("events") or [] if isinstance(event, dict)]
    return [
        event for event in events
        if _failure_text(event.get("journal_key")).casefold() == journal_key.casefold()
    ][-8:]


def _failure_lifecycle_state(group: dict[str, object], events: list[dict[str, object]]) -> str:
    clearable_count = int(group.get("clearable_count") or 0)
    retryable_count = int(group.get("retryable_count") or 0)
    blocking_count = int(group.get("blocking_count") or 0)
    last_state = _failure_text(events[-1].get("lifecycle_state") if events else "").casefold()
    if last_state == "resolved" and clearable_count > 0:
        return "reopened"
    if last_state in FAILURE_LIFECYCLE_LABELS:
        return last_state
    if retryable_count > 0 and blocking_count == 0:
        return "waiting_backend"
    if clearable_count > 0 and blocking_count == 0:
        return "ready_to_clear"
    return "new"


def _failure_available_transitions(state: str, verification: dict[str, object]) -> list[dict[str, object]]:
    transitions_by_state = {
        "new": ["acknowledge", "start_work"],
        "acknowledged": ["start_work", "mark_resolved"],
        "working": ["complete_step", "mark_resolved"],
        "waiting_backend": ["acknowledge", "start_work"],
        "ready_to_clear": ["mark_resolved"],
        "resolved": ["reopen"],
        "reopened": ["start_work", "mark_resolved"],
    }
    blockers = verification.get("blockers") if isinstance(verification, dict) else []
    safe_to_resolve = bool(verification.get("safe_to_resolve")) if isinstance(verification, dict) else False
    transitions: list[dict[str, object]] = []
    for transition in transitions_by_state.get(state, ["acknowledge"]):
        disabled = transition == "mark_resolved" and not safe_to_resolve
        reason = "; ".join(str(item) for item in blockers if str(item).strip()) if disabled else ""
        transitions.append(
            {
                "transition": transition,
                "label": FAILURE_LIFECYCLE_TRANSITION_LABELS.get(transition, transition.replace("_", " ").title()),
                "preview_required": transition in {"mark_resolved", "reopen", "waive_step"},
                "reason_required": transition in {"mark_resolved", "reopen", "waive_step"},
                "disabled": disabled,
                "disabled_reason": reason,
            }
        )
    return transitions


def _failure_verification(group: dict[str, object]) -> dict[str, object]:
    active_marker_count = int(group.get("clearable_count") or 0)
    retryable_count = int(group.get("retryable_count") or 0)
    active_rows = int(group.get("row_count") or 0)
    blockers: list[str] = []
    if active_marker_count:
        blockers.append("Active failure markers remain in the backend marker folder.")
    if retryable_count:
        blockers.append("At least one row is retryable; wait for backend retry unless operator review changes the cause.")
    return {
        "schema_version": "failure_resolution_verification.v1",
        "active_marker_count": active_marker_count,
        "active_failure_row_count": active_rows,
        "blocking_count": int(group.get("blocking_count") or 0),
        "retryable_count": retryable_count,
        "clearable": active_marker_count > 0,
        "safe_to_resolve": active_marker_count == 0,
        "blockers": blockers,
        "safe_next_action": (
            "Preview and clear markers only after the root cause is understood."
            if active_marker_count
            else "Markers are not active for this group; it can be marked resolved if evidence was reviewed."
        ),
    }


def _failure_playbook_steps(
    group: dict[str, object],
    *,
    lifecycle_state: str,
    verification: dict[str, object],
) -> list[dict[str, object]]:
    owner = _failure_text(group.get("owner")) or "Diagnostics"
    action = group.get("primary_action") if isinstance(group.get("primary_action"), dict) else {}
    action_step_id, action_detail = _failure_resolution_action_step(owner, action)
    resolved = lifecycle_state == "resolved"
    working_started = lifecycle_state in {"working", "ready_to_clear", "resolved"}
    acknowledged = lifecycle_state in {"acknowledged", "working", "ready_to_clear", "resolved"}
    markers_clear = int(verification.get("active_marker_count") or 0) == 0
    return [
        {
            "id": "review_evidence",
            "label": "Review evidence",
            "detail": "Read why it stopped and compare failure JSON, reports, markers, and run logs.",
            "status": "done" if acknowledged or working_started or resolved else "current",
        },
        {
            "id": action_step_id,
            "label": _failure_text(action.get("label") if isinstance(action, dict) else "") or "Open owner page",
            "detail": action_detail,
            "status": "done" if working_started or resolved else "current" if acknowledged else "not_started",
        },
        {
            "id": "verify_markers",
            "label": "Verify marker state",
            "detail": "Confirm whether active backend failure markers still block retry.",
            "status": "done" if markers_clear else "current" if working_started else "not_started",
        },
        {
            "id": "close_issue",
            "label": "Close issue",
            "detail": "Mark resolved only after verification passes; reopen if matching markers return.",
            "status": "done" if resolved else "current" if markers_clear else "blocked",
        },
    ]


def _failure_enrich_resolution_group(group: dict[str, object], journal_state: dict[str, object] | None) -> dict[str, object]:
    group["journal_key"] = _failure_text(group.get("journal_key")) or _failure_text(group.get("group_key"))
    events = _failure_journal_events_for_group(group, journal_state)
    group["timeline"] = [
        {
            "recorded_at": _failure_text(event.get("recorded_at")),
            "transition": _failure_text(event.get("transition")),
            "lifecycle_state": _failure_text(event.get("lifecycle_state")),
            "reason": _failure_text(event.get("reason")),
            "operator_note": _failure_text(event.get("operator_note")),
        }
        for event in events
    ]
    lifecycle_state = _failure_lifecycle_state(group, events)
    group["lifecycle_state"] = lifecycle_state
    group["lifecycle_label"] = FAILURE_LIFECYCLE_LABELS.get(lifecycle_state, lifecycle_state.replace("_", " ").title())
    last_event = events[-1] if events else {}
    group["last_transition_at"] = _failure_text(last_event.get("recorded_at") if isinstance(last_event, dict) else "")
    group["operator_note"] = _failure_text(last_event.get("operator_note") if isinstance(last_event, dict) else "")
    verification = _failure_verification(group)
    group["verification"] = verification
    group["playbook_steps"] = _failure_playbook_steps(
        group,
        lifecycle_state=lifecycle_state,
        verification=verification,
    )
    group["available_transitions"] = _failure_available_transitions(lifecycle_state, verification)
    group["resolution_journal_path"] = _failure_text(journal_state.get("path") if isinstance(journal_state, dict) else "")
    return group


def _failure_resolution_groups(rows: list[dict[str, object]], *, journal_state: dict[str, object] | None = None) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    severity_rank: dict[str, int] = {}
    for row in rows:
        triage = row.get("triage") if isinstance(row.get("triage"), dict) else {}
        suggested_action = _failure_text(triage.get("suggested_fix") if isinstance(triage, dict) else "") or _failure_suggested_fix(row)
        owner = _failure_resolution_owner(row)
        group_key = _failure_resolution_group_key(row, owner, suggested_action)
        clear_error = row.get("clear_error") if isinstance(row.get("clear_error"), dict) else {}
        clearable_paths = _unique_failure_marker_paths(clear_error.get("marker_paths") if isinstance(clear_error, dict) else [])
        severity = _failure_text(triage.get("severity") if isinstance(triage, dict) else "") or "info"
        priority = _failure_resolution_severity_priority(severity)
        existing = grouped.get(group_key)
        if existing is None:
            existing = {
                "schema_version": FAILURE_RESOLUTION_GROUP_SCHEMA_VERSION,
                "group_key": group_key,
                "journal_key": group_key,
                "status_label": _failure_text(triage.get("status_label") if isinstance(triage, dict) else "")
                or _failure_resolution_status_label(severity),
                "severity": severity,
                "error_code": _failure_text(row.get("error_code")) or "NO_CODE",
                "stage": _failure_text(row.get("stage")) or "unknown-stage",
                "owner": owner,
                "owner_page": FAILURE_RESOLUTION_OWNER_PAGES.get(owner, ""),
                "suggested_action": suggested_action,
                "cause": _failure_text(triage.get("plain_summary") if isinstance(triage, dict) else "") or _failure_plain_summary(row),
                "safe_next_action": _failure_text(triage.get("safe_next_action") if isinstance(triage, dict) else "")
                or _failure_text(row.get("retry_safe_next_action"))
                or suggested_action,
                "row_count": 0,
                "affected_row_keys": [],
                "affected_sources": [],
                "sample_rows": [],
                "evidence_lines": [],
                "clearable_marker_paths": [],
                "clearable_count": 0,
                "marker_count": 0,
                "blocking_count": 0,
                "retryable_count": 0,
                "operator_required_count": 0,
                "permanent_count": 0,
                "transient_count": 0,
                "diagnostic_targets": _failure_resolution_diagnostic_targets(row, owner),
                "primary_action": {},
            }
            grouped[group_key] = existing
            severity_rank[group_key] = priority
        elif priority < severity_rank[group_key]:
            existing["severity"] = severity
            existing["status_label"] = _failure_text(triage.get("status_label") if isinstance(triage, dict) else "") or existing.get("status_label")
            severity_rank[group_key] = priority

        existing["row_count"] = int(existing.get("row_count") or 0) + 1
        classification = _failure_text(row.get("classification")).casefold()
        if classification == "operator_required":
            existing["operator_required_count"] = int(existing.get("operator_required_count") or 0) + 1
        if classification == "permanent":
            existing["permanent_count"] = int(existing.get("permanent_count") or 0) + 1
        if classification == "transient":
            existing["transient_count"] = int(existing.get("transient_count") or 0) + 1
        if classification in {"operator_required", "permanent"} or _failure_text(row.get("retry_status_state")).casefold() == "blocked":
            existing["blocking_count"] = int(existing.get("blocking_count") or 0) + 1
        if row.get("retry_allowed") is True:
            existing["retryable_count"] = int(existing.get("retryable_count") or 0) + 1

        row_key = _failure_text(row.get("row_key")) or _failure_row_key(row)
        if row_key and row_key not in existing["affected_row_keys"]:
            existing["affected_row_keys"].append(row_key)
        source = _failure_text(row.get("lookup_title")) or _failure_text(row.get("source_path")) or _failure_text(row.get("source_json"))
        if source and source not in existing["affected_sources"]:
            existing["affected_sources"].append(source)
        if len(existing["sample_rows"]) < 5:
            existing["sample_rows"].append(row)
        for line in _failure_evidence_display_lines(
            row.get("evidence_details") if isinstance(row.get("evidence_details"), dict) else {},
            include_fallback=False,
        ):
            if line not in existing["evidence_lines"] and len(existing["evidence_lines"]) < FAILURE_EVIDENCE_MAX_LINES:
                existing["evidence_lines"].append(line)
        marker_paths = _unique_failure_marker_paths([*existing["clearable_marker_paths"], *clearable_paths])
        existing["clearable_marker_paths"] = marker_paths
        existing["clearable_count"] = len(marker_paths)
        existing["marker_count"] = len(marker_paths)

    for group in grouped.values():
        retryable = int(group.get("retryable_count") or 0) > 0
        clearable = int(group.get("clearable_count") or 0) > 0
        group["primary_action"] = _failure_resolution_primary_action(
            owner=_failure_text(group.get("owner")),
            clearable=clearable,
            retry_allowed=retryable,
        )
        group["primary_action_label"] = _failure_text(group["primary_action"].get("label") if isinstance(group["primary_action"], dict) else "")
        group["safe_next_action"] = _failure_text(group.get("safe_next_action")) or group["primary_action_label"]
        _failure_enrich_resolution_group(group, journal_state)

    return sorted(
        grouped.values(),
        key=lambda item: (
            _failure_resolution_severity_priority(_failure_text(item.get("severity"))),
            -int(item.get("blocking_count") or 0),
            -int(item.get("clearable_count") or 0),
            -int(item.get("row_count") or 0),
            _failure_text(item.get("error_code")),
            _failure_text(item.get("stage")),
        ),
    )


def _failure_resolution_summary(
    *,
    rows: list[dict[str, object]],
    groups: list[dict[str, object]],
    source: str,
    source_kind: str,
    warnings: list[str],
) -> dict[str, object]:
    primary = groups[0] if groups else {}
    retryable_count = sum(int(group.get("retryable_count") or 0) for group in groups)
    blocking_count = sum(int(group.get("blocking_count") or 0) for group in groups)
    clearable_paths = _unique_failure_marker_paths(
        [path for group in groups for path in (group.get("clearable_marker_paths") or [])]
    )
    status = "empty"
    status_label = "No active failures"
    if rows:
        if blocking_count:
            status = "blocked"
            status_label = "Needs operator"
        elif retryable_count:
            status = "retrying"
            status_label = "Will retry"
        elif warnings:
            status = "warning"
            status_label = "Review"
        else:
            status = "review"
            status_label = "Review"
    elif warnings:
        status = "warning"
        status_label = "No rows"
    primary_action = primary.get("primary_action") if isinstance(primary, dict) else {}
    return {
        "schema_version": FAILURE_RESOLUTION_SCHEMA_VERSION,
        "status": status,
        "status_label": status_label,
        "source": source,
        "source_kind": source_kind,
        "source_mode_label": "Failure markers" if source_kind == "markers" else "Latest failure JSON",
        "refresh_state": "partial" if warnings and rows else "empty" if not rows else "loaded",
        "row_count": len(rows),
        "group_count": len(groups),
        "primary_group_key": _failure_text(primary.get("group_key") if isinstance(primary, dict) else ""),
        "primary_group_label": _failure_text(primary.get("cause") if isinstance(primary, dict) else ""),
        "primary_owner": _failure_text(primary.get("owner") if isinstance(primary, dict) else "") or "Reports",
        "primary_action": primary_action if isinstance(primary_action, dict) else {},
        "primary_action_label": _failure_text(primary_action.get("label") if isinstance(primary_action, dict) else "")
        or ("Refresh Reports" if not rows else "Review details"),
        "safe_next_action": _failure_text(primary.get("safe_next_action") if isinstance(primary, dict) else "")
        or ("Refresh Reports or open Diagnostics if a recent failure was expected." if not rows else "Review grouped failure evidence."),
        "blocking_count": blocking_count,
        "retryable_count": retryable_count,
        "clearable_count": len(clearable_paths),
        "clearable_marker_paths": clearable_paths,
        "warning_count": len(warnings),
        "lifecycle_counts": {
            state: sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == state)
            for state in FAILURE_LIFECYCLE_LABELS
        },
        "unacknowledged_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "new"),
        "working_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "working"),
        "waiting_backend_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "waiting_backend"),
        "ready_to_clear_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "ready_to_clear"),
        "resolved_recently_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "resolved"),
    }

__all__ = (
    "_failure_suggested_fix",
    "_failure_resolution_search_text",
    "_failure_resolution_owner",
    "_failure_resolution_diagnostic_targets",
    "_failure_resolution_primary_action",
    "_failure_resolution_action_step",
    "_failure_resolution_group_key",
    "_failure_resolution_severity_priority",
    "_failure_resolution_status_label",
    "_failure_journal_events_for_group",
    "_failure_lifecycle_state",
    "_failure_available_transitions",
    "_failure_verification",
    "_failure_playbook_steps",
    "_failure_enrich_resolution_group",
    "_failure_resolution_groups",
    "_failure_resolution_summary",
)
