"""Queue route evidence summary helpers."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from .row_identity import LIBRARY_EFFECTIVE_SETTINGS_SCOPE, _bool_value, _float_value, _json_list

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
