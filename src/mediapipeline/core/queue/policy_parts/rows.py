"""Queue row shaping, route evidence, and operator-state policy."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from mediapipeline.core.queue.policy_parts.rules import EMPTY_QUEUE_SNAPSHOT_WARNING
from mediapipeline.core.queue.policy_parts.file_override_rows import _annotate_queue_file_override
from mediapipeline.core.queue.policy_parts.operator_guidance import (
    queue_row_operator_guidance,
    queue_row_operator_status_state,
    queue_row_trust_fields,
)
from mediapipeline.core.queue.policy_parts.route_evidence import queue_row_route_decision_summary, queue_row_route_evidence_lines
from mediapipeline.core.queue.policy_parts.row_identity import (
    LIBRARY_EFFECTIVE_SETTINGS_SCOPE,
    OVERRIDE_LAYERS_PENDING,
    RUNTIME_EVIDENCE_NOTE,
    _bool_value,
    _float_value,
    _json_list,
    _json_mapping,
    _text_value,
    queue_row_available_open_targets,
    queue_row_key,
)
from mediapipeline.core.queue.policy_parts.runtime_outcomes import queue_apply_runtime_outcomes
from mediapipeline.core.queue.policy_parts.track_metadata import queue_preview_track_metadata_summary
from mediapipeline.core.subtitles.qa import build_queue_subtitle_qa
from mediapipeline.desktop.models import QueueRecord



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
    row["subtitle_qa"] = build_queue_subtitle_qa(row)
    return row






















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
            invalid_row["subtitle_qa"] = build_queue_subtitle_qa(invalid_row)
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
            if "manual_order_position" in raw_row:
                safe_row["manual_order_position"] = raw_row.get("manual_order_position")
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
            safe_row["subtitle_qa"] = build_queue_subtitle_qa(safe_row)
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
