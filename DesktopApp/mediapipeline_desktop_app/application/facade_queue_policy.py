from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..models import QueueRecord
from .dto import CommandResult
from .facade_artifact_freshness import datetime_freshness_fields, file_freshness_fields
from .facade_status_policy import progress_bar
from .runtime_outcomes import RUNTIME_OUTCOME_EVENT_LIMIT, runtime_outcome_index, source_identity_key


NO_QUEUE_SNAPSHOT_WARNING = "No queue snapshot is available yet."
QUEUE_PREVIEW_SERVICE_WARNING = "Queue preview service is not available."
INVALID_QUEUE_SNAPSHOT_WARNING = "Queue snapshot is missing or invalid."
EMPTY_QUEUE_SNAPSHOT_WARNING = "Queue snapshot contains no runnable rows."
QUEUE_SNAPSHOT_STALE_AFTER_SECONDS = 3600
QUEUE_RUNTIME_OUTCOME_EVENT_LIMIT = RUNTIME_OUTCOME_EVENT_LIMIT
QUEUE_SOURCE_SCAN_PROGRESS_SCHEMA_VERSION = "desktop_queue_source_scan_progress.v1"
QUEUE_OPEN_COMMAND = "queue.open"
QUEUE_REFRESH_HINT = "queue"
QUEUE_OPEN_TARGETS = {
    "source_file": "queue source file",
    "source_folder": "queue source folder",
    "source_root": "queue source root",
}
QUEUE_OPEN_SCOPES = {
    "runnable": "runnable queue row",
    "excluded": "excluded source row",
}


def queue_row_key(row: dict[str, Any]) -> str:
    return "\x1f".join(
        [
            str(row.get("source_path") or ""),
            str(row.get("global_order") or ""),
            str(row.get("queue_index") or ""),
            str(row.get("route_name") or ""),
        ]
    ).casefold()


def queue_record_to_row(record: QueueRecord) -> dict[str, Any]:
    row = {
        "source_path": str(record.source_path),
        "source_root": str(record.source_root),
        "media_type": record.media_type,
        "is_priority": record.is_priority,
        "priority_reasons": list(record.priority_reasons),
        "priority_rank": record.priority_rank,
        "display_name": record.display_name,
        "relative_path": record.relative_path,
        "show_folder": record.show_folder,
        "season_folder": record.season_folder,
        "season_number": record.season_number,
        "episode_number": record.episode_number,
        "size_gb": record.size_gb,
        "route_name": record.route_name,
        "route_reason": record.route_reason,
        "queue_index": record.queue_index,
        "queue_total": record.queue_total,
        "queue_position": record.queue_position,
        "phase": record.phase,
        "global_order": record.global_order,
    }
    row["row_key"] = queue_row_key(row)
    row["available_open_targets"] = queue_row_available_open_targets(row)
    row.update(queue_row_operator_guidance(row))
    return row


def queue_row_available_open_targets(row: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    if str(row.get("source_path") or "").strip():
        targets.extend(["source_file", "source_folder"])
    if str(row.get("source_root") or "").strip():
        targets.append("source_root")
    return targets


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
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    runtime_failed = runtime_success is False or runtime_success_text == "false" or runtime_outcome_status.casefold() in {
        "failed",
        "skipped",
        "stopped",
        "transient_failure",
        "permanent_failure",
        "operator_required_failure",
        "failure_recorded",
    }
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
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    runtime_failed = runtime_success is False or runtime_success_text == "false" or runtime_status.casefold() in {
        "failed",
        "skipped",
        "stopped",
        "transient_failure",
        "permanent_failure",
        "operator_required_failure",
        "failure_recorded",
    }

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


def queue_row_route_decision_summary(row: dict[str, Any]) -> str:
    route_name = str(row.get("route_name") or "").strip()
    route_reason_code = str(row.get("route_reason_code") or "").strip()
    route_reason = str(row.get("route_reason") or "").strip()
    if route_name and route_reason_code:
        return f"{route_name} ({route_reason_code})"
    if route_name and route_reason:
        return f"{route_name} ({route_reason})"
    if route_name:
        return route_name
    return "Route not reported"


def queue_row_route_evidence_lines(row: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    route_name = str(row.get("route_name") or "").strip()
    route_reason_code = str(row.get("route_reason_code") or "").strip()
    route_reason = str(row.get("route_reason") or "").strip()
    blocked_reason = str(row.get("blocked_reason") or "").strip()
    blocked_reason_code = str(row.get("blocked_reason_code") or "").strip()
    if route_name:
        lines.append(f"Route: {route_name}")
    if route_reason_code:
        lines.append(f"Reason code: {route_reason_code}")
    if route_reason:
        lines.append(f"Reason: {route_reason}")
    if blocked_reason:
        if blocked_reason_code:
            lines.append(f"Blocked reason code: {blocked_reason_code}")
        lines.append(f"Blocked reason: {blocked_reason}")
    media_type = str(row.get("media_type") or "").strip()
    phase = str(row.get("phase") or "").strip()
    if media_type or phase:
        lines.append(f"Media/phase: {media_type or 'unknown'} / {phase or 'unknown'}")
    if str(row.get("is_priority") or "").casefold() == "true" or bool(row.get("is_priority")):
        reasons = row.get("priority_reasons")
        reason_text = ", ".join(str(item) for item in reasons if str(item).strip()) if isinstance(reasons, list) else ""
        lines.append(f"Priority: yes{f' ({reason_text})' if reason_text else ''}")
    if str(row.get("media_type") or "").casefold() == "tv":
        season = row.get("season_number")
        episode = row.get("episode_number")
        show = str(row.get("show_folder") or "").strip()
        season_folder = str(row.get("season_folder") or "").strip()
        if not show or not season_folder:
            relative_parts = [part for part in str(row.get("relative_path") or "").replace("/", "\\").split("\\") if part]
            folder_parts = relative_parts[:-1]
            if not season_folder and folder_parts:
                season_folder = folder_parts[-1]
            if not show and len(folder_parts) >= 2:
                show = folder_parts[-2]
            elif not show and folder_parts:
                show = folder_parts[-1]
        if show or season_folder or season not in (None, "") or episode not in (None, ""):
            lines.append(f"TV parse: show={show or 'unknown'}; folder={season_folder or 'unknown'}; S{int(season or 0):02d}E{int(episode or 0):02d}")
    size_gb = row.get("size_gb")
    if size_gb not in (None, ""):
        lines.append(f"Source size: {size_gb} GB")
    position = str(row.get("queue_position") or "").strip() or f"{row.get('queue_index') or ''}/{row.get('queue_total') or ''}".strip("/")
    if position:
        lines.append(f"Queue position: {position}")
    last_write = str(row.get("last_write_utc") or "").strip()
    if last_write:
        lines.append(f"Source last write: {last_write}")
    runtime_codes = [str(item).strip() for item in row.get("runtime_check_codes") or [] if str(item).strip()] if isinstance(row.get("runtime_check_codes"), list) else []
    runtime_notes = [str(item).strip() for item in row.get("runtime_check_notes") or [] if str(item).strip()] if isinstance(row.get("runtime_check_notes"), list) else []
    if bool(row.get("runtime_checks_deferred")) or runtime_codes:
        lines.append(f"Runtime checks deferred: {', '.join(runtime_codes) if runtime_codes else 'yes'}")
        for note in runtime_notes[:4]:
            lines.append(f"Runtime note: {note}")
    runtime_status = str(row.get("runtime_outcome_status") or "").strip()
    if runtime_status:
        runtime_at = str(row.get("runtime_outcome_at") or "").strip()
        runtime_event = str(row.get("runtime_outcome_event_type") or "").strip()
        runtime_freshness = str(row.get("runtime_outcome_freshness_status") or "").strip()
        runtime_age = str(row.get("runtime_outcome_age_text") or "").strip()
        runtime_error = str(row.get("runtime_outcome_error_code") or "").strip()
        runtime_reason = str(row.get("runtime_outcome_reason") or "").strip()
        runtime_stage = str(row.get("runtime_outcome_stage") or "").strip()
        runtime_route = str(row.get("runtime_outcome_route") or "").strip()
        lines.append(
            "Last runtime outcome: "
            f"{runtime_status}"
            f"{f' via {runtime_event}' if runtime_event else ''}"
            f"{f' at {runtime_at}' if runtime_at else ''}"
            f"{f' ({runtime_age}; {runtime_freshness})' if runtime_age or runtime_freshness else ''}"
        )
        if runtime_stage or runtime_route:
            lines.append(f"Runtime stage/route: {runtime_stage or 'unknown'} / {runtime_route or 'unknown'}")
        if runtime_error:
            lines.append(f"Runtime error code: {runtime_error}")
        if runtime_reason:
            lines.append(f"Runtime reason: {runtime_reason}")
        publish_state = str(row.get("runtime_outcome_publish_state") or "").strip()
        publish_mode = str(row.get("runtime_outcome_publish_mode") or "").strip()
        if publish_state or publish_mode:
            lines.append(f"Runtime publish: {publish_state or 'unknown'} / {publish_mode or 'unknown'}")
        output_path = str(row.get("runtime_outcome_output_path") or "").strip()
        if output_path:
            lines.append(f"Runtime output: {output_path}")
    return lines


def queue_apply_runtime_outcomes(rows: list[dict[str, Any]], events: Iterable[Any]) -> list[dict[str, Any]]:
    outcome_index = runtime_outcome_index(events)
    if not outcome_index:
        return rows
    for row in rows:
        source_key = source_identity_key(row.get("source_path"))
        if not source_key:
            continue
        outcome = outcome_index.get(source_key)
        if outcome is None:
            continue
        row.update(outcome)
        row.update(queue_row_operator_guidance(row))
    return rows


def queue_preview_rows(
    raw_rows: Iterable[Any],
    row_factory: Callable[[dict[str, Any]], object],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            continue
        try:
            record = row_factory(raw_row)
        except Exception as exc:
            invalid_row = {"status": "invalid", "error": str(exc), "raw": raw_row}
            invalid_row["available_open_targets"] = queue_row_available_open_targets(invalid_row)
            invalid_row.update(queue_row_operator_guidance(invalid_row))
            rows.append(invalid_row)
            continue
        if isinstance(record, QueueRecord):
            safe_row = queue_record_to_row(record)
            safe_row["route_reason_code"] = str(raw_row.get("route_reason_code") or "").strip()
            safe_row["blocked_reason_code"] = str(raw_row.get("blocked_reason_code") or "").strip()
            safe_row["blocked_reason"] = str(raw_row.get("blocked_reason") or "").strip()
            safe_row["last_write_utc"] = str(raw_row.get("last_write_utc") or "").strip()
            safe_row["runtime_checks_deferred"] = bool(raw_row.get("runtime_checks_deferred", False))
            safe_row["runtime_check_codes"] = [str(item) for item in raw_row.get("runtime_check_codes") or [] if str(item).strip()] if isinstance(raw_row.get("runtime_check_codes"), list) else []
            safe_row["runtime_check_notes"] = [str(item) for item in raw_row.get("runtime_check_notes") or [] if str(item).strip()] if isinstance(raw_row.get("runtime_check_notes"), list) else []
            safe_row["row_key"] = queue_row_key(safe_row)
            safe_row["available_open_targets"] = queue_row_available_open_targets(safe_row)
            safe_row.update(queue_row_operator_guidance(safe_row))
            rows.append(safe_row)
    return rows


def queue_preview_warnings(rows: list[dict[str, Any]]) -> list[str]:
    return [] if rows else [EMPTY_QUEUE_SNAPSHOT_WARNING]


def queue_snapshot_int(snapshot: dict[str, Any], key: str) -> int:
    try:
        return max(0, int(snapshot.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def queue_safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def queue_safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def queue_media_type_label(value: Any) -> str:
    media_kind = str(value or "").strip().casefold()
    if media_kind == "tv":
        return "TV"
    if media_kind == "movie":
        return "Movie"
    return "Unknown"


def queue_excluded_row_key(row: dict[str, Any]) -> str:
    return "\x1f".join(
        [
            str(row.get("source_path") or ""),
            str(row.get("source_order") or ""),
            str(row.get("reason_code") or ""),
        ]
    ).casefold()


def queue_preview_excluded_rows(raw_rows: Iterable[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            continue
        source_path = str(raw_row.get("source_path") or "").strip()
        if not source_path:
            continue
        media_type = queue_media_type_label(raw_row.get("media_kind"))
        reason_code = str(raw_row.get("reason_code") or "excluded").strip() or "excluded"
        row = {
            "source_order": queue_safe_int(raw_row.get("source_order")),
            "reason_code": reason_code,
            "reason": str(raw_row.get("reason") or "").strip(),
            "phase": str(raw_row.get("phase") or "").strip(),
            "media_type": media_type,
            "media_kind": str(raw_row.get("media_kind") or "").strip(),
            "queue_index": queue_safe_int(raw_row.get("queue_index")),
            "queue_total": queue_safe_int(raw_row.get("queue_total")),
            "is_priority": bool(raw_row.get("is_priority", False)),
            "priority_reasons": [str(item) for item in raw_row.get("priority_reasons") or [] if str(item).strip()]
            if isinstance(raw_row.get("priority_reasons"), list)
            else [],
            "priority_rank": queue_safe_int(raw_row.get("priority_rank")),
            "source_path": source_path,
            "source_root": str(raw_row.get("root_path") or raw_row.get("source_root") or "").strip(),
            "relative_path": str(raw_row.get("relative_path") or "").strip(),
            "display_name": str(raw_row.get("display_name") or Path(source_path).name).strip(),
            "show_folder": str(raw_row.get("show_sort_key") or "").strip(),
            "season_folder": str(raw_row.get("season_sort_key") or "").strip(),
            "season_number": queue_safe_int(raw_row.get("season_number")),
            "episode_number": queue_safe_int(raw_row.get("episode_number")),
            "size_gb": queue_safe_float(raw_row.get("size_gb")),
            "last_write_utc": str(raw_row.get("last_write_utc") or "").strip(),
        }
        row["row_key"] = queue_excluded_row_key(row)
        row["available_open_targets"] = queue_row_available_open_targets(row)
        rows.append(row)
    return rows


def queue_count_by_key(rows: Iterable[dict[str, Any]], key: str, *, default: str = "unknown") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or default).strip() or default
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def queue_counts_text(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={count}" for key, count in sorted(counts.items())) or "none"


def queue_count_list_values(rows: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = row.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            text = str(value or "").strip()
            if text:
                counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))


def queue_priority_reason_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reasons = row.get("priority_reasons")
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            key = str(reason or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def queue_season_key(row: dict[str, Any]) -> str:
    media_type = str(row.get("media_type") or "").casefold()
    if media_type != "tv":
        return "not_tv"
    try:
        season = int(row.get("season_number") or 0)
    except (TypeError, ValueError):
        season = 0
    return f"S{season:02d}" if season >= 0 else "unknown"


def queue_season_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = queue_season_key(row)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def queue_total_size_gb(rows: Iterable[dict[str, Any]]) -> float:
    total = 0.0
    for row in rows:
        try:
            total += max(0.0, float(row.get("size_gb") or 0.0))
        except (TypeError, ValueError):
            continue
    return round(total, 3)


def format_queue_size_gb(value: float) -> str:
    return f"{max(0.0, float(value or 0.0)):.2f} GB"


def queue_completed_collision_fields(
    *,
    source_count: int,
    runnable_count: int,
    completed_excluded_count: int,
    snapshot_stale: bool,
    produced_stale: bool,
    excluded_rows: list[dict[str, Any]],
    excluded_row_count: int,
    excluded_row_limit: int,
    excluded_rows_truncated: bool,
    row_level_available: bool,
) -> dict[str, Any]:
    flags: list[str] = []
    if completed_excluded_count > 0:
        flags.append("completed_or_blocked_exclusions")
    if row_level_available:
        flags.append("row_level_exclusions_available")
    if excluded_rows_truncated:
        flags.append("excluded_rows_truncated")
    if snapshot_stale:
        flags.append("stale_snapshot_file")
    if produced_stale:
        flags.append("stale_snapshot_produced_at")
    if not source_count and not runnable_count:
        flags.append("no_source_candidates")

    if completed_excluded_count > 0 and (snapshot_stale or produced_stale):
        status = "Stale exclusions"
        severity = "warning"
        guidance = "Refresh Queue before launch. Aggregate completed/blocked exclusions exist and the snapshot is stale, so newly moved or half-copied files may be hidden."
    elif completed_excluded_count > 0:
        status = "Excluded candidates"
        severity = "info"
        guidance = "Some source candidates are excluded from runnable rows. This can be correct when completed history, source filters, or block policies apply."
    elif snapshot_stale or produced_stale:
        status = "Snapshot stale"
        severity = "warning"
        guidance = "Refresh Queue before launch. A stale snapshot can hide files whose completed status or source state changed."
    elif not source_count and not runnable_count:
        status = "No candidates"
        severity = "info"
        guidance = "No source candidates are reported in the loaded queue snapshot."
    else:
        status = "No exclusions"
        severity = "ok"
        guidance = "Loaded queue snapshot reports no completed/blocked aggregate exclusions."

    lines = [
        f"Source candidates: {source_count}",
        f"Runnable rows: {runnable_count}",
        f"Completed/blocked exclusions: {completed_excluded_count}",
    ]
    if row_level_available:
        shown = len(excluded_rows)
        total = max(excluded_row_count, shown)
        limit_text = f" (limit {excluded_row_limit})" if excluded_row_limit else ""
        trunc_text = "; truncated" if excluded_rows_truncated else ""
        lines.append(f"Row-level excluded-file detail: available, showing {shown} of {total}{limit_text}{trunc_text}.")
        reason_counts = queue_count_by_key(excluded_rows, "reason_code")
        if reason_counts:
            lines.append(f"Excluded reasons: {queue_counts_text(reason_counts)}")
        for row in excluded_rows[:8]:
            label = str(row.get("display_name") or row.get("relative_path") or row.get("source_path") or "").strip()
            reason = str(row.get("reason_code") or "excluded").strip()
            media = str(row.get("media_type") or "Unknown").strip()
            lines.append(f"- {reason} [{media}]: {label}")
    else:
        lines.append("Row-level excluded-file detail: unavailable in the current queue snapshot contract.")
    if completed_excluded_count > 0:
        lines.append("Interpretation: the aggregate exclusion count can include already-completed files, blocked rows, and source rows filtered before runnable planning.")
    if snapshot_stale or produced_stale:
        lines.append("Risk: stale queue state can make completed-history collisions look resolved when source folders changed after the snapshot was written.")
    lines.append("Mutation guardrail: this is read-only guidance; queue mutation, completed reconciliation, and rerun remain backend-owned.")
    return {
        "completed_collision_status": status,
        "completed_collision_severity": severity,
        "completed_collision_guidance": guidance,
        "completed_collision_lines": lines,
        "completed_collision_flags": flags,
        "completed_collision_row_level_available": row_level_available,
    }


def queue_source_scan_progress_payload(
    *,
    source: str = "",
    row_count: int = 0,
    metadata: Mapping[str, Any] | None = None,
    warnings: Iterable[str] | None = None,
    status: str = "",
    detail: str = "",
) -> dict[str, Any]:
    fields = dict(metadata or {})
    warnings_list = [str(warning).strip() for warning in (warnings or []) if str(warning).strip()]
    snapshot_freshness = str(fields.get("snapshot_file_freshness_status") or "").casefold()
    produced_freshness = str(fields.get("produced_freshness_status") or "").casefold()
    stale = snapshot_freshness == "stale" or produced_freshness == "stale"
    source_count = max(0, queue_snapshot_int(fields, "source_count_total"))
    movie_count = max(0, queue_snapshot_int(fields, "movie_count_total"))
    tv_count = max(0, queue_snapshot_int(fields, "tv_count_total"))
    runnable_count = max(0, queue_snapshot_int(fields, "runnable_count") or row_count)
    effective_status = status.strip().casefold() if status else ""
    if not effective_status:
        if stale or warnings_list:
            effective_status = "warning"
        elif source or row_count or source_count:
            effective_status = "complete"
        else:
            effective_status = "idle"
    source_label = source or "queue_snapshot.json"
    source_candidates = (
        f"Source candidates: {source_count} ({movie_count} movie / {tv_count} TV)"
        if source_count
        else "Source candidate count is not reported by the current scanner contract"
    )
    summary_lines = [
        "Queue source scan progress:",
        source_candidates,
        f"Runnable rows loaded: {runnable_count}",
        f"Rows displayed: {max(0, row_count)}",
        fields.get("snapshot_file_age_text") and f"Snapshot file age: {fields.get('snapshot_file_age_text')} ({fields.get('snapshot_file_freshness_status') or 'unknown'})",
        fields.get("produced_age_text") and f"Produced age: {fields.get('produced_age_text')} ({fields.get('produced_freshness_status') or 'unknown'})",
        "Progress mode: indeterminate until backend scanner telemetry emits a reliable candidate numerator and denominator.",
        "Guardrail: Queue progress is read-only evidence; the WebView cannot refresh, reorder, drop, or mutate queue state.",
        *(f"Warning: {warning}" for warning in warnings_list[:3]),
    ]
    if detail:
        bar_detail = detail
    else:
        detail_parts = [
            source_candidates,
            f"runnable {runnable_count}",
            warnings_list[0] if warnings_list else "",
        ]
        bar_detail = " | ".join(part for part in detail_parts if part)
    bar = progress_bar(
        bar_id="queue_source_scan",
        label="Queue source scan",
        mode="indeterminate",
        status=effective_status,
        detail=bar_detail,
        source=source_label,
        updated_at=str(fields.get("produced_at") or fields.get("snapshot_file_mtime_utc") or ""),
        stale=stale,
    )
    return {
        "schema_version": QUEUE_SOURCE_SCAN_PROGRESS_SCHEMA_VERSION,
        "status": effective_status,
        "source": source,
        "updated_at": bar["updated_at"],
        "stale": stale,
        "summary_lines": [str(line) for line in summary_lines if line],
        "progress_bars": [bar],
    }


def queue_preview_metadata(
    snapshot: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    snapshot_path: Path | None = None,
    runtime_event_count: int = 0,
    runtime_outcome_source: str = "",
    runtime_outcome_warning: str = "",
) -> dict[str, Any]:
    raw_excluded_rows = snapshot.get("excluded_rows")
    row_level_available = isinstance(raw_excluded_rows, list)
    excluded_rows = queue_preview_excluded_rows(raw_excluded_rows or [])
    excluded_row_count = queue_snapshot_int(snapshot, "excluded_count")
    if not excluded_row_count and excluded_rows:
        excluded_row_count = len(excluded_rows)
    excluded_row_limit = queue_snapshot_int(snapshot, "excluded_row_limit")
    excluded_rows_truncated = bool(snapshot.get("excluded_rows_truncated", False))
    movie_count = queue_snapshot_int(snapshot, "movie_count_total")
    tv_count = queue_snapshot_int(snapshot, "tv_count_total")
    source_count = movie_count + tv_count
    runnable_count = queue_snapshot_int(snapshot, "runnable_count")
    if not runnable_count and rows:
        runnable_count = len(rows)
    completed_excluded = max(0, source_count - runnable_count)
    invalid_row_count = sum(1 for row in rows if str(row.get("status") or "").casefold() == "invalid")
    blocked_rows = [row for row in rows if str(row.get("blocked_reason") or "").strip()]
    runtime_deferred_rows = [row for row in rows if bool(row.get("runtime_checks_deferred"))]
    runtime_outcome_rows = [row for row in rows if str(row.get("runtime_outcome_status") or "").strip()]
    total_size_gb = queue_total_size_gb(rows)
    produced_fields = datetime_freshness_fields(
        snapshot.get("produced_at"),
        prefix="produced",
        stale_after_seconds=QUEUE_SNAPSHOT_STALE_AFTER_SECONDS,
    )
    snapshot_file_fields = file_freshness_fields(
        snapshot_path,
        prefix="snapshot_file",
        stale_after_seconds=QUEUE_SNAPSHOT_STALE_AFTER_SECONDS,
    )
    metadata = {
        "produced_at": str(snapshot.get("produced_at", "") or ""),
        "config_path": str(snapshot.get("config_path", "") or ""),
        "local_base": str(snapshot.get("local_base", "") or ""),
        "source_movies": str(snapshot.get("source_movies", "") or ""),
        "source_tv": str(snapshot.get("source_tv", "") or ""),
        "outsource": str(snapshot.get("outsource", "") or ""),
        "movie_count_total": movie_count,
        "tv_count_total": tv_count,
        "source_count_total": source_count,
        "priority_count": queue_snapshot_int(snapshot, "priority_count"),
        "runnable_count": runnable_count,
        "completed_excluded_count": completed_excluded,
        "excluded_row_count": excluded_row_count,
        "excluded_row_limit": excluded_row_limit,
        "excluded_rows_truncated": excluded_rows_truncated,
        "excluded_reason_counts": queue_count_by_key(excluded_rows, "reason_code"),
        "excluded_media_type_counts": queue_count_by_key(excluded_rows, "media_type"),
        "excluded_rows": excluded_rows,
        "blocked_row_count": len(blocked_rows),
        "blocked_reason_code_counts": queue_count_by_key(blocked_rows, "blocked_reason_code"),
        "blocked_reason_counts": queue_count_by_key(blocked_rows, "blocked_reason"),
        "runtime_check_deferred_count": len(runtime_deferred_rows),
        "runtime_check_code_counts": queue_count_list_values(runtime_deferred_rows, "runtime_check_codes"),
        "runtime_outcome_source": runtime_outcome_source,
        "runtime_outcome_event_count": max(0, int(runtime_event_count or 0)),
        "runtime_outcome_match_count": len(runtime_outcome_rows),
        "runtime_outcome_warning": runtime_outcome_warning,
        "runtime_outcome_status_counts": queue_count_by_key(runtime_outcome_rows, "runtime_outcome_status"),
        "runtime_outcome_event_type_counts": queue_count_by_key(runtime_outcome_rows, "runtime_outcome_event_type"),
        "runtime_outcome_error_code_counts": queue_count_by_key(runtime_outcome_rows, "runtime_outcome_error_code"),
        "runtime_outcome_freshness_counts": queue_count_by_key(runtime_outcome_rows, "runtime_outcome_freshness_status"),
        "available_open_target_counts": queue_count_list_values(rows, "available_open_targets"),
        "route_counts": queue_count_by_key(rows, "route_name"),
        "route_reason_counts": queue_count_by_key(rows, "route_reason_code"),
        "operator_status_counts": queue_count_by_key(rows, "operator_status"),
        "operator_severity_counts": queue_count_by_key(rows, "operator_severity"),
        "operator_trust_state_counts": queue_count_by_key(rows, "operator_trust_state"),
        "phase_counts": queue_count_by_key(rows, "phase"),
        "media_type_counts": queue_count_by_key(rows, "media_type"),
        "source_root_counts": queue_count_by_key(rows, "source_root"),
        "season_counts": queue_season_counts(rows),
        "priority_reason_counts": queue_priority_reason_counts(rows),
        "priority_visible_count": sum(1 for row in rows if bool(row.get("is_priority"))),
        "invalid_row_count": invalid_row_count,
        "total_visible_size_gb": total_size_gb,
        "total_visible_size_text": format_queue_size_gb(total_size_gb),
    }
    metadata.update(produced_fields)
    metadata.update(snapshot_file_fields)
    metadata.update(
        queue_completed_collision_fields(
            source_count=source_count,
            runnable_count=runnable_count,
            completed_excluded_count=completed_excluded,
            snapshot_stale=str(snapshot_file_fields.get("snapshot_file_freshness_status") or "").casefold() == "stale",
            produced_stale=str(produced_fields.get("produced_freshness_status") or "").casefold() == "stale",
            excluded_rows=excluded_rows,
            excluded_row_count=excluded_row_count,
            excluded_row_limit=excluded_row_limit,
            excluded_rows_truncated=excluded_rows_truncated,
            row_level_available=row_level_available,
        )
    )
    return metadata


def normalize_queue_open_target(value: Any) -> str:
    return str(value or "").strip().casefold()


def normalize_queue_open_scope(value: Any) -> str:
    scope = str(value or "").strip().casefold()
    return scope or "runnable"


def allowed_queue_open_targets_text() -> str:
    return ", ".join(sorted(QUEUE_OPEN_TARGETS))


def allowed_queue_open_scopes_text() -> str:
    return ", ".join(sorted(QUEUE_OPEN_SCOPES))


def queue_open_target_label(target: str) -> str:
    return QUEUE_OPEN_TARGETS[target]


def queue_open_scope_label(scope: str) -> str:
    return QUEUE_OPEN_SCOPES[scope]


def queue_open_path(row: dict[str, Any], target: str) -> Path | None:
    source_text = str(row.get("source_path") or "").strip()
    source_root = str(row.get("source_root") or "").strip()
    if target == "source_file" and source_text:
        return Path(source_text)
    if target == "source_folder" and source_text:
        return Path(source_text).parent
    if target == "source_root" and source_root:
        return Path(source_root)
    return None


def queue_open_requires_row_result() -> CommandResult:
    return CommandResult(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="Queue open requires a selected row.",
        severity="warning",
        warnings=["No queue row key was provided."],
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_disallowed_target_result() -> CommandResult:
    return CommandResult(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="Queue open target is not allowed.",
        severity="error",
        errors=[f"Allowed targets: {allowed_queue_open_targets_text()}"],
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_disallowed_scope_result(scope: str) -> CommandResult:
    return CommandResult(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="Queue open row scope is not allowed.",
        severity="error",
        errors=[f"Allowed row scopes: {allowed_queue_open_scopes_text()}"],
        data={"row_scope": scope},
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_row_missing_result(row_key: str = "") -> CommandResult:
    return CommandResult(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="The selected queue row is no longer available.",
        severity="warning",
        warnings=["Refresh Queue and select the row again."],
        data={"row_key": row_key},
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_path_missing_result(target: str, row_key: str, row_scope: str = "runnable") -> CommandResult:
    return CommandResult(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message=f"No path is available for {queue_open_target_label(target)}.",
        severity="warning",
        warnings=[f"No path is available for target '{target}'."],
        data={"target": target, "row_key": row_key, "row_scope": row_scope},
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_path_service_unavailable_result(target: str, row_key: str, path: Path, row_scope: str = "runnable") -> CommandResult:
    return CommandResult(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message="Path open service is not available.",
        severity="error",
        errors=["Path open service is not available."],
        data=queue_open_result_data(target, row_key, path, row_scope=row_scope),
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_exception_result(target: str, row_key: str, path: Path, exc: Exception, row_scope: str = "runnable") -> CommandResult:
    return CommandResult(
        command=QUEUE_OPEN_COMMAND,
        ok=False,
        message=f"Could not open {queue_open_target_label(target)}: {exc}",
        severity="error",
        errors=[str(exc)],
        data=queue_open_result_data(target, row_key, path, row_scope=row_scope),
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_success_result(target: str, row_key: str, path: Path, row_scope: str = "runnable") -> CommandResult:
    return CommandResult(
        command=QUEUE_OPEN_COMMAND,
        ok=True,
        message=f"Opened {queue_open_target_label(target)} from {queue_open_scope_label(row_scope)}.",
        severity="info",
        data=queue_open_result_data(target, row_key, path, row_scope=row_scope),
        refresh_hint=QUEUE_REFRESH_HINT,
    )


def queue_open_result_data(target: str, row_key: str, path: Path, row_scope: str = "runnable") -> dict[str, str]:
    return {"target": target, "row_key": row_key, "row_scope": row_scope, "path": str(path)}

__all__ = [
    "NO_QUEUE_SNAPSHOT_WARNING",
    "QUEUE_PREVIEW_SERVICE_WARNING",
    "INVALID_QUEUE_SNAPSHOT_WARNING",
    "EMPTY_QUEUE_SNAPSHOT_WARNING",
    "QUEUE_SNAPSHOT_STALE_AFTER_SECONDS",
    "QUEUE_RUNTIME_OUTCOME_EVENT_LIMIT",
    "QUEUE_SOURCE_SCAN_PROGRESS_SCHEMA_VERSION",
    "QUEUE_OPEN_COMMAND",
    "QUEUE_REFRESH_HINT",
    "QUEUE_OPEN_TARGETS",
    "QUEUE_OPEN_SCOPES",
    "queue_row_key",
    "queue_record_to_row",
    "queue_row_available_open_targets",
    "queue_row_operator_guidance",
    "queue_row_trust_fields",
    "queue_row_route_decision_summary",
    "queue_row_route_evidence_lines",
    "queue_apply_runtime_outcomes",
    "queue_preview_rows",
    "queue_preview_warnings",
    "queue_snapshot_int",
    "queue_safe_int",
    "queue_safe_float",
    "queue_media_type_label",
    "queue_excluded_row_key",
    "queue_preview_excluded_rows",
    "queue_count_by_key",
    "queue_counts_text",
    "queue_count_list_values",
    "queue_priority_reason_counts",
    "queue_season_key",
    "queue_season_counts",
    "queue_total_size_gb",
    "format_queue_size_gb",
    "queue_completed_collision_fields",
    "queue_source_scan_progress_payload",
    "queue_preview_metadata",
    "normalize_queue_open_target",
    "normalize_queue_open_scope",
    "allowed_queue_open_targets_text",
    "allowed_queue_open_scopes_text",
    "queue_open_target_label",
    "queue_open_scope_label",
    "queue_open_path",
    "queue_open_requires_row_result",
    "queue_open_disallowed_target_result",
    "queue_open_disallowed_scope_result",
    "queue_open_row_missing_result",
    "queue_open_path_missing_result",
    "queue_open_path_service_unavailable_result",
    "queue_open_exception_result",
    "queue_open_success_result",
    "queue_open_result_data",
]
