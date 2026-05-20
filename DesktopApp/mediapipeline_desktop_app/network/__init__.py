"""
network
=======
Standalone / Coordinator / Worker distributed queue architecture.

Public API
----------
``get_dispatcher(app)``
    Factory that reads ``NetworkRole`` from the resolved config and returns
    the appropriate ``QueueDispatcher`` implementation.  Unknown or missing
    roles fall back to ``StandaloneDispatcher``.

``QueueDispatcher``, ``ClaimedJob``
    Re-exported for callers that need type annotations without importing
    the sub-module directly.

Phases
------
* Phase 0/1: Standalone and Coordinator modes are production-ready.
* Phase 2: Worker mode is production-ready as of this implementation.
* Phase 3: mDNS auto-discovery and per-worker config overrides — production-ready.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..config_keys import KEY_NETWORK_ROLE
from .dispatcher import ClaimedJob, QueueDispatcher
from .standalone import StandaloneDispatcher

if TYPE_CHECKING:
    from ..app import MediaPipelineApp

__all__ = ["get_dispatcher", "QueueDispatcher", "ClaimedJob", "StandaloneDispatcher"]

_log = logging.getLogger(__name__)


def get_dispatcher(app: "MediaPipelineApp") -> QueueDispatcher:
    """Return the correct ``QueueDispatcher`` for the configured network role.

    Role dispatch:
    - ``"standalone"`` (default) → ``StandaloneDispatcher`` (current behaviour)
    - ``"coordinator"``          → ``CoordinatorDispatcher`` (Phase 1)
    - ``"worker"``               → ``WorkerDispatcher`` (Phase 2)
    - any unknown value          → ``StandaloneDispatcher`` with a warning

    The factory always returns a working dispatcher so the app never crashes
    due to a misconfigured ``NetworkRole``.  ``ValueError`` from a worker
    missing its coordinator URL is re-raised so the user sees the message.
    """
    resolved = getattr(app, "resolved", None)
    config   = getattr(resolved, "config_data", {}) if resolved else {}
    role     = str(config.get(KEY_NETWORK_ROLE, "standalone")).strip().lower()

    if role == "standalone":
        return StandaloneDispatcher(app)

    if role == "coordinator":
        from .coordinator import CoordinatorDispatcher
        return CoordinatorDispatcher(app)

    if role == "worker":
        from .worker import WorkerDispatcher
        return WorkerDispatcher(app)

    _log.warning("Unknown NetworkRole %r — falling back to standalone.", role)
    return StandaloneDispatcher(app)
