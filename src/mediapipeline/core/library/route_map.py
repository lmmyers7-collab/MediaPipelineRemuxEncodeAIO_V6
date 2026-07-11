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
from mediapipeline.core.library.route_map_evidence import *  # noqa: F403

def build_library_route_map(config: Mapping[str, Any]) -> dict[str, Any]:
    config_map = dict(config or {})
    profiles = effective_library_profiles_from_config(config_map)
    state_by_id = _state_by_library_id(config_map)
    rows = [
        _route_profile_row(config_map, profile, state_by_id.get(str(profile.get("id") or "")))
        for profile in profiles
    ]
    summary_lines = [
        f"Library Route Map profiles: {len(rows)}.",
        "Evidence authority: backend config, Library Profile inheritance state, and backend field metadata.",
        "Boundary: route map is planning evidence only; it does not prove a file processed successfully.",
    ]
    return _base_payload(
        ROUTE_MAP_SCHEMA_VERSION,
        profiles=rows,
        profile_count=len(rows),
        enabled_profile_count=sum(1 for row in rows if row.get("enabled")),
        decision_matrix=[item for row in rows for item in row.get("decision_matrix", [])],
        navigation_actions=[item for row in rows for item in row.get("navigation_actions", [])],
        summary_lines=summary_lines,
        warnings=_route_map_warnings(rows),
    )

def build_library_route_trace(
    config: Mapping[str, Any],
    query: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config_map = dict(config or {})
    query_map = dict(query or {})
    evidence_map = dict(evidence or {})
    selected = _select_existing_evidence_row(query_map, evidence_map)
    selector = selected.get("selector", {})
    row = selected.get("row") if isinstance(selected.get("row"), Mapping) else {}
    source_path = _first_text(
        row.get("source_path"),
        row.get("source"),
        query_map.get("source_path"),
        query_map.get("path"),
    )
    profile = effective_library_profile_for_source_path(config_map, source_path) if source_path else None
    candidates = _matching_profile_candidates(config_map, source_path)
    metadata_gaps = _trace_metadata_gaps(row)
    evidence_state = _selected_evidence_state(selected, evidence_map)
    status = _trace_status(profile, evidence_state, metadata_gaps)
    trace_steps = _trace_steps(profile, candidates, selected, source_path, evidence_state, metadata_gaps)
    runtime_evidence = _runtime_diagnostic_evidence(row)
    return _base_payload(
        ROUTE_TRACE_SCHEMA_VERSION,
        trace_status=status,
        selector=selector,
        selected_source=selected.get("source_name", ""),
        selected_row=_bounded_row(row),
        source_path=source_path,
        library_match=_trace_library_match(profile, config_map),
        candidate_matches=candidates,
        metadata_gaps=metadata_gaps,
        trace_steps=trace_steps,
        runtime_diagnostic_evidence=runtime_evidence,
        summary_lines=[
            f"Selected evidence: {selected.get('source_name') or 'missing'}.",
            f"Trace status: {status}.",
            "Trace uses already loaded Queue, Completed, and Sample Validation evidence only.",
            "Runtime effective settings, when present, are diagnostic-only and separate from library-only effective settings.",
        ],
        warnings=_trace_warnings(status, selected, metadata_gaps),
    )

def build_library_profile_compare(
    config: Mapping[str, Any],
    left_id: str = "",
    right_id: str = "",
) -> dict[str, Any]:
    config_map = dict(config or {})
    profiles = effective_library_profiles_from_config(config_map)
    left, right = _compare_profile_pair(profiles, left_id, right_id)
    if left is None or right is None:
        return _base_payload(
            LIBRARY_PROFILE_COMPARE_SCHEMA_VERSION,
            compare_status="missing",
            left_library_id=str(left_id or ""),
            right_library_id=str(right_id or ""),
            rows=[],
            changed_count=0,
            summary_lines=["Profile compare unavailable: two library profiles are required."],
            warnings=["Select two configured Library Profiles before comparing."],
        )
    rows = _compare_rows(left, right)
    changed_count = sum(1 for row in rows if row.get("changed"))
    return _base_payload(
        LIBRARY_PROFILE_COMPARE_SCHEMA_VERSION,
        compare_status="changed" if changed_count else "same",
        left_library=_profile_identity(left),
        right_library=_profile_identity(right),
        rows=rows,
        row_count=len(rows),
        changed_count=changed_count,
        summary_lines=[
            f"Compared {left.get('name') or left.get('id')} to {right.get('name') or right.get('id')}.",
            f"Changed fields: {changed_count}.",
            "Compare is backend-authored evidence only; edit/save still uses the existing Library Profile Preview/Save path.",
        ],
        warnings=[],
    )

def build_library_route_validation(
    config: Mapping[str, Any],
    evidence: Mapping[str, Any] | None = None,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    config_map = dict(config or {})
    evidence_map = dict(evidence or {})
    normalized_limit = max(1, min(100, int(limit or 20)))
    proof_sections = [
        _sample_validation_proof(evidence_map.get("sample_validation"), normalized_limit),
        _completed_proof(evidence_map.get("completed"), normalized_limit),
        _pending_publish_proof(evidence_map.get("pending_publish"), normalized_limit),
        _diagnostics_proof(evidence_map.get("diagnostics"), normalized_limit),
        _command_history_proof(evidence_map.get("commands"), normalized_limit),
    ]
    proof_rows = [row for section in proof_sections for row in section.get("rows", [])]
    route_map = build_library_route_map(config_map)
    status = _validation_status(proof_sections)
    return _base_payload(
        ROUTE_VALIDATION_SCHEMA_VERSION,
        validation_status=status,
        profile_count=route_map.get("profile_count", 0),
        proof_sections=proof_sections,
        proof_rows=proof_rows,
        proof_row_count=len(proof_rows),
        summary_lines=[
            f"Validation handoff status: {status}.",
            "Route-map evidence is not processing proof.",
            "Completed proof, pending-publish proof, sample-validation proof, diagnostics, and commands remain distinct categories.",
        ],
        warnings=_validation_warnings(proof_sections),
    )
