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

_log = logging.getLogger(__name__)


def normalize_source_identity(source_path: Any) -> str:
    """Return the coordinator identity key for a Windows/UNC source path."""
    text = str(source_path or "").strip()
    if not text:
        return ""
    normalized = ntpath.normpath(text.replace("/", "\\"))
    return ntpath.normcase(normalized)


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
    return f"{str(worker_id or '').strip()}\0{normalize_source_identity(source_path)}"


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


def _parse_utc_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


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
    job_kind:          str   = "pipeline_queue"
    claim_metadata:    dict  = field(default_factory=dict)

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
            "job_kind":          self.job_kind,
            "claim_metadata":    self.claim_metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InFlightJob:
        raw_metadata = d.get("claim_metadata", {})
        claim_metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
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
            job_kind=str(d.get("job_kind", "pipeline_queue") or "pipeline_queue"),
            claim_metadata=claim_metadata,
        )


# ---------------------------------------------------------------------------
# InFlightRegistry
# ---------------------------------------------------------------------------


__all__ = (
    "normalize_source_identity",
    "_default_worker_stats",
    "_ensure_worker_stats_fields",
    "_safe_worker_stats",
    "_safe_snapshot_progress",
    "_failure_ledger_key",
    "_safe_failure_reason_code",
    "_safe_failure_ledger_entry",
    "_parse_utc_datetime",
    "InFlightJob",
)
