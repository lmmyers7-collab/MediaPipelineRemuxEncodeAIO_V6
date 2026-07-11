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

class InFlightRegistryRecoveryMixin:
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
        now = datetime.now(UTC).isoformat()
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
        now = datetime.now(UTC)
        with self._lock:
            for job_id in list(self._jobs):
                job = self._jobs[job_id]
                try:
                    last = datetime.fromisoformat(job.last_heartbeat)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=UTC)
                    age = (now - last).total_seconds()
                except (ValueError, TypeError):
                    age = float("inf")
                if age > cutoff_secs:
                    stale.append(job)
                    del self._jobs[job_id]
                    source_identity = normalize_source_identity(job.source_path)
                    self._claimed_paths.pop(source_identity, None)
                    # Quarantine like complete()/unclaim() (N10): the
                    # silenced worker may still be running and writing
                    # output; the grace TTL absorbs its late done/release
                    # reports before the path can be claimed again.
                    self._recent_completions[source_identity] = time.monotonic()
                    self._record_reclaim_locked(job, timeout_mins=timeout_mins, reclaimed_at=now.isoformat())
        return stale

    def _record_reclaim_locked(self, job: InFlightJob, *, timeout_mins: float, reclaimed_at: str) -> None:
        self._reclaim_ledger[job.job_id] = {
            "job_id": job.job_id,
            "worker_id": job.worker_id,
            "worker_name": job.worker_name,
            "source_path": job.source_path,
            "source_identity": normalize_source_identity(job.source_path),
            "claimed_at": job.claimed_at,
            "last_heartbeat": job.last_heartbeat,
            "reclaimed_at": reclaimed_at,
            "timeout_mins": float(timeout_mins),
        }
        while len(self._reclaim_ledger) > self._MAX_RECLAIM_LEDGER_ENTRIES:
            self._reclaim_ledger.pop(next(iter(self._reclaim_ledger)), None)

    def record_late_terminal_report(self, request: Any) -> dict[str, Any] | None:
        """Persist terminal worker evidence for a job already reclaimed stale."""
        job_id = str(getattr(request, "job_id", "") or "").strip()
        worker_id = str(getattr(request, "worker_id", "") or "").strip()
        if not job_id or not worker_id:
            return None
        now = datetime.now(UTC).isoformat()
        with self._lock:
            reclaim = self._reclaim_ledger.get(job_id)
            if not reclaim:
                return None
            report = {
                "job_id": job_id,
                "worker_id": worker_id,
                "reclaimed_worker_id": str(reclaim.get("worker_id", "") or ""),
                "source_path": str(reclaim.get("source_path", "") or ""),
                "source_identity": str(reclaim.get("source_identity", "") or ""),
                "reclaimed_at": str(reclaim.get("reclaimed_at", "") or ""),
                "reported_at": now,
                "success": bool(getattr(request, "success", False)),
                "completion_status": str(getattr(request, "completion_status", "") or ""),
                "publish_state": str(getattr(request, "publish_state", "") or ""),
                "publish_mode": str(getattr(request, "publish_mode", "") or ""),
                "route": str(getattr(request, "route", "") or ""),
                "output_path": str(getattr(request, "output_path", "") or ""),
                "output_size_bytes": int(getattr(request, "output_size_bytes", 0) or 0),
                "reason_code": str(getattr(request, "reason_code", "") or ""),
                "reason": bounded_failure_reason(
                    getattr(request, "reason", "") or getattr(request, "error_message", "") or ""
                ),
                "queue_terminal": bool(getattr(request, "queue_terminal", False)),
                "retry_on_failure": bool(getattr(request, "retry_on_failure", True)),
            }
            self._late_terminal_reports.append(report)
            if len(self._late_terminal_reports) > self._MAX_LATE_TERMINAL_REPORTS:
                self._late_terminal_reports = self._late_terminal_reports[-self._MAX_LATE_TERMINAL_REPORTS :]
            return dict(report)

    def rollback_snapshot(self) -> dict[str, Any]:
        """Return an in-memory snapshot for rolling back failed durable transitions."""
        with self._lock:
            return {
                "jobs": copy.deepcopy(self._jobs),
                "claimed_paths": copy.deepcopy(self._claimed_paths),
                "recent_completions": copy.deepcopy(self._recent_completions),
                "session_completed": self.session_completed,
                "session_failed": self.session_failed,
                "worker_stats": copy.deepcopy(self._worker_stats),
                "failure_ledger": copy.deepcopy(self._failure_ledger),
                "reclaim_ledger": copy.deepcopy(self._reclaim_ledger),
                "late_terminal_reports": copy.deepcopy(self._late_terminal_reports),
            }

    def restore_rollback_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Restore a snapshot returned by :meth:`rollback_snapshot`."""
        with self._lock:
            self._jobs = copy.deepcopy(snapshot.get("jobs", {}))
            self._claimed_paths = copy.deepcopy(snapshot.get("claimed_paths", {}))
            self._recent_completions = copy.deepcopy(snapshot.get("recent_completions", {}))
            self.session_completed = int(snapshot.get("session_completed", 0) or 0)
            self.session_failed = int(snapshot.get("session_failed", 0) or 0)
            self._worker_stats = copy.deepcopy(snapshot.get("worker_stats", {}))
            self._failure_ledger = copy.deepcopy(snapshot.get("failure_ledger", {}))
            self._reclaim_ledger = copy.deepcopy(snapshot.get("reclaim_ledger", {}))
            self._late_terminal_reports = copy.deepcopy(snapshot.get("late_terminal_reports", []))

    def reclaim_ledger_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(entry) for entry in self._reclaim_ledger.values()]

    def late_terminal_reports_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(entry) for entry in self._late_terminal_reports]
