"""
network.worker
==============
``WorkerDispatcher`` — polls a remote coordinator for jobs and executes them
by launching the PowerShell pipeline with ``-SingleFile <path>``.

Phase 2 implementation.
"""
from __future__ import annotations

import logging
import socket
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..config_keys import (
    KEY_WORKER_AUTH_TOKEN,
    KEY_WORKER_COORDINATOR_URL,
    KEY_WORKER_NAME,
    KEY_WORKER_POLL_INTERVAL_SECS,
    KEY_WORKER_SOURCE_PATH_MAP,
)
from .coordinator_url import validate_coordinator_url as _validate_coordinator_url
from .diagnostics import diagnostic_preview as _worker_diagnostic_preview
from .dispatcher import ClaimedJob, QueueDispatcher
from .auth import sign_request as _sign_request_headers
from .http_json import HTTP_MAX_RESPONSE_BYTES as _HTTP_MAX_RESPONSE_BYTES
from .http_json import HTTP_TIMEOUT as _HTTP_TIMEOUT
from .http_json import http_get_json, http_post_json
from .http_json import http_read_capped as _http_read_capped
from .path_map import apply_source_path_map, parse_source_path_map
from .poll_policy import resolve_worker_poll_interval, resolve_worker_wait_seconds
from .protocol import ClaimResponse, HeartbeatRequest, LogEntryRequest, coerce_progress_percent
from .worker_done import (
    build_completion_done_request,
    build_crash_recovery_done_request,
    build_release_done_request,
)
from .worker_parts.reporting import (
    claim_failure_status_message,
    is_unauthorized_http_error as _is_unauthorized_http_error,  # noqa: F401 - compatibility re-export
    notify_status_callback,
    post_app_callback,
    request_abort_reclaimed_job,
)
from .worker_parts.results import completion_cluster_event, release_cluster_event
from .worker_parts.state_reports import save_active_worker_state, save_pending_worker_report
from .worker_parts.tasks import (
    build_claimed_job,
    claim_with_source_path,
    malformed_claim_identity,
    parse_claim_response_payload,
)
from .worker_record import make_queue_record as _make_queue_record
from .worker_state import atomic_write_text as _atomic_write_text
from .worker_state import clear_worker_state, load_worker_state, save_worker_state

if TYPE_CHECKING:
    from ..app import MediaPipelineApp

_log = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL = 30   # seconds between heartbeats
# HTTP timeout and response-size caps live in network.http_json and are
# imported here under their historical names for compatibility.


class WorkerDispatcher(QueueDispatcher):
    """Polls a remote ``CoordinatorDispatcher`` for work via HTTP.

    The actual encode is delegated to the PowerShell pipeline via
    ``start_pipeline -SingleFile <path>``.  This dispatcher provides:

    * A background **poll thread** that calls ``GET /api/claim`` on a
      configurable interval and, when a job is available, schedules
      ``app._worker_start_single_file(job)`` on the app callback thread.
    * A **heartbeat thread** (started per-job) that sends
      ``POST /api/heartbeat`` every 30 s.  If the coordinator responds
      with ``"reclaimed"`` the worker signals the active pipeline process
      to abort.
    * ``mark_done()`` / ``release()`` that call the coordinator's HTTP API.
    * **Crash recovery**: on init, if ``worker_state.json`` is present, the
      worker immediately reports the interrupted job as failed to the
      coordinator, then begins polling normally.
    """

    def __init__(self, app: "MediaPipelineApp") -> None:
        self.app = app

        resolved = getattr(app, "resolved", None)
        config   = getattr(resolved, "config_data", {}) if resolved else {}

        # N17 — strict URL validation. Bad config used to send the
        # bearer token to whatever host the typo pointed at. Failing
        # fast here forces the operator to fix the URL before the
        # worker leaks anything.
        self._base_url      = _validate_coordinator_url(str(config.get(KEY_WORKER_COORDINATOR_URL, "")))
        self._worker_id     = str(getattr(app, "_machine_id", "") or uuid.uuid4())
        # Use the configured name; fall back to the OS hostname so multiple
        # unnamed workers appear as distinct machines in the coordinator board.
        _cfg_name = str(config.get(KEY_WORKER_NAME, "")).strip()
        self._worker_name = _cfg_name or _safe_hostname()
        self._auth_token    = str(config.get(KEY_WORKER_AUTH_TOKEN, "")).strip()
        self._poll_interval = resolve_worker_poll_interval(config.get(KEY_WORKER_POLL_INTERVAL_SECS, 30))

        # Source path mapping: rewrite coordinator paths to local-reachable ones.
        # Parsed once at construction; callers can hot-swap via update_source_path_map().
        self._source_path_map: list[tuple[str, str]] = self._parse_source_path_map(
            str(config.get(KEY_WORKER_SOURCE_PATH_MAP, "") or "").strip()
        )

        # State path for crash recovery — same directory as the app state file.
        svc = getattr(app, "service", None)
        state_dir = (
            Path(svc.app_state_path).parent
            if svc and hasattr(svc, "app_state_path")
            else Path.home()
        )
        self._state_path: Path = state_dir / "worker_state.json"

        # Currently-active job (set while encode is in flight).
        self._active_job: ClaimedJob | None = None
        self._active_job_lock = threading.Lock()

        # Heartbeat thread management.
        self._heartbeat_stop   = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._job_reclaimed    = False
        self._last_heartbeat_failure_text = ""

        # Poll thread management.
        self._poll_stop   = threading.Event()
        self._wakeup      = threading.Event()   # set() to interrupt the inter-poll sleep
        self._poll_thread: threading.Thread | None = threading.Thread(
            target=self._poll_loop, name="worker-poll", daemon=True
        )
        self._last_claim_failure_text = ""

        # Optional status callback — called from the poll thread with a human-
        # readable status string after every claim attempt.  Wired by the app
        # so the Home screen notice bar stays current without tight coupling
        # between WorkerDispatcher and the app callback thread.
        # Signature: callback(msg: str) -> None  (called on the poll thread)
        self._status_callback: "Callable[[str], None] | None" = None

        # Crash recovery: if a previous run left worker_state.json, report
        # it as failed before entering the poll loop.
        self._crash_recover()

        try:
            self._poll_thread.start()
        except Exception as exc:
            self._poll_thread = None
            _log.error("Could not start worker poll thread for coordinator %s: %s", self._base_url, exc)
            raise RuntimeError(f"Could not start worker poll thread for coordinator {self._base_url}: {exc}") from exc
        _log.info(
            "WorkerDispatcher started: coordinator=%s worker=%s poll_interval=%ss path_map_entries=%d",
            self._base_url, self._worker_name, self._poll_interval,
            len(self._source_path_map),
        )
        self._safe_log_cluster_event(
            "worker-started",
            level="INFO",
            event="worker_started",
            message=(
                f"Connected to {self._base_url} "
                f"(poll={self._poll_interval}s, path_map={len(self._source_path_map)} entries)"
            ),
        )

    # ------------------------------------------------------------------
    # Cluster log (fire-and-forget POST /api/log to the coordinator)
    # ------------------------------------------------------------------

    def log_cluster_event(
        self,
        *,
        level: str = "INFO",
        event: str,
        message: str = "",
        job_id: str = "",
        source_path: str = "",
    ) -> None:
        """Fire-and-forget POST one event to the coordinator's cluster log.

        Runs the HTTP call on a daemon thread so the calling code never
        blocks on network round-trips.  Failed POSTs warn in the local
        desktop app log but never escape the helper -- the cluster log is
        a convenience, not a correctness mechanism.

        Also mirrors the entry into the local Python logger so a worker
        without coordinator connectivity still has the event in its own log.
        """
        # Local mirror — always written, even if the coordinator is unreachable.
        py_level = {"DEBUG": logging.DEBUG, "INFO": logging.INFO,
                    "WARN": logging.WARNING, "WARNING": logging.WARNING,
                    "ERROR": logging.ERROR}.get(level.upper(), logging.INFO)
        _log.log(py_level, "[cluster:%s] %s %s", event, message,
                 f"(job={job_id[:8]})" if job_id else "")

        # Build the request payload once and dispatch on a daemon thread.
        entry = LogEntryRequest(
            timestamp   = datetime.now().astimezone().isoformat(timespec="seconds"),
            worker_id   = self._worker_id,
            worker_name = self._worker_name,
            role        = "worker",
            level       = level.upper(),
            event       = event,
            message     = message,
            job_id      = job_id,
            source_path = source_path,
        )

        def _send():
            try:
                self._http_post("/api/log", entry.to_dict())
            except Exception as exc:
                _log.warning("cluster log POST failed for event %s: %s", event, _worker_diagnostic_preview(exc))

        try:
            threading.Thread(target=_send, name="cluster-log-post", daemon=True).start()
        except Exception as exc:
            _log.warning(
                "Failed to start cluster log POST thread for event %s: %s",
                event,
                _worker_diagnostic_preview(exc),
            )

    def _safe_log_cluster_event(self, context: str, **kwargs: Any) -> None:
        """Emit a best-effort cluster event without changing worker control flow."""
        try:
            self.log_cluster_event(**kwargs)
        except Exception as exc:
            job_id = str(kwargs.get("job_id", "") or "")
            _log.warning(
                "Failed to emit %s cluster event for job %s: %s",
                context,
                job_id[:8],
                _worker_diagnostic_preview(exc),
            )

    # ------------------------------------------------------------------
    # Source path mapping (for heterogeneous coordinator/worker setups)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_source_path_map(raw: str) -> list[tuple[str, str]]:
        return parse_source_path_map(raw)

    def _apply_path_map(self, path: str) -> str:
        """Rewrite *path* using the first matching prefix in the source path map.

        Match is case-insensitive (Windows filesystems are case-insensitive),
        but the original casing of the un-matched suffix is preserved.
        Returns *path* unchanged when no prefix matches.
        """
        return apply_source_path_map(path, self._source_path_map)

    def update_source_path_map(self, raw: str) -> None:
        """Hot-swap the source path map without restarting the dispatcher.

        Called from the Network tab when the user edits WorkerSourcePathMap
        and wants the change applied immediately.
        """
        self._source_path_map = self._parse_source_path_map((raw or "").strip())
        _log.info(
            "Worker source path map updated (hot-swap, %d entries).",
            len(self._source_path_map),
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }

    def _sign_request(self, method: str, path_with_query: str, body: bytes) -> dict[str, str]:
        if not self._auth_token:
            return {}
        return _sign_request_headers(method, path_with_query, body, self._auth_token)

    def _http_get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        return http_get_json(
            self._base_url,
            path,
            headers=self._headers(),
            params=params,
            sign_request=self._sign_request,
            timeout_seconds=_HTTP_TIMEOUT,
        )

    def _http_post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        return http_post_json(
            self._base_url,
            path,
            data,
            headers=self._headers(),
            sign_request=self._sign_request,
            timeout_seconds=_HTTP_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------

    def _crash_recover(self) -> None:
        """If ``worker_state.json`` exists, report the interrupted job as failed."""
        if not self._state_path.exists():
            return
        try:
            state = load_worker_state(self._state_path)
        except Exception as exc:
            _log.warning("worker_state.json unreadable (%s) — removing.", exc)
            self._clear_worker_state()
            return

        job_id = str(state.get("job_id", ""))
        if not job_id:
            _log.warning("worker_state.json missing job_id — removing stale crash-recovery state.")
            self._clear_worker_state()
            return

        sp = str(state.get("source_path", ""))
        pending_done_report = state.get("pending_done_report")
        if isinstance(pending_done_report, dict) and str(pending_done_report.get("job_id", "") or "").strip():
            payload = dict(pending_done_report)
            payload.setdefault("worker_id", self._worker_id)
            _log.warning(
                "Crash recovery: retrying pending done report for job_id=%s.",
                str(payload.get("job_id", "")),
            )
            try:
                self._http_post("/api/done", payload)
            except Exception as exc:
                _log.warning("Crash recovery pending done-report failed: %s", _worker_diagnostic_preview(exc))
                return
            else:
                self._safe_log_cluster_event(
                    "pending-done-recovered",
                    level="WARN",
                    event="pending_done_recovered",
                    message=(
                        f"Retried pending done report after restart "
                        f"({Path(sp).name if sp else '(unknown source)'})"
                    ),
                    job_id=str(payload.get("job_id", "")),
                    source_path=sp,
                )
                self._clear_worker_state_after_accepted_report(
                    str(payload.get("job_id", "")),
                    "pending done recovery",
                )
                return

        if "pending_done_report" in state:
            _log.warning(
                "Ignoring malformed pending done report in worker_state.json for job_id=%s; falling back to crash-failed recovery.",
                job_id,
            )

        _log.warning(
            "Crash recovery: reporting job_id=%s as failed to coordinator.", job_id
        )
        try:
            self._http_post(
                "/api/done",
                build_crash_recovery_done_request(job_id, self._worker_id).to_dict(),
            )
        except Exception as exc:
            _log.warning("Crash recovery done-report failed: %s", _worker_diagnostic_preview(exc))
            return
        else:
            # Only log success to the cluster — if the POST itself failed
            # the cluster log POST will fail too and we'll have nothing to
            # show.  The local Python log carries the failure.
            self._safe_log_cluster_event(
                "crash-recovered",
                level="WARN",
                event="crash_recovered",
                message=(
                    f"Reported orphaned job as failed after restart "
                    f"({Path(sp).name if sp else '(unknown source)'})"
                ),
                job_id=job_id,
                source_path=sp,
            )
            self._clear_worker_state_after_accepted_report(job_id, "crash recovery done")

    # ------------------------------------------------------------------
    # Worker state persistence
    # ------------------------------------------------------------------

    def _save_worker_state(self, job: ClaimedJob) -> None:
        """Write job identity to disk so crash recovery can report it on next start."""
        save_active_worker_state(
            self._state_path,
            job,
            save_state=save_worker_state,
            notify_status=self._notify_status,
            safe_log_cluster_event=self._safe_log_cluster_event,
            log=_log,
        )

    def _save_pending_done_report(self, job: ClaimedJob, payload: dict[str, Any]) -> bool:
        """Persist an exact done/release payload for retry after restart."""
        return save_pending_worker_report(
            self._state_path,
            job,
            payload,
            save_state=save_worker_state,
            notify_status=self._notify_status,
            safe_log_cluster_event=self._safe_log_cluster_event,
            log=_log,
        )

    def _clear_worker_state(self) -> bool:
        try:
            clear_worker_state(self._state_path)
        except Exception as exc:
            _log.warning("Failed to clear worker_state.json after coordinator state transition: %s", exc)
            return False
        return True

    def _clear_worker_state_after_accepted_report(self, job_id: str, report_context: str) -> None:
        """Best-effort cleanup after the coordinator accepted a terminal report."""
        try:
            cleared = self._clear_worker_state()
        except Exception as exc:
            _log.warning(
                "Coordinator accepted %s report for job %s, but worker_state cleanup failed; not saving a pending done report: %s",
                report_context,
                job_id,
                exc,
            )
            return
        if not cleared:
            _log.warning(
                "Coordinator accepted %s report for job %s, but worker_state cleanup failed; not saving a pending done report.",
                report_context,
                job_id,
            )

    # ------------------------------------------------------------------
    # Hot-swap methods — apply config changes without restarting the dispatcher
    # ------------------------------------------------------------------

    def update_auth_token(self, new_token: str) -> None:
        """Replace the bearer token used in outgoing requests immediately.

        Thread-safe: the poll loop reads ``_auth_token`` on each HTTP call
        so the new value is picked up on the very next request.
        """
        self._auth_token = new_token.strip()
        _log.info("WorkerDispatcher: auth token updated (hot-swap).")

    def update_coordinator_url(self, new_url: str) -> None:
        """Replace the coordinator base URL immediately. N17 — validates
        before swapping; raises ``ValueError`` on bad input so the UI
        can surface the problem instead of silently leaking the token.

        The poll loop uses ``_base_url`` on each HTTP call so the new URL
        is picked up on the next poll cycle.  The wakeup event fires so the
        change takes effect without waiting for the full sleep interval.
        """
        self._base_url = _validate_coordinator_url(new_url)
        _log.info("WorkerDispatcher: coordinator URL updated to %s (hot-swap).", self._base_url)
        self._wakeup.set()

    def set_status_callback(self, callback: "Callable[[str], None] | None") -> None:
        """Register a callback invoked from the poll thread after every attempt.

        The callback receives a single human-readable string describing the
        current worker state.  Since it runs on the poll thread, callers that
        need to update shared app state must marshal through the configured
        app callback scheduler.
        Pass ``None`` to remove the callback.
        """
        self._status_callback = callback

    def _notify_status(self, msg: str) -> None:
        """Internal: invoke the status callback if one is registered."""
        notify_status_callback(
            getattr(self, "_status_callback", None),
            msg,
            log=_log,
            diagnostic_preview=_worker_diagnostic_preview,
        )

    def _post_app_callback(self, name: str, callback: "Callable[[], None]") -> None:
        """Schedule an app callback through the configured app scheduler."""
        post_app_callback(self.app, name, callback)

    def _request_abort_reclaimed_job(self, job: ClaimedJob) -> None:
        """Ask the app callback scheduler to abort a job reclaimed by the coordinator."""
        request_abort_reclaimed_job(
            self.app,
            job,
            post_callback=self._post_app_callback,
            log=_log,
            diagnostic_preview=_worker_diagnostic_preview,
        )

    def _release_unstartable_claim(self, claim: ClaimResponse, reason: str) -> None:
        """Release a claimed job that cannot be converted into local work."""
        self._release_claim_identity(claim.job_id, claim.source_path, reason)

    def _release_claim_identity(self, job_id: str, source_path: str, reason: str) -> None:
        """Release a claimed job when only its wire identity is trustworthy."""
        reason_preview = _worker_diagnostic_preview(reason)
        try:
            self._http_post(
                "/api/done",
                build_release_done_request(job_id, self._worker_id).to_dict(),
            )
            self._notify_status(f"⚠ Released unstartable claim: {reason_preview[:80]}")
        except Exception as exc:
            failure_preview = _worker_diagnostic_preview(exc)
            _log.warning(
                "Failed to release unstartable claimed job %s after %s: %s",
                job_id[:8],
                reason_preview,
                failure_preview,
            )
            self._notify_status(f"⚠ Could not release unstartable claim: {failure_preview[:80]}")

    def _release_malformed_claim_response(self, resp: object, reason: str) -> bool:
        """Release an already-claimed job when the claim body cannot be parsed."""
        identity = malformed_claim_identity(resp)
        if identity is None:
            return False
        job_id, source_path = identity
        reason_preview = _worker_diagnostic_preview(reason)
        _log.warning(
            "Malformed claimed response for job %s; releasing claim: %s",
            job_id[:8],
            reason_preview,
        )
        self._safe_log_cluster_event(
            "malformed-claim",
            level="ERROR",
            event="claim_response_invalid",
            message=f"Worker could not parse claimed job response: {reason_preview}",
            job_id=job_id,
            source_path=source_path,
        )
        self._release_claim_identity(job_id, source_path, f"malformed claim response: {reason_preview}")
        return True

    # ------------------------------------------------------------------
    # Poll loop (background daemon thread)
    # ------------------------------------------------------------------

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
            # Don't sleep — let the busy-guard at the top of this loop
            # idle until the encode completes.

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    def _on_job_claimed(self, job: ClaimedJob) -> None:
        """Called by the poll thread right after a job is claimed.

        Saves crash-recovery state, starts the heartbeat thread, and
        schedules the encode on the app callback thread.
        """
        self._save_worker_state(job)
        self._job_reclaimed  = False
        self._last_heartbeat_failure_text = ""
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(job,),
            name="worker-heartbeat",
            daemon=True,
        )
        try:
            self._heartbeat_thread.start()
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.error("Failed to start worker heartbeat thread for job %s: %s", job.job_id, reason_preview)
            self._notify_status(f"⚠ Could not start heartbeat for claimed job: {reason_preview[:80]}")
            self._safe_log_cluster_event(
                "heartbeat-start-failed",
                level="ERROR",
                event="heartbeat_start_failed",
                message=f"Worker could not start heartbeat thread for claimed job: {reason_preview}",
                job_id=job.job_id,
                source_path=str(job.record.source_path),
            )
            self._do_release(job)
            return
        _log.info(
            "Job claimed: job_id=%s path=%s",
            job.job_id, job.record.source_path,
        )
        self._safe_log_cluster_event(
            "claim-received",
            level="INFO",
            event="claim_received",
            message=f"Picked up {Path(str(job.record.source_path)).name}",
            job_id=job.job_id,
            source_path=str(job.record.source_path),
        )

        # Schedule the encode on the app callback thread.
        try:
            self._post_app_callback(
                "worker-start-single-file",
                lambda: self.app._worker_start_single_file(job),
            )
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.error("Failed to schedule _worker_start_single_file: %s", reason_preview)
            self._notify_status(f"⚠ Could not schedule claimed job: {reason_preview[:80]}")
            # Release the job immediately so the coordinator can re-queue it.
            self._do_release(job)

    def _do_release(self, job: ClaimedJob) -> None:
        """Internal: POST /api/done with released=True and clean up local state."""
        self._stop_heartbeat()
        with self._active_job_lock:
            self._active_job = None
        payload = build_release_done_request(job.job_id, self._worker_id).to_dict()
        report_accepted = False
        pending_report_saved = False
        try:
            self._http_post("/api/done", payload)
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.warning("POST /api/done (internal release) failed: %s", reason_preview)
            pending_report_saved = self._save_pending_done_report(job, payload)
            self._notify_status(f"⚠ Release report failed: {reason_preview[:80]}")
        else:
            report_accepted = True
            self._clear_worker_state_after_accepted_report(job.job_id, "internal release")
        if report_accepted:
            _log.info("Job %s internal release report accepted by coordinator.", job.job_id)
        elif pending_report_saved:
            _log.info("Job %s internal release report pending retry after coordinator POST failure.", job.job_id)
        else:
            _log.warning(
                "Job %s internal release report could not be saved for pending retry after coordinator POST failure.",
                job.job_id,
            )

    # ------------------------------------------------------------------
    # Heartbeat loop (per-job daemon thread)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # QueueDispatcher ABC implementation
    # ------------------------------------------------------------------

    def claim_next(self) -> ClaimedJob | None:
        """In worker mode, claiming is driven by the background poll thread.

        This method always returns ``None``; the poll loop schedules work
        on the app callback thread through the app's UI callback queue.
        """
        return None

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
        """Report job completion to the coordinator and clean up local state."""
        self._stop_heartbeat()
        with self._active_job_lock:
            self._active_job = None
        payload = build_completion_done_request(
            job,
            self._worker_id,
            success=success,
            output_path=output_path,
            elapsed_seconds=elapsed_seconds,
            output_size_bytes=output_size_bytes,
            error=error,
            completion_status=completion_status,
            publish_state=publish_state,
            publish_mode=publish_mode,
            route=route,
            queue_terminal=queue_terminal,
        ).to_dict()
        report_accepted = False
        pending_report_saved = False
        try:
            self._http_post("/api/done", payload)
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.warning("POST /api/done failed: %s", reason_preview)
            pending_report_saved = self._save_pending_done_report(job, payload)
            self._notify_status(f"⚠ Done report failed: {reason_preview[:80]}")
        else:
            report_accepted = True
            self._clear_worker_state_after_accepted_report(job.job_id, "done")
        if report_accepted:
            _log.info(
                "Job %s %s report accepted by coordinator.",
                job.job_id,
                "done" if success else "failed",
            )
        elif pending_report_saved:
            _log.info("Job %s completion report pending retry after coordinator POST failure.", job.job_id)
        else:
            _log.warning(
                "Job %s completion report could not be saved for pending retry after coordinator POST failure.",
                job.job_id,
            )
        event_context, event_kwargs = completion_cluster_event(
            job,
            success=success,
            elapsed_seconds=elapsed_seconds,
            output_size_bytes=output_size_bytes,
            completion_status=completion_status,
            error=error,
            publish_state=publish_state,
            queue_terminal=queue_terminal,
        )
        self._safe_log_cluster_event(event_context, **event_kwargs)

    def release(self, job: ClaimedJob) -> None:
        """Return the job to the coordinator queue without a failure record.

        Called on clean shutdown when the encode is still in flight.
        """
        self._stop_heartbeat()
        with self._active_job_lock:
            self._active_job = None
        payload = build_release_done_request(job.job_id, self._worker_id).to_dict()
        report_accepted = False
        pending_report_saved = False
        try:
            self._http_post("/api/done", payload)
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.warning("POST /api/done (release) failed: %s", reason_preview)
            pending_report_saved = self._save_pending_done_report(job, payload)
            self._notify_status(f"⚠ Release report failed: {reason_preview[:80]}")
        else:
            report_accepted = True
            self._clear_worker_state_after_accepted_report(job.job_id, "release")
        if report_accepted:
            _log.info("Job %s release report accepted by coordinator.", job.job_id)
        elif pending_report_saved:
            _log.info("Job %s release report pending retry after coordinator POST failure.", job.job_id)
        else:
            _log.warning(
                "Job %s release report could not be saved for pending retry after coordinator POST failure.",
                job.job_id,
            )
        event_context, event_kwargs = release_cluster_event(job)
        self._safe_log_cluster_event(event_context, **event_kwargs)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_active_job(self) -> ClaimedJob | None:
        """Return the currently-active job, or ``None`` if idle."""
        with self._active_job_lock:
            return self._active_job

    @property
    def coordinator_url(self) -> str:
        return self._base_url

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Module-level helpers (keep WorkerDispatcher free of model imports)
# ---------------------------------------------------------------------------

def _safe_hostname() -> str:
    """Return the machine hostname, or 'worker' if it cannot be determined."""
    try:
        return socket.gethostname() or "worker"
    except Exception as exc:
        _log.warning("Worker hostname lookup failed; using fallback worker name: %s", exc)
        return "worker"
