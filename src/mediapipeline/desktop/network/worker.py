"""
network.worker
==============
``WorkerDispatcher`` — polls a remote coordinator for jobs and executes them
by launching the PowerShell pipeline with ``-SingleFile <path>``.

Phase 2 implementation.
"""
from __future__ import annotations

import hashlib
import logging
import socket
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from mediapipeline.core.network.url_policy import redact_network_secret_text

from ..config_keys import (
    KEY_WORKER_AUTH_TOKEN,
    KEY_WORKER_COORDINATOR_URL,
    KEY_WORKER_ENCODER_MAP,
    KEY_WORKER_HONOR_COORDINATOR_POLICY,
    KEY_WORKER_NAME,
    KEY_WORKER_POLL_INTERVAL_SECS,
    KEY_WORKER_SOURCE_PATH_MAP,
)
from .coordinator_url import validate_coordinator_url as _validate_coordinator_url
from .diagnostics import diagnostic_preview as _worker_diagnostic_preview
from .dispatcher import ClaimedJob, QueueDispatcher
from .worker_claims import WorkerClaimMixin
from .worker_http import WorkerHttpMixin
from .worker_loops import WorkerLoopMixin
from .http_json import HTTP_MAX_RESPONSE_BYTES as _HTTP_MAX_RESPONSE_BYTES
from .http_json import HTTP_TIMEOUT as _HTTP_TIMEOUT
from .http_json import http_read_capped as _http_read_capped
from .library_roots import (
    auto_source_path_map_from_libraries,
    merge_manual_and_auto_path_maps,
    resolve_worker_library_relative_path,
)
from .path_map import apply_source_path_map, parse_source_path_map
from .poll_policy import resolve_worker_poll_interval
from .processing_policy import worker_encoder_map_descriptor, worker_honor_coordinator_policy_enabled
from .protocol import ClaimResponse, LogEntryRequest
from .worker_record import make_queue_record as _make_queue_record
from .worker_parts.reporting import (
    is_unauthorized_http_error as _is_unauthorized_http_error,  # noqa: F401 - compatibility re-export
    notify_status_callback,
    post_app_callback,
)
from .worker_state import WorkerStateMixin
from .worker_state import atomic_write_text as _atomic_write_text

if TYPE_CHECKING:
    from ..app import MediaPipelineApp

_log = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL = 30   # seconds between heartbeats
# HTTP timeout and response-size caps live in network.http_json and are
# imported here under their historical names for compatibility.


def _fingerprint_text(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def _path_map_fingerprint(mappings: list[tuple[str, str]]) -> str:
    if not mappings:
        return ""
    material = "\n".join(f"{source}\0{target}" for source, target in mappings)
    return _fingerprint_text(material)


class WorkerDispatcher(
    WorkerHttpMixin,
    WorkerStateMixin,
    WorkerClaimMixin,
    WorkerLoopMixin,
    QueueDispatcher,
):
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

    def __init__(self, app: "MediaPipelineApp", *, start_polling: bool = True) -> None:
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
        self._poll_interval = resolve_worker_poll_interval(config.get(KEY_WORKER_POLL_INTERVAL_SECS))
        self._worker_encoder_map = str(config.get(KEY_WORKER_ENCODER_MAP, "") or "").strip()
        self._worker_honor_coordinator_policy = worker_honor_coordinator_policy_enabled(config)

        # Source path mapping: rewrite coordinator paths to local-reachable ones.
        # Parsed once at construction; callers can hot-swap via update_source_path_map().
        self._manual_source_path_map: list[tuple[str, str]] = self._parse_source_path_map(
            str(config.get(KEY_WORKER_SOURCE_PATH_MAP, "") or "").strip()
        )
        self._auto_source_path_map: list[tuple[str, str]] = []
        self._source_path_map: list[tuple[str, str]] = self._combined_source_path_map()
        self._library_auto_map_last_refresh = 0.0
        self._library_auto_map_refresh_seconds = 300.0
        self._library_auto_map_last_error = ""

        # State path for crash recovery — same directory as the app state file.
        svc = getattr(app, "service", None)
        state_dir = (
            Path(svc.app_state_path).parent
            if svc and hasattr(svc, "app_state_path")
            else Path.home()
        )
        self._state_path: Path = state_dir / "worker_state.json"
        self._worker_state_startup_error = ""

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
        self._poll_started = False
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

        if start_polling:
            self.start_polling()

    def start_polling(self) -> None:
        """Start the background claim poller after provider attachment."""
        if getattr(self, "_poll_started", False):
            return
        if self._poll_thread is None:
            self._poll_thread = threading.Thread(
                target=self._poll_loop, name="worker-poll", daemon=True
            )
        try:
            self._poll_thread.start()
        except Exception as exc:
            self._poll_thread = None
            _log.error("Could not start worker poll thread for coordinator %s: %s", self._base_url, exc)
            raise RuntimeError(f"Could not start worker poll thread for coordinator {self._base_url}: {exc}") from exc
        self._poll_started = True
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
        safe_event = redact_network_secret_text(event)
        safe_message = redact_network_secret_text(message)
        safe_job_id = redact_network_secret_text(job_id)
        safe_source_path = redact_network_secret_text(source_path)
        source_display = f"(source={Path(safe_source_path).name})" if safe_source_path else ""
        _log.log(py_level, "[cluster:%s] %s %s %s", safe_event, safe_message,
                 f"(job={safe_job_id[:8]})" if safe_job_id else "", source_display)

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
                _log.warning("cluster log POST failed for event %s: %s", safe_event, _worker_diagnostic_preview(exc))

        try:
            threading.Thread(target=_send, name="cluster-log-post", daemon=True).start()
        except Exception as exc:
            _log.warning(
                "Failed to start cluster log POST thread for event %s: %s",
                safe_event,
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
        _base_url, _auth_token, mappings = self._runtime_settings_snapshot()
        return apply_source_path_map(path, mappings)

    def _runtime_settings_snapshot(self) -> tuple[str, str, list[tuple[str, str]]]:
        """Return a consistent URL/token/path-map snapshot for the poll loop."""
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            return (
                str(getattr(self, "_base_url", "") or ""),
                str(getattr(self, "_auth_token", "") or ""),
                list(getattr(self, "_source_path_map", []) or []),
            )
        with lock:
            return (
                str(getattr(self, "_base_url", "") or ""),
                str(getattr(self, "_auth_token", "") or ""),
                list(getattr(self, "_source_path_map", []) or []),
            )

    def _combined_source_path_map(self) -> list[tuple[str, str]]:
        return merge_manual_and_auto_path_maps(
            list(getattr(self, "_manual_source_path_map", []) or []),
            list(getattr(self, "_auto_source_path_map", []) or []),
        )

    def _worker_config(self) -> dict[str, Any]:
        app = getattr(self, "app", None)
        resolved = getattr(app, "resolved", None)
        config = getattr(resolved, "config_data", {}) if resolved is not None else {}
        return dict(config or {})

    def update_source_path_map(self, raw: str) -> None:
        """Hot-swap the source path map without restarting the dispatcher.

        Called from the Network tab when the user edits WorkerSourcePathMap
        and wants the change applied immediately.
        """
        mappings = self._parse_source_path_map((raw or "").strip())
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            self._manual_source_path_map = mappings
            self._source_path_map = self._combined_source_path_map()
        else:
            with lock:
                self._manual_source_path_map = mappings
                self._source_path_map = self._combined_source_path_map()
        _log.info(
            "Worker source path map updated (hot-swap, manual=%d effective=%d entries).",
            len(mappings),
            len(self._source_path_map),
        )
        wakeup = getattr(self, "_wakeup", None)
        if wakeup is not None:
            wakeup.set()

    def update_library_auto_map(self, coordinator_libraries: list[dict[str, Any]]) -> None:
        """Hot-swap the auto-derived library path map without restarting."""
        auto_mappings = auto_source_path_map_from_libraries(coordinator_libraries, self._worker_config())
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            self._auto_source_path_map = auto_mappings
            self._source_path_map = self._combined_source_path_map()
            effective_count = len(self._source_path_map)
        else:
            with lock:
                self._auto_source_path_map = auto_mappings
                self._source_path_map = self._combined_source_path_map()
                effective_count = len(self._source_path_map)
        _log.info(
            "Worker library auto-map refreshed (auto=%d effective=%d entries).",
            len(auto_mappings),
            effective_count,
        )

    def refresh_library_auto_map(self) -> bool:
        """Fetch coordinator library roots and refresh the auto-derived path map."""
        response = self._http_get("/api/libraries")
        libraries = response.get("libraries", [])
        if not isinstance(libraries, list):
            raise RuntimeError("Coordinator /api/libraries response did not include a libraries list.")
        self.update_library_auto_map([dict(item) for item in libraries if isinstance(item, dict)])
        self._library_auto_map_last_error = ""
        return True

    def _maybe_refresh_library_auto_map(self, *, force: bool = False) -> None:
        interval = max(60.0, float(getattr(self, "_library_auto_map_refresh_seconds", 300.0) or 300.0))
        now = time.monotonic()
        last_refresh = float(getattr(self, "_library_auto_map_last_refresh", 0.0) or 0.0)
        if not force and last_refresh > 0 and now - last_refresh < interval:
            return
        self._library_auto_map_last_refresh = now
        try:
            self.refresh_library_auto_map()
        except Exception as exc:
            err_text = _worker_diagnostic_preview(exc)
            if err_text != getattr(self, "_library_auto_map_last_error", ""):
                _log.warning("Worker library auto-map refresh failed; manual path map remains active: %s", err_text)
                self._library_auto_map_last_error = err_text
            else:
                _log.debug("Worker library auto-map refresh still failing: %s", err_text)

    def resolve_claim_source_path(self, claim: ClaimResponse) -> tuple[str, str]:
        """Resolve the source path for a claim, preferring library-relative fields."""
        library_path = resolve_worker_library_relative_path(
            self._worker_config(),
            claim.library_id,
            claim.relative_path,
        )
        if library_path:
            return library_path, "library_relative"
        return self._apply_path_map(claim.source_path), "path_map"

    # ------------------------------------------------------------------
    # Hot-swap methods — apply config changes without restarting the dispatcher
    # ------------------------------------------------------------------

    def update_auth_token(self, new_token: str) -> None:
        """Replace the bearer token used in outgoing requests immediately.

        Thread-safe: the poll loop reads ``_auth_token`` on each HTTP call
        so the new value is picked up on the very next request.
        """
        token = new_token.strip()
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            self._auth_token = token
        else:
            with lock:
                self._auth_token = token
        _log.info("WorkerDispatcher: auth token updated (hot-swap).")
        wakeup = getattr(self, "_wakeup", None)
        if wakeup is not None:
            wakeup.set()

    def update_coordinator_url(self, new_url: str) -> None:
        """Replace the coordinator base URL immediately. N17 — validates
        before swapping; raises ``ValueError`` on bad input so the UI
        can surface the problem instead of silently leaking the token.

        The poll loop uses ``_base_url`` on each HTTP call so the new URL
        is picked up on the next poll cycle.  The wakeup event fires so the
        change takes effect without waiting for the full sleep interval.
        """
        validated_url = _validate_coordinator_url(new_url)
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            old_url = str(getattr(self, "_base_url", "") or "")
            self._base_url = validated_url
        else:
            with lock:
                old_url = str(getattr(self, "_base_url", "") or "")
                self._base_url = validated_url
        _log.info(
            "WorkerDispatcher: coordinator URL hot-swapped %s -> %s.",
            old_url or "(unset)",
            validated_url,
        )
        wakeup = getattr(self, "_wakeup", None)
        if wakeup is not None:
            wakeup.set()

    def update_worker_encoder_map(self, new_map: str) -> None:
        """Replace the worker-owned family->encoder map immediately."""
        raw = str(new_map or "").strip()
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            self._worker_encoder_map = raw
        else:
            with lock:
                self._worker_encoder_map = raw
        descriptor = worker_encoder_map_descriptor(raw)
        _log.info(
            "WorkerDispatcher: encoder map hot-swapped (entries=%d valid=%s).",
            int(descriptor.get("worker_encoder_map_entries") or 0),
            "yes" if descriptor.get("worker_encoder_map_valid") else "no",
        )
        wakeup = getattr(self, "_wakeup", None)
        if wakeup is not None:
            wakeup.set()

    def update_honor_coordinator_policy(self, raw_value: str) -> None:
        """Replace the worker's coordinator-policy authority flag immediately."""
        enabled = worker_honor_coordinator_policy_enabled({KEY_WORKER_HONOR_COORDINATOR_POLICY: raw_value})
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            self._worker_honor_coordinator_policy = enabled
        else:
            with lock:
                self._worker_honor_coordinator_policy = enabled
        _log.info(
            "WorkerDispatcher: coordinator policy authority hot-swapped (%s).",
            "enabled" if enabled else "disabled",
        )
        wakeup = getattr(self, "_wakeup", None)
        if wakeup is not None:
            wakeup.set()

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

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_active_job(self) -> ClaimedJob | None:
        """Return the currently-active job, or ``None`` if idle."""
        with self._active_job_lock:
            return self._active_job

    def runtime_descriptor(self) -> dict[str, Any]:
        """Return token-safe live settings evidence for drift detection."""
        base_url, auth_token, mappings = self._runtime_settings_snapshot()
        lock = getattr(self, "_active_job_lock", None)
        if lock is None:
            honor_policy = bool(getattr(self, "_worker_honor_coordinator_policy", False))
            encoder_map = str(getattr(self, "_worker_encoder_map", "") or "")
            manual_source = getattr(self, "_manual_source_path_map", None)
            manual_mappings = list(manual_source if manual_source is not None else mappings)
            auto_mappings = list(getattr(self, "_auto_source_path_map", []) or [])
        else:
            with lock:
                honor_policy = bool(getattr(self, "_worker_honor_coordinator_policy", False))
                encoder_map = str(getattr(self, "_worker_encoder_map", "") or "")
                manual_source = getattr(self, "_manual_source_path_map", None)
                manual_mappings = list(manual_source if manual_source is not None else mappings)
                auto_mappings = list(getattr(self, "_auto_source_path_map", []) or [])
        return {
            "schema_version": "desktop_network_worker_runtime_descriptor.v1",
            "coordinator_url": base_url,
            "token_fingerprint": _fingerprint_text(auth_token),
            "manual_path_map_entries": len(manual_mappings),
            "manual_path_map_fingerprint": _path_map_fingerprint(manual_mappings),
            "auto_path_map_entries": len(auto_mappings),
            "auto_path_map_fingerprint": _path_map_fingerprint(auto_mappings),
            "auto_path_map_active": bool(auto_mappings),
            "effective_path_map_entries": len(mappings),
            "effective_path_map_fingerprint": _path_map_fingerprint(mappings),
            "path_map_entries": len(mappings),
            "path_map_fingerprint": _path_map_fingerprint(mappings),
            "honor_coordinator_policy": honor_policy,
            **worker_encoder_map_descriptor(encoder_map),
            "read_only": True,
        }

    @property
    def coordinator_url(self) -> str:
        base_url, _auth_token, _mappings = self._runtime_settings_snapshot()
        return base_url


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
