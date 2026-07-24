"""Polling, heartbeat, and shutdown loops for :class:`WorkerDispatcher`."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .coordinator_policy import heartbeat_timeout_mins
from .diagnostics import diagnostic_preview as _worker_diagnostic_preview
from .library_roots import accessible_library_ids_from_config
from .protocol import HeartbeatRequest, coerce_progress_percent
from .poll_policy import resolve_worker_wait_seconds
from .worker_parts.reporting import claim_failure_status_message
from .worker_parts.tasks import build_claimed_job, claim_with_source_path, parse_claim_response_payload
from .worker_record import make_queue_record as _make_queue_record

if TYPE_CHECKING:
    from .dispatcher import ClaimedJob

_log = logging.getLogger("mediapipeline.desktop.network.worker")

_HEARTBEAT_INTERVAL = 30


def _probe_csv_rerun_handoff(claim: Any) -> dict[str, Any]:
    if str(getattr(claim, "job_kind", "") or "") != "csv_rerun_row":
        return {}
    planned_path = str(
        getattr(claim, "planned_output_path", "")
        or (getattr(claim, "output_handoff", {}) or {}).get("planned_row_handoff_path")
        or ""
    ).strip()
    result: dict[str, Any] = {
        "schema_version": "desktop_rerun_network_worker_handoff_probe.v1",
        "status": "not_run",
        "ok": False,
        "planned_output_path": planned_path,
        "operations": [],
        "cleanup_result": "not_started",
    }
    if not planned_path:
        result.update({"status": "blocked", "error": "csv_rerun_row claim is missing planned_output_path"})
        raise RuntimeError(result["error"])
    handoff_dir = Path(planned_path)
    probe_file = handoff_dir / f".worker-handoff-probe-{uuid.uuid4().hex}.txt"
    try:
        handoff_dir.mkdir(parents=True, exist_ok=True)
        result["operations"].append("create_dir")
        probe_file.write_text("network csv rerun worker handoff probe\n", encoding="utf-8")
        result["operations"].append("write")
        if probe_file.read_text(encoding="utf-8") != "network csv rerun worker handoff probe\n":
            raise RuntimeError("probe read did not match written content")
        result["operations"].append("read")
        _ = list(handoff_dir.iterdir())
        result["operations"].append("list")
        probe_file.unlink()
        result["operations"].append("delete_probe")
        result["status"] = "ok"
        result["ok"] = True
        result["cleanup_result"] = "probe_file_deleted"
        return result
    except Exception as exc:
        result.update({"status": "failed", "error": str(exc), "cleanup_result": "cleanup_attempted"})
        try:
            probe_file.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(f"csv rerun handoff probe failed: {exc}") from exc


class WorkerLoopMixin:
    def _accessible_library_ids(self) -> list[str]:
        """Return currently reachable worker library IDs for coordinator dispatch."""
        try:
            worker_config = getattr(self, "_worker_config", None)
            if callable(worker_config):
                config = worker_config()
            else:
                app = getattr(self, "app", None)
                resolved = getattr(app, "resolved", None)
                config = getattr(resolved, "config_data", {}) if resolved is not None else {}
            return accessible_library_ids_from_config(config)
        except Exception as exc:
            _log.warning(
                "Worker library capability probe failed; reporting no accessible libraries: %s",
                _worker_diagnostic_preview(exc),
            )
            return []

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

    def _heartbeat_failure_abort_threshold_seconds(self) -> int:
        """Return local abort threshold for consecutive heartbeat POST failures."""
        try:
            worker_config = getattr(self, "_worker_config", None)
            if callable(worker_config):
                config = worker_config()
            else:
                app = getattr(self, "app", None)
                resolved = getattr(app, "resolved", None)
                config = getattr(resolved, "config_data", {}) if resolved is not None else {}
            timeout_seconds = heartbeat_timeout_mins(config) * 60.0
        except Exception as exc:
            _log.warning("Worker heartbeat timeout lookup failed; using conservative abort threshold: %s", exc)
            timeout_seconds = 5 * 60.0
        return int(max(60.0, min(240.0, timeout_seconds - 60.0)))

    def _reset_heartbeat_failure_state(self) -> None:
        self._heartbeat_failure_started_monotonic = None
        self._heartbeat_failure_started_at = ""
        self._heartbeat_failure_age_seconds = 0
        self._heartbeat_failure_abort_threshold_seconds_value = self._heartbeat_failure_abort_threshold_seconds()

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

            # Deliver any persisted pending done report before claiming:
            # worker_state.json is a single slot, so a new claim's state
            # save would overwrite the undelivered report.
            if not self._flush_pending_done_report():
                self._wait_interruptible()
                continue
            self._maybe_refresh_library_auto_map()

            resp: dict[str, Any] | None = None
            claim_http_context: tuple[str, str] | None = None
            try:
                accessible_library_ids = self._accessible_library_ids()
                resp, claim_http_context = self._http_get_for_claim(
                    "/api/claim",
                    {
                        "worker_id":   self._worker_id,
                        "worker_name": self._worker_name,
                        "accessible_library_ids": ",".join(accessible_library_ids),
                    },
                )
                claim = parse_claim_response_payload(resp)
                self._last_claim_failure_text = ""
            except Exception as exc:
                try:
                    if resp is not None and self._release_malformed_claim_response(
                        resp,
                        str(exc),
                        http_context=claim_http_context,
                    ):
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
                    auth_message = (
                        "Coordinator returned 401 - coordinator/worker clock skew exceeds five minutes."
                        if "clock_skew" in err_str
                        else "Coordinator returned 401 - token mismatch."
                    )
                    # Auth error is loud — fire one cluster log so the
                    # operator sees it on the coordinator immediately.
                    # (Will only land if the token is at least valid enough
                    # to get past /api/log auth — usually identical token.)
                    self._safe_log_cluster_event(
                        "claim-unauthorized",
                        level="ERROR", event="claim_unauthorized",
                        message=auth_message,
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
                now = datetime.now(UTC).strftime("%H:%M:%S")
                self._notify_status(f"● Idle — coordinator queue empty (last checked {now})")
                self._wait_interruptible(
                    self._resolve_wait_seconds(getattr(claim, "retry_after_seconds", 0))
                )
                continue

            # Prefer additive library-relative claim fields when present, then
            # fall back to C1/manual prefix maps and finally the raw source path.
            original_path = claim.source_path
            try:
                mapped_path, resolution_mode = self.resolve_claim_source_path(claim)
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
                if claim_http_context is not None:
                    self._register_claim_http_context(claim.job_id, claim_http_context)
                self._release_unstartable_claim(claim, f"path map failed: {exc}")
                self._wait_interruptible()
                continue
            if mapped_path != original_path:
                log_event = "path_remapped"
                log_context = "path-remapped"
                if resolution_mode == "library_relative":
                    _log.info(
                        "Library-relative claim resolved %s/%s -> %s",
                        claim.library_id,
                        claim.relative_path,
                        mapped_path,
                    )
                    log_event = "claim_library_resolved"
                    log_context = "claim-library-resolved"
                else:
                    _log.info(
                        "Path map rewrote %s → %s",
                        original_path, mapped_path,
                    )
                self._safe_log_cluster_event(
                    log_context,
                    level="DEBUG",
                    event=log_event,
                    message=f"{original_path} → {mapped_path}",
                    job_id=claim.job_id,
                    source_path=mapped_path,
                )
                # Build a new ClaimResponse with the rewritten path so downstream
                # code (heartbeat, mark_done, _make_queue_record) sees the local form.
                # The coordinator still tracks the original path internally.
                claim = claim_with_source_path(claim, mapped_path)

            try:
                claim.handoff_probe = _probe_csv_rerun_handoff(claim)
            except Exception as exc:
                reason_preview = _worker_diagnostic_preview(exc)
                _log.error("Handoff probe failed for claimed job %s: %s", claim.job_id, reason_preview)
                self._safe_log_cluster_event(
                    "handoff-probe-failed",
                    level="ERROR",
                    event="handoff_probe_failed",
                    message=f"Worker handoff probe failed for claimed job: {reason_preview}",
                    job_id=claim.job_id,
                    source_path=claim.source_path,
                )
                if claim_http_context is not None:
                    self._register_claim_http_context(claim.job_id, claim_http_context)
                self._release_unstartable_claim(claim, reason_preview)
                self._wait_interruptible()
                continue

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
                if claim_http_context is not None:
                    self._register_claim_http_context(claim.job_id, claim_http_context)
                self._release_unstartable_claim(claim, reason_preview)
                self._wait_interruptible()
                continue

            if claim_http_context is None:
                raise RuntimeError(f"Claim {job.job_id} did not retain its coordinator HTTP context")
            self._register_claim_http_context(job.job_id, claim_http_context)
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
        threshold_seconds = self._heartbeat_failure_abort_threshold_seconds()
        self._heartbeat_failure_abort_threshold_seconds_value = threshold_seconds
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
                resp = self._http_post_for_claim(
                    job.job_id,
                    "/api/heartbeat",
                    HeartbeatRequest(
                        job_id           = job.job_id,
                        worker_id        = self._worker_id,
                        progress_percent = progress,
                        current_stage    = stage,
                        accessible_library_ids = self._accessible_library_ids(),
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
                    abort_contained = self._request_abort_reclaimed_job(job)
                    if abort_contained is not False:
                        break
                    self._notify_status("⚠ Abort containment not yet proven; retrying until the process exits")
                    continue
                self._last_heartbeat_failure_text = ""
                self._reset_heartbeat_failure_state()
            except Exception as exc:
                now_monotonic = time.monotonic()
                started = getattr(self, "_heartbeat_failure_started_monotonic", None)
                if started is None:
                    self._heartbeat_failure_started_monotonic = now_monotonic
                    self._heartbeat_failure_started_at = datetime.now(UTC).isoformat()
                    failure_age = 0
                else:
                    failure_age = max(0, int(now_monotonic - float(started)))
                self._heartbeat_failure_age_seconds = failure_age
                self._heartbeat_failure_abort_threshold_seconds_value = threshold_seconds
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
                if failure_age >= threshold_seconds:
                    _log.error(
                        "Worker heartbeat failed for %ss on job %s; aborting before coordinator lease expiry.",
                        failure_age,
                        job.job_id,
                    )
                    self._notify_status(
                        f"⚠ Heartbeat failed for {failure_age}s — aborting {Path(str(job.record.source_path)).name}"
                    )
                    self._safe_log_cluster_event(
                        "heartbeat-failure-abort",
                        level="ERROR",
                        event="heartbeat_failure_abort",
                        message=(
                            f"Heartbeat POST failed for {failure_age}s "
                            f"(threshold={threshold_seconds}s); aborting local encode"
                        ),
                        job_id=job.job_id,
                        source_path=str(job.record.source_path),
                    )
                    self._job_reclaimed = True
                    abort_contained = self._request_abort_reclaimed_job(job)
                    if abort_contained is not False:
                        break
                    self._notify_status("⚠ Abort containment not yet proven; retrying until the process exits")
                    continue

    def _stop_heartbeat(self) -> None:
        """Signal the heartbeat thread to stop and wait for it."""
        self._heartbeat_stop.set()
        t = self._heartbeat_thread
        if t is not None and t.is_alive():
            t.join(timeout=5)
            if t.is_alive():
                _log.warning("Worker heartbeat thread did not stop within 5 seconds; continuing cleanup.")
        self._heartbeat_thread = None

    def shutdown(self, *, release_active_job: bool = True, preserve_active_job: bool = False) -> None:
        """Stop polling and optionally preserve or release an active job."""
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
            if preserve_active_job:
                _log.warning(
                    "WorkerDispatcher shutdown preserved active job %s; heartbeat and done reporting remain active.",
                    getattr(job, "job_id", "")[:8],
                )
            elif release_active_job:
                self.release(job)
            else:
                _log.warning(
                    "WorkerDispatcher shutdown left active job %s claimed because the pipeline process is still running.",
                    getattr(job, "job_id", "")[:8],
                )
                self._stop_heartbeat()
        else:
            # Still need to stop the heartbeat if it's running independently.
            self._stop_heartbeat()

        t = self._poll_thread
        if t is not None and t.is_alive():
            t.join(timeout=5)
            if t.is_alive():
                _log.warning("Worker poll thread did not stop within 5 seconds; continuing shutdown.")
