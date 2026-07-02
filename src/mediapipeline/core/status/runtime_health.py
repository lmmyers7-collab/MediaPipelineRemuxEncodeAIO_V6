from __future__ import annotations

import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.status.active_jobs import active_job_detail_rows
from mediapipeline.core.status.progress import parse_progress_datetime
from mediapipeline.core.storage.db import (
    DEFAULT_STATE_DB_COMPLETED_JOBS_MAX_ROWS,
    STATE_DB_FILENAME,
    STATE_DB_MAINTENANCE_MARKER_FILENAME,
)

RUNTIME_RELIABILITY_SCHEMA_VERSION = "desktop_runtime_reliability_counters.v1"
DEFAULT_CONSECUTIVE_ROUND_FAILURE_BLOCK_LIMIT = 12
DEFAULT_CONSECUTIVE_ROUND_FAILURE_PROBE_BACKOFF_SECONDS = 900
DEFAULT_PENDING_PUBLISH_BACKLOG_BLOCK_THRESHOLD = 100
DEFAULT_PENDING_PUBLISH_DEFERRED_BLOCK_THRESHOLD = 25
DEFAULT_PAUSE_FLAG_REVIEW_SECONDS = 1800
DEFAULT_PAUSE_FLAG_BLOCK_SECONDS = 21600
DEFAULT_LOCAL_WORKER_HEARTBEAT_GRACE_SECONDS = 900
DEFAULT_STATE_DB_MAINTENANCE_INTERVAL_SECONDS = 21600
DEFAULT_STATE_DB_WAL_REVIEW_BYTES = 33_554_432
DEFAULT_COORDINATOR_HEARTBEAT_TIMEOUT_MINS = 5
DEFAULT_COORDINATOR_FAILURE_LEDGER_MAX_ENTRIES = 5000


def runtime_reliability_counters(
    resolved: Any,
    *,
    progress: Mapping[str, Any] | None = None,
    pending_publish: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    checked_at = (now or datetime.now(UTC)).astimezone(UTC)
    progress_mapping = progress if isinstance(progress, Mapping) else _read_json_mapping(getattr(resolved, "progress_file", None))
    pending_mapping = pending_publish if isinstance(pending_publish, Mapping) else None
    config_data = getattr(resolved, "config_data", {})
    return {
        "schema_version": RUNTIME_RELIABILITY_SCHEMA_VERSION,
        "checked_at_utc": checked_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "read_only": True,
        "current_file": _current_file_counters(progress_mapping, checked_at),
        "round_failures": _round_failure_counters(progress_mapping),
        "continuous_round_state": _continuous_round_state(progress_mapping, checked_at),
        "control_flags": _control_flag_counters(resolved, progress_mapping, checked_at),
        "native_processes": _native_process_counters(progress_mapping),
        "pending_publish": _pending_publish_counters(getattr(resolved, "pending_push_path", None), pending_mapping),
        "pending_publish_backpressure": _pending_publish_backpressure_counters(
            getattr(resolved, "pending_push_path", None),
            pending_mapping,
            config_data,
            checked_at,
        ),
        "worker_heartbeat_failure": _worker_heartbeat_failure_counters(progress_mapping, config_data, checked_at),
        "worker_pending_reports": _worker_pending_report_counters(resolved, checked_at),
        "active_jobs": _active_job_counters(getattr(resolved, "active_jobs_path", None)),
        "worker_slots": _worker_slot_counters(resolved, config_data, checked_at),
        "coordinator_state": _coordinator_state_counters(resolved, checked_at),
        "debug_log": _debug_log_counters(getattr(resolved, "log_file", None), config_data),
        "sqlite_mirror": _sqlite_mirror_counters(getattr(resolved, "state_root", None), config_data),
        "state_db": _state_db_counters(getattr(resolved, "state_root", None), config_data),
        "progress_persistence": _progress_persistence_counters(progress_mapping, getattr(resolved, "progress_file", None)),
        "policy": (
            "Read-only long-run reliability counters from backend-owned runtime evidence. "
            "This payload does not drain pending publish, release worker claims, mutate queue state, "
            "kill processes, repair JSON, checkpoint SQLite, or touch media files."
        ),
    }


def _current_file_counters(progress: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    started_at = _first_text(progress, "CurrentItemStartedAt", "CurrentStageStartedAt")
    return {
        "name": _first_text(progress, "CurrentFileDisplay", "CurrentFile"),
        "path": _first_text(progress, "CurrentFilePath"),
        "stage": _first_text(progress, "CurrentStage"),
        "status": _first_text(progress, "Status"),
        "started_at": started_at,
        "age_seconds": _age_seconds(started_at, now),
    }


def _round_failure_counters(progress: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "round_failure_count": _safe_int(progress.get("RoundFailureCount"), progress.get("RoundFailures")),
        "unexpected_queue_entry_failures": _safe_int(progress.get("UnexpectedQueueEntryFailures")),
        "unexpected_round_failures": _safe_int(progress.get("UnexpectedRoundFailures")),
    }


def _continuous_round_state(progress: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    limit = _safe_int(progress.get("ConsecutiveRoundFailureBlockLimit")) or DEFAULT_CONSECUTIVE_ROUND_FAILURE_BLOCK_LIMIT
    consecutive = _safe_int(
        progress.get("ConsecutiveUnexpectedRoundFailures"),
        progress.get("UnexpectedRoundFailures"),
    )
    last_failure_at = _first_text(progress, "LastUnexpectedRoundFailureAt", "LastRoundFailureAt")
    blocked = bool(progress.get("ContinuousRoundFailuresBlocked", False)) or consecutive >= limit
    return {
        "consecutive_unexpected_round_failures": consecutive,
        "block_limit": limit,
        "last_failure_at": last_failure_at,
        "last_failure_age_seconds": _age_seconds(last_failure_at, now),
        "probe_backoff_seconds": _safe_int(progress.get("ConsecutiveRoundFailureProbeBackoffSeconds"))
        or DEFAULT_CONSECUTIVE_ROUND_FAILURE_PROBE_BACKOFF_SECONDS,
        "blocked": blocked,
    }


def _control_flag_counters(resolved: Any, progress: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    requests = progress.get("ControlRequests")
    pause_info = requests.get("Pause") if isinstance(requests, Mapping) else {}
    stop_info = requests.get("Stop") if isinstance(requests, Mapping) else {}
    pause_path = getattr(resolved, "pause_flag", None)
    stop_path = getattr(resolved, "stop_flag", None)
    pause_present = bool(pause_info.get("Requested")) if isinstance(pause_info, Mapping) else _path_exists(pause_path)
    stop_present = bool(stop_info.get("Requested")) if isinstance(stop_info, Mapping) else _path_exists(stop_path)
    pause_created = _first_text(pause_info, "CreatedAt", "LastObservedCreatedAt") if isinstance(pause_info, Mapping) else ""
    stop_created = _first_text(stop_info, "CreatedAt", "LastObservedCreatedAt") if isinstance(stop_info, Mapping) else ""
    pause_age = _age_seconds(pause_created, now) if pause_created else _file_age_seconds(pause_path, now)
    stop_age = _age_seconds(stop_created, now) if stop_created else _file_age_seconds(stop_path, now)
    return {
        "pause_flag_path": str(pause_path or ""),
        "pause_flag_present": pause_present,
        "pause_age_seconds": pause_age,
        "pause_review_seconds": _safe_int(progress.get("PauseFlagReviewSeconds")) or DEFAULT_PAUSE_FLAG_REVIEW_SECONDS,
        "pause_block_seconds": _safe_int(progress.get("PauseFlagBlockSeconds")) or DEFAULT_PAUSE_FLAG_BLOCK_SECONDS,
        "stop_flag_path": str(stop_path or ""),
        "stop_flag_present": stop_present,
        "stop_age_seconds": stop_age,
    }


def _native_process_counters(progress: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "native_no_progress_abort_count": _safe_int(
            progress.get("NativeNoProgressAbortCount"),
            progress.get("NativeIdleWatchdogAbortCount"),
        ),
    }


def _pending_publish_counters(path: Path | None, pending_publish: Mapping[str, Any] | None) -> dict[str, Any]:
    manifest_file_count = _count_files(path, "*.json")
    if isinstance(pending_publish, Mapping):
        rows = pending_publish.get("rows")
        row_count = len(rows) if isinstance(rows, list) else _safe_int(pending_publish.get("row_count"), pending_publish.get("count"))
        count_source = "payload"
        total_bytes = _safe_int(pending_publish.get("total_bytes"))
        health_count = _safe_int(pending_publish.get("health_count"))
    else:
        row_count = manifest_file_count
        count_source = "filesystem"
        total_bytes = _directory_file_bytes(path)
        health_count = 0
    return {
        "path": str(path or ""),
        "count_source": count_source,
        "backlog_count": row_count,
        "manifest_file_count": manifest_file_count,
        "health_count": health_count,
        "total_bytes": total_bytes,
    }


def _pending_publish_backpressure_counters(
    path: Path | None,
    pending_publish: Mapping[str, Any] | None,
    config_data: Mapping[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    config = config_data if isinstance(config_data, Mapping) else {}
    pending = _pending_publish_counters(path, pending_publish)
    deferred = _safe_bool(config.get("DeferredPublish"))
    normal_threshold = _safe_int(config.get("PendingPublishBacklogBlockThreshold")) or DEFAULT_PENDING_PUBLISH_BACKLOG_BLOCK_THRESHOLD
    deferred_threshold = _safe_int(config.get("PendingPublishDeferredBlockThreshold")) or DEFAULT_PENDING_PUBLISH_DEFERRED_BLOCK_THRESHOLD
    rows = pending_publish.get("rows") if isinstance(pending_publish, Mapping) else None
    oldest_age = _oldest_pending_age_seconds(rows, now)
    retry_exhausted = _pending_retry_exhausted_count(rows)
    backlog_count = _safe_int(pending.get("backlog_count"))
    reason = ""
    if deferred and backlog_count >= deferred_threshold:
        reason = "deferred_backlog_threshold"
    elif not deferred and backlog_count >= normal_threshold:
        reason = "backlog_threshold"
    elif not deferred and oldest_age is not None and oldest_age >= 72 * 60 * 60:
        reason = "oldest_age_threshold"
    elif not deferred and retry_exhausted > 0:
        reason = "retry_exhausted"
    return {
        "path": str(path or ""),
        "manifest_count": backlog_count,
        "oldest_age_seconds": oldest_age,
        "total_bytes": _safe_int(pending.get("total_bytes")),
        "deferred_publish": deferred,
        "normal_block_threshold": normal_threshold,
        "deferred_block_threshold": deferred_threshold,
        "retry_exhausted_count": retry_exhausted,
        "blocked": bool(reason),
        "block_reason": reason,
    }


def _worker_heartbeat_failure_counters(
    progress: Mapping[str, Any],
    config_data: Mapping[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    config = config_data if isinstance(config_data, Mapping) else {}
    timeout_mins = _safe_int(config.get("CoordinatorHeartbeatTimeoutMins")) or DEFAULT_COORDINATOR_HEARTBEAT_TIMEOUT_MINS
    abort_threshold = _heartbeat_failure_abort_threshold_seconds(timeout_mins)
    started_at = _first_text(
        progress,
        "HeartbeatFailureStartedAt",
        "WorkerHeartbeatFailureStartedAt",
        "CoordinatorHeartbeatFailureStartedAt",
    )
    reported_age = _safe_int(
        progress.get("HeartbeatFailureAgeSeconds"),
        progress.get("WorkerHeartbeatFailureAgeSeconds"),
        progress.get("CoordinatorHeartbeatFailureAgeSeconds"),
    )
    computed_age = _age_seconds(started_at, now) if started_at else None
    age_seconds = computed_age if computed_age is not None else reported_age if reported_age > 0 else None
    failure_active = bool(started_at or (age_seconds is not None and age_seconds > 0))
    return {
        "coordinator_heartbeat_timeout_mins": timeout_mins,
        "abort_threshold_seconds": abort_threshold,
        "failure_started_at": started_at,
        "failure_age_seconds": age_seconds,
        "age_seconds": age_seconds,
        "failure_active": failure_active,
        "abort_due": bool(failure_active and age_seconds is not None and age_seconds >= abort_threshold),
        "source": "progress_evidence" if failure_active else "derived_config_threshold",
    }


def _heartbeat_failure_abort_threshold_seconds(timeout_mins: int) -> int:
    try:
        timeout_seconds = int(timeout_mins) * 60
    except (TypeError, ValueError):
        timeout_seconds = DEFAULT_COORDINATOR_HEARTBEAT_TIMEOUT_MINS * 60
    return max(60, min(240, timeout_seconds - 60))


def _worker_pending_report_counters(resolved: Any, now: datetime) -> dict[str, Any]:
    state_dir = _network_state_dir(resolved)
    worker_state_path = state_dir / "worker_state.json" if state_dir is not None else None
    queued_dir = state_dir / "pending_done_reports" if state_dir is not None else None
    review_dir = state_dir / "pending_done_reports_review" if state_dir is not None else None
    worker_state = _read_json_mapping(worker_state_path)
    read_error = str(worker_state.get("_read_error") or "")
    legacy_pending = isinstance(worker_state.get("pending_done_report"), Mapping)
    queued_count = _count_files(queued_dir, "*.json")
    review_count = _count_files(review_dir, "*.json")
    oldest_age = _oldest_file_age_seconds([queued_dir, review_dir], "*.json", now)
    if legacy_pending:
        legacy_age = _file_age_seconds(worker_state_path, now)
        if legacy_age is not None:
            oldest_age = max([age for age in (oldest_age, legacy_age) if age is not None])
    return {
        "state_dir": str(state_dir or ""),
        "worker_state_path": str(worker_state_path or ""),
        "worker_state_read_error": read_error,
        "legacy_single_slot_pending": legacy_pending,
        "queued_report_count": queued_count,
        "review_report_count": review_count,
        "pending_report_count": queued_count + review_count + (1 if legacy_pending else 0),
        "oldest_pending_report_age_seconds": oldest_age,
        "blocked": bool(read_error or legacy_pending or queued_count or review_count),
        "block_reason": "worker_state_read_error" if read_error else "pending_done_reports_present" if (legacy_pending or queued_count or review_count) else "",
    }


def _active_job_counters(path: Path | None) -> dict[str, Any]:
    rows = active_job_detail_rows(path, max_items=100000)
    total_count = len(rows)
    blocking_count = sum(1 for row in rows if str(row.get("status_state") or "").casefold() == "blocked")
    running_count = sum(1 for row in rows if str(row.get("status_state") or "").casefold() == "running")
    warning_count = sum(1 for row in rows if str(row.get("status_state") or "").casefold() == "warning")
    terminal_count = sum(1 for row in rows if str(row.get("status_state") or "").casefold() == "completed")
    ambiguous_count = max(0, total_count - terminal_count)
    return {
        "path": str(path or ""),
        "total_count": total_count,
        "blocking_count": blocking_count,
        "running_count": running_count,
        "warning_count": warning_count,
        "terminal_count": terminal_count,
        "ignored_count": 0,
        "ignored_pids": [],
        "ambiguous_count": ambiguous_count,
        "ambiguous_read_first": False,
        "policy": "Passive evidence only; ActiveJobs records do not block launch, close-readiness, or autonomy health.",
    }


def _worker_slot_counters(resolved: Any, config_data: Mapping[str, Any] | None, now: datetime) -> dict[str, Any]:
    state_root = getattr(resolved, "state_root", None)
    workers_root = Path(state_root) / "Workers" if state_root is not None else None
    grace_seconds = _safe_int((config_data or {}).get("LocalWorkerHeartbeatGraceSeconds")) or DEFAULT_LOCAL_WORKER_HEARTBEAT_GRACE_SECONDS
    heartbeat_paths: list[Path] = []
    if workers_root is not None and workers_root.exists():
        try:
            heartbeat_paths = [path for path in workers_root.glob("slot-*/worker_heartbeat.json") if path.is_file()]
        except OSError:
            heartbeat_paths = []
    ages = [_file_age_seconds(path, now) for path in heartbeat_paths]
    numeric_ages = [age for age in ages if age is not None]
    stale_count = sum(1 for age in numeric_ages if age >= grace_seconds)
    return {
        "workers_root": str(workers_root or ""),
        "active_child_count": len(heartbeat_paths),
        "oldest_child_age_seconds": max(numeric_ages) if numeric_ages else None,
        "stale_heartbeat_count": stale_count,
        "heartbeat_grace_seconds": grace_seconds,
    }


def _coordinator_state_counters(resolved: Any, now: datetime) -> dict[str, Any]:
    state_dir = _network_state_dir(resolved)
    inflight_path = state_dir / "coordinator_inflight.json" if state_dir is not None else None
    payload = _read_json_mapping(inflight_path)
    read_error = str(payload.get("_read_error") or "") if isinstance(payload, Mapping) else ""
    quarantine = payload.get("reclaimed_source_quarantine") if isinstance(payload, Mapping) else []
    if isinstance(quarantine, Mapping):
        quarantine_items = [item for item in quarantine.values() if isinstance(item, Mapping)]
    elif isinstance(quarantine, list):
        quarantine_items = [item for item in quarantine if isinstance(item, Mapping)]
    else:
        quarantine_items = []
    active_quarantine_items: list[Mapping[str, Any]] = []
    for item in quarantine_items:
        expires_at = _parse_datetime(item.get("expires_at"))
        if expires_at is None or expires_at > now:
            active_quarantine_items.append(item)
    oldest_quarantine_age = _oldest_mapping_age_seconds(active_quarantine_items, now, "reclaimed_at", "created_at")

    failure_ledger = payload.get("failure_ledger") if isinstance(payload, Mapping) else []
    if isinstance(failure_ledger, Mapping):
        failure_ledger_count = len(failure_ledger)
    elif isinstance(failure_ledger, list):
        failure_ledger_count = len(failure_ledger)
    else:
        failure_ledger_count = 0
    late_reports = payload.get("late_terminal_reports") if isinstance(payload, Mapping) else []
    late_report_count = len(late_reports) if isinstance(late_reports, list) else 0
    return {
        "state_dir": str(state_dir or ""),
        "inflight_state_path": str(inflight_path or ""),
        "read_error": read_error,
        "reclaimed_source_quarantine_count": len(active_quarantine_items),
        "reclaimed_source_quarantine_oldest_age_seconds": oldest_quarantine_age,
        "late_terminal_report_count": late_report_count,
        "failure_ledger_count": failure_ledger_count,
        "failure_ledger_max_entries": DEFAULT_COORDINATOR_FAILURE_LEDGER_MAX_ENTRIES,
    }


def _debug_log_counters(path: Path | None, config_data: Mapping[str, Any] | None) -> dict[str, Any]:
    config = config_data if isinstance(config_data, Mapping) else {}
    max_bytes = _safe_int(config.get("PipelineDebugLogMaxBytes")) or 104_857_600
    size = _file_size(path)
    rotation_state = "missing"
    if path is not None and _path_exists(path):
        rotation_state = "rotation_due_or_pending" if size >= max_bytes else "within_limit"
    return {
        "path": str(path or ""),
        "size_bytes": size,
        "max_bytes": max_bytes,
        "rotation_state": rotation_state,
        "rotation_due": bool(size >= max_bytes and path is not None and _path_exists(path)),
    }


def _sqlite_mirror_counters(state_root: Path | None, config_data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    db_path = Path(state_root) / STATE_DB_FILENAME if state_root is not None else None
    wal_path = db_path.with_name(f"{db_path.name}-wal") if db_path is not None else None
    shm_path = db_path.with_name(f"{db_path.name}-shm") if db_path is not None else None
    completed_jobs_max = _state_db_completed_jobs_max_rows(config_data)
    completed_count, completed_error = _sqlite_table_count(db_path, "completed_jobs")
    return {
        "path": str(db_path or ""),
        "db_size_bytes": _file_size(db_path),
        "wal_size_bytes": _file_size(wal_path),
        "shm_size_bytes": _file_size(shm_path),
        "write_failures": None,
        "write_failure_source": "in-process StateDb.health_counters() when a mirror instance is active",
        "completed_jobs_count": completed_count,
        "completed_jobs_max_rows": completed_jobs_max,
        "completed_jobs_count_error": completed_error,
    }


def _state_db_counters(state_root: Path | None, config_data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    maintenance_path = Path(state_root) / STATE_DB_MAINTENANCE_MARKER_FILENAME if state_root is not None else None
    maintenance = _read_json_mapping(maintenance_path)
    return {
        **_sqlite_mirror_counters(state_root, config_data),
        "maintenance_path": str(maintenance_path or ""),
        "last_maintenance": dict(maintenance) if isinstance(maintenance, Mapping) else {},
        "maintenance_interval_seconds": DEFAULT_STATE_DB_MAINTENANCE_INTERVAL_SECONDS,
        "wal_review_bytes": DEFAULT_STATE_DB_WAL_REVIEW_BYTES,
        "completed_jobs_max_rows": _state_db_completed_jobs_max_rows(config_data),
    }


def _progress_persistence_counters(progress: Mapping[str, Any], path: Path | None) -> dict[str, Any]:
    if not progress:
        healthy = True
        write_failures = 0
        source = "progress_file_missing"
    else:
        healthy = bool(progress.get("ProgressPersistenceHealthy", True))
        write_failures = _safe_int(progress.get("ProgressWriteFailures"))
        source = "pipeline_progress"
    return {
        "path": str(path or ""),
        "healthy": healthy,
        "write_failures": write_failures,
        "source": source,
    }


def _network_state_dir(resolved: Any) -> Path | None:
    app_state_path = getattr(resolved, "app_state_path", None)
    if app_state_path:
        return Path(app_state_path).parent
    state_root = getattr(resolved, "state_root", None)
    if state_root is not None:
        return Path(state_root) / "App"
    app_root = getattr(resolved, "app_root", None)
    return Path(app_root) if app_root is not None else None


def _state_db_completed_jobs_max_rows(config_data: Mapping[str, Any] | None) -> int:
    config = config_data if isinstance(config_data, Mapping) else {}
    configured = _safe_int(config.get("StateDbCompletedJobsMaxRows"))
    return configured if configured > 0 else DEFAULT_STATE_DB_COMPLETED_JOBS_MAX_ROWS


def _sqlite_table_count(db_path: Path | None, table: str) -> tuple[int | None, str]:
    if db_path is None or not Path(db_path).exists() or not Path(db_path).is_file():
        return None, ""
    try:
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            count = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            conn.close()
        return count, ""
    except Exception as exc:
        return None, str(exc)


def _oldest_file_age_seconds(roots: list[Path | None], pattern: str, now: datetime) -> int | None:
    ages: list[int] = []
    for root in roots:
        if root is None or not Path(root).exists() or not Path(root).is_dir():
            continue
        try:
            paths = [item for item in Path(root).glob(pattern) if item.is_file()]
        except OSError:
            continue
        for path in paths:
            age = _file_age_seconds(path, now)
            if age is not None:
                ages.append(age)
    return max(ages) if ages else None


def _oldest_mapping_age_seconds(items: list[Mapping[str, Any]], now: datetime, *keys: str) -> int | None:
    ages: list[int] = []
    for item in items:
        timestamp = _first_text(item, *keys)
        age = _age_seconds(timestamp, now)
        if age is not None:
            ages.append(age)
    return max(ages) if ages else None


def _parse_datetime(value: Any) -> datetime | None:
    parsed = parse_progress_datetime(str(value or ""))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _oldest_pending_age_seconds(rows: Any, now: datetime) -> int | None:
    if not isinstance(rows, list):
        return None
    ages: list[int] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        timestamp = _first_text(row, "parked_at", "ParkedAt", "created_at", "CreatedAt")
        age = _age_seconds(timestamp, now)
        if age is not None:
            ages.append(age)
    return max(ages) if ages else None


def _pending_retry_exhausted_count(rows: Any) -> int:
    if not isinstance(rows, list):
        return 0
    count = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        retry_count = _safe_int(row.get("retry_count"), row.get("RetryCount"))
        retry_limit = _safe_int(row.get("retry_limit"), row.get("RetryLimit")) or 3
        if retry_count >= retry_limit:
            count += 1
    return count


def _read_json_mapping(path: Path | None) -> Mapping[str, Any]:
    if path is None or not Path(path).exists() or not Path(path).is_file():
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_read_error": str(exc)}
    return payload if isinstance(payload, Mapping) else {"_json_root": type(payload).__name__}


def _age_seconds(value: Any, now: datetime) -> int | None:
    parsed = parse_progress_datetime(str(value or ""))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max(0, int((now - parsed.astimezone(UTC)).total_seconds()))


def _first_text(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _count_files(path: Path | None, pattern: str) -> int:
    if path is None or not Path(path).exists() or not Path(path).is_dir():
        return 0
    try:
        return sum(1 for item in Path(path).glob(pattern) if item.is_file())
    except OSError:
        return 0


def _directory_file_bytes(path: Path | None) -> int:
    if path is None or not Path(path).exists() or not Path(path).is_dir():
        return 0
    total = 0
    try:
        for item in Path(path).iterdir():
            if item.is_file():
                total += _file_size(item)
    except OSError:
        return total
    return total


def _file_size(path: Path | None) -> int:
    if path is None:
        return 0
    try:
        return int(Path(path).stat().st_size)
    except OSError:
        return 0


def _path_exists(path: Path | None) -> bool:
    try:
        return bool(path is not None and Path(path).exists())
    except OSError:
        return False


def _file_age_seconds(path: Path | None, now: datetime) -> int | None:
    if path is None:
        return None
    try:
        modified = datetime.fromtimestamp(Path(path).stat().st_mtime, tz=UTC)
    except OSError:
        return None
    return max(0, int((now - modified).total_seconds()))


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    return text in {"1", "true", "yes", "on"}


def _safe_int(*values: Any) -> int:
    for value in values:
        try:
            if value in (None, ""):
                continue
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


__all__ = [
    "RUNTIME_RELIABILITY_SCHEMA_VERSION",
    "runtime_reliability_counters",
]
