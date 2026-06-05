"""Coordinator HTTP server, reaper, mDNS, and snapshot helpers."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from .coordinator_parts.http_server import _CoordHandler, _CoordServer
from .protocol import WorkerEntry

_log = logging.getLogger("mediapipeline.desktop.network.coordinator")


class CoordinatorLifecycleMixin:
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
