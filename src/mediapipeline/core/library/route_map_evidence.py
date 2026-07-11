"""Read-only Library Route Map evidence builders."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from mediapipeline.core.config.library_profile_defaults import (
    LIBRARY_OVERRIDE_GROUPS,
    LIBRARY_OVERRIDE_KEYS_BY_GROUP,
    LIBRARY_PROFILE_PATH_FIELDS,
)
from mediapipeline.core.config.library_profile_state import (
    effective_library_profile_for_source_path,
    effective_library_profiles_from_config,
    library_profile_state_from_config,
)
from mediapipeline.core.config.metadata_parts.field_definitions import CONFIG_FIELD_DEFINITIONS
from mediapipeline.core.kernel.dto_base import json_safe


ROUTE_MAP_SCHEMA_VERSION = "library_route_map.v1"
ROUTE_TRACE_SCHEMA_VERSION = "library_route_trace.v1"
LIBRARY_PROFILE_COMPARE_SCHEMA_VERSION = "library_profile_compare.v1"
ROUTE_VALIDATION_SCHEMA_VERSION = "library_route_validation_handoff.v1"

ROUTE_EDITOR_FIELD_KEYS: tuple[str, ...] = (
    "RoutingProfile",
    "RouteThresholdMode",
    "SizeGuardMode",
    "EncodeTuningPreset",
    "EncodeLadder",
    "VideoCodec",
    "OutputContainer",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
    "MovieRoute1080pTargetSizeGB",
    "MovieRoute1440pTargetSizeGB",
    "MovieRoute4KTargetSizeGB",
    "TVRoute1080pTargetSizeGB",
    "TVRoute1440pTargetSizeGB",
    "TVRoute4KTargetSizeGB",
    "Route1080pUpperHeightTolerancePercent",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route4KLowerHeightTolerancePercent",
    "Route1080pMaxVideoBitrateMbps",
    "Route1440pMaxVideoBitrateMbps",
    "Route4KMaxVideoBitrateMbps",
)

ROUTE_BUCKETS: tuple[dict[str, Any], ...] = (
    {
        "bucket": "1080p",
        "label": "1080p",
        "movie_target_key": "MovieRoute1080pTargetSizeGB",
        "tv_target_key": "TVRoute1080pTargetSizeGB",
        "bitrate_key": "Route1080pMaxVideoBitrateMbps",
    },
    {
        "bucket": "1440p",
        "label": "1440p",
        "movie_target_key": "MovieRoute1440pTargetSizeGB",
        "tv_target_key": "TVRoute1440pTargetSizeGB",
        "bitrate_key": "Route1440pMaxVideoBitrateMbps",
    },
    {
        "bucket": "4k",
        "label": "4K",
        "movie_target_key": "MovieRoute4KTargetSizeGB",
        "tv_target_key": "TVRoute4KTargetSizeGB",
        "bitrate_key": "Route4KMaxVideoBitrateMbps",
    },
)

_FIELD_BY_KEY: dict[str, Mapping[str, Any]] = {
    str(field.get("key") or ""): field
    for field in CONFIG_FIELD_DEFINITIONS
    if str(field.get("key") or "")
}



from mediapipeline.core.library.route_map_projection import *  # noqa: F403

def _matching_profile_candidates(config: Mapping[str, Any], source_path: str) -> list[dict[str, Any]]:
    if not source_path:
        return []
    source_key = _path_key(source_path)
    matches: list[dict[str, Any]] = []
    for profile in effective_library_profiles_from_config(config):
        root = _first_text(profile.get("effective_source_root"), profile.get("source_path"))
        root_key = _path_key(root)
        matched = bool(root_key and (source_key == root_key or source_key.startswith(root_key + "/")))
        if not matched:
            continue
        matches.append(
            {
                **_profile_identity(profile),
                "enabled": _bool(profile.get("enabled"), True),
                "source_root": root,
                "match_depth": len(root_key),
                "eligible": _bool(profile.get("enabled"), True),
            }
        )
    matches.sort(key=lambda item: (not bool(item.get("eligible")), -int(item.get("match_depth") or 0)))
    return matches


def _select_existing_evidence_row(query: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    selector = {
        "row_key": _first_text(query.get("row_key"), query.get("id")),
        "source_path": _first_text(query.get("source_path"), query.get("path")),
        "output_path": _text(query.get("output_path")),
    }
    sources = (
        ("queue", _rows_from_payload(evidence.get("queue"), "rows")),
        ("completed", _rows_from_payload(evidence.get("completed"), "rows")),
        ("sample_validation", _rows_from_payload(evidence.get("sample_validation"), "records")),
    )
    fallback: tuple[str, Mapping[str, Any]] | None = None
    for source_name, rows in sources:
        for row in rows:
            if fallback is None:
                fallback = (source_name, row)
            if _row_matches_selector(row, selector):
                return {"source_name": source_name, "row": row, "selector": selector}
    if any(selector.values()):
        return {"source_name": "", "row": {}, "selector": selector}
    if fallback is not None:
        return {"source_name": fallback[0], "row": fallback[1], "selector": selector}
    return {"source_name": "", "row": {}, "selector": selector}


def _rows_from_payload(payload: Any, key: str) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get(key)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _row_matches_selector(row: Mapping[str, Any], selector: Mapping[str, str]) -> bool:
    row_key = _text(selector.get("row_key"))
    if row_key and row_key.casefold() in {
        _text(row.get("row_key")).casefold(),
        _text(row.get("record_id")).casefold(),
        _text(row.get("id")).casefold(),
    }:
        return True
    source_path = _text(selector.get("source_path"))
    if source_path and _path_key(source_path) in {
        _path_key(row.get("source_path")),
        _path_key(row.get("source")),
    }:
        return True
    output_path = _text(selector.get("output_path"))
    if output_path and _path_key(output_path) in {
        _path_key(row.get("output_path")),
        _path_key(row.get("manifest_output_path")),
        _path_key(row.get("local_file")),
        _path_key(row.get("server_out")),
    }:
        return True
    return False


def _selected_evidence_state(selected: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    source_name = str(selected.get("source_name") or "")
    if not source_name:
        return {"status": "missing", "summary": "No loaded Queue, Completed, or Sample Validation row matched the selector."}
    payload = evidence.get(source_name)
    if not isinstance(payload, Mapping):
        return {"status": "missing", "summary": f"{source_name} payload is unavailable."}
    freshness = _first_text(
        payload.get("produced_freshness_status"),
        payload.get("snapshot_file_freshness_status"),
        payload.get("manifest_freshness_status"),
    ).casefold()
    if freshness == "stale":
        return {"status": "stale", "summary": f"{source_name} evidence is stale."}
    if payload.get("error"):
        return {"status": "blocked", "summary": f"{source_name} evidence has an error: {payload.get('error')}"}
    return {"status": "current", "summary": f"{source_name} evidence row is loaded."}


def _trace_metadata_gaps(row: Mapping[str, Any]) -> list[str]:
    if not row:
        return ["row_evidence"]
    gaps: list[str] = []
    if _value_missing(_first_present(row, "height", "video_height", "source_height")):
        gaps.append("dimensions")
    if _value_missing(_first_present(row, "duration_seconds", "duration_sec", "source_duration_seconds")):
        gaps.append("duration")
    if _value_missing(_first_present(row, "estimated_bitrate_mbps", "video_bitrate_mbps", "bitrate_mbps")):
        gaps.append("bitrate")
    if _value_missing(_first_present(row, "media_type", "library_designation")):
        gaps.append("media_type")
    return gaps


def _trace_status(
    profile: Mapping[str, Any] | None,
    evidence_state: Mapping[str, Any],
    metadata_gaps: list[str],
) -> str:
    evidence_status = str(evidence_state.get("status") or "missing")
    if evidence_status in {"missing", "blocked"}:
        return evidence_status
    if evidence_status == "stale":
        return "stale"
    if profile is None:
        return "review"
    profile_status = _profile_route_status(
        profile,
        {
            field: _path_evidence((profile.get("path_field_state") or {}).get(field))
            for field in LIBRARY_PROFILE_PATH_FIELDS
        },
        _profile_route_fields(profile),
    )
    if profile_status == "blocked":
        return "blocked"
    if metadata_gaps:
        return "review"
    if profile_status != "current":
        return "review"
    return "current"


def _trace_steps(
    profile: Mapping[str, Any] | None,
    candidates: list[Mapping[str, Any]],
    selected: Mapping[str, Any],
    source_path: str,
    evidence_state: Mapping[str, Any],
    metadata_gaps: list[str],
) -> list[dict[str, Any]]:
    matched = _profile_identity(profile) if isinstance(profile, Mapping) else {}
    return [
        {
            "step": "existing_evidence",
            "status": evidence_state.get("status", "missing"),
            "summary": evidence_state.get("summary", ""),
            "source": selected.get("source_name", ""),
        },
        {
            "step": "source_path",
            "status": "current" if source_path else "missing",
            "summary": source_path or "No source path was present in the selected evidence.",
        },
        {
            "step": "profile_match",
            "status": "current" if matched else "review",
            "summary": (
                f"Matched {matched.get('library_name')} by deepest enabled source-root match."
                if matched
                else "No enabled Library Profile source root matched this source path."
            ),
            "matched_library": matched,
            "candidates": list(candidates),
        },
        {
            "step": "metadata_completeness",
            "status": "review" if metadata_gaps else "current",
            "summary": "Missing metadata blocks a confident route trace." if metadata_gaps else "Required trace metadata is present.",
            "gaps": metadata_gaps,
        },
        {
            "step": "runtime_effective_settings",
            "status": "diagnostic_only",
            "summary": "Runtime effective settings are displayed separately and do not overwrite library-only route evidence.",
        },
    ]


def _trace_library_match(profile: Mapping[str, Any] | None, config: Mapping[str, Any]) -> dict[str, Any]:
    if profile is None:
        return {}
    state_by_id = _state_by_library_id(config)
    row = _route_profile_row(config, profile, state_by_id.get(str(profile.get("id") or "")))
    return {
        **_profile_identity(profile),
        "profile_status": row.get("profile_status"),
        "path_evidence": row.get("path_evidence"),
        "decision_matrix": row.get("decision_matrix"),
        "route_fields": row.get("route_fields"),
    }


def _runtime_diagnostic_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "runtime_effective_settings_available": _bool(row.get("runtime_effective_settings_available"), False),
        "library_effective_settings_scope": _text(row.get("library_effective_settings_scope")),
        "library_effective_settings": row.get("library_effective_settings") if isinstance(row.get("library_effective_settings"), Mapping) else {},
        "runtime_evidence_note": _text(row.get("runtime_evidence_note")),
        "override_layers_pending": row.get("override_layers_pending") if isinstance(row.get("override_layers_pending"), list) else [],
        "diagnostic_only": True,
    }


def _trace_warnings(
    status: str,
    selected: Mapping[str, Any],
    metadata_gaps: list[str],
) -> list[str]:
    warnings: list[str] = []
    if status in {"missing", "stale", "review", "blocked"}:
        warnings.append(f"Trace status is {status}; do not treat this as proof of safe processing.")
    if not selected.get("source_name"):
        warnings.append("No existing Queue, Completed, or Sample Validation row matched the selector.")
    if metadata_gaps:
        warnings.append(f"Trace metadata gaps: {', '.join(metadata_gaps)}.")
    return warnings


def _compare_profile_pair(
    profiles: list[Mapping[str, Any]],
    left_id: str,
    right_id: str,
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    by_id = {str(profile.get("id") or ""): profile for profile in profiles}
    left = by_id.get(str(left_id or "")) if left_id else (profiles[0] if profiles else None)
    if right_id:
        right = by_id.get(str(right_id or ""))
    else:
        right = next((profile for profile in profiles if profile is not left), None)
    return left, right


def _compare_rows(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in LIBRARY_PROFILE_PATH_FIELDS:
        left_evidence = _path_evidence((left.get("path_field_state") or {}).get(field))
        right_evidence = _path_evidence((right.get("path_field_state") or {}).get(field))
        rows.append(
            {
                "section": "paths",
                "field": field,
                "label": field.replace("_", " ").title(),
                "left": left_evidence,
                "right": right_evidence,
                "changed": _compare_value(left_evidence.get("effective_value")) != _compare_value(right_evidence.get("effective_value"))
                or left_evidence.get("state") != right_evidence.get("state"),
                "applies": {"left": True, "right": True},
                "navigation": {
                    "left": _navigation_target(left, path_field=field),
                    "right": _navigation_target(right, path_field=field),
                },
            }
        )
    for group in LIBRARY_OVERRIDE_GROUPS:
        for key in LIBRARY_OVERRIDE_KEYS_BY_GROUP[group]:
            field = _field(key)
            left_applies = _field_applies_to_designation(field, _designation(left))
            right_applies = _field_applies_to_designation(field, _designation(right))
            if not (left_applies or right_applies):
                continue
            left_row = _route_field_row(left, group, key, _setting_evidence(left, group, key), field)
            right_row = _route_field_row(right, group, key, _setting_evidence(right, group, key), field)
            rows.append(
                {
                    "section": group,
                    "field": key,
                    "label": str(field.get("label") or key),
                    "left": left_row if left_applies else {"status": "not_applicable"},
                    "right": right_row if right_applies else {"status": "not_applicable"},
                    "changed": _compare_value(left_row.get("effective_value")) != _compare_value(right_row.get("effective_value"))
                    or left_row.get("state") != right_row.get("state")
                    or left_applies != right_applies,
                    "applies": {"left": left_applies, "right": right_applies},
                    "navigation": {
                        "left": _navigation_target(left, group=group, key=key),
                        "right": _navigation_target(right, group=group, key=key),
                    },
                }
            )
    return rows


def _sample_validation_proof(payload: Any, limit: int) -> dict[str, Any]:
    records = _rows_from_payload(payload, "records")[:limit]
    rows = [
        {
            "proof_type": "sample_validation",
            "status": _first_text(record.get("operator_decision"), record.get("proof_strength"), "review"),
            "source_path": _text(record.get("source_path")),
            "output_path": _text(record.get("output_path")),
            "sample_category": _text(record.get("sample_category")),
            "record_id": _text(record.get("record_id")),
        }
        for record in records
    ]
    return _proof_section("sample_validation", payload, rows, "Sample Validation proof")


def _completed_proof(payload: Any, limit: int) -> dict[str, Any]:
    rows = [
        {
            "proof_type": "completed",
            "status": _first_text(row.get("output_proof"), row.get("operator_status_state"), "review"),
            "source_path": _text(row.get("source_path")),
            "output_path": _text(row.get("output_path")),
            "route": _first_text(row.get("route"), row.get("route_label")),
            "row_key": _text(row.get("row_key")),
        }
        for row in _rows_from_payload(payload, "rows")[:limit]
    ]
    return _proof_section("completed", payload, rows, "Completed proof")


def _pending_publish_proof(payload: Any, limit: int) -> dict[str, Any]:
    rows = [
        {
            "proof_type": "pending_publish",
            "status": _first_text(row.get("state"), row.get("diagnostic_status_state"), "review"),
            "source_path": _text(row.get("source_path")),
            "output_path": _first_text(row.get("server_out"), row.get("local_file")),
            "ready_to_drain": _bool(row.get("ready_to_drain"), False),
            "row_key": _text(row.get("row_key")),
        }
        for row in _rows_from_payload(payload, "rows")[:limit]
    ]
    return _proof_section("pending_publish", payload, rows, "Pending Publish proof")


def _diagnostics_proof(payload: Any, limit: int) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    lines = [str(item) for item in payload_map.get("recent_errors") or []][:limit]
    lines.extend(str(item) for item in payload_map.get("warnings") or [] if str(item).strip())
    rows = [
        {
            "proof_type": "diagnostics",
            "status": "review" if lines else "missing",
            "source_path": "",
            "output_path": "",
            "message": line,
        }
        for line in lines[:limit]
    ]
    if not rows and payload_map:
        rows.append(
            {
                "proof_type": "diagnostics",
                "status": "current",
                "source_path": "",
                "output_path": "",
                "message": _first_text(payload_map.get("status_summary"), "Diagnostics payload loaded."),
            }
        )
    return _proof_section("diagnostics", payload, rows, "Diagnostics proof")


def _command_history_proof(payload: Any, limit: int) -> dict[str, Any]:
    rows = [
        {
            "proof_type": "command_history",
            "status": _first_text(entry.get("severity"), entry.get("status"), "recorded"),
            "command": _text(entry.get("command")),
            "message": _text(entry.get("message")),
            "recorded_at": _first_text(entry.get("recorded_at"), entry.get("timestamp")),
        }
        for entry in _rows_from_payload(payload, "entries")[:limit]
    ]
    return _proof_section("command_history", payload, rows, "Command evidence")


def _proof_section(name: str, payload: Any, rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    payload_map = payload if isinstance(payload, Mapping) else {}
    status = "missing" if not payload_map else ("current" if rows else "review")
    if payload_map.get("error"):
        status = "blocked"
    return {
        "proof_type": name,
        "label": label,
        "status": status,
        "row_count": len(rows),
        "rows": rows,
        "source_schema": _text(payload_map.get("schema_version")),
        "source_error": _text(payload_map.get("error")),
        "source_warnings": [str(item) for item in payload_map.get("warnings") or [] if str(item).strip()],
    }


def _validation_status(sections: Iterable[Mapping[str, Any]]) -> str:
    statuses = {str(section.get("status") or "missing") for section in sections}
    if "blocked" in statuses:
        return "blocked"
    if statuses <= {"missing", "review"}:
        return "missing"
    if "review" in statuses or "missing" in statuses:
        return "review"
    return "current"


def _validation_warnings(sections: Iterable[Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for section in sections:
        if section.get("status") != "current":
            warnings.append(f"{section.get('label')}: {section.get('status')}.")
    return warnings



















__all__ = (
    "_matching_profile_candidates",
    "_select_existing_evidence_row",
    "_rows_from_payload",
    "_row_matches_selector",
    "_selected_evidence_state",
    "_trace_metadata_gaps",
    "_trace_status",
    "_trace_steps",
    "_trace_library_match",
    "_runtime_diagnostic_evidence",
    "_trace_warnings",
    "_compare_profile_pair",
    "_compare_rows",
    "_sample_validation_proof",
    "_completed_proof",
    "_pending_publish_proof",
    "_diagnostics_proof",
    "_command_history_proof",
    "_proof_section",
    "_validation_status",
    "_validation_warnings",
)
