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


def _base_payload(schema_version: str, **fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "evidence_authority": "backend",
        "read_only": True,
        "mutation_enabled": False,
        "effects": [],
        "guardrail": (
            "Evidence only. No launch, drain, accept, repair, rename, settings save, "
            "plugin execution, queue mutation, or filesystem mutation is performed."
        ),
    }
    payload.update(fields)
    return json_safe(payload)


def _state_by_library_id(config: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(state.get("library_id") or ""): state
        for state in library_profile_state_from_config(config)
        if isinstance(state, Mapping)
    }


def _route_profile_row(
    config: Mapping[str, Any],
    profile: Mapping[str, Any],
    state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    state_map = state if isinstance(state, Mapping) else {}
    path_fields = state_map.get("path_fields") if isinstance(state_map.get("path_fields"), Mapping) else {}
    path_evidence = {
        field: _path_evidence(path_fields.get(field) if isinstance(path_fields, Mapping) else None)
        for field in LIBRARY_PROFILE_PATH_FIELDS
    }
    route_fields = _profile_route_fields(profile)
    status = _profile_route_status(profile, path_evidence, route_fields)
    nodes = _profile_nodes(profile, path_evidence, route_fields, status)
    return {
        **_profile_identity(profile),
        "enabled": _bool(profile.get("enabled"), True),
        "profile_status": status,
        "path_evidence": path_evidence,
        "route_fields": route_fields,
        "decision_matrix": _decision_matrix_rows(profile, route_fields),
        "nodes": nodes,
        "edges": _profile_edges(nodes),
        "navigation_actions": _navigation_actions(profile, route_fields),
        "summary_lines": _profile_summary_lines(profile, status, path_evidence),
        "library_only_effective_settings": _library_only_effective_settings(profile),
        "runtime_effective_settings": {
            "available": False,
            "status": "diagnostic_only",
            "summary": "Runtime effective settings are intentionally not merged into this library-only map.",
        },
        "source_match_policy": "enabled profiles only; deepest source-root match wins",
    }


def _profile_identity(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "library_id": str(profile.get("id") or profile.get("library_id") or ""),
        "library_name": str(profile.get("name") or profile.get("id") or "Library"),
        "designation": _designation(profile),
    }


def _designation(profile: Mapping[str, Any]) -> str:
    value = str(profile.get("designation") or "auto").strip().casefold()
    return value if value in {"movie", "tv", "auto"} else "auto"


def _path_evidence(raw: Any) -> dict[str, Any]:
    item = raw if isinstance(raw, Mapping) else {}
    state = str(item.get("state") or "unknown").strip() or "unknown"
    effective_value = _text(item.get("effective_value"))
    required = _bool(item.get("required"), False)
    if state == "explicit" and effective_value:
        status = "current"
    elif state == "invalid_unresolved" or (required and not effective_value):
        status = "blocked"
    elif state in {"inherited", "synthesized_builtin_default"}:
        status = "review"
    elif state in {"not_configured", "unknown"} or not effective_value:
        status = "unknown"
    else:
        status = "review"
    return {
        "field": str(item.get("field") or ""),
        "state": state,
        "status": status,
        "safe": status == "current",
        "origin": str(item.get("origin") or ""),
        "source_key": str(item.get("source_key") or ""),
        "effective_value": effective_value,
        "explicit_value": item.get("explicit_value"),
        "required": required,
        "summary": _path_summary(state, status, effective_value),
    }


def _path_summary(state: str, status: str, value: str) -> str:
    if status == "current":
        return f"Explicit path is configured: {value}"
    if status == "blocked":
        return "Required path is missing or unresolved."
    if state == "inherited":
        return "Inherited path requires review before treating this route as safe."
    if state == "synthesized_builtin_default":
        return "Synthesized built-in default path requires review before treating this route as safe."
    return "Path evidence is unknown or not configured."


def _profile_route_fields(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    designation = _designation(profile)
    route_fields: list[dict[str, Any]] = []
    for key in ROUTE_EDITOR_FIELD_KEYS:
        field = _field(key)
        applies = _field_applies_to_designation(field, designation)
        if not applies:
            continue
        evidence = _setting_evidence(profile, "editor", key)
        route_fields.append(_route_field_row(profile, "editor", key, evidence, field))
    return route_fields


def _route_field_row(
    profile: Mapping[str, Any],
    group: str,
    key: str,
    evidence: Mapping[str, Any],
    field: Mapping[str, Any],
) -> dict[str, Any]:
    state = str(evidence.get("state") or "inherited").strip() or "inherited"
    effective_value = evidence.get("effective_value")
    value_missing = _value_missing(effective_value)
    status = "unknown" if value_missing else "current"
    return {
        "group": group,
        "key": key,
        "label": str(field.get("label") or key),
        "short_label": str(field.get("short_label") or field.get("label") or key),
        "section": str(field.get("section") or ""),
        "strictness": str(field.get("strictness") or ""),
        "rule_taxonomy": [str(item) for item in field.get("rule_taxonomy") or []],
        "state": state,
        "status": status,
        "effective_value": effective_value,
        "inherited_value": evidence.get("inherited_value"),
        "explicit_value": evidence.get("explicit_value"),
        "value_equals_global": _bool(evidence.get("value_equals_global"), False),
        "source": "library_override" if state == "explicit" else "global_inherited",
        "navigation": _navigation_target(profile, group=group, key=key),
        "metadata": {
            "unit": field.get("unit"),
            "min": field.get("min"),
            "max": field.get("max"),
            "allowed_values": field.get("allowed_values"),
            "validation_owner": field.get("validation_owner"),
            "runtime_consumer": field.get("runtime_consumer"),
        },
    }


def _setting_evidence(profile: Mapping[str, Any], group: str, key: str) -> Mapping[str, Any]:
    states = profile.get("setting_override_state")
    if isinstance(states, Mapping):
        group_states = states.get(group)
        if isinstance(group_states, Mapping):
            item = group_states.get(key)
            if isinstance(item, Mapping):
                return item
    settings = profile.get("effective_settings")
    group_settings = settings.get(group) if isinstance(settings, Mapping) else {}
    effective_value = group_settings.get(key) if isinstance(group_settings, Mapping) else None
    return {
        "field": key,
        "group": group,
        "state": "inherited",
        "effective_value": effective_value,
        "inherited_value": effective_value,
        "explicit_value": None,
        "value_equals_global": False,
    }


def _field(key: str) -> Mapping[str, Any]:
    return _FIELD_BY_KEY.get(key, {"key": key, "label": key})


def _field_applies_to_designation(field: Mapping[str, Any], designation: str) -> bool:
    allowed = field.get("library_profile_designations")
    if not allowed:
        return True
    return designation in {str(item).strip().casefold() for item in allowed}


def _profile_route_status(
    profile: Mapping[str, Any],
    path_evidence: Mapping[str, Mapping[str, Any]],
    route_fields: Iterable[Mapping[str, Any]],
) -> str:
    if not _bool(profile.get("enabled"), True):
        return "disabled"
    path_statuses = {str(item.get("status") or "") for item in path_evidence.values()}
    required_path_statuses = {
        str(item.get("status") or "")
        for item in path_evidence.values()
        if _bool(item.get("required"), False)
    }
    if "blocked" in path_statuses:
        return "blocked"
    if required_path_statuses & {"review", "unknown"}:
        return "review"
    if any(str(field.get("status") or "") == "unknown" for field in route_fields):
        return "review"
    return "current"


def _profile_nodes(
    profile: Mapping[str, Any],
    path_evidence: Mapping[str, Mapping[str, Any]],
    route_fields: list[Mapping[str, Any]],
    status: str,
) -> list[dict[str, Any]]:
    library_id = str(profile.get("id") or "")
    route_field_keys = [str(field.get("key") or "") for field in route_fields]
    return [
        {
            "id": f"{library_id}:source",
            "type": "source_root",
            "label": "Source root",
            "status": str(path_evidence.get("source_path", {}).get("status") or "unknown"),
            "fields": ["source_path"],
            "evidence": path_evidence.get("source_path", {}),
            "navigation": _navigation_target(profile, path_field="source_path"),
        },
        {
            "id": f"{library_id}:profile_match",
            "type": "profile_match",
            "label": "Profile match",
            "status": status,
            "fields": ["enabled", "designation"],
            "evidence": {
                "enabled": _bool(profile.get("enabled"), True),
                "designation": _designation(profile),
                "source_match_policy": "deepest enabled source root wins",
            },
        },
        {
            "id": f"{library_id}:route_decision",
            "type": "route_decision",
            "label": "Decision matrix",
            "status": "review" if status in {"review", "blocked"} else "current",
            "fields": route_field_keys,
            "evidence": {"field_count": len(route_field_keys)},
            "navigation": _navigation_target(profile, group="editor", key="RoutingProfile"),
        },
        {
            "id": f"{library_id}:processing",
            "type": "processing_policy",
            "label": "Remux / encode settings",
            "status": "review" if status == "blocked" else status,
            "fields": ["RouteThresholdMode", "VideoCodec", "OutputContainer"],
            "evidence": {"library_only": True, "runtime_effective_settings": "diagnostic_only"},
            "navigation": _navigation_target(profile, group="editor", key="RouteThresholdMode"),
        },
        {
            "id": f"{library_id}:validation_handoff",
            "type": "validation_handoff",
            "label": "Validation handoff",
            "status": "unknown",
            "fields": ["sample_validation", "completed", "pending_publish", "diagnostics"],
            "evidence": {"proof_required": True, "route_map_is_not_processing_proof": True},
        },
    ]


def _profile_edges(nodes: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    ids = [str(node.get("id") or "") for node in nodes if str(node.get("id") or "")]
    return [{"from": ids[index], "to": ids[index + 1]} for index in range(max(0, len(ids) - 1))]


def _navigation_actions(profile: Mapping[str, Any], route_fields: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    actions = [
        _navigation_target(profile, path_field="source_path"),
        _navigation_target(profile, path_field="output_path"),
    ]
    actions.extend(field.get("navigation", {}) for field in route_fields)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in actions:
        key = "|".join(
            [
                str(action.get("library_id") or ""),
                str(action.get("path_field") or ""),
                str(action.get("group") or ""),
                str(action.get("key") or ""),
            ]
        )
        if key not in seen:
            seen.add(key)
            deduped.append(dict(action))
    return deduped


def _navigation_target(
    profile: Mapping[str, Any],
    *,
    path_field: str = "",
    group: str = "",
    key: str = "",
) -> dict[str, Any]:
    library_id = str(profile.get("id") or "")
    label = key or path_field or library_id
    return {
        "type": "existing_library_profile_control",
        "library_id": library_id,
        "label": label,
        "path_field": path_field,
        "group": group,
        "key": key,
        "selector": _navigation_selector(library_id, path_field=path_field, group=group, key=key),
        "mutation": "none",
        "handoff": "existing Library Profile Stage Patch, Preview, and Save controls only",
    }


def _navigation_selector(library_id: str, *, path_field: str = "", group: str = "", key: str = "") -> str:
    if path_field:
        return f'[data-library-id="{library_id}"] [data-library-field="{path_field}"]'
    if group and key:
        return (
            f'[data-library-id="{library_id}"] '
            f'[data-library-override-row][data-library-override-group="{group}"][data-library-override-key="{key}"]'
        )
    return f'[data-library-profile-tab][data-profile-id="{library_id}"]'


def _decision_matrix_rows(profile: Mapping[str, Any], route_fields: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    values = {str(field.get("key") or ""): field.get("effective_value") for field in route_fields}
    boundaries = _route_boundaries(values)
    designation = _designation(profile)
    missing = [key for key in ROUTE_EDITOR_FIELD_KEYS if key in values and _value_missing(values.get(key))]
    rows: list[dict[str, Any]] = []
    for bucket in ROUTE_BUCKETS:
        target_fields = _target_fields_for_designation(bucket, designation)
        rows.append(
            {
                "library_id": str(profile.get("id") or ""),
                "library_name": str(profile.get("name") or profile.get("id") or ""),
                "designation": designation,
                "bucket": bucket["bucket"],
                "label": bucket["label"],
                "height_rule": _height_rule(bucket["bucket"], boundaries),
                "target_fields": target_fields,
                "target_values": {field: values.get(field) for field in target_fields},
                "direct_copy_bitrate_field": bucket["bitrate_key"],
                "direct_copy_bitrate_mbps": values.get(str(bucket["bitrate_key"])),
                "threshold_mode": values.get("RouteThresholdMode"),
                "routing_profile": values.get("RoutingProfile"),
                "status": "review" if missing else "current",
                "missing_keys": missing,
            }
        )
    rows.append(
        {
            "library_id": str(profile.get("id") or ""),
            "library_name": str(profile.get("name") or profile.get("id") or ""),
            "designation": designation,
            "bucket": "unknown_dimensions",
            "label": "Unknown dimensions",
            "height_rule": "ffprobe dimensions missing",
            "target_fields": _target_fields_for_designation(ROUTE_BUCKETS[0], designation),
            "target_values": {
                field: values.get(field)
                for field in _target_fields_for_designation(ROUTE_BUCKETS[0], designation)
            },
            "direct_copy_bitrate_field": "",
            "direct_copy_bitrate_mbps": None,
            "threshold_mode": values.get("RouteThresholdMode"),
            "routing_profile": values.get("RoutingProfile"),
            "status": "review",
            "missing_keys": ["dimensions"],
        }
    )
    return rows


def _route_boundaries(values: Mapping[str, Any]) -> dict[str, int | None]:
    return {
        "route1080p_max_height": _boundary_height(1080, values.get("Route1080pUpperHeightTolerancePercent"), "upper"),
        "route1440p_min_height": _boundary_height(1440, values.get("Route1440pLowerHeightTolerancePercent"), "lower"),
        "route1440p_max_height": _boundary_height(1440, values.get("Route1440pUpperHeightTolerancePercent"), "upper"),
        "route4k_min_height": _boundary_height(2160, values.get("Route4KLowerHeightTolerancePercent"), "lower"),
    }


def _boundary_height(base: int, percent: Any, direction: str) -> int | None:
    number = _number(percent)
    if number is None:
        return None
    multiplier = 1.0 + (number / 100.0) if direction == "upper" else 1.0 - (number / 100.0)
    return int(round(float(base) * multiplier))


def _height_rule(bucket: str, boundaries: Mapping[str, int | None]) -> str:
    if bucket == "1080p":
        value = boundaries.get("route1080p_max_height")
        return f"height <= {value}p" if value else "1080p upper bound unknown"
    if bucket == "1440p":
        lower = boundaries.get("route1440p_min_height")
        upper = boundaries.get("route1440p_max_height")
        return f"{lower}p <= height <= {upper}p" if lower and upper else "1440p bounds unknown"
    lower = boundaries.get("route4k_min_height")
    return f"height >= {lower}p" if lower else "4K lower bound unknown"


def _target_fields_for_designation(bucket: Mapping[str, Any], designation: str) -> list[str]:
    if designation == "movie":
        return [str(bucket["movie_target_key"])]
    if designation == "tv":
        return [str(bucket["tv_target_key"])]
    return [str(bucket["movie_target_key"]), str(bucket["tv_target_key"])]


def _profile_summary_lines(
    profile: Mapping[str, Any],
    status: str,
    path_evidence: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    source = path_evidence.get("source_path", {})
    output = path_evidence.get("output_path", {})
    return [
        f"{profile.get('name') or profile.get('id')}: {status}.",
        f"Source path evidence: {source.get('status') or 'unknown'} ({source.get('state') or 'unknown'}).",
        f"Output path evidence: {output.get('status') or 'unknown'} ({output.get('state') or 'unknown'}).",
    ]


def _library_only_effective_settings(profile: Mapping[str, Any]) -> dict[str, Any]:
    settings = profile.get("effective_settings")
    return dict(settings) if isinstance(settings, Mapping) else {}


def _route_map_warnings(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if not list(rows):
        warnings.append("No Library Profiles are configured or synthesized.")
        return warnings
    for row in rows:
        if row.get("profile_status") in {"blocked", "review", "disabled"}:
            warnings.append(
                f"{row.get('library_name') or row.get('library_id')}: route status is {row.get('profile_status')}."
            )
    return warnings


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


def _bounded_row(row: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "row_key",
        "record_id",
        "source_path",
        "output_path",
        "media_type",
        "library_id",
        "library_name",
        "library_designation",
        "route",
        "route_name",
        "route_reason",
        "route_reason_code",
        "estimated_bitrate_mbps",
        "route_size_threshold_gb",
        "route_bitrate_threshold_mbps",
        "route_threshold_mode",
        "height",
        "video_height",
        "duration_seconds",
        "size_gb",
    }
    return {key: json_safe(row.get(key)) for key in sorted(allowed) if key in row}


def _first_present(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and not _value_missing(row.get(key)):
            return row.get(key)
    return None


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return fallback
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _value_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _path_key(value: Any) -> str:
    return _text(value).replace("\\", "/").rstrip("/").casefold()


def _compare_value(value: Any) -> Any:
    safe = json_safe(value)
    if isinstance(safe, str):
        return safe.replace("\\", "/")
    if isinstance(safe, list):
        return [_compare_value(item) for item in safe]
    if isinstance(safe, dict):
        return {str(key): _compare_value(item) for key, item in sorted(safe.items(), key=lambda pair: str(pair[0]))}
    return safe


__all__ = [
    "LIBRARY_PROFILE_COMPARE_SCHEMA_VERSION",
    "ROUTE_MAP_SCHEMA_VERSION",
    "ROUTE_TRACE_SCHEMA_VERSION",
    "ROUTE_VALIDATION_SCHEMA_VERSION",
    "build_library_profile_compare",
    "build_library_route_map",
    "build_library_route_trace",
    "build_library_route_validation",
]
