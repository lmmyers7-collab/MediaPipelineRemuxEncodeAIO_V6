"""Worker state persistence status and cluster-log reporting."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def save_active_worker_state(
    state_path: Path,
    job: object,
    *,
    save_state: Callable[..., None],
    notify_status: Callable[[str], None],
    safe_log_cluster_event: Callable[..., None],
    log: Any,
) -> None:
    """Write active-job crash-recovery state and report persistence failures."""
    source_path = str(job.record.source_path)
    job_id = job.job_id
    try:
        save_state(
            state_path,
            job_id=job_id,
            source_path=source_path,
        )
    except Exception as exc:
        log.warning("Failed to save worker_state.json for job %s: %s", job_id, exc)
        notify_status("⚠ Worker crash recovery state save failed - check logs.")
        safe_log_cluster_event(
            "worker-state-save-failed",
            level="WARN",
            event="worker_state_save_failed",
            message="Worker could not save crash-recovery state; restart recovery may miss this job.",
            job_id=job_id,
            source_path=source_path,
        )


def save_pending_worker_report(
    state_path: Path,
    job: object,
    payload: dict[str, Any],
    *,
    save_state: Callable[..., None],
    notify_status: Callable[[str], None],
    safe_log_cluster_event: Callable[..., None],
    log: Any,
) -> bool:
    """Persist a pending done/release report and report retry-save failures."""
    record = job.record
    source_path = str(getattr(record, "source_path", "")) if record else ""
    job_id = job.job_id
    try:
        save_state(
            state_path,
            job_id=job_id,
            source_path=source_path,
            pending_done_report=payload,
        )
    except Exception as exc:
        log.warning("Failed to save pending done report for job %s: %s", job_id, exc)
        notify_status("⚠ Pending done-report retry save failed - check logs.")
        safe_log_cluster_event(
            "pending-done-save-failed",
            level="WARN",
            event="pending_done_save_failed",
            message="Worker could not save pending done/release report; restart retry may miss this report.",
            job_id=job_id,
            source_path=source_path,
        )
        return False
    return True
