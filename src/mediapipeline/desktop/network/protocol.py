"""
network.protocol
================
Request and response dataclasses for the coordinator HTTP API.

All dataclasses are stdlib-only (no third-party deps) and serialise to/from
plain dicts so they can be JSON-encoded with the standard ``json`` module.

This module is imported by both the coordinator (server side) and the worker
dispatcher (client side) so the wire format is defined in one place.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .failure_reasons import bounded_failure_reason, normalize_failure_reason_code


PING_RESPONSE_SCHEMA_VERSION = "desktop_network_coordinator_ping.v1"


def coerce_finite_float(value: Any, field_name: str, *, minimum: float | None = None) -> float:
    """Coerce a wire value to a finite float with optional lower bound."""
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return result


def coerce_nonnegative_int(value: Any, field_name: str) -> int:
    """Coerce a wire value to a non-negative integer."""
    result = int(value)
    if result < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return result


def coerce_optional_bool(d: dict[str, Any], field_name: str, *, default: bool) -> bool:
    """Read an optional wire boolean without accepting truthy/falsy coercions."""
    if field_name not in d:
        return default
    value = d[field_name]
    if type(value) is not bool:
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _coerce_strict_nonnegative_int_field(d: dict[str, Any], field_name: str, *, default: int) -> int:
    """Read an optional wire integer without bool/string/float coercions."""
    if field_name not in d:
        return default
    value = d[field_name]
    if type(value) is not int:
        raise ValueError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return value


def coerce_library_id_list(value: Any) -> list[str]:
    """Return a bounded, deduped list of library IDs from wire data."""
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = [value]

    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        if isinstance(raw, (dict, list, tuple, set)):
            continue
        text = str(raw or "").strip()
        if not text:
            continue
        text = text[:96]
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


# ---------------------------------------------------------------------------
# /api/ping
# ---------------------------------------------------------------------------

@dataclass
class PingResponse:
    """Response body for auth-required ``GET /api/ping``."""

    ok: bool = True
    server_time: str = ""
    schema_version: str = PING_RESPONSE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "server_time": self.server_time,
        }


# ---------------------------------------------------------------------------
# /api/claim
# ---------------------------------------------------------------------------

@dataclass
class ClaimResponse:
    """Response body for ``GET /api/claim``.

    ``status`` is ``"ok"`` when a job was assigned or ``"empty"`` when the
    queue has no more work.  All other fields are only populated on ``"ok"``.

    ``retry_on_failure`` is ``True`` (default) when the coordinator is happy
    for the job to be re-queued if this encode fails.  Set to ``False`` when
    the file already appears in the failure log, signalling that the worker
    should mark it as a permanent failure rather than letting it loop.
    """

    status:             str   = "empty"       # "ok" | "empty"
    job_id:             str   = ""
    source_path:        str   = ""
    library_id:         str   = ""
    relative_path:      str   = ""
    priority:           bool  = False
    estimated_size_gb:  float = 0.0
    encode_config:      dict  = field(default_factory=dict)
    retry_on_failure:   bool  = True
    # W4 — coordinator backoff hint, only meaningful when status="empty".
    # Workers SHOULD wait at least this many seconds before re-polling,
    # but MAY clamp to their own configured maximum (WorkerPollIntervalSecs)
    # so an over-eager hint can't dilate the configured cadence. Zero or
    # missing means "use the worker's default poll interval" — old workers
    # ignore the field entirely so the protocol remains backward-compatible.
    retry_after_seconds: int  = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status":              self.status,
            "job_id":              self.job_id,
            "source_path":         self.source_path,
            "library_id":          self.library_id,
            "relative_path":       self.relative_path,
            "priority":            self.priority,
            "estimated_size_gb":   self.estimated_size_gb,
            "encode_config":       self.encode_config,
            "retry_on_failure":    self.retry_on_failure,
            "retry_after_seconds": self.retry_after_seconds,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ClaimResponse:
        return cls(
            status=str(d.get("status", "empty")),
            job_id=str(d.get("job_id", "")),
            source_path=str(d.get("source_path", "")),
            library_id=str(d.get("library_id", "")),
            relative_path=str(d.get("relative_path", "")),
            priority=coerce_optional_bool(d, "priority", default=False),
            estimated_size_gb=coerce_finite_float(d.get("estimated_size_gb", 0.0), "estimated_size_gb", minimum=0.0),
            encode_config=dict(d.get("encode_config", {})),
            retry_on_failure=coerce_optional_bool(d, "retry_on_failure", default=True),
            retry_after_seconds=_coerce_strict_nonnegative_int_field(d, "retry_after_seconds", default=0),
        )

    @classmethod
    def empty(cls, retry_after_seconds: int = 0) -> ClaimResponse:
        return cls(status="empty", retry_after_seconds=int(retry_after_seconds or 0))


# ---------------------------------------------------------------------------
# /api/done
# ---------------------------------------------------------------------------

@dataclass
class DoneRequest:
    """Request body for ``POST /api/done``."""

    job_id:            str   = ""
    worker_id:         str   = ""
    success:           bool  = False
    output_path:       str   = ""
    elapsed_seconds:   float = 0.0
    output_size_bytes: int   = 0
    error_message:     str   = ""
    completion_status: str   = ""
    reason_code:       str   = ""
    reason:            str   = ""
    publish_state:     str   = ""
    publish_mode:      str   = ""
    route:             str   = ""
    queue_terminal:    bool  = False
    # When True, the job is returned to the queue without a failure record.
    # Used by WorkerDispatcher.release() on clean shutdown.
    released:          bool  = False
    # Echo of ClaimResponse.retry_on_failure.  When False, the coordinator
    # should remove this file from the queue on failure rather than re-queueing.
    retry_on_failure:  bool  = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id":            self.job_id,
            "worker_id":         self.worker_id,
            "success":           self.success,
            "output_path":       self.output_path,
            "elapsed_seconds":   self.elapsed_seconds,
            "output_size_bytes": self.output_size_bytes,
            "error_message":     self.error_message,
            "completion_status": self.completion_status,
            "reason_code":       self.reason_code,
            "reason":            self.reason,
            "publish_state":     self.publish_state,
            "publish_mode":      self.publish_mode,
            "route":             self.route,
            "queue_terminal":    self.queue_terminal,
            "released":          self.released,
            "retry_on_failure":  self.retry_on_failure,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DoneRequest:
        return cls(
            job_id=str(d.get("job_id", "")),
            worker_id=str(d.get("worker_id", "")),
            success=coerce_optional_bool(d, "success", default=False),
            output_path=str(d.get("output_path", "")),
            elapsed_seconds=coerce_finite_float(d.get("elapsed_seconds", 0.0), "elapsed_seconds", minimum=0.0),
            output_size_bytes=_coerce_strict_nonnegative_int_field(d, "output_size_bytes", default=0),
            error_message=str(d.get("error_message", "")),
            completion_status=str(d.get("completion_status", "")),
            reason_code=normalize_failure_reason_code(d.get("reason_code", "")),
            reason=bounded_failure_reason(d.get("reason", "")),
            publish_state=str(d.get("publish_state", "")),
            publish_mode=str(d.get("publish_mode", "")),
            route=str(d.get("route", "")),
            queue_terminal=coerce_optional_bool(d, "queue_terminal", default=False),
            released=coerce_optional_bool(d, "released", default=False),
            retry_on_failure=coerce_optional_bool(d, "retry_on_failure", default=True),
        )


# ---------------------------------------------------------------------------
# /api/heartbeat
# ---------------------------------------------------------------------------

def coerce_progress_percent(value: Any) -> float:
    """Coerce a wire progress value into a finite 0..100 percentage."""
    progress = float(value)
    if not math.isfinite(progress):
        raise ValueError("progress_percent must be finite")
    return max(0.0, min(100.0, progress))


@dataclass
class HeartbeatRequest:
    """Request body for ``POST /api/heartbeat``."""

    job_id:           str   = ""
    worker_id:        str   = ""
    progress_percent: float = 0.0
    current_stage:    str   = ""
    fps:              float = 0.0
    eta_seconds:      int   = 0
    accessible_library_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id":           self.job_id,
            "worker_id":        self.worker_id,
            "progress_percent": self.progress_percent,
            "current_stage":    self.current_stage,
            "fps":              self.fps,
            "eta_seconds":      self.eta_seconds,
            "accessible_library_ids": coerce_library_id_list(self.accessible_library_ids),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HeartbeatRequest:
        return cls(
            job_id=str(d.get("job_id", "")),
            worker_id=str(d.get("worker_id", "")),
            progress_percent=coerce_progress_percent(d.get("progress_percent", 0.0)),
            current_stage=str(d.get("current_stage", "")),
            fps=coerce_finite_float(d.get("fps", 0.0), "fps", minimum=0.0),
            eta_seconds=_coerce_strict_nonnegative_int_field(d, "eta_seconds", default=0),
            accessible_library_ids=coerce_library_id_list(d.get("accessible_library_ids", [])),
        )


@dataclass
class HeartbeatResponse:
    """Response body for ``POST /api/heartbeat``."""

    # "ok" — continue encoding.
    # "reclaimed" — coordinator timed out this job; worker should abort.
    status: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status}


# ---------------------------------------------------------------------------
# /api/workers
# ---------------------------------------------------------------------------

@dataclass
class WorkerEntry:
    """One row in the workers board."""

    worker_id:          str   = ""
    worker_name:        str   = ""
    status:             str   = "idle"   # "encoding" | "idle"
    current_file:       str   = ""
    progress_percent:   float = 0.0
    current_stage:      str   = ""
    last_heartbeat:     str   = ""       # ISO-8601 string
    claimed_at:         str   = ""       # ISO-8601 string
    # Cumulative session stats (Phase 3 — performance history).
    files_completed:    int   = 0
    total_gb_encoded:   float = 0.0      # sum of estimated_size_gb for success
    avg_speed_gbh:      float = 0.0      # total_gb / total_encode_hours
    last_failure_reason_code: str = ""
    last_failure_reason:      str = ""
    last_failure_job_id:      str = ""
    last_failure_source_path: str = ""
    last_failure_at:          str = ""
    failure_streak_reason_code: str = ""
    failure_streak_count:       int = 0
    worker_misconfigured_reason_code: str = ""
    worker_misconfigured_at:          str = ""
    accessible_library_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id":         self.worker_id,
            "worker_name":       self.worker_name,
            "status":            self.status,
            "current_file":      self.current_file,
            "progress_percent":  self.progress_percent,
            "current_stage":     self.current_stage,
            "last_heartbeat":    self.last_heartbeat,
            "claimed_at":        self.claimed_at,
            "files_completed":   self.files_completed,
            "total_gb_encoded":  self.total_gb_encoded,
            "avg_speed_gbh":     self.avg_speed_gbh,
            "last_failure_reason_code": self.last_failure_reason_code,
            "last_failure_reason":      self.last_failure_reason,
            "last_failure_job_id":      self.last_failure_job_id,
            "last_failure_source_path": self.last_failure_source_path,
            "last_failure_at":          self.last_failure_at,
            "failure_streak_reason_code": self.failure_streak_reason_code,
            "failure_streak_count":       self.failure_streak_count,
            "worker_misconfigured_reason_code": self.worker_misconfigured_reason_code,
            "worker_misconfigured_at":          self.worker_misconfigured_at,
            "accessible_library_ids": coerce_library_id_list(self.accessible_library_ids),
        }


# ---------------------------------------------------------------------------
# /api/log  (cluster-wide observability)
# ---------------------------------------------------------------------------

@dataclass
class LogEntryRequest:
    """Request body for ``POST /api/log``.

    A worker (or the coordinator-encoding-locally path) sends one of these for
    every interesting lifecycle event: dispatcher start, claim, encode start,
    encode complete (success / failure), reclaim, abort, shutdown, etc.

    The coordinator appends them — one line per entry — to ``cluster.log``
    in its state directory so the operator has a single chronological view
    across every machine in the cluster.
    """

    timestamp:    str   = ""        # ISO-8601 with timezone, set by sender
    worker_id:    str   = ""
    worker_name:  str   = ""
    role:         str   = "worker"  # "worker" | "coordinator"
    level:        str   = "INFO"    # DEBUG | INFO | WARN | ERROR
    event:        str   = ""        # short stable token, e.g. "claim_ok"
    message:      str   = ""        # free-form human-readable
    job_id:       str   = ""
    source_path:  str   = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":   self.timestamp,
            "worker_id":   self.worker_id,
            "worker_name": self.worker_name,
            "role":        self.role,
            "level":       self.level,
            "event":       self.event,
            "message":     self.message,
            "job_id":      self.job_id,
            "source_path": self.source_path,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LogEntryRequest:
        return cls(
            timestamp   = str(d.get("timestamp", "")),
            worker_id   = str(d.get("worker_id", "")),
            worker_name = str(d.get("worker_name", "")),
            role        = str(d.get("role", "worker")),
            level       = str(d.get("level", "INFO")).upper(),
            event       = str(d.get("event", "")),
            message     = str(d.get("message", "")),
            job_id      = str(d.get("job_id", "")),
            source_path = str(d.get("source_path", "")),
        )


@dataclass
class WorkersResponse:
    """Response body for ``GET /api/workers``."""

    workers:                list[WorkerEntry] = field(default_factory=list)
    queue_remaining:         int              = 0
    jobs_completed_session:  int              = 0
    jobs_failed_session:     int              = 0
    # W6 — coordinator wall-clock at response time (ISO-8601, with tz).
    # Lets the UI compute heartbeat ages relative to the coordinator
    # rather than the local coordinator host, which removes false "stale"
    # warnings on hosts whose clocks drift relative to the coordinator.
    # Older clients ignore the field; newer clients prefer it over
    # ``datetime.now()`` when present.
    coordinator_now:         str              = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "workers":               [w.to_dict() for w in self.workers],
            "queue_remaining":        self.queue_remaining,
            "jobs_completed_session": self.jobs_completed_session,
            "jobs_failed_session":    self.jobs_failed_session,
            "coordinator_now":        self.coordinator_now,
        }
