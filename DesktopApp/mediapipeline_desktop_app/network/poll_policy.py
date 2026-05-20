from __future__ import annotations

import logging


_log = logging.getLogger(__name__)


def resolve_worker_poll_interval(raw_value: object, default_seconds: int = 30) -> int:
    """Coerce configured WorkerPollIntervalSecs to a bounded worker interval."""
    if raw_value is None or raw_value == "":
        return int(default_seconds)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        _log.warning("Invalid WorkerPollIntervalSecs %r; falling back to %d.", raw_value, default_seconds)
        return int(default_seconds)
    if value < 5:
        _log.warning("WorkerPollIntervalSecs %r is below 5; clamping to 5.", raw_value)
        return 5
    return value


def resolve_worker_wait_seconds(server_hint_seconds: int | None, poll_interval_seconds: int) -> float:
    """Clamp a coordinator retry hint to the worker poll interval."""
    if server_hint_seconds is None or server_hint_seconds <= 0:
        return float(poll_interval_seconds)
    return float(max(1, min(int(server_hint_seconds), int(poll_interval_seconds))))
