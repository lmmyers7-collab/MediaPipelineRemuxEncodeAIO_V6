from __future__ import annotations

import logging
from typing import Mapping

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
    KEY_MOVIE_ROUTE_MAX_VIDEO_BITRATE_MBPS,
    KEY_OUTPUT_CONTAINER,
    KEY_ROUTING_PROFILE,
    KEY_SIZE_GUARD_MODE,
    KEY_TV_ROUTE_MAX_VIDEO_BITRATE_MBPS,
    KEY_VIDEO_CODEC,
    KEY_VIDEO_PRESET,
    KEY_VIDEO_QUALITY,
    KEY_WORKER_CONFIG_OVERRIDES,
)
from .json_policy import loads_strict_json


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
    KEY_MOVIE_ROUTE_MAX_VIDEO_BITRATE_MBPS,
    KEY_TV_ROUTE_MAX_VIDEO_BITRATE_MBPS,
    KEY_ALLOW_H264_REMUX_IF_PLEX_COMPATIBLE,
    KEY_H264_REMUX_MAX_BITRATE_MBPS,
    KEY_H264_REMUX_MAX_HEIGHT,
    KEY_SIZE_GUARD_MODE,
    KEY_MAX_ENCODE_GROWTH_PERCENT,
    KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
)


def snapshot_encode_config(config: Mapping[str, object], worker_name: str = "") -> dict[str, object]:
    snapshot = {key: config.get(key) for key in ENCODE_CONFIG_KEYS if key in config}
    worker = str(worker_name or "").casefold()
    if not worker:
        return snapshot

    raw_overrides = str(config.get(KEY_WORKER_CONFIG_OVERRIDES, "") or "").strip()
    if not raw_overrides:
        return snapshot
    try:
        overrides_map = loads_strict_json(raw_overrides)
    except Exception as exc:
        _log.warning("WorkerConfigOverrides JSON is invalid: %s", exc)
        return snapshot
    if not isinstance(overrides_map, dict):
        return snapshot

    for name_key, patch in overrides_map.items():
        if isinstance(patch, dict) and str(name_key).casefold() == worker:
            snapshot.update(patch)
            _log.debug("Applied config overrides for worker '%s': %s", worker_name, list(patch))
            break
    return snapshot
