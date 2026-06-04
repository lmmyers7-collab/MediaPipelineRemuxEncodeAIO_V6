"""Queue row shaping, route evidence, and operator-state policy."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from app.observability.runtime_outcomes import runtime_outcome_index, source_identity_key
from app.queue.file_overrides import FILE_OVERRIDE_BATCH_METADATA_KEY, resolve_file_override_match
from app.queue.policy_parts.rules import EMPTY_QUEUE_SNAPSHOT_WARNING
from mediapipeline_desktop_app.models import QueueRecord

LIBRARY_EFFECTIVE_SETTINGS_SCOPE = "library_only"
RUNTIME_EVIDENCE_NOTE = "resolved during job processing"
OVERRIDE_LAYERS_PENDING = ["show", "folder", "file"]


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
        "manifest_priority_level": record.manifest_priority_level,
    }
    row.update(queue_preview_runtime_evidence_fields())
    row.update(queue_preview_track_metadata_summary({}))
    row["row_key"] = queue_row_key(row)
    row["available_open_targets"] = queue_row_available_open_targets(row)
    row.update(queue_row_operator_guidance(row))
    return row


def _json_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _json_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def _text_value(value: Any) -> str:
    return str(value or "").strip()


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _queue_normalized_path_key(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip().casefold()


def _queue_file_override_artifact_row(row: Mapping[str, Any]) -> bool:
    values = (
        row.get("source_path"),
        row.get("relative_path"),
        row.get("display_name"),
        row.get("name"),
    )
    for value in values:
        key = _queue_normalized_path_key(value)
        if key.endswith(".override.json") or key.endswith("/override.json") or key == "override.json":
            return True
    return False


def _mapping_value(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            dumped = dump(mode="json")
        except TypeError:
            dumped = dump()
        return dumped if isinstance(dumped, Mapping) else {}
    if hasattr(value, "__dict__"):
        data = vars(value)
        return data if isinstance(data, Mapping) else {}
    return {}


def _list_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _int_metadata_value(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _track_language_value(value: Any) -> str:
    language = str(value or "").strip().casefold()
    return language


def _track_language_list(value: Any) -> list[str]:
    languages: list[str] = []
    seen: set[str] = set()
    for item in _list_value(value):
        language = _track_language_value(item)
        if language and language not in seen:
            languages.append(language)
            seen.add(language)
    return languages


def _stream_language(row: Mapping[str, Any]) -> str:
    tags = _mapping_value(row.get("tags"))
    return _track_language_value(row.get("language") or row.get("lang") or tags.get("language"))


def _stream_forced(row: Mapping[str, Any]) -> bool:
    if "forced" in row:
        return _bool_value(row.get("forced"))
    disposition = _mapping_value(row.get("disposition"))
    return _bool_value(disposition.get("forced"))


def _stream_kind(row: Mapping[str, Any], fallback: str = "") -> str:
    value = str(row.get("kind") or row.get("codec_type") or row.get("stream_type") or row.get("type") or fallback)
    kind = value.strip().casefold()
    if kind in {"subtitles", "subtitle_stream", "s"}:
        return "subtitle"
    if kind in {"audio_stream", "a"}:
        return "audio"
    return kind


def _append_track_rows(target: list[Mapping[str, Any]], value: Any, *, fallback_kind: str = "") -> bool:
    rows = _list_value(value)
    for item in rows:
        row = _mapping_value(item)
        if row and (fallback_kind or _stream_kind(row) in {"audio", "subtitle"}):
            target.append(row if not fallback_kind else {**dict(row), "_queue_track_kind": fallback_kind})
    return isinstance(value, (list, tuple))


def _embedded_track_rows(raw_row: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], bool]:
    rows: list[Mapping[str, Any]] = []
    metadata_present = False
    metadata_present = _append_track_rows(rows, raw_row.get("streams")) or metadata_present
    metadata_present = _append_track_rows(rows, raw_row.get("probe_streams")) or metadata_present

    for key in ("probe", "probe_result", "source_media", "source_media_info", "source_media_profile", "ffprobe"):
        nested = _mapping_value(raw_row.get(key))
        if not nested:
            continue
        metadata_present = _append_track_rows(rows, nested.get("streams")) or metadata_present
        metadata_present = _append_track_rows(rows, nested.get("audio_streams"), fallback_kind="audio") or metadata_present
        metadata_present = _append_track_rows(rows, nested.get("subtitle_streams"), fallback_kind="subtitle") or metadata_present
        metadata_present = _append_track_rows(rows, nested.get("audio_tracks"), fallback_kind="audio") or metadata_present
        metadata_present = _append_track_rows(rows, nested.get("subtitle_tracks"), fallback_kind="subtitle") or metadata_present

    metadata_present = _append_track_rows(rows, raw_row.get("audio_streams"), fallback_kind="audio") or metadata_present
    metadata_present = _append_track_rows(rows, raw_row.get("subtitle_streams"), fallback_kind="subtitle") or metadata_present
    metadata_present = _append_track_rows(rows, raw_row.get("audio_tracks"), fallback_kind="audio") or metadata_present
    metadata_present = _append_track_rows(rows, raw_row.get("subtitle_tracks"), fallback_kind="subtitle") or metadata_present

    audio = [row for row in rows if _stream_kind(row, str(row.get("_queue_track_kind") or "")) == "audio"]
    subtitles = [row for row in rows if _stream_kind(row, str(row.get("_queue_track_kind") or "")) == "subtitle"]
    return audio, subtitles, metadata_present


def _track_metadata_summary_from_fields(raw_row: Mapping[str, Any]) -> dict[str, Any] | None:
    summary_keys = {
        "audio_track_count",
        "subtitle_track_count",
        "audio_languages",
        "subtitle_languages",
        "has_forced_subtitles",
    }
    if "track_metadata_available" in raw_row and not _bool_value(raw_row.get("track_metadata_available")):
        return {"track_metadata_available": False}
    if "probe_available" in raw_row and not _bool_value(raw_row.get("probe_available")):
        return {"track_metadata_available": False}
    if "track_metadata_available" not in raw_row and not any(key in raw_row for key in summary_keys):
        return None
    return {
        "track_metadata_available": True,
        "audio_track_count": _int_metadata_value(raw_row.get("audio_track_count")),
        "subtitle_track_count": _int_metadata_value(raw_row.get("subtitle_track_count")),
        "audio_languages": _track_language_list(raw_row.get("audio_languages")),
        "subtitle_languages": _track_language_list(raw_row.get("subtitle_languages")),
        "has_forced_subtitles": _bool_value(raw_row.get("has_forced_subtitles")),
    }


def queue_preview_track_metadata_summary(raw_row: Mapping[str, Any]) -> dict[str, Any]:
    field_summary = _track_metadata_summary_from_fields(raw_row)
    if field_summary is not None:
        return field_summary

    audio, subtitles, metadata_present = _embedded_track_rows(raw_row)
    if not metadata_present:
        return {"track_metadata_available": False}

    return {
        "track_metadata_available": True,
        "audio_track_count": len(audio),
        "subtitle_track_count": len(subtitles),
        "audio_languages": _track_language_list([_stream_language(row) for row in audio]),
        "subtitle_languages": _track_language_list([_stream_language(row) for row in subtitles]),
        "has_forced_subtitles": any(_stream_forced(row) for row in subtitles),
    }


def _annotate_queue_file_override(
    row: dict[str, Any],
    file_override_manifest: Mapping[str, Any] | None,
) -> None:
    if file_override_manifest is None or _queue_file_override_artifact_row(row):
        return
    source_path = str(row.get("source_path") or "").strip()
    if not source_path:
        row["has_file_override"] = False
        return
    match = resolve_file_override_match(dict(file_override_manifest), source_path)
    entry = match.get("entry")
    row["has_file_override"] = isinstance(entry, dict)
    if not row["has_file_override"]:
        return
    row["file_override_path"] = str(match.get("matched_path") or "")
    row["file_override_scope"] = str(match.get("scope") or "")
    batch = entry.get(FILE_OVERRIDE_BATCH_METADATA_KEY) if isinstance(entry, Mapping) else None
    if isinstance(batch, Mapping):
        row["file_override_origin"] = str(batch.get("origin") or "")
        row["file_override_batch_id"] = str(batch.get("batch_id") or "")
        row["file_override_batch_label"] = str(batch.get("batch_label") or "")
        row["file_override_batch_scope"] = str(batch.get("batch_scope") or "")


def _optional_bool_value(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    return _bool_value(value)


def _nested_path_field_text(raw_row: Mapping[str, Any], field: str, key: str) -> str:
    for state_key in ("library_path_field_state", "path_field_state"):
        state_map = raw_row.get(state_key)
        if not isinstance(state_map, Mapping):
            continue
        field_state = state_map.get(field)
        if isinstance(field_state, Mapping):
            text = _text_value(field_state.get(key))
            if text:
                return text
    return ""


def queue_preview_runtime_evidence_fields() -> dict[str, Any]:
    return {
        "library_effective_settings_scope": LIBRARY_EFFECTIVE_SETTINGS_SCOPE,
        "runtime_effective_settings_available": False,
        "runtime_evidence_note": RUNTIME_EVIDENCE_NOTE,
        "override_layers_pending": list(OVERRIDE_LAYERS_PENDING),
    }


def queue_preview_library_promotion_fields(raw_row: Mapping[str, Any]) -> dict[str, Any]:
    promotion_enabled = _optional_bool_value(
        raw_row.get("library_promotion_enabled", raw_row.get("promotion_enabled"))
    )
    destination = _text_value(
        raw_row.get("library_promotion_destination")
        or raw_row.get("promotion_destination")
        or raw_row.get("final_library_destination_root")
    )
    rule_id = _text_value(raw_row.get("library_promotion_rule_id") or raw_row.get("final_library_rule_id"))
    rule_label = _text_value(raw_row.get("library_promotion_rule_label") or raw_row.get("final_library_rule_label"))
    status = _text_value(raw_row.get("library_promotion_status") or raw_row.get("final_library_promotion_status"))
    output_state = _text_value(
        raw_row.get("library_output_root_state")
        or raw_row.get("library_output_path_state")
        or _nested_path_field_text(raw_row, "output_path", "state")
    )
    output_source_key = _text_value(
        raw_row.get("library_output_root_source_key")
        or raw_row.get("library_output_path_source_key")
        or _nested_path_field_text(raw_row, "output_path", "source_key")
    )
    return {
        "library_promotion_enabled": promotion_enabled,
        "library_promotion_destination": destination,
        "library_promotion_rule_id": rule_id,
        "library_promotion_rule_label": rule_label,
        "library_promotion_status": status,
        "library_output_root_state": output_state,
        "library_output_root_source_key": output_source_key,
    }


def queue_row_available_open_targets(row: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    if str(row.get("source_path") or "").strip():
        targets.extend(["source_file", "source_folder"])
    if str(row.get("source_root") or "").strip():
        targets.append("source_root")
    return targets


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
    runtime_success = row.get("runtime_outcome_success")
    runtime_success_text = str(runtime_success).casefold() if runtime_success is not None else ""
    if status == "invalid" or operator_severity in {"error", "critical"}:
        return "blocked"
    if row.get("blocked_reason") or row.get("blocked_reason_code") or "blocked" in flags:
        return "blocked"
    if runtime_recent:
        if runtime_status == "skipped":
            return "skipped"
        if runtime_success is False or runtime_success_text == "false" or runtime_status in {
            "failed",
            "stopped",
            "transient_failure",
            "permanent_failure",
            "operator_required_failure",
            "failure_recorded",
        }:
            return "failed"
        if runtime_success is True or runtime_success_text == "true":
            return "completed"
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
    threshold_mode = str(row.get("route_threshold_mode") or "").strip()
    if threshold_mode:
        lines.append(f"Route threshold mode: {threshold_mode}")
    size_threshold = _float_value(row.get("route_size_threshold_gb"))
    if size_threshold > 0:
        lines.append(f"Size threshold: {size_threshold:g} GB; over threshold: {'yes' if _bool_value(row.get('size_over_threshold')) else 'no'}")
    estimated_bitrate = _float_value(row.get("estimated_bitrate_mbps"))
    bitrate_threshold = _float_value(row.get("route_bitrate_threshold_mbps"))
    if estimated_bitrate > 0 or bitrate_threshold > 0:
        lines.append(
            "Bitrate estimate: "
            f"{estimated_bitrate:g} Mbps; threshold: {bitrate_threshold:g} Mbps; "
            f"over threshold: {'yes' if _bool_value(row.get('bitrate_over_threshold')) else 'no'}"
        )
    trace = row.get("route_decision_trace")
    if isinstance(trace, list) and trace:
        codes = []
        for item in trace:
            if isinstance(item, Mapping):
                code = str(item.get("code") or "").strip()
            else:
                code = ""
            if code:
                codes.append(code)
        if codes:
            suffix = "..." if len(codes) > 8 else ""
            lines.append(f"Route trace: {', '.join(codes[:8])}{suffix}")
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
    library_id = str(row.get("library_id") or "").strip()
    library_name = str(row.get("library_name") or "").strip()
    library_designation = str(row.get("library_designation") or "").strip()
    library_output_root = str(row.get("library_output_root") or "").strip()
    library_output_root_state = str(row.get("library_output_root_state") or "").strip()
    library_output_root_source_key = str(row.get("library_output_root_source_key") or "").strip()
    library_source_root = str(row.get("library_source_root") or row.get("source_root") or "").strip()
    library_override_keys = _json_list(row.get("library_settings_override_keys"))
    if library_id or library_name or library_output_root:
        label = library_name or library_id or "not reported"
        lines.append(f"Library profile: {label}{f' ({library_id})' if library_id and library_id != label else ''}")
        if library_designation:
            lines.append(f"Library designation: {library_designation}")
        if library_source_root:
            lines.append(f"Library source root: {library_source_root}")
        if library_output_root:
            lines.append(f"Library output root: {library_output_root}")
        if library_output_root_state:
            if library_output_root_state == "inherited" and library_output_root_source_key:
                lines.append(f"Library output root state: inherited from {library_output_root_source_key}")
            else:
                lines.append(f"Library output root state: {library_output_root_state}")
        lines.append(f"Library override keys: {', '.join(library_override_keys) if library_override_keys else 'none'}")
        if str(row.get("library_effective_settings_scope") or "").strip() == LIBRARY_EFFECTIVE_SETTINGS_SCOPE:
            lines.append("Library effective settings: library-only (global settings plus library overrides)")
    promotion_enabled = row.get("library_promotion_enabled")
    promotion_destination = str(row.get("library_promotion_destination") or "").strip()
    promotion_rule_id = str(row.get("library_promotion_rule_id") or "").strip()
    promotion_rule_label = str(row.get("library_promotion_rule_label") or "").strip()
    if promotion_enabled is not None:
        lines.append(f"Library promotion: {'enabled' if bool(promotion_enabled) else 'disabled'}")
    if promotion_destination:
        lines.append(f"Library promotion destination: {promotion_destination}")
    if promotion_rule_id or promotion_rule_label:
        rule_label = promotion_rule_label or promotion_rule_id
        lines.append(f"Library promotion rule: {rule_label}{f' ({promotion_rule_id})' if promotion_rule_id and promotion_rule_id != rule_label else ''}")
    runtime_available = bool(row.get("runtime_effective_settings_available"))
    runtime_note = str(row.get("runtime_evidence_note") or "").strip()
    pending_layers = _json_list(row.get("override_layers_pending"))
    if not runtime_available and (runtime_note or pending_layers):
        pending_text = ", ".join(pending_layers) if pending_layers else "later"
        lines.append(f"Runtime effective settings: {runtime_note or 'deferred'}; pending layers: {pending_text}")
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
    *,
    file_override_manifest: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            continue
        try:
            record = row_factory(raw_row)
        except Exception as exc:
            invalid_row = {"status": "invalid", "error": str(exc), "raw": raw_row}
            invalid_row.update(queue_preview_runtime_evidence_fields())
            invalid_row.update(queue_preview_track_metadata_summary(raw_row))
            invalid_row["available_open_targets"] = queue_row_available_open_targets(invalid_row)
            invalid_row.update(queue_row_operator_guidance(invalid_row))
            rows.append(invalid_row)
            continue
        if isinstance(record, QueueRecord):
            safe_row = queue_record_to_row(record)
            safe_row["route_reason_code"] = str(raw_row.get("route_reason_code") or "").strip()
            safe_row["route_decision_trace"] = raw_row.get("route_decision_trace") if isinstance(raw_row.get("route_decision_trace"), list) else []
            safe_row["estimated_bitrate_mbps"] = _float_value(raw_row.get("estimated_bitrate_mbps"))
            safe_row["route_size_threshold_gb"] = _float_value(raw_row.get("route_size_threshold_gb"))
            safe_row["route_bitrate_threshold_mbps"] = _float_value(raw_row.get("route_bitrate_threshold_mbps"))
            safe_row["route_threshold_mode"] = str(raw_row.get("route_threshold_mode") or "").strip()
            safe_row["size_over_threshold"] = _bool_value(raw_row.get("size_over_threshold"))
            safe_row["bitrate_over_threshold"] = _bool_value(raw_row.get("bitrate_over_threshold"))
            safe_row["blocked_reason_code"] = str(raw_row.get("blocked_reason_code") or "").strip()
            safe_row["blocked_reason"] = str(raw_row.get("blocked_reason") or "").strip()
            safe_row["last_write_utc"] = str(raw_row.get("last_write_utc") or "").strip()
            safe_row["runtime_checks_deferred"] = bool(raw_row.get("runtime_checks_deferred", False))
            safe_row["runtime_check_codes"] = [str(item) for item in raw_row.get("runtime_check_codes") or [] if str(item).strip()] if isinstance(raw_row.get("runtime_check_codes"), list) else []
            safe_row["runtime_check_notes"] = [str(item) for item in raw_row.get("runtime_check_notes") or [] if str(item).strip()] if isinstance(raw_row.get("runtime_check_notes"), list) else []
            safe_row["library_id"] = str(raw_row.get("library_id") or "").strip()
            safe_row["library_name"] = str(raw_row.get("library_name") or "").strip()
            safe_row["library_designation"] = str(raw_row.get("library_designation") or "").strip()
            safe_row["library_source_root"] = str(raw_row.get("library_source_root") or raw_row.get("root_path") or "").strip()
            safe_row["library_output_root"] = str(raw_row.get("library_output_root") or "").strip()
            safe_row["library_settings_override_keys"] = _json_list(raw_row.get("library_settings_override_keys"))
            safe_row["library_settings_overrides"] = _json_mapping(raw_row.get("library_settings_overrides"))
            safe_row["library_effective_settings"] = _json_mapping(raw_row.get("library_effective_settings"))
            safe_row.update(queue_preview_runtime_evidence_fields())
            safe_row.update(queue_preview_library_promotion_fields(raw_row))
            safe_row.update(queue_preview_track_metadata_summary(raw_row))
            _annotate_queue_file_override(safe_row, file_override_manifest)
            safe_row["row_key"] = queue_row_key(safe_row)
            safe_row["available_open_targets"] = queue_row_available_open_targets(safe_row)
            safe_row.update(queue_row_operator_guidance(safe_row))
            rows.append(safe_row)
    return rows


def queue_preview_warnings(rows: list[dict[str, Any]]) -> list[str]:
    return [] if rows else [EMPTY_QUEUE_SNAPSHOT_WARNING]


__all__ = [
    "queue_row_key",
    "queue_record_to_row",
    "queue_row_available_open_targets",
    "queue_row_operator_status_state",
    "queue_row_operator_guidance",
    "queue_row_trust_fields",
    "queue_row_route_decision_summary",
    "queue_row_route_evidence_lines",
    "queue_apply_runtime_outcomes",
    "queue_preview_rows",
    "queue_preview_track_metadata_summary",
    "queue_preview_runtime_evidence_fields",
    "queue_preview_library_promotion_fields",
    "queue_preview_warnings",
]
