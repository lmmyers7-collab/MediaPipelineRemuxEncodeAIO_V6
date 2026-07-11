from __future__ import annotations

from importlib import import_module
from pathlib import Path

from mediapipeline.core.kernel.config_keys import KEY_LOCAL_BASE, KEY_PRIORITY_MARKERS, KEY_SOURCE_MOVIES, KEY_SOURCE_TV
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.paths.contracts import PathResolutionServiceProtocol
from mediapipeline.core.storage.state_migration import app_state_path_for_state_root


def _config_identity_helpers():
    module = import_module("mediapipeline.core.config.identity")
    return module.build_config_identity, module.write_last_good_config_snapshot


def resolve_paths_for_service(service: PathResolutionServiceProtocol, pipeline_path: str, config_path: str) -> ResolvedPaths:
    build_config_identity, write_last_good_config_snapshot = _config_identity_helpers()
    resolved = ResolvedPaths(
        app_root=service.app_root,
        workspace_root=service.workspace_root,
        pipeline_path=Path(pipeline_path).expanduser(),
        config_path=Path(config_path).expanduser(),
        audit_script_path=service.default_audit_script_path(),
        rerun_script_path=service.default_rerun_script_path(),
        powershell_host=service.resolve_powershell_host(),
    )
    runtime_roots = getattr(service, "product_runtime_roots", None) or {}
    resolved.runtime_state_root = runtime_roots.get("state_root")
    resolved.run_logs_root = getattr(service, "run_logs_root", None)
    if resolved.runtime_state_root is not None:
        # This is a productized fallback only. A configured LocalBase remains
        # authoritative for media state and replaces this value below.
        resolved.state_root = resolved.runtime_state_root
        resolved.app_state_path = app_state_path_for_state_root(resolved.state_root)

    authority_loader = getattr(service, "load_settings_authority", None)
    if callable(authority_loader):
        config_data = authority_loader(resolved.config_path, resolved.powershell_host)
    else:
        config_data = service.load_config_data(resolved.config_path, resolved.powershell_host)
    resolved.config_data = config_data
    metadata_getter = getattr(service, "settings_store_metadata", None)
    if callable(metadata_getter):
        try:
            store_metadata = dict(metadata_getter(resolved.config_path) or {})
            resolved.persistence_authority = str(store_metadata.get("persistence_authority") or "")
            resolved.settings_store_status = dict(store_metadata.get("settings_store_status") or {})
            resolved.projection_status = dict(store_metadata.get("projection_status") or {})
            resolved.migration_journal = [str(item) for item in store_metadata.get("migration_journal") or []]
            resolved.legacy_extras_count = int(store_metadata.get("legacy_extras_count") or 0)
            resolved.psd1_drift_status = str(store_metadata.get("psd1_drift_status") or "")
        except Exception as exc:
            resolved.settings_store_status = {
                "schema_version": "desktop_settings_store_status.v1",
                "status": "metadata_error",
                "status_state": "warning",
                "errors": [],
                "warnings": [str(exc)],
            }
    resolved.config_identity = build_config_identity(
        resolved.config_path,
        config_data,
        app_root=resolved.app_root,
        workspace_root=resolved.workspace_root,
    )

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
        # Audit-only control state. These files are backend-owned and must not
        # be treated as queue priority, file override, or media-policy inputs.
        resolved.audit_score_policy_path = resolved.state_root / "audit_score_policy.json"
        resolved.audit_ignore_manifest_path = resolved.state_root / "audit_ignore_manifest.json"
        try:
            snapshot_path = write_last_good_config_snapshot(
                resolved.config_path,
                resolved.local_base,
                resolved.config_identity,
            )
            if snapshot_path is not None:
                resolved.config_last_good_snapshot_path = snapshot_path
                resolved.config_identity["last_good_snapshot_path"] = str(snapshot_path)
        except Exception as exc:
            resolved.config_identity["snapshot_error"] = str(exc)

    if not resolved.audit_reports_path:
        resolved.audit_reports_path = (resolved.runtime_state_root or service.app_root) / "AuditReports"

    markers = config_data.get(KEY_PRIORITY_MARKERS)
    if isinstance(markers, list) and markers:
        resolved.priority_markers = [str(item) for item in markers if str(item).strip()]

    return resolved
