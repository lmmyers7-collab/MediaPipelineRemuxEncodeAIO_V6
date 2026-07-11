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
__all__ = (
    "_compare_value",
    "_path_key",
    "_value_missing",
    "_number",
    "_bool",
    "_text",
    "_first_text",
    "_first_present",
    "_bounded_row",
    "_base_payload",
    "_state_by_library_id",
    "_route_profile_row",
    "_profile_identity",
    "_designation",
    "_path_evidence",
    "_path_summary",
    "_profile_route_fields",
    "_route_field_row",
    "_setting_evidence",
    "_field",
    "_field_applies_to_designation",
    "_profile_route_status",
    "_profile_nodes",
    "_profile_edges",
    "_navigation_actions",
    "_navigation_target",
    "_navigation_selector",
    "_decision_matrix_rows",
    "_route_boundaries",
    "_boundary_height",
    "_height_rule",
    "_target_fields_for_designation",
    "_profile_summary_lines",
    "_library_only_effective_settings",
    "_route_map_warnings",
)
