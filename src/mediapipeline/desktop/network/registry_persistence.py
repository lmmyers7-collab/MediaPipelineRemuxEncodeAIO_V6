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

class InFlightRegistryPersistenceMixin:
    def save(self, path: Path) -> None:
        """Write in-flight state to *path* (atomic rename via temp file)."""
        with self._lock:
            data: dict[str, Any] = {
                "jobs":              [j.to_dict() for j in self._jobs.values()],
                "session_completed": self.session_completed,
                "session_failed":    self.session_failed,
                "worker_stats":      dict(self._worker_stats),
                "failure_ledger":    [dict(entry) for entry in self._failure_ledger.values()],
                "reclaim_ledger":    [dict(entry) for entry in self._reclaim_ledger.values()],
                "late_terminal_reports": [dict(entry) for entry in self._late_terminal_reports],
                "reclaimed_source_quarantine": [dict(entry) for entry in self._reclaimed_source_quarantine.values()],
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
                source_identity = normalize_source_identity(job.source_path)
                if source_identity in claimed_paths:
                    owner = claimed_paths[source_identity]
                    raise ValueError(
                        f"duplicate in-flight source_path {job.source_path!r} at index {index}; "
                        f"already claimed by job_id {owner!r}"
                    )
                jobs[job.job_id] = job
                claimed_paths[source_identity] = job.job_id

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
            while len(failure_ledger) > self._MAX_FAILURE_LEDGER_ENTRIES:
                failure_ledger.pop(next(iter(failure_ledger)), None)

            reclaim_ledger: dict[str, dict[str, Any]] = {}
            raw_reclaim = data.get("reclaim_ledger", [])
            if isinstance(raw_reclaim, dict):
                reclaim_items = list(raw_reclaim.values())
            elif isinstance(raw_reclaim, list):
                reclaim_items = raw_reclaim
            else:
                reclaim_items = []
                _log.warning("Ignoring malformed reclaim_ledger in %s: expected array or object", path)
            for index, raw_entry in enumerate(reclaim_items):
                if not isinstance(raw_entry, dict):
                    _log.warning("Skipping malformed reclaim ledger entry at index %d in %s", index, path)
                    continue
                job_id = str(raw_entry.get("job_id", "") or "").strip()
                source_path = str(raw_entry.get("source_path", "") or "").strip()
                if not job_id or not source_path:
                    _log.warning("Skipping incomplete reclaim ledger entry at index %d in %s", index, path)
                    continue
                try:
                    timeout_mins = coerce_finite_float(raw_entry.get("timeout_mins", 0.0), "timeout_mins", minimum=0.0)
                except Exception:
                    timeout_mins = 0.0
                reclaim_ledger[job_id] = {
                    "job_id": job_id,
                    "worker_id": str(raw_entry.get("worker_id", "") or ""),
                    "worker_name": str(raw_entry.get("worker_name", "") or ""),
                    "source_path": source_path,
                    "source_identity": normalize_source_identity(raw_entry.get("source_identity", "") or source_path),
                    "claimed_at": str(raw_entry.get("claimed_at", "") or ""),
                    "last_heartbeat": str(raw_entry.get("last_heartbeat", "") or ""),
                    "reclaimed_at": str(raw_entry.get("reclaimed_at", "") or ""),
                    "timeout_mins": timeout_mins,
                    "quarantine_expires_at": str(raw_entry.get("quarantine_expires_at", "") or ""),
                }

            late_terminal_reports: list[dict[str, Any]] = []
            raw_late = data.get("late_terminal_reports", [])
            if isinstance(raw_late, list):
                late_items = raw_late[-self._MAX_LATE_TERMINAL_REPORTS :]
            else:
                late_items = []
                if raw_late:
                    _log.warning("Ignoring malformed late_terminal_reports in %s: expected array", path)
            for index, raw_entry in enumerate(late_items):
                if not isinstance(raw_entry, dict):
                    _log.warning("Skipping malformed late terminal report at index %d in %s", index, path)
                    continue
                if not str(raw_entry.get("job_id", "") or "").strip() or not str(raw_entry.get("worker_id", "") or "").strip():
                    _log.warning("Skipping incomplete late terminal report at index %d in %s", index, path)
                    continue
                late_terminal_reports.append(dict(raw_entry))

            reclaimed_source_quarantine: dict[str, dict[str, Any]] = {}
            raw_quarantine = data.get("reclaimed_source_quarantine", [])
            if isinstance(raw_quarantine, dict):
                quarantine_items = list(raw_quarantine.values())
            elif isinstance(raw_quarantine, list):
                quarantine_items = raw_quarantine
            else:
                quarantine_items = []
                if raw_quarantine:
                    _log.warning("Ignoring malformed reclaimed_source_quarantine in %s: expected array or object", path)
            load_now = datetime.now(UTC)
            for index, raw_entry in enumerate(quarantine_items):
                if not isinstance(raw_entry, dict):
                    _log.warning("Skipping malformed reclaimed-source quarantine entry at index %d in %s", index, path)
                    continue
                source_path = str(raw_entry.get("source_path", "") or "").strip()
                source_identity = normalize_source_identity(raw_entry.get("source_identity", "") or source_path)
                if not source_path or not source_identity:
                    _log.warning("Skipping incomplete reclaimed-source quarantine entry at index %d in %s", index, path)
                    continue
                expires_at = _parse_utc_datetime(raw_entry.get("expires_at"))
                if expires_at is None or expires_at <= load_now:
                    continue
                try:
                    timeout_mins = coerce_finite_float(raw_entry.get("timeout_mins", 0.0), "timeout_mins", minimum=0.0)
                except Exception:
                    timeout_mins = 0.0
                try:
                    quarantine_seconds = coerce_nonnegative_int(raw_entry.get("quarantine_seconds", 0), "quarantine_seconds")
                except Exception:
                    quarantine_seconds = 0
                reclaimed_source_quarantine[source_identity] = {
                    "source_identity": source_identity,
                    "source_path": source_path,
                    "job_id": str(raw_entry.get("job_id", "") or ""),
                    "worker_id": str(raw_entry.get("worker_id", "") or ""),
                    "worker_name": str(raw_entry.get("worker_name", "") or ""),
                    "claimed_at": str(raw_entry.get("claimed_at", "") or ""),
                    "last_heartbeat": str(raw_entry.get("last_heartbeat", "") or ""),
                    "reclaimed_at": str(raw_entry.get("reclaimed_at", "") or ""),
                    "expires_at": expires_at.isoformat(),
                    "timeout_mins": timeout_mins,
                    "quarantine_seconds": quarantine_seconds,
                }

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
                self._reclaim_ledger = reclaim_ledger
                self._late_terminal_reports = late_terminal_reports
                self._reclaimed_source_quarantine = reclaimed_source_quarantine
            _log.info("Restored %d in-flight job(s) from %s", len(self._jobs), path)
            return True
        except Exception:
            _log.exception("Failed to load InFlightRegistry from %s", path)
            return False
