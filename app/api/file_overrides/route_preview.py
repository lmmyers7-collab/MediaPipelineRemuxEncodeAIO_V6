from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from app.config.constants import (
    ROUTE_THRESHOLD_MODE_NAMES,
    ROUTING_PROFILE_NAMES,
    SIZE_GUARD_MODE_NAMES,
)
from app.config.library_profiles import effective_library_profile_for_source_path
from app.config.metadata_choices import CONFIG_LIST_CHOICES
from app.queue.file_overrides import normalize_file_override_path
from mediapipeline_desktop_app.config_keys import (
    KEY_ENCODE_LADDER,
    KEY_ENCODE_TUNING_PRESET,
    KEY_OUTPUT_CONTAINER,
    KEY_REMUX_SAFE_VIDEO_CODECS,
    KEY_ROUTE_THRESHOLD_MODE,
    KEY_ROUTING_PROFILE,
    KEY_SIZE_GUARD_MODE,
    KEY_VIDEO_CODEC,
)

from .effective_fields import _profile_effective_route_settings
from .results import (
    _choice_error,
    _literal_choices,
    _mapping,
    _positive_int_value,
    _route_preview_base_payload,
    _route_preview_error,
)


ROUTE_FORCE_VALUES = {
    "auto":      "auto",
    "encode":    "transcode",
    "transcode": "transcode",
    "remux":     "remux",
}
ROUTE_PREVIEW_ROUTING_KEYS = frozenset(
    {
        "forceRoute",
        "route",
        "routingProfile",
        "routeThresholdMode",
        "sizeGuardMode",
        "maxVideoBitrateMbps",
        "maxResolutionHeight",
        "allowedVideoCodecs",
        "plexStrictMode",
        "reason",
    }
)
ROUTE_PREVIEW_VIDEO_KEYS = frozenset(
    {
        "codec",
        "videoCodec",
        "encodeTuningPreset",
        "encodePreset",
        "encodeLadder",
        "container",
        "outputContainer",
    }
)
ROUTE_PREVIEW_TOP_LEVEL_KEYS = frozenset({"routing", "video"})


def _normalize_route_name(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if not text:
        return "unknown"
    if "remux" in text:
        return "remux"
    if "transcode" in text or "encode" in text:
        return "transcode"
    return text


def _route_preview_source_key(value: Any) -> str:
    return normalize_file_override_path(value)


def _load_route_preview_snapshot_row(resolved: Any, source_path: str) -> tuple[dict[str, Any] | None, str]:
    snapshot_path = getattr(resolved, "queue_snapshot_path", None)
    if snapshot_path is None:
        return None, "Queue snapshot path is not configured; route preview is unavailable."
    path = Path(snapshot_path)
    if not path.exists():
        return None, f"Queue snapshot was not found: {path}"
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"Queue snapshot could not be read: {exc}"
    rows = snapshot.get("rows") if isinstance(snapshot, Mapping) else None
    if not isinstance(rows, list):
        return None, "Queue snapshot does not contain route preview rows."
    source_key = _route_preview_source_key(source_path)
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _route_preview_source_key(row.get("source_path")) == source_key:
            return dict(row), ""
    return None, "Source path is not present in the latest queue snapshot; refresh Queue before route preview."


def _route_video_requires_transcode(video: Mapping[str, Any]) -> bool:
    if any(key in video and video.get(key) not in (None, "") for key in ("codec", "encodeTuningPreset", "encodePreset", "encodeLadder")):
        return True
    container = str(video.get("container") or video.get("outputContainer") or "").strip().casefold()
    return container in {"mp4", "m4v", "mov"}


def _validate_route_preview_proposal(value: Any) -> tuple[dict[str, Any], list[str], list[dict[str, str]]]:
    if value in (None, ""):
        return {}, [], []
    if not isinstance(value, Mapping):
        return {}, ["'proposed_override' must be an object when provided."], []

    proposed = _mapping(value)
    errors: list[str] = []
    warnings: list[dict[str, str]] = []
    unknown_sections = sorted(str(key) for key in proposed.keys() if str(key) not in ROUTE_PREVIEW_TOP_LEVEL_KEYS)
    if unknown_sections:
        errors.append(
            "Unsupported proposed_override section(s): "
            f"{', '.join(unknown_sections)}. Allowed sections: {', '.join(sorted(ROUTE_PREVIEW_TOP_LEVEL_KEYS))}."
        )

    normalized: dict[str, Any] = {}
    routing = proposed.get("routing")
    if routing is not None:
        if not isinstance(routing, Mapping):
            errors.append("'proposed_override.routing' must be an object.")
        else:
            routing_map = _mapping(routing)
            unknown = sorted(str(key) for key in routing_map.keys() if str(key) not in ROUTE_PREVIEW_ROUTING_KEYS)
            if unknown:
                errors.append(
                    "Unsupported proposed_override.routing field(s): "
                    f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(ROUTE_PREVIEW_ROUTING_KEYS))}."
                )
            normalized_routing: dict[str, Any] = {}
            force_value = routing_map.get("forceRoute", routing_map.get("route"))
            if force_value not in (None, ""):
                force_text = str(force_value or "").strip().casefold()
                if force_text not in ROUTE_FORCE_VALUES:
                    errors.append("'routing.forceRoute' must be one of: auto, encode, remux, transcode.")
                else:
                    normalized_routing["forceRoute"] = ROUTE_FORCE_VALUES[force_text]
                    normalized_routing["forceRouteInput"] = force_text
            if "routingProfile" in routing_map:
                error = _choice_error("routing.routingProfile", routing_map.get("routingProfile"), ROUTING_PROFILE_NAMES)
                if error:
                    errors.append(error)
                else:
                    normalized_routing["routingProfile"] = str(routing_map.get("routingProfile")).strip().casefold()
            if "routeThresholdMode" in routing_map:
                error = _choice_error(
                    "routing.routeThresholdMode",
                    routing_map.get("routeThresholdMode"),
                    ROUTE_THRESHOLD_MODE_NAMES,
                )
                if error:
                    errors.append(error)
                else:
                    normalized_routing["routeThresholdMode"] = str(routing_map.get("routeThresholdMode")).strip().casefold()
            if "sizeGuardMode" in routing_map:
                error = _choice_error("routing.sizeGuardMode", routing_map.get("sizeGuardMode"), SIZE_GUARD_MODE_NAMES)
                if error:
                    errors.append(error)
                else:
                    normalized_routing["sizeGuardMode"] = str(routing_map.get("sizeGuardMode")).strip().casefold()
            if "maxVideoBitrateMbps" in routing_map:
                bitrate = _positive_int_value(
                    errors,
                    "routing.maxVideoBitrateMbps",
                    routing_map.get("maxVideoBitrateMbps"),
                    minimum=1,
                    maximum=500,
                )
                if bitrate is not None:
                    normalized_routing["maxVideoBitrateMbps"] = bitrate
            if "maxResolutionHeight" in routing_map:
                height = _positive_int_value(
                    errors,
                    "routing.maxResolutionHeight",
                    routing_map.get("maxResolutionHeight"),
                    minimum=1,
                    maximum=4320,
                )
                if height is not None:
                    normalized_routing["maxResolutionHeight"] = height
            if "allowedVideoCodecs" in routing_map:
                raw_codecs = routing_map.get("allowedVideoCodecs")
                allowed = {str(choice[0]).casefold() for choice in CONFIG_LIST_CHOICES.get(KEY_REMUX_SAFE_VIDEO_CODECS, ())}
                if not isinstance(raw_codecs, list) or not raw_codecs:
                    errors.append("'routing.allowedVideoCodecs' must be a non-empty list of codec strings.")
                else:
                    values: list[str] = []
                    for item in raw_codecs:
                        codec = str(item or "").strip().casefold()
                        if not codec or codec not in allowed:
                            errors.append(
                                "'routing.allowedVideoCodecs' entries must be one of: "
                                f"{', '.join(sorted(allowed))}."
                            )
                            break
                        values.append(codec)
                    if values:
                        normalized_routing["allowedVideoCodecs"] = values
            if "plexStrictMode" in routing_map:
                if not isinstance(routing_map.get("plexStrictMode"), bool):
                    errors.append("'routing.plexStrictMode' must be a boolean.")
                else:
                    normalized_routing["plexStrictMode"] = bool(routing_map.get("plexStrictMode"))
            if "reason" in routing_map:
                reason = str(routing_map.get("reason") or "").strip()
                if len(reason) > 240:
                    errors.append("'routing.reason' must be 240 characters or fewer.")
                elif reason:
                    normalized_routing["reason"] = reason
            if normalized_routing:
                normalized["routing"] = normalized_routing

    video = proposed.get("video")
    if video is not None:
        if not isinstance(video, Mapping):
            errors.append("'proposed_override.video' must be an object.")
        else:
            video_map = _mapping(video)
            unknown = sorted(str(key) for key in video_map.keys() if str(key) not in ROUTE_PREVIEW_VIDEO_KEYS)
            if unknown:
                errors.append(
                    "Unsupported proposed_override.video field(s): "
                    f"{', '.join(unknown)}. Allowed fields: {', '.join(sorted(ROUTE_PREVIEW_VIDEO_KEYS))}."
                )
            normalized_video: dict[str, Any] = {}
            codec_value = video_map.get("codec", video_map.get("videoCodec"))
            if codec_value not in (None, ""):
                error = _choice_error("video.codec", codec_value, _literal_choices(KEY_VIDEO_CODEC))
                if error:
                    errors.append(error)
                else:
                    normalized_video["codec"] = str(codec_value).strip().casefold()
            preset_value = video_map.get("encodeTuningPreset", video_map.get("encodePreset"))
            if preset_value not in (None, ""):
                error = _choice_error("video.encodeTuningPreset", preset_value, _literal_choices(KEY_ENCODE_TUNING_PRESET))
                if error:
                    errors.append(error)
                else:
                    normalized_video["encodeTuningPreset"] = str(preset_value).strip().casefold()
            if "encodeLadder" in video_map:
                error = _choice_error("video.encodeLadder", video_map.get("encodeLadder"), _literal_choices(KEY_ENCODE_LADDER))
                if error:
                    errors.append(error)
                else:
                    normalized_video["encodeLadder"] = str(video_map.get("encodeLadder")).strip().casefold()
            container_value = video_map.get("container", video_map.get("outputContainer"))
            if container_value not in (None, ""):
                error = _choice_error("video.container", container_value, _literal_choices(KEY_OUTPUT_CONTAINER))
                if error:
                    errors.append(error)
                else:
                    normalized_video["container"] = str(container_value).strip().casefold()
            if normalized_video:
                normalized["video"] = normalized_video

    normalized_routing = _mapping(normalized.get("routing"))
    normalized_video = _mapping(normalized.get("video"))
    if normalized_routing.get("forceRoute") == "remux" and _route_video_requires_transcode(normalized_video):
        errors.append(
            "'routing.forceRoute' remux cannot be combined with video encode/container fields "
            "that require transcode."
        )
    if normalized.get("video") and not _mapping(normalized.get("routing")).get("forceRoute"):
        warnings.append({
            "field":   "video",
            "message": "Video encode/container settings may force transcode during processing.",
        })
    return normalized, errors, warnings


def _route_preview_settings_value(settings: Mapping[str, Any], key: str, default: str = "") -> str:
    return str(settings.get(key) or default).strip()


def _route_preview_current_payload(
    row: Mapping[str, Any],
    settings: Mapping[str, Any],
    settings_source: str,
) -> dict[str, Any]:
    route = _normalize_route_name(row.get("route") or row.get("route_name"))
    configured_video_codec = _route_preview_settings_value(settings, KEY_VIDEO_CODEC)
    return {
        "route":             route,
        "routeRaw":          str(row.get("route") or row.get("route_name") or "").strip(),
        "routeReason":       str(row.get("route_reason") or "").strip(),
        "routeReasonCode":   str(row.get("route_reason_code") or "").strip(),
        "videoCodec":        "copy" if route == "remux" else configured_video_codec,
        "configuredVideoCodec": configured_video_codec,
        "container":         _route_preview_settings_value(settings, KEY_OUTPUT_CONTAINER),
        "routingProfile":    _route_preview_settings_value(settings, KEY_ROUTING_PROFILE),
        "routeThresholdMode": _route_preview_settings_value(settings, KEY_ROUTE_THRESHOLD_MODE),
        "sizeGuardMode":     _route_preview_settings_value(settings, KEY_SIZE_GUARD_MODE),
        "source":            "queue_snapshot",
        "settingsSource":    settings_source,
    }


def _route_preview_proposed_payload(
    current: Mapping[str, Any],
    proposed_override: Mapping[str, Any],
) -> dict[str, Any]:
    routing = _mapping(proposed_override.get("routing"))
    video = _mapping(proposed_override.get("video"))
    force_route = str(routing.get("forceRoute") or "").strip()
    video_requires_transcode = _route_video_requires_transcode(video)
    if force_route and force_route != "auto":
        route = force_route
    elif video_requires_transcode:
        route = "transcode"
    else:
        route = str(current.get("route") or "unknown")
    source = "proposed_file_override" if (force_route and force_route != "auto") or video_requires_transcode else str(current.get("source") or "queue_snapshot")
    if force_route and force_route != "auto":
        decision_source = "forced_route_preview"
    elif video_requires_transcode:
        decision_source = "proposed_file_override"
    else:
        decision_source = "current_queue_snapshot"
    codec = "copy" if route == "remux" else str(video.get("codec") or current.get("configuredVideoCodec") or current.get("videoCodec") or "")
    return {
        "route":             route,
        "videoCodec":        codec,
        "container":         str(video.get("container") or current.get("container") or ""),
        "routingProfile":    str(routing.get("routingProfile") or current.get("routingProfile") or ""),
        "routeThresholdMode": str(routing.get("routeThresholdMode") or current.get("routeThresholdMode") or ""),
        "sizeGuardMode":     str(routing.get("sizeGuardMode") or current.get("sizeGuardMode") or ""),
        "source":            source,
        "decisionSource":    decision_source,
    }


def _route_preview_impact(
    current: Mapping[str, Any],
    proposed: Mapping[str, Any],
    proposed_override: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    current_route = str(current.get("route") or "unknown")
    proposed_route = str(proposed.get("route") or "unknown")
    routing = _mapping(proposed_override.get("routing"))
    video = _mapping(proposed_override.get("video"))
    force_route = str(routing.get("forceRoute") or "").strip()
    video_requires_transcode = _route_video_requires_transcode(video)

    will_force_transcode = force_route == "transcode" or video_requires_transcode or (current_route != "transcode" and proposed_route == "transcode")
    will_prevent_remux = current_route == "remux" and proposed_route == "transcode"
    forced_remux_change = force_route == "remux" and current_route != "remux"

    if will_force_transcode:
        warnings.append({
            "field":   "video" if video_requires_transcode and force_route != "transcode" else "routing.forceRoute",
            "message": "This route preview would force a full video transcode for this file.",
        })
    if forced_remux_change:
        warnings.append({
            "field":   "routing.forceRoute",
            "message": "Forced remux cannot be proven safe by this advisory endpoint without the processing route helper accepting proposed file overrides.",
        })
    if video and proposed_route == "remux":
        warnings.append({
            "field":   "video",
            "message": "Video encode settings do not apply while the proposed route is remux.",
        })
    non_force_routing = any(key != "forceRoute" and key != "forceRouteInput" for key in routing)
    if non_force_routing:
        warnings.append({
            "field":   "routing",
            "message": "Non-forcing routing fields are validated, but full route recomputation for proposed per-file overrides is not available yet.",
        })

    if will_force_transcode:
        risk = "high"
    elif forced_remux_change:
        risk = "high"
    elif force_route == "remux" and current_route == "remux" and not video:
        risk = "low"
    elif force_route or video or non_force_routing:
        risk = "medium"
    else:
        risk = "low"

    return {
        "will_force_transcode":   will_force_transcode,
        "will_prevent_remux":     will_prevent_remux,
        "estimated_risk":         risk,
        "requires_confirmation":  risk in {"medium", "high"},
        "route_decision_helper":  "queue_snapshot_current_route",
        "full_recompute":         False,
        "advisory_only":          True,
    }, warnings


def _file_override_route_preview_payload(
    *,
    resolved: Any,
    source_path: str,
    proposed_override: Mapping[str, Any],
) -> dict[str, Any]:
    row, route_error = _load_route_preview_snapshot_row(resolved, source_path)
    if row is None:
        return _route_preview_error(
            "Route preview unavailable.",
            [
                route_error,
                "Stage 5 route override UI cannot proceed safely until a queue snapshot row provides backend route evidence for this path.",
            ],
        )

    config = getattr(resolved, "config_data", {}) or {}
    config_map = config if isinstance(config, Mapping) else {}
    profile = effective_library_profile_for_source_path(config_map, source_path)
    library_effective_settings, settings_source = _profile_effective_route_settings(profile, config_map)
    current = _route_preview_current_payload(row, library_effective_settings, settings_source)
    proposed = _route_preview_proposed_payload(current, proposed_override)
    impact, impact_warnings = _route_preview_impact(current, proposed, proposed_override)
    warnings = list(impact_warnings)
    if impact.get("advisory_only"):
        warnings.append({
            "field":   "route_preview",
            "message": "Preview uses current queue snapshot route evidence and does not write or process media.",
        })
    payload = _route_preview_base_payload(
        ok=True,
        severity="ok",
        message=f"Route impact preview for: {source_path}",
    )
    payload.update({
        "path":                       source_path,
        "normalized_path":            normalize_file_override_path(source_path),
        "current":                    current,
        "proposed":                   proposed,
        "impact":                     impact,
        "warnings":                   warnings,
        "errors":                     [],
        "accepted_fields": {
            "routing": sorted(ROUTE_PREVIEW_ROUTING_KEYS),
            "video":   sorted(ROUTE_PREVIEW_VIDEO_KEYS),
        },
    })
    return payload
