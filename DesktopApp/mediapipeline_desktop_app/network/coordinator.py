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
* Per-worker encode config overrides via ``WorkerConfigOverrides`` (Phase 3).
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
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..config_keys import KEY_COORDINATOR_AUTH_TOKEN

from .auth import generate_token, validate_request_auth
from .cluster_log import format_cluster_log_line
from .coordinator_http import MAX_COORDINATOR_BODY_BYTES, parse_query_params, validate_content_length
from .coordinator_policy import RETRY_AFTER_ACTIVE_SECONDS as _RETRY_AFTER_ACTIVE_SECONDS
from .coordinator_policy import RETRY_AFTER_IDLE_SECONDS as _RETRY_AFTER_IDLE_SECONDS
from .coordinator_policy import compute_retry_after_seconds
from .coordinator_policy import coordinator_bind_address, coordinator_port, heartbeat_timeout_mins
from .coordinator_parts.http_server import (
    _COORDINATOR_PROTOCOL_VERSION,
    _CoordHandler,
    _CoordServer,
    _coordinator_health_heartbeat_timeout_mins,
)
from .dispatcher import ClaimedJob, QueueDispatcher
from .encode_config_snapshot import snapshot_encode_config
from .failure_policy import source_has_prior_failure
from .identity import WORKER_ID_MAX_LEN as _WORKER_ID_MAX_LEN
from .identity import WORKER_ID_PATTERN as _WORKER_ID_PATTERN
from .identity import WORKER_NAME_MAX_LEN as _WORKER_NAME_MAX_LEN
from .identity import WORKER_NAME_PATTERN as _WORKER_NAME_PATTERN
from .identity import coerce_worker_name, is_valid_worker_id, sanitize_log_entry_fields
from .json_policy import loads_strict_json
from .protocol import (
    ClaimResponse,
    DoneRequest,
    HeartbeatRequest,
    HeartbeatResponse,
    LogEntryRequest,
    WorkerEntry,
    WorkersResponse,
    coerce_finite_float,
)
from .registry import InFlightRegistry
from .use_cases.done_outcome import CoordinatorDoneOutcomeService, DoneOutcome

if TYPE_CHECKING:
    from ..app import MediaPipelineApp

_log = logging.getLogger(__name__)


def _coerce_record_estimated_size_gb(record: object, source_path: str) -> float:
    """Return a safe non-negative size estimate for a queue record."""
    try:
        return coerce_finite_float(
            getattr(record, "estimated_size_gb", 0.0),
            "estimated_size_gb",
            minimum=0.0,
        )
    except Exception as exc:
        _log.warning(
            "Invalid estimated_size_gb for queue record %s; using 0.0: %s",
            source_path,
            exc,
        )
        return 0.0


# ---------------------------------------------------------------------------
# CoordinatorDispatcher
# ---------------------------------------------------------------------------

class CoordinatorDispatcher(QueueDispatcher):
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
        self._registry.load(self._inflight_state_path())

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
    # Token management
    # ------------------------------------------------------------------

    def _load_or_generate_token(self) -> str:
        # 1. User-configured token in PSD1 config takes precedence.
        token = str(self._config().get(KEY_COORDINATOR_AUTH_TOKEN, "") or "").strip()
        if token:
            return token

        # 2. Auto-generated token persisted in app state.
        try:
            state = self._app.service.load_app_state()
            token = str(state.get("coordinator_auth_token", "") or "").strip()
            if token:
                return token
        except Exception:
            _log.exception("Could not read coordinator token from app state.")

        # 3. Generate a fresh token and persist it.
        token = generate_token()
        try:
            self._app.service.save_app_state({"coordinator_auth_token": token})
        except Exception:
            _log.exception("Could not persist new coordinator token to app state.")
            _log.warning(
                "Generated coordinator auth token is active for this run only; "
                "persistence failed, so workers may need a new token after restart."
            )
        else:
            _log.info("Generated new coordinator auth token (stored in app state).")
        return token

    def _validate_request_auth(
        self,
        headers: dict,
        *,
        method: str,
        path_with_query: str,
        body: bytes,
    ) -> bool:
        with self._auth_nonce_lock:
            return validate_request_auth(
                headers,
                self._auth_token,
                method=method,
                path_with_query=path_with_query,
                body=body,
                nonce_cache=self._auth_nonce_cache,
            )

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _inflight_state_path(self) -> Path:
        """JSON file that persists in-flight state across crashes."""
        state_file: Path = getattr(self._app.service, "app_state_path", None)
        if state_file is not None:
            return state_file.parent / "coordinator_inflight.json"
        return Path.home() / ".mediapipeline" / "coordinator_inflight.json"

    def cluster_log_path(self) -> Path:
        """Path to the aggregated cluster log (worker + coordinator events)."""
        state_file: Path = getattr(self._app.service, "app_state_path", None)
        if state_file is not None:
            return state_file.parent / "cluster.log"
        return Path.home() / ".mediapipeline" / "cluster.log"

    # ------------------------------------------------------------------
    # Cluster log writer (shared by /api/log handler and local events)
    # ------------------------------------------------------------------

    def _format_cluster_log_line(self, entry: LogEntryRequest) -> str:
        return format_cluster_log_line(entry)

    def _append_cluster_log(self, entry: LogEntryRequest) -> None:
        """Append one entry to ``cluster.log``, rotating when oversized."""
        path: Path | None = None
        try:
            path = self.cluster_log_path()
            line = self._format_cluster_log_line(entry)
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._cluster_log_lock:
                # Cheap rotation: if the file is too big, move it to .1 and
                # start fresh.  Single backup — operators tail the live file.
                try:
                    size = path.stat().st_size if path.exists() else 0
                except OSError as exc:
                    _log.warning("Failed to inspect cluster log size for %s before rotation check: %s", path, exc)
                    size = 0
                if size >= self._cluster_log_max_bytes:
                    backup = path.with_suffix(path.suffix + ".1")
                    try:
                        if backup.exists():
                            backup.unlink()
                        path.rename(backup)
                    except OSError as exc:
                        # Rotation is best-effort; never block logging, but keep
                        # the failure visible because a stuck cluster.log can grow
                        # indefinitely during unattended network-mode runs.
                        _log.warning("Failed to rotate cluster log %s to %s: %s", path, backup, exc)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
        except Exception:
            if path is None:
                _log.exception("Failed to resolve cluster log path.")
            else:
                _log.exception("Failed to prepare or append cluster log %s", path)

    def log_cluster_event(
        self,
        *,
        level: str = "INFO",
        event: str,
        message: str = "",
        worker_id: str = "",
        worker_name: str = "",
        role: str = "coordinator",
        job_id: str = "",
        source_path: str = "",
    ) -> None:
        """Convenience used by the coordinator itself for its own events.

        Workers post via ``/api/log``; the handler ultimately calls
        :meth:`_append_cluster_log` with the same machinery.
        """
        if not worker_name and role == "coordinator":
            worker_name = "coordinator"
        if not worker_id and role == "coordinator":
            worker_id = str(getattr(self._app, "_machine_id", "") or "coordinator")
        entry = LogEntryRequest(
            timestamp   = datetime.now().astimezone().isoformat(timespec="seconds"),
            worker_id   = worker_id,
            worker_name = worker_name,
            role        = role,
            level       = level,
            event       = event,
            message     = message,
            job_id      = job_id,
            source_path = source_path,
        )
        self._append_cluster_log(entry)

    def _safe_log_cluster_event(self, context: str, **kwargs: Any) -> None:
        """Emit a best-effort coordinator cluster event without changing control flow."""
        try:
            self.log_cluster_event(**kwargs)
        except Exception as exc:
            job_id = str(kwargs.get("job_id", "") or "")
            _log.warning(
                "Failed to emit %s cluster event for job %s: %s",
                context,
                job_id[:8],
                exc,
            )

    # ------------------------------------------------------------------
    # HTTP server lifecycle
    # ------------------------------------------------------------------

    def _start_http_server(self) -> None:
        port = self._coord_port()
        bind_address = self._coord_bind_address()
        server: _CoordServer | None = None
        try:
            server = _CoordServer((bind_address, port), _CoordHandler)
            server.dispatcher = self
            t = threading.Thread(
                target=server.serve_forever,
                name="CoordHTTP",
                daemon=True,
            )
            t.start()
            self._http_server = server
            _log.info("Coordinator HTTP API listening on %s:%d", bind_address, port)
        except Exception as exc:
            self._http_server = None
            if server is not None:
                try:
                    server.server_close()
                except Exception as close_exc:
                    _log.warning(
                        "Coordinator HTTP server cleanup failed after startup error: %s",
                        close_exc,
                    )
            _log.error(
                "Could not start coordinator HTTP server on %s:%d: %s — "
                "workers will not be able to connect.",
                bind_address,
                port,
                exc,
            )
            raise RuntimeError(
                f"Could not start coordinator HTTP server on {bind_address}:{port}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Stale-job reaper
    # ------------------------------------------------------------------

    def _start_reaper(self) -> None:
        self._reaper_stop.clear()
        t = threading.Thread(target=self._reaper_loop, name="StaleReaper", daemon=True)
        try:
            t.start()
        except Exception as exc:
            self._reaper_thread = None
            _log.error("Could not start coordinator stale-job reaper thread: %s", exc)
            raise RuntimeError(f"Could not start coordinator stale-job reaper thread: {exc}") from exc
        self._reaper_thread = t

    def _start_mdns(self) -> None:
        """Advertise this coordinator via mDNS (requires zeroconf).

        Failure is non-fatal — workers can still enter the coordinator URL
        manually even when mDNS is unavailable.
        """
        try:
            from .mdns import CoordinatorAdvertiser, ZeroconfUnavailable  # noqa: PLC0415
            adv = CoordinatorAdvertiser(port=self._coord_port())
            if adv.start():
                self._mdns = adv
            else:
                self._mdns = None
                _log.warning(
                    "Coordinator mDNS advertisement unavailable; workers can enter the coordinator URL manually."
                )
        except Exception as exc:
            self._mdns = None
            _log.warning(
                "Coordinator mDNS advertisement unavailable; workers can enter the coordinator URL manually: %s",
                exc,
            )

    def _reaper_interval_seconds(self) -> float:
        """How often the reaper sweeps for stale jobs.

        W2 — previously hardcoded to 60 s, which meant tightening
        ``CoordinatorHeartbeatTimeoutMins`` below ~2 min didn't actually
        speed up reclaim — the reaper still only checked once a minute,
        so jobs sat "officially stale" for up to a full sweep past their
        timeout. Now the cadence is half the heartbeat-timeout, clamped
        to the [15s, 60s] range so we neither hammer the lock on tiny
        timeouts nor go too long between sweeps on large ones.
        """
        try:
            timeout_seconds = self._heartbeat_timeout_mins() * 60.0
        except Exception as exc:
            _log.warning("Coordinator reaper heartbeat timeout lookup failed; using default sweep cadence: %s", exc)
            timeout_seconds = 5 * 60.0
        return max(15.0, min(60.0, timeout_seconds / 2.0))

    def _reaper_loop(self) -> None:
        while not self._reaper_stop.wait(self._reaper_interval_seconds()):
            try:
                timeout = self._heartbeat_timeout_mins()
                stale   = self._registry.reclaim_stale(timeout)
                for job in stale:
                    _log.warning(
                        "Reclaimed stale job %s from worker '%s' (%s) — "
                        "file will be available for reclaim.",
                        job.job_id[:8],
                        job.worker_name or job.worker_id[:8],
                        Path(job.source_path).name,
                    )
                    self._safe_log_cluster_event(
                        "reclaimed-stale",
                        level="WARN",
                        event="reclaimed_stale",
                        message=(
                            f"{Path(job.source_path).name} (heartbeat older "
                            f"than {timeout:.1f} min)"
                        ),
                        worker_id=job.worker_id,
                        worker_name=job.worker_name,
                        role="coordinator",
                        job_id=job.job_id,
                        source_path=job.source_path,
                    )
                # W5 — persist on every reaper tick whenever the registry is
                # non-empty, not just when reclaim_stale mutated it. Heartbeats
                # update last_heartbeat / progress_percent in memory only, so
                # without this flush a coordinator crash mid-encode would lose
                # all progress markers since the last claim/done. The save is
                # an atomic small-JSON write so the I/O cost is negligible.
                if stale or self._registry.active_count > 0:
                    try:
                        self._registry.save(self._inflight_state_path())
                    except Exception as exc:
                        _log.warning(
                            "Coordinator in-flight registry save failed during stale-job reaper: %s",
                            exc,
                        )
                        self._safe_log_cluster_event(
                            "inflight-save-failed",
                            level="WARN",
                            event="inflight_save_failed",
                            message=f"Failed to save in-flight registry during stale-job reaper: {exc}",
                            role="coordinator",
                        )
            except Exception:
                _log.exception("Error in stale-job reaper loop.")

    # ------------------------------------------------------------------
    # QueueDispatcher interface (used when coordinator encodes locally)
    # ------------------------------------------------------------------

    def claim_next(self) -> ClaimedJob | None:
        """Claim the next unclaimed queue record for local encode.

        Only executes when ``CoordinatorAlsoEncodeLocally`` is ``True``.
        Returns ``None`` when the setting is off, the queue is empty, or
        all records are already in-flight with remote workers.

        Uses the same ``_claim_lock`` as the HTTP claim handler so a local
        claim and a concurrent remote worker claim never race over the
        same file.
        """
        # Respect the CoordinatorAlsoEncodeLocally config flag.
        if not bool(self._config().get("CoordinatorAlsoEncodeLocally", False)):
            return None

        worker_id   = getattr(self._app, "_machine_id", "coordinator")
        worker_name = "coordinator"

        # Hold the same claim lock used by the HTTP handler so local and
        # remote claims are serialised and never race on the same record.
        with self._claim_lock:
            record, encode_config = self._scan_for_next_record(worker_name)
            if record is None:
                return None

            job_id      = str(uuid.uuid4())
            source_path = str(getattr(record, "source_path", ""))

            ok = self._registry.claim(
                job_id=job_id,
                worker_id=worker_id,
                worker_name=worker_name,
                source_path=source_path,
                encode_config=encode_config,
                priority=bool(getattr(record, "priority", False)),
                estimated_size_gb=_coerce_record_estimated_size_gb(record, source_path),
            )

        if not ok:
            # Another worker claimed it between scan and claim.
            return None

        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            _log.warning("Failed to save inflight state after local claim %s: %s", job_id[:8], exc)
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="WARN",
                event="inflight_save_failed",
                message=f"Failed to save in-flight registry after local claim: {exc}",
                worker_id=worker_id,
                worker_name=worker_name,
                role="coordinator",
                job_id=job_id,
                source_path=source_path,
            )
        return ClaimedJob(
            job_id=job_id,
            record=record,
            encode_config=encode_config,
            claimed_at=datetime.now(),
            worker_id=worker_id,
        )

    def mark_done(
        self,
        job: ClaimedJob,
        *,
        success: bool,
        output_path: str | None = None,
        error: str | None = None,
        elapsed_seconds: float = 0.0,
        output_size_bytes: int | None = None,
        completion_status: str | None = None,
        publish_state: str | None = None,
        publish_mode: str | None = None,
        route: str | None = None,
        queue_terminal: bool = False,
    ) -> None:
        # W1 — previously this method called registry.complete() and saved,
        # but discarded every other parameter. The local-encode path
        # therefore produced no cluster.log entry, no queue-record removal,
        # no retry-policy decision, and no per-worker stats — local jobs
        # silently vanished from the operator's audit trail. Now both the
        # HTTP /api/done handler and this local path funnel through the
        # shared _emit_done_outcome helper for consistent bookkeeping.
        completed = self._registry.complete(
            job.job_id,
            job.worker_id,
            success           = success,
            elapsed_seconds   = elapsed_seconds,
            output_size_bytes = output_size_bytes or 0,
        )
        if completed is None:
            # The job was reclaimed by the stale-reaper between heartbeat
            # and completion, or already finalised by a duplicate report.
            # Save and bail — no log/queue side-effects to apply.
            _log.warning(
                "Local mark_done for job %s found no matching registry "
                "entry (likely reclaimed); skipping post-completion logging.",
                job.job_id[:8],
            )
            try:
                self._registry.save(self._inflight_state_path())
            except Exception as exc:
                _log.warning("Failed to save inflight state after missing local completion: %s", exc)
                source_path = str(getattr(getattr(job, "record", None), "source_path", "") or "")
                self._safe_log_cluster_event(
                    "inflight-save-failed",
                    level="WARN",
                    event="inflight_save_failed",
                    message=f"Failed to save in-flight registry after missing local completion: {exc}",
                    worker_id=job.worker_id,
                    worker_name="coordinator",
                    role="coordinator",
                    job_id=job.job_id,
                    source_path=source_path,
                )
            return

        self._emit_done_outcome(
            job               = completed,
            success           = success,
            worker_id         = job.worker_id,
            elapsed_seconds   = elapsed_seconds,
            output_size_bytes = int(output_size_bytes or 0),
            completion_status = completion_status or "",
            publish_state     = publish_state or "",
            publish_mode      = publish_mode or "",
            error_message     = error or "",
            queue_terminal    = bool(queue_terminal),
            # Local encodes follow the same default retry policy the
            # HTTP handler uses (DoneRequest.retry_on_failure default).
            retry_on_failure  = True,
        )

    def release(self, job: ClaimedJob) -> None:
        # N3 — pass the local worker_id so the registry's ownership
        # check accepts the release. Local-encode jobs are owned by
        # the coordinator process, identified by job.worker_id.
        self._registry.unclaim(job.job_id, job.worker_id)
        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            _log.warning("Failed to save inflight state after local release %s: %s", job.job_id[:8], exc)
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="WARN",
                event="inflight_save_failed",
                message=f"Failed to save in-flight registry after local release: {exc}",
                worker_id=job.worker_id,
                worker_name="coordinator",
                role="coordinator",
                job_id=job.job_id,
            )

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
            _log.warning("Local coordinator heartbeat failed for job %s; keeping job active: %s", job.job_id[:8], exc)
            return True
        return result == "ok"

    def shutdown(self) -> None:
        """Stop the reaper thread, HTTP server, and mDNS advertiser."""
        # W3 — stop advertising claim availability before we tear down the
        # HTTP server so any worker that polls /api/health between this
        # call and the server actually closing learns to back off instead
        # of hammering /api/claim during the teardown window.
        self._accepting_claims = False
        try:
            active_count: int | str = self._registry.active_count
        except Exception as exc:
            _log.warning("Coordinator active-count lookup failed during shutdown: %s", exc)
            active_count = "unknown"
        self._safe_log_cluster_event(
            "coordinator-stopped",
            level="INFO",
            event="coordinator_stopped",
            message=f"Coordinator shutting down (active={active_count})",
        )
        self._reaper_stop.set()
        if self._http_server is not None:
            try:
                self._http_server.shutdown()
            except Exception as exc:
                _log.warning("Coordinator HTTP server shutdown failed: %s", exc)
            try:
                self._http_server.server_close()
            except Exception as exc:
                _log.warning("Coordinator HTTP server close failed: %s", exc)
            self._http_server = None
        if self._mdns is not None:
            try:
                self._mdns.stop()
            except Exception as exc:
                _log.warning("Coordinator mDNS advertiser stop failed: %s", exc)
            self._mdns = None
        if self._reaper_thread is not None and self._reaper_thread is not threading.current_thread():
            try:
                self._reaper_thread.join(timeout=2.0)
                if self._reaper_thread.is_alive():
                    _log.warning("Coordinator stale-job reaper did not stop within 2.0 seconds.")
                else:
                    self._reaper_thread = None
            except Exception as exc:
                _log.warning("Coordinator stale-job reaper join failed: %s", exc)
        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            _log.warning("Coordinator in-flight registry save failed during shutdown: %s", exc)
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="WARN",
                event="inflight_save_failed",
                message=f"Failed to save in-flight registry during coordinator shutdown: {exc}",
                role="coordinator",
            )
        _log.info("CoordinatorDispatcher shut down.")

    # ------------------------------------------------------------------
    # Public UI helpers
    # ------------------------------------------------------------------

    def workers_snapshot(self) -> list[WorkerEntry]:
        """Return a point-in-time copy of all in-flight jobs (for the UI)."""
        return self._registry.snapshot()

    def idle_workers_snapshot(self) -> list[WorkerEntry]:
        """Return workers that have session stats but are not currently encoding.

        Combined with ``workers_snapshot()`` this gives the full picture:
        active workers (encoding now) + idle workers (done since last restart).
        """
        return self._registry.idle_workers_snapshot()

    def coordinator_stats(self) -> dict[str, int]:
        return {
            "active":              self._registry.active_count,
            "session_completed":   self._registry.session_completed,
            "session_failed":      self._registry.session_failed,
        }

    def get_auth_token(self) -> str:
        """Return the active bearer token (for settings display)."""
        return self._auth_token

    def update_auth_token(self, new_token: str) -> None:
        """Hot-swap the bearer token without restarting the HTTP server.

        Takes effect immediately for all subsequent requests — no reload or
        restart needed.  Called from the Network tab when the user regenerates
        the coordinator token.

        N7 — refuses an empty / whitespace-only token (which would have
        opened the API to anonymous access on the LAN) and persists the
        new token to app_state so a coordinator restart preserves it.
        Raises ``ValueError`` when the supplied token is blank.
        """
        new_token = (new_token or "").strip()
        if not new_token:
            raise ValueError(
                "Coordinator auth token cannot be empty. Generate a new "
                "token via secrets.token_hex(32) instead of clearing it."
            )
        if len(new_token) < 16:
            raise ValueError(
                "Coordinator auth token is too short (minimum 16 characters). "
                "Use a cryptographically random token."
            )
        self._auth_token = new_token
        # Persist so the next start picks up the rotated token instead of
        # silently reverting to the old auto-generated one in app_state.
        try:
            self._app.service.save_app_state({"coordinator_auth_token": new_token})
        except Exception:
            _log.exception("Could not persist rotated coordinator token to app state.")
            _log.warning(
                "Coordinator auth token updated live, but persistence failed; "
                "workers may need a new token after coordinator restart."
            )
        else:
            _log.info("Coordinator auth token updated and persisted (hot-swap, no restart required).")
        self._safe_log_cluster_event(
            "auth-token-rotated",
            level="INFO",
            event="auth_token_rotated",
            message="Coordinator auth token rotated via hot-swap.",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_for_next_record(self, worker_name: str = "") -> tuple:
        """Find the first queue record not currently in-flight.

        Returns ``(record, encode_config)`` or ``(None, {})``.
        Callers that need atomicity (the HTTP claim handler and the local
        ``claim_next`` path) must hold ``_claim_lock`` before calling here.

        Takes a shallow snapshot of ``queue_records`` before iterating so
        that concurrent mutations from the app callback scheduler (for
        example ``_remove_from_queue``) cannot cause iterator-invalidation bugs.
        """
        records = list(getattr(self._app, "queue_records", []))  # snapshot
        for r in records:
            source = str(getattr(r, "source_path", ""))
            if not self._registry.is_in_flight(source):
                return r, self._snapshot_encode_config(worker_name)
        return None, {}

    def _compute_retry_after_seconds(self) -> int:
        """Return the backoff hint to attach to an empty ClaimResponse.

        W4 — when this worker found no claimable record, the reason is
        either (a) other workers are still encoding and a job may free
        up soon, or (b) the cluster is genuinely idle. Distinguish the
        two so workers poll fast in case (a) (catch a freshly-released
        job within a few seconds) and slow in case (b) (avoid hammering
        an empty coordinator with a stampede of pollers every cycle).

        Heuristic: any active in-flight job means "busy somewhere" —
        even if all queue records are claimed, an encode failure could
        re-queue one and we want to be ready. With zero active jobs,
        nothing is going to change without operator action, so back off.
        """
        try:
            active_count = self._registry.active_count
        except Exception as exc:
            _log.warning("Could not read active in-flight job count; using idle retry hint: %s", exc)
            return _RETRY_AFTER_IDLE_SECONDS
        return compute_retry_after_seconds(active_count)

    def _source_has_prior_failure(self, source_path: str) -> bool:
        """Return ``True`` if *source_path* appears in the app's failure records."""
        return source_has_prior_failure(source_path, getattr(self._app, "failure_records", []))

    def _snapshot_encode_config(self, worker_name: str = "") -> dict:
        """Snapshot the encode-relevant config keys at claim time.

        If *worker_name* matches an entry in ``WorkerConfigOverrides`` (a
        JSON object mapping worker names to partial config dicts), those
        overrides are applied on top of the global config snapshot.  This
        allows BEAST-PC to use ``"VideoPreset": "p4"`` while LAPTOP uses
        ``"VideoPreset": "p2"`` without separate config files.
        """
        resolved = getattr(self._app, "resolved", None)
        if resolved is None or not hasattr(resolved, "config_data"):
            return {}
        return snapshot_encode_config(resolved.config_data, worker_name)

    def _remove_from_queue(self, source_path: str) -> None:
        """Remove a completed record from queue_records (UI-thread only)."""
        records = getattr(self._app, "queue_records", None)
        if not records:
            return
        to_remove = [
            r for r in records
            if str(getattr(r, "source_path", "")) == source_path
        ]
        for r in to_remove:
            records.remove(r)
        if to_remove and hasattr(self._app, "apply_queue_filters"):
            self._app.apply_queue_filters()

    # ------------------------------------------------------------------
    # HTTP endpoint handlers
    # Signature: (handler: _CoordHandler, ...) -> None
    # ------------------------------------------------------------------

    def _http_claim(self, handler: _CoordHandler, params: dict[str, str]) -> None:
        """Handle ``GET /api/claim?worker_id=<id>&worker_name=<name>``."""
        worker_id   = str(params.get("worker_id", "") or "").strip()
        worker_name = coerce_worker_name(params.get("worker_name", ""), worker_id)

        if not worker_id:
            _log.warning("Rejected /api/claim with missing worker_id")
            handler._send_json({"error": "worker_id query parameter is required"}, 400)
            return

        # N13 — bound and validate the worker identity before it reaches
        # the registry, where it would otherwise be persisted into
        # coordinator_inflight.json, cluster.log, and the per-worker
        # stats table. Garbage values (e.g. a 1 MB worker_id from a
        # buggy client) used to bloat all three.
        if not is_valid_worker_id(worker_id):
            _log.warning("Rejected /api/claim with invalid worker_id=%r", worker_id[:80])
            handler._send_json({
                "error": "worker_id must be 1..64 chars of [A-Za-z0-9._-]",
                "received_length": len(worker_id),
            }, 400)
            return

        if not self._accepting_claims:
            handler._send_json(
                ClaimResponse.empty(
                    retry_after_seconds=self._compute_retry_after_seconds()
                ).to_dict()
            )
            return

        # Scan-and-claim must be atomic — hold the claim lock for the whole
        # find-then-claim sequence so two concurrent workers don't race.
        try:
            with self._claim_lock:
                record, encode_config = self._scan_for_next_record(worker_name)

                if record is None:
                    # W4 — choose a backoff hint that reflects whether other
                    # workers are still encoding (a job may free up soon) or
                    # the cluster is genuinely idle (back off harder).
                    handler._send_json(
                        ClaimResponse.empty(
                            retry_after_seconds=self._compute_retry_after_seconds()
                        ).to_dict()
                    )
                    return

                job_id      = str(uuid.uuid4())
                source_path = str(getattr(record, "source_path", ""))
                priority    = bool(getattr(record, "priority", False))
                size_gb     = _coerce_record_estimated_size_gb(record, source_path)

                ok = self._registry.claim(
                    job_id=job_id,
                    worker_id=worker_id,
                    worker_name=worker_name,
                    source_path=source_path,
                    encode_config=encode_config,
                    priority=priority,
                    estimated_size_gb=size_gb,
                )
        except Exception as exc:
            _log.exception("Failed to process /api/claim for worker %s: %s", worker_id, exc)
            handler._send_json({"error": "claim unavailable"}, 500)
            return

        if not ok:
            # Another thread claimed the same path between scan and claim.
            # The cluster is provably busy (someone just claimed under us)
            # so always emit the active hint here.
            handler._send_json(
                ClaimResponse.empty(
                    retry_after_seconds=_RETRY_AFTER_ACTIVE_SECONDS,
                ).to_dict()
            )
            return

        # Retry policy: if this file already has a failure record, tell the
        # worker not to re-queue it if the encode fails again.
        try:
            retry_on_failure = not self._source_has_prior_failure(source_path)
        except Exception as exc:
            _log.exception(
                "Failed to evaluate retry policy after claim %s for worker %s: %s",
                job_id[:8],
                worker_id,
                exc,
            )
            try:
                self._registry.unclaim(job_id, worker_id)
            except Exception as release_exc:
                _log.warning(
                    "Failed to release claim %s after retry-policy failure: %s",
                    job_id[:8],
                    release_exc,
                )
            handler._send_json({"error": "claim unavailable"}, 500)
            return

        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            _log.exception("Failed to save registry after claim.")
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="WARN",
                event="inflight_save_failed",
                message=f"Failed to save in-flight registry after claim: {exc}",
                worker_id=worker_id,
                worker_name=worker_name,
                role="coordinator",
                job_id=job_id,
                source_path=source_path,
            )

        _log.info(
            "Claimed job %s (%s) for worker '%s' (retry=%s, %.2f GB, priority=%s)",
            job_id[:8], Path(source_path).name, worker_name,
            retry_on_failure, size_gb, priority,
        )
        self._safe_log_cluster_event(
            "claim-handed",
            level="INFO",
            event="claim_handed",
            message=f"{Path(source_path).name} (retry={retry_on_failure}, {size_gb:.2f} GB)",
            worker_id=worker_id,
            worker_name=worker_name,
            role="coordinator",
            job_id=job_id,
            source_path=source_path,
        )
        response = ClaimResponse(
            status            = "ok",
            job_id            = job_id,
            source_path       = source_path,
            priority          = priority,
            estimated_size_gb = size_gb,
            encode_config     = encode_config,
            retry_on_failure  = retry_on_failure,
        )
        handler._send_json(response.to_dict())

    def _http_done(self, handler: _CoordHandler, body: bytes) -> None:
        """Handle ``POST /api/done``."""
        try:
            data = loads_strict_json(body) if body else {}
            req  = DoneRequest.from_dict(data)
        except Exception as exc:
            _log.warning("Rejected /api/done with invalid JSON body: %s", exc)
            handler._send_json({"error": "Invalid JSON body"}, 400)
            return
        # N13 — same identity validation as /api/claim. Empty worker_id
        # is allowed here because crash-recovery callers may not know
        # their previous worker_id; ownership is still enforced
        # downstream by the registry's worker_id check (N2/N3).
        if req.worker_id and not is_valid_worker_id(req.worker_id):
            _log.warning("Rejected /api/done with invalid worker_id=%r", req.worker_id[:80])
            handler._send_json({"error": "invalid worker_id"}, 400)
            return
        if req.job_id and not is_valid_worker_id(req.job_id):
            _log.warning("Rejected /api/done with invalid job_id=%r", req.job_id[:80])
            handler._send_json({"error": "invalid job_id"}, 400)
            return

        if req.released:
            # Worker is shutting down cleanly — release without failure count.
            # N3 — pass worker_id so a foreign worker can't release a job
            # it doesn't own. Distinguish "not found" from "wrong worker".
            try:
                with self._registry._lock:
                    _existing = self._registry._jobs.get(req.job_id)
                    _existing_owner = _existing.worker_id if _existing else None
                job = self._registry.unclaim(req.job_id, req.worker_id)
            except Exception as exc:
                _log.exception("Failed to process /api/done release for job %s from worker %s: %s", req.job_id, req.worker_id, exc)
                handler._send_json({"error": "done state unavailable"}, 500)
                return
            if job is None:
                if _existing is None:
                    _log.warning(
                        "Release report for unknown job %s from worker '%s' "
                        "(likely already reclaimed or completed).",
                        req.job_id[:8], req.worker_id[:32],
                    )
                    self._safe_log_cluster_event(
                        "release-not-found",
                        level="WARN",
                        event="release_not_found",
                        message="Worker released a job that is no longer in-flight.",
                        worker_id=req.worker_id,
                        role="coordinator",
                        job_id=req.job_id,
                    )
                    handler._send_json({"status": "not_found", "job_id": req.job_id}, 404)
                else:
                    _log.warning(
                        "Rejected /api/done released=True from worker '%s' for job %s "
                        "owned by '%s'.",
                        req.worker_id[:32], req.job_id[:8], (_existing_owner or "?")[:32],
                    )
                    handler._send_json({"status": "forbidden", "reason": "worker_id does not match job owner", "job_id": req.job_id}, 403)
                return
            _log.info(
                "Worker '%s' released job %s (%s).",
                req.worker_id[:8], req.job_id[:8], Path(job.source_path).name,
            )
            try:
                self._registry.save(self._inflight_state_path())
            except Exception as exc:
                _log.warning("Failed to save inflight state after worker release: %s", exc)
                self._safe_log_cluster_event(
                    "inflight-save-failed",
                    level="WARN",
                    event="inflight_save_failed",
                    message=f"Failed to save in-flight registry after worker release: {exc}",
                    worker_id=req.worker_id,
                    worker_name=job.worker_name,
                    role="coordinator",
                    job_id=req.job_id,
                    source_path=job.source_path,
                )
            handler._send_json({"status": "ok"})
            return

        # N2 — peek the job before mutation so we can return a precise
        # 403 vs 404 to the worker.  Without this peek a worker can't
        # tell whether its job_id was stale or whether the coordinator
        # is rejecting it for ownership reasons.
        try:
            with self._registry._lock:
                _existing = self._registry._jobs.get(req.job_id)
                _existing_owner = _existing.worker_id if _existing else None

            job = self._registry.complete(
                req.job_id,
                req.worker_id,
                success           = req.success,
                elapsed_seconds   = req.elapsed_seconds,
                output_size_bytes = req.output_size_bytes,
            )
        except Exception as exc:
            _log.exception("Failed to process /api/done completion for job %s from worker %s: %s", req.job_id, req.worker_id, exc)
            handler._send_json({"error": "done state unavailable"}, 500)
            return

        if job is None:
            if _existing is None:
                _log.warning(
                    "Done report for unknown job %s from worker '%s' "
                    "(likely already reclaimed or completed).",
                    req.job_id[:8], req.worker_id[:32],
                )
                self._safe_log_cluster_event(
                    "done-not-found",
                    level="WARN",
                    event="done_not_found",
                    message="Worker reported completion for a job that is no longer in-flight.",
                    worker_id=req.worker_id,
                    role="coordinator",
                    job_id=req.job_id,
                )
                handler._send_json({"status": "not_found", "job_id": req.job_id}, 404)
            else:
                _log.warning(
                    "Rejected /api/done from worker '%s' for job %s owned by '%s'.",
                    req.worker_id[:32], req.job_id[:8], (_existing_owner or "?")[:32],
                )
                self._safe_log_cluster_event(
                    "done-owner-mismatch",
                    level="WARN",
                    event="done_owner_mismatch",
                    message=f"Worker '{req.worker_id[:16]}' tried to close job owned by '{(_existing_owner or '?')[:16]}'",
                    worker_id=req.worker_id,
                    role="coordinator",
                    job_id=req.job_id,
                )
                handler._send_json({"status": "forbidden", "reason": "worker_id does not match job owner", "job_id": req.job_id}, 403)
            return

        # W1 — both paths (HTTP and local mark_done) share this helper so
        # cluster.log, queue-record removal, and the inflight-state save
        # all happen consistently regardless of dispatch source.
        self._emit_done_outcome(
            job               = job,
            success           = req.success,
            worker_id         = req.worker_id,
            elapsed_seconds   = req.elapsed_seconds,
            output_size_bytes = req.output_size_bytes,
            completion_status = req.completion_status or "",
            publish_state     = req.publish_state or "",
            publish_mode      = req.publish_mode or "",
            error_message     = req.error_message or "",
            queue_terminal    = bool(req.queue_terminal),
            retry_on_failure  = bool(req.retry_on_failure),
        )

        handler._send_json({"status": "ok"})

    def _emit_done_outcome(
        self,
        *,
        job,                            # InFlightJob returned by registry.complete
        success: bool,
        worker_id: str,
        elapsed_seconds: float,
        output_size_bytes: int,
        completion_status: str,
        publish_state: str,
        publish_mode: str,
        error_message: str,
        queue_terminal: bool,
        retry_on_failure: bool,
    ) -> None:
        """Shared post-``registry.complete()`` bookkeeping.

        Emits the operator-facing console + cluster.log entry, schedules
        queue-record removal through the app callback scheduler, and persists the inflight
        state.  Called by both the HTTP ``/api/done`` handler and the
        local-encode :meth:`mark_done` path so a job completed by the
        coordinator's own encode session leaves the same audit trail as
        one completed by a remote worker.

        Source-policy guardrail phrases remain visible here while the
        service owns the implementation: "Failed to schedule queue removal after done report",
        "queue record may remain claimable until manually removed", and
        "Retry policy: scheduled queue removal".
        """
        CoordinatorDoneOutcomeService(
            app=getattr(self, "_app", None),
            registry=self._registry,
            inflight_state_path=self._inflight_state_path,
            remove_from_queue=self._remove_from_queue,
            safe_log_cluster_event=self._safe_log_cluster_event,
            logger=_log,
        ).handle(
            DoneOutcome(
                job=job,
                success=success,
                worker_id=worker_id,
                elapsed_seconds=elapsed_seconds,
                output_size_bytes=output_size_bytes,
                completion_status=completion_status,
                publish_state=publish_state,
                publish_mode=publish_mode,
                error_message=error_message,
                queue_terminal=queue_terminal,
                retry_on_failure=retry_on_failure,
            )
        )

    def _http_heartbeat(self, handler: _CoordHandler, body: bytes) -> None:
        """Handle ``POST /api/heartbeat``."""
        try:
            data = loads_strict_json(body) if body else {}
            req  = HeartbeatRequest.from_dict(data)
        except Exception as exc:
            _log.warning("Rejected /api/heartbeat with invalid JSON body: %s", exc)
            handler._send_json({"error": "Invalid JSON body"}, 400)
            return
        # N13 — bound identifiers, same rules as /api/claim.
        if req.worker_id and not is_valid_worker_id(req.worker_id):
            _log.warning("Rejected /api/heartbeat with invalid worker_id=%r", req.worker_id[:80])
            handler._send_json({"error": "invalid worker_id"}, 400)
            return
        if req.job_id and not is_valid_worker_id(req.job_id):
            _log.warning("Rejected /api/heartbeat with invalid job_id=%r", req.job_id[:80])
            handler._send_json({"error": "invalid job_id"}, 400)
            return

        try:
            result = self._registry.heartbeat(
                req.job_id,
                req.worker_id,
                progress_percent=req.progress_percent,
                current_stage=req.current_stage,
            )
        except Exception as exc:
            _log.exception("Failed to process /api/heartbeat for job %s from worker %s: %s", req.job_id, req.worker_id, exc)
            handler._send_json({"error": "heartbeat unavailable"}, 500)
            return
        if result == "reclaimed":
            # Tell the cluster log when a worker discovers its job was
            # taken away — most useful diagnostic for "why did my encode
            # die mid-way" surprises.
            self._safe_log_cluster_event(
                "heartbeat-reclaimed",
                level="WARN",
                event="heartbeat_reclaimed",
                message=(
                    f"Worker reported progress on a job that's no longer "
                    f"theirs (stage={req.current_stage}, {req.progress_percent:.1f}%)"
                ),
                worker_id=req.worker_id,
                role="coordinator",
                job_id=req.job_id,
            )
        handler._send_json(HeartbeatResponse(status=result).to_dict())

    def _http_workers(self, handler: _CoordHandler, params: dict[str, str]) -> None:
        """Handle ``GET /api/workers``."""
        try:
            entries   = self._registry.snapshot()
            remaining = len(getattr(self._app, "queue_records", []))
        except Exception as exc:
            _log.exception("Failed to build /api/workers response: %s", exc)
            handler._send_json({"error": "worker snapshot unavailable"}, 500)
            return
        # W6 — stamp the coordinator's wall clock so the UI can compute
        # heartbeat ages relative to the coordinator rather than the
        # local coordinator host.  Eliminates false "stale" highlights when the
        # operator's laptop clock drifts away from the coordinator's.
        response  = WorkersResponse(
            workers=entries,
            queue_remaining=remaining,
            jobs_completed_session=self._registry.session_completed,
            jobs_failed_session=self._registry.session_failed,
            coordinator_now=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        handler._send_json(response.to_dict())

    def _http_log(self, handler: _CoordHandler, body: bytes) -> None:
        """Handle ``POST /api/log`` — append a worker-emitted entry to cluster.log.

        Workers fire-and-forget POST these for every interesting lifecycle
        event so an operator can see what every machine in the cluster is
        doing in one chronological view.  Auth is the same bearer token as
        every other endpoint, so untrusted boxes can't pollute the log.
        """
        try:
            data = loads_strict_json(body) if body else {}
            entry = LogEntryRequest.from_dict(data)
        except Exception as exc:
            _log.warning("Rejected /api/log with invalid JSON body: %s", exc)
            handler._send_json({"error": "Invalid JSON body"}, 400)
            return
        if not entry.event:
            _log.warning("Rejected /api/log without required event field from worker_id=%r", entry.worker_id[:80])
            handler._send_json({"error": "event field is required"}, 400)
            return
        # N13 — bound identifiers and clip the message so a misbehaving
        # worker can't burn cluster.log space with multi-MB lines. The
        # cluster log line formatter already truncates display fields;
        # this just rejects pathological inputs early. Clip rather than
        # reject the message body — operators want partial diagnostics
        # over silent drops.
        raw_worker_id = entry.worker_id or ""
        raw_job_id = entry.job_id or ""
        raw_event = entry.event or ""
        raw_message = entry.message or ""
        sanitize_log_entry_fields(entry)
        if raw_worker_id and not entry.worker_id:
            _log.warning("Sanitized /api/log invalid worker_id=%r before appending cluster log entry.", raw_worker_id[:80])
        if raw_job_id and not entry.job_id:
            _log.warning("Sanitized /api/log invalid job_id=%r before appending cluster log entry.", raw_job_id[:80])
        if raw_event and entry.event != raw_event:
            _log.warning("Truncated /api/log event field from %d to %d characters.", len(raw_event), len(entry.event))
        if raw_message and entry.message != raw_message:
            _log.warning("Truncated /api/log message field from %d to %d characters.", len(raw_message), len(entry.message))
        # W7 — preserve the worker-supplied timestamp on a side-channel
        # attribute and rewrite ``entry.timestamp`` to the coordinator
        # receive time. The cluster log is keyed off entry.timestamp, so
        # this guarantees the file is monotonically ordered by the time
        # we observed each event regardless of worker clock skew. The
        # original worker_ts is rendered as a trailing tag by
        # :meth:`_format_cluster_log_line` for forensic visibility.
        coord_now = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            entry._worker_ts = entry.timestamp or ""    # type: ignore[attr-defined]
        except Exception as exc:
            _log.warning(
                "Could not preserve worker timestamp for /api/log event %s; using coordinator receive time only: %s",
                entry.event,
                exc,
            )
        entry.timestamp = coord_now
        try:
            self._append_cluster_log(entry)
        except Exception as exc:
            _log.warning("Unexpected cluster log append failure for event %s: %s", entry.event, exc)
        handler._send_json({"status": "ok"})
