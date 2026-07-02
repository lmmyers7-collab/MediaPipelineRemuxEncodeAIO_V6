from __future__ import annotations

import logging
import threading
from collections.abc import Callable


def start_daemon_thread(
    *,
    name: str,
    target: Callable[[], None],
    log: logging.Logger,
    failure_message: str,
    on_failure: Callable[[Exception], None] | None = None,
) -> threading.Thread | None:
    """Start a daemon thread and log startup failures with caller context."""
    try:
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()
    except Exception as exc:
        log.warning("%s: %s", failure_message, exc)
        if on_failure is not None:
            try:
                on_failure(exc)
            except Exception as handler_exc:
                log.warning("%s failure handler failed: %s", failure_message, handler_exc)
        return None
    return thread
