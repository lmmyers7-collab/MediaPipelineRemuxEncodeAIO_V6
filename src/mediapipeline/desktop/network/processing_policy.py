from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mediapipeline.core.config.file_io import atomic_write_text
from mediapipeline.core.config.library_profile_defaults import default_library_settings
from mediapipeline.core.config.library_profile_state import (
    effective_library_profile_for_source_path,
)
from mediapipeline.core.config.load import serialize_psd1_document
from mediapipeline.core.kernel.models import ResolvedPaths

from ..config_keys import (
    KEY_ALLOW_H264_REMUX_IF_PLEX_COMPATIBLE,
    KEY_ALLOW_NO_AUDIO,
    KEY_AUDIO_DOWNMIX_MODE,
    KEY_AUDIO_MAX_CHANNELS,
    KEY_AUDIO_PASSTHROUGH_PROFILE,
    KEY_AUDIO_TRANSCODE_AUTO_BITRATE_BY_CHANNELS,
    KEY_AUDIO_TRANSCODE_BITRATE,
    KEY_AUDIO_TRANSCODE_CODEC,
    KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
    KEY_COMPATIBLE_AUDIO_CODECS,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_CONVERT_TX3G_TO_SRT,
    KEY_CONVERT_VOBSUB_TO_SRT,
    KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS,
    KEY_DROP_ASS_AFTER_CONVERSION,
    KEY_DROP_BDPGS_AFTER_CONVERSION,
    KEY_DROP_TX3G_AFTER_CONVERSION,
    KEY_DROP_VOBSUB_AFTER_CONVERSION,
    KEY_ENCODE_LADDER,
    KEY_ENCODE_TUNING_PRESET,
    KEY_EXCLUDE_SUBTITLE_STYLES,
    KEY_H264_REMUX_MAX_BITRATE_MBPS,
    KEY_H264_REMUX_MAX_HEIGHT,
    KEY_INCLUDE_SUBTITLE_STYLES,
    KEY_KEEP_SIGNS_AND_SONGS,
    KEY_MAX_ENCODE_GROWTH_PERCENT,
    KEY_MERGE_ADJACENT,
    KEY_MERGE_THRESHOLD_MS,
    KEY_OUTPUT_CONTAINER,
    KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES,
    KEY_REMOVE_KARAOKE,
    KEY_REMUX_SAFE_VIDEO_CODECS,
    KEY_ROUTE_1080P_MAX_VIDEO_BITRATE_MBPS,
    KEY_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    KEY_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT,
    KEY_ROUTE_1440P_MAX_VIDEO_BITRATE_MBPS,
    KEY_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    KEY_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT,
    KEY_ROUTE_4K_MAX_VIDEO_BITRATE_MBPS,
    KEY_ROUTE_THRESHOLD_MODE,
    KEY_ROUTING_PROFILE,
    KEY_SIZE_GUARD_MODE,
    KEY_STRIP_FORMATTING,
    KEY_SUB_KEEP_LANGUAGES,
    KEY_SUB_SDH_TITLE_KEYWORDS,
    KEY_SUB_SUPPLEMENTAL_KEYWORDS,
    KEY_TREAT_ASS_SIGNS_SONGS_AS_FORCED,
    KEY_TREAT_BDPGS_SIGNS_SONGS_AS_FORCED,
    KEY_TREAT_TX3G_SIGNS_SONGS_AS_FORCED,
    KEY_TREAT_VOBSUB_SIGNS_SONGS_AS_FORCED,
    KEY_TX3G_EXTRACT_LANGUAGES,
    KEY_TX3G_PRESERVE_EXISTING_SRT,
    KEY_TX3G_TREAT_FORCED_AS_SEPARATE,
    KEY_VIDEO_CODEC,
    KEY_VIDEO_QUALITY,
    KEY_WORKER_ENCODER_MAP,
    KEY_WORKER_HONOR_COORDINATOR_POLICY,
)
from .json_policy import loads_strict_json


_log = logging.getLogger(__name__)

COORDINATOR_PROCESSING_POLICY_KEY = "__coordinator_policy"
COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION = "network_coordinator_processing_policy.v1"
WORKER_EFFECTIVE_CONFIG_SCHEMA_VERSION = "network_worker_effective_config.v1"

CODEC_FAMILY_BY_ENCODER = {
    "libx265": "hevc",
    "hevc_nvenc": "hevc",
    "hevc_qsv": "hevc",
    "hevc_amf": "hevc",
    "libx264": "h264",
    "h264_nvenc": "h264",
    "h264_qsv": "h264",
    "h264_amf": "h264",
    "libaom-av1": "av1",
    "av1_nvenc": "av1",
    "av1_qsv": "av1",
    "av1_amf": "av1",
}
CPU_ENCODER_BY_FAMILY = {
    "hevc": "libx265",
    "h264": "libx264",
    "av1": "libaom-av1",
}
KNOWN_WORKER_ENCODERS = frozenset(CODEC_FAMILY_BY_ENCODER)
QUALITY_TIERS = ("very_high", "high", "standard", "compact")
CPU_QUALITY_BY_TIER = {
    "very_high": 18,
    "high": 20,
    "standard": 22,
    "compact": 26,
}
HARDWARE_QUALITY_BY_TIER = {
    "very_high": 17,
    "high": 19,
    "standard": 21,
    "compact": 25,
}
ROUTE_THRESHOLD_KEYS = (
    KEY_ROUTE_THRESHOLD_MODE,
    KEY_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    KEY_ROUTE_1080P_MAX_VIDEO_BITRATE_MBPS,
    KEY_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT,
    KEY_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    KEY_ROUTE_1440P_MAX_VIDEO_BITRATE_MBPS,
    KEY_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT,
    KEY_ROUTE_4K_MAX_VIDEO_BITRATE_MBPS,
)
SIZE_GUARD_KEYS = (
    KEY_SIZE_GUARD_MODE,
    KEY_MAX_ENCODE_GROWTH_PERCENT,
    KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
)
VIDEO_POLICY_KEYS = (
    KEY_ENCODE_TUNING_PRESET,
    KEY_ENCODE_LADDER,
    KEY_ALLOW_H264_REMUX_IF_PLEX_COMPATIBLE,
    KEY_H264_REMUX_MAX_BITRATE_MBPS,
    KEY_H264_REMUX_MAX_HEIGHT,
    KEY_REMUX_SAFE_VIDEO_CODECS,
)
AUDIO_POLICY_KEYS = (
    KEY_AUDIO_PASSTHROUGH_PROFILE,
    KEY_COMPATIBLE_AUDIO_CODECS,
    KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES,
    KEY_AUDIO_TRANSCODE_CODEC,
    KEY_AUDIO_TRANSCODE_BITRATE,
    KEY_AUDIO_TRANSCODE_AUTO_BITRATE_BY_CHANNELS,
    KEY_AUDIO_DOWNMIX_MODE,
    KEY_AUDIO_MAX_CHANNELS,
    KEY_ALLOW_NO_AUDIO,
)
SUBTITLE_POLICY_KEYS = (
    KEY_SUB_KEEP_LANGUAGES,
    KEY_CONVERT_TX3G_TO_SRT,
    KEY_DROP_TX3G_AFTER_CONVERSION,
    KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS,
    KEY_TX3G_EXTRACT_LANGUAGES,
    KEY_TX3G_PRESERVE_EXISTING_SRT,
    KEY_TX3G_TREAT_FORCED_AS_SEPARATE,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_DROP_BDPGS_AFTER_CONVERSION,
    KEY_CONVERT_VOBSUB_TO_SRT,
    KEY_DROP_VOBSUB_AFTER_CONVERSION,
    KEY_DROP_ASS_AFTER_CONVERSION,
    KEY_STRIP_FORMATTING,
    KEY_REMOVE_KARAOKE,
    KEY_MERGE_ADJACENT,
    KEY_MERGE_THRESHOLD_MS,
    KEY_KEEP_SIGNS_AND_SONGS,
    KEY_TREAT_ASS_SIGNS_SONGS_AS_FORCED,
    KEY_TREAT_TX3G_SIGNS_SONGS_AS_FORCED,
    KEY_TREAT_BDPGS_SIGNS_SONGS_AS_FORCED,
    KEY_TREAT_VOBSUB_SIGNS_SONGS_AS_FORCED,
    KEY_SUB_SDH_TITLE_KEYWORDS,
    KEY_SUB_SUPPLEMENTAL_KEYWORDS,
    KEY_EXCLUDE_SUBTITLE_STYLES,
    KEY_INCLUDE_SUBTITLE_STYLES,
)


def _jsonable_mapping(values: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: values[key] for key in keys if key in values}


def _fingerprint_text(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def codec_family_from_encoder(encoder: object) -> str:
    text = str(encoder or "").strip().casefold()
    return CODEC_FAMILY_BY_ENCODER.get(text, "")


def quality_tier_from_video_quality(value: object) -> str:
    try:
        quality = int(str(value or "").strip())
    except (TypeError, ValueError):
        return "standard"
    if quality <= 18:
        return "very_high"
    if quality <= 21:
        return "high"
    if quality <= 24:
        return "standard"
    return "compact"


def _quality_value_for_encoder(encoder: str, tier: str) -> int:
    normalized_tier = tier if tier in QUALITY_TIERS else "standard"
    encoder_text = str(encoder or "").strip().casefold()
    if encoder_text.startswith("lib"):
        return CPU_QUALITY_BY_TIER[normalized_tier]
    return HARDWARE_QUALITY_BY_TIER[normalized_tier]


def _effective_settings_for_record(config: Mapping[str, Any], record: object) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    source_path = str(getattr(record, "source_path", "") or "")
    profile = effective_library_profile_for_source_path(config, source_path) if source_path else None
    if profile:
        settings = profile.get("effective_settings")
        if isinstance(settings, Mapping):
            return {
                "editor": dict(settings.get("editor", {}) or {}),
                "video": dict(settings.get("video", {}) or {}),
                "subtitles": dict(settings.get("subtitles", {}) or {}),
                "audio": dict(settings.get("audio", {}) or {}),
            }, dict(profile)
    return default_library_settings(config), None


def build_coordinator_processing_policy(config: Mapping[str, Any], record: object) -> dict[str, Any]:
    config_map = dict(config or {})
    settings, profile = _effective_settings_for_record(config_map, record)
    editor = dict(settings.get("editor", {}) or {})
    video = dict(settings.get("video", {}) or {})
    audio = dict(settings.get("audio", {}) or {})
    subtitles = dict(settings.get("subtitles", {}) or {})
    literal_encoder = str(editor.get(KEY_VIDEO_CODEC) or config_map.get(KEY_VIDEO_CODEC) or "").strip()
    family = codec_family_from_encoder(literal_encoder) or "hevc"
    quality_tier = quality_tier_from_video_quality(video.get(KEY_VIDEO_QUALITY) or config_map.get(KEY_VIDEO_QUALITY))
    library_id = str(getattr(record, "library_id", "") or (profile or {}).get("library_id") or (profile or {}).get("id") or "").strip()
    relative_path = str(getattr(record, "relative_path", "") or "").strip()
    return {
        "policy_schema_version": COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION,
        "policy_authority": "coordinator",
        "library_id": library_id,
        "relative_path": relative_path,
        "target_codec_family": family,
        "quality_tier": quality_tier,
        "output_container": editor.get(KEY_OUTPUT_CONTAINER) or config_map.get(KEY_OUTPUT_CONTAINER),
        "routing_profile": editor.get(KEY_ROUTING_PROFILE) or config_map.get(KEY_ROUTING_PROFILE),
        "route_thresholds": _jsonable_mapping(editor, ROUTE_THRESHOLD_KEYS),
        "size_guards": _jsonable_mapping(editor, SIZE_GUARD_KEYS),
        "video_policy": _jsonable_mapping({**editor, **video}, VIDEO_POLICY_KEYS),
        "audio_policy": _jsonable_mapping(audio, AUDIO_POLICY_KEYS),
        "subtitle_policy": _jsonable_mapping(subtitles, SUBTITLE_POLICY_KEYS),
    }


def claim_processing_policy(encode_config: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = encode_config.get(COORDINATOR_PROCESSING_POLICY_KEY)
    if not isinstance(raw, Mapping):
        return None
    policy = dict(raw)
    if policy.get("policy_schema_version") != COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION:
        return None
    return policy


def worker_honor_coordinator_policy_enabled(config: Mapping[str, Any]) -> bool:
    raw = config.get(KEY_WORKER_HONOR_COORDINATOR_POLICY, False)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().casefold() in {"1", "true", "yes", "on"}


def parse_worker_encoder_map(raw: object) -> dict[str, str]:
    if isinstance(raw, Mapping):
        payload = raw
    else:
        text = str(raw or "").strip()
        if not text:
            payload = {}
        else:
            parsed = loads_strict_json(text)
            if not isinstance(parsed, Mapping):
                raise ValueError("WorkerEncoderMap must be a JSON object.")
            payload = parsed
    result: dict[str, str] = {}
    for key, value in payload.items():
        family = str(key or "").strip().casefold()
        encoder = str(value or "").strip().casefold()
        if family in {"hevc", "h264", "av1"} and encoder:
            result[family] = encoder
    return result


def worker_encoder_map_descriptor(raw: object) -> dict[str, Any]:
    """Return token-safe WorkerEncoderMap drift evidence."""
    try:
        encoder_map = parse_worker_encoder_map(raw)
    except Exception as exc:
        text = str(raw or "").strip()
        return {
            "worker_encoder_map_entries": 0,
            "worker_encoder_map_fingerprint": _fingerprint_text(text),
            "worker_encoder_map_valid": False,
            "worker_encoder_map_error": str(exc)[:200],
        }
    if not encoder_map and not str(raw or "").strip():
        return {
            "worker_encoder_map_entries": 0,
            "worker_encoder_map_fingerprint": "",
            "worker_encoder_map_valid": True,
            "worker_encoder_map_error": "",
        }
    material = json.dumps(encoder_map, sort_keys=True, separators=(",", ":"))
    return {
        "worker_encoder_map_entries": len(encoder_map),
        "worker_encoder_map_fingerprint": _fingerprint_text(material),
        "worker_encoder_map_valid": True,
        "worker_encoder_map_error": "",
    }


def _cpu_fallback_for_family(family: str) -> str:
    return CPU_ENCODER_BY_FAMILY.get(family, "libx265")


def resolve_worker_encoder(config: Mapping[str, Any], family: str) -> tuple[str, str]:
    target_family = str(family or "").strip().casefold()
    fallback = _cpu_fallback_for_family(target_family)
    try:
        encoder_map = parse_worker_encoder_map(config.get(KEY_WORKER_ENCODER_MAP, ""))
    except Exception as exc:
        _log.warning("WorkerEncoderMap could not be parsed; falling back to CPU encoder %s: %s", fallback, exc)
        return fallback, "cpu_fallback"
    encoder = encoder_map.get(target_family, "").strip().casefold()
    if not encoder:
        return fallback, "cpu_fallback"
    if encoder not in KNOWN_WORKER_ENCODERS or codec_family_from_encoder(encoder) != target_family:
        _log.warning(
            "WorkerEncoderMap entry for family %s uses unsupported encoder %r; falling back to CPU encoder %s.",
            target_family,
            encoder,
            fallback,
        )
        return fallback, "cpu_fallback"
    return encoder, "worker_encoder_map"


def _overlay_mapping(target: dict[str, Any], values: Any) -> None:
    if isinstance(values, Mapping):
        target.update({str(key): value for key, value in values.items()})


def build_worker_effective_config(
    worker_config: Mapping[str, Any],
    claim_encode_config: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    effective = dict(worker_config or {})
    policy = claim_processing_policy(claim_encode_config)
    if not policy:
        return effective, {"status": "not_available"}
    family = str(policy.get("target_codec_family") or "hevc").strip().casefold()
    encoder, encoder_source = resolve_worker_encoder(effective, family)
    tier = str(policy.get("quality_tier") or "standard").strip().casefold()

    if policy.get("output_container"):
        effective[KEY_OUTPUT_CONTAINER] = policy["output_container"]
    if policy.get("routing_profile"):
        effective[KEY_ROUTING_PROFILE] = policy["routing_profile"]
    _overlay_mapping(effective, policy.get("route_thresholds"))
    _overlay_mapping(effective, policy.get("size_guards"))
    _overlay_mapping(effective, policy.get("video_policy"))
    _overlay_mapping(effective, policy.get("audio_policy"))
    _overlay_mapping(effective, policy.get("subtitle_policy"))
    effective[KEY_VIDEO_CODEC] = encoder
    effective[KEY_VIDEO_QUALITY] = _quality_value_for_encoder(encoder, tier)
    effective[KEY_WORKER_HONOR_COORDINATOR_POLICY] = bool(
        worker_honor_coordinator_policy_enabled(effective)
    )
    return effective, {
        "schema_version": WORKER_EFFECTIVE_CONFIG_SCHEMA_VERSION,
        "status": "applied",
        "target_codec_family": family,
        "local_encoder": encoder,
        "encoder_source": encoder_source,
        "quality_tier": tier if tier in QUALITY_TIERS else "standard",
        "quality_value": effective[KEY_VIDEO_QUALITY],
    }


def _safe_job_id(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text[:80] or "network-job"


def materialize_worker_effective_config(
    resolved: ResolvedPaths,
    *,
    job: object,
) -> tuple[ResolvedPaths, dict[str, Any]]:
    worker_config = dict(getattr(resolved, "config_data", {}) or {})
    if not worker_honor_coordinator_policy_enabled(worker_config):
        return resolved, {"status": "disabled"}
    claim_encode_config = getattr(job, "encode_config", {}) or {}
    effective, evidence = build_worker_effective_config(worker_config, claim_encode_config)
    if evidence.get("status") != "applied":
        return resolved, evidence
    state_root = Path(resolved.state_root or resolved.local_base or resolved.config_path.parent)
    config_dir = state_root / "NetworkWorkerEffectiveConfigs"
    config_path = config_dir / f"{_safe_job_id(getattr(job, 'job_id', ''))}.psd1"
    atomic_write_text(config_path, serialize_psd1_document(effective))
    return replace(resolved, config_path=config_path, config_data=effective), {
        **evidence,
        "config_path": str(config_path),
    }


__all__ = [
    "COORDINATOR_PROCESSING_POLICY_KEY",
    "COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION",
    "WORKER_EFFECTIVE_CONFIG_SCHEMA_VERSION",
    "build_coordinator_processing_policy",
    "build_worker_effective_config",
    "claim_processing_policy",
    "codec_family_from_encoder",
    "materialize_worker_effective_config",
    "parse_worker_encoder_map",
    "quality_tier_from_video_quality",
    "resolve_worker_encoder",
    "worker_encoder_map_descriptor",
    "worker_honor_coordinator_policy_enabled",
]
