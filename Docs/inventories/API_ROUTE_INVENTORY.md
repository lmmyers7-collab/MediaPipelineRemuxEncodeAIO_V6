# API Route Inventory

Date: 2026-06-05

Full inventory of all Local API routes: route, method, effect class, backend contract/handler, mutation risk, primary frontend caller, and test coverage. Source: `contract_read.py`, `contract_command.py`, `routes_read.py`, `routes_command.py`.

Total: 89 routes — 36 GET (read) + 53 POST (command).

All routes require the bootstrap token (`Authorization: Bearer` or `X-MediaPipeline-Token`) except `GET /api/health`.

---

## GET Routes (Read — 36 routes)

All GET routes return data only. None launch pipeline work, write config, drain pending outputs, rename files, or mutate queue or manifest state.

### Status Group (11 routes)

| Route | Effect | Response Schema | Frontend Caller | Auth | Backend Test Coverage |
|---|---|---|---|---|---|
| `GET /api/health` | `none` | `desktop_backend_health.v1` | Tauri shell (startup probe) | **No** | `test_app_bootstrap.py`, `test_backend_bootstrap.py`, `test_application_facade_local_api.py` |
| `GET /api/contract` | `none` | `desktop_local_api_contract.v1` | Tauri shell (startup validation) | Yes | `test_api_contract_payload.py`, `test_application_facade_local_api.py` |
| `GET /api/snapshot` | `none` | `desktop_app_snapshot.v1` | Home, all pages (poll) | Yes | `test_facade_status_policy.py`, `test_status_service.py` |
| `GET /api/telemetry` | `none` | `desktop_telemetry.v1` | Home, Live, Diagnostics | Yes | `test_telemetry_service.py` |
| `GET /api/diagnostics` | `none` | `desktop_diagnostics.v1` | Diagnostics, Home | Yes | `test_facade_diagnostics_policy.py` |
| `GET /api/diagnostics/tail` | `none` | `desktop_diagnostics_tail.v1` | Diagnostics | Yes | `test_facade_diagnostics_policy.py`, `test_application_facade_local_api.py` |
| `GET /api/diagnostics/state-summary` | `none` | `desktop_diagnostics_state_summary.v1` | Diagnostics | Yes | `test_facade_diagnostics_policy.py`, `test_application_facade_local_api.py` |
| `GET /api/backend/close-readiness` | `none` | `desktop_close_readiness.v1` | Tauri shell (close flow) | Yes | `test_tauri_shell_scaffold.py`, `test_local_api_lifecycle_contract_smoke.py`, `test_application_facade_local_api.py` |
| `GET /api/ui-preferences` | `none` | `desktop_ui_preferences.v1` | Chrome WebView, Tauri shell | Yes | `test_application_facade_core_contracts.py`, `test_webview_frontend_mutation_boundary.py` |
| `GET /api/launch/preflight` | `none` | `desktop_launch_preflight.v1` + nested `desktop_launch_readiness.v1` | Launch | Yes | `test_service_process_readiness.py`, `test_facade_process_pipeline_policy.py`, `test_application_facade_process_launch.py`, `test_application_facade_local_api.py` |
| `GET /api/commands` | `none` | `desktop_command_history.v1` | Diagnostics, Home | Yes | `test_api_command_journal_policy.py`, `test_application_facade_local_api.py` |

Query params: `/api/diagnostics/tail` accepts `target` (allowlisted key) and `max_bytes` (1 KB–256 KB); backend tail evidence includes `evidence_authority=backend`, and any WebView fallback over older/no-evidence payloads must be labelled frontend advisory only. `/api/launch/preflight` accepts target-specific read-only start-intent fields (`target`, pipeline `mode`, `sleep_seconds`, `show_config`, `show_console`, `single_file`, `schedule_override`, `extra_args`, `allow_extra_args`, audit `library_root`/`include_sidecars`, and rerun `csv_path`/`dry_run`/`stage_mode`/`original_mode`/`return_mode`) and returns nested backend `operator_readiness` (`desktop_launch_readiness.v1`) so Launch readiness rendering does not have to infer start posture from DOM state. `/api/commands` accepts `limit`. `/api/failures` accepts `source` and `limit`. `/api/queue/file-overrides`, `/api/queue/file-overrides/effective`, and `/api/queue/file-overrides/tracks` accept `path` and validate it under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots).

### Inventory Group (16 routes)

| Route | Effect | Response Schema | Frontend Caller | Auth | Backend Test Coverage |
|---|---|---|---|---|---|
| `GET /api/queue` | `none` | `desktop_queue_preview.v1` | Queue | Yes | `test_facade_queue_policy.py`, `test_service_queue_preview_builder.py`, `test_service_queue_source_scan.py` |
| `GET /api/queue/priority` | `none` | `queue_priority_manifest.v1` | Queue | Yes | `test_application_facade_local_api.py` |
| `GET /api/queue/strategy` | `none` | `queue_strategy_state.v1` | Queue | Yes | `test_application_facade_local_api.py` |
| `GET /api/queue/file-overrides` | `none` | `queue_file_overrides.v1` | Queue | Yes | `test_application_facade_local_api.py` |
| `GET /api/queue/file-overrides/effective` | `none` | `queue_file_overrides_effective.v1` | Queue | Yes | `test_application_facade_local_api.py`, `test_file_override_tracks.py` |
| `GET /api/queue/file-overrides/tracks` | `none` | `queue_file_override_tracks.v1` | Queue | Yes | `test_file_override_tracks.py` |
| `GET /api/completed` | `none` | `desktop_completed_preview.v1` | Completed | Yes | `test_facade_completed_policy.py`, `test_service_completed_manifest.py` |
| `GET /api/metrics` | `none` | `desktop_metrics.v1` | Metrics | Yes | `test_metrics_feature.py` |
| `GET /api/final-library-promotion/status` | `none` | `desktop_final_library_promotion_status.v1` | Completed | Yes | `test_final_library_promotion.py` |
| `GET /api/failures` | `none` | `desktop_failure_preview.v1` | Reports, Diagnostics | Yes | `test_facade_failures_policy.py`, `test_service_failure_markers.py` |
| `GET /api/audit-results` | `none` | `desktop_audit_preview.v1` | Reports | Yes | `test_facade_audit_policy.py`, `test_service_audit_rerun_records.py` |
| `GET /api/audit-controls` | `none` | `desktop_audit_controls.v1` | Reports | Yes | `test_application_facade_local_api.py` |
| `GET /api/rename/movie-cleaning-filters` | `none` | `desktop_rename_movie_filter_catalog.v1` | Rename | Yes | `test_api_contract_payload.py`, `test_application_facade_local_api.py` |
| `GET /api/rename/clean-filename-preview` | `none` | `desktop_rename_clean_filename_preview.v1` | Rename | Yes | `test_api_contract_payload.py`, `test_application_facade_local_api.py` |
| `GET /api/pending-publish` | `none` | `desktop_pending_publish_preview.v1` | Pending Publish | Yes | `test_facade_pending_publish_policy.py`, `test_service_pending_publish_manifest.py` |
| `GET /api/publish-reconciliation` | `none` | `desktop_publish_reconciliation.v1` | Completed | Yes | `test_application_facade_pending_publish.py` |

`/api/publish-reconciliation` performs a read-only correlation of Completed rows, current Pending Publish rows, and the latest durable pending drain summary. No repair, drain, or publish action is triggered.

Repair/reconcile mutation remains design-only. `/api/contract` publishes the future dry-run, rollback, source-file, and route-exposure gates, but there are no repair/reconcile POST routes in this inventory and no WebView controls may call one until `docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md` is satisfied.

Network lifecycle mutation remains design-only. `/api/contract` publishes the future dry-run, process cleanup/rollback, source-file, and route-exposure gates for coordinator/worker lifecycle commands, but there are no Network start/stop/reclaim/ops/release/metadata/worker-polling POST routes in this inventory and no WebView controls may call one until `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` is satisfied.

### Workspace Group (9 routes)

| Route | Effect | Response Schema | Frontend Caller | Auth | Backend Test Coverage |
|---|---|---|---|---|---|
| `GET /api/maintenance` | `bounded-health-check` | `desktop_maintenance_workspace.v1` | Maintenance | Yes | `test_facade_maintenance_policy.py`, `test_application_facade_maintenance.py` |
| `GET /api/maintenance/progress` | `none` | `desktop_maintenance_health_progress.v1` | Maintenance | Yes | `test_application_facade_maintenance.py` |
| `GET /api/maintenance/change-ledger` | `none` | `desktop_change_ledger.v1` | Maintenance | Yes | `test_maintenance_change_ledger.py` |
| `GET /api/schedule` | `none` | `desktop_schedule_workspace.v1` | Schedule | Yes | `test_facade_schedule_policy.py`, `test_application_facade_schedule.py` |
| `GET /api/settings/workspace` | `none` | `desktop_settings_workspace.v1` | Settings | Yes | `test_facade_settings_policy.py`, `test_application_facade_settings_workspace.py` |
| `GET /api/settings/wizard/status` | `none` | `desktop_settings_wizard_status.v1` | Settings Wizard | Yes | `test_api_command_contracts.py`, `test_application_facade_settings_workspace.py` |
| `GET /api/settings/wizard/defaults` | `none` | `desktop_settings_wizard.v1` | Settings Wizard | Yes | `test_api_command_contracts.py`, `test_application_facade_settings_workspace.py` |
| `GET /api/network/workers` | `none` | `desktop_network_workers.v1` | Network | Yes | `test_application_facade_network.py`, `test_webview_network_read_only_boundary.py` |
| `GET /api/sample-validation` | `none` | `desktop_sample_validation_log.v1` + summary + readiness + reconciliation + worksheet runs + pilot plan/checklist + sample set + evidence gaps + pilot runbook + policy alignment + validation audit | Home (Validation Log) | Yes | `test_sample_validation_api.py` |

`GET /api/maintenance` runs bounded environment and tool health probes. It does not repair, install, modify, or remove anything. Effect is `bounded-health-check` to distinguish it from pure data reads. `GET /api/maintenance/change-ledger` is a pure read of structured change-control packets and changelog source hygiene; it does not run health probes or regenerate changelog files.

---

## POST Routes (Command — 53 routes)

All POST routes require auth. File-open routes pass row keys or allowlisted target keys. Queue state routes accept only absolute paths under backend-configured `SourceMovies`/`SourceTV` roots and write non-destructive state manifests. Queue source scan is backend-owned and writes scan evidence plus an authoritative queue snapshot through the existing queue-plan dry run.

### Queue Scan And State Commands (9 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/queue/priority` | `queue-state-write` | `path`, `level`, `reason`, `items`, `clear_all`; levels `high`/`normal`/`low`/`hold` | Queue | Medium — writes or clears non-destructive priority manifest only | `test_application_facade_local_api.py` |
| `POST /api/queue/strategy` | `queue-state-write` | `strategy` | Queue | Medium — writes queue strategy state only | `test_application_facade_local_api.py` |
| `POST /api/queue/scan` | `process-dry-run` | `mode`, `force`, `scope`, `reason`; modes `inventory_then_curate`/`inventory_only`/`curate_only`; scope `all` | Queue | Medium — runs backend source inventory and queue-plan dry-run; no media processing or source mutation | `test_service_queue_source_scan.py`, `test_application_facade_queue.py` |
| `POST /api/queue/file-overrides` | `queue-state-write` | `path`, `audio`, `subtitles`, `routing`, `video`, `clear`, `clear_all`, `clear_fields` | Queue | Medium — writes non-destructive file override manifest only | `test_application_facade_local_api.py`, `test_file_override_tracks.py` |
| `POST /api/queue/file-overrides/route-preview` | `read-only-preview` | `path`, `proposed_override` | Queue | None — advisory route impact preview only | `test_application_facade_local_api.py` |
| `POST /api/queue/file-overrides/series-preview` | `read-only-preview` | `path`, `proposed_override` | Queue | None — current-queue TV series batch preview only | `test_file_override_tracks.py` |
| `POST /api/queue/file-overrides/series-apply` | `queue-state-write` | `path`, `proposed_override`, `confirm_apply`, `preview_fingerprint` | Queue | Medium — writes exact per-current-row overrides for eligible detected TV series rows only | `test_file_override_tracks.py`, `test_api_command_contracts.py` |
| `POST /api/queue/file-overrides/folder-preview` | `read-only-preview` | `folder_path`, `proposed_override`, `options` | Queue | None — bounded folder rule impact preview only | `test_file_override_tracks.py` |
| `POST /api/queue/file-overrides/folder-rule` | `queue-state-write` | `folder_path`, `override`, `confirmation`, `clear` | Queue | Medium — writes validated non-destructive folder-prefix override manifest entries only | `test_file_override_tracks.py` |

Priority and file override/folder-rule path writes are rejected unless the submitted path is absolute and under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots). Priority `clear_all` clears priority manifest state only. Series apply requires an immediate matching preview fingerprint, protects exact manual rows, and does not create future show/folder policy. Folder rules reject source/library roots, file-only stream indexes, and raw ffmpeg map fields. The preview routes are read-only and do not write `file_overrides.json`, scan source folders, run processing, or mutate source media. Queue source scan reads source metadata, writes `queue_source_inventory.json`, then uses the backend queue-plan dry-run to refresh `queue_snapshot.json`.

### Failure Marker Commands (1 route)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/failures/clear` | `failure-marker-write` | `scope`, `marker_path`, `marker_paths`, `source_json`, `dry_run`, `confirm_clear` | Reports | Medium — moves failure marker JSON out of the active marker folder only | `test_service_failure_markers.py`, `test_webview_frontend_mutation_boundary.py` |

`failures/clear` requires `confirm_clear: true` unless `dry_run: true`. Submitted marker paths are accepted only when they resolve inside the backend failure marker folder. The command writes a clear manifest and moves marker JSON to a cleared-marker archive; it does not delete media, reports, completed manifests, pending publish state, or source/output files.

### File Open Commands (4 routes)

| Route | Effect | Allowed Targets | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/queue/open` | `shell-open` | `source_file`, `source_folder`, `source_root` | Queue | Low — OS open only | `test_facade_queue_policy.py`, `test_service_file_open.py` |
| `POST /api/completed/open` | `shell-open` | `output_file`, `play_output_file`, `output_folder`, `sidecar`, `source_folder` | Completed | Low | `test_facade_completed_open_policy.py`, `test_service_file_open.py` |
| `POST /api/pending-publish/open` | `shell-open` | `local_file`, `manifest`, `destination_folder`, `source_folder` | Pending Publish | Low | `test_facade_pending_publish_policy.py`, `test_service_file_open.py` |
| `POST /api/pending-publish/recovery-plan` | `none` | `scope` (`all`/`selected`), `row_key` | Pending Publish | None — dry-run plan only | `test_facade_pending_publish_policy.py` |

`recovery-plan` builds a backend-authored dry-run plan and returns it. No files are drained, moved, deleted, or published.

### Final Library Promotion Commands (3 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/final-library-promotion/promote-queue` | `filesystem-mutation` | `confirm_promote`, `row_keys` | Completed | **High** — starts backend-owned queue-wide or selected-row final-library copy/promotion run after confirmation | `test_final_library_promotion.py`, `test_api_command_contracts.py` |
| `POST /api/final-library-promotion/pause` | `control-state-write` | `run_id` | Completed | Medium — writes cooperative pause state for the active promotion run only | `test_final_library_promotion.py`, `test_api_command_contracts.py` |
| `POST /api/final-library-promotion/resume` | `control-state-write` | `run_id` | Completed | Medium — clears cooperative pause state for the active promotion run only | `test_final_library_promotion.py`, `test_api_command_contracts.py` |

Final-library promotion is backend-owned. The frontend can request the run, pause, or resume with allowlisted keys, but the backend owns destination resolution, completed-output eligibility, copy behavior, pause state, and any configured publish-output cleanup.

### Diagnostics Open Command (1 route)

| Route | Effect | Allowed Targets | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/diagnostics/open` | `shell-open` | 20 allowlisted target keys (see below) | Diagnostics, all pages | Low — OS open only | `test_facade_diagnostics_open_policy.py` |

Allowlisted targets (20): `run_logs`, `cluster_log`, `config`, `config_folder`, `workspace`, `state`, `pending_publish`, `failed_reports`, `failed_markers`, `audit_reports`, `queue_snapshot`, `active_jobs`, `completed_manifest`, `latest_failure_report`, `latest_failure_json`, `latest_audit_csv`, `latest_priority_csv`, `last_stdout_log`, `last_stderr_log`, `sample_validation_log`.

Full target catalog: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`.

### UI Preference Commands (1 route)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/ui-preferences` | `ui-state-write` | `storage`, `source_surface` | Chrome WebView, Tauri shell | Low — writes allowlisted UI preference JSON only | `test_application_facade_core_contracts.py`, `test_webview_frontend_mutation_boundary.py` |

`ui-preferences` persists browser-local UI customization such as layout, theme, evidence visibility, and selected tabs under `LocalBase\State`. It does not save settings, mutate queue state, launch work, drain, rename, publish, or touch media files.

### Maintenance Commands (4 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/maintenance/release-dry-run` | `process-dry-run` | `destination_root`, `zip_package`, `verify`, `include_tests` | Maintenance | None — `-DryRun` only | `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` |
| `POST /api/maintenance/release-build` | `deployment-write` | `destination_root`, `zip_package`, `verify`, `include_tests`, `force`, `confirm_create` | Maintenance | Medium — creates deployable release folder, manifest, and optional zip through the backend release builder; `force` may replace the destination | `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` |
| `POST /api/maintenance/completed-backfill-dry-run` | `process-dry-run` | `timeout_seconds` | Maintenance | None — `-DryRun` only | `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` |
| `POST /api/maintenance/dependency-atlas` | `tooling-artifact-write` | `timeout_seconds`, `min_overview_edge_count`, `min_overview_files` | Maintenance | Low — regenerates dependency atlas HTML, PNG/SVG, and CSV tooling artifacts under `docs/generated/dependency-atlas/` only | `test_application_facade_maintenance.py`, `test_application_facade_local_api.py` |

The dry-run routes do not write a release folder, zip, manifest, or completed manifest. `dependency-atlas` writes generated tooling artifacts under `docs/generated/dependency-atlas/` only; it does not touch media, queue, settings, manifests, pending publish state, or pipeline state. `release-build` requires `confirm_create: true`, is blocked while active work is present, and writes deployment artifacts only through the backend release builder.

### Metrics Commands (2 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/metrics/sources` | `metrics-state-write` | `action`, `path`, `source_id`, `label`, `enabled` | Metrics | Medium — writes Metrics source registry state under `State\Metrics` only | `test_metrics_feature.py`, `test_api_command_contracts.py` |
| `POST /api/metrics/backfill` | `metrics-backfill-state-write` | `scope`, `source_id`, `path`, `max_sidecars` | Metrics | Medium — recursively reads configured sidecar roots and writes Metrics cache/status under `State\Metrics`; no media or sidecar mutation | `test_metrics_feature.py`, `test_api_command_contracts.py` |

Metrics source and backfill commands are backend-owned. Source registry updates write only Metrics state, and backfill recursively reads `*.pipeline.json` sidecars under configured source roots while skipping symlinked folders. It does not rewrite sidecars, launch work, drain, publish, rename, mutate queue state, or touch source/output media files.

### Rename Commands (3 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/rename/preview` | `none` | `paths`, `mode`, `show_name`, `season`, `start_episode`, `movie_title`, `movie_year` | Rename | None — predictions only | `test_facade_rename_policy.py`, `test_service_rename_preview.py` |
| `POST /api/rename/browse` | `shell-dialog` | `selection_mode` (`files`, `folder`, `folder_files`), `initial_path` | Rename | Low — opens native Windows file/folder browser only | `test_application_facade_local_api.py`, `test_api_path_dialogs.py`, `test_webview_browser_rename_smoke.py` |
| `POST /api/rename/apply` | `filesystem-mutation` | `paths`, `selected_sources`, `confirm_apply`, `allow_outside_configured_roots` | Rename | **High** — renames files on disk | `test_application_facade_rename.py`, `test_service_rename_apply.py` |

`rename/browse` is a non-mutating path-selection helper: the backend opens the Windows file/folder browser and returns operator-selected paths for staging. It does not preview, apply, rename, move, delete, or touch media files. `rename/apply` requires `confirm_apply: true`. Backend rebuilds the rename plan from its own state, not from the frontend-submitted plan. If selected paths are outside backend-injected configured media roots, the backend also requires `allow_outside_configured_roots: true` after explicit operator review.

### Settings Commands (12 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/settings/validate` | `none` | `values` | Settings | None — validation only | `test_facade_settings_policy.py`, `test_service_config_validation.py`, `test_application_facade_settings_workspace.py` |
| `POST /api/settings/browse-path` | `shell-dialog` | `setting_key`, `selection_mode`, `initial_path` | Settings | Low — backend-owned native Windows folder browser for allowlisted path fields only | `test_application_facade_local_api.py`, `test_api_path_dialogs.py`, `test_webview_frontend_mutation_boundary.py` |
| `POST /api/settings/preview-patch` | `none` | `changes`, `remove_keys`, `library_profile_resets` | Settings; Network Worker Mode Settings delegates through Settings view | None — returns redacted diff | `test_facade_settings_patch_policy.py`, `test_service_config_preview.py` |
| `POST /api/settings/pipeline-plan-preview` | `none` | `source_media`, `changes`, `remove_keys` | Settings | None — validates supplied source facts and returns a backend-owned dry-run pipeline plan only | `test_settings_pipeline_plan_preview.py` |
| `POST /api/settings/save-patch` | `config-write` | `changes`, `remove_keys`, `library_profile_resets`, `confirm_save` | Settings; Network Worker Mode Settings delegates through Settings view | **High** — writes PSD1 config | `test_facade_settings_patch_policy.py`, `test_service_config_save_runner.py` |
| `POST /api/settings/wizard/validate-paths` | `none` | `wizard` | Settings Wizard | None — validation only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/validate-tools` | `none` | `wizard` | Settings Wizard | None — validation only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/probe-hardware` | `none` | `wizard` | Settings Wizard | None — bounded probe evidence only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/validate-workers` | `none` | `wizard` | Settings Wizard | None — validation only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/preview` | `none` | `wizard` | Settings Wizard | None — preview only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/save` | `config-write` | `wizard`, `confirm_save` | Settings Wizard | **High** — writes PSD1 config through the normal backend save path | `test_api_command_contracts.py` |
| `POST /api/settings/reload` | `none` | *(none)* | Settings | None — reloads cached state | `test_facade_settings_policy.py` |

`browse-path` opens only the backend-owned Windows folder browser for allowlisted Settings path fields (`SourceMovies`, `SourceTV`, `Outsource`, `LocalBase`, `FinalLibraryPromotionRuleSourceRoot`, `FinalLibraryPromotionRuleDestinationRoot`) and returns selected-folder validation evidence for WebView staging. It does not save the PSD1, launch work, rewrite queue state, or touch media files. Settings Wizard validation/preview routes share the same backend policy without writing config. `settings/wizard/save` and `save-patch` require `confirm_save: true`; backend backs up current config before writing. Frontend cannot write the PSD1 file directly. The Network page's Worker Mode Settings panel uses the same Settings preview/save routes for config only; it does not create Network lifecycle command routes or start/stop coordinator or worker runtime.

### Schedule Commands (2 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/schedule/preview` | `none` | `enabled`, `day_windows`, `grid` | Schedule | None — validation only | `test_facade_schedule_policy.py`, `test_application_facade_schedule.py` |
| `POST /api/schedule/save` | `app-state-write` | `enabled`, `day_windows`, `grid`, `confirm_save` | Schedule | Medium — writes schedule app-state keys | `test_facade_schedule_policy.py`, `test_service_app_schedule.py`, `test_application_facade_schedule.py` |

`schedule/save` writes only `schedule_enabled` and `schedule_grid` app-state keys. It cannot launch work, alter queue state, or override schedule gates.

### Sample Validation Commands (2 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/sample-validation/preview` | `none` | `schema`, `shell`, `source_path`, `output_path`, `sample_label`, `sample_category`, `proof_strength`, `operator_decision`, `checks`, `evidence`, `operator_notes` | Home | None — preview only; includes read-only current-backend-evidence comparison, pilot evidence packet, post-run capture, and append-readiness/manual-check gap advice | `test_sample_validation_api.py`, `Test-LocalApiSampleValidationContractSmoke.ps1` |
| `POST /api/sample-validation/append` | `validation-log-write` | `schema`, `shell`, `source_path`, `output_path`, `sample_label`, `sample_category`, `proof_strength`, `operator_decision`, `checks`, `evidence`, `operator_notes` | Home | Low — appends to `sample_validation_log.jsonl` only; returns current-evidence, pilot evidence packet, post-run capture, and append-readiness advice but does not accept outputs | `test_sample_validation_api.py`, `Test-LocalApiSampleValidationContractSmoke.ps1` |

`append` does not mark jobs complete, clear failures, drain pending publish, rewrite manifests, launch work, or mutate media files.

### Audit Control Commands (3 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/audit/score-policy` | `audit-state-write` | `policy`, `reset` | Reports | Medium — writes backend-owned audit score policy only | `test_application_facade_local_api.py` |
| `POST /api/audit/ignore` | `audit-state-write` | `action`, `row_keys`, `paths`, `reason`, `priority_only`, `limit` | Reports | Medium — writes audit-only ignore state without queue holds or media mutation | `test_application_facade_local_api.py` |
| `POST /api/audit/export-rerun-csv` | `report-file-write` | `row_keys`, `priority_only`, `limit` | Reports | Medium — writes a backend-owned rerun CSV artifact only; does not launch rerun work | `test_application_facade_local_api.py` |

Audit control commands are backend-owned report/state helpers. They do not
write queue priority, apply holds, launch rerun work, change settings, or touch
media files.

### Process Commands (6 routes)

| Route | Effect | Key Request Keys / Allowed Values | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/pipeline/control` | `control-flag-write` | `action`: `pause`, `stop`, `rescan`, `kill` | Launch | Medium — writes control flags or runs backend-owned emergency process cleanup for `kill` | `test_facade_process_control_policy.py`, `test_application_facade_process_control.py`, `test_service_process_control_flags.py` |
| `POST /api/pipeline/browse-file` | `shell-dialog` | `selection_mode`: `files`; `initial_path` | Launch | Low — opens backend-owned native Windows file browser for single-file staging only; does not save config or launch work | `test_application_facade_local_api.py`, `test_webview_frontend_mutation_boundary.py` |
| `POST /api/pipeline/start` | `process-launch` | `mode`: `once`/`continuous`/`validate`/`drain_pending_pushes`; `schedule_override`: `""`/`run_once`/`ignore` | Launch | **High** — spawns pipeline process | `test_facade_process_pipeline_policy.py`, `test_application_facade_process_launch.py`, `test_facade_process_guard_policy.py` |
| `POST /api/audit/start` | `process-launch` | `library_root`, `include_sidecars`, `show_console` | Launch, Reports | **High** — spawns audit process | `test_facade_process_audit_policy.py`, `test_application_facade_process_launch.py` |
| `POST /api/rerun/start` | `process-launch` | `csv_path`, `dry_run`, `stage_mode`, `original_mode`, `return_mode`, `show_console` | Reports | **High** — spawns rerun process | `test_facade_process_rerun_policy.py`, `test_application_facade_process_launch.py` |
| `POST /api/backend/shutdown` | `backend-lifecycle` | `reason`, `force_active_work_shutdown` | Tauri shell (close flow) | **Critical** — initiates shutdown only when close-readiness is safe, unless literal boolean `true` force cleanup is requested | `test_tauri_shell_scaffold.py`, `test_local_api_lifecycle_contract_smoke.py` |

`rerun/start` media-safe defaults: `stage_mode: copy`, `original_mode: keep`, `return_mode: park`. `backend/shutdown` must be preceded by `GET /api/backend/close-readiness`; unsafe close-readiness returns an error unless `force_active_work_shutdown` is literal JSON boolean `true`.

---

## Effect Class Summary

| Effect | Count | Routes |
|---|---|---|
| `none` (read-only) | 48 | All non-probing GET routes + preview/validate/reload POSTs |
| `bounded-health-check` | 1 | `GET /api/maintenance` |
| `read-only-preview` | 3 | `POST /api/queue/file-overrides/route-preview`, `POST /api/queue/file-overrides/series-preview`, `POST /api/queue/file-overrides/folder-preview` |
| `shell-open` | 4 | `POST /api/queue/open`, `completed/open`, `pending-publish/open`, `diagnostics/open` |
| `shell-dialog` | 3 | `POST /api/rename/browse`, `POST /api/settings/browse-path`, `POST /api/pipeline/browse-file` |
| `ui-state-write` | 1 | `POST /api/ui-preferences` |
| `metrics-state-write` | 1 | `POST /api/metrics/sources` |
| `metrics-backfill-state-write` | 1 | `POST /api/metrics/backfill` |
| `queue-state-write` | 5 | `POST /api/queue/priority`, `queue/strategy`, `queue/file-overrides`, `queue/file-overrides/series-apply`, `queue/file-overrides/folder-rule` |
| `failure-marker-write` | 1 | `POST /api/failures/clear` |
| `audit-state-write` | 2 | `POST /api/audit/score-policy`, `audit/ignore` |
| `report-file-write` | 1 | `POST /api/audit/export-rerun-csv` |
| `process-dry-run` | 3 | `POST /api/queue/scan`, `maintenance/release-dry-run`, `maintenance/completed-backfill-dry-run` |
| `tooling-artifact-write` | 1 | `POST /api/maintenance/dependency-atlas` |
| `deployment-write` | 1 | `POST /api/maintenance/release-build` |
| `control-state-write` | 2 | `POST /api/final-library-promotion/pause`, `final-library-promotion/resume` |
| `control-flag-write` | 1 | `POST /api/pipeline/control` |
| `validation-log-write` | 1 | `POST /api/sample-validation/append` |
| `app-state-write` | 1 | `POST /api/schedule/save` |
| `config-write` | 2 | `POST /api/settings/save-patch`, `settings/wizard/save` |
| `filesystem-mutation` | 2 | `POST /api/rename/apply`, `final-library-promotion/promote-queue` |
| `process-launch` | 3 | `POST /api/pipeline/start`, `audit/start`, `rerun/start` |
| `backend-lifecycle` | 1 | `POST /api/backend/shutdown` |

---

## Test Coverage Summary

| Coverage type | Scope |
|---|---|
| `test_api_contract_payload.py` | Contract schema serialization and shape for all routes |
| `test_api_command_results_policy.py` | POST command result shaping |
| `test_api_read_payloads_policy.py` | GET response payload contracts |
| `test_api_handler_policy.py` | Route handler dispatch (auth, error codes) |
| `test_api_command_journal_policy.py` | `/api/commands` journal entries |
| `test_api_http_helpers.py` | HTTP client error parsing, token headers |
| `test_contracts.py` | Data contract round-trip (all schema versions) |
| Domain policy/facade tests (`test_*_policy.py`, `test_application_facade_*.py`) | Business logic and parameter validation per route group |
| Domain service tests | Underlying service behavior exercised by route handlers |
| WebView smokes (21 PS1 wrappers) | Integration rendering and mutation-boundary verification |
| `Test-LocalApiLifecycleContractSmoke.ps1` | Browser-free lifecycle route contract smoke for close-readiness/shutdown safe and watcher-blocked payloads |
| `Test-LocalApiMaintenanceDryRunContractSmoke.ps1` | Browser-free Maintenance route contract smoke for dry-run-only ops/release/metadata/backfill POSTs, token enforcement, command history, and unchanged temp source/output bytes |
| `Test-LocalApiSampleValidationContractSmoke.ps1` | Browser-free sample-validation route contract smoke for preview/append/read/tail, token enforcement, current-backend-evidence preview, command history, and temp-only validation-log writes |

Routes with no dedicated smoke coverage: `GET /api/telemetry` is covered by `Test-WebViewBrowserTelemetrySmoke.ps1` through the Live page rather than by a route-only smoke. `GET /api/failures` and `GET /api/audit-results` are covered through the browser-backed Maintenance/Reports smoke. `GET /api/maintenance/change-ledger` is covered by route/unit tests plus the browser-backed Maintenance Change Ledger smoke.

---

## See Also

- Route ownership map: `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Command matrix: `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- Mutation boundary matrix: `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Diagnostics target allowlist: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Test coverage matrix: `docs/testing/TEST_COVERAGE_MATRIX.md`
