from __future__ import annotations

from mediapipeline.desktop.models import ResolvedPaths, Snapshot
from mediapipeline.core.status.contracts import StatusSnapshotServiceProtocol


def _pipeline_active_job_messages(service: StatusSnapshotServiceProtocol, resolved: ResolvedPaths) -> list[str]:
    active_jobs = getattr(service, "active_job_close_block_messages", None)
    if not callable(active_jobs):
        return []
    try:
        messages = active_jobs(resolved, job_kinds={"pipeline"})
    except TypeError:
        messages = active_jobs(resolved)
    except Exception as exc:
        service.logger.warning("ActiveJobs freshness check failed: %s", exc)
        return []
    return [str(message).strip() for message in messages or [] if str(message).strip()]


def build_snapshot_for_service(service: StatusSnapshotServiceProtocol, resolved: ResolvedPaths, audit_root: str) -> Snapshot:
    reconcile = getattr(service, "reconcile_active_job_records", None)
    if callable(reconcile):
        try:
            reconcile(resolved)
        except Exception as exc:
            service.logger.warning("ActiveJobs reconciliation failed: %s", exc)

    progress = service.read_progress(resolved)
    audit_progress = service.read_audit_progress(resolved)
    latest_failure_report = service.latest_matching_file(resolved.failed_reports_path, "round_failures_*.txt")
    latest_failure_json = service.latest_failure_json(resolved)
    latest_audit_csv = service.latest_audit_csv(resolved, priority_only=False)
    latest_priority_csv = service.latest_audit_csv(resolved, priority_only=True)
    log_tail = service.read_log_tail(resolved)
    pipeline_events = service.read_pipeline_events_tail(resolved)

    status_summary = service._build_status_summary(
        resolved=resolved,
        progress=progress,
        audit_progress=audit_progress,
        pipeline_events=pipeline_events,
        audit_root=audit_root,
        latest_failure_report=latest_failure_report,
        latest_failure_json=latest_failure_json,
        latest_audit_csv=latest_audit_csv,
        latest_priority_csv=latest_priority_csv,
    )
    progress_is_stale = service.is_progress_stale(progress)
    if progress_is_stale and _pipeline_active_job_messages(service, resolved):
        progress_is_stale = False
    current_activity = service._build_current_activity(
        resolved,
        None if progress_is_stale else progress,
        log_tail,
        pipeline_events,
    )
    if progress_is_stale:
        if current_activity == "No active work reported.":
            current_activity = "Stale progress from previous run; no active pipeline process reported."
        else:
            current_activity = f"Stale progress from previous run; latest event: {current_activity}"

    return Snapshot(
        resolved=resolved,
        current_activity=current_activity,
        status_summary=status_summary,
        log_tail=log_tail,
        pipeline_events=pipeline_events,
        progress=progress,
        audit_progress=audit_progress,
        latest_failure_report=latest_failure_report,
        latest_failure_json=latest_failure_json,
        latest_audit_csv=latest_audit_csv,
        latest_priority_csv=latest_priority_csv,
    )
