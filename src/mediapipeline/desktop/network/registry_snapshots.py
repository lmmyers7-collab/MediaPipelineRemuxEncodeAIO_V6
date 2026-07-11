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

class InFlightRegistrySnapshotsMixin:
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

    def active_claims_snapshot(self) -> list[dict[str, Any]]:
        """Return token-safe evidence for active claims.

        This is separate from ``snapshot()`` because lifecycle dry-runs need the
        claim id and source identity while the worker-board DTO intentionally
        stays UI-focused.
        """
        with self._lock:
            jobs = list(self._jobs.values())

        now = datetime.now(UTC)
        rows: list[dict[str, Any]] = []
        for job in jobs:
            heartbeat_age_seconds: int | None = None
            last_heartbeat = str(job.last_heartbeat or "")
            if last_heartbeat:
                try:
                    parsed = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=UTC)
                    heartbeat_age_seconds = max(0, int((now - parsed).total_seconds()))
                except Exception:
                    heartbeat_age_seconds = None
            rows.append(
                {
                    "job_id": redact_network_secret_text(job.job_id),
                    "worker_id": redact_network_secret_text(job.worker_id),
                    "worker_name": redact_network_secret_text(job.worker_name),
                    "source_path": redact_network_secret_text(job.source_path),
                    "claimed_at": redact_network_secret_text(job.claimed_at),
                    "last_heartbeat": redact_network_secret_text(last_heartbeat),
                    "heartbeat_age_seconds": heartbeat_age_seconds,
                }
            )
        return rows

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
