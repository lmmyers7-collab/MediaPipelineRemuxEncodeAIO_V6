# Tauri/WebView2 Transition Groundwork

Date: 2026-05-07  
Branch folder: `MediaPipelineRemuxEncodeAIO_V5`  
Backup folder: `MediaPipelineRemuxEncodeAIO_V4`  
Decision: V5 is the active migration/refactor workspace. V4 should remain the known-good fallback unless explicitly updated later.

## Purpose

This document lays the groundwork for moving MediaPipelineRemuxEncodeAIO from the current CustomTkinter desktop shell toward a Tauri/WebView2 style application: a modern web frontend running in a Windows desktop shell, backed by a local Python application service that continues to own the PowerShell pipeline, FFmpeg/ffprobe orchestration, file safety, settings, telemetry, queue state, audit state, rename logic, and pending-publish behavior.

This is not a rewrite order. It is the transition map. The first real implementation steps should be small, reversible, and useful even if the UI shell decision changes later.

## Current Direction

The target direction is:

```text
Tauri/WebView2 desktop shell
  -> bundled local web frontend
    -> localhost or named local Python backend API
      -> Python application facade
        -> existing Python services and contracts
          -> PowerShell pipeline
            -> FFmpeg / ffprobe / MKVToolNix / PgsToSrt
```

The current CustomTkinter app remains the production UI until the new frontend has proven feature parity for daily operation.

## Current V5 Implementation Status

The first backend-boundary chunks are now in place:

- `DesktopApp\mediapipeline_desktop_app\application\`: UI-neutral DTOs and `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_completed.py`: extracted completed-manifest preview adapter used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_completed_policy.py`: extracted completed-preview row-key, row-shaping, count, byte-formatting, warning DTO policy, and read-error result policy behind the completed facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_completed_open.py`: extracted backend-allowlisted completed-row open command policy.
- `DesktopApp\mediapipeline_desktop_app\application\facade_completed_open_policy.py`: extracted completed-row open target allowlisting, row lookup, manifest-owned path selection, and command-result policy behind the completed open command facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_diagnostics.py`: extracted diagnostics DTO shaping and allowlisted diagnostics-location open policy used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_diagnostics_policy.py`: extracted diagnostics read-side active-job, summary-line, launch-log, and warning policy behind the diagnostics facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_diagnostics_open_policy.py`: extracted diagnostics open target allowlisting, labels, path selection, and command-result message/payload shaping behind the diagnostics facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_queue.py`: extracted read-only queue snapshot adapter used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_queue_policy.py`: extracted queue-preview row-shaping, invalid-row shaping, and empty-snapshot warning policy behind the queue facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_failures.py`: extracted read-only failure report and marker adapter used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_failures_policy.py`: extracted failure-preview source-kind, row-shaping, classification-count, warning DTO policy, and read-error result policy behind the failure facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_audit.py`: extracted read-only audit CSV adapter used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_audit_policy.py`: extracted audit-preview row-shaping, bucket/priority count, duplicate-group, warning DTO policy, and read-error result policy behind the audit facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_pending_publish.py`: extracted read-only pending-publish scan adapter used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_pending_publish_policy.py`: extracted pending-publish raw scan-result, row filtering, integer coercion, error-warning policy, invalid-result policy, and scan-exception DTO policy behind the pending-publish facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_inventory.py`: retained as a compatibility marker for inventory-related facade mixins.
- `DesktopApp\mediapipeline_desktop_app\application\facade_maintenance.py`: extracted read-only maintenance workspace adapter used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_policy.py`: extracted maintenance health-row shaping and count policy behind the maintenance facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_commands.py`: retained as the shared helper layer for maintenance command mixins.
- `DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_command_policy.py`: extracted maintenance release/backfill dry-run request shaping, stdout parsing, and command-result policy behind the maintenance command facades.
- `DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_release.py`: extracted release-package dry-run command adapter.
- `DesktopApp\mediapipeline_desktop_app\application\facade_maintenance_backfill.py`: extracted completed-manifest backfill dry-run command adapter.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process.py`: retained as a compatibility marker for process launch facade mixins.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_pipeline.py`: extracted pipeline start command policy used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_pipeline_policy.py`: extracted pipeline-start mode allowlisting, sleep parsing, extra-args gating, and command-result policy behind the pipeline launch facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_audit.py`: extracted audit start command policy used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_audit_policy.py`: extracted audit-start library-root resolution and command-result policy behind the audit launch facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_rerun.py`: extracted CSV rerun start command policy used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_rerun_policy.py`: extracted CSV rerun path normalization, copy/keep/park mode gating, and command-result policy behind the rerun launch facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_control.py`: extracted pause/stop/rescan control-flag command policy used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_control_policy.py`: extracted pause/stop/rescan action allowlisting, command naming, and success-payload policy behind the control command facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_guard.py`: extracted active-work and close-readiness guards shared by process commands and shell close checks.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_guard_policy.py`: extracted close-readiness field calculation plus pipeline/audit progress-active interpretation behind the process guard facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_schedule.py`: extracted local API pipeline-start schedule gate and override policy used by process launch commands.
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_schedule_policy.py`: extracted pure pipeline-start schedule gate calculation, schedule override normalization, and schedule block messages behind the schedule facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_rename.py`: extracted rename preview and guarded selected-apply request adapters used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_rename_policy.py`: extracted rename preview counts, request parsing, selected-row matching, blocked-row message policy, and apply command-result policy behind the rename facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_schedule.py`: extracted read-only schedule workspace and day-summary shaping used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_schedule_policy.py`: extracted schedule workspace grid shaping, contiguous-window grouping, block-label fallback, and day-summary policy behind the schedule facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_settings.py`: extracted settings workspace and validation adapters used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_settings_policy.py`: extracted settings workspace path shaping and validation command-result policy behind the settings facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_settings_helpers.py`: extracted settings schema, redaction, patch-key validation, and redacted diff helpers used by settings commands.
- `DesktopApp\mediapipeline_desktop_app\application\facade_settings_patch.py`: extracted settings patch preview/save command adapters.
- `DesktopApp\mediapipeline_desktop_app\application\facade_settings_patch_policy.py`: extracted settings patch request-shape validation, preview/save command-result, key sorting, and diff truncation policy behind the settings patch facade.
- `DesktopApp\mediapipeline_desktop_app\application\facade_settings_patch_candidate.py`: extracted settings patch candidate merge/validate/diff construction shared by preview/save commands.
- `DesktopApp\mediapipeline_desktop_app\application\facade_settings_risk.py`: extracted settings patch risk classification used by settings preview/save commands.
- `DesktopApp\mediapipeline_desktop_app\application\facade_status_policy.py`: extracted health capabilities, snapshot count/path/event/warning shaping, and telemetry field policy behind the status facade.
- `DesktopApp\mediapipeline_desktop_app\application\settings_risk_policy.py`: retained the UI-neutral settings patch risk-summary entry point used by preview/save adapters.
- `DesktopApp\mediapipeline_desktop_app\application\settings_risk_policy_rules.py`: extracted pure settings patch risk classification, severity aggregation, source-mutation detection, and warning text formatting rules.
- `DesktopApp\mediapipeline_desktop_app\models_media_paths.py`: extracted model-layer media path, lookup-title, relative-path, season-token, and timestamp parsing helpers while preserving `models.py` compatibility exports.
- `DesktopApp\mediapipeline_desktop_app\models_core.py`: extracted core resolved-path, snapshot, config result, and telemetry dataclasses while preserving `models.py` compatibility exports.
- `DesktopApp\mediapipeline_desktop_app\config_schema_support.py`: extracted static schema support descriptions and tree-column tuples while preserving `config_schema.py` compatibility exports.
- `DesktopApp\mediapipeline_desktop_app\config_schema_network.py`: extracted network-mode defaults and role choices while preserving `config_schema.py` compatibility exports.
- `DesktopApp\mediapipeline_desktop_app\config_schema_choices.py`: extracted static list-choice metadata for audio, subtitle, remux-safe-codec, and queue-marker fields while preserving `config_schema.py` compatibility exports.
- `DesktopApp\mediapipeline_desktop_app\config_schema_layout.py`: extracted static settings page and section ordering constants while preserving `config_schema.py` compatibility exports.
- `DesktopApp\mediapipeline_desktop_app\service_config_psd1.py`: extracted pure PSD1 serialization, ordering, key quoting, and value rendering helpers while preserving `service_config.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_config_profiles.py`: extracted config profile name normalization and profile path construction helpers while preserving `service_config.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_config_document_runner.py`: extracted service-bound PSD1 import and config syntax-validation subprocess orchestration, hidden-window kwargs, and run-capture injection while preserving `service_config.py` compatibility methods.
- `DesktopApp\mediapipeline_desktop_app\service_config_save_runner.py`: extracted service-bound config document save, backup selection, profile listing, settings path normalization, and profile save/load file I/O while preserving `service_config.py` compatibility methods.
- `DesktopApp\mediapipeline_desktop_app\service_config_numeric_policy.py`: extracted required-field and numeric/range validation policy for timeouts, thresholds, retry limits, quality, and CPU bounds while preserving `service_config_validation.py` policy orchestration.
- `DesktopApp\mediapipeline_desktop_app\service_config_option_policy.py`: extracted enum/list/log-level plus structured encoder, routing, and audio validation policy while preserving `service_config_validation.py` policy orchestration.
- `DesktopApp\mediapipeline_desktop_app\service_config_path_warnings.py`: extracted Source/Output/Scratch absolute-path and root-overlap warning policy while preserving `service_config_validation.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_config_preview.py`: extracted config preview merge policy, optional blank handling, encoder tuning flag reset, and audio passthrough profile codec expansion while preserving `service_config.py` PowerShell import/save/profile ownership.
- `DesktopApp\mediapipeline_desktop_app\service_config_validation.py`: extracted config list parsing, value validation, enum/range checks, audio/encoding warning policy, and source/output/scratch root-overlap warnings while preserving `service_config.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_config_value_checks.py`: extracted primitive config required-field, numeric bounds, optional numeric, and unique-warning helpers while preserving `service_config_validation.py` policy ownership.
- `DesktopApp\mediapipeline_desktop_app\service_failure_markers.py`: extracted failure-marker snake_case-to-PascalCase payload normalization and marker-to-record shaping while preserving `service_audit_rerun.py` marker-store scanning.
- `DesktopApp\mediapipeline_desktop_app\service_file_open_plan.py`: extracted file-open VLC discovery, long-path decision, VLC launch arguments, creation flags, and Explorer select-argument planning while preserving `service_file_open.py` OS launching and junction ownership.
- `DesktopApp\mediapipeline_desktop_app\service_folder_policy_contracts.py`: extracted default folder-policy payload, ffprobe stream-signature normalization, and topology shaping while preserving `service_folder_policy.py` ffprobe execution and sidecar persistence.
- `DesktopApp\mediapipeline_desktop_app\service_folder_policy_probe.py`: extracted folder-policy ffprobe JSON parsing and audio/subtitle stream grouping while preserving `service_folder_policy.py` subprocess timeout/error ownership.
- `DesktopApp\mediapipeline_desktop_app\service_process_control_flags.py`: extracted pause/stop/rescan control-flag payload, read/write/remove, and age helpers while preserving `service_processes.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_process_control_runner.py`: extracted pause/stop/rescan service orchestration, stale control-flag launch cleanup, and toggle/write command wrappers while preserving `service_processes.py` compatibility methods.
- `DesktopApp\mediapipeline_desktop_app\service_process_kill.py`: extracted app-owned process exit waiting, fallback kill, psutil tree kill, related PowerShell process discovery, and process-tree kill helpers while preserving `service_processes.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_process_launch_env.py`: extracted bundled launch-directory discovery and process-launch environment PATH prefixing while preserving `service_processes.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_process_launch_plans.py`: extracted pipeline, audit, and CSV-rerun subprocess argument/metadata plan builders while preserving `service_processes.py` launch-method compatibility.
- `DesktopApp\mediapipeline_desktop_app\service_process_launch_runner.py`: extracted pipeline, audit, and CSV-rerun start-method orchestration from the process lifecycle mixin while preserving the same service methods and `_spawn` boundary.
- `DesktopApp\mediapipeline_desktop_app\service_process_logs.py`: extracted process launch-log summary and tail formatting helpers while preserving `service_processes.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_process_readiness.py`: extracted immediate process-launch readiness checking, ActiveJobs status transitions, and startup failure log-tail error construction while preserving `service_processes.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_process_active_jobs.py`: extracted ActiveJobs record path, write, update, PID-liveness, and orphan reconciliation helpers while preserving `service_processes.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_process_active_job_runner.py`: extracted service-bound ActiveJobs orchestration, run-log path injection, psutil boundary passing, app-PID injection, and update/reconcile wrapper calls while preserving `service_processes.py` compatibility methods.
- `DesktopApp\mediapipeline_desktop_app\service_process_runtime_artifacts.py`: extracted runtime progress/control/audit artifact path-contract, validation, filtering, and safe-clear helpers while preserving `service_processes.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_process_runtime_runner.py`: extracted pipeline/audit runtime cleanup orchestration, stale-progress launch cleanup routing, and service-bound artifact wrapper calls while preserving `service_processes.py` compatibility methods.
- `DesktopApp\mediapipeline_desktop_app\service_process_launch_cleanup.py`: extracted launch-time stale-progress cleanup and pause/stop/rescan flag cleanup policy while preserving `service_processes.py` process ownership and compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_process_spawn.py`: extracted subprocess command-line formatting, hidden-window flags, run-log path generation, launch cwd selection, and spawn kwargs assembly while preserving the existing `_spawn` process boundary.
- `DesktopApp\mediapipeline_desktop_app\service_process_spawn_runner.py`: extracted process spawn orchestration, run-log handle lifecycle, `subprocess.Popen` boundary, ActiveJobs launch record writes, and launch readiness checks while preserving `service_processes.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_release_plan.py`: extracted release-package destination, PowerShell argument, command-line display, and artifact-path planning while preserving `service_release.py` subprocess execution and manifest reads.
- `DesktopApp\mediapipeline_desktop_app\service_release_result.py`: extracted release-package subprocess-result normalization and operator payload shaping while preserving `service_release.py` manifest file IO.
- `DesktopApp\mediapipeline_desktop_app\service_pending_publish_format.py`: extracted pending-publish bytes, timestamp, datetime, age-text, and integer parsing helpers while preserving `service_pending_publish.py` manifest scanning and row construction.
- `DesktopApp\mediapipeline_desktop_app\service_pending_publish_paths.py`: extracted pending-publish manifest path selection, text-to-path fallback selection, safe mtime reads, and orphan payload row shaping while preserving `service_pending_publish.py` manifest contract scanning.
- `DesktopApp\mediapipeline_desktop_app\service_path_host_runner.py`: extracted PowerShell host discovery and hidden-window subprocess kwargs while preserving `service_paths.py` compatibility methods and `shutil.which` injection.
- `DesktopApp\mediapipeline_desktop_app\service_path_layout.py`: extracted pure path selection, LocalBase state-root derivation, optional path conversion, valid-extension defaults, normalized path keys, and root-containment helpers while preserving `service_paths.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_path_state_migration.py`: extracted legacy desktop app-state migration into `LocalBase\State\App` while preserving the existing fallback-to-legacy behavior if the copy fails.
- `DesktopApp\mediapipeline_desktop_app\service_path_defaults.py`: extracted default Pipeline/config/audit/rerun script path candidate selection while preserving `service_paths.py` compatibility methods.
- `DesktopApp\mediapipeline_desktop_app\service_path_resolution_runner.py`: extracted config-driven `ResolvedPaths` assembly, versioned LocalBase state paths, PriorityMarkers, and app-state migration orchestration behind the existing `service_paths.py` compatibility method.
- `DesktopApp\mediapipeline_desktop_app\service_folder_policy_io.py`: extracted folder-policy sidecar path selection, JSON shape validation, schema/folder defaults, and atomic writes while preserving `service_folder_policy.py` compatibility methods.
- `DesktopApp\mediapipeline_desktop_app\service_pending_publish_manifest.py`: retained pending-publish manifest JSON/contract parsing while preserving `service_pending_publish.py` folder scanning and aggregate counts.
- `DesktopApp\mediapipeline_desktop_app\service_pending_publish_manifest_rows.py`: extracted pending-publish unreadable/invalid/readable row shaping, sidecar health, output-size fallback, and missing-payload health text.
- `DesktopApp\mediapipeline_desktop_app\service_queue_priority.py`: extracted queue priority marker detection, priority ranking, file/folder rename target construction, collision checks, and priority timestamp touching while preserving `service_queue.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_queue_snapshot.py`: extracted queue snapshot path derivation, contract-checked JSON reads, stale dry-run snapshot checks, dry-run tail formatting, and queue snapshot-row mapping while preserving `service_queue.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_audit_rerun_csv.py`: extracted rerun CSV row construction, source-metadata row overlay, and source-stat timestamp formatting while preserving `service_audit_rerun.py` file IO and metadata subprocess orchestration.
- `DesktopApp\mediapipeline_desktop_app\service_audit_rerun_export.py`: extracted rerun CSV export orchestration, safe rerun mode defaults, source metadata enrichment, source-stat fallback, and atomic CSV writes while preserving `service_audit_rerun.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_audit_rerun_io.py`: extracted audit CSV load/export, failure JSON load, and failure-marker JSON scan/load helpers while preserving `service_audit_rerun.py` source-metadata subprocess orchestration and rerun CSV generation.
- `DesktopApp\mediapipeline_desktop_app\service_audit_rerun_metadata.py`: extracted rerun source-metadata helper script discovery, temp JSON request/response handling, subprocess timeout/failure handling, and source-path result indexing while preserving `service_audit_rerun.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_audit_rerun_records.py`: extracted audit/rerun correlation lookup, completed/failure matching, correlation display rows, audit row fallback, and media-kind inference while preserving `service_audit_rerun.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_rename_movie.py`: extracted movie rename scrub/filter helpers, release-group removal, movie title casing, and filter-option normalization while preserving `service_rename.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_rename_tv.py`: extracted TV rename helpers for explicit season/episode parsing, folder-season inference, specials/OVA `S00` handling, confident episode-title extraction, and auto TV output naming while preserving `service_rename.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_rename_tv_folder.py`: extracted TV folder season/specials/OVA/ordinal-season inference while preserving `service_rename_tv.py` public helper and constant exports.
- `DesktopApp\mediapipeline_desktop_app\service_rename_utils.py`: extracted pure rename utility helpers for natural sorting, Plex component cleanup, rename number/remove-term parsing, sidecar candidate paths, same-file comparison, media suffix stripping, and priority marker removal while preserving `service_rename.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_rename_apply.py`: extracted standalone rename apply helpers for case-safe media renames, sidecar metadata rewrites, undo manifests, duplicate-target operation planning, and rollback while preserving `service_rename.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_rename_apply_runner.py`: extracted standalone rename transaction orchestration, undo-manifest status updates, metadata backup/restore, sidecar metadata update sequencing, and rollback coordination while preserving `service_rename.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_rename_discovery.py`: extracted standalone rename folder discovery, recursive media filtering, and natural sorting while preserving `service_rename.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_rename_preview.py`: extracted pipeline naming-preview script discovery, request JSON shaping, bounded PowerShell preview subprocess handling, output JSON parsing, and preview-row normalization while preserving `service_rename.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_rename_preview_runner.py`: extracted service-bound rename naming-preview orchestration, hidden subprocess kwargs, movie/TV wrapper routing, and run-capture injection while preserving `service_rename.py` compatibility methods.
- `DesktopApp\mediapipeline_desktop_app\service_rename_plan_policy.py`: extracted standalone rename planning policy for manual final-name normalization, movie title/year target construction, casefolded override maps, and preview-row status precedence while preserving `service_rename.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_rename_planner.py`: extracted standalone TV/movie rename preview planning, destination collision checks, long-path warnings, sidecar move preview, and status assembly while preserving `service_rename.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_queue_dry_run.py`: extracted queue dry-run temp snapshot naming, `-EmitQueuePlan` command construction, snapshot freshness checks, and queue-preview status text while preserving `service_queue.py` subprocess execution and snapshot promotion.
- `DesktopApp\mediapipeline_desktop_app\service_queue_dry_run_runner.py`: extracted queue dry-run subprocess execution, timeout/cached-fallback handling, temp snapshot cleanup, request-id tagging, and atomic snapshot promotion while preserving `service_queue.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_queue_preview_builder.py`: extracted queue preview assembly, snapshot-vs-dry-run selection, record mapping, source-candidate counts, and source-status text construction while preserving `service_queue.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_status_errors.py`: extracted recent error summary assembly from pipeline events, failure JSON, and log tail while preserving `service_status.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_status_active_jobs.py`: extracted ActiveJobs diagnostics summary formatting and legacy/current contract fallback handling while preserving `service_status.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_status_files.py`: extracted latest status report, audit CSV, priority audit CSV, and failure JSON file-selection helpers while preserving `service_status.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_status_events.py`: extracted pipeline-event diagnostic summary rows, stage labels, and structured event status interpretation while preserving `service_status_presentation.py` compatibility exports.
- `DesktopApp\mediapipeline_desktop_app\service_status_presentation.py`: extracted pure current-activity composition, pipeline-event, and status-display helpers while preserving `service_status.py` compatibility method wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_status_progress.py`: extracted progress timestamp parsing, pipeline/audit stale detection, and audit-progress status-line formatting while preserving `service_status.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_status_readers.py`: extracted tolerant progress JSON, audit-progress JSON, log-tail, and pipeline-events JSONL readers while preserving `service_status.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_status_snapshot_runner.py`: extracted status snapshot reconciliation, reader orchestration, stale-progress current-activity handling, and `Snapshot` construction while preserving `service_status.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_status_summary.py`: retained diagnostics status-summary ordering and entry-point assembly while preserving `service_status.py` compatibility wrappers.
- `DesktopApp\mediapipeline_desktop_app\service_status_summary_sections.py`: extracted diagnostics status-summary section formatting for paths, flags, active jobs, progress, audit progress, recent errors, event summaries, and latest report links.
- `DesktopApp\mediapipeline_desktop_app\service_completed_backfill.py`: extracted completed-manifest backfill validation, script path resolution, argument construction, launch-exception text, and subprocess result-message policy while preserving `service_completed.py` subprocess execution and cache invalidation.
- `DesktopApp\mediapipeline_desktop_app\service_completed_manifest.py`: extracted completed-jobs JSONL parsing, BOM-tolerant row handling, completed sidecar fallback selection, and output-health annotation while preserving `service_completed.py` cache and backfill subprocess ownership.
- `DesktopApp\mediapipeline_desktop_app\service_app_schedule.py`: extracted schedule grid defaults/normalization, block labels, schedule datetime formatting, current/next window evaluation, and next-stop calculation while preserving `service_app_state.py` JSON load/save ownership.
- `DesktopApp\mediapipeline_desktop_app\service_telemetry_health.py`: extracted environment-health tool discovery, PowerShell/NVIDIA/subtitle helper health-row shaping, and ASS helper result interpretation while preserving `service_telemetry.py` subprocess checks.
- `DesktopApp\mediapipeline_desktop_app\service_telemetry_nvidia.py`: extracted `nvidia-smi` encoder telemetry parsing, idle/unsupported `N/A` handling as visible 0% rows, active-GPU selection, and snapshot application while preserving `service_telemetry.py` sampling behavior.
- `DesktopApp\mediapipeline_desktop_app\service_telemetry_system.py`: extracted `psutil` CPU sampler priming and CPU/memory snapshot mutation while preserving `service_telemetry.py` sampler-loop and subprocess ownership.
- `DesktopApp\mediapipeline_desktop_app\application\facade_status.py`: extracted health, snapshot, and telemetry DTO shaping used by `MediaPipelineApplicationFacade`.
- `DesktopApp\mediapipeline_desktop_app\application\facade_utils.py`: extracted shared path, numeric, snapshot-state, and timeout helpers used across facade mixins.
- `DesktopApp\mediapipeline_desktop_app\api\`: localhost-only `LocalApiServer`, domain-split read/command route contract metadata, route contract payload helper, split read/command handler maps, split read/command payload adapters, shared HTTP handler/CORS/error policy, static asset/bootstrap response policy, shared read/command unavailable payload policy, command lifecycle result helpers, command journal summary policy, and a bounded command-result journal for the future Tauri/WebView2 shell.
- `DesktopApp\mediapipeline_desktop_app\backend_bootstrap.py`: headless local API bootstrap payload helper used by launcher-facing backend startup.
- `DesktopApp\mediapipeline_desktop_app\local_api_main.py`: headless backend entry point a future shell can launch.
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\`: bundled static browser prototype.
- `Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat` and `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat`: operator/developer launchers for the headless local API.
- `DesktopApp\tauri_shell\`: scaffold-only Tauri/WebView2 shell. It is not production yet. The Rust shell is designed to start the Python local API, read the bootstrap JSON, then open the backend-served UI.
- `DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1`: non-destructive scaffold/toolchain checker. By default it warns for missing Node/Rust and only fails for missing scaffold/backend basics; use `-RequireToolchain` when the machine is expected to build the shell.
- `DesktopApp\tauri_shell\Test-TauriShell-Build.ps1`: developer build checker. It resolves user-scope Node/Rust installs, enters the Visual Studio C++ developer environment, and runs `npm run check`.
- `DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1`: real dev-shell smoke checker. It launches `npm run dev`, detects the Tauri shell process, visible WebView window, and Python backend, closes the actual Tauri shell process normally, waits for backend cleanup for the configured close timeout, and verifies the backend is not orphaned.
- `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat` and `DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1`: explicit opt-in preview launcher for trying the Tauri/WebView2 shell without replacing the current CustomTkinter launcher.
- `DesktopApp\tauri_shell\package-lock.json` and `DesktopApp\tauri_shell\src-tauri\Cargo.lock`: resolved dependency lockfiles for reproducible shell checks.
- `DesktopApp\tauri_shell\src-tauri\icons\icon.ico`: temporary Windows icon required by Tauri's Windows resource generation. Replace this with a MediaPipeline-specific icon before installer branding work.
- The Tauri scaffold drains backend stdout/stderr pipes after startup and terminates the backend child if bootstrap read, timeout, JSON parse, or schema validation fails.
- The Tauri scaffold tolerates non-JSON stdout before backend bootstrap, logs those pre-bootstrap lines, and continues waiting for the required `desktop_local_api_bootstrap.v1` payload until the startup timeout expires.
- After backend bootstrap, the Tauri scaffold now calls `/api/health` and verifies `desktop_backend_health.v1`, `status == ok`, and required shell capabilities before opening the WebView. Failed health validation terminates the Python backend child and surfaces startup failure instead of opening a partially functional shell.
- The Tauri scaffold now handles `WindowEvent::CloseRequested`, `WindowEvent::Destroyed`, and app-level `RunEvent::ExitRequested` / `RunEvent::Exit`, requests graceful Python backend shutdown before the shell exits, and keeps `Drop` as a fallback.
- The Tauri close path now calls the backend close-readiness API before shutdown. If active work is reported, or readiness cannot be verified, the shell asks for Windows-native confirmation before closing.
- Tauri shell backend HTTP requests for close readiness and graceful shutdown now share one bounded request helper, keeping token handling and timeout behavior consistent.
- The Tauri launch/close smoke harness waits for backend cleanup for the configured close timeout, matching the asynchronous graceful shutdown path instead of relying on a one-shot process check.
- The local API exposes token-protected `POST /api/backend/shutdown`; `local_api_main` uses it to stop through the normal backend cleanup path, and the Tauri scaffold calls it before falling back to child termination.
- Read APIs currently exposed: health, snapshot, close readiness, command history, telemetry, diagnostics, queue preview, completed preview, failure preview, audit preview, pending-publish preview, maintenance workspace, settings workspace.
- Maintenance API currently exposed: token-protected `GET /api/maintenance`, which adapts the existing environment/tool health check into structured OK/missing/warning rows without repairing or changing anything; token-protected `POST /api/maintenance/release-dry-run`, which runs the existing release builder with `-DryRun` only; and token-protected `POST /api/maintenance/completed-backfill-dry-run`, which runs the existing completed-manifest backfill with `-DryRun` only. The health-check contract effect is `bounded-health-check`; both dry-run command effects are `process-dry-run`.
- Schedule API currently exposed: token-protected `GET /api/schedule`, which reads the existing desktop app state schedule grid, evaluates the current run window, and returns day summaries; token-protected `POST /api/schedule/preview`, which validates proposed day windows without writing; and token-protected `POST /api/schedule/save`, which requires confirmation and writes only `schedule_enabled`/`schedule_grid` through the backend app-state service.
- Contract API currently exposed: token-protected `GET /api/contract`, which lists route paths, auth requirements, side-effect class, response schemas, and coarse request keys for the future frontend.
- Rename commands currently exposed: rename preview and guarded selected-row rename apply. Preview returns structured predictions only. Apply rebuilds the plan in the backend from the current request, requires explicit confirmation, and applies only selected source rows through the existing transactional rename service.
- Safe commands currently exposed: settings validation, settings patch preview, settings patch save, settings reload, diagnostics-location open, completed-row location open, maintenance release dry-run, and completed-manifest backfill dry-run. Settings validation returns a command-result envelope and does not persist PSD1 changes. Settings patch preview merges explicit key changes with the backend's unredacted config and returns a redacted diff without saving. Settings patch preview/save results now include a versioned backend risk summary for unknown keys, source/original mutation toggles, source/output/scratch path root changes, size-guard policy changes, no-audio/system-tool fallbacks, subtitle drop toggles, MP4 container limits, and full reprocess mode. Settings patch save requires explicit confirmation, rejects redacted sensitive placeholders, creates a backup, writes through the existing config save service, and reloads backend resolved state. Settings reload refreshes backend resolved paths/config from disk without writing. The settings workspace DTO includes backend schema metadata for labels, choices, defaults, and help text. The web Settings page now includes a read-only grouped operational overview over the same backend config data for routing/size, paths/safety, encoder, subtitles, audio, publish/network, and diagnostics/runtime settings, plus structured patch builders for common routing/size/encoder keys, subtitle policy keys, and audio policy keys. The routing and audio builders refresh choices from backend schema metadata when available, display choice guidance, preserve in-progress edits across polling refreshes, and only update the patch JSON field. The subtitle builder exposes shared subtitle language/style policy plus TX3G, BDPGS, and ASS/SSA toggle groups and also only stages patch JSON. The local patch summary table parses staged JSON, compares it with the loaded settings snapshot, styles changed/new/unknown/unchanged rows, and can filter to changed/unknown rows before backend preview/save. Preview and save still go through backend validation. Diagnostics open is backend-allowlisted to known log/config/state/report locations. Completed-row open uses a backend-generated completed manifest row key and target enum. Release dry-run is forced to `-DryRun` by the backend and does not expose a build-package route. Completed-manifest backfill dry-run is forced to `-DryRun` and writes its progress checkpoint to the RunLogs area instead of the normal completed-state checkpoint path. Neither path-opening command accepts arbitrary frontend paths.
- Process commands currently exposed through the backend contract: pause/resume flag, stop flag, rescan flag, pipeline start, pending-publish drain via pipeline start mode, audit start, and CSV rerun start. The static prototype renders pause/resume, Stop After Current, rescan, guarded pipeline start, Publish Parked Outputs, guarded audit start, guarded CSV rerun start, and backend-mediated diagnostics location open.
- Pipeline start from the local API now includes a backend schedule gate. Validate and drain-pending modes are unscheduled; normal starts are allowed when schedule enforcement is off; outside-window starts require an explicit schedule override; scheduled continuous starts are blocked unless the user explicitly ignores schedule because the local API does not yet own the Tk stop-at-window-end watcher.
- The static prototype now keeps a command-result history table backed by `GET /api/commands` and also mirrors that history in Diagnostics. Browser-local command feedback is replaced from the backend journal on refresh so recent operator actions survive page reloads. Stop After Current and rescan require a browser confirmation before the backend control-flag write is sent.
- The static prototype now includes a read-only Queue page backed by the existing queue snapshot DTO. It shows queue rows, client-side filtering, selected queue-row details, route reason, source path, priority state, and TV season/episode context without queue dry-runs, priority writes, or process launches.
- The static prototype now includes a Pending Publish page backed by the existing pending-publish scanner. It shows parked manifest count, payload count, total size, health count, rows for parked/orphan/problem payloads, and selected pending-row details without mutating anything; the drain action remains a separate guarded process command.
- The static prototype now includes a read-only Audit / Reports page backed by existing snapshot, failure preview, audit preview, and settings workspace DTOs. It shows latest failure/audit/priority report paths, recent failure rows, failure-marker mode, selected failure-row details, latest audit rows, selected audit-row details, a latest-priority-CSV toggle, report roots, completed manifest location, and snapshot warnings without opening, clearing, prioritizing, rerunning, exporting, or mutating files.
- The static prototype now includes a Schedule page backed by existing app-state schedule services and backend command routes. It shows enforcement, allowed-now state, next allowed window, app-state path, warnings, weekly window summaries, coverage/day detail, and a backend-owned Schedule Editor for previewing/saving `schedule_enabled`/`schedule_grid`; it cannot launch work, override schedule gates, mutate queue/media state, or own the continuous-run schedule-stop watcher.
- The static prototype now includes a Maintenance page backed by the existing environment health checker, release builder dry-run, and completed-manifest backfill dry-run. It shows bundled/native tool status and optional telemetry warnings without running reset, repair, real release build actions, or manifest rewrites. Health checks are explicit/lazy through the Maintenance tab and `Run Health Check` button, not part of the global 4-second refresh loop. Release and backfill dry-runs run only when the operator presses their buttons.
- The static prototype now refreshes read endpoints independently with partial-failure tolerance. Snapshot remains the required top-level read, while optional panels update when their endpoint succeeds and a top-bar refresh-health pill reports any endpoint issues.
- Backend lifecycle command currently exposed: graceful local API shutdown for a shell-owned backend process. It is token-protected and not rendered as an operator button in the static prototype.
- Backend close-readiness API currently exposed: token-protected `GET /api/backend/close-readiness`, which reports whether closing the local shell is safe based on active process/progress/audit evidence and snapshot state. The static prototype renders this as a top-bar close pill, shows the same structured state/reason/warnings in Diagnostics, and uses it for a `beforeunload` warning when active work is detected.
- The current CustomTkinter app still launches through the existing path; this work does not replace it.
- The V5 release builder now defaults to a `MediaPipelineRemuxEncodeAIO_V5_Deployable_*` output name, and the release verifier checks that the backend facade/API/static prototype and Tauri scaffold files are present.
- The V5 release self-test now runs the non-destructive Tauri prereq checker as a preview gate. It fails for missing scaffold/backend basics, surfaces toolchain warnings, and does not require Node/Rust/MSVC unless the dedicated Tauri build checker is run.
- Clean V5 release packages omit local Tauri/WebView2 build artifacts, including `DesktopApp\tauri_shell\node_modules`, `DesktopApp\tauri_shell\src-tauri\gen`, and `DesktopApp\tauri_shell\src-tauri\target`.

The local API remains intentionally conservative. Queue preview reads the latest backend-owned snapshot instead of spawning a queue dry-run. Rename preview defaults to the Python scrub planner and only runs pipeline naming preview if an explicit request opts in. Settings workspace is read-only and redacts auth/token-like values before returning config data.

The Tauri shell scaffold is intentionally not wired as the default app launcher yet. It should remain behind explicit developer/operator launch commands until bundle resources, backend shutdown, installer behavior, and operator close behavior are validated on the target workstation.

Current scaffold validation on this workstation:

- Python desktop/API test suite: 387 tests passed.
- PowerShell reliability regression checks: passed.
- Release dry-run: passed, 4,286-file V5 deployable plan.
- Release self-test now includes PowerShell parser checks, explicitly named API/facade syntax checks, and recursive syntax checks for all project-owned `mediapipeline_desktop_app` Python files: passed.
- Node.js LTS, Rustup, and Visual Studio 2022 C++ Build Tools are installed on this workstation.
- Tauri prerequisite checker with `-RequireToolchain -RequireBuildTools`: passed.
- Tauri build checker: passed; `cargo check --manifest-path src-tauri\Cargo.toml` completed successfully.
- Tauri launch checker: passed; dev shell opened, backend started, window close completed, and backend cleanup was verified.
- Tauri launch checker was rerun after the web prototype pending-publish update: passed.
- Tauri launch checker was rerun after the Schedule page update and smoke-harness cleanup wait fix: passed.
- Tauri launch checker was rerun after the Maintenance page update and Rust close-lifecycle reinforcement: passed.
- Tauri launch checker was rerun after the guarded Launch page updates and smoke-harness shell-process selection fix: passed.
- Tauri launch checker was rerun after adding app-level run-event backend cleanup: passed.
- Tauri launch checker was rerun after adding backend-mediated diagnostics location open: passed.
- Tauri launch checker was rerun after adding the Pending Publish page drain action: passed.
- Tauri launch checker was rerun after adding non-mutating settings patch preview: passed.
- Tauri launch checker was rerun after adding settings reload from disk: passed.
- Tauri launch checker was rerun after adding the Completed Jobs page: passed.
- Tauri launch checker was rerun after adding backend-mediated completed row open locations: passed.
- Tauri launch checker was rerun after adding preview-only selected-row rename overrides: passed.
- Tauri launch checker was rerun after fixing completed-manifest backfill success handling: passed.
- Tauri launch checker was rerun after adding guarded selected-row rename apply: passed.
- Tauri launch checker was rerun after adding guarded settings patch save: passed.
- Tauri launch checker was rerun after adding Maintenance release dry-run: passed.
- Tauri launch checker was rerun after adding Maintenance completed-manifest backfill dry-run: passed.
- Tauri launch checker was rerun after adding read-only failure preview: passed.
- Tauri launch checker was rerun after adding read-only audit preview: passed.
- Tauri launch checker was rerun after adding audit preview detail/priority mode: passed.
- Tauri launch checker was rerun after adding failure detail/marker mode: passed.
- Tauri launch checker was rerun after adding queue row detail: passed.
- Tauri launch checker was rerun after adding pending-publish row detail: passed.
- Tauri launch checker was rerun after adding structured settings overview: passed.
- Tauri launch checker was rerun after adding structured settings patch builder: passed.
- Tauri launch checker was rerun after adding settings schema guidance: passed.
- Tauri launch checker was rerun after adding structured subtitle patch builder: passed.
- Tauri launch checker was rerun after adding structured audio patch builder: passed.
- Tauri launch checker was rerun after adding local settings patch summary: passed.
- Tauri launch checker was rerun after adding patch summary filtering/status styling: passed.
- Tauri launch checker was rerun after adding backend settings patch risk summary: passed.
- Tauri launch checker was rerun after adding backend close-readiness and the web close warning: passed.
- Tauri launch checker was rerun after adding partial web refresh resilience: passed.
- Tauri launch checker was rerun after adding the native Tauri close guard: passed.
- Tauri launch checker was rerun after hardening backend stdout bootstrap tolerance: passed.
- Tauri preview launcher `-CheckOnly` was run after adding the explicit preview launcher: passed.
- Tauri launch checker was rerun after adding the backend command journal and Diagnostics command-history view: passed.
- Release self-test now runs the desktop Python unit suite through the bundled runtime: passed.
- Tauri Rust build checker was rerun after adding the backend health capability gate: passed.
- Tauri launch/close smoke was rerun after the local API helper/static/route-map/read-payload/command-payload/handler refactors: passed.
- Tauri launch/close smoke was rerun after adding the backend health capability gate: passed.
- Release self-test now layout/syntax-checks the local API route map, local API read-payload mixin, local API command-payload mixin, local API HTTP handler factory, and ASS subtitle helper: passed.
- Release self-test streams recursive Python syntax-check file paths through stdin to avoid Windows native command-line length limits as module splits grow: passed.
- Release self-test now invokes the Tauri preview prereq checker without `-RequireToolchain` / `-RequireBuildTools`: passed.
- Web prototype command surface: backend-hydrated command-result history, backend close-readiness, active-work close warning, Stop After Current/rescan confirmation, read-only settings validation, and backend-allowlisted diagnostics location open are covered by static/API tests.
- Local API request/static plumbing: token auth sources, query value/int/bool parsing, JSON-body parsing path, response writer extraction, index bootstrap rendering, guarded static asset reads, static asset traversal rejection, and content-type mapping are covered by focused API/helper tests.
- Web prototype close-readiness diagnostics and command-journal update: JavaScript parse check passed, focused application facade/local API unittest suite passed, and release self-test passed.
- Web prototype pending-publish surface: pending-publish DTO/API/static rendering, selected row details, and guarded Publish Parked Outputs command wiring are covered by static/API tests.
- Web prototype completed surface: read-only completed-jobs manifest DTO/API/static rendering, filtering, row detail selection, and backend-mediated location opening are covered by static/API tests.
- Web prototype rename and diagnostics detail surface: custom negative terms, built-in movie scrub filter toggles, sidecar/force/pipeline-preview toggles, selected-row final-name/force overrides, guarded selected-row apply, log tail, and launch log rendering are covered by static/API tests.
- Web prototype queue and pending-publish filters: client-side filtering over backend DTO rows, plus selected queue-row and pending-row detail rendering, are covered by static/API tests.
- Web prototype settings and GPU detail surface: settings search/profile/validation panels, grouped operational settings overview, structured settings patch builder, schema-driven settings guidance, structured subtitle patch builder, structured audio patch builder, local settings patch summary with changed-only filtering and status styling, backend settings patch risk summary rendering, settings reload, non-mutating settings patch preview, guarded settings patch save, and per-GPU telemetry rows are covered by static/API tests.
- Web prototype Home dashboard details: read-only progress detail, recent pipeline event tables, and partial refresh-health rendering are covered by static/API tests.
- Web prototype Audit / Reports surface: read-only latest report paths, recent failure rows/filtering, failure-marker mode, selected failure-row details, latest audit rows/filtering, selected audit-row details, latest priority CSV mode, report roots, completed manifest location, and snapshot warnings are covered by static/API tests.
- Web prototype Schedule surface: read-only persisted schedule grid, current schedule evaluation, app-state path, and weekly window summaries are covered by static/API tests.
- Web prototype Maintenance surface: environment health rows, OK/missing/warning counts, forced release dry-run, and forced completed-manifest backfill dry-run are covered by static/API tests.
- Web prototype Launch surface: guarded pipeline start form, schedule override payload, command-result logging, and backend schedule-gate behavior are covered by static/API tests.
- Web prototype Audit Launch surface: library-root/include-sidecars/show-console payload, confirmation flow, command-result logging, and settings-derived default library root are covered by static/API tests.
- Web prototype CSV Rerun surface: CSV path validation, copy/keep/park fixed policy payload, confirmation flow, and command-result logging are covered by static/API tests.

## Core Rule

The Tauri/WebView2 frontend must not directly mutate files, write config, spawn FFmpeg, spawn PowerShell, touch queue manifests, rename files, delete files, or inspect raw pipeline state paths.

The backend owns all state-changing operations. The frontend sends commands and renders backend-owned snapshots/results.

## Why V5 Exists

V4 is working well enough to preserve as a stable backup. V5 should become the migration branch where larger architectural changes can be staged without risking the known-good V4 workflow.

V5 should start by improving internal architecture before adding a new shell:

1. Extract a UI-neutral Python application facade.
2. Move current Tk controllers toward the facade.
3. Add a local API server around the facade.
4. Build a read-only browser prototype.
5. Add write commands only after command contracts and tests are solid.
6. Package the frontend in Tauri/WebView2 after the browser prototype proves stable.

## Existing V5 Baseline

V5 was copied from the current V4 state. The important inherited pieces are:

| Area | Current V5 Files | Keep / Replace |
|---|---|---|
| Current UI shell | `DesktopApp\mediapipeline_desktop_app\app.py`, `views\*.py`, `controllers\*.py` | Keep temporarily. Replace only after backend boundary is stable. |
| State bootstrap | `DesktopApp\mediapipeline_desktop_app\app_bootstrap.py` | Gradually split into typed state containers and UI adapters. |
| Service facade | `DesktopApp\mediapipeline_desktop_app\services.py` plus `service_*.py` | Keep as compatibility facade. Extract true application/backend services behind it. |
| Contracts | `DesktopApp\mediapipeline_desktop_app\contracts\*.py` | Keep and expand. These are the foundation of the local API. |
| Process lifecycle | `DesktopApp\mediapipeline_desktop_app\service_processes.py` | Keep behavior. Wrap behind command APIs. |
| Telemetry | `service_telemetry.py`, `controllers\telemetry_controller.py` | Backend should own sampling; frontend should only render samples. |
| Rename | `service_rename.py`, `controllers\rename_*.py`, `views\rename.py` | Keep logic; expose preview/apply through backend commands. |
| Queue/audit/pending | `service_queue.py`, `service_status.py`, `service_pending_publish.py`, controllers/views | Keep behavior; expose as snapshot/query DTOs. |
| PowerShell backend | `Pipeline\*.ps1`, `Pipeline\Modules\*.ps1` | Keep operational model. Do not port to frontend. |
| Packaging | `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`, release verifier | Extend later to include frontend build and shell assets. |

## Non-Goals For Early V5

- Do not remove CustomTkinter.
- Do not immediately create a Tauri executable.
- Do not port PowerShell pipeline logic to TypeScript, Rust, C#, or frontend code.
- Do not reimplement FFmpeg command generation in the frontend.
- Do not expose raw filesystem mutation endpoints.
- Do not add remote LAN control until localhost-only behavior is proven.
- Do not combine network worker/coordinator API with the local UI API without an explicit boundary.
- Do not change remux/encode/subtitle/audio behavior just because the UI architecture changes.

## Endgame

The desired endgame is a desktop app that feels like a modern operations console:

- Left navigation and workflow structure similar to the current app.
- Rich queue/audit/completed/pending/rename tables with fast filtering, sorting, virtual scrolling, stable selection, column persistence, and detail panes.
- Clear pipeline state, route decisions, remux-vs-encode reasons, size policy results, subtitle conversion actions, audio policy actions, and publish status.
- Diagnostics panel with recent errors, current process tree, ActiveJobs, progress state, control flags, event stream, log tails, tool versions, and suggested recovery actions.
- Settings UX with structured controls, presets, validation, dirty-state safety, profile support, searchable fields, and explanations that do not require raw flag editing.
- Rename UX closer to PowerRename but pipeline-aware: movie scrub preview, TV season/episode prediction, selected-row batch operations, sidecar tagging, force pipeline name policy, conflict detection, and transactional apply.
- Telemetry with persistent graph lines, 0 percent NVENC shown as real data, CPU/RAM/GPU/VRAM/encoder history, and encode throughput trends.
- A backend that remains testable without UI and safe to use from either the current Tk shell or the future web shell.

## Architecture Principles

### 1. Backend Owns Media Safety

Every operation that can affect media files, config, state files, sidecars, manifests, scratch folders, pending-publish payloads, or processes must go through backend command handlers.

### 2. UI Renders Snapshots

The frontend should render versioned snapshots and command results. It should not infer pipeline state from raw files.

### 3. Commands Are Explicit

Every state-changing action should have:

- a command name
- a request schema
- validation
- a structured result
- log/event output
- a refresh hint
- safe failure behavior

### 4. Local API First, Shell Later

The local API and browser prototype should exist before Tauri/WebView2 packaging. A shell around a bad API would only hide coupling.

### 5. Preserve Current Behavior

The current pipeline has successful subtitle logic, route logic, pending publish, scratch behavior, and recovery behavior. Migration should expose these systems, not casually replace them.

### 6. Keep V4 Intact

V5 can take architectural risks. V4 remains the rollback target.

## Target Directory Shape

Proposed V5 layout after several phases:

```text
MediaPipelineRemuxEncodeAIO_V5/
  DesktopApp/
    mediapipeline_desktop_app/
      application/
        __init__.py
        facade.py
        dto.py
        dto_base.py
        dto_commands.py
        dto_inventory.py
        dto_status.py
        dto_workspaces.py
        commands.py
        errors.py
        permissions.py
      backend/
        __init__.py
        process_lifecycle.py
        telemetry_service.py
        config_store.py
        state_store.py
        queue_service.py
        audit_service.py
        pending_publish_service.py
        rename_service.py
      api/
        __init__.py
        server.py
        routes_health.py
        routes_snapshot.py
        routes_commands.py
        routes_settings.py
        routes_rename.py
        routes_diagnostics.py
        schemas.py
      ui_tk/
        adapter.py
      ui_web/
        package.json
        src/
          app/
          components/
          pages/
          api/
          state/
          styles/
        dist/
      app.py
      app_bootstrap.py
      services.py
  Pipeline/
  Docs/
```

This is a target, not an immediate file-move order. Early work should add `application/` first and leave existing modules in place.

## Backend Facade

The application facade is the most important transition layer.

### Responsibilities

- Convert current service/app behavior into UI-neutral methods.
- Hide `tkinter`, `customtkinter`, `ttk`, widget refs, `Popen` handles, and app-global state from callers.
- Return serializable DTOs.
- Normalize error handling.
- Provide command/query boundaries usable by both Tk and web.

### First Facade Methods

Read-only first:

| Method | Purpose |
|---|---|
| `get_health()` | Return backend status, app version, paths, runtime readiness summary. |
| `get_snapshot()` | Return current activity, pipeline status, queue counts, progress, schedule, active process state. |
| `get_telemetry()` | Return latest CPU/RAM/GPU/NVENC telemetry sample and history if available. |
| `get_diagnostics()` | Return log tail, recent errors, ActiveJobs, control flags, progress state, event tail. |
| `get_queue_preview()` | Return queue rows and preview health without exposing tree widgets. |
| `get_rename_preview(request)` | Return rename rows using existing rename service logic. |

Implemented command-oriented facade methods:

| Method | Purpose |
|---|---|
| `start_pipeline_process(resolved, request)` | Launch validate, run-once, continuous, or pending-publish drain through existing process service with schedule and active-work guards. |
| `start_audit_process(resolved, request)` | Launch audit through existing process service with active-work guards. |
| `start_rerun_csv_process(resolved, request)` | Launch CSV rerun through existing process service with copy/keep/park defaults. |
| `request_pipeline_control(resolved, action)` | Write pause, stop, or rescan control flags. |
| `save_settings_patch(resolved, request)` | Validate and persist explicit PSD1 patch changes after confirmation. |
| `apply_rename_selection(request)` | Apply transactional selected-row rename plan. |
| `open_diagnostics_location(resolved, request)` | Open backend-allowlisted diagnostics locations. |
| `open_completed_location(resolved, request)` | Open backend-selected completed-row paths. |

Still intentionally deferred:

| Method | Reason |
|---|---|
| `kill_processes(request)` | Emergency kill semantics are highest risk and should remain in the current Tk app until the shell has more real-operation validation. |

## DTO Contract Style

DTOs should be plain, serializable Python dataclasses or pydantic-style models if a dependency is intentionally added later. Start with standard-library dataclasses to keep risk low.

### Command Result

```json
{
  "ok": true,
  "command": "start_pipeline",
  "message": "Started pipeline via PID 1234.",
  "severity": "info",
  "warnings": [],
  "errors": [],
  "job_id": "20260507_...",
  "refresh_hint": "snapshot",
  "log_paths": {
    "stdout": "C:\\...\\RunLogs\\run_...stdout.log",
    "stderr": "C:\\...\\RunLogs\\run_...stderr.log"
  }
}
```

### Snapshot

```json
{
  "schema_version": "desktop_app_snapshot.v1",
  "app_version": "v5.000-dev",
  "activity": "Current activity: Ready.",
  "pipeline_state": "idle",
  "schedule_state": "off",
  "counts": {
    "queue_total": 0,
    "processed": 0,
    "failed": 0,
    "pending_publish": 0
  },
  "active_jobs": [],
  "progress": {},
  "warnings": []
}
```

### Telemetry

```json
{
  "schema_version": "desktop_telemetry.v1",
  "sampled_at": "2026-05-07T21:00:00-04:00",
  "cpu_percent": 12.0,
  "memory_percent": 44.0,
  "gpu_present": true,
  "gpu_encoder_percent": 0.0,
  "gpu_name": "NVIDIA GPU",
  "gpu_count": 1,
  "gpu_rows": [
    {
      "index": "0",
      "name": "NVIDIA GPU",
      "encoder_percent": 0.0
    }
  ],
  "source": "nvidia-smi",
  "error": ""
}
```

Important: `gpu_encoder_percent: 0.0` means the GPU was detected and the encoder is idle. It must not be treated as missing data.

## Local API Model

### Binding

Default binding should be localhost-only:

```text
127.0.0.1:<dynamic or configured port>
```

Remote LAN access should be a separate explicit mode. Do not reuse the coordinator/worker API as the local UI API without authentication and scope review.

### Early API Routes

Read-only routes first:

| Route | Method | Purpose |
|---|---|---|
| `/api/health` | GET | API status, version, feature flags. |
| `/api/snapshot` | GET | Main app snapshot. |
| `/api/backend/close-readiness` | GET | Shell close safety state and reason. |
| `/api/commands` | GET | Recent backend-recorded command-result summaries. |
| `/api/telemetry` | GET | Latest telemetry sample/history. |
| `/api/diagnostics` | GET | Logs, errors, ActiveJobs, events. |
| `/api/queue` | GET | Queue rows with filters/sort params. |
| `/api/rename/preview` | POST | Rename preview request and response. |

Implemented guarded command routes:

| Route | Method | Purpose |
|---|---|---|
| `/api/pipeline/start` | POST | Launch validate, run-once, continuous, or pending-publish drain through the backend schedule/active-work guard. |
| `/api/audit/start` | POST | Launch audit through the backend active-work guard. |
| `/api/rerun/start` | POST | Launch CSV rerun with copy/keep/park safety defaults. |
| `/api/pipeline/control` | POST | Write pause, stop-after-current, or rescan control flags. |
| `/api/settings/save-patch` | POST | Save validated config patch changes after explicit confirmation. |
| `/api/rename/apply` | POST | Apply selected-row rename transaction after explicit confirmation. |
| `/api/diagnostics/open` | POST | Open backend-allowlisted diagnostics locations. |
| `/api/completed/open` | POST | Open backend-selected completed-row locations. |
| `/api/backend/shutdown` | POST | Gracefully stop the shell-owned local API backend. |

### API Security

Even localhost APIs need guardrails:

- Bind to `127.0.0.1` by default.
- Generate a per-run token for shell/frontend requests.
- Do not log token values.
- Reject requests without token for command routes.
- Keep command routes disabled until tests exist.
- Do not expose unrestricted file read endpoints.
- Redact paths in any endpoint intended for remote display.
- Use explicit allowlisted operations such as `open_path(path_id)` rather than arbitrary command execution.

## Tauri/WebView2 Shell Strategy

### First Shell Goal

The first shell should be boring:

1. Start or connect to the local Python backend.
2. Wait for `/api/health`.
3. Load the web frontend.
4. Show backend startup errors in a readable screen.
5. Shut down the backend cleanly when the app exits, unless a pipeline process is intentionally left running.

### Shell Responsibilities

The shell can own:

- window creation
- app icon/title
- local frontend loading
- native open folder/file dialog bridges if needed
- backend process startup/shutdown
- passing backend URL/token to frontend

The shell must not own:

- pipeline logic
- FFmpeg commands
- PowerShell commands
- config writes
- rename application
- pending publish mutation
- queue state
- audit classification

## Frontend Architecture

The web frontend should be organized by workflow, not by backend files.

Suggested pages:

| Page | Purpose |
|---|---|
| Home | Current status, primary commands, queue summary, pending publish, schedule summary. |
| Live | Progress, telemetry, recent events, route details, process state. |
| Queue | Queue table, filters, priority planning, details. |
| Rename | Movie/TV rename planner, scrub filters, selected-row operations, transaction preview. |
| Library | Audit, failures, completed outputs, reports. |
| CSV Rerun | CSV import, preview, policy summary, launch/result logs. |
| Schedule | Weekly schedule editor. |
| Pending Publish | Parked output manifests, drain planning, errors. |
| Settings | Structured config editor with validation and profiles. |
| Diagnostics | Logs, ActiveJobs, control flags, events, tool health, recovery actions. |
| Maintenance | Release package, environment check, cleanup/recovery tools. |

### Frontend State

Frontend state should be limited to:

- selected tab/view
- filters/sort/search
- table column sizes/order
- unsaved form edits
- selected rows
- visible dialogs/drawers

Backend state should remain authoritative for:

- queue records
- active jobs
- pipeline progress
- config on disk
- rename plan validity
- pending publish state
- process status
- telemetry samples

## Process Control Safety

Process controls are the highest risk web commands. They should be delayed until the read-only API and command-result model are stable.

### Required Process Command Properties

Every process command should include:

- command ID
- operator-visible description
- validation outcome
- process/action guard result
- generated ActiveJobs record if launching
- log path result
- event record
- failure record on startup failure

### Dangerous Commands

These should require explicit confirmation and backend validation:

- kill active process tree
- kill related pipeline processes
- clear stale runtime progress
- clear failure records
- apply rename to actual files
- drain pending publish
- save config over existing PSD1

## Telemetry Model

Telemetry should become backend-sampled and frontend-rendered.

Backend owns:

- `psutil` CPU/RAM sampling
- `nvidia-smi` lookup and parsing
- GPU row aggregation
- telemetry errors
- sample timestamps
- history ring buffer if retained server-side

Frontend owns:

- chart rendering
- visual continuity
- tooltips
- multi-GPU presentation
- empty vs 0 percent display

### Telemetry Invariants

- `None` means unavailable or parse failed.
- `0.0` means valid sample with zero activity.
- GPU graph should remain visible if a GPU is detected, even at 0 percent.
- Telemetry errors should be visible in Diagnostics, not silently swallowed.

## Rename Tool Migration

Rename is a strong candidate for early web UI after read-only diagnostics because it benefits from rich tables and batch-edit UX.

### Backend-Owned Rename Logic

Keep backend ownership of:

- movie scrub logic
- TV season/episode inference
- season folder detection
- S00 specials/OVA/OAD/extras rules
- selected-row order
- manual final-name overrides
- force pipeline-name sidecar tagging
- sidecar rename/update
- collision detection
- transactional apply

### Web UI Improvements Enabled

- Inline editable final names.
- Multi-row selected operations.
- Drag/drop or explicit order controls.
- Filter chips for negative filters.
- Confidence labels for TV episode-title inference.
- Side-by-side current/scrubbed/final/pipeline override columns.
- Preview of sidecar changes before apply.
- Transaction plan summary before mutating files.

## Settings Migration

Settings should not be ported as raw form fields first. The web UI should use structured sections with typed controls.

Priority areas:

- routing profile and size guard policy
- encoder preset ladder
- remux vs encode decision settings
- subtitle family settings: ASS/SSA, TX3G, BDPGS
- audio passthrough/downmix/default-language policy
- path layout and scratch/output safety warnings
- pending publish behavior
- diagnostics/logging settings

Backend must preserve unknown PSD1 keys.

## Queue/Audit/Pending Publish Migration

These views should migrate after the read-only snapshot API is stable.

### Queue

- Backend returns normalized queue rows.
- Frontend handles filtering/sorting/paging/virtualization.
- Backend remains authoritative for actual queue planning and priority markers.

### Audit

- Backend returns audit report metadata and rows.
- Frontend provides filter/search/grouping.
- Backend owns rerun CSV export and failure classification.

### Pending Publish

- Backend returns manifest records and payload status.
- Frontend shows destination, size, sidecars, reason, failure state.
- Backend owns drain/publish commands.

## Packaging Plan

### Current Packaging To Preserve

The existing release builder should continue to:

- exclude live config by default
- exclude logs/state/runtime artifacts by default
- include bundled PowerShell/Python/FFmpeg/MKVToolNix/PgsToSrt as appropriate
- include optional tools/docs only by switch
- write `release_manifest.json`
- verify package hygiene

### New Packaging Additions Later

Once the web frontend exists:

- include frontend build output under `DesktopApp\mediapipeline_desktop_app\ui_web\dist` or `DesktopApp\Web`.
- record frontend build/version in release manifest.
- add release verification for frontend assets.
- add backend API startup smoke test.
- add shell executable verification once Tauri/WebView2 shell exists.

### Portable First

Keep the project a portable folder until there is a clear reason for an installer.

## Testing Strategy

### Immediate Tests

Add tests for:

- application facade DTO creation without Tk
- health/snapshot/telemetry DTO serialization
- diagnostics DTO redaction/formatting
- command result envelope
- rename preview facade preserves current behavior

### API Tests

Add tests for:

- API starts on localhost and random port
- `/api/health` returns version and status
- `/api/snapshot` returns valid schema
- API rejects command requests without token
- API shutdown is clean

### Frontend Tests

When frontend exists:

- load Home/Live/Diagnostics with mocked API fixtures
- verify 0 percent GPU telemetry still shows graph
- verify queue table filtering/sorting
- verify rename selected rows and final name edits
- verify settings dirty state

### End-To-End Gates

Before replacing the current GUI:

- full Python desktop tests pass
- PowerShell reliability regression checks pass
- release package verification passes
- current CustomTkinter app still launches
- web API smoke tests pass
- web UI read-only flows pass
- no source mutation behavior changed

## Incremental Work Plan

### Phase 0 - V5 Branch Baseline

Goal: establish V5 as the migration branch.

Tasks:

- Keep V4 untouched.
- Record V5 migration intent in docs.
- Run baseline tests before code refactors.
- Keep current app launcher working.

Risk: low.

### Phase 1 - Application Facade, Read-Only

Goal: add a UI-neutral facade without changing UI behavior.

Tasks:

- Add `application\dto.py` as a compatibility export and split focused DTO families into `dto_base.py`, `dto_commands.py`, `dto_inventory.py`, `dto_status.py`, and `dto_workspaces.py`.
- Add `application\facade.py`.
- Wrap existing `DesktopAppService`.
- Add read-only DTO methods for health, snapshot, telemetry, diagnostics.
- Add tests that do not import or instantiate CustomTkinter.

Risk: low-medium.

### Phase 2 - Command Result Envelope

Goal: standardize backend command results before exposing commands over HTTP.

Tasks:

- Add `CommandResult`.
- Convert selected existing controller/service returns where safe.
- Start with non-destructive commands.
- Keep Tk compatibility shims.

Risk: low-medium.

### Phase 3 - Local API Server, Read-Only

Goal: expose facade through localhost-only API.

Tasks:

- Add API server module.
- Add health/snapshot/telemetry/diagnostics routes.
- Add generated per-run token but allow health token-free.
- Add tests for API lifecycle.
- Do not expose mutation commands yet.

Risk: medium.

### Phase 4 - Browser Prototype, Read-Only

Goal: validate the future UI direction without shell packaging.

Tasks:

- Build minimal frontend for Home, Live, Diagnostics.
- Use mocked fixtures first, then real API.
- Verify telemetry graph behavior.
- Keep current app as default.

Risk: medium.

### Phase 5 - Rename And Queue Prototype

Goal: prove the web frontend handles complex batch/table workflows better than Tk.

Tasks:

- Add rename preview API.
- Add queue query API.
- Build table views with selection, filters, and details.
- Keep apply/mutation disabled or behind backend dry-run.

Risk: medium.

### Phase 6 - Settings Prototype

Goal: validate structured settings UI and config safety.

Tasks:

- Add settings workspace DTO.
- Add validation endpoint.
- Add save endpoint only after tests.
- Preserve unknown keys.
- Show dirty state and diff.

Risk: medium-high.

### Phase 7 - Safe Commands

Goal: add low-risk commands to web UI.

Tasks:

- Refresh snapshot.
- Refresh queue.
- Validate config.
- Open diagnostics log locations through backend-mediated command.
- Toggle pause only after command auth is proven.

Risk: medium.

### Phase 8 - Process Commands

Goal: migrate core operator controls.

Tasks:

- Start validate-only.
- Start run-once.
- Start continuous.
- Stop after current.
- Drain pending publish.
- Kill commands last.

Risk: high. Requires manual validation.

### Phase 9 - Tauri/WebView2 Shell

Goal: package web UI as desktop shell.

Status: scaffold started and developer-validated. `DesktopApp\tauri_shell` now contains a minimal Tauri v2 shell that is designed to spawn the Python local API and open the backend-served UI. It is not yet the default launcher. On this workstation, Node.js, Rust/Cargo, and Visual Studio C++ Build Tools are installed; `npm run check`/`cargo check` and the real launch/close smoke both pass.

Tasks:

- Add shell project. Completed for scaffold-only mode.
- Start backend. Completed for the developer shell.
- Wait for health/bootstrap. Completed through backend bootstrap JSON validation.
- Pass backend URL/token to frontend. Completed through backend-served UI bootstrap.
- Handle startup failure. Completed with child termination on bootstrap, timeout, JSON, or schema failure.
- Handle close behavior. Completed for normal window close and backend close-readiness confirmation. Manual validation with a real active pipeline is still required before making the Tauri shell the production launcher.

Risk: high.

### Phase 10 - Feature Parity And Tk Retirement Decision

Goal: decide if Tk remains fallback or is retired.

Tasks:

- Compare all current workflows.
- Verify daily operation in new UI.
- Keep Tk fallback until at least one real processing cycle, audit cycle, rename apply, settings save, pending drain, and release check succeed from the new UI.

Risk: high if rushed.

## Work Chunk Order

Least to most invasive:

1. Documentation and baseline test notes.
2. Add read-only DTOs.
3. Add application facade.
4. Add facade tests.
5. Move diagnostics read-only formatting behind facade.
6. Add local read-only API.
7. Add browser read-only prototype.
8. Add rename preview API.
9. Add queue API.
10. Add settings workspace API.
11. Add safe commands.
12. Add process commands.
13. Add Tauri/WebView2 shell.
14. Decide Tk fallback/retirement.

## Migration Gates

Do not advance to the next gate until the previous gate passes.

| Gate | Required Proof |
|---|---|
| Gate 1 | Current V5 app launches and current tests pass. |
| Gate 2 | Application facade can be tested without Tk. |
| Gate 3 | Read-only API starts/stops cleanly and returns valid DTOs. |
| Gate 4 | Browser prototype can show live status/diagnostics from real API. |
| Gate 5 | Rename and queue prototypes match current backend behavior. |
| Gate 6 | Settings API preserves PSD1 unknown keys and dirty-state safety. |
| Gate 7 | Safe commands return structured results and event/log evidence. |
| Gate 8 | Process commands match current Tk behavior and recovery semantics. |
| Gate 9 | Tauri/WebView2 shell starts backend and closes safely. |
| Gate 10 | New UI reaches feature parity or Tk remains supported fallback. |

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| API exposes unsafe file operations | Data loss/security risk | Backend allowlists operations; no arbitrary paths/commands. |
| Frontend duplicates backend logic | Drift and wrong decisions | Frontend only renders backend decisions and requests previews. |
| Backend startup fails silently | Operator cannot trust app | Shell must show startup diagnostics and log paths. |
| Local API conflicts with network coordinator API | Confusion/security risk | Separate modules, ports, auth, and route namespaces. |
| Pipeline process left orphaned | Stuck GPU/locks/scratch state | Preserve ActiveJobs and psutil reconciliation. |
| Telemetry 0 percent treated as missing | Empty graph/regression | Telemetry schema distinguishes `None` from `0.0`. |
| Tauri packaging breaks portability | Deployment risk | Browser prototype first; shell packaging only after API is stable. |
| Settings save breaks PSD1 | Pipeline launch failure | Preserve unknown keys; atomic writes; validation before save. |
| Rename apply mutates wrong files | Data loss | Transaction plan, selected-row apply, collision checks, rollback/journal. |
| V5 diverges from V4 unexpectedly | Backup loses value | Do not modify V4; document V5-only changes. |

## What Can Be Pushed Further With This Architecture

The hybrid architecture enables future work that would be awkward in the current Tk-only app:

- Route decision explorer: show why remux vs encode happened, including source codec, size guard, subtitle/audio pressure, and profile rules.
- Encode size analytics: track expected vs actual output size, reject/warn thresholds, encoder profile performance, and problematic releases.
- Subtitle conversion inspector: show ASS/TX3G/BDPGS tracks, conversion results, failures, generated SRTs, and manual-review reasons.
- Audio policy inspector: show default track selection, passthrough/downmix decisions, language fallbacks, and channel output.
- Pending publish dashboard: show parked artifacts, retry history, destination health, sidecars, and drain safety.
- Rename lab: preview whole seasons/movies with confidence levels, filters, sidecar tagging, and batch conflict resolution.
- Worker/coordinator dashboard: if network mode becomes production, show workers, claims, heartbeats, failures, and throughput.
- Historical telemetry: encode speed history, GPU utilization, queue ETAs, disk throughput, and error trends.
- Recovery center: stale progress, orphaned ActiveJobs, failed manifests, sidecar mismatches, and guided cleanup.
- Operator profiles: Plex Direct/Stream, Direct Play, Archive Shrink, Archive Quality, Manual, and folder sidecar overrides in one UI.

## First Implementation Chunk

### Name

V5 Facade Foundation.

### Files To Add

- `DesktopApp\mediapipeline_desktop_app\application\__init__.py`
- `DesktopApp\mediapipeline_desktop_app\application\dto.py`
- `DesktopApp\mediapipeline_desktop_app\application\dto_base.py`
- `DesktopApp\mediapipeline_desktop_app\application\dto_commands.py`
- `DesktopApp\mediapipeline_desktop_app\application\dto_inventory.py`
- `DesktopApp\mediapipeline_desktop_app\application\dto_status.py`
- `DesktopApp\mediapipeline_desktop_app\application\dto_workspaces.py`
- `DesktopApp\mediapipeline_desktop_app\application\facade.py`
- `DesktopApp\tests\test_application_facade.py`

### Files To Avoid Changing Initially

- `DesktopApp\mediapipeline_desktop_app\views\*.py`
- `DesktopApp\mediapipeline_desktop_app\controllers\*.py`
- `Pipeline\*.ps1`
- `Pipeline\Modules\*.ps1`
- release packaging scripts

### Expected Behavior

- No GUI behavior changes.
- No pipeline behavior changes.
- No new dependency.
- New DTOs can serialize to dictionaries.
- Tests can run without a Tk root.

### Validation

Run:

```powershell
cd C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5
$env:PYTHONDONTWRITEBYTECODE='1'
.\DesktopApp\Runtime\Python\python.exe -m unittest discover -s DesktopApp\tests -p "test_*.py"
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1
```

## Working Agreement For V5

- Treat V5 as the active development folder from this point forward.
- Treat V4 as stable fallback.
- Prefer additive backend abstractions before UI rewrites.
- Keep the current CustomTkinter app working at every checkpoint.
- Do not introduce Tauri/WebView2 until the local API is real and tested.
- Do not change media-processing behavior as part of UI migration unless separately requested and tested.
