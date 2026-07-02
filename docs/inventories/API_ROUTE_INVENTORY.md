# API Route Inventory

Date: 2026-06-19

Full inventory of all Local API routes: route, method, effect class, backend contract/handler, mutation risk, primary frontend caller, and test coverage. Source: `contract_read.py`, `contract_command.py`, `routes_read.py`, `routes_command.py`.

Total: 156 routes — 52 GET (read) + 104 POST (command).

All routes require the bootstrap token (`Authorization: Bearer` or `X-MediaPipeline-Token`) except `GET /api/health`.

---

## GET Routes (Read — 52 routes)

All GET routes return data only. None launch pipeline work, write config, drain pending outputs, rename files, or mutate queue or manifest state.

### Status Group (14 routes)

| Route | Effect | Response Schema | Frontend Caller | Auth | Backend Test Coverage |
|---|---|---|---|---|---|
| `GET /api/health` | `none` | `desktop_backend_health.v1` | Tauri shell (startup probe) | **No** | `test_app_bootstrap.py`, `test_backend_bootstrap.py`, `test_application_facade_local_api_http.py` |
| `GET /api/contract` | `none` | `desktop_local_api_contract.v1` | Tauri shell (startup validation) | Yes | `test_api_contract_payload.py`, `test_application_facade_local_api_http.py` |
| `GET /api/snapshot` | `none` | `desktop_app_snapshot.v1` | Home, all pages (poll) | Yes | `test_facade_status_policy.py`, `test_status_service.py`; includes read-only long-run reliability counters when available |
| `GET /api/telemetry` | `none` | `desktop_telemetry.v1` | Home, Live, Diagnostics | Yes | `test_telemetry_service.py` |
| `GET /api/diagnostics` | `none` | `desktop_diagnostics.v1` | Diagnostics, Home | Yes | `test_facade_diagnostics_policy.py`; includes backend-owned autonomy health evidence, not frontend policy authority |
| `GET /api/diagnostics/tail` | `none` | `desktop_diagnostics_tail.v1` | Diagnostics | Yes | `test_facade_diagnostics_policy.py`, `test_application_facade_local_api_diagnostics.py` |
| `GET /api/diagnostics/state-summary` | `none` | `desktop_diagnostics_state_summary.v1` | Diagnostics | Yes | `test_facade_diagnostics_policy.py`, `test_application_facade_local_api_diagnostics.py` |
| `GET /api/diagnostics/tdarr-matrix/latest` | `none` | `desktop_tdarr_matrix_console.v1` | Diagnostics | Yes | `test_service_tdarr_matrix_audit.py` |
| `GET /api/diagnostics/tdarr-matrix/runs` | `none` | `desktop_tdarr_matrix_runs.v1` | Diagnostics | Yes | `test_service_tdarr_matrix_audit.py` |
| `GET /api/diagnostics/tdarr-matrix/compare` | `none` | `desktop_tdarr_matrix_compare.v1` | Diagnostics | Yes | `test_service_tdarr_matrix_audit.py` |
| `GET /api/backend/close-readiness` | `none` | `desktop_close_readiness.v1` | Tauri shell (close flow) | Yes | `test_tauri_shell_scaffold.py`, `test_local_api_lifecycle_contract_smoke.py`, `test_application_facade_local_api_lifecycle.py` |
| `GET /api/ui-preferences` | `none` | `desktop_ui_preferences.v1` | Chrome WebView, Tauri shell | Yes | `test_application_facade_core_contracts.py`, `test_webview_frontend_mutation_boundary.py` |
| `GET /api/launch/preflight` | `none` | `desktop_launch_preflight.v1` + nested `desktop_launch_readiness.v1` | Launch | Yes | `test_service_process_readiness.py`, `test_facade_process_pipeline_policy.py`, `test_application_facade_process_launch.py`, `test_application_facade_local_api_http.py`; pipeline checks include non-blocking encoder capability diagnostic evidence and refresh `State\Progress\encoder_capabilities.json` only when `refresh_encoder_capability_report=true` |
| `GET /api/commands` | `none` | `desktop_command_history.v1` | Diagnostics, Home | Yes | `test_api_command_journal_policy.py`, `test_application_facade_local_api_http.py`, `test_application_facade_local_api_workflow.py` |
| `GET /api/rerun/results` | `none` | `desktop_rerun_results.v1` | Launch | Yes | `test_api_contract_payload.py`, `test_application_facade_process_launch.py` |

Query params: `/api/diagnostics/tail` accepts `target` (allowlisted key) and `max_bytes` (1 KB–256 KB); backend tail evidence includes `evidence_authority=backend`, and any WebView fallback over older/no-evidence payloads must be labelled frontend advisory only. `/api/launch/preflight` accepts target-specific read-only start-intent fields (`target`, pipeline `mode`, `sleep_seconds`, `show_config`, `show_console`, `single_file`, `schedule_override`, `extra_args`, `allow_extra_args`, `refresh_encoder_capability_report`, audit `library_root`/`include_sidecars`, and rerun `csv_path`/`dry_run` plus lifecycle fields `execution_mode`/`destination_mode`/`original_policy`/`collision_policy`/`window_size`; legacy rerun `stage_mode`/`original_mode`/`return_mode` aliases are accepted for compatibility) and returns nested backend `operator_readiness` (`desktop_launch_readiness.v1`) plus pipeline encoder capability report evidence; pipeline preflight refreshes the backend diagnostic artifact at `State\Progress\encoder_capabilities.json` only when `refresh_encoder_capability_report=true`, so routine Launch readiness rendering stays read-only and does not infer start posture from DOM state. `/api/commands` accepts `limit`. `/api/failures` accepts `source` and `limit`. `/api/queue/file-overrides`, `/api/queue/file-overrides/effective`, and `/api/queue/file-overrides/tracks` accept `path` and validate it under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots).

### Inventory Group (23 routes)

| Route | Effect | Response Schema | Frontend Caller | Auth | Backend Test Coverage |
|---|---|---|---|---|---|
| `GET /api/queue` | `none` | `desktop_queue_preview.v1` | Queue | Yes | `test_facade_queue_policy.py`, `test_service_queue_preview_builder.py`, `test_service_queue_source_scan.py` |
| `GET /api/queue/priority` | `none` | `queue_priority_manifest.v1` | Queue | Yes | `test_application_facade_local_api_queue.py` |
| `GET /api/queue/strategy` | `none` | `queue_strategy_state.v1` | Queue | Yes | `test_application_facade_local_api_queue.py` |
| `GET /api/queue/file-overrides` | `none` | `queue_file_overrides.v1` | Queue | Yes | `test_application_facade_local_api_queue.py` |
| `GET /api/queue/file-overrides/effective` | `none` | `queue_file_overrides_effective.v1` | Queue | Yes | `test_application_facade_local_api_queue.py`, `test_file_override_tracks.py` |
| `GET /api/queue/file-overrides/tracks` | `none` | `queue_file_override_tracks.v1` | Queue | Yes | `test_file_override_tracks.py` |
| `GET /api/completed` | `none` | `desktop_completed_preview.v1` | Completed | Yes | `test_facade_completed_policy.py`, `test_service_completed_manifest.py` |
| `GET /api/subtitle-qa/summary` | `none` | `subtitle_qa_summary.v1` | Queue, Completed | Yes | `test_subtitle_qa_feature.py` |
| `GET /api/subtitle-qa/item` | `none` | `subtitle_qa_result.v1` | Queue, Completed | Yes | `test_subtitle_qa_feature.py` |
| `GET /api/metrics` | `none` | `desktop_metrics.v1` | Metrics | Yes | `test_metrics_feature.py` |
| `GET /api/final-library-promotion/status` | `none` | `desktop_final_library_promotion_status.v1` | Completed | Yes | `test_final_library_promotion.py` |
| `GET /api/failures` | `none` | `desktop_failure_preview.v1` + backend-authored `resolution_summary` / `resolution_groups` / row `evidence_details` | Reports, Diagnostics | Yes | `test_facade_failures_policy.py`, `test_application_facade_local_api_workflow.py`, `test_service_failure_markers.py` |
| `GET /api/failures/artifacts` | `none` | `failure_artifact_summary.v1` | Home, Reports | Yes | `test_service_failure_markers.py`, `test_application_facade_local_api_http.py`, `test_reports_view_static.py`, `test_application_facade_web_static.py` |
| `GET /api/audit-results` | `none` | `desktop_audit_preview.v1` | Reports | Yes | `test_facade_audit_policy.py`, `test_service_audit_rerun_records.py` |
| `GET /api/audit-controls` | `none` | `desktop_audit_controls.v1` | Reports | Yes | `test_application_facade_local_api_http.py` |
| `GET /api/audit-sources` | `none` | `desktop_audit_sources.v1` | Reports | Yes | `test_audit_sources.py`, `test_webview_browser_maintenance_reports_smoke.py` |
| `GET /api/rename/cleaning-filters` | `none` | `desktop_rename_cleaning_filter_catalog.v1` | Rename, Settings | Yes | `test_api_contract_payload.py`, `test_application_facade_local_api_rename.py` |
| `GET /api/rename/movie-cleaning-filters` | `none` | `desktop_rename_movie_filter_catalog.v1` | Rename | Yes | `test_api_contract_payload.py`, `test_application_facade_local_api_rename.py` |
| `GET /api/rename/clean-filename-preview` | `none` | `desktop_rename_clean_filename_preview.v1` | Rename | Yes | `test_api_contract_payload.py`, `test_application_facade_local_api_rename.py` |
| `GET /api/pending-publish` | `none` | `desktop_pending_publish_preview.v1` | Pending Publish | Yes | `test_facade_pending_publish_policy.py`, `test_service_pending_publish_manifest.py` |
| `GET /api/publish-reconciliation` | `none` | `desktop_publish_reconciliation.v1` | Completed | Yes | `test_application_facade_pending_publish.py` |

`/api/publish-reconciliation` performs a read-only correlation of Completed rows, current Pending Publish rows, and the latest durable pending drain summary. No repair, drain, or publish action is triggered.

Repair/reconcile dry-run routes now publish a stable `dry_run_fingerprint`; confirmed apply routes rerun the dry-run, require a matching fingerprint plus explicit confirmation, back up touched manifests/sidecars, and remain backend-owned.

Network lifecycle start/stop now has backend-owned dry-run and confirmed command routes. Dry-runs have `effect=none` and report preconditions plus `would_not_touch` evidence. Confirmed routes are confirmation-gated, command-journaled, and provider-guarded; if the real coordinator/worker lifecycle provider is unavailable, they fail closed without normal Launch, queue scan, media processing, or source/scratch/output/pending-publish mutation.

### Workspace Group (17 routes)

| Route | Effect | Response Schema | Frontend Caller | Auth | Backend Test Coverage |
|---|---|---|---|---|---|
| `GET /api/maintenance` | `bounded-health-check` | `desktop_maintenance_workspace.v1` | Maintenance | Yes | `test_facade_maintenance_policy.py`, `test_application_facade_maintenance.py` |
| `GET /api/maintenance/progress` | `none` | `desktop_maintenance_health_progress.v1` | Maintenance | Yes | `test_application_facade_maintenance.py` |
| `GET /api/maintenance/change-ledger` | `none` | `desktop_change_ledger.v1` | Maintenance | Yes | `test_maintenance_change_ledger.py` |
| `GET /api/maintenance/productization` | `none` | `desktop_productization_status.v1` | Maintenance | Yes | `test_productization_support.py` |
| `GET /api/schedule` | `none` | `desktop_schedule_workspace.v1` | Schedule | Yes | `test_facade_schedule_policy.py`, `test_application_facade_schedule.py` |
| `GET /api/watch-folders/status` | `none` | `desktop_watch_folders.v1` | Schedule | Yes | `test_watch_folder_routes.py` |
| `GET /api/settings/workspace` | `none` | `desktop_settings_workspace.v1` | Settings | Yes | `test_facade_settings_policy.py`, `test_application_facade_settings_workspace.py`, `test_application_facade_local_api_http.py` |
| `GET /api/settings/preset-library` | `none` | `preset_library.v1` | Settings | Yes | `test_preset_library.py`, `test_api_command_contracts.py` |
| `GET /api/libraries/summary` | `none` | `desktop_libraries_summary.v1` | Libraries | Yes | `test_library_route_map_api.py`, `test_service_queue_source_scan.py`, `test_api_contract_payload.py` |
| `GET /api/libraries/route-map` | `none` | `library_route_map.v1` | Libraries | Yes | `test_route_map.py`, `test_library_route_map_api.py`, `test_api_contract_payload.py` |
| `GET /api/libraries/route-map/trace` | `none` | `library_route_trace.v1` | Libraries | Yes | `test_route_map.py`, `test_library_route_map_api.py`, `test_api_contract_payload.py` |
| `GET /api/libraries/route-map/compare` | `none` | `library_profile_compare.v1` | Libraries | Yes | `test_route_map.py`, `test_library_route_map_api.py`, `test_api_contract_payload.py` |
| `GET /api/libraries/route-map/validation` | `none` | `library_route_validation_handoff.v1` | Libraries | Yes | `test_route_map.py`, `test_library_route_map_api.py`, `test_api_contract_payload.py` |
| `GET /api/settings/wizard/status` | `none` | `desktop_settings_wizard_status.v1` | Settings Wizard | Yes | `test_api_command_contracts.py`, `test_application_facade_settings_workspace.py` |
| `GET /api/settings/wizard/defaults` | `none` | `desktop_settings_wizard.v1` | Settings Wizard | Yes | `test_api_command_contracts.py`, `test_application_facade_settings_workspace.py` |
| `GET /api/network/workers` | `none` | `desktop_network_workers.v1` | Network | Yes | `test_application_facade_network.py`, `test_webview_network_read_only_boundary.py` |
| `GET /api/sample-validation` | `none` | `desktop_sample_validation_log.v1` + summary + readiness + reconciliation + worksheet runs + pilot plan/checklist + sample set + evidence gaps + pilot runbook + policy alignment + validation audit | Home (Validation Log) | Yes | `test_sample_validation_api.py` |

`GET /api/maintenance` runs bounded environment and tool health probes. It does not repair, install, modify, or remove anything. Effect is `bounded-health-check` to distinguish it from pure data reads. `GET /api/maintenance/change-ledger` is a pure read of structured change-control packets and changelog source hygiene; it does not run health probes or regenerate changelog files.

---

## POST Routes (Command — 104 routes)

All POST routes require auth. File-open routes pass row keys or allowlisted target keys. Queue state routes accept only absolute paths under backend-configured `SourceMovies`/`SourceTV` roots and write non-destructive state manifests. Queue source scan is backend-owned and writes scan evidence plus an authoritative queue snapshot through the existing queue-plan dry run.

### Queue Scan And State Commands (12 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/queue/priority` | `queue-state-write` | `path`, `level`, `reason`, `items`, `clear_all`; levels `high`/`normal`/`low`/`hold` | Queue | Medium — writes or clears non-destructive priority manifest only | `test_application_facade_local_api_queue.py` |
| `POST /api/queue/strategy` | `queue-state-write` | `strategy` | Queue | Medium — writes queue strategy state only | `test_application_facade_local_api_queue.py` |
| `POST /api/queue/scan` | `process-dry-run` | `mode`, `force`, `scope`, `reason`; modes `inventory_then_curate`/`inventory_only`/`curate_only`; scope `all` | Queue | Medium — runs backend source inventory and queue-plan dry-run; no media processing or source mutation | `test_service_queue_source_scan.py`, `test_application_facade_queue.py` |
| `POST /api/queue/file-overrides` | `queue-state-write` | `path`, `audio`, `subtitles`, `routing`, `video`, `clear`, `clear_all`, `clear_fields` | Queue | Medium — writes non-destructive file override manifest only | `test_application_facade_local_api_queue.py`, `test_file_override_tracks.py` |
| `POST /api/queue/file-overrides/route-preview` | `read-only-preview` | `path`, `proposed_override` | Queue | None — advisory route impact preview only | `test_application_facade_local_api_queue.py` |
| `POST /api/queue/file-overrides/series-preview` | `read-only-preview` | `path`, `proposed_override` | Queue | None — current-queue TV series batch preview only | `test_file_override_tracks.py` |
| `POST /api/queue/file-overrides/series-apply` | `queue-state-write` | `path`, `proposed_override`, `confirm_apply`, `preview_fingerprint` | Queue | Medium — writes exact per-current-row overrides for eligible detected TV series rows only | `test_file_override_tracks.py`, `test_api_command_contracts.py` |
| `POST /api/queue/file-overrides/series-clear-preview` | `read-only-preview` | `path` | Queue | None — current-queue TV series exact-override clear preview only | `test_file_override_tracks.py` |
| `POST /api/queue/file-overrides/series-clear-apply` | `queue-state-write` | `path`, `confirm_apply`, `preview_fingerprint` | Queue | Medium — clears exact per-current-row file overrides for detected TV series rows only | `test_file_override_tracks.py`, `test_api_command_contracts.py` |
| `POST /api/queue/file-overrides/remux-pilot-promote` | `queue-state-write` | `pilot_source_paths`, `confirm_apply`, `reason` | Queue | Medium — writes exact per-file remux overrides for eligible current queue rows in the detected pilot series only | `test_api_command_contracts.py` |
| `POST /api/queue/file-overrides/folder-preview` | `read-only-preview` | `folder_path`, `proposed_override`, `options` | Queue | None — bounded folder rule impact preview only | `test_file_override_tracks.py` |
| `POST /api/queue/file-overrides/folder-rule` | `queue-state-write` | `folder_path`, `override`, `confirmation`, `clear` | Queue | Medium — writes validated non-destructive folder-prefix override manifest entries only | `test_file_override_tracks.py` |

Priority and file override/folder-rule path writes are rejected unless the submitted path is absolute and under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots). Priority `clear_all` clears priority manifest state only. Series apply and remux pilot promotion require confirmation, protect exact manual rows, and do not create future show/folder policy. Series clear requires confirmation plus a matching preview fingerprint, clears exact current-row file overrides only, and leaves inherited folder rules untouched. Folder rules reject source/library roots, file-only stream indexes, and raw ffmpeg map fields. The preview routes are read-only and do not write `file_overrides.json`, scan source folders, run processing, or mutate source media. Queue source scan reads source metadata, writes `queue_source_inventory.json`, then uses the backend queue-plan dry-run to refresh `queue_snapshot.json`.

### Failure Marker And Artifact Commands (5 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/failures/clear` | `failure-marker-write` | `scope`, `marker_path`, `marker_paths`, `source_json`, `dry_run`, `confirm_clear` | Reports | Medium — moves failure marker JSON out of the active marker folder only | `test_service_failure_markers.py`, `test_webview_frontend_mutation_boundary.py` |
| `POST /api/failures/archive-evidence` | `failure-evidence-archive` | `scope`, `include_markers`, `include_reports`, `dry_run`, `dry_run_fingerprint`, `confirm_archive`, `reason` | Reports | Medium — moves active failure markers and round failure reports into a manifest-backed evidence archive only; routine confirmed archive can use the current backend plan without a reason or fingerprint | `test_service_failure_markers.py`, `test_api_command_contracts.py` |
| `POST /api/failures/open` | `shell-open` | `row_key`, `target`, `source_kind` | Reports | Low — opens only backend-owned failure evidence paths selected from the current failure preview row | `test_application_facade_reports.py`, `test_api_command_contracts.py` |
| `POST /api/failures/artifacts/cleanup` | `failure-artifact-delete` | `dry_run`, `dry_run_fingerprint`, `confirm_delete`, `reason`, `retention_days`, `target_gb`, `artifact_paths` | Reports | High — permanently deletes backend-owned failure artifact files only after confirmation; selected `artifact_paths` still require a dry-run fingerprint; policy cleanup can use the current backend plan; never deletes source/output media | `test_service_failure_markers.py`, `test_application_facade_local_api_http.py`, `test_api_command_contracts.py`, `test_reports_view_static.py` |
| `POST /api/failures/lifecycle` | `failure-resolution-journal-write` | `journal_key`, `transition`, `step_id`, `reason`, `operator_note`, `dry_run`, `dry_run_fingerprint`, `confirm_transition` | Reports | Low — appends operator lifecycle evidence for an active failure group only | `test_application_facade_reports.py`, `test_api_command_contracts.py` |

`failures/clear` requires `confirm_clear: true` unless `dry_run: true`. Submitted marker paths are accepted only when they resolve inside the backend failure marker folder. The command writes a clear manifest and moves marker JSON to a cleared-marker archive; it does not delete media, reports, completed manifests, pending publish state, or source/output files.
`failures/archive-evidence` supports `scope: all_active` in v1. Confirmed archive requires `confirm_archive: true`; reason and dry-run fingerprint are optional for routine current-plan archive, and supplied fingerprints are validated. Confirmed archive moves active marker JSON and `round_failures_*.json/.txt` reports into `State\Failures\ClearManifests\ClearedEvidence`; it does not unlink evidence directly and does not touch media, completed manifests, pending publish state, or source/output files.
`failures/open` accepts only `row_key`, `target`, and `source_kind`; the backend resolves the current failure preview row and opens only allowed evidence targets (`artifact`, `repro`, `record_file`, `record_folder`) under backend failure evidence roots.
`failures/artifacts/cleanup` previews and then deletes only files under backend-resolved current and legacy failure artifact roots. Confirmed delete requires `confirm_delete: true`; selected `artifact_paths` deletion requires the matching dry-run fingerprint, while policy-based cleanup can use the current backend plan and records a default reason when omitted. Configured `FailureArtifactCleanupTargetGB = 0` keeps automatic cleanup disabled; an explicit command payload with `target_gb: 0` still previews/deletes the current failure artifact backlog. It never deletes source media, output media, failure markers, round failure reports, completed manifests, pending publish state, or artifact root directories.
`failures/lifecycle` appends operator resolution-state events under `State\Failures\ResolutionJournal\events.jsonl`. It requires a backend-authored active failure group; resolve/reopen/waive transitions require a non-empty reason and `confirm_transition: true`, with blockers recomputed by the backend at apply time. It does not clear markers, archive reports, retry work, mutate queue/publish/completed state, or touch media files.

### File Open, Pending Recovery, And Repair/Reconcile Commands (13 routes)

| Route | Effect | Allowed Targets | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/queue/open` | `shell-open` | `source_file`, `source_folder`, `source_root` | Queue | Low — OS open only | `test_facade_queue_policy.py`, `test_service_file_open.py` |
| `POST /api/completed/open` | `shell-open` | `output_file`, `play_output_file`, `output_folder`, `sidecar`, `source_folder` | Completed | Low | `test_facade_completed_open_policy.py`, `test_service_file_open.py` |
| `POST /api/pending-publish/open` | `shell-open` | `local_file`, `manifest`, `destination_folder`, `source_folder` | Pending Publish | Low | `test_facade_pending_publish_policy.py`, `test_service_file_open.py` |
| `POST /api/pending-publish/recovery-plan` | `none` | `scope` (`all`/`selected`), `row_key` | Pending Publish | None — dry-run plan only | `test_facade_pending_publish_policy.py` |
| `POST /api/completed/reconcile-manifest-dry-run` | `none` | `scope`, `row_key`, `limit`, `reason` | Completed | None — backend dry-run diff only; no manifest write | `test_repair_reconcile_dry_run.py`, `test_application_facade_local_api_repair.py` |
| `POST /api/completed/reconcile-manifest` | `completed-manifest-write` | `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply` | Completed | Medium — backs up and atomically rewrites existing selected completed manifest rows only after matching dry-run fingerprint | `test_repair_reconcile_apply.py`, `test_api_command_contracts.py` |
| `POST /api/completed/repair-sidecar-metadata-dry-run` | `none` | `scope`, `row_key`, `limit`, `reason` | Completed | None — backend dry-run diff only; no sidecar write | `test_repair_reconcile_dry_run.py`, `test_application_facade_local_api_repair.py` |
| `POST /api/completed/repair-sidecar-metadata` | `completed-sidecar-json-write` | `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply` | Completed | Medium — backs up and atomically rewrites backend-derived sidecar metadata fields only; unknown sidecar fields are preserved | `test_repair_reconcile_apply.py`, `test_api_command_contracts.py` |
| `POST /api/pending-publish/repair-manifest-dry-run` | `none` | `scope`, `row_key`, `limit`, `reason` | Pending Publish | None — backend dry-run diff only; can produce backend-validated manifest-normalization candidates but writes nothing and does not drain | `test_repair_reconcile_dry_run.py`, `test_application_facade_local_api_repair.py` |
| `POST /api/pending-publish/repair-manifest` | `pending-manifest-write` | `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply` | Pending Publish | Medium — writes only backend-validated manifest-normalization candidates after matching fingerprint and strict confirmation; blocks incomplete evidence; no drain, publish, move, or delete | `test_repair_reconcile_apply.py`, `test_api_command_contracts.py` |
| `POST /api/pending-publish/reconcile-orphan-payloads-dry-run` | `none` | `scope`, `row_key`, `limit`, `reason` | Pending Publish | None — backend dry-run evidence only; no manifest create, drain, or publish | `test_repair_reconcile_dry_run.py`, `test_application_facade_local_api_repair.py` |
| `POST /api/pending-publish/reconcile-orphan-payloads` | `pending-orphan-manifest-write` | `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply` | Pending Publish | Medium — manifest-only confirmed route exists but blocks without complete backend evidence; never moves, deletes, drains, or publishes payloads | `test_repair_reconcile_apply.py`, `test_api_command_contracts.py` |
| `POST /api/startup/reconcile-dry-run` | `none` | `scope`, `row_key`, `limit`, `reason` | No WebView caller; backend route only | None — backend startup reconciliation evidence only; no manifest write, repair, rebuild, drain, publish, move, delete, or media touch | `test_repair_reconcile_dry_run.py`, `test_application_facade_local_api_repair.py` |

`recovery-plan` builds a backend-authored dry-run plan and returns it. Repair/reconcile dry-runs accept only `scope`, `row_key`, `limit`, and `reason`, suppress command journaling, and return a dry-run fingerprint. Confirmed apply routes accept only scope, row key, limit, reason, fingerprint, and `confirm_apply`; they rerun the backend dry-run and reject stale fingerprints or unsafe dry-run state. No repair/reconcile route drains, moves, deletes, publishes, reruns, or touches media bytes.

### Subtitle QA Preview Commands (1 route)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/subtitle-qa/preview` | `read-only-preview` | `id`, `row_key`, `path`, `source_path`, `output_path`, `scope`, `limit` | Queue, Completed | None — backend-authored evidence preview only | `test_subtitle_qa_feature.py` |

`subtitle-qa/preview` reads evidence already present in loaded Queue and Completed payloads. It does not probe files, OCR, convert, sync, repair, rewrite sidecars, publish, drain, or touch media.

### Final Library Promotion Commands (3 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/final-library-promotion/promote-queue` | `filesystem-mutation` | `confirm_promote`, `row_keys` | Completed | **High** — starts backend-owned queue-wide or selected-row final-library copy/promotion run after confirmation | `test_final_library_promotion.py`, `test_api_command_contracts.py` |
| `POST /api/final-library-promotion/pause` | `control-state-write` | `run_id` | Completed | Medium — writes cooperative pause state for the active promotion run only | `test_final_library_promotion.py`, `test_api_command_contracts.py` |
| `POST /api/final-library-promotion/resume` | `control-state-write` | `run_id` | Completed | Medium — clears cooperative pause state for the active promotion run only | `test_final_library_promotion.py`, `test_api_command_contracts.py` |

Final-library promotion is backend-owned. The frontend can request the run, pause, or resume with allowlisted keys, but the backend owns destination resolution, completed-output eligibility, copy behavior, pause state, and any configured publish-output cleanup.

### Diagnostics Commands (4 routes)

| Route | Effect | Allowed Targets | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/diagnostics/open` | `shell-open` | 20 allowlisted target keys (see below) | Diagnostics, all pages | Low — OS open only | `test_facade_diagnostics_open_policy.py` |
| `POST /api/diagnostics/tdarr-matrix-audit` | `diagnostic-process` | actions: `report`, `smoke`, `matrix`, `full`, `strict-report` | Diagnostics | Medium — backend runs fixed Tdarr Matrix scratch audit presets only | `test_service_tdarr_matrix_audit.py` |
| `POST /api/diagnostics/tdarr-matrix/evidence/open` | `shell-open` | `stdout`, `stderr`, `worker_result`, `source_hashes`, `failure_artifact`, `output`, `report_folder` | Diagnostics | Low — opens only backend-resolved Tdarr Matrix evidence artifacts | `test_service_tdarr_matrix_audit.py` |
| `POST /api/diagnostics/tdarr-matrix/rerun` | `diagnostic-process` | selections: `selected`, `latest_failures` | Diagnostics | Medium — backend maps finding keys to manifest case IDs and reruns into a fresh isolated TdarrMatrixRuns root | `test_service_tdarr_matrix_audit.py` |

Allowlisted targets (20): `run_logs`, `cluster_log`, `config`, `config_folder`, `workspace`, `state`, `pending_publish`, `failed_reports`, `failed_markers`, `audit_reports`, `queue_snapshot`, `active_jobs`, `completed_manifest`, `latest_failure_report`, `latest_failure_json`, `latest_audit_csv`, `latest_priority_csv`, `last_stdout_log`, `last_stderr_log`, `sample_validation_log`.

Full target catalog: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`.

### UI Preference Commands (2 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/ui-preferences` | `ui-state-write` | `storage`, `source_surface` | Chrome WebView, Tauri shell | Low — writes allowlisted UI preference JSON only | `test_application_facade_core_contracts.py`, `test_webview_frontend_mutation_boundary.py` |
| `POST /api/path-picker/browse` | `shell-dialog` | `target_key`, `selection_mode`, `initial_path`, `file_filter` | WebView path picker badges | Low — opens a backend-owned native Windows picker for allowlisted path targets only; stages validation evidence only | `test_path_picker_command.py` |

`ui-preferences` persists browser-local UI customization such as layout, theme, evidence visibility, and selected tabs under `LocalBase\State`. `path-picker/browse` opens a backend-owned Windows picker for allowlisted real path fields and returns staged-only validation evidence. Neither route saves settings, mutates queue state, launches work, drains, renames, publishes, or touches media files.

### Maintenance Commands (8 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/maintenance/release-dry-run` | `process-dry-run` | `destination_root`, `zip_package`, `verify`, `include_tests` | Maintenance | None — `-DryRun` only | `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` |
| `POST /api/maintenance/release-build` | `deployment-write` | `destination_root`, `zip_package`, `verify`, `include_tests`, `force`, `confirm_create` | Maintenance | Medium — creates deployable release folder, manifest, and optional zip through the backend release builder; `force` may replace the destination | `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` |
| `POST /api/maintenance/completed-backfill-dry-run` | `process-dry-run` | `timeout_seconds` | Maintenance | None — `-DryRun` only | `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` |
| `POST /api/maintenance/retention-dry-run` | `none` | `limit`, `reason` | No WebView caller; backend route only | None — backend retention cleanup candidate report only; no delete, move, archive, truncate, rewrite, drain, publish, or media touch | `test_maintenance_retention_dry_run.py` |
| `POST /api/maintenance/dependency-atlas` | `tooling-artifact-write` | `timeout_seconds`, `min_overview_edge_count`, `min_overview_files` | Maintenance | Low — regenerates dependency atlas HTML, PNG/SVG, and CSV tooling artifacts under `docs/generated/dependency-atlas/` only | `test_application_facade_maintenance.py`, `test_application_facade_local_api_workflow.py` |
| `POST /api/maintenance/dependency-atlas/open-folder` | `shell-open` | none | Maintenance | Low — opens the backend-resolved `docs/generated/dependency-atlas/` folder only; no frontend path is accepted | `test_application_facade_maintenance.py`, `test_application_facade_local_api_workflow.py`, `test_webview_frontend_mutation_boundary.py` |
| `POST /api/maintenance/support-export` | `diagnostics-artifact-write` | `reason`, `include_recent_logs`, `max_log_bytes` | Maintenance | Low — writes a redacted support export under per-user AppData DiagnosticsExports; no config write, launch, queue, manifest, or media mutation | `test_application_facade_maintenance.py`, `test_api_command_contracts.py` |
| `POST /api/maintenance/archive-state-journals` | `runtime-evidence-archive` | `confirm_archive`, `reason` | Maintenance | Medium — archives backend state journal evidence only after confirmation; no media, queue, settings, manifest, pending publish, or pipeline mutation | `test_api_command_contracts.py` |

The dry-run routes do not write a release folder, zip, manifest, or completed manifest. `dependency-atlas` writes generated tooling artifacts under `docs/generated/dependency-atlas/` only; `dependency-atlas/open-folder` opens that backend-resolved folder only and accepts no frontend path. State journal archive writes only runtime evidence archives after confirmation. These maintenance routes do not touch media, queue, settings, manifests, pending publish state, or pipeline state. `release-build` requires `confirm_create: true`, is blocked while active work is present, and writes deployment artifacts only through the backend release builder.

### Metrics Commands (2 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/metrics/sources` | `metrics-state-write` | `action`, `path`, `source_id`, `label`, `enabled` | Metrics | Medium — writes Metrics source registry state under `State\Metrics` only | `test_metrics_feature.py`, `test_api_command_contracts.py` |
| `POST /api/metrics/backfill` | `metrics-backfill-state-write` | `scope`, `source_id`, `path`, `max_sidecars` | Metrics | Medium — recursively reads configured sidecar roots and writes Metrics cache/status under `State\Metrics`; no media or sidecar mutation | `test_metrics_feature.py`, `test_api_command_contracts.py` |

Metrics source and backfill commands are backend-owned. Source registry updates write only Metrics state, and backfill recursively reads `*.pipeline.json` sidecars under configured source roots while skipping symlinked folders. It does not rewrite sidecars, launch work, drain, publish, rename, mutate queue state, or touch source/output media files.

### Audit Source Commands (2 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/audit/sources` | `audit-source-state-write` | `action`, `path`, `source_id`, `label`, `enabled` | Reports | Medium — writes the Reports audit source registry under `State\Audit` only | `test_audit_sources.py`, `test_api_command_contracts.py`, `test_webview_browser_maintenance_reports_smoke.py` |
| `POST /api/audit/sources/scan` | `audit-source-scan-state-write` | `scope`, `source_id`, `source_ids`, `path`, `max_entries` | Reports | Medium — recursively counts media, sidecar, and folder totals for selected audit roots and writes aggregate scan evidence under `State\Audit`; no media or sidecar mutation | `test_audit_sources.py`, `test_api_command_contracts.py`, `test_webview_browser_maintenance_reports_smoke.py` |

Audit source commands are backend-owned. Source updates write only the Reports audit source registry. Scans recursively read selected source folders, count aggregate media/sidecar/folder metrics, skip symlinked folders, and refresh audit-source scan status files without rewriting sidecars, launching audit work, changing queue state, or touching media files.

### Rename Commands (5 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/rename/preview` | `none` | `paths`, `mode`, `show_name`, `season`, `start_episode`, `movie_title`, `movie_year` | Rename | None — media-only predictions; optional `input_counts` reports raw/media/ignored sidecar scope | `test_facade_rename_policy.py`, `test_service_rename_preview.py` |
| `POST /api/rename/browse` | `shell-dialog` | `selection_mode` (`files`, `folder`, `folder_files`), `initial_path`, `paths` | Rename | Low — opens native Windows file/folder browser or resolves already-known dropped paths; `folder_files` filters sidecars/non-media and reports optional ignored counts | `test_application_facade_local_api_rename.py`, `test_api_path_dialogs.py`, `test_webview_browser_rename_smoke.py` |
| `POST /api/rename/filter-cases` | `test-fixture-write` | `kind`, `source_folder`, `source_file`, `expected_name`, `expected_show`, `expected_movie_title`, `expected_year`, `status`, `confirm_append` | Rename | Low — appends to rename regression fixture only | `test_rename_workbench.py`, `test_rename_bad_case_corpus.py`, `test_api_command_contracts.py`, `test_webview_rename_readiness_smoke.py` |
| `POST /api/rename/apply` | `filesystem-mutation` | `paths`, `selected_sources`, `confirm_apply`, `allow_outside_configured_roots` | Rename | **High** — renames files on disk | `test_application_facade_rename.py`, `test_service_rename_apply.py` |
| `POST /api/rename/undo` | `filesystem-mutation` | `undo_manifest`, `confirm_undo` | Rename | **High** — reverses a backend-owned rename undo manifest under the resolved undo root | `test_application_facade_local_api_rename.py`, `test_service_rename_apply_runner.py`, `test_api_command_contracts.py` |

`rename/browse` is a non-mutating path-selection helper: the backend opens the Windows file/folder browser or resolves already-known dropped paths and returns media paths for staging. In `folder_files` mode it returns only media-extension paths and reports `raw_path_count`, `ignored_path_count`, and `ignored_sidecar_count` when sidecars or other non-media files are present. It does not preview, apply, rename, move, delete, or touch media files. `GET /api/rename/clean-filename-preview` also powers the Settings rename filter case workbench comparison and suggestion payload; suggestion rows distinguish already-covered terms from stage-recommended new terms, destination choices are scoped to the selected media type, and the route remains read-only and stages nothing by itself. `rename/filter-cases` appends only `tv_auto` or `movie_auto` cases to `tests/fixtures/rename/bad_rename_cases.jsonl` after `confirm_append: true`; it does not inspect or mutate media files. `rename/apply` requires `confirm_apply: true`; `rename/undo` requires `confirm_undo: true` and a backend-owned undo manifest under the resolved undo root. Backend rebuilds the rename plan from its own state, not from the frontend-submitted plan, and preview/apply canonicalize staged input to media rows before sidecar companion moves are planned. If selected paths are outside backend-injected configured media roots, the backend also requires `allow_outside_configured_roots: true` after explicit operator review.

### Settings Commands (21 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/settings/validate` | `none` | `values` | Settings | None — validation only | `test_facade_settings_policy.py`, `test_service_config_validation.py`, `test_application_facade_settings_workspace.py` |
| `POST /api/settings/browse-path` | `shell-dialog` | `setting_key`, `selection_mode`, `initial_path` | Settings | Low — backend-owned native Windows folder browser for allowlisted path fields only | `test_application_facade_local_api_workflow.py`, `test_api_path_dialogs.py`, `test_webview_frontend_mutation_boundary.py` |
| `POST /api/settings/preview-patch` | `none` | `changes`, `remove_keys`, `library_profile_resets` | Settings; Network Worker Mode Settings delegates through Settings view | None — returns redacted diff | `test_facade_settings_patch_policy.py`, `test_service_config_preview.py` |
| `POST /api/settings/pipeline-plan-preview` | `none` | `source_media`, `changes`, `remove_keys` | Settings | None — validates supplied source facts and returns a backend-owned dry-run pipeline plan only | `test_settings_pipeline_plan_preview.py` |
| `POST /api/settings/preset-library/validate` | `none` | `preset_v2` | Settings | None — validates inline PresetV2 only | `test_preset_library.py`, `test_api_command_contracts.py` |
| `POST /api/settings/preset-library/compare` | `none` | `left_id`, `right_id`, `left_preset_v2`, `right_preset_v2` | Settings | None — compares PresetV2 records or inline presets through backend patch projection only | `test_preset_library.py`, `test_api_command_contracts.py` |
| `POST /api/settings/preset-library/import-preview` | `none` | `records` | Settings | None — validates import candidates and reports State JSON target only | `test_preset_library.py`, `test_api_command_contracts.py` |
| `POST /api/settings/preset-library/save` | `preset-library-state-write` | `id`, `name`, `description`, `tags`, `source`, `imported_from`, `preset_v2`, `confirm_save` | Settings | Low — writes backend PresetV2 library JSON under State/PresetLibrary only; does not save active config | `test_preset_library.py`, `test_api_command_contracts.py` |
| `POST /api/settings/preset-library/export` | `none` | `id`, `preset_v2` | Settings | None — returns a preset export payload only | `test_preset_library.py`, `test_api_command_contracts.py` |
| `POST /api/settings/preset-library/apply-preview` | `none` | `id`, `preset_v2` | Settings | None — converts PresetV2 to a legacy settings patch and previews through existing settings policy only | `test_preset_library.py`, `test_api_command_contracts.py` |
| `POST /api/settings/preset-library/apply` | `config-write` | `id`, `preset_v2`, `confirm_apply` | Settings | **High** — converts PresetV2 to a legacy settings patch and saves through the existing backend settings save path for future launches | `test_preset_library.py`, `test_api_command_contracts.py` |
| `POST /api/settings/save-patch` | `config-write` | `changes`, `remove_keys`, `library_profile_resets`, `review_confirmation`, `confirm_save` | Settings; Network Worker Mode Settings delegates through Settings view | **High** — writes JSON settings authority and generated PSD1 projection together; save requires `confirm_save: true` plus `review_confirmation` from the matching backend preview | `test_facade_settings_patch_policy.py`, `test_application_facade_settings_patch.py`, `test_settings_store.py`, `test_service_config_save_runner.py` |
| `POST /api/settings/import-psd1-preview` | `none` | *(none)* | Settings | None — previews explicit PSD1 recovery import into JSON authority without writing | `test_api_command_contracts.py`, `test_settings_store.py` |
| `POST /api/settings/import-psd1` | `config-write` | `confirm_import` | Settings | **High** — imports active PSD1 into JSON authority, preserves legacy extras inertly, and regenerates PSD1 projection | `test_api_command_contracts.py`, `test_settings_store.py` |
| `POST /api/settings/wizard/validate-paths` | `none` | `wizard` | Settings Wizard | None — validation only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/validate-tools` | `none` | `wizard` | Settings Wizard | None — validation only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/probe-hardware` | `none` | `wizard` | Settings Wizard | None — bounded probe evidence only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/validate-workers` | `none` | `wizard` | Settings Wizard | None — validation only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/preview` | `none` | `wizard` | Settings Wizard | None — preview only | `test_api_command_contracts.py` |
| `POST /api/settings/wizard/save` | `config-write` | `wizard`, `confirm_save` | Settings Wizard | **High** — writes PSD1 config through the normal backend save path | `test_api_command_contracts.py` |
| `POST /api/settings/reload` | `none` | *(none)* | Settings | None — reloads cached state | `test_facade_settings_policy.py` |

`browse-path` opens only the backend-owned Windows folder browser for allowlisted Settings path fields (`SourceMovies`, `SourceTV`, `Outsource`, `LocalBase`, `FinalLibraryPromotionRuleSourceRoot`, `FinalLibraryPromotionRuleDestinationRoot`) and returns selected-folder validation evidence for WebView staging. It does not save settings, launch work, rewrite queue state, or touch media files. Preset library save writes `State/PresetLibrary/presets.json` only; preset apply uses the existing settings preview/save policy and affects future launches only. Settings Wizard validation/preview routes share the same backend policy without writing config. `settings/wizard/save`, `save-patch`, explicit `import-psd1`, and preset apply require confirmation; backend backs up current config before writing. Frontend cannot write the JSON settings store or generated PSD1 projection directly. The Network page's Worker Mode Settings panel uses the same Settings preview/save routes for config only; it does not create Network lifecycle command routes or start/stop coordinator or worker runtime.

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
| `POST /api/audit/score-policy` | `audit-state-write` | `policy`, `reset` | Reports | Medium — writes backend-owned audit score policy only | `test_application_facade_local_api_http.py` |
| `POST /api/audit/ignore` | `audit-state-write` | `action`, `row_keys`, `paths`, `reason`, `priority_only`, `limit` | Reports | Medium — writes audit-only ignore state without queue holds or media mutation | `test_application_facade_local_api_http.py` |
| `POST /api/audit/export-rerun-csv` | `report-file-write` | `row_keys`, `priority_only`, `limit` | Reports | Medium — writes a backend-owned rerun CSV artifact only; does not launch rerun work | `test_application_facade_local_api_http.py` |

Audit control commands are backend-owned report/state helpers. They do not
write queue priority, apply holds, launch rerun work, change settings, or touch
media files.

### Network Commands (12 routes)

| Route | Effect | Key Request Keys / Allowed Values | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/network/coordinator/start-dry-run` | `none` | `reason` | Network | None — lifecycle dry-run only; reports coordinator preconditions, active-work posture, state-file posture, and `would_not_touch` evidence | `test_application_facade_process_launch.py`, `test_api_contract_payload.py`, `test_api_command_contracts.py` |
| `POST /api/network/coordinator/stop-dry-run` | `none` | `reason` | Network | None — lifecycle dry-run only; reports stop preconditions and state preservation evidence without releasing claims | `test_api_contract_payload.py`, `test_api_command_contracts.py` |
| `POST /api/network/worker/start-dry-run` | `none` | `reason` | Network | None — lifecycle dry-run only; reports coordinator URL/path-map/pending-done posture without claiming, scanning, or launching work | `test_api_contract_payload.py`, `test_api_command_contracts.py` |
| `POST /api/network/worker/stop-dry-run` | `none` | `reason` | Network | None — lifecycle dry-run only; reports worker stop and pending done posture without aborting active work or deleting scratch files | `test_api_contract_payload.py`, `test_api_command_contracts.py` |
| `POST /api/network/worker/test-connection` | `none` | `timeout_seconds` | Network | None — read-only worker TCP/auth/path preflight; does not claim work, start lifecycle, scan queue, save settings, publish, drain, or touch media files | `test_network_test_connection.py`, `test_api_contract_payload.py`, `test_api_command_contracts.py`, `test_webview_network_read_only_boundary.py` |
| `POST /api/network/worker/discover-coordinators` | `none` | `timeout_seconds` | Network | None — read-only mDNS coordinator discovery; selecting a result only stages `WorkerCoordinatorUrl` in the Settings patch until preview/save | `test_network_mdns.py`, `test_api_contract_payload.py`, `test_api_command_contracts.py`, `test_webview_network_read_only_boundary.py` |
| `POST /api/network/coordinator/join-blob` | `secret-transfer` | `coordinator_url`, `confirm_create`, `rotate_token`, `confirm_rotate` | Network | High — returns an unjournaled join blob containing the worker auth secret; does not start lifecycle, claim work, launch processing, publish, drain, or touch media files | `test_network_join.py`, `test_api_contract_payload.py`, `test_api_command_contracts.py`, `test_webview_network_read_only_boundary.py` |
| `POST /api/network/worker/join-cluster` | `config-write` | `join_blob`, `confirm_import`, `timeout_seconds` | Network | High — imports a join blob through backend settings save, seeds worker URL/token/path-map settings, then runs read-only test-connection | `test_network_join.py`, `test_api_contract_payload.py`, `test_api_command_contracts.py`, `test_webview_network_read_only_boundary.py` |
| `POST /api/network/coordinator/start` | `backend-lifecycle` | `confirm_start`, `reason` | Network | **High** — starts only the real coordinator lifecycle provider after confirmation and preconditions; provider unavailable fails closed | `test_application_facade_process_launch.py`, `test_api_contract_payload.py`, `test_api_command_contracts.py` |
| `POST /api/network/coordinator/stop` | `backend-lifecycle` | `confirm_stop`, `reason` | Network | **High** — stops only the coordinator lifecycle provider while preserving `coordinator_inflight.json`, `worker_state.json`, and `cluster.log` | `test_api_contract_payload.py`, `test_api_command_contracts.py` |
| `POST /api/network/worker/start` | `backend-lifecycle` | `confirm_start`, `reason` | Network | **High** — starts only the real worker polling lifecycle provider; worker must claim coordinator-assigned work one file at a time and must not scan local queue | `test_api_contract_payload.py`, `test_api_command_contracts.py` |
| `POST /api/network/worker/stop` | `backend-lifecycle` | `confirm_stop`, `reason` | Network | **High** — requests worker lifecycle stop while preserving pending done reports and `worker_state.json`; abort/partial cleanup remains separate | `test_api_contract_payload.py`, `test_api_command_contracts.py` |

Network lifecycle dry-runs, worker test-connection, and mDNS discovery are no-mutation evidence/setup routes. Confirmed start/stop routes require confirmation fields and backend provider preconditions. They do not use normal Launch, do not scan the full queue, do not silently release claims, and do not mutate source media. If the provider hook is unavailable, the route returns a blocked command result rather than starting a fake local run.

### Process Commands (8 routes)

| Route | Effect | Key Request Keys / Allowed Values | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/pipeline/control` | `control-flag-write` | `action`: `pause`, `stop`, `rescan`, `kill` | Launch | Medium — writes control flags or runs backend-owned emergency process cleanup for `kill` | `test_facade_process_control_policy.py`, `test_application_facade_process_control.py`, `test_service_process_control_flags.py` |
| `POST /api/pipeline/browse-file` | `shell-dialog` | `selection_mode`: `files`; `initial_path` | Launch | Low — opens backend-owned native Windows file browser for single-file staging only; does not save config or launch work | `test_application_facade_local_api_workflow.py`, `test_webview_frontend_mutation_boundary.py` |
| `POST /api/pipeline/start` | `process-launch` | `mode`: `once`/`continuous`/`validate`/`drain_pending_pushes`; `schedule_override`: `""`/`run_once`/`ignore` | Launch | **High** — spawns pipeline process | `test_facade_process_pipeline_policy.py`, `test_application_facade_process_launch.py`, `test_facade_process_guard_policy.py` |
| `POST /api/audit/start` | `process-launch` | `library_root`, `library_roots`, `source_ids`, `include_sidecars`, `show_console` | Launch, Reports | **High** — spawns audit process for one or more selected audit source locations | `test_facade_process_audit_policy.py`, `test_application_facade_process_launch.py`, `test_webview_browser_maintenance_reports_smoke.py` |
| `POST /api/audit/stop` | `process-control` | `confirm_stop`, `reason` | Reports | **High** — explicit backend-owned audit-only process cleanup and terminal audit progress write | `test_application_facade_process_launch.py`, `test_webview_browser_maintenance_reports_smoke.py` |
| `POST /api/rerun/preview` | `read-only-preview` | `csv_path`, `execution_mode`, `destination_mode`, `original_policy`, `collision_policy`, `window_size`, confirmations, `scope` filters | Launch | None — parses and summarizes rerun CSV rows, import/scoped CSV candidates, lifecycle warnings, filter options, tiles, and scoped counts without launching or touching media files | `test_rerun_csv_preview.py`, `test_api_contract_payload.py`, `test_api_command_contracts.py` |
| `POST /api/rerun/start` | `process-launch` | `csv_path`, `dry_run`, `plan_only`, `execution_mode`, `destination_mode`, `original_policy`, `collision_policy`, `window_size`, confirmations, `scope` filters | Launch | **High** — spawns backend-owned CSV rerun v2; default execution is one-at-a-time, scoped starts write under `State\Rerun\ScopedCsv`, final replacement requires strict confirmation, and original source policies are rejected | `test_facade_process_rerun_policy.py`, `test_application_facade_process_launch.py`, `test_rerun_csv_preview.py` |
| `POST /api/rerun/open` | `shell-open` | `target`, `row_key`, `csv_key` | Launch | Low — opens only backend-derived rerun review outputs, manifests, import/scoped CSVs, or folders; arbitrary filesystem paths are rejected | `test_api_contract_payload.py` |
| `POST /api/rerun/promote-dry-run` | `read-only-preview` | `row_key` | Launch | None — computes dry-run evidence for promoting an existing rerun review output into Pending Publish without moving files or writing manifests | `test_api_contract_payload.py` |
| `POST /api/rerun/promote` | `pending-manifest-write` | `row_key`, `dry_run_fingerprint`, `confirm_promote` | Launch | Medium — after matching dry-run evidence and strict confirmation, writes a `pending_move` manifest, moves an existing rerun review output into Pending Publish, updates the manifest to `parked`, and preserves known sidecar evidence; it does not directly publish or touch source media | `test_api_contract_payload.py`, `test_process_rerun_results.py` |
| `POST /api/backend/shutdown` | `backend-lifecycle` | `reason`, `force_active_work_shutdown` | Tauri shell (close flow) | **Critical** — initiates shutdown only when close-readiness is safe, unless literal boolean `true` force cleanup is requested | `test_tauri_shell_scaffold.py`, `test_local_api_lifecycle_contract_smoke.py` |

`rerun/preview` is no-write and drives auto-preview for the Review & Start CSV Rerun flow. `rerun/start` media-safe defaults are `execution_mode: one_at_a_time`, `destination_mode: review_workspace`, `original_policy: keep`, `collision_policy: suffix`, `enabled_only: true`; legacy `stage_mode`/`original_mode`/`return_mode` aliases are compatibility inputs only. Source rename/move/delete policies are rejected for CSV rerun, and final replacement remains strict-confirmation gated. Pending-publish rerun output is parked with a `pending_move` manifest before media movement, then marked `parked` after the move. Scope filters may narrow live starts by writing a backend-owned scoped CSV under `State\Rerun\ScopedCsv`. `backend/shutdown` must be preceded by `GET /api/backend/close-readiness`; unsafe close-readiness returns an error unless `force_active_work_shutdown` is literal JSON boolean `true`.

---

## Effect Class Summary

| Effect | Count | Routes |
|---|---|---|
| `none` (read-only) | 83 | All non-probing GET routes + preview/validate/reload POSTs + repair/reconcile dry-runs + startup reconcile dry-run + maintenance retention dry-run + preset library preview/export routes + Network lifecycle dry-runs + worker test-connection/discovery |
| `bounded-health-check` | 1 | `GET /api/maintenance` |
| `read-only-preview` | 7 | `POST /api/queue/file-overrides/route-preview`, `POST /api/queue/file-overrides/series-preview`, `POST /api/queue/file-overrides/series-clear-preview`, `POST /api/queue/file-overrides/folder-preview`, `POST /api/subtitle-qa/preview`, `POST /api/rerun/preview`, `POST /api/rerun/promote-dry-run` |
| `shell-open` | 8 | `POST /api/queue/open`, `completed/open`, `pending-publish/open`, `diagnostics/open`, `diagnostics/tdarr-matrix/evidence/open`, `failures/open`, `maintenance/dependency-atlas/open-folder`, `rerun/open` |
| `shell-dialog` | 4 | `POST /api/rename/browse`, `POST /api/settings/browse-path`, `POST /api/path-picker/browse`, `POST /api/pipeline/browse-file` |
| `test-fixture-write` | 1 | `POST /api/rename/filter-cases` |
| `diagnostic-process` | 2 | `POST /api/diagnostics/tdarr-matrix-audit`, `POST /api/diagnostics/tdarr-matrix/rerun` |
| `diagnostics-artifact-write` | 1 | `POST /api/maintenance/support-export` |
| `runtime-evidence-archive` | 1 | `POST /api/maintenance/archive-state-journals` |
| `ui-state-write` | 1 | `POST /api/ui-preferences` |
| `metrics-state-write` | 1 | `POST /api/metrics/sources` |
| `metrics-backfill-state-write` | 1 | `POST /api/metrics/backfill` |
| `audit-source-state-write` | 1 | `POST /api/audit/sources` |
| `audit-source-scan-state-write` | 1 | `POST /api/audit/sources/scan` |
| `queue-state-write` | 7 | `POST /api/queue/priority`, `queue/strategy`, `queue/file-overrides`, `queue/file-overrides/series-apply`, `queue/file-overrides/series-clear-apply`, `queue/file-overrides/remux-pilot-promote`, `queue/file-overrides/folder-rule` |
| `failure-marker-write` | 1 | `POST /api/failures/clear` |
| `failure-evidence-archive` | 1 | `POST /api/failures/archive-evidence` |
| `failure-artifact-delete` | 1 | `POST /api/failures/artifacts/cleanup` |
| `failure-resolution-journal-write` | 1 | `POST /api/failures/lifecycle` |
| `audit-state-write` | 2 | `POST /api/audit/score-policy`, `audit/ignore` |
| `report-file-write` | 1 | `POST /api/audit/export-rerun-csv` |
| `process-dry-run` | 3 | `POST /api/queue/scan`, `maintenance/release-dry-run`, `maintenance/completed-backfill-dry-run` |
| `tooling-artifact-write` | 1 | `POST /api/maintenance/dependency-atlas` |
| `deployment-write` | 1 | `POST /api/maintenance/release-build` |
| `control-state-write` | 2 | `POST /api/final-library-promotion/pause`, `final-library-promotion/resume` |
| `control-flag-write` | 1 | `POST /api/pipeline/control` |
| `process-control` | 1 | `POST /api/audit/stop` |
| `validation-log-write` | 1 | `POST /api/sample-validation/append` |
| `app-state-write` | 1 | `POST /api/schedule/save` |
| `secret-transfer` | 1 | `POST /api/network/coordinator/join-blob` |
| `preset-library-state-write` | 1 | `POST /api/settings/preset-library/save` |
| `config-write` | 5 | `POST /api/settings/save-patch`, `settings/import-psd1`, `settings/preset-library/apply`, `settings/wizard/save`, `network/worker/join-cluster` |
| `completed-manifest-write` | 1 | `POST /api/completed/reconcile-manifest` |
| `completed-sidecar-json-write` | 1 | `POST /api/completed/repair-sidecar-metadata` |
| `pending-manifest-write` | 2 | `POST /api/pending-publish/repair-manifest`, `POST /api/rerun/promote` |
| `pending-orphan-manifest-write` | 1 | `POST /api/pending-publish/reconcile-orphan-payloads` |
| `filesystem-mutation` | 3 | `POST /api/rename/apply`, `POST /api/rename/undo`, `final-library-promotion/promote-queue` |
| `process-launch` | 3 | `POST /api/pipeline/start`, `audit/start`, `rerun/start` |
| `backend-lifecycle` | 5 | `POST /api/backend/shutdown`, `POST /api/network/coordinator/start`, `POST /api/network/coordinator/stop`, `POST /api/network/worker/start`, `POST /api/network/worker/stop` |

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
| `Test-LocalApiRepairReconcileDryRunContractSmoke.ps1` | Browser-free repair/reconcile route contract smoke for strict request fields, required dry-run schema fields, command-journal suppression, WebView boundary, and unchanged temp manifest/sidecar/payload/output/source bytes |

Routes with no dedicated smoke coverage: `GET /api/telemetry` is covered by `Test-WebViewBrowserTelemetrySmoke.ps1` through the Live page rather than by a route-only smoke. `GET /api/failures`, `GET /api/failures/artifacts`, and `GET /api/audit-results` are covered through route/static tests and the browser-backed Maintenance/Reports smoke. `GET /api/maintenance/change-ledger` is covered by route/unit tests plus the browser-backed Maintenance Change Ledger smoke. `GET /api/maintenance/productization` and `POST /api/maintenance/support-export` are covered by focused productization route and redaction unit tests.

---

## See Also

- Route ownership map: `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Command matrix: `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- Mutation boundary matrix: `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Diagnostics target allowlist: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Test coverage matrix: `docs/testing/TEST_COVERAGE_MATRIX.md`
