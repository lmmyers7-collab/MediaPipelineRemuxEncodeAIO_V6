"""Queue preview metadata, excluded-row shaping, and progress policy."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Iterable, Mapping

from mediapipeline.core.observability.artifact_freshness import datetime_freshness_fields, file_freshness_fields
from mediapipeline.core.observability.status_policy import progress_bar
from mediapipeline.core.queue.policy_parts.metrics import (
    format_queue_size_gb,
    queue_count_by_key,
    queue_count_list_values,
    queue_counts_text,
    queue_media_type_label,
    queue_priority_reason_counts,
    queue_safe_float,
    queue_safe_int,
    queue_season_counts,
    queue_snapshot_int,
    queue_total_size_gb,
)
from mediapipeline.core.queue.policy_parts.rows import queue_row_available_open_targets
from mediapipeline.core.queue.policy_parts.rules import QUEUE_SNAPSHOT_STALE_AFTER_SECONDS, QUEUE_SOURCE_SCAN_PROGRESS_SCHEMA_VERSION


def _snapshot_int_with_fallback(snapshot: Mapping[str, Any], key: str, fallback: int) -> int:
    if key in snapshot:
        return queue_snapshot_int(dict(snapshot), key)
    return max(0, int(fallback or 0))


def queue_row_has_visible_priority(row: dict[str, Any]) -> bool:
    manifest_level = str(row.get("manifest_priority_level") or "normal").strip().casefold()
    return bool(row.get("is_priority")) or manifest_level in {"high", "low", "hold"}


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

    if completed_excluded_count > 0:
        status = "Excluded candidates"
        severity = "info"
        guidance = (
            "Some source candidates are excluded from runnable rows. Snapshot age is preview context only; "
            "Run Once rebuilds and fingerprint-verifies the queue before media dispatch."
            if snapshot_stale or produced_stale
            else "Some source candidates are excluded from runnable rows. This can be correct when completed history, source filters, or block policies apply."
        )
    elif snapshot_stale or produced_stale:
        status = "Snapshot age advisory"
        severity = "info"
        guidance = "Snapshot age is informational. Run Once rebuilds and fingerprint-verifies the queue before media dispatch; refresh only to update the displayed preview."
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
        lines.append("Age advisory: this preview may predate source or completed-history changes; runtime rebuilds and fingerprint-verifies the queue before media dispatch.")
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
    runnable_count = _snapshot_int_with_fallback(fields, "runnable_count", row_count)
    effective_status = status.strip().casefold() if status else ""
    if not effective_status:
        if warnings_list:
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
    runnable_count = _snapshot_int_with_fallback(snapshot, "runnable_count", len(rows))
    total_row_count = _snapshot_int_with_fallback(snapshot, "total_row_count", len(rows))
    shown_row_count = _snapshot_int_with_fallback(snapshot, "shown_row_count", len(rows))
    row_limit = queue_snapshot_int(snapshot, "row_limit")
    rows_truncated = bool(snapshot.get("rows_truncated", False))
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
        "total_row_count": total_row_count,
        "shown_row_count": shown_row_count,
        "row_limit": row_limit,
        "rows_truncated": rows_truncated,
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
        "operator_status_state_counts": queue_count_by_key(rows, "operator_status_state"),
        "operator_severity_counts": queue_count_by_key(rows, "operator_severity"),
        "operator_trust_state_counts": queue_count_by_key(rows, "operator_trust_state"),
        "phase_counts": queue_count_by_key(rows, "phase"),
        "media_type_counts": queue_count_by_key(rows, "media_type"),
        "source_root_counts": queue_count_by_key(rows, "source_root"),
        "season_counts": queue_season_counts(rows),
        "priority_reason_counts": queue_priority_reason_counts(rows),
        "priority_visible_count": sum(1 for row in rows if queue_row_has_visible_priority(row)),
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


__all__ = [
    "queue_excluded_row_key",
    "queue_preview_excluded_rows",
    "queue_completed_collision_fields",
    "queue_source_scan_progress_payload",
    "queue_preview_metadata",
]
