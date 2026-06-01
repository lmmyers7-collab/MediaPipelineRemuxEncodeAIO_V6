from __future__ import annotations

from pathlib import Path

from mediapipeline_desktop_app.config_keys import KEY_LOCAL_BASE, KEY_PRIORITY_MARKERS, KEY_SOURCE_MOVIES, KEY_SOURCE_TV
from mediapipeline_desktop_app.models import ResolvedPaths
from app.paths.contracts import PathResolutionServiceProtocol
from app.storage.state_migration import app_state_path_for_state_root


def resolve_paths_for_service(service: PathResolutionServiceProtocol, pipeline_path: str, config_path: str) -> ResolvedPaths:
    resolved = ResolvedPaths(
        app_root=service.app_root,
        workspace_root=service.workspace_root,
        pipeline_path=Path(pipeline_path).expanduser(),
        config_path=Path(config_path).expanduser(),
        audit_script_path=service.default_audit_script_path(),
        rerun_script_path=service.default_rerun_script_path(),
        powershell_host=service.resolve_powershell_host(),
    )

    config_data = service.load_config_data(resolved.config_path, resolved.powershell_host)
    resolved.config_data = config_data

    local_base_raw = config_data.get(KEY_LOCAL_BASE)
    if local_base_raw:
        resolved.local_base = Path(str(local_base_raw))
        resolved.state_root = service._state_root_for_local_base(resolved.local_base)
        progress_state = resolved.state_root / "Progress"
        pipeline_state = resolved.state_root / "Pipeline"
        failures_state = resolved.state_root / "Failures"
        completed_state = resolved.state_root / "Completed"
        resolved.active_jobs_path = resolved.state_root / "ActiveJobs"
        resolved.app_state_path = app_state_path_for_state_root(resolved.state_root)
        service._migrate_app_state_path(resolved.app_state_path)
        resolved.source_movies = service._path_or_none(config_data.get(KEY_SOURCE_MOVIES))
        resolved.source_tv = service._path_or_none(config_data.get(KEY_SOURCE_TV))
        resolved.log_file = resolved.local_base / "pipeline_debug.log"
        resolved.progress_file = service._first_existing(
            progress_state / "pipeline_progress.json",
            resolved.local_base / "pipeline_progress.json",
        )
        resolved.event_file = service._first_existing(
            progress_state / "pipeline_events.jsonl",
            resolved.local_base / "pipeline_events.jsonl",
        )
        resolved.pause_flag = pipeline_state / "pipeline_pause.flag"
        resolved.stop_flag = pipeline_state / "pipeline_stop.flag"
        resolved.rescan_flag = pipeline_state / "pipeline_rescan.flag"
        resolved.failed_reports_path = service._first_existing(
            failures_state / "Reports",
            resolved.local_base / "Failed" / "Reports",
        )
        resolved.failed_markers_path = service._first_existing(
            failures_state / "Markers",
            resolved.local_base / "Failed" / "Markers",
        )
        resolved.pending_push_path = service._first_existing(
            resolved.state_root / "PendingServerPush",
            resolved.local_base / "PendingServerPush",
        )
        resolved.audit_reports_path = resolved.local_base / "AuditReports"
        resolved.queue_snapshot_path = service._first_existing(
            progress_state / "queue_snapshot.json",
            resolved.local_base / "Progress" / "queue_snapshot.json",
        )
        # The Completed tab reads this append-only manifest instead of
        # walking the outsource SMB share in the UI path.
        resolved.completed_manifest_path = service._first_existing(
            completed_state / "completed_jobs.jsonl",
            resolved.local_base / "Completed" / "completed_jobs.jsonl",
        )
        # Non-destructive priority manifest — lives at state root so both
        # the DesktopApp API and the PS1 pipeline can access it with a
        # deterministic path derived from LocalBase.
        resolved.priority_manifest_path = resolved.state_root / "priority_manifest.json"
        # Queue ordering strategy state file — read by PS1 at queue-build time.
        resolved.queue_strategy_path = resolved.state_root / "queue_strategy.json"
        # Per-file à-la-carte processing overrides — read by PS1 at per-file
        # processing time.
        resolved.file_overrides_path = resolved.state_root / "file_overrides.json"

    if not resolved.audit_reports_path:
        resolved.audit_reports_path = service.app_root / "AuditReports"

    markers = config_data.get(KEY_PRIORITY_MARKERS)
    if isinstance(markers, list) and markers:
        resolved.priority_markers = [str(item) for item in markers if str(item).strip()]

    return resolved
