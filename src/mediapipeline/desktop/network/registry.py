"""
network.registry
================
``InFlightRegistry`` — coordinator-side tracking of claimed-but-not-yet-done
encode jobs.

Thread safety: every public method acquires ``_lock`` before touching shared
state.  Callers must not hold any other lock when calling in here to avoid
deadlocks.

Phase 1: full implementation.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .failure_reasons import REASON_ENCODE_ERROR, bounded_failure_reason, normalize_failure_reason_code
from .json_policy import loads_strict_json
from .protocol import (
    WorkerEntry,
    coerce_finite_float,
    coerce_library_id_list,
    coerce_nonnegative_int,
    coerce_progress_percent,
)

_log = logging.getLogger(__name__)


def _default_worker_stats(worker_id: str, worker_name: str = "") -> dict[str, Any]:
    safe_name = str(worker_name or "").strip() or worker_id[:8]
    return {
        "name": safe_name,
        "files": 0,
        "gb": 0.0,
        "secs": 0.0,
        "last_seen": "",
        "last_failure_reason_code": "",
        "last_failure_reason": "",
        "last_failure_job_id": "",
        "last_failure_source_path": "",
        "last_failure_at": "",
        "failure_streak_reason_code": "",
        "failure_streak_count": 0,
        "worker_misconfigured_reason_code": "",
        "worker_misconfigured_at": "",
        "accessible_library_ids": [],
    }


def _ensure_worker_stats_fields(stats: dict[str, Any], worker_id: str, worker_name: str = "") -> dict[str, Any]:
    defaults = _default_worker_stats(worker_id, worker_name)
    for key, value in defaults.items():
        stats.setdefault(key, value)
    if worker_name:
        stats["name"] = str(worker_name)
    return stats


def _safe_worker_stats(worker_id: str, raw_stats: Any) -> dict[str, Any]:
    """Return worker-board-safe cumulative stats for one worker."""
    if not isinstance(raw_stats, dict):
        _log.warning("Malformed worker stats for %s while building worker snapshot; using zero metrics.", worker_id)
        return _default_worker_stats(worker_id)

    name = str(raw_stats.get("name", "") or worker_id[:8])
    safe: dict[str, Any] = _default_worker_stats(worker_id, name)
    safe["last_seen"] = str(raw_stats.get("last_seen", "") or "")
    safe["last_failure_reason_code"] = normalize_failure_reason_code(raw_stats.get("last_failure_reason_code", ""))
    safe["last_failure_reason"] = bounded_failure_reason(raw_stats.get("last_failure_reason", ""))
    safe["last_failure_job_id"] = str(raw_stats.get("last_failure_job_id", "") or "")
    safe["last_failure_source_path"] = str(raw_stats.get("last_failure_source_path", "") or "")
    safe["last_failure_at"] = str(raw_stats.get("last_failure_at", "") or "")
    safe["failure_streak_reason_code"] = normalize_failure_reason_code(raw_stats.get("failure_streak_reason_code", ""))
    safe["worker_misconfigured_reason_code"] = normalize_failure_reason_code(raw_stats.get("worker_misconfigured_reason_code", ""))
    safe["worker_misconfigured_at"] = str(raw_stats.get("worker_misconfigured_at", "") or "")
    safe["accessible_library_ids"] = coerce_library_id_list(raw_stats.get("accessible_library_ids", []))
    try:
        safe["files"] = coerce_nonnegative_int(raw_stats.get("files", 0), "files")
    except Exception as exc:
        _log.warning("Invalid worker stats files for %s while building worker snapshot; using 0: %s", worker_id, exc)
    try:
        safe["gb"] = coerce_finite_float(raw_stats.get("gb", 0.0), "gb", minimum=0.0)
    except Exception as exc:
        _log.warning("Invalid worker stats gb for %s while building worker snapshot; using 0.0: %s", worker_id, exc)
    try:
        safe["secs"] = coerce_finite_float(raw_stats.get("secs", 0.0), "secs", minimum=0.0)
    except Exception as exc:
        _log.warning("Invalid worker stats secs for %s while building worker snapshot; using 0.0: %s", worker_id, exc)
    try:
        safe["failure_streak_count"] = coerce_nonnegative_int(raw_stats.get("failure_streak_count", 0), "failure_streak_count")
    except Exception as exc:
        _log.warning("Invalid worker failure streak for %s while building worker snapshot; using 0: %s", worker_id, exc)
    return safe


def _safe_snapshot_progress(worker_id: str, value: Any) -> float:
    """Return worker-board-safe progress for one active job."""
    try:
        return coerce_progress_percent(value)
    except Exception as exc:
        _log.warning("Invalid worker progress for %s while building worker snapshot; using 0.0: %s", worker_id, exc)
        return 0.0


def _failure_ledger_key(worker_id: str, source_path: str) -> str:
    return f"{str(worker_id or '').strip()}\0{str(source_path or '').strip()}"


def _safe_failure_reason_code(value: Any) -> str:
    return normalize_failure_reason_code(value) or REASON_ENCODE_ERROR


def _safe_failure_ledger_entry(raw_entry: Any) -> dict[str, Any] | None:
    if not isinstance(raw_entry, dict):
        return None
    worker_id = str(raw_entry.get("worker_id", "") or "").strip()
    source_path = str(raw_entry.get("source_path", "") or "").strip()
    if not worker_id or not source_path:
        return None
    try:
        count = coerce_nonnegative_int(raw_entry.get("consecutive_count", 0), "consecutive_count")
    except Exception:
        count = 0
    return {
        "worker_id": worker_id,
        "worker_name": str(raw_entry.get("worker_name", "") or ""),
        "source_path": source_path,
        "reason_code": _safe_failure_reason_code(raw_entry.get("reason_code", "")),
        "reason": bounded_failure_reason(raw_entry.get("reason", "")),
        "consecutive_count": count,
        "first_failed_at": str(raw_entry.get("first_failed_at", "") or ""),
        "last_failed_at": str(raw_entry.get("last_failed_at", "") or ""),
        "last_job_id": str(raw_entry.get("last_job_id", "") or ""),
        "alert_emitted": bool(raw_entry.get("alert_emitted", False)),
    }


# ---------------------------------------------------------------------------
# InFlightJob
# ---------------------------------------------------------------------------

@dataclass
class InFlightJob:
    """A single job that has been claimed by a worker but not yet completed."""

    job_id:            str
    worker_id:         str
    worker_name:       str
    source_path:       str
    claimed_at:        str     # ISO-8601
    last_heartbeat:    str     # ISO-8601
    progress_percent:  float = 0.0
    current_stage:     str   = ""
    encode_config:     dict  = field(default_factory=dict)
    priority:          bool  = False
    estimated_size_gb: float = 0.0
    accessible_library_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id":            self.job_id,
            "worker_id":         self.worker_id,
            "worker_name":       self.worker_name,
            "source_path":       self.source_path,
            "claimed_at":        self.claimed_at,
            "last_heartbeat":    self.last_heartbeat,
            "progress_percent":  self.progress_percent,
            "current_stage":     self.current_stage,
            "encode_config":     self.encode_config,
            "priority":          self.priority,
            "estimated_size_gb": self.estimated_size_gb,
            "accessible_library_ids": coerce_library_id_list(self.accessible_library_ids),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "InFlightJob":
        return cls(
            job_id=str(d.get("job_id", "")),
            worker_id=str(d.get("worker_id", "")),
            worker_name=str(d.get("worker_name", "")),
            source_path=str(d.get("source_path", "")),
            claimed_at=str(d.get("claimed_at", "")),
            last_heartbeat=str(d.get("last_heartbeat", "")),
            progress_percent=coerce_progress_percent(d.get("progress_percent", 0.0)),
            current_stage=str(d.get("current_stage", "")),
            encode_config=dict(d.get("encode_config", {})),
            priority=bool(d.get("priority", False)),
            estimated_size_gb=coerce_finite_float(d.get("estimated_size_gb", 0.0), "estimated_size_gb", minimum=0.0),
            accessible_library_ids=coerce_library_id_list(d.get("accessible_library_ids", [])),
        )


# ---------------------------------------------------------------------------
# InFlightRegistry
# ---------------------------------------------------------------------------

class InFlightRegistry:
    """Thread-safe coordinator-side registry of in-progress encode jobs.

    Coordinator flow
    ----------------
    1. Worker calls ``GET /api/claim``.
    2. Coordinator calls :meth:`claim` — returns ``False`` if the path is
       already taken; caller picks the next file and retries.
    3. Worker sends ``POST /api/heartbeat`` every 30 s.
       Coordinator calls :meth:`heartbeat` — returns ``"reclaimed"`` if the
       job has been taken back by the stale-reaper; worker aborts.
    4. Worker calls ``POST /api/done``.
       Coordinator calls :meth:`complete` (success or failure) or
       :meth:`unclaim` (clean release / shutdown).
    """

    # N10 — keep recently-completed source paths quarantined briefly so a
    # second worker calling /api/claim can't re-pick a path that was
    # just dropped from `_claimed_paths` but hasn't yet been removed
    # from the queue_records list (which lives on the local service thread and
    # mutates asynchronously via root.after). 30s is plenty for the UI
    # thread to process the removal even under heavy load; older entries
    # are GC'd lazily by `is_in_flight` so the dict can't grow unbounded.
    _RECENT_COMPLETION_TTL_SECONDS = 30.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()
        self._jobs: dict[str, InFlightJob] = {}        # job_id  → job
        self._claimed_paths: dict[str, str] = {}       # source_path → job_id
        # N10 — source_path → epoch-seconds completion time. Read by
        # is_in_flight() which lazy-prunes stale entries on access.
        self._recent_completions: dict[str, float] = {}
        self.session_completed: int = 0
        self.session_failed: int    = 0
        # Per-worker cumulative session stats plus last terminal failure reason.
        self._worker_stats: dict[str, dict[str, Any]] = {}
        # Worker/source failure ledger used to suppress repeated same-reason
        # redispatch loops without mutating source media or queue records.
        self._failure_ledger: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def claim(
        self,
        *,
        job_id: str,
        worker_id: str,
        worker_name: str,
        source_path: str,
        encode_config: dict,
        priority: bool = False,
        estimated_size_gb: float = 0.0,
        accessible_library_ids: list[str] | None = None,
    ) -> bool:
        """Atomically claim *source_path* for *worker_id*.

        Returns ``False`` if *source_path* is already claimed (another
        worker beat this one to it).  The caller should scan for the next
        unclaimed record and try again.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            if source_path in self._claimed_paths:
                return False
            try:
                safe_estimated_size_gb = coerce_finite_float(
                    estimated_size_gb,
                    "estimated_size_gb",
                    minimum=0.0,
                )
            except Exception as exc:
                _log.warning(
                    "Invalid estimated_size_gb for claimed job %s (%s); using 0.0: %s",
                    job_id[:8],
                    source_path,
                    exc,
                )
                safe_estimated_size_gb = 0.0
            safe_library_ids = coerce_library_id_list(accessible_library_ids or [])
            job = InFlightJob(
                job_id=job_id,
                worker_id=worker_id,
                worker_name=worker_name,
                source_path=source_path,
                claimed_at=now,
                last_heartbeat=now,
                encode_config=encode_config,
                priority=priority,
                estimated_size_gb=safe_estimated_size_gb,
                accessible_library_ids=safe_library_ids,
            )
            self._jobs[job_id] = job
            self._claimed_paths[source_path] = job_id

            safe_worker_id = str(worker_id or "").strip()
            if safe_worker_id:
                stats = self._worker_stats.setdefault(
                    safe_worker_id,
                    _default_worker_stats(safe_worker_id, worker_name),
                )
                _ensure_worker_stats_fields(stats, safe_worker_id, worker_name)
                stats["name"] = worker_name or str(stats.get("name", "") or safe_worker_id[:8])
                stats["last_seen"] = now
                stats["accessible_library_ids"] = safe_library_ids
        return True

    def note_worker_seen(
        self,
        *,
        worker_id: str,
        worker_name: str,
        accessible_library_ids: list[str] | None = None,
    ) -> None:
        """Record that a worker reached the coordinator, even if no job is claimable."""
        now = datetime.now(timezone.utc).isoformat()
        safe_worker_id = str(worker_id or "").strip()
        if not safe_worker_id:
            return
        safe_worker_name = str(worker_name or "").strip() or safe_worker_id[:8]
        with self._lock:
            stats = self._worker_stats.setdefault(safe_worker_id, _default_worker_stats(safe_worker_id, safe_worker_name))
            _ensure_worker_stats_fields(stats, safe_worker_id, safe_worker_name)
            stats["name"] = safe_worker_name or str(stats.get("name", "") or safe_worker_id[:8])
            stats["last_seen"] = now
            if accessible_library_ids is not None:
                stats["accessible_library_ids"] = coerce_library_id_list(accessible_library_ids)

    def heartbeat(
        self,
        job_id: str,
        worker_id: str,
        *,
        progress_percent: float = 0.0,
        current_stage: str = "",
        accessible_library_ids: list[str] | None = None,
    ) -> str:
        """Update heartbeat for *job_id*.

        Returns ``"ok"`` when the heartbeat was accepted, ``"reclaimed"``
        when the job no longer exists or belongs to a different worker
        (the stale-reaper or a duplicate claim took it back).
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.worker_id != worker_id:
                return "reclaimed"
            job.last_heartbeat   = datetime.now(timezone.utc).isoformat()
            job.progress_percent = coerce_progress_percent(progress_percent)
            job.current_stage    = current_stage
            if accessible_library_ids is not None:
                safe_library_ids = coerce_library_id_list(accessible_library_ids)
                job.accessible_library_ids = safe_library_ids
                stats = self._worker_stats.setdefault(
                    worker_id,
                    _default_worker_stats(worker_id, job.worker_name),
                )
                _ensure_worker_stats_fields(stats, worker_id, job.worker_name)
                stats["name"] = job.worker_name or stats["name"]
                stats["last_seen"] = job.last_heartbeat
                stats["accessible_library_ids"] = safe_library_ids
        return "ok"

    def complete(
        self,
        job_id: str,
        worker_id: str,
        *,
        success: bool,
        elapsed_seconds: float = 0.0,
        output_size_bytes: int = 0,
        reason_code: str = "",
        reason: str = "",
    ) -> "InFlightJob | None":
        """Remove *job_id* from in-flight and increment the session counter.

        When *success* is ``True`` and *elapsed_seconds* > 0, the
        per-worker stats table is updated so the Worker Board can show
        cumulative throughput.

        Returns the completed ``InFlightJob`` or ``None`` if the job was
        not found (already reclaimed / completed) or if *worker_id* does
        not match the recorded owner of the job — a foreign worker may
        not close someone else's encode (N2).  Empty *worker_id* is
        treated as ``None`` to keep crash-recovery / coordinator-internal
        callers (which have no specific worker identity) functional.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            # N2 fix — verify ownership before mutation. Empty worker_id
            # is allowed for backward compat with internal callers; any
            # non-empty mismatch is rejected so a misbehaving / spoofing
            # worker can't close another worker's job.
            requester = (worker_id or "").strip()
            if requester and requester != job.worker_id:
                _log.warning(
                    "Rejecting complete() for job %s: requester worker_id=%r "
                    "does not match owner %r",
                    job_id[:8], requester[:32], job.worker_id[:32],
                )
                return None
            del self._jobs[job_id]
            self._claimed_paths.pop(job.source_path, None)
            # N10 — quarantine the source path for the grace TTL so
            # is_in_flight() still says "yes" while the app callback
            # finishes removing this record from queue_records. Without
            # this, a concurrent /api/claim from another worker would
            # walk the not-yet-pruned queue list, see is_in_flight()
            # return False (already cleared above), and re-claim the
            # same source.
            self._recent_completions[job.source_path] = time.monotonic()
            now = datetime.now(timezone.utc).isoformat()
            ledger_key = _failure_ledger_key(job.worker_id, job.source_path)
            if success:
                self._failure_ledger.pop(ledger_key, None)
                self.session_completed += 1
                # Update per-worker performance stats.
                stats = self._worker_stats.setdefault(
                    job.worker_id,
                    _default_worker_stats(job.worker_id, job.worker_name),
                )
                _ensure_worker_stats_fields(stats, job.worker_id, job.worker_name)
                stats["name"]  = job.worker_name or stats["name"]
                stats["last_seen"] = now
                stats["files"] += 1
                stats["failure_streak_reason_code"] = ""
                stats["failure_streak_count"] = 0
                stats["worker_misconfigured_reason_code"] = ""
                stats["worker_misconfigured_at"] = ""
                # Prefer output_size_bytes when provided; fall back to estimate.
                gb = (
                    output_size_bytes / (1024 ** 3)
                    if output_size_bytes > 0
                    else job.estimated_size_gb
                )
                stats["gb"]   += gb
                stats["secs"] += max(0.0, elapsed_seconds)
            else:
                self.session_failed += 1
                safe_reason_code = _safe_failure_reason_code(reason_code)
                safe_reason = bounded_failure_reason(reason)
                previous_entry = self._failure_ledger.get(ledger_key)
                if previous_entry and previous_entry.get("reason_code") == safe_reason_code:
                    consecutive_count = int(previous_entry.get("consecutive_count", 0) or 0) + 1
                    first_failed_at = str(previous_entry.get("first_failed_at", "") or now)
                    alert_emitted = bool(previous_entry.get("alert_emitted", False))
                else:
                    consecutive_count = 1
                    first_failed_at = now
                    alert_emitted = False
                self._failure_ledger[ledger_key] = {
                    "worker_id": job.worker_id,
                    "worker_name": job.worker_name,
                    "source_path": job.source_path,
                    "reason_code": safe_reason_code,
                    "reason": safe_reason,
                    "consecutive_count": consecutive_count,
                    "first_failed_at": first_failed_at,
                    "last_failed_at": now,
                    "last_job_id": job.job_id,
                    "alert_emitted": alert_emitted,
                }
                stats = self._worker_stats.setdefault(
                    job.worker_id,
                    _default_worker_stats(job.worker_id, job.worker_name),
                )
                _ensure_worker_stats_fields(stats, job.worker_id, job.worker_name)
                stats["name"] = job.worker_name or stats["name"]
                stats["last_seen"] = now
                stats["last_failure_reason_code"] = safe_reason_code
                stats["last_failure_reason"] = safe_reason
                stats["last_failure_job_id"] = job.job_id
                stats["last_failure_source_path"] = job.source_path
                stats["last_failure_at"] = now
                if stats.get("failure_streak_reason_code") == safe_reason_code:
                    stats["failure_streak_count"] = int(stats.get("failure_streak_count", 0) or 0) + 1
                else:
                    stats["failure_streak_reason_code"] = safe_reason_code
                    stats["failure_streak_count"] = 1
        return job

    def unclaim(self, job_id: str, worker_id: str = "") -> "InFlightJob | None":
        """Remove *job_id* without incrementing completed or failed counters.

        Used when a worker is shutting down cleanly (*release* path) or
        when the coordinator cancels a stale job. Like :meth:`complete`,
        non-empty *worker_id* must match the recorded owner (N3).
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            requester = (worker_id or "").strip()
            if requester and requester != job.worker_id:
                _log.warning(
                    "Rejecting unclaim() for job %s: requester worker_id=%r "
                    "does not match owner %r",
                    job_id[:8], requester[:32], job.worker_id[:32],
                )
                return None
            del self._jobs[job_id]
            self._claimed_paths.pop(job.source_path, None)
            # N10 — same grace quarantine as complete(). Released jobs
            # may be re-queued by the coordinator; the brief grace
            # window prevents the same machine's poll loop from
            # immediately re-picking the path it just released.
            self._recent_completions[job.source_path] = time.monotonic()
        return job

    def rollback_claim(self, job_id: str, worker_id: str = "") -> "InFlightJob | None":
        """Undo a claim that was never durably saved.

        Unlike :meth:`unclaim`, this does not add the source path to the
        recent-completion quarantine. The coordinator is rolling back an
        uncommitted claim, not releasing work that a worker has observed.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            requester = (worker_id or "").strip()
            if requester and requester != job.worker_id:
                _log.warning(
                    "Rejecting rollback_claim() for job %s: requester worker_id=%r "
                    "does not match owner %r",
                    job_id[:8], requester[:32], job.worker_id[:32],
                )
                return None
            del self._jobs[job_id]
            self._claimed_paths.pop(job.source_path, None)
            self._recent_completions.pop(job.source_path, None)
        return job

    def claim_blocked_by_failure(self, *, worker_id: str, source_path: str, max_retries: int) -> dict[str, Any] | None:
        """Return ledger evidence when this worker/source is retry-suppressed."""
        threshold = max(1, int(max_retries or 1))
        key = _failure_ledger_key(worker_id, source_path)
        with self._lock:
            entry = self._failure_ledger.get(key)
            if not entry:
                return None
            if int(entry.get("consecutive_count", 0) or 0) < threshold:
                return None
            return dict(entry)

    def mark_failure_quarantine_alerted(
        self,
        *,
        worker_id: str,
        source_path: str,
        max_retries: int,
    ) -> dict[str, Any] | None:
        """Mark and return the quarantine entry once when its threshold is reached."""
        threshold = max(1, int(max_retries or 1))
        key = _failure_ledger_key(worker_id, source_path)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            entry = self._failure_ledger.get(key)
            if not entry:
                return None
            if int(entry.get("consecutive_count", 0) or 0) < threshold:
                return None
            if bool(entry.get("alert_emitted", False)):
                return None
            entry["alert_emitted"] = True
            stats = self._worker_stats.setdefault(
                str(worker_id or ""),
                _default_worker_stats(str(worker_id or ""), str(entry.get("worker_name", "") or "")),
            )
            _ensure_worker_stats_fields(stats, str(worker_id or ""), str(entry.get("worker_name", "") or ""))
            if int(stats.get("failure_streak_count", 0) or 0) >= threshold:
                stats["worker_misconfigured_reason_code"] = str(entry.get("reason_code", "") or "")
                stats["worker_misconfigured_at"] = now
            return dict(entry)

    def failure_ledger_snapshot(self) -> list[dict[str, Any]]:
        """Return a stable copy of per-worker/source failure suppression state."""
        with self._lock:
            return [dict(entry) for entry in self._failure_ledger.values()]

    def reclaim_stale(self, timeout_mins: float) -> list[InFlightJob]:
        """Return and remove all jobs whose heartbeat has expired.

        A job is stale when its ``last_heartbeat`` is older than
        *timeout_mins* minutes.  Returns an empty list when *timeout_mins*
        is zero or negative (stale-check effectively disabled).
        """
        if timeout_mins <= 0:
            return []
        cutoff_secs = timeout_mins * 60
        stale: list[InFlightJob] = []
        now = datetime.now(timezone.utc)
        with self._lock:
            for job_id in list(self._jobs):
                job = self._jobs[job_id]
                try:
                    last = datetime.fromisoformat(job.last_heartbeat)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    age = (now - last).total_seconds()
                except (ValueError, TypeError):
                    age = float("inf")
                if age > cutoff_secs:
                    stale.append(job)
                    del self._jobs[job_id]
                    self._claimed_paths.pop(job.source_path, None)
                    # Quarantine like complete()/unclaim() (N10): the
                    # silenced worker may still be running and writing
                    # output; the grace TTL absorbs its late done/release
                    # reports before the path can be claimed again.
                    self._recent_completions[job.source_path] = time.monotonic()
        return stale

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_active(self, job_id: str, worker_id: str = "") -> bool:
        """Return ``True`` if *job_id* is still tracked, and — when a
        non-empty *worker_id* is given — still owned by that worker."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            return not worker_id or job.worker_id == worker_id

    def is_in_flight(self, source_path: str) -> bool:
        """Return ``True`` if *source_path* is currently claimed OR was
        completed/released within the recent-completion grace TTL (N10).

        The grace window closes a race between ``complete()`` (which
        synchronously clears ``_claimed_paths``) and the UI-thread
        ``_remove_from_queue()`` callback (which clears ``queue_records``
        asynchronously). Without it, a second worker's ``/api/claim``
        would find the source still in the queue, see
        ``is_in_flight=False``, and re-claim it.
        """
        with self._lock:
            if source_path in self._claimed_paths:
                return True
            # Lazy-prune any expired grace entries while we're here.
            ttl = self._RECENT_COMPLETION_TTL_SECONDS
            if self._recent_completions:
                now = time.monotonic()
                if source_path in self._recent_completions:
                    age = now - self._recent_completions[source_path]
                    if age <= ttl:
                        return True
                    del self._recent_completions[source_path]
                # Opportunistic prune of unrelated stale entries — keeps
                # this dict small without needing a separate sweeper.
                if len(self._recent_completions) > 64:
                    expired = [
                        sp for sp, t in self._recent_completions.items()
                        if now - t > ttl
                    ]
                    for sp in expired:
                        self._recent_completions.pop(sp, None)
        return False

    def snapshot(self) -> list[WorkerEntry]:
        """Return a point-in-time copy of all in-flight jobs as ``WorkerEntry`` objects.

        Each entry is augmented with the worker's cumulative session stats
        (files completed, total GB encoded, average speed) drawn from the
        ``_worker_stats`` table.
        """
        with self._lock:
            jobs  = list(self._jobs.values())
            stats = dict(self._worker_stats)   # shallow copy for read-only access

        entries: list[WorkerEntry] = []
        for j in jobs:
            ws = _safe_worker_stats(j.worker_id, stats.get(j.worker_id, {}))
            total_gb  = float(ws.get("gb", 0.0))
            total_secs = float(ws.get("secs", 0.0))
            avg_speed = (total_gb / (total_secs / 3600.0)) if total_secs > 0 else 0.0
            entries.append(WorkerEntry(
                worker_id        = j.worker_id,
                worker_name      = j.worker_name or j.worker_id[:8],
                status           = "encoding",
                current_file     = j.source_path,
                progress_percent = _safe_snapshot_progress(j.worker_id, j.progress_percent),
                current_stage    = j.current_stage,
                last_heartbeat   = j.last_heartbeat,
                claimed_at       = j.claimed_at,
                files_completed  = int(ws.get("files", 0)),
                total_gb_encoded = round(total_gb, 2),
                avg_speed_gbh    = round(avg_speed, 2),
                last_failure_reason_code = str(ws.get("last_failure_reason_code", "") or ""),
                last_failure_reason      = str(ws.get("last_failure_reason", "") or ""),
                last_failure_job_id      = str(ws.get("last_failure_job_id", "") or ""),
                last_failure_source_path = str(ws.get("last_failure_source_path", "") or ""),
                last_failure_at          = str(ws.get("last_failure_at", "") or ""),
                failure_streak_reason_code = str(ws.get("failure_streak_reason_code", "") or ""),
                failure_streak_count       = int(ws.get("failure_streak_count", 0) or 0),
                worker_misconfigured_reason_code = str(ws.get("worker_misconfigured_reason_code", "") or ""),
                worker_misconfigured_at          = str(ws.get("worker_misconfigured_at", "") or ""),
                accessible_library_ids = coerce_library_id_list(
                    j.accessible_library_ids or ws.get("accessible_library_ids", [])
                ),
            ))
        return entries

    def idle_workers_snapshot(self) -> list[WorkerEntry]:
        """Return ``WorkerEntry`` objects for workers that have session stats
        but are NOT currently encoding (i.e. between jobs or done for the day).

        Used by the Live Worker Board to keep worker rows visible after a job
        finishes rather than making the board appear empty.
        """
        with self._lock:
            active_ids = {j.worker_id for j in self._jobs.values()}
            stats = dict(self._worker_stats)

        entries: list[WorkerEntry] = []
        for wid_raw, raw_ws in stats.items():
            wid = str(wid_raw)
            if wid in active_ids:
                continue  # already included in the active snapshot
            ws = _safe_worker_stats(wid, raw_ws)
            total_gb   = float(ws.get("gb", 0.0))
            total_secs = float(ws.get("secs", 0.0))
            avg_speed  = (total_gb / (total_secs / 3600.0)) if total_secs > 0 else 0.0
            entries.append(WorkerEntry(
                worker_id        = wid,
                worker_name      = str(ws.get("name", wid[:8])),
                status           = "idle",
                current_file     = "",
                progress_percent = 100.0,
                current_stage    = "idle",
                last_heartbeat   = str(ws.get("last_seen", "") or ""),
                claimed_at       = "",
                files_completed  = int(ws.get("files", 0)),
                total_gb_encoded = round(total_gb, 2),
                avg_speed_gbh    = round(avg_speed, 2),
                last_failure_reason_code = str(ws.get("last_failure_reason_code", "") or ""),
                last_failure_reason      = str(ws.get("last_failure_reason", "") or ""),
                last_failure_job_id      = str(ws.get("last_failure_job_id", "") or ""),
                last_failure_source_path = str(ws.get("last_failure_source_path", "") or ""),
                last_failure_at          = str(ws.get("last_failure_at", "") or ""),
                failure_streak_reason_code = str(ws.get("failure_streak_reason_code", "") or ""),
                failure_streak_count       = int(ws.get("failure_streak_count", 0) or 0),
                worker_misconfigured_reason_code = str(ws.get("worker_misconfigured_reason_code", "") or ""),
                worker_misconfigured_at          = str(ws.get("worker_misconfigured_at", "") or ""),
                accessible_library_ids = coerce_library_id_list(ws.get("accessible_library_ids", [])),
            ))
        return entries

    @property
    def active_count(self) -> int:
        """Number of jobs currently in flight."""
        with self._lock:
            return len(self._jobs)

    # ------------------------------------------------------------------
    # Persistence (crash recovery)
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Write in-flight state to *path* (atomic rename via temp file)."""
        with self._lock:
            data: dict[str, Any] = {
                "jobs":              [j.to_dict() for j in self._jobs.values()],
                "session_completed": self.session_completed,
                "session_failed":    self.session_failed,
                "worker_stats":      dict(self._worker_stats),
                "failure_ledger":    [dict(entry) for entry in self._failure_ledger.values()],
            }
        tmp_path: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(data, indent=2, allow_nan=False) + "\n"
            with self._save_lock:
                fd, tmp_name = tempfile.mkstemp(
                    prefix=f".{path.name}.",
                    suffix=".tmp",
                    dir=path.parent,
                    text=True,
                )
                tmp_path = Path(tmp_name)
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_path, path)
                tmp_path = None
        except Exception:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError as cleanup_exc:
                    _log.warning("Failed to remove temporary InFlightRegistry file %s: %s", tmp_path, cleanup_exc)
            _log.exception("Failed to save InFlightRegistry to %s", path)
            raise

    def load(self, path: Path) -> bool:
        """Restore in-flight state from *path* (crash recovery on startup)."""
        if not path.exists():
            return True
        try:
            data = loads_strict_json(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("registry state root must be a JSON object")
            jobs: dict[str, InFlightJob] = {}
            claimed_paths: dict[str, str] = {}
            for index, j_dict in enumerate(data.get("jobs", [])):
                if not isinstance(j_dict, dict):
                    _log.warning("Skipping malformed in-flight job at index %d in %s: expected object", index, path)
                    continue
                try:
                    job = InFlightJob.from_dict(j_dict)
                except Exception as exc:
                    _log.warning("Skipping malformed in-flight job at index %d in %s: %s", index, path, exc)
                    continue
                if not job.job_id or not job.source_path:
                    _log.warning(
                        "Skipping incomplete in-flight job at index %d in %s: missing job_id or source_path",
                        index,
                        path,
                    )
                    continue
                if job.job_id in jobs:
                    raise ValueError(
                        f"duplicate in-flight job_id {job.job_id!r} at index {index}; "
                        "coordinator recovery requires unique job ownership"
                    )
                if job.source_path in claimed_paths:
                    owner = claimed_paths[job.source_path]
                    raise ValueError(
                        f"duplicate in-flight source_path {job.source_path!r} at index {index}; "
                        f"already claimed by job_id {owner!r}"
                    )
                jobs[job.job_id] = job
                claimed_paths[job.source_path] = job.job_id

            worker_stats: dict[str, dict[str, Any]] = {}
            raw_stats = data.get("worker_stats", {})
            if isinstance(raw_stats, dict):
                for wid, ws in raw_stats.items():
                    if not isinstance(ws, dict):
                        _log.warning("Skipping malformed worker stats for %s in %s: expected object", wid, path)
                        continue
                    try:
                        worker_stats[str(wid)] = {
                            "name":  str(ws.get("name", "")),
                            "files": coerce_nonnegative_int(ws.get("files", 0), "files"),
                            "gb":    coerce_finite_float(ws.get("gb", 0.0), "gb", minimum=0.0),
                            "secs":  coerce_finite_float(ws.get("secs", 0.0), "secs", minimum=0.0),
                            "last_seen": str(ws.get("last_seen", "") or ""),
                            "last_failure_reason_code": normalize_failure_reason_code(ws.get("last_failure_reason_code", "")),
                            "last_failure_reason": bounded_failure_reason(ws.get("last_failure_reason", "")),
                            "last_failure_job_id": str(ws.get("last_failure_job_id", "") or ""),
                            "last_failure_source_path": str(ws.get("last_failure_source_path", "") or ""),
                            "last_failure_at": str(ws.get("last_failure_at", "") or ""),
                            "failure_streak_reason_code": normalize_failure_reason_code(ws.get("failure_streak_reason_code", "")),
                            "failure_streak_count": coerce_nonnegative_int(ws.get("failure_streak_count", 0), "failure_streak_count"),
                            "worker_misconfigured_reason_code": normalize_failure_reason_code(ws.get("worker_misconfigured_reason_code", "")),
                            "worker_misconfigured_at": str(ws.get("worker_misconfigured_at", "") or ""),
                        }
                    except Exception as exc:
                        _log.warning("Skipping malformed worker stats for %s in %s: %s", wid, path, exc)
            else:
                _log.warning("Ignoring malformed worker_stats in %s: expected object", path)

            failure_ledger: dict[str, dict[str, Any]] = {}
            raw_ledger = data.get("failure_ledger", [])
            if isinstance(raw_ledger, dict):
                raw_ledger_items = list(raw_ledger.values())
            elif isinstance(raw_ledger, list):
                raw_ledger_items = raw_ledger
            else:
                raw_ledger_items = []
                _log.warning("Ignoring malformed failure_ledger in %s: expected array or object", path)
            for index, raw_entry in enumerate(raw_ledger_items):
                entry = _safe_failure_ledger_entry(raw_entry)
                if entry is None:
                    _log.warning("Skipping malformed failure ledger entry at index %d in %s", index, path)
                    continue
                failure_ledger[_failure_ledger_key(entry["worker_id"], entry["source_path"])] = entry

            try:
                session_completed = coerce_nonnegative_int(data.get("session_completed", 0), "session_completed")
            except Exception as exc:
                _log.warning("Invalid session_completed in %s: %s", path, exc)
                session_completed = 0
            try:
                session_failed = coerce_nonnegative_int(data.get("session_failed", 0), "session_failed")
            except Exception as exc:
                _log.warning("Invalid session_failed in %s: %s", path, exc)
                session_failed = 0

            with self._lock:
                self._jobs = jobs
                self._claimed_paths = claimed_paths
                self.session_completed = session_completed
                self.session_failed = session_failed
                self._worker_stats = worker_stats
                self._failure_ledger = failure_ledger
            _log.info("Restored %d in-flight job(s) from %s", len(self._jobs), path)
            return True
        except Exception:
            _log.exception("Failed to load InFlightRegistry from %s", path)
            return False
