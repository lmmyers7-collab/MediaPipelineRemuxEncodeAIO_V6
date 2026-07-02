from __future__ import annotations

import logging
from collections.abc import Mapping

from ..config_keys import (
    KEY_ALLOW_H264_REMUX_IF_PLEX_COMPATIBLE,
    KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
    KEY_ENCODE_LADDER,
    KEY_ENCODE_TUNING_PRESET,
    KEY_EXTRA_VIDEO_FLAGS,
    KEY_FALLBACK_CPU_QUALITY,
    KEY_H264_REMUX_MAX_BITRATE_MBPS,
    KEY_H264_REMUX_MAX_HEIGHT,
    KEY_MAX_ENCODE_GROWTH_PERCENT,
    KEY_OUTPUT_CONTAINER,
    KEY_ROUTE_1080P_MAX_VIDEO_BITRATE_MBPS,
    KEY_ROUTE_THRESHOLD_MODE,
    KEY_ROUTING_PROFILE,
    KEY_SIZE_GUARD_MODE,
    KEY_VIDEO_CODEC,
    KEY_VIDEO_PRESET,
    KEY_VIDEO_QUALITY,
    KEY_WORKER_CONFIG_OVERRIDES,
)
from .processing_policy import COORDINATOR_PROCESSING_POLICY_KEY, build_coordinator_processing_policy


_log = logging.getLogger(__name__)

ENCODE_CONFIG_KEYS = (
    KEY_VIDEO_CODEC,
    KEY_VIDEO_PRESET,
    KEY_VIDEO_QUALITY,
    KEY_OUTPUT_CONTAINER,
    KEY_ENCODE_TUNING_PRESET,
    KEY_ENCODE_LADDER,
    KEY_EXTRA_VIDEO_FLAGS,
    KEY_FALLBACK_CPU_QUALITY,
    KEY_ROUTING_PROFILE,
    KEY_ROUTE_THRESHOLD_MODE,
    KEY_ROUTE_1080P_MAX_VIDEO_BITRATE_MBPS,
    KEY_ALLOW_H264_REMUX_IF_PLEX_COMPATIBLE,
    KEY_H264_REMUX_MAX_BITRATE_MBPS,
    KEY_H264_REMUX_MAX_HEIGHT,
    KEY_SIZE_GUARD_MODE,
    KEY_MAX_ENCODE_GROWTH_PERCENT,
    KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
)


def snapshot_encode_config(
    config: Mapping[str, object],
    worker_name: str = "",
    record: object | None = None,
) -> dict[str, object]:
    snapshot = {key: config.get(key) for key in ENCODE_CONFIG_KEYS if key in config}
    if record is not None:
        snapshot[COORDINATOR_PROCESSING_POLICY_KEY] = build_coordinator_processing_policy(config, record)
    worker = str(worker_name or "").casefold()
    if not worker:
        return snapshot

    raw_overrides = str(config.get(KEY_WORKER_CONFIG_OVERRIDES, "") or "").strip()
    if not raw_overrides:
        return snapshot
    _log.warning(
        "WorkerConfigOverrides is disabled by backend policy; ignoring overrides for worker '%s'.",
        worker_name,
    )
    return snapshot
