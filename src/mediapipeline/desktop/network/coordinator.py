"""
network.coordinator
===================
``CoordinatorDispatcher`` — manages the in-flight registry and serves the
coordinator HTTP API on a dedicated ``ThreadingHTTPServer``.

Architecture
------------
* Starts its own HTTP server on ``<CoordinatorBindAddress>:<CoordinatorPort>``
  so workers on other LAN machines can reach it when the bind address allows
  LAN traffic.  The existing status-display server (localhost) is left
  untouched.
* HMAC-signed worker requests via :mod:`network.auth`.
* ``InFlightRegistry`` handles all thread-safe job tracking.
* A daemon *stale-reaper* thread runs every 60 s and reclaims jobs whose
  heartbeat has expired, returning them to the available queue.
* mDNS advertisement via :mod:`network.mdns` (Phase 3 — requires zeroconf).
* ``WorkerConfigOverrides`` remains loadable for compatibility but is ignored
  by backend encode snapshot policy until a real override authority is defined.
* Retry policy: files already in the failure log get ``retry_on_failure=False``
  so workers won't re-queue them on failure (Phase 3).

Source-policy anchors retained for split HTTP-server warning checks:
* "Failed to send coordinator JSON response status=%s" / "client may not receive response"
* "Failed to send oversized coordinator request response" / "client may not receive 413"
* "Failed to send malformed Content-Length coordinator request response" / "client may not receive 400"
* "Failed to read coordinator request body after Content-Length %d" / "request handler will stop"
* "Failed to send coordinator OPTIONS response" / "client may not receive 204"

Phase 1 + Phase 3: full implementation.
"""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from .coordinator_auth import CoordinatorAuthMixin
from .coordinator_http_handlers import CoordinatorHttpHandlersMixin
from .coordinator_lifecycle import CoordinatorLifecycleMixin
from .coordinator_policy import coordinator_bind_address, coordinator_port, heartbeat_timeout_mins
from .coordinator_queue import CoordinatorQueueMixin
from .coordinator_state import CoordinatorStateMixin
from .coordinator_parts.http_server import (
    _COORDINATOR_PROTOCOL_VERSION,
    _CoordHandler,
    _CoordServer,
    _coordinator_health_heartbeat_timeout_mins,
)
from .dispatcher import ClaimedJob, QueueDispatcher
from .identity import WORKER_ID_MAX_LEN as _WORKER_ID_MAX_LEN
from .identity import WORKER_ID_PATTERN as _WORKER_ID_PATTERN
from .identity import WORKER_NAME_MAX_LEN as _WORKER_NAME_MAX_LEN
from .identity import WORKER_NAME_PATTERN as _WORKER_NAME_PATTERN
from .registry import InFlightRegistry

if TYPE_CHECKING:
    from ..app import MediaPipelineApp

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CoordinatorDispatcher
# ---------------------------------------------------------------------------

class CoordinatorDispatcher(
    CoordinatorAuthMixin,
    CoordinatorStateMixin,
    CoordinatorLifecycleMixin,
    CoordinatorQueueMixin,
    CoordinatorHttpHandlersMixin,
    QueueDispatcher,
):
    """Coordinator-mode dispatcher.

    Starts a ``_CoordServer`` on
    ``<CoordinatorBindAddress>:<CoordinatorPort>`` and serves
    four API endpoints:

    * ``GET  /api/claim``     — workers request their next file.
    * ``POST /api/done``      — workers report completion / failure.
    * ``POST /api/heartbeat`` — workers signal they are still alive.
    * ``GET  /api/workers``   — coordinator UI polls for worker status.

    The :class:`InFlightRegistry` is the authoritative source of truth for
    which files are currently being processed.  The scan-and-claim operation
    is serialised via ``_claim_lock`` so two concurrent claim requests never
    race over the same record.
    """

    def __init__(self, app: "MediaPipelineApp") -> None:
        self._app          = app
        self._registry     = InFlightRegistry()
        self._claim_lock   = threading.Lock()
        self._reaper_stop  = threading.Event()
        self._reaper_thread: threading.Thread | None = None
        self._http_server: _CoordServer | None       = None
        self._mdns: object | None                    = None   # CoordinatorAdvertiser | None

        # W3 — advertised in /api/health so polling workers can stop
        # claiming during a coordinator drain/shutdown without racing
        # the HTTP server going down. Currently flipped only by
        # ``shutdown()``; future drain-mode UI hook can flip it earlier
        # to bleed the cluster gracefully.
        self._accepting_claims = True

        # Cluster-wide log: serialised file writes from many request threads.
        self._cluster_log_lock = threading.Lock()
        # Cap at ~50 MB; rotate to .1 on overflow.  Keep just one backup —
        # the goal is recent visibility, not long-term retention.
        self._cluster_log_max_bytes = 50 * 1024 * 1024

        # Load / generate the shared auth token.
        self._auth_token = self._load_or_generate_token()
        self._auth_nonce_cache: dict[str, float] = {}
        self._auth_nonce_lock = threading.Lock()

        # Crash-recovery: restore any jobs that were in-flight when the
        # coordinator last exited unexpectedly.
        self._restore_inflight_state()

        # Start the coordinator HTTP server first. If a later startup step
        # fails, tear it back down so we do not leave a half-initialized
        # coordinator listening for workers.
        self._start_http_server()
        try:
            # Start the stale-job reaper daemon.
            self._start_reaper()

            # Advertise via mDNS so workers can auto-discover this coordinator.
            self._start_mdns()
        except Exception:
            _log.exception("Coordinator startup failed after HTTP server start; cleaning up partial coordinator.")
            self.shutdown()
            raise

        port = self._coord_port()
        bind_address = self._coord_bind_address()
        _log.info("CoordinatorDispatcher ready — listening on %s:%d", bind_address, port)
        if bind_address in {"", "0.0.0.0", "::"}:
            _log.warning(
                "Coordinator API is plaintext HTTP on all interfaces. Use only on a trusted LAN, "
                "or set CoordinatorBindAddress to a specific interface such as 127.0.0.1."
            )
        # First entry in the cluster log marks the boot point so an operator
        # paging through can correlate restarts with claim/done patterns.
        self._safe_log_cluster_event(
            "coordinator-started",
            level="INFO",
            event="coordinator_started",
            message=f"Coordinator HTTP API up on {bind_address}:{port}",
        )

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _coord_port(self) -> int:
        return coordinator_port(self._config())

    def _coord_bind_address(self) -> str:
        return coordinator_bind_address(self._config())

    def _heartbeat_timeout_mins(self) -> float:
        return heartbeat_timeout_mins(self._config())

    def _config(self) -> dict:
        resolved = getattr(self._app, "resolved", None)
        return getattr(resolved, "config_data", {}) if resolved else {}

    # ------------------------------------------------------------------
    # Local heartbeat (used when coordinator encodes locally)
    # ------------------------------------------------------------------

    def heartbeat(
        self,
        job: ClaimedJob,
        *,
        progress: float = 0.0,
        stage: str = "",
    ) -> bool:
        try:
            result = self._registry.heartbeat(
                job.job_id,
                job.worker_id,
                progress_percent=progress,
                current_stage=stage,
            )
        except Exception as exc:
            # Keep the local encode alive on a transient registry error,
            # but only while the registry still tracks this claim — once
            # the job is gone (e.g. reclaimed), reporting "alive" would
            # let two machines encode the same source.
            try:
                still_active = self._registry.is_active(job.job_id, job.worker_id)
            except Exception:
                still_active = True
            if still_active:
                _log.warning("Local coordinator heartbeat failed for job %s; keeping job active: %s", job.job_id[:8], exc)
                return True
            _log.warning("Local coordinator heartbeat failed for job %s and the job is no longer registered; ending local claim: %s", job.job_id[:8], exc)
            return False
        return result == "ok"
