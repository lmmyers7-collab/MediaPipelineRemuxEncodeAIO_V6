# API Route Inventory

Date: 2026-05-20

Full inventory of all Local API routes: route, method, effect class, backend contract/handler, mutation risk, primary frontend caller, and test coverage. Source: `contract_read.py`, `contract_command.py`, `routes_read.py`, `routes_command.py`.

Total: 53 routes — 25 GET (read) + 28 POST (command).

All routes require the bootstrap token (`X-Desktop-Token`) except `GET /api/health`.

---

## GET Routes (Read — 25 routes)

All GET routes return data only. None launch pipeline work, write config, drain pending outputs, rename files, or mutate queue or manifest state.

### Status Group (10 routes)

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
| `GET /api/launch/preflight` | `none` | `desktop_launch_preflight.v1` + nested `desktop_launch_readiness.v1` | Launch | Yes | `test_service_process_readiness.py`, `test_facade_process_pipeline_policy.py`, `test_application_facade_process_launch.py`, `test_application_facade_local_api.py` |
| `GET /api/commands` | `none` | `desktop_command_history.v1` | Diagnostics, Home | Yes | `test_api_command_journal_policy.py`, `test_application_facade_local_api.py` |

Query params: `/api/diagnostics/tail` accepts `target` (allowlisted key) and `max_bytes` (1 KB–256 KB); backend tail evidence includes `evidence_authority=backend`, and any WebView fallback over older/no-evidence payloads must be labelled frontend advisory only. `/api/launch/preflight` accepts target-specific read-only start-intent fields and returns nested backend `operator_readiness` (`desktop_launch_readiness.v1`) so Launch readiness rendering does not have to infer start posture from DOM state. `/api/commands` accepts `limit`. `/api/failures` accepts `source` and `limit`. `/api/queue/file-overrides` accepts optional `path` and validates it under `SourceMovies`/`SourceTV`.

### Inventory Group (9 routes)

| Route | Effect | Response Schema | Frontend Caller | Auth | Backend Test Coverage |
|---|---|---|---|---|---|
| `GET /api/queue` | `none` | `desktop_queue_preview.v1` | Queue | Yes | `test_facade_queue_policy.py`, `test_service_queue_preview_builder.py` |
| `GET /api/queue/priority` | `none` | `queue_priority_manifest.v1` | Queue | Yes | `test_application_facade_local_api.py` |
| `GET /api/queue/strategy` | `none` | `queue_strategy_state.v1` | Queue | Yes | `test_application_facade_local_api.py` |
| `GET /api/queue/file-overrides` | `none` | `queue_file_overrides.v1` | Queue | Yes | `test_application_facade_local_api.py` |
| `GET /api/completed` | `none` | `desktop_completed_preview.v1` | Completed | Yes | `test_facade_completed_policy.py`, `test_service_completed_manifest.py` |
| `GET /api/failures` | `none` | `desktop_failure_preview.v1` | Reports, Diagnostics | Yes | `test_facade_failures_policy.py`, `test_service_failure_markers.py` |
| `GET /api/audit-results` | `none` | `desktop_audit_preview.v1` | Reports | Yes | `test_facade_audit_policy.py`, `test_service_audit_rerun_records.py` |
| `GET /api/pending-publish` | `none` | `desktop_pending_publish_preview.v1` | Pending Publish | Yes | `test_facade_pending_publish_policy.py`, `test_service_pending_publish_manifest.py` |
| `GET /api/publish-reconciliation` | `none` | `desktop_publish_reconciliation.v1` | Completed | Yes | `test_facade_completed_policy.py` |

`/api/publish-reconciliation` performs a read-only correlation of Completed rows, current Pending Publish rows, and the latest durable pending drain summary. No repair, drain, or publish action is triggered.

Repair/reconcile mutation remains design-only. `/api/contract` publishes the future dry-run, rollback, source-file, and route-exposure gates, but there are no repair/reconcile POST routes in this inventory and no WebView controls may call one until `Docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md` is satisfied.

Network lifecycle mutation remains design-only. `/api/contract` publishes the future dry-run, process cleanup/rollback, source-file, and route-exposure gates for coordinator/worker lifecycle commands, but there are no Network start/stop/reclaim/release/worker-polling POST routes in this inventory and no WebView controls may call one until `Docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` is satisfied.

### Workspace Group (6 routes)

| Route | Effect | Response Schema | Frontend Caller | Auth | Backend Test Coverage |
|---|---|---|---|---|---|
| `GET /api/maintenance` | `bounded-health-check` | `desktop_maintenance_workspace.v1` | Maintenance | Yes | `test_facade_maintenance_policy.py`, `test_application_facade_maintenance.py` |
| `GET /api/maintenance/progress` | `none` | `desktop_maintenance_health_progress.v1` | Maintenance | Yes | `test_application_facade_maintenance.py` |
| `GET /api/schedule` | `none` | `desktop_schedule_workspace.v1` | Schedule | Yes | `test_facade_schedule_policy.py`, `test_application_facade_schedule.py` |
| `GET /api/settings/workspace` | `none` | `desktop_settings_workspace.v1` | Settings | Yes | `test_facade_settings_policy.py`, `test_application_facade_settings_workspace.py` |
| `GET /api/network/workers` | `none` | `desktop_network_workers.v1` | Network | Yes | `test_network_view_source_policy.py`, `test_application_facade_network.py` |
| `GET /api/sample-validation` | `none` | `desktop_sample_validation_log.v1` + readiness + reconciliation + pilot plan/checkpoints + execution checklist + generated worksheet runs | Home (Validation Log) | Yes | `test_sample_validation_api.py` |

`GET /api/maintenance` runs bounded environment and tool health probes. It does not repair, install, modify, or remove anything. Effect is `bounded-health-check` to distinguish it from pure data reads.

---

## POST Routes (Command — 28 routes)

All POST routes require auth. File-open routes pass row keys or allowlisted target keys. Queue state routes accept only absolute paths under backend-configured `SourceMovies`/`SourceTV` roots and write non-destructive state manifests.

### Queue State Commands (3 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/queue/priority` | `queue-state-write` | `path`, `level`, `reason`, `items`; levels `high`/`normal`/`low`/`hold` | Queue | Medium — writes non-destructive priority manifest only | `test_application_facade_local_api.py` |
| `POST /api/queue/strategy` | `queue-state-write` | `strategy` | Queue | Medium — writes queue strategy state only | `test_application_facade_local_api.py` |
| `POST /api/queue/file-overrides` | `queue-state-write` | `path`, `audio`, `subtitles`, `clear`, `clear_all` | Queue | Medium — writes non-destructive file override manifest only | `test_application_facade_local_api.py` |

Priority and file override path writes are rejected unless the submitted path is absolute and under `SourceMovies` or `SourceTV`. These routes do not rename, move, delete, launch, process, or mutate source media.

### Failure Marker Commands (1 route)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/failures/clear` | `failure-marker-write` | `scope`, `marker_path`, `marker_paths`, `source_json`, `dry_run`, `confirm_clear` | Reports | Medium — moves failure marker JSON out of the active marker folder only | `test_service_failure_markers.py`, `test_webview_frontend_mutation_boundary.py` |

`failures/clear` requires `confirm_clear: true` unless `dry_run: true`. Submitted marker paths are accepted only when they resolve inside the backend failure marker folder. The command writes a clear manifest and moves marker JSON to a cleared-marker archive; it does not delete media, reports, completed manifests, pending publish state, or source/output files.

### File Open Commands (4 routes)

| Route | Effect | Allowed Targets | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/queue/open` | `shell-open` | `source_file`, `source_folder`, `source_root` | Queue | Low — OS open only | `test_facade_queue_policy.py`, `test_service_file_open.py` |
| `POST /api/completed/open` | `shell-open` | `output_folder`, `sidecar`, `source_folder` | Completed | Low | `test_facade_completed_open_policy.py`, `test_service_file_open.py` |
| `POST /api/pending-publish/open` | `shell-open` | `local_file`, `manifest`, `destination_folder`, `source_folder` | Pending Publish | Low | `test_facade_pending_publish_policy.py`, `test_service_file_open.py` |
| `POST /api/pending-publish/recovery-plan` | `none` | `scope` (`all`/`selected`), `row_key` | Pending Publish | None — dry-run plan only | `test_facade_pending_publish_policy.py` |

`recovery-plan` builds a backend-authored dry-run plan and returns it. No files are drained, moved, deleted, or published.

### Diagnostics Open Command (1 route)

| Route | Effect | Allowed Targets | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/diagnostics/open` | `shell-open` | 20 allowlisted target keys (see below) | Diagnostics, all pages | Low — OS open only | `test_facade_diagnostics_open_policy.py` |

Allowlisted targets (20): `run_logs`, `cluster_log`, `config`, `config_folder`, `workspace`, `state`, `pending_publish`, `failed_reports`, `failed_markers`, `audit_reports`, `queue_snapshot`, `active_jobs`, `completed_manifest`, `latest_failure_report`, `latest_failure_json`, `latest_audit_csv`, `latest_priority_csv`, `last_stdout_log`, `last_stderr_log`, `sample_validation_log`.

Full target catalog: `Docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`.

### Maintenance Commands (3 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/maintenance/release-dry-run` | `process-dry-run` | `destination_root`, `zip_package`, `verify`, `include_tests` | Maintenance | None — `-DryRun` only | `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` |
| `POST /api/maintenance/release-build` | `deployment-write` | `destination_root`, `zip_package`, `verify`, `include_tests`, `force`, `confirm_create` | Maintenance | Medium — creates deployable release folder, manifest, and optional zip through the backend release builder; `force` may replace the destination | `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` |
| `POST /api/maintenance/completed-backfill-dry-run` | `process-dry-run` | `timeout_seconds` | Maintenance | None — `-DryRun` only | `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` |

The dry-run routes do not write a release folder, zip, manifest, or completed manifest. `release-build` requires `confirm_create: true`, is blocked while active work is present, and writes deployment artifacts only through the backend release builder.

### Rename Commands (3 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/rename/preview` | `none` | `paths`, `mode`, `show_name`, `season`, `start_episode`, `movie_title`, `movie_year` | Rename | None — predictions only | `test_facade_rename_policy.py`, `test_service_rename_preview.py` |
| `POST /api/rename/browse` | `shell-dialog` | `selection_mode`, `initial_path` | Rename | Low — opens native Windows file/folder browser only | `test_application_facade_local_api.py`, `test_api_path_dialogs.py`, `test_webview_browser_rename_smoke.py` |
| `POST /api/rename/apply` | `filesystem-mutation` | `paths`, `selected_sources`, `confirm_apply`, `allow_outside_configured_roots` | Rename | **High** — renames files on disk | `test_application_facade_rename.py`, `test_service_rename_apply.py` |

`rename/browse` is a non-mutating path-selection helper: the backend opens the Windows file/folder browser and returns operator-selected paths for staging. It does not preview, apply, rename, move, delete, or touch media files. `rename/apply` requires `confirm_apply: true`. Backend rebuilds the rename plan from its own state, not from the frontend-submitted plan. If selected paths are outside backend-injected configured media roots, the backend also requires `allow_outside_configured_roots: true` after explicit operator review.

### Settings Commands (4 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/settings/validate` | `none` | `values` | Settings | None — validation only | `test_facade_settings_policy.py`, `test_service_config_validation.py`, `test_application_facade_settings_workspace.py` |
| `POST /api/settings/preview-patch` | `none` | `changes`, `remove_keys` | Settings | None — returns redacted diff | `test_facade_settings_patch_policy.py`, `test_service_config_preview.py` |
| `POST /api/settings/save-patch` | `config-write` | `changes`, `remove_keys`, `confirm_save` | Settings | **High** — writes PSD1 config | `test_facade_settings_patch_policy.py`, `test_service_config_save_runner.py` |
| `POST /api/settings/reload` | `none` | *(none)* | Settings | None — reloads cached state | `test_facade_settings_policy.py` |

`save-patch` requires `confirm_save: true`. Backend backs up current config before writing. Frontend cannot write the PSD1 file directly.

### Schedule Commands (2 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/schedule/preview` | `none` | `enabled`, `day_windows`, `grid` | Schedule | None — validation only | `test_facade_schedule_policy.py`, `test_application_facade_schedule.py` |
| `POST /api/schedule/save` | `app-state-write` | `enabled`, `day_windows`, `grid`, `confirm_save` | Schedule | Medium — writes schedule app-state keys | `test_facade_schedule_policy.py`, `test_service_app_schedule.py`, `test_application_facade_schedule.py` |

`schedule/save` writes only `schedule_enabled` and `schedule_grid` app-state keys. It cannot launch work, alter queue state, or override schedule gates.

### Sample Validation Commands (2 routes)

| Route | Effect | Key Request Keys | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/sample-validation/preview` | `none` | `schema`, `source_path`, `output_path`, `proof_strength`, `operator_decision` | Home | None — preview only; includes read-only current-backend-evidence comparison, pilot evidence packet, and append-readiness/manual-check gap advice | `test_sample_validation_api.py`, `Test-LocalApiSampleValidationContractSmoke.ps1` |
| `POST /api/sample-validation/append` | `validation-log-write` | `schema`, `source_path`, `output_path`, `proof_strength`, `operator_decision` | Home | Low — appends to `sample_validation_log.jsonl` only; returns current-evidence, pilot evidence packet, and append-readiness advice but does not accept outputs | `test_sample_validation_api.py`, `Test-LocalApiSampleValidationContractSmoke.ps1` |

`append` does not mark jobs complete, clear failures, drain pending publish, rewrite manifests, launch work, or mutate media files.

### Process Commands (5 routes)

| Route | Effect | Key Request Keys / Allowed Values | Frontend Caller | Mutation Risk | Backend Test Coverage |
|---|---|---|---|---|---|
| `POST /api/pipeline/control` | `control-flag-write` | `action`: `pause`, `stop`, `rescan` | Launch | Medium — writes control flags | `test_facade_process_control_policy.py`, `test_application_facade_process_control.py`, `test_service_process_control_flags.py` |
| `POST /api/pipeline/start` | `process-launch` | `mode`: `once`/`continuous`/`validate`/`drain_pending_pushes`; `schedule_override`: `""`/`run_once`/`ignore` | Launch | **High** — spawns pipeline process | `test_facade_process_pipeline_policy.py`, `test_application_facade_process_launch.py`, `test_facade_process_guard_policy.py` |
| `POST /api/audit/start` | `process-launch` | `library_root`, `include_sidecars`, `show_console` | Launch, Reports | **High** — spawns audit process | `test_facade_process_audit_policy.py`, `test_application_facade_process_launch.py` |
| `POST /api/rerun/start` | `process-launch` | `csv_path`, `dry_run`, `stage_mode`, `original_mode`, `return_mode`, `show_console` | Reports | **High** — spawns rerun process | `test_facade_process_rerun_policy.py`, `test_application_facade_process_launch.py` |
| `POST /api/backend/shutdown` | `backend-lifecycle` | `reason`, `force_active_work_shutdown` | Tauri shell (close flow) | **Critical** — initiates shutdown only when close-readiness is safe, unless explicit force cleanup is requested | `test_tauri_shell_scaffold.py`, `test_local_api_lifecycle_contract_smoke.py` |

`rerun/start` media-safe defaults: `stage_mode: copy`, `original_mode: keep`, `return_mode: park`. `backend/shutdown` must be preceded by `GET /api/backend/close-readiness`; unsafe close-readiness returns an error unless `force_active_work_shutdown` is explicitly true.

---

## Effect Class Summary

| Effect | Count | Routes |
|---|---|---|
| `none` (read-only) | 31 | All non-probing GET routes + preview/validate/reload POSTs |
| `bounded-health-check` | 1 | `GET /api/maintenance` |
| `shell-open` | 4 | `POST /api/queue/open`, `completed/open`, `pending-publish/open`, `diagnostics/open` |
| `shell-dialog` | 1 | `POST /api/rename/browse` |
| `queue-state-write` | 3 | `POST /api/queue/priority`, `queue/strategy`, `queue/file-overrides` |
| `failure-marker-write` | 1 | `POST /api/failures/clear` |
| `process-dry-run` | 2 | `POST /api/maintenance/release-dry-run`, `maintenance/completed-backfill-dry-run` |
| `deployment-write` | 1 | `POST /api/maintenance/release-build` |
| `control-flag-write` | 1 | `POST /api/pipeline/control` |
| `validation-log-write` | 1 | `POST /api/sample-validation/append` |
| `app-state-write` | 1 | `POST /api/schedule/save` |
| `config-write` | 1 | `POST /api/settings/save-patch` |
| `filesystem-mutation` | 1 | `POST /api/rename/apply` |
| `process-launch` | 3 | `POST /api/pipeline/start`, `audit/start`, `rerun/start` |
| `backend-lifecycle` | 1 | `POST /api/backend/shutdown` |

---

## Test Coverage Summary

| Coverage type | Scope |
|---|---|
| `test_api_contract_payload.py` | Contract schema serialization and shape for all routes |
| `test_api_command_payloads_policy.py` | POST command payload contracts |
| `test_api_read_payloads_policy.py` | GET response payload contracts |
| `test_api_handler_policy.py` | Route handler dispatch (auth, error codes) |
| `test_api_command_journal_policy.py` | `/api/commands` journal entries |
| `test_api_http_helpers.py` | HTTP client error parsing, token headers |
| `test_contracts.py` | Data contract round-trip (all schema versions) |
| Facade tests (`test_facade_*.py`) | Business logic and parameter validation per route group |
| Service tests (`test_service_*.py`) | Underlying service behavior exercised by route handlers |
| WebView smokes (20 PS1 wrappers) | Integration rendering and mutation-boundary verification |
| `Test-LocalApiLifecycleContractSmoke.ps1` | Browser-free lifecycle route contract smoke for close-readiness/shutdown safe and watcher-blocked payloads |
| `Test-LocalApiMaintenanceDryRunContractSmoke.ps1` | Browser-free Maintenance route contract smoke for dry-run-only release/backfill POSTs, token enforcement, command history, and unchanged temp source/output bytes |
| `Test-LocalApiSampleValidationContractSmoke.ps1` | Browser-free sample-validation route contract smoke for preview/append/read/tail, token enforcement, current-backend-evidence preview, command history, and temp-only validation-log writes |

Routes with no dedicated smoke coverage: `GET /api/telemetry` is covered by `Test-WebViewBrowserTelemetrySmoke.ps1` through the Live page rather than by a route-only smoke. `GET /api/failures` and `GET /api/audit-results` are covered through the browser-backed Maintenance/Reports smoke.

---

## See Also

- Route ownership map: `Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Command matrix: `Docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- Mutation boundary review: `Docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md`
- Diagnostics target allowlist: `Docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`
- Test coverage matrix: `Docs/testing/TEST_COVERAGE_MATRIX.md`
