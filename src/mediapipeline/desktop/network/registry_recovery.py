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
from datetime import datetime, timedelta, UTC
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

_log = logging.getLogger("mediapipeline.desktop.network.registry")



from mediapipeline.desktop.network.registry_support import *  # noqa: F403

class InFlightRegistryRecoveryMixin:
    def _reclaimed_source_quarantine_seconds(self, timeout_mins: float) -> float:
        try:
            timeout_seconds = coerce_finite_float(timeout_mins, "timeout_mins", minimum=0.0) * 60.0
        except Exception:
            timeout_seconds = 0.0
        return max(self._MIN_RECLAIMED_SOURCE_QUARANTINE_SECONDS, timeout_seconds * 2.0)

    def _prune_reclaimed_source_quarantine_locked(self, now: datetime | None = None) -> None:
        if not self._reclaimed_source_quarantine:
            return
        now = now or datetime.now(UTC)
        expired: list[str] = []
        for source_identity, entry in self._reclaimed_source_quarantine.items():
            expires_at = _parse_utc_datetime(entry.get("expires_at"))
            if expires_at is None or expires_at <= now:
                expired.append(source_identity)
        for source_identity in expired:
            self._reclaimed_source_quarantine.pop(source_identity, None)

    def _reclaimed_source_quarantine_entry_locked(
        self,
        source_identity: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        if not source_identity:
            return None
        now = now or datetime.now(UTC)
        entry = self._reclaimed_source_quarantine.get(source_identity)
        if not entry:
            return None
        expires_at = _parse_utc_datetime(entry.get("expires_at"))
        if expires_at is None or expires_at <= now:
            self._reclaimed_source_quarantine.pop(source_identity, None)
            return None
        return entry

    def _record_reclaimed_source_quarantine_locked(
        self,
        job: InFlightJob,
        *,
        timeout_mins: float,
        reclaimed_at: str,
        quarantine_seconds: float | None = None,
    ) -> dict[str, Any]:
        source_identity = normalize_source_identity(job.source_path)
        if not source_identity:
            return {}
        reclaimed_dt = _parse_utc_datetime(reclaimed_at) or datetime.now(UTC)
        ttl = float(quarantine_seconds) if quarantine_seconds is not None else self._reclaimed_source_quarantine_seconds(timeout_mins)
        ttl = max(self._MIN_RECLAIMED_SOURCE_QUARANTINE_SECONDS, ttl)
        expires_at = (reclaimed_dt + timedelta(seconds=ttl)).isoformat()
        entry = {
            "source_identity": source_identity,
            "source_path": job.source_path,
            "job_id": job.job_id,
            "worker_id": job.worker_id,
            "worker_name": job.worker_name,
            "claimed_at": job.claimed_at,
            "last_heartbeat": job.last_heartbeat,
            "reclaimed_at": reclaimed_dt.isoformat(),
            "expires_at": expires_at,
            "timeout_mins": float(timeout_mins),
            "quarantine_seconds": int(ttl),
        }
        self._reclaimed_source_quarantine[source_identity] = entry
        return dict(entry)

    def clear_reclaimed_source_quarantine(self, source_path: str) -> bool:
        """Clear stale-reclaim quarantine after an accepted terminal report."""
        source_identity = normalize_source_identity(source_path)
        if not source_identity:
            return False
        with self._lock:
            return self._reclaimed_source_quarantine.pop(source_identity, None) is not None

    def _cap_failure_ledger_locked(self) -> None:
        while len(self._failure_ledger) > self._MAX_FAILURE_LEDGER_ENTRIES:
            self._failure_ledger.pop(next(iter(self._failure_ledger)), None)

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

    def reclaim_stale(
        self,
        timeout_mins: float,
        *,
        quarantine_seconds: float | None = None,
    ) -> list[InFlightJob]:
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
                    # output; the short grace TTL absorbs immediate late
                    # reports while the persisted reclaimed-source quarantine
                    # blocks duplicate claims until a terminal report is
                    # accepted or the lease-safety window expires.
                    self._recent_completions[source_identity] = time.monotonic()
                    quarantine = self._record_reclaimed_source_quarantine_locked(
                        job,
                        timeout_mins=timeout_mins,
                        reclaimed_at=now.isoformat(),
                        quarantine_seconds=quarantine_seconds,
                    )
                    self._record_reclaim_locked(
                        job,
                        timeout_mins=timeout_mins,
                        reclaimed_at=now.isoformat(),
                        quarantine_expires_at=str(quarantine.get("expires_at", "") or ""),
                    )
        return stale

    def _record_reclaim_locked(
        self,
        job: InFlightJob,
        *,
        timeout_mins: float,
        reclaimed_at: str,
        quarantine_expires_at: str = "",
    ) -> None:
        claim_metadata = job.claim_metadata if isinstance(job.claim_metadata, dict) else {}
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
            "quarantine_expires_at": quarantine_expires_at,
            "job_kind": str(job.job_kind or claim_metadata.get("job_kind") or ""),
            "rerun_batch_id": str(claim_metadata.get("rerun_batch_id") or ""),
            "rerun_row_key": str(claim_metadata.get("rerun_row_key") or ""),
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
            reclaimed_worker_id = str(reclaim.get("worker_id", "") or "")
            owner_matches = bool(reclaimed_worker_id and worker_id == reclaimed_worker_id)
            report = {
                "job_id": job_id,
                "worker_id": worker_id,
                "reclaimed_worker_id": reclaimed_worker_id,
                "accepted": owner_matches,
                "authorization_status": (
                    "accepted" if owner_matches else "rejected_owner_mismatch"
                ),
                "source_path": str(reclaim.get("source_path", "") or ""),
                "source_identity": str(reclaim.get("source_identity", "") or ""),
                "job_kind": str(reclaim.get("job_kind", "") or ""),
                "rerun_batch_id": str(reclaim.get("rerun_batch_id", "") or ""),
                "rerun_row_key": str(reclaim.get("rerun_row_key", "") or ""),
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
            report["removes_queue_record"] = bool(
                owner_matches and (report["success"] or report["queue_terminal"])
            )
            self._late_terminal_reports.append(report)
            if len(self._late_terminal_reports) > self._MAX_LATE_TERMINAL_REPORTS:
                self._late_terminal_reports = self._late_terminal_reports[-self._MAX_LATE_TERMINAL_REPORTS :]
            return dict(report)

    def rollback_snapshot(
        self,
        job_id: str,
        *,
        transition: str = "",
        success: bool = False,
        elapsed_seconds: float = 0.0,
        output_size_bytes: int = 0,
    ) -> dict[str, Any]:
        """Capture only one job's state for a compare-and-set rollback.

        The receipt deliberately excludes unrelated jobs and collection-wide
        snapshots. A failed durable transition can therefore be reversed
        without replacing claims, completions, heartbeats, or recovery
        evidence committed by another request thread.
        """
        safe_job_id = str(job_id or "").strip()
        if not safe_job_id:
            raise ValueError("rollback snapshot requires a non-empty job_id")
        with self._lock:
            job = copy.deepcopy(self._jobs.get(safe_job_id))
            reclaim = self._reclaim_ledger.get(safe_job_id, {})
            source_path = str(getattr(job, "source_path", "") or reclaim.get("source_path", "") or "")
            source_identity = normalize_source_identity(source_path)
            worker_id = str(getattr(job, "worker_id", "") or "")
            failure_key = _failure_ledger_key(worker_id, source_path) if worker_id and source_path else ""
            return {
                "schema_version": "network_registry_job_rollback.v1",
                "job_id": safe_job_id,
                "transition": str(transition or "").strip().casefold(),
                "success": bool(success),
                "elapsed_seconds": max(0.0, float(elapsed_seconds or 0.0)),
                "output_size_bytes": max(0, int(output_size_bytes or 0)),
                "job_present": job is not None,
                "job": job,
                "source_identity": source_identity,
                "claimed_path_present": bool(source_identity and source_identity in self._claimed_paths),
                "claimed_path_owner": self._claimed_paths.get(source_identity, "") if source_identity else "",
                "recent_completion_present": bool(
                    source_identity and source_identity in self._recent_completions
                ),
                "recent_completion": self._recent_completions.get(source_identity) if source_identity else None,
                "session_completed": self.session_completed,
                "session_failed": self.session_failed,
                "worker_id": worker_id,
                "worker_stats_present": bool(worker_id and worker_id in self._worker_stats),
                "worker_stats": copy.deepcopy(self._worker_stats.get(worker_id)) if worker_id else None,
                "failure_key": failure_key,
                "failure_entry_present": bool(failure_key and failure_key in self._failure_ledger),
                "failure_entry": copy.deepcopy(self._failure_ledger.get(failure_key)) if failure_key else None,
                "late_terminal_reports": copy.deepcopy(
                    [entry for entry in self._late_terminal_reports if str(entry.get("job_id", "")) == safe_job_id]
                ),
                "quarantine_present": bool(
                    source_identity and source_identity in self._reclaimed_source_quarantine
                ),
                "quarantine": copy.deepcopy(
                    self._reclaimed_source_quarantine.get(source_identity)
                ) if source_identity else None,
            }

    def restore_rollback_snapshot(self, snapshot: dict[str, Any]) -> bool:
        """Merge one failed transition back without replacing unrelated state."""
        if snapshot.get("schema_version") != "network_registry_job_rollback.v1":
            raise ValueError("unsupported registry rollback snapshot")
        job_id = str(snapshot.get("job_id", "") or "").strip()
        if not job_id:
            raise ValueError("registry rollback snapshot requires job_id")

        with self._lock:
            original_job = copy.deepcopy(snapshot.get("job")) if snapshot.get("job_present") else None
            source_identity = str(snapshot.get("source_identity", "") or "")
            transition_applied = False
            if original_job is not None:
                current_job = self._jobs.get(job_id)
                if current_job is None:
                    current_owner = self._claimed_paths.get(source_identity) if source_identity else None
                    if current_owner not in {None, "", job_id}:
                        _log.error(
                            "Refusing rollback for job %s because source is now owned by job %s.",
                            job_id[:8],
                            str(current_owner)[:8],
                        )
                        return False
                    self._jobs[job_id] = original_job
                    if source_identity:
                        self._claimed_paths[source_identity] = str(
                            snapshot.get("claimed_path_owner", "") or job_id
                        )
                    transition_applied = True
                elif current_job != original_job:
                    _log.error("Refusing rollback for job %s because its identity changed.", job_id[:8])
                    return False

                if source_identity:
                    if snapshot.get("recent_completion_present"):
                        self._recent_completions[source_identity] = float(
                            snapshot.get("recent_completion", 0.0) or 0.0
                        )
                    else:
                        self._recent_completions.pop(source_identity, None)

            transition = str(snapshot.get("transition", "") or "")
            worker_id = str(snapshot.get("worker_id", "") or "")
            if transition_applied and transition == "complete" and original_job is not None:
                success = bool(snapshot.get("success", False))
                if success:
                    self.session_completed = max(
                        int(snapshot.get("session_completed", 0) or 0),
                        self.session_completed - 1,
                    )
                else:
                    self.session_failed = max(
                        int(snapshot.get("session_failed", 0) or 0),
                        self.session_failed - 1,
                    )

                prior_stats = copy.deepcopy(snapshot.get("worker_stats"))
                current_stats = self._worker_stats.get(worker_id) if worker_id else None
                if snapshot.get("worker_stats_present") and isinstance(prior_stats, dict):
                    if not isinstance(current_stats, dict):
                        self._worker_stats[worker_id] = prior_stats
                    elif success:
                        prior_files = int(prior_stats.get("files", 0) or 0)
                        current_stats["files"] = max(prior_files, int(current_stats.get("files", 0) or 0) - 1)
                        size_bytes = int(snapshot.get("output_size_bytes", 0) or 0)
                        size_gb = (
                            size_bytes / (1024 ** 3)
                            if size_bytes > 0
                            else float(getattr(original_job, "estimated_size_gb", 0.0) or 0.0)
                        )
                        current_stats["gb"] = max(
                            float(prior_stats.get("gb", 0.0) or 0.0),
                            float(current_stats.get("gb", 0.0) or 0.0) - size_gb,
                        )
                        elapsed = float(snapshot.get("elapsed_seconds", 0.0) or 0.0)
                        current_stats["secs"] = max(
                            float(prior_stats.get("secs", 0.0) or 0.0),
                            float(current_stats.get("secs", 0.0) or 0.0) - elapsed,
                        )
                        reset_values = {
                            "failure_streak_reason_code": "",
                            "failure_streak_count": 0,
                            "worker_misconfigured_reason_code": "",
                            "worker_misconfigured_at": "",
                        }
                        for field_name, target_value in reset_values.items():
                            if current_stats.get(field_name) == target_value:
                                current_stats[field_name] = copy.deepcopy(prior_stats.get(field_name, target_value))
                    elif str(current_stats.get("last_failure_job_id", "") or "") == job_id:
                        later_success = int(current_stats.get("files", 0) or 0) > int(
                            prior_stats.get("files", 0) or 0
                        )
                        for field_name in (
                            "last_failure_reason_code",
                            "last_failure_reason",
                            "last_failure_job_id",
                            "last_failure_source_path",
                            "last_failure_at",
                        ):
                            current_stats[field_name] = copy.deepcopy(prior_stats.get(field_name, ""))
                        if not later_success:
                            for field_name in ("failure_streak_reason_code", "failure_streak_count"):
                                current_stats[field_name] = copy.deepcopy(prior_stats.get(field_name, "" if field_name.endswith("code") else 0))

                failure_key = str(snapshot.get("failure_key", "") or "")
                if failure_key:
                    current_failure = self._failure_ledger.get(failure_key)
                    target_owns_failure = bool(
                        isinstance(current_failure, dict)
                        and str(current_failure.get("last_job_id", "") or "") == job_id
                    )
                    if success:
                        target_owns_failure = current_failure is None
                    if target_owns_failure:
                        if snapshot.get("failure_entry_present"):
                            self._failure_ledger[failure_key] = copy.deepcopy(snapshot.get("failure_entry"))
                        else:
                            self._failure_ledger.pop(failure_key, None)

            prior_reports = copy.deepcopy(snapshot.get("late_terminal_reports", []))
            current_target_reports = [
                entry for entry in self._late_terminal_reports if str(entry.get("job_id", "")) == job_id
            ]
            # record_late_terminal_report appends one row. Remove only the
            # first post-snapshot row attributable to this failed transition;
            # retain later same-job reports that another request may have
            # committed while external persistence was in progress.
            if current_target_reports[: len(prior_reports)] == prior_reports and len(
                current_target_reports
            ) > len(prior_reports):
                remove_target_index = len(prior_reports)
                target_index = 0
                merged_reports: list[dict[str, Any]] = []
                for entry in self._late_terminal_reports:
                    if str(entry.get("job_id", "")) == job_id:
                        if target_index == remove_target_index:
                            target_index += 1
                            continue
                        target_index += 1
                    merged_reports.append(entry)
                self._late_terminal_reports = merged_reports
            if source_identity:
                if snapshot.get("quarantine_present"):
                    current_quarantine = self._reclaimed_source_quarantine.get(source_identity)
                    prior_quarantine = copy.deepcopy(snapshot.get("quarantine"))
                    if current_quarantine is None or current_quarantine == prior_quarantine:
                        self._reclaimed_source_quarantine[source_identity] = prior_quarantine
            return True

    def reclaim_ledger_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(entry) for entry in self._reclaim_ledger.values()]

    def late_terminal_reports_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(entry) for entry in self._late_terminal_reports]

    def reclaimed_source_quarantine_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            self._prune_reclaimed_source_quarantine_locked()
            return [dict(entry) for entry in self._reclaimed_source_quarantine.values()]

    def reclaimed_source_quarantine_stats(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self._lock:
            self._prune_reclaimed_source_quarantine_locked(now)
            entries = [dict(entry) for entry in self._reclaimed_source_quarantine.values()]
        oldest_age_seconds: int | None = None
        oldest_reclaimed_at = ""
        for entry in entries:
            reclaimed_at = _parse_utc_datetime(entry.get("reclaimed_at"))
            if reclaimed_at is None:
                continue
            age = max(0, int((now - reclaimed_at).total_seconds()))
            if oldest_age_seconds is None or age > oldest_age_seconds:
                oldest_age_seconds = age
                oldest_reclaimed_at = reclaimed_at.isoformat()
        return {
            "count": len(entries),
            "oldest_age_seconds": oldest_age_seconds,
            "oldest_reclaimed_at": oldest_reclaimed_at,
        }

    def failure_ledger_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._failure_ledger),
                "max_entries": self._MAX_FAILURE_LEDGER_ENTRIES,
            }
