from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any
import uuid
from collections.abc import Iterable, Mapping

from mediapipeline.core.diagnostics.autonomy_evaluators import (
    category_evaluation_error as autonomy_category_evaluation_error,
    evaluate_category as autonomy_evaluate_category,
)
from mediapipeline.core.diagnostics.autonomy_growth import (
    acquire_growth_snapshot_lock,
    bounded_snapshot_limit,
    growth_snapshot_write_result,
    minimum_present,
    release_growth_snapshot_lock,
)
from mediapipeline.core.diagnostics.autonomy_policy import AutonomyPolicy, autonomy_policy_from_resolved
from mediapipeline.core.diagnostics.autonomy_recovery import (
    journal_archive_action,
    pending_publish_drain_action,
    pending_publish_recovery_plan_action,
)
from mediapipeline.core.diagnostics.autonomy_scan import (
    directory_size_scan,
    limited_iter_files,
    unique_observed_bytes,
)
from mediapipeline.core.diagnostics.autonomy_types import (
    category as autonomy_category,
    issue as autonomy_issue,
    issue_status as autonomy_issue_status,
    overall_status as autonomy_overall_status,
    status_state as autonomy_status_state,
)
from mediapipeline.core.kernel.contracts.pending_publish import PENDING_PUSH_RETRY_LIMIT
from mediapipeline.core.status.runtime_health import runtime_reliability_counters

from mediapipeline.core.diagnostics.autonomy_health_constants import *  # noqa: F403


from mediapipeline.core.diagnostics.autonomy_health_support import *  # noqa: F403
from mediapipeline.core.diagnostics.autonomy_health_projection import *  # noqa: F403

def _runtime_health_category(runtime_reliability: Mapping[str, Any], *, policy: AutonomyPolicy) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    continuous_round_state = runtime_reliability.get("continuous_round_state")
    if isinstance(continuous_round_state, Mapping):
        consecutive = _safe_int(continuous_round_state.get("consecutive_unexpected_round_failures"))
        limit = _safe_int(continuous_round_state.get("block_limit"))
        if bool(continuous_round_state.get("blocked")):
            blockers.append(
                _issue(
                    "autonomy_round_failures_blocked",
                    "runtime_health",
                    "high",
                    f"Continuous pipeline round failures reached the block threshold: consecutive={consecutive}; limit={limit}.",
                    next_action="Inspect the latest pipeline_round_unexpected_failure events before starting or trusting unattended work.",
                )
            )
    control_flags = runtime_reliability.get("control_flags")
    if isinstance(control_flags, Mapping):
        pause_age = _safe_int(control_flags.get("pause_age_seconds"))
        pause_review = _safe_int(control_flags.get("pause_review_seconds"))
        pause_block = _safe_int(control_flags.get("pause_block_seconds"))
        if bool(control_flags.get("pause_flag_present")) and pause_age > 0:
            issue = _issue(
                "autonomy_pause_flag_stale",
                "runtime_health",
                "medium" if pause_age < pause_block else "high",
                f"Pipeline pause flag is present; age_seconds={pause_age}.",
                evidence_path=str(control_flags.get("pause_flag_path") or ""),
                next_action="Confirm whether the operator pause is intentional before unattended operation.",
            )
            if pause_age >= pause_block:
                blockers.append(issue)
            elif pause_age >= pause_review:
                review_items.append(issue)
    pending_backpressure = runtime_reliability.get("pending_publish_backpressure")
    if isinstance(pending_backpressure, Mapping) and bool(pending_backpressure.get("blocked")):
        blockers.append(
            _issue(
                "autonomy_pending_backlog_blocked",
                "runtime_health",
                "high",
                f"Pending publish backpressure is blocking new work: {pending_backpressure.get('block_reason') or 'threshold'}.",
                evidence_path=str(pending_backpressure.get("path") or ""),
                next_action="Use backend-owned Pending Publish diagnostics/recovery before adding more unattended work.",
            )
        )
    worker_slots = runtime_reliability.get("worker_slots")
    if isinstance(worker_slots, Mapping):
        stale_heartbeats = _safe_int(worker_slots.get("stale_heartbeat_count"))
        if stale_heartbeats > 0:
            blockers.append(
                _issue(
                    "autonomy_worker_slot_stale",
                    "runtime_health",
                    "high",
                    f"Local worker heartbeat evidence is stale for {stale_heartbeats} slot(s).",
                    evidence_path=str(worker_slots.get("workers_root") or ""),
                    next_action="Let backend lifecycle cleanup reconcile stale local worker slots before starting more unattended work.",
                )
            )
    progress = runtime_reliability.get("progress_persistence")
    if isinstance(progress, Mapping):
        progress_healthy = bool(progress.get("healthy", True))
        progress_failures = _safe_int(progress.get("write_failures"))
        if not progress_healthy or progress_failures > 0:
            blockers.append(
                _issue(
                    "autonomy_progress_persistence_unhealthy",
                    "runtime_health",
                    "high",
                    f"Progress persistence is unhealthy; write_failures={progress_failures}.",
                    evidence_path=str(progress.get("path") or ""),
                    next_action="Fix progress-state persistence before launching unattended work; progress writes are the stop reason evidence.",
                )
            )
    round_failures = runtime_reliability.get("round_failures")
    if isinstance(round_failures, Mapping):
        round_failure_count = _safe_int(round_failures.get("round_failure_count"))
        unexpected_item_count = _safe_int(round_failures.get("unexpected_queue_entry_failures"))
        unexpected_round_count = _safe_int(round_failures.get("unexpected_round_failures"))
        if round_failure_count > 0 or unexpected_item_count > 0 or unexpected_round_count > 0:
            review_items.append(
                _issue(
                    "autonomy_runtime_round_failures_present",
                    "runtime_health",
                    "medium",
                    f"Runtime failure counters are nonzero: round={round_failure_count}; item={unexpected_item_count}; loop={unexpected_round_count}.",
                    next_action="Review the latest failure markers and event log before trusting a long unattended run.",
                )
            )
    native_processes = runtime_reliability.get("native_processes")
    if isinstance(native_processes, Mapping):
        abort_count = _safe_int(native_processes.get("native_no_progress_abort_count"))
        if abort_count > 0:
            review_items.append(
                _issue(
                    "autonomy_native_no_progress_aborts_present",
                    "runtime_health",
                    "medium",
                    f"Native no-progress watchdog aborts recorded: {abort_count}.",
                    next_action="Inspect FFmpeg/MKVToolNix no-progress abort evidence before starting more unattended work.",
                )
            )
    worker_reports = runtime_reliability.get("worker_pending_reports")
    if isinstance(worker_reports, Mapping):
        pending_reports = _safe_int(worker_reports.get("pending_report_count"))
        if pending_reports > 0:
            review_items.append(
                _issue(
                    "autonomy_worker_pending_done_reports_present",
                    "runtime_health",
                    "medium",
                    f"Worker pending done report evidence remains queued or under review: {pending_reports}.",
                    evidence_path=str(worker_reports.get("state_dir") or ""),
                    next_action="Let backend worker recovery deliver or quarantine pending done reports before trusting new claims.",
                )
            )
    heartbeat_failure = runtime_reliability.get("worker_heartbeat_failure")
    if isinstance(heartbeat_failure, Mapping) and bool(heartbeat_failure.get("abort_due")):
        blockers.append(
            _issue(
                "autonomy_worker_heartbeat_failure_abort_due",
                "runtime_health",
                "high",
                f"Worker heartbeat POST failures have exceeded the local abort threshold: age_seconds={heartbeat_failure.get('age_seconds')}.",
                next_action="Inspect worker/coordinator connectivity before starting more network work.",
            )
        )
    sqlite_mirror = runtime_reliability.get("sqlite_mirror")
    if isinstance(sqlite_mirror, Mapping):
        db_size = _safe_int(sqlite_mirror.get("db_size_bytes"))
        wal_size = _safe_int(sqlite_mirror.get("wal_size_bytes"))
        if db_size > policy.state_file_block_bytes or wal_size > policy.state_file_block_bytes:
            blockers.append(
                _issue(
                    "autonomy_sqlite_mirror_blocked_size",
                    "runtime_health",
                    "high",
                    f"SQLite mirror DB/WAL exceeds the blocked size budget: db={db_size}; wal={wal_size}.",
                    evidence_path=str(sqlite_mirror.get("path") or ""),
                    next_action="Run backend-owned SQLite mirror maintenance or archive planning before unattended launch.",
                )
            )
        elif db_size > policy.state_file_review_bytes or wal_size > policy.state_file_review_bytes:
            review_items.append(
                _issue(
                    "autonomy_sqlite_mirror_review_size",
                    "runtime_health",
                    "medium",
                    f"SQLite mirror DB/WAL exceeds the review size budget: db={db_size}; wal={wal_size}.",
                    evidence_path=str(sqlite_mirror.get("path") or ""),
                    next_action="Review SQLite mirror maintenance posture before a long unattended run.",
                )
            )
    state_db = runtime_reliability.get("state_db")
    if isinstance(state_db, Mapping):
        wal_size = _safe_int(state_db.get("wal_size_bytes"))
        wal_review = _safe_int(state_db.get("wal_review_bytes"))
        last_maintenance = state_db.get("last_maintenance")
        maintenance_error = ""
        if isinstance(last_maintenance, Mapping):
            maintenance_error = str(last_maintenance.get("error") or "")
        if wal_review > 0 and wal_size >= wal_review:
            review_items.append(
                _issue(
                    "autonomy_state_db_maintenance_overdue",
                    "runtime_health",
                    "medium",
                    f"SQLite mirror WAL is at or above the review threshold: wal={wal_size}; threshold={wal_review}.",
                    evidence_path=str(state_db.get("maintenance_path") or state_db.get("path") or ""),
                    next_action="Confirm backend-owned mirror maintenance is running; JSON files remain authoritative.",
                )
            )
        if maintenance_error:
            review_items.append(
                _issue(
                    "autonomy_state_db_maintenance_overdue",
                    "runtime_health",
                    "medium",
                    f"Last SQLite mirror maintenance failed: {maintenance_error}.",
                    evidence_path=str(state_db.get("maintenance_path") or state_db.get("path") or ""),
                    next_action="Inspect maintenance diagnostics; do not delete authoritative JSON state files.",
                )
            )
    metrics = _runtime_health_metrics(runtime_reliability)
    return _category(
        "runtime_health",
        _issue_status(blockers, review_items),
        metrics=metrics,
        summary_lines=[
            (
                "Runtime counters: "
                f"current_file_age_seconds={metrics['current_file_age_seconds']}; "
                f"round_failures={metrics['round_failure_count']}; "
                f"native_no_progress_aborts={metrics['native_no_progress_abort_count']}."
            ),
            (
                "Backlog counters: "
                f"pending_publish={metrics['pending_publish_backlog_count']}; "
                f"worker_pending_reports={metrics['worker_pending_report_count']}; "
                f"active_jobs_total={metrics['active_jobs_total_count']}; "
                f"active_jobs_blocking={metrics['active_jobs_blocking_count']}."
            ),
            (
                "State counters: "
                f"sqlite_db_bytes={metrics['sqlite_db_size_bytes']}; "
                f"sqlite_wal_bytes={metrics['sqlite_wal_size_bytes']}; "
                f"progress_persistence_healthy={metrics['progress_persistence_healthy']}."
            ),
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _runtime_health_metrics(runtime_reliability: Mapping[str, Any]) -> dict[str, Any]:
    current_file = runtime_reliability.get("current_file") if isinstance(runtime_reliability, Mapping) else {}
    round_failures = runtime_reliability.get("round_failures") if isinstance(runtime_reliability, Mapping) else {}
    native_processes = runtime_reliability.get("native_processes") if isinstance(runtime_reliability, Mapping) else {}
    pending_publish = runtime_reliability.get("pending_publish") if isinstance(runtime_reliability, Mapping) else {}
    worker_reports = runtime_reliability.get("worker_pending_reports") if isinstance(runtime_reliability, Mapping) else {}
    active_jobs = runtime_reliability.get("active_jobs") if isinstance(runtime_reliability, Mapping) else {}
    sqlite_mirror = runtime_reliability.get("sqlite_mirror") if isinstance(runtime_reliability, Mapping) else {}
    progress = runtime_reliability.get("progress_persistence") if isinstance(runtime_reliability, Mapping) else {}
    continuous_round_state = runtime_reliability.get("continuous_round_state") if isinstance(runtime_reliability, Mapping) else {}
    control_flags = runtime_reliability.get("control_flags") if isinstance(runtime_reliability, Mapping) else {}
    pending_backpressure = runtime_reliability.get("pending_publish_backpressure") if isinstance(runtime_reliability, Mapping) else {}
    worker_slots = runtime_reliability.get("worker_slots") if isinstance(runtime_reliability, Mapping) else {}
    state_db = runtime_reliability.get("state_db") if isinstance(runtime_reliability, Mapping) else {}
    heartbeat_failure = runtime_reliability.get("worker_heartbeat_failure") if isinstance(runtime_reliability, Mapping) else {}
    coordinator_state = runtime_reliability.get("coordinator_state") if isinstance(runtime_reliability, Mapping) else {}
    debug_log = runtime_reliability.get("debug_log") if isinstance(runtime_reliability, Mapping) else {}
    return {
        "current_file_age_seconds": None if not isinstance(current_file, Mapping) else current_file.get("age_seconds"),
        "round_failure_count": _safe_int(round_failures.get("round_failure_count")) if isinstance(round_failures, Mapping) else 0,
        "unexpected_queue_entry_failures": _safe_int(round_failures.get("unexpected_queue_entry_failures")) if isinstance(round_failures, Mapping) else 0,
        "unexpected_round_failures": _safe_int(round_failures.get("unexpected_round_failures")) if isinstance(round_failures, Mapping) else 0,
        "consecutive_unexpected_round_failures": _safe_int(continuous_round_state.get("consecutive_unexpected_round_failures")) if isinstance(continuous_round_state, Mapping) else 0,
        "continuous_round_blocked": bool(continuous_round_state.get("blocked")) if isinstance(continuous_round_state, Mapping) else False,
        "pause_flag_present": bool(control_flags.get("pause_flag_present")) if isinstance(control_flags, Mapping) else False,
        "pause_age_seconds": control_flags.get("pause_age_seconds") if isinstance(control_flags, Mapping) else None,
        "native_no_progress_abort_count": _safe_int(native_processes.get("native_no_progress_abort_count")) if isinstance(native_processes, Mapping) else 0,
        "pending_publish_backlog_count": _safe_int(pending_publish.get("backlog_count")) if isinstance(pending_publish, Mapping) else 0,
        "pending_publish_health_count": _safe_int(pending_publish.get("health_count")) if isinstance(pending_publish, Mapping) else 0,
        "pending_publish_oldest_age_seconds": pending_backpressure.get("oldest_age_seconds") if isinstance(pending_backpressure, Mapping) else None,
        "pending_publish_backpressure_blocked": bool(pending_backpressure.get("blocked")) if isinstance(pending_backpressure, Mapping) else False,
        "pending_publish_backpressure_reason": str(pending_backpressure.get("block_reason") or "") if isinstance(pending_backpressure, Mapping) else "",
        "worker_pending_report_count": _safe_int(worker_reports.get("pending_report_count")) if isinstance(worker_reports, Mapping) else 0,
        "worker_pending_report_oldest_age_seconds": worker_reports.get("oldest_pending_report_age_seconds") if isinstance(worker_reports, Mapping) else None,
        "worker_heartbeat_failure_age_seconds": heartbeat_failure.get("age_seconds") if isinstance(heartbeat_failure, Mapping) else None,
        "worker_heartbeat_failure_abort_threshold_seconds": _safe_int(heartbeat_failure.get("abort_threshold_seconds")) if isinstance(heartbeat_failure, Mapping) else 0,
        "worker_heartbeat_failure_abort_due": bool(heartbeat_failure.get("abort_due")) if isinstance(heartbeat_failure, Mapping) else False,
        "worker_slot_active_child_count": _safe_int(worker_slots.get("active_child_count")) if isinstance(worker_slots, Mapping) else 0,
        "worker_slot_stale_heartbeat_count": _safe_int(worker_slots.get("stale_heartbeat_count")) if isinstance(worker_slots, Mapping) else 0,
        "active_jobs_total_count": _safe_int(active_jobs.get("total_count")) if isinstance(active_jobs, Mapping) else 0,
        "active_jobs_blocking_count": _safe_int(active_jobs.get("blocking_count")) if isinstance(active_jobs, Mapping) else 0,
        "active_jobs_ambiguous_count": _safe_int(active_jobs.get("ambiguous_count")) if isinstance(active_jobs, Mapping) else 0,
        "active_jobs_ambiguous_read_first": bool(active_jobs.get("ambiguous_read_first")) if isinstance(active_jobs, Mapping) else False,
        "sqlite_db_size_bytes": _safe_int(sqlite_mirror.get("db_size_bytes")) if isinstance(sqlite_mirror, Mapping) else 0,
        "sqlite_wal_size_bytes": _safe_int(sqlite_mirror.get("wal_size_bytes")) if isinstance(sqlite_mirror, Mapping) else 0,
        "sqlite_completed_jobs_count": sqlite_mirror.get("completed_jobs_count") if isinstance(sqlite_mirror, Mapping) else None,
        "sqlite_completed_jobs_max_rows": _safe_int(sqlite_mirror.get("completed_jobs_max_rows")) if isinstance(sqlite_mirror, Mapping) else 0,
        "sqlite_completed_jobs_count_error": str(sqlite_mirror.get("completed_jobs_count_error") or "") if isinstance(sqlite_mirror, Mapping) else "",
        "state_db_wal_review_bytes": _safe_int(state_db.get("wal_review_bytes")) if isinstance(state_db, Mapping) else 0,
        "sqlite_write_failures": sqlite_mirror.get("write_failures") if isinstance(sqlite_mirror, Mapping) else None,
        "progress_persistence_healthy": bool(progress.get("healthy", True)) if isinstance(progress, Mapping) else True,
        "progress_write_failures": _safe_int(progress.get("write_failures")) if isinstance(progress, Mapping) else 0,
        "coordinator_reclaimed_source_quarantine_count": _safe_int(coordinator_state.get("reclaimed_source_quarantine_count")) if isinstance(coordinator_state, Mapping) else 0,
        "coordinator_reclaimed_source_quarantine_oldest_age_seconds": coordinator_state.get("reclaimed_source_quarantine_oldest_age_seconds") if isinstance(coordinator_state, Mapping) else None,
        "coordinator_pending_done_report_count": _safe_int(coordinator_state.get("late_terminal_report_count")) if isinstance(coordinator_state, Mapping) else 0,
        "coordinator_failure_ledger_count": _safe_int(coordinator_state.get("failure_ledger_count")) if isinstance(coordinator_state, Mapping) else 0,
        "coordinator_failure_ledger_max_entries": _safe_int(coordinator_state.get("failure_ledger_max_entries")) if isinstance(coordinator_state, Mapping) else 0,
        "debug_log_size_bytes": _safe_int(debug_log.get("size_bytes")) if isinstance(debug_log, Mapping) else 0,
        "debug_log_max_bytes": _safe_int(debug_log.get("max_bytes")) if isinstance(debug_log, Mapping) else 0,
        "debug_log_rotation_state": str(debug_log.get("rotation_state") or "") if isinstance(debug_log, Mapping) else "",
    }


def _active_liveness_watchdog(records: list[dict[str, Any]], *, policy: AutonomyPolicy) -> dict[str, Any]:
    retained = records[: policy.watchdog_record_limit]
    return {
        "schema_version": "desktop_active_liveness_watchdog.v1",
        "effect": "none",
        "read_only": True,
        "would_kill_active_processes": False,
        "would_rewrite_active_jobs": False,
        "policy": (
            "Passive ActiveJobs evidence only. ActiveJobs records do not block launch, Shutdown Readiness, "
            "or autonomy health."
        ),
        "native_timeout_grace_seconds": policy.active_job_timeout_grace_seconds,
        "no_native_timeout_block_after_seconds": policy.active_job_no_timeout_block_seconds,
        "record_count": len(retained),
        "record_total_count": len(records),
        "records_truncated": len(records) > len(retained),
        "record_limit": policy.watchdog_record_limit,
        "records": retained,
    }


def _active_liveness_evidence(
    resolved: Any,
    payload: Mapping[str, Any],
    active_job_path: Path,
    now: datetime,
    *,
    policy: AutonomyPolicy,
) -> dict[str, Any]:
    heartbeat_age = _age_seconds(_first_text(payload, "last_update", "launched_at"), active_job_path, now)
    evidence_candidates = [
        {
            "source": "active_job",
            "path": str(active_job_path),
            "age_seconds": heartbeat_age,
        }
    ]
    progress = _progress_liveness_evidence(resolved.progress_file, now)
    if progress is not None:
        evidence_candidates.append(progress)
    for source, path in (("event_file", resolved.event_file), ("log_file", resolved.log_file)):
        file_evidence = _file_mtime_liveness_evidence(source, path, now)
        if file_evidence is not None:
            evidence_candidates.append(file_evidence)
    latest = _latest_liveness_candidate(evidence_candidates)
    native_timeout_source, native_timeout_seconds = _native_timeout_for_active_job(payload, resolved.config_data)
    block_after = (
        native_timeout_seconds + policy.active_job_timeout_grace_seconds
        if native_timeout_seconds is not None
        else policy.active_job_no_timeout_block_seconds
    )
    return {
        "status": "ready",
        "active_job_path": str(active_job_path),
        "pid": payload.get("pid"),
        "job_kind": str(payload.get("job_kind") or ""),
        "mode": str(payload.get("mode") or ""),
        "active_status": str(payload.get("status") or ""),
        "heartbeat_age_seconds": heartbeat_age,
        "latest_evidence_source": str(latest.get("source") or ""),
        "latest_evidence_path": str(latest.get("path") or ""),
        "latest_evidence_age_seconds": latest.get("age_seconds"),
        "native_timeout_source": native_timeout_source,
        "native_timeout_seconds": native_timeout_seconds,
        "native_timeout_grace_seconds": policy.active_job_timeout_grace_seconds,
        "block_after_seconds": block_after,
        "evidence_candidates": evidence_candidates,
    }


def _progress_liveness_evidence(path: Path | None, now: datetime) -> dict[str, Any] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    payload = _read_json_mapping(path)
    if "_read_error" in payload or "_json_root" in payload:
        return None
    status = _first_text(payload, "Status", "status", "CurrentStage", "current_stage").casefold()
    if status in {"completed", "complete", "failed", "idle", "stopped", "not_running", "not running"}:
        return None
    age_seconds = _age_seconds(
        _first_text(payload, "LastUpdate", "last_update", "updated_at", "timestamp", "Timestamp"),
        path,
        now,
    )
    return {
        "source": "progress_file",
        "path": str(path),
        "age_seconds": age_seconds,
    }


def _file_mtime_liveness_evidence(source: str, path: Path | None, now: datetime) -> dict[str, Any] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    return {
        "source": source,
        "path": str(path),
        "age_seconds": _age_seconds("", path, now),
    }


def _latest_liveness_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    with_age = [item for item in candidates if item.get("age_seconds") is not None]
    if not with_age:
        return candidates[0] if candidates else {"source": "", "path": "", "age_seconds": None}
    return min(with_age, key=lambda item: int(item.get("age_seconds") or 0))


def _native_timeout_for_active_job(payload: Mapping[str, Any], config_data: Mapping[str, Any] | None) -> tuple[str, int | None]:
    if not isinstance(config_data, Mapping):
        return "", None
    text = " ".join(
        str(payload.get(key) or "")
        for key in ("job_kind", "mode", "stage", "current_stage", "operation", "label")
    ).casefold()
    candidate_keys: list[str] = []
    if "cpu" in text and "encode" in text:
        candidate_keys.append("FFmpegCpuEncodeTimeoutSeconds")
    if "encode" in text:
        candidate_keys.append("FFmpegEncodeTimeoutSeconds")
    if "remux" in text:
        if "mkvmerge" in text:
            candidate_keys.append("MkvmergeRemuxTimeoutSeconds")
        candidate_keys.extend(["FFmpegRemuxTimeoutSeconds", "MkvmergeRemuxTimeoutSeconds"])
    if "subtitle" in text or "tx3g" in text or "ass" in text or "ssa" in text:
        candidate_keys.append("SubtitleExtractTimeoutSeconds")
    if "bdpgs" in text:
        candidate_keys.append("BdpgsOcrTimeoutSeconds")
    if "vobsub" in text:
        candidate_keys.append("VobSubOcrTimeoutSeconds")
    if "copy" in text or "publish" in text or "robocopy" in text:
        candidate_keys.append("RobocopyTimeoutSeconds")
    if "scan" in text or "audit" in text:
        candidate_keys.extend(["SourceScanTimeoutSeconds", "IndexScanTimeoutSeconds"])
    for key in candidate_keys:
        value = _safe_int(config_data.get(key))
        if value > 0:
            return key, value
    return "", None
