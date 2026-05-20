from __future__ import annotations

import logging
import math
from typing import Mapping

from ..config_keys import (
    KEY_COORDINATOR_BIND_ADDRESS,
    KEY_COORDINATOR_HEARTBEAT_TIMEOUT_MINS,
    KEY_COORDINATOR_PORT,
)


_log = logging.getLogger(__name__)

DEFAULT_COORDINATOR_PORT = 7830
DEFAULT_COORDINATOR_BIND_ADDRESS = "0.0.0.0"
DEFAULT_HEARTBEAT_TIMEOUT_MINS = 5.0
RETRY_AFTER_ACTIVE_SECONDS = 5
RETRY_AFTER_IDLE_SECONDS = 30


def coordinator_port(config: Mapping[str, object]) -> int:
    raw = config.get(KEY_COORDINATOR_PORT, DEFAULT_COORDINATOR_PORT)
    try:
        port = int(str(raw or "").strip() or DEFAULT_COORDINATOR_PORT)
    except (TypeError, ValueError):
        _log.warning("Invalid CoordinatorPort %r; falling back to %d.", raw, DEFAULT_COORDINATOR_PORT)
        return DEFAULT_COORDINATOR_PORT
    if port < 1 or port > 65535:
        _log.warning("CoordinatorPort %r is outside 1..65535; falling back to %d.", raw, DEFAULT_COORDINATOR_PORT)
        return DEFAULT_COORDINATOR_PORT
    return port


def coordinator_bind_address(config: Mapping[str, object]) -> str:
    value = str(config.get(KEY_COORDINATOR_BIND_ADDRESS, DEFAULT_COORDINATOR_BIND_ADDRESS) or DEFAULT_COORDINATOR_BIND_ADDRESS).strip()
    if not value:
        return DEFAULT_COORDINATOR_BIND_ADDRESS
    if "://" in value or "/" in value or "\\" in value:
        _log.warning("Invalid CoordinatorBindAddress %r; falling back to %s.", value, DEFAULT_COORDINATOR_BIND_ADDRESS)
        return DEFAULT_COORDINATOR_BIND_ADDRESS
    return value


def heartbeat_timeout_mins(config: Mapping[str, object]) -> float:
    raw = config.get(KEY_COORDINATOR_HEARTBEAT_TIMEOUT_MINS, DEFAULT_HEARTBEAT_TIMEOUT_MINS)
    try:
        timeout = float(str(raw or "").strip() or DEFAULT_HEARTBEAT_TIMEOUT_MINS)
    except (TypeError, ValueError):
        _log.warning(
            "Invalid CoordinatorHeartbeatTimeoutMins %r; falling back to %.1f.",
            raw,
            DEFAULT_HEARTBEAT_TIMEOUT_MINS,
        )
        return DEFAULT_HEARTBEAT_TIMEOUT_MINS
    if not math.isfinite(timeout) or timeout <= 0:
        _log.warning(
            "CoordinatorHeartbeatTimeoutMins %r must be finite and positive; falling back to %.1f.",
            raw,
            DEFAULT_HEARTBEAT_TIMEOUT_MINS,
        )
        return DEFAULT_HEARTBEAT_TIMEOUT_MINS
    return timeout


def compute_retry_after_seconds(active_count: object) -> int:
    try:
        return RETRY_AFTER_ACTIVE_SECONDS if int(active_count) > 0 else RETRY_AFTER_IDLE_SECONDS
    except Exception as exc:
        _log.warning(
            "Invalid active_count %r for retry hint; falling back to %d seconds: %s",
            active_count,
            RETRY_AFTER_IDLE_SECONDS,
            exc,
        )
        return RETRY_AFTER_IDLE_SECONDS
