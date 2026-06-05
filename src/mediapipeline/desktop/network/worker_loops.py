"""Polling, heartbeat, and shutdown loops for :class:`WorkerDispatcher`."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .diagnostics import diagnostic_preview as _worker_diagnostic_preview
from .protocol import HeartbeatRequest, coerce_progress_percent
from .poll_policy import resolve_worker_wait_seconds
from .worker_parts.reporting import claim_failure_status_message
from .worker_parts.tasks import build_claimed_job, claim_with_source_path, parse_claim_response_payload
from .worker_record import make_queue_record as _make_queue_record

_log = logging.getLogger("mediapipeline.desktop.network.worker")

_HEARTBEAT_INTERVAL = 30


class WorkerLoopMixin:
    def wakeup(self) -> None:
        """Wake the poll loop immediately instead of waiting for the next interval.

        Thread-safe — can be called from any thread (e.g. the UI callback thread
        when the user clicks "Poll Now").
        """
        self._wakeup.set()

    def _resolve_wait_seconds(self, server_hint_seconds: int) -> float:
        """Reconcile the coordinator's backoff hint with the worker's
        configured poll cadence.

        W4 — the coordinator advertises a ``retry_after_seconds`` value
        on every empty ClaimResponse: short (~5 s) when the cluster is
        busy and a job might free soon, long (~30 s) when truly idle.
        We honour the hint but clamp it into ``[1s, _poll_interval]``:

        * Lower bound 1 s prevents a buggy or malicious coordinator
          from inducing a tight poll loop that DoS-es itself.
        * Upper bound ``_poll_interval`` honours the operator-set
          ceiling — operators tune ``WorkerPollIntervalSecs`` to balance
          responsiveness against load, so the server can't ask the
          worker to wait *longer* than that, only shorter.

        ``server_hint_seconds <= 0`` means "no hint provided" and
        produces the legacy behaviour (wait the full poll interval).
        """
        return resolve_worker_wait_seconds(server_hint_seconds, self._poll_interval)

    def _wait_interruptible(self, seconds: float | None = None) -> None:
        """Sleep for ``seconds`` (default ``_poll_interval``), exiting
        early when either ``_poll_stop`` or ``_wakeup`` is set.

        Uses 0.1-second slices so the stop/wake signals are honoured
        quickly without burning CPU in a tight spin.
        """
        import time as _time  # noqa: PLC0415
        wait_for = float(seconds) if seconds is not None else float(self._poll_interval)
        deadline = _time.monotonic() + wait_for
        while not self._poll_stop.is_set():
            remaining = deadline - _time.monotonic()
            if remaining <= 0:
                break
            if self._wakeup.wait(min(remaining, 0.1)):
                self._wakeup.clear()
                break

    def _poll_loop(self) -> None:
        """Main worker poll loop.

        Runs forever until ``shutdown()`` is called.  Sleeps
        ``WorkerPollIntervalSecs`` between attempts, skips claiming when
        an encode is already in flight.  Calls ``_notify_status`` after
        every attempt so the Home screen notice bar stays current.
        """
        _log.info("Worker poll loop started (interval=%ss).", self._poll_interval)
        while not self._poll_stop.is_set():
            # Don't claim while an encode is already in flight.
            with self._active_job_lock:
                busy = self._active_job is not None
            if busy:
                self._wait_interruptible()
                continue

            resp: dict[str, Any] | None = None
            try:
                resp = self._http_get(
                    "/api/claim",
                    {
                        "worker_id":   self._worker_id,
                        "worker_name": self._worker_name,
                    },
                )
                claim = parse_claim_response_payload(resp)
                self._last_claim_failure_text = ""
            except Exception as exc:
                try:
                    if resp is not None and self._release_malformed_claim_response(resp, str(exc)):
                        self._wait_interruptible()
                        continue
                except Exception as release_exc:
                    _log.warning(
                        "Failed to release malformed claimed response after parse error %s: %s",
                        exc,
                        release_exc,
                    )
                err_str = str(exc)
                reason_preview = _worker_diagnostic_preview(exc)
                if err_str != getattr(self, "_last_claim_failure_text", ""):
                    _log.warning(
                        "Worker claim request failed; poll loop will retry: %s",
                        reason_preview,
                    )
                    self._last_claim_failure_text = err_str
                else:
                    _log.debug("Claim request still failing: %s — sleeping.", reason_preview)
                status_message, log_auth_event = claim_failure_status_message(
                    err_str,
                    reason_preview,
                    self._base_url,
                )
                self._notify_status(status_message)
                if log_auth_event:
                    # Auth error is loud — fire one cluster log so the
                    # operator sees it on the coordinator immediately.
                    # (Will only land if the token is at least valid enough
                    # to get past /api/log auth — usually identical token.)
                    self._safe_log_cluster_event(
                        "claim-unauthorized",
                        level="ERROR", event="claim_unauthorized",
                        message="Coordinator returned 401 — token mismatch.",
                    )
                self._wait_interruptible()
                continue

            if claim.status != "ok":
                # Queue is empty; wait and try again. W4 — honour the
                # coordinator's backoff hint when present so we poll
                # faster when other workers are encoding (a job may free
                # up soon) and slower when the cluster is idle.  The
                # hint is clamped to [1s, _poll_interval] inside
                # _resolve_wait_seconds so it can't dilate beyond the
                # operator-configured ceiling.
                now = datetime.now(timezone.utc).strftime("%H:%M:%S")
                self._notify_status(f"● Idle — coordinator queue empty (last checked {now})")
                self._wait_interruptible(
                    self._resolve_wait_seconds(getattr(claim, "retry_after_seconds", 0))
                )
                continue

            # Apply source path map: rewrite coordinator paths to local ones if
            # this worker has WorkerSourcePathMap configured.  No-op when unset.
            original_path = claim.source_path
            try:
                mapped_path = self._apply_path_map(original_path)
            except Exception as exc:
                _log.error("Source path map failed for claimed job %s: %s", claim.job_id, exc)
                self._safe_log_cluster_event(
                    "path-map-failure",
                    level="ERROR",
                    event="path_map_failed",
                    message=f"Worker source path map failed for claimed job: {exc}",
                    job_id=claim.job_id,
                    source_path=original_path,
                )
                self._release_unstartable_claim(claim, f"path map failed: {exc}")
                self._wait_interruptible()
                continue
            if mapped_path != original_path:
                _log.info(
                    "Path map rewrote %s → %s",
                    original_path, mapped_path,
                )
                self._safe_log_cluster_event(
                    "path-remapped",
                    level="DEBUG",
                    event="path_remapped",
                    message=f"{original_path} → {mapped_path}",
                    job_id=claim.job_id,
                    source_path=mapped_path,
                )
                # Build a new ClaimResponse with the rewritten path so downstream
                # code (heartbeat, mark_done, _make_queue_record) sees the local form.
                # The coordinator still tracks the original path internally.
                claim = claim_with_source_path(claim, mapped_path)

            # Build a synthetic QueueRecord for the claimed path.
            try:
                job = build_claimed_job(
                    claim,
                    self._worker_id,
                    record_builder=_make_queue_record,
                )
            except Exception as exc:
                reason_preview = _worker_diagnostic_preview(exc)
                _log.error("Failed to build QueueRecord for claimed job: %s", reason_preview)
                self._safe_log_cluster_event(
                    "claim-record-invalid",
                    level="ERROR",
                    event="claim_record_invalid",
                    message=f"Worker could not build QueueRecord for claimed job: {reason_preview}",
                    job_id=claim.job_id,
                    source_path=claim.source_path,
                )
                self._release_unstartable_claim(claim, reason_preview)
                self._wait_interruptible()
                continue

            with self._active_job_lock:
                self._active_job = job

            try:
                self._on_job_claimed(job)
            except Exception as exc:
                reason_preview = _worker_diagnostic_preview(exc)
                _log.error("Worker failed after claiming job %s; releasing claim. %s", job.job_id, reason_preview)
                self._notify_status(f"⚠ Claimed job handoff failed: {reason_preview[:80]}")
                self._do_release(job)

    def _heartbeat_loop(self, job: ClaimedJob) -> None:
        """Send ``POST /api/heartbeat`` every ``_HEARTBEAT_INTERVAL`` seconds.

        Stops when ``_heartbeat_stop`` is set (on ``mark_done`` / ``release``
        / ``shutdown``).  If the coordinator responds with ``"reclaimed"``,
        sets ``_job_reclaimed = True`` and schedules an abort on the app callback thread.
        """
        while not self._heartbeat_stop.wait(_HEARTBEAT_INTERVAL):
            # Grab current progress from the app's live snapshot.
            progress = 0.0
            stage    = ""
            try:
                snap = getattr(self.app, "snapshot", None)
                if snap is not None:
                    _p = getattr(snap, "progress", None)
                    if isinstance(_p, dict):
                        stage    = str(_p.get("CurrentStage", "") or "")
                        progress = coerce_progress_percent(_p.get("CurrentStagePercent", 0) or 0)
            except Exception as exc:
                _log.warning(
                    "Heartbeat progress snapshot read failed for job %s; sending 0%% progress: %s",
                    job.job_id,
                    exc,
                )
                progress = 0.0

            try:
                resp = self._http_post(
                    "/api/heartbeat",
                    HeartbeatRequest(
                        job_id           = job.job_id,
                        worker_id        = self._worker_id,
                        progress_percent = progress,
                        current_stage    = stage,
                    ).to_dict(),
                )
                if resp.get("status") == "reclaimed":
                    _log.warning(
                        "Job %s reclaimed by coordinator — aborting encode.",
                        job.job_id,
                    )
                    self._notify_status(
                        f"⚠ Job reclaimed by coordinator — aborting {Path(str(job.record.source_path)).name}"
                    )
                    self._safe_log_cluster_event(
                        "job-reclaimed",
                        level="WARN",
                        event="job_reclaimed",
                        message=(
                            f"Heartbeat returned 'reclaimed' for "
                            f"{Path(str(job.record.source_path)).name}; aborting"
                        ),
                        job_id=job.job_id,
                        source_path=str(job.record.source_path),
                    )
                    self._job_reclaimed = True
                    self._request_abort_reclaimed_job(job)
                    break
                self._last_heartbeat_failure_text = ""
            except Exception as exc:
                err_str = str(exc)
                reason_preview = _worker_diagnostic_preview(exc)
                if err_str != getattr(self, "_last_heartbeat_failure_text", ""):
                    _log.warning(
                        "Worker heartbeat POST failed for job %s; heartbeat loop will retry: %s",
                        job.job_id,
                        reason_preview,
                    )
                    self._last_heartbeat_failure_text = err_str
                else:
                    _log.debug("Heartbeat POST still failing for job %s: %s", job.job_id, reason_preview)
                self._notify_status(f"⚠ Heartbeat failed: {reason_preview[:80]}")

    def _stop_heartbeat(self) -> None:
        """Signal the heartbeat thread to stop and wait for it."""
        self._heartbeat_stop.set()
        t = self._heartbeat_thread
        if t is not None and t.is_alive():
            t.join(timeout=5)
            if t.is_alive():
                _log.warning("Worker heartbeat thread did not stop within 5 seconds; continuing cleanup.")
        self._heartbeat_thread = None

    def shutdown(self) -> None:
        """Stop all background threads.  Release any active job back to the queue."""
        _log.info("WorkerDispatcher shutting down.")
        self._safe_log_cluster_event(
            "worker-stopped",
            level="INFO",
            event="worker_stopped",
            message=f"Worker '{self._worker_name}' shutting down",
        )
        self._poll_stop.set()

        # Release the in-flight job so the coordinator can re-queue it.
        with self._active_job_lock:
            job = self._active_job
        if job is not None:
            self.release(job)
        else:
            # Still need to stop the heartbeat if it's running independently.
            self._stop_heartbeat()

        t = self._poll_thread
        if t is not None and t.is_alive():
            t.join(timeout=5)
            if t.is_alive():
                _log.warning("Worker poll thread did not stop within 5 seconds; continuing shutdown.")
