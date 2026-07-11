"""Completed-job preview DTO policy."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.completed.manifest import OUTPUT_PROOF_DEFERRED, OUTPUT_PROOF_LIVE
from mediapipeline.core.completed.trust_fields import build_completed_row_trust_fields
from mediapipeline.core.completed.validation_state import validation_state_for_completed_row, validation_state_payload
from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.core.observability.artifact_freshness import file_freshness_fields
from mediapipeline.core.observability.runtime_outcomes import (
    RUNTIME_OUTCOME_EVENT_LIMIT as COMPLETED_RUNTIME_OUTCOME_EVENT_LIMIT,
    runtime_outcome_index,
    source_identity_key,
)
from mediapipeline.core.subtitles.qa import build_completed_subtitle_qa
from mediapipeline.core.completed.contracts import CompletedJobRecord

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_inventory import CompletedPreviewDto


COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE = "Completed history service is not available."
COMPLETED_HISTORY_EMPTY_MESSAGE = "No completed jobs are available from the local manifest."
COMPLETED_MANIFEST_STALE_AFTER_SECONDS = 604800
COMPLETED_INVENTORY_PROGRESS_SCHEMA_VERSION = "desktop_completed_inventory_progress.v1"
COMPLETED_HISTORY_ALL_LIMIT = "all"
COMPLETED_NEUTRAL_SIZE_DELTA_PERCENT = 1.0
COMPLETED_PENDING_PUBLISH_ROW_STATES = {
    "parked",
    "parked_recovered",
    "pending_move",
}
COMPLETED_RUNTIME_FAILURE_STATUSES = {
    "failed",
    "skipped",
    "stopped",
    "transient_failure",
    "permanent_failure",
    "operator_required_failure",
    "failure_recorded",
}
COMPLETED_BENIGN_RUNTIME_ERROR_CODES = {"already_processed"}



from mediapipeline.core.completed.policy_projection import *  # noqa: F403

from mediapipeline.core.completed.policy_evidence import *  # noqa: F403

from mediapipeline.core.completed.policy_quality import *  # noqa: F403

from mediapipeline.core.completed.policy_guidance import *  # noqa: F403


def completed_pending_publish_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    payload = _pending_publish_completed_payload(row)
    if payload is None:
        return None
    manifest_path = _mapping_text(row, "manifest_path")
    pending_state = _mapping_text(row, "state").casefold()
    record = CompletedJobRecord(sidecar_path=Path(manifest_path), payload=payload)
    completed = completed_record_to_row(record)
    issue_summary = _mapping_text(row, "issue_summary", "error")
    ready_to_drain = bool(row.get("ready_to_drain"))
    missing_sidecar_count = row.get("missing_sidecar_count")
    review_flags = [
        "pending_publish_parked",
        f"pending_publish_state:{pending_state}",
    ]
    if issue_summary:
        review_flags.append("pending_publish_issue")
    try:
        if int(missing_sidecar_count or 0) > 0:
            review_flags.append("pending_publish_missing_sidecar")
    except (TypeError, ValueError):
        pass
    completed.update(
        {
            "completed_source": "pending_publish",
            "pending_publish": True,
            "pending_publish_manifest_path": manifest_path,
            "pending_publish_local_file": _mapping_text(row, "local_file"),
            "pending_publish_server_out": _mapping_text(row, "server_out"),
            "pending_publish_state": pending_state,
            "pending_publish_row_key": _mapping_text(row, "row_key"),
            "pending_publish_ready_to_drain": ready_to_drain,
            "pending_publish_issue_summary": issue_summary,
            "pending_publish_diagnostic_status": _mapping_text(row, "diagnostic_status"),
            "pending_publish_diagnostic_status_state": _mapping_text(row, "diagnostic_status_state"),
            "pending_publish_diagnostic_severity": _mapping_text(row, "diagnostic_severity"),
            "pending_publish_recovery_class": _mapping_text(row, "recovery_class"),
            "pending_publish_drain_recommendation": _mapping_text(row, "drain_recommendation"),
            "pending_publish_sidecar_count": row.get("sidecar_count"),
            "pending_publish_missing_sidecar_count": missing_sidecar_count,
            "pending_publish_sidecar_paths": (
                list(row.get("sidecar_paths") or [])
                if isinstance(row.get("sidecar_paths"), list)
                else []
            ),
            "output_exists": None,
            "output_proof": OUTPUT_PROOF_DEFERRED,
            "output_health": "",
            "sidecar_exists": None,
            "sidecar_matches_output": None,
            "consistency_status": "Parked",
            "consistency_severity": "warning",
            "consistency_issues": review_flags[:],
            "consistency_guidance": (
                "Output is parked in Pending Publish and has not been drained to "
                "the final destination."
            ),
            "operator_status": "Parked",
            "operator_status_state": "parked",
            "operator_severity": "warning",
            "operator_guidance": (
                "Use Pending Publish drain/review controls before treating this "
                "output as published in the final library."
            ),
            "review_flags": review_flags,
            "available_open_targets": [],
        }
    )
    validation_state = validation_state_for_completed_row(completed)
    completed.update(
        {
            "validation_status_state": validation_state["validation_status_state"],
            "validation_failure_reason": validation_state["failure_reason"],
            "validation_probe_ok": validation_state["probe_ok"],
            "validation_hash_ok": validation_state["hash_ok"],
            "validation_playback_required": validation_state["playback_required"],
            "validation_unavailable_reasons": validation_state["unavailable_reasons"],
            "validation_safe_next_action": validation_state["safe_next_action"],
        }
    )
    completed.update(
        {
            "operator_trust_state": "parked-pending-publish",
            "primary_concern": "output is parked in Pending Publish and has not been drained",
            "safe_next_action": "Use Pending Publish drain/review controls; Completed is showing this as read-only parked evidence.",
            "unsafe_if_ignored": "Treating parked output as published can hide outputs that still require manifest-backed drain.",
            "recommended_diagnostics_targets": [
                "pending_publish",
                "completed_manifest",
                "run_logs",
                "last_stderr_log",
            ],
            "proof_summary": [
                "status=Parked",
                "publish=parked",
                f"pending_state={pending_state or 'unknown'}",
                f"output={completed.get('output_path') or 'not reported'}",
            ],
        }
    )
    evidence_lines = completed_row_route_evidence_lines(completed)
    if manifest_path:
        evidence_lines.append(f"Pending publish manifest: {manifest_path}")
    if issue_summary:
        evidence_lines.append(f"Pending publish issue: {issue_summary}")
    completed["route_evidence_lines"] = evidence_lines
    return completed

def completed_pending_publish_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    completed_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        completed = completed_pending_publish_row(row)
        if completed is None:
            continue
        identity = "|".join(
            [
                str(completed.get("pending_publish_manifest_path") or ""),
                str(completed.get("pending_publish_local_file") or ""),
                str(completed.get("output_path") or ""),
            ]
        ).casefold()
        if identity in seen:
            continue
        seen.add(identity)
        completed_rows.append(completed)
    return completed_rows

def completed_record_to_row(record: CompletedJobRecord) -> dict[str, Any]:
    deferred = _output_proof_deferred(record)
    completed_at = record.completed_at
    # Deferred rows must not touch the filesystem: take output size from the
    # manifest payload only (skip the stat() fallback in output_size_bytes).
    output_size = _payload_output_size(record) if deferred else record.output_size_bytes
    source_size = record.source_size_bytes
    size_delta_percent = completed_size_delta_percent(source_size, output_size)
    size_policy_fields = completed_size_policy_fields(record.payload, size_delta_percent=size_delta_percent)
    quality_fields = completed_quality_fields(record.payload)
    bitrate_fields = completed_bitrate_fields(record.payload, source_size=source_size, output_size=output_size)
    route_reason = str(record.payload.get("route_reason", "") or "").strip()
    route_reason_code = str(record.payload.get("route_reason_code", "") or "").strip()
    audio_decisions = record.audio_decisions
    subtitle_decisions = record.subtitle_decisions
    subtitle_conversion_results = record.subtitle_conversion_results
    media_track_verification = record.payload.get("media_track_verification")
    if not isinstance(media_track_verification, Mapping):
        media_track_verification = {}
    media_track_mismatches = media_track_verification.get("mismatches")
    if not isinstance(media_track_mismatches, list):
        media_track_mismatches = []
    media_track_status = "unknown"
    if media_track_verification:
        media_track_status = "pass" if bool(media_track_verification.get("allowed")) else "blocked"
    row = {
        "row_key": completed_record_key(record),
        "completed_at": _completed_at_text(completed_at),
        "completed_at_sort_key": _completed_at_sort_key(completed_at),
        "route": record.route,
        "route_label": record.route_label,
        **completed_route_display_fields(record.payload),
        "route_reason": route_reason,
        "route_reason_code": route_reason_code,
        "elapsed": record.elapsed_text,
        "publish": record.publish_label,
        "publish_state": record.publish_state,
        "publish_mode": record.publish_mode,
        "media_type": record.media_type,
        "library_id": str(record.payload.get("library_id", "") or "").strip(),
        "library_name": str(record.payload.get("library_name", "") or "").strip(),
        "library_designation": str(record.payload.get("library_designation", "") or "").strip(),
        "library_source_root": str(record.payload.get("library_source_root", "") or "").strip(),
        "library_output_root": str(record.payload.get("library_output_root", "") or "").strip(),
        "lookup_title": record.lookup_title,
        "relative_path": record.relative_path,
        "output_file": record.output_file,
        "output_path": str(record.output_path),
        "output_exists": (None if deferred else bool(record.output_exists)),
        "output_proof": (OUTPUT_PROOF_DEFERRED if deferred else OUTPUT_PROOF_LIVE),
        "output_health": ("" if deferred else record.output_health),
        "source_path": record.source_path_text,
        "manifest_output_path": str(record.payload.get("output_path", "") or "").strip(),
        "manifest_output_file": str(record.payload.get("output_file", "") or "").strip(),
        "sidecar_path": str(record.sidecar_path),
        "source_size_bytes": record.source_size_bytes,
        "output_size_bytes": output_size,
        "output_size_text": format_bytes_compact(output_size or 0),
        "size_reduction_text": completed_size_reduction_text(source_size, output_size),
        "size_delta_percent": size_delta_percent,
        "size_delta_label": completed_size_delta_label(size_delta_percent),
        "size_growth_over_5": bool(size_delta_percent is not None and size_delta_percent > 5.0),
        **size_policy_fields,
        **quality_fields,
        **bitrate_fields,
        "encoder": record.encode_selected_encoder,
        "encoder_kind": record.encode_selected_encoder_kind,
        "gpu_device": record.encode_selected_gpu_device,
        "audio_decision_count": len(audio_decisions),
        "audio_decision_details": completed_decision_detail_rows(audio_decisions, kind="audio"),
        "audio_decision_preview": completed_audio_decision_preview(audio_decisions),
        "subtitle_decision_count": len(subtitle_decisions),
        "subtitle_decision_details": completed_decision_detail_rows(subtitle_decisions, kind="subtitle"),
        "subtitle_decision_preview": completed_subtitle_decision_preview(subtitle_decisions),
        "subtitle_conversion_result_count": len(subtitle_conversion_results),
        "subtitle_conversion_results": subtitle_conversion_results,
        "media_track_verification": dict(media_track_verification),
        "media_track_verification_status": media_track_status,
        "media_track_verification_reason": str(media_track_verification.get("reason", "") or "").strip(),
        "media_track_verification_error_code": str(media_track_verification.get("error_code", "") or "").strip(),
        "media_track_verification_mismatches": [item for item in media_track_mismatches if isinstance(item, Mapping)],
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
        "last_promotion_run_id": "",
        "last_promotion_completed_at": "",
        "promotion_error": "",
        "promotion_warnings": [],
    }
    row.update(completed_row_consistency(record, row))
    row["available_open_targets"] = completed_row_available_open_targets(row)
    row.update(completed_row_operator_guidance(row))
    validation_state = validation_state_for_completed_row(row)
    row.update(
        {
            "validation_status_state": validation_state["validation_status_state"],
            "validation_failure_reason": validation_state["failure_reason"],
            "validation_probe_ok": validation_state["probe_ok"],
            "validation_hash_ok": validation_state["hash_ok"],
            "validation_playback_required": validation_state["playback_required"],
            "validation_unavailable_reasons": validation_state["unavailable_reasons"],
            "validation_safe_next_action": validation_state["safe_next_action"],
        }
    )
    row.update(completed_row_trust_fields(row))
    row["subtitle_qa"] = build_completed_subtitle_qa(
        row,
        subtitle_decisions=subtitle_decisions,
        record_payload=record.payload,
    )
    return row

def completed_apply_runtime_outcomes(rows: list[dict[str, Any]], events: Iterable[Any]) -> list[dict[str, Any]]:
    source_index, output_index = completed_runtime_outcome_indices(events)
    if not source_index and not output_index:
        return rows
    for row in rows:
        outcome = None
        match = ""
        source_key = source_identity_key(row.get("source_path"))
        if source_key:
            outcome = source_index.get(source_key)
            if outcome is not None:
                match = "exact_source_path"
        if outcome is None:
            output_key = source_identity_key(row.get("output_path"))
            if output_key:
                outcome = output_index.get(output_key)
                if outcome is not None:
                    match = "exact_output_path"
        if outcome is None:
            continue
        patched = dict(outcome)
        if match:
            patched["runtime_outcome_match"] = match
        row.update(patched)
        row.update(completed_row_operator_guidance(row))
        row.update(completed_row_trust_fields(row))
    return rows

def completed_preview_rows(records: Iterable[object]) -> list[dict[str, Any]]:
    return [completed_record_to_row(record) for record in records if isinstance(record, CompletedJobRecord)]

def completed_preview_fields(
    rows: list[dict[str, Any]],
    *,
    source: str,
    manifest_path: Path | None = None,
    runtime_event_count: int = 0,
    runtime_outcome_source: str = "",
    runtime_outcome_warning: str = "",
    warnings: Iterable[str] = (),
    parse_health: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    output_sizes = [int(row.get("output_size_bytes") or 0) for row in rows]
    total_output_bytes = sum(output_sizes)
    size_unknown_count = sum(1 for row in rows if row.get("size_delta_percent") is None)
    audio_decision_total = sum(int(row.get("audio_decision_count") or 0) for row in rows)
    subtitle_decision_total = sum(int(row.get("subtitle_decision_count") or 0) for row in rows)
    runtime_outcome_rows = [row for row in rows if str(row.get("runtime_outcome_status") or "").strip()]
    inventory_progress = completed_inventory_progress_payload(rows_loaded=len(rows), source=source)
    warning_list = [
        str(warning or "").strip()
        for warning in warnings
        if str(warning or "").strip()
    ]
    completed_parse_health = dict(parse_health or {})
    skipped_manifest_rows = max(0, int(completed_parse_health.get("skipped_count") or 0))
    if skipped_manifest_rows:
        warning_list.insert(
            0,
            f"Completed manifest parse health is degraded: {skipped_manifest_rows} malformed row(s) were omitted from this preview.",
        )
    if not rows:
        warning_list.insert(0, COMPLETED_HISTORY_EMPTY_MESSAGE)
    fields = {
        "rows": rows,
        "source": source,
        "count": len(rows),
        "missing_output_count": sum(1 for row in rows if row.get("output_exists") is False),
        "encode_count": sum(1 for row in rows if str(row.get("route") or "").startswith("encode")),
        "remux_count": sum(1 for row in rows if str(row.get("route") or "") == "remux"),
        "route_counts": count_by_key(rows, "route"),
        "publish_counts": count_by_key(rows, "publish_state"),
        "health_counts": count_by_key(rows, "output_health", default="ok"),
        "operator_status_counts": count_by_key(rows, "operator_status"),
        "operator_status_state_counts": count_by_key(rows, "operator_status_state"),
        "operator_severity_counts": count_by_key(rows, "operator_severity"),
        "operator_trust_state_counts": count_by_key(rows, "operator_trust_state"),
        "consistency_status_counts": count_by_key(rows, "consistency_status"),
        "consistency_severity_counts": count_by_key(rows, "consistency_severity"),
        "validation_status_state_counts": count_by_key(rows, "validation_status_state"),
        "size_bucket_counts": count_by_key(rows, "size_bucket"),
        "media_type_counts": count_by_key(rows, "media_type"),
        "decision_totals": {
            "audio": audio_decision_total,
            "subtitle": subtitle_decision_total,
        },
        "runtime_outcome_source": runtime_outcome_source,
        "runtime_outcome_event_count": max(0, int(runtime_event_count or 0)),
        "runtime_outcome_match_count": len(runtime_outcome_rows),
        "runtime_outcome_warning": runtime_outcome_warning,
        "runtime_outcome_status_counts": count_by_key(runtime_outcome_rows, "runtime_outcome_status"),
        "runtime_outcome_event_type_counts": count_by_key(runtime_outcome_rows, "runtime_outcome_event_type"),
        "runtime_outcome_error_code_counts": count_by_key(runtime_outcome_rows, "runtime_outcome_error_code"),
        "runtime_outcome_freshness_counts": count_by_key(runtime_outcome_rows, "runtime_outcome_freshness_status"),
        "available_open_target_counts": count_list_values(rows, "available_open_targets"),
        "size_growth_count": sum(1 for row in rows if isinstance(row.get("size_delta_percent"), (int, float)) and float(row["size_delta_percent"]) > 0.0),
        "size_growth_over_5_count": sum(1 for row in rows if bool(row.get("size_growth_over_5"))),
        "size_policy_available_count": sum(1 for row in rows if bool(row.get("size_policy_available"))),
        "size_policy_exceeded_count": sum(1 for row in rows if bool(row.get("size_policy_exceeded"))),
        "size_policy_blocked_count": sum(1 for row in rows if bool(row.get("size_policy_exceeded")) and bool(row.get("size_policy_enforced"))),
        "size_policy_within_limit_count": sum(1 for row in rows if bool(row.get("size_policy_available")) and not bool(row.get("size_policy_exceeded"))),
        "size_policy_status_counts": count_by_key(rows, "size_policy_status"),
        "size_policy_mode_counts": count_by_key(rows, "size_policy_mode"),
        "size_unknown_count": size_unknown_count,
        "missing_sidecar_count": sum(1 for row in rows if "missing_sidecar" in (row.get("consistency_issues") or [])),
        "output_sidecar_mismatch_count": sum(1 for row in rows if "output_sidecar_mismatch" in (row.get("consistency_issues") or [])),
        "stale_sidecar_count": sum(1 for row in rows if "sidecar_older_than_output" in (row.get("consistency_issues") or [])),
        "missing_manifest_output_path_count": sum(1 for row in rows if "manifest_missing_output_path" in (row.get("consistency_issues") or [])),
        "total_output_bytes": total_output_bytes,
        "total_output_size_text": format_bytes_compact(total_output_bytes),
        "inventory_progress": inventory_progress,
        "progress_bars": inventory_progress["progress_bars"],
        "validation_state": validation_state_payload(rows, source=source),
        "warnings": warning_list,
        "parse_health": completed_parse_health,
    }
    fields.update(
        file_freshness_fields(
            manifest_path,
            prefix="manifest",
            stale_after_seconds=COMPLETED_MANIFEST_STALE_AFTER_SECONDS,
        )
    )
    return fields

def completed_history_service_unavailable_result() -> CompletedPreviewDto:
    progress = completed_inventory_progress_payload(
        rows_loaded=0,
        status="blocked",
        detail=COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE,
    )
    return _completed_preview_dto(
        inventory_progress=progress,
        progress_bars=progress["progress_bars"],
        warnings=[COMPLETED_HISTORY_SERVICE_UNAVAILABLE_MESSAGE],
    )

def completed_history_read_error_result(manifest_path: object, exc: Exception) -> CompletedPreviewDto:
    detail = f"Completed history could not be read: {exc}"
    progress = completed_inventory_progress_payload(
        rows_loaded=0,
        source=str(manifest_path or ""),
        status="blocked",
        detail=detail,
    )
    return _completed_preview_dto(
        source=str(manifest_path or ""),
        inventory_progress=progress,
        progress_bars=progress["progress_bars"],
        warnings=[detail],
    )

def completed_preview_from_records(
    records: Iterable[object],
    *,
    source: str,
    manifest_path: Path | None = None,
    runtime_events: Iterable[Any] = (),
    runtime_event_count: int = 0,
    runtime_outcome_source: str = "",
    runtime_outcome_warning: str = "",
    pending_publish_rows: Iterable[Mapping[str, Any]] = (),
    warnings: Iterable[str] = (),
    parse_health: Mapping[str, Any] | None = None,
) -> CompletedPreviewDto:
    rows = completed_preview_rows(records)
    rows = completed_apply_runtime_outcomes(rows, runtime_events)
    rows = completed_pending_publish_rows(pending_publish_rows) + rows
    return _completed_preview_dto(
        **completed_preview_fields(
            rows,
            source=source,
            manifest_path=manifest_path,
            runtime_event_count=runtime_event_count,
            runtime_outcome_source=runtime_outcome_source,
            runtime_outcome_warning=runtime_outcome_warning,
            warnings=warnings,
            parse_health=parse_health,
        )
    )

__all__ = (
    "completed_pending_publish_row",
    "completed_pending_publish_rows",
    "completed_record_to_row",
    "completed_apply_runtime_outcomes",
    "completed_preview_rows",
    "completed_preview_fields",
    "completed_history_service_unavailable_result",
    "completed_history_read_error_result",
    "completed_preview_from_records",
)
