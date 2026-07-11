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

import copy
import json
import logging
import ntpath
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.network.url_policy import redact_network_secret_text

from .failure_reasons import REASON_ENCODE_ERROR, bounded_failure_reason, normalize_failure_reason_code
from .json_policy import loads_strict_json
from .protocol import (
    WorkerEntry,
    coerce_finite_float,
    coerce_library_id_list,
    coerce_nonnegative_int,
    coerce_progress_percent,
)

_log = logging.getLogger("mediapipeline.core.network.registry")



from mediapipeline.core.network.registry_support import *  # noqa: F403

class InFlightRegistryLifecycleMixin:
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
        now = datetime.now(UTC).isoformat()
        safe_job_id = str(job_id or "").strip()
        safe_worker_id = str(worker_id or "").strip()
        safe_source_path = str(source_path or "").strip()
        source_identity = normalize_source_identity(safe_source_path)
        if not safe_job_id or not safe_worker_id or not safe_source_path or not source_identity:
            _log.warning(
                "Rejecting claim with incomplete identity: job_id=%r worker_id=%r source_path=%r",
                safe_job_id[:32],
                safe_worker_id[:32],
                safe_source_path[:120],
            )
            return False
        with self._lock:
            if safe_job_id in self._jobs:
                _log.warning("Rejecting duplicate in-flight job_id %r for source %s", safe_job_id[:32], safe_source_path)
                return False
            if source_identity in self._claimed_paths:
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
                    safe_job_id[:8],
                    safe_source_path,
                    exc,
                )
                safe_estimated_size_gb = 0.0
            safe_library_ids = coerce_library_id_list(accessible_library_ids or [])
            job = InFlightJob(
                job_id=safe_job_id,
                worker_id=safe_worker_id,
                worker_name=worker_name,
                source_path=safe_source_path,
                claimed_at=now,
                last_heartbeat=now,
                encode_config=encode_config,
                priority=priority,
                estimated_size_gb=safe_estimated_size_gb,
                accessible_library_ids=safe_library_ids,
            )
            self._jobs[safe_job_id] = job
            self._claimed_paths[source_identity] = safe_job_id

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
        now = datetime.now(UTC).isoformat()
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
            job.last_heartbeat   = datetime.now(UTC).isoformat()
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
    ) -> InFlightJob | None:
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
            self._claimed_paths.pop(normalize_source_identity(job.source_path), None)
            # N10 — quarantine the source path for the grace TTL so
            # is_in_flight() still says "yes" while the app callback
            # finishes removing this record from queue_records. Without
            # this, a concurrent /api/claim from another worker would
            # walk the not-yet-pruned queue list, see is_in_flight()
            # return False (already cleared above), and re-claim the
            # same source.
            self._recent_completions[normalize_source_identity(job.source_path)] = time.monotonic()
            now = datetime.now(UTC).isoformat()
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

    def unclaim(self, job_id: str, worker_id: str = "") -> InFlightJob | None:
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
            source_identity = normalize_source_identity(job.source_path)
            self._claimed_paths.pop(source_identity, None)
            # N10 — same grace quarantine as complete(). Released jobs
            # may be re-queued by the coordinator; the brief grace
            # window prevents the same machine's poll loop from
            # immediately re-picking the path it just released.
            self._recent_completions[source_identity] = time.monotonic()
        return job

    def rollback_claim(self, job_id: str, worker_id: str = "") -> InFlightJob | None:
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
            source_identity = normalize_source_identity(job.source_path)
            self._claimed_paths.pop(source_identity, None)
            self._recent_completions.pop(source_identity, None)
        return job

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
        source_identity = normalize_source_identity(source_path)
        if not source_identity:
            return False
        with self._lock:
            if source_identity in self._claimed_paths:
                return True
            # Lazy-prune any expired grace entries while we're here.
            ttl = self._RECENT_COMPLETION_TTL_SECONDS
            if self._recent_completions:
                now = time.monotonic()
                if source_identity in self._recent_completions:
                    age = now - self._recent_completions[source_identity]
                    if age <= ttl:
                        return True
                    del self._recent_completions[source_identity]
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

    @property
    def active_count(self) -> int:
        """Number of jobs currently in flight."""
        with self._lock:
            return len(self._jobs)
