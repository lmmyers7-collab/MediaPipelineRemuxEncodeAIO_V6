# Local API Route Ownership Map

Documents all Local API routes, their mutation risk, auth requirements, backend owner confirmation, and primary frontend caller. Source of truth is `contract_read.py` and `contract_command.py`; handler dispatch is in `routes_read.py` and `routes_command.py`.

Total routes: 54 (25 read, 29 command).

All routes that mutate state are backend-owned. The WebView never resolves filesystem paths, selects output targets, chooses encode settings, or launches processes directly — it forwards requests with allowlisted parameters and the backend validates, plans, and executes.

---

## Read Routes (GET)

All GET routes have `"effect": "none"` unless noted. None touch media files, launch pipeline work, write config, or change queue/manifest state. `/api/maintenance` is the one exception: it runs bounded health checks (read-only tool probes) and is marked `"effect": "bounded-health-check"`.

### Status Group

| Route | Auth | Response Schema | Frontend Caller | Notes |
|---|---|---|---|---|
| `GET /api/health` | No | `desktop_backend_health.v1` | Tauri shell (startup) | No token required — used before WebView2 opens |
| `GET /api/contract` | Yes | `desktop_local_api_contract.v1` | Tauri shell (startup) | Self-describing route/command contract; Tauri validates before opening WebView2 |
| `GET /api/snapshot` | Yes | `desktop_app_snapshot.v1` | Home, all pages (refresh) | Core pipeline/audit status payload |
| `GET /api/telemetry` | Yes | `desktop_telemetry.v1` | Home, Diagnostics | CPU/RAM/GPU sample; cached by backend |
| `GET /api/diagnostics` | Yes | `desktop_diagnostics.v1` | Diagnostics, Home | Recent events, errors, launch-log summary |
| `GET /api/diagnostics/tail` | Yes | `desktop_diagnostics_tail.v1` | Diagnostics | Query params: `target` (allowlisted key only), `max_bytes` (1 KB–256 KB); backend rejects arbitrary paths; response evidence is marked `evidence_authority=backend` |
| `GET /api/diagnostics/state-summary` | Yes | `desktop_diagnostics_state_summary.v1` | Diagnostics | Bounded inline artifact summary; no arbitrary path accepted |
| `GET /api/backend/close-readiness` | Yes | `desktop_close_readiness.v1` | Tauri shell (close flow) | Backend has authority over whether it is safe to close; shell must not decide unilaterally |
| `GET /api/launch/preflight` | Yes | `desktop_launch_preflight.v1` | Launch | Backend-authored pre-launch checks; no locks reserved, no processes started |
| `GET /api/commands` | Yes | `desktop_command_history.v1` | Diagnostics, Home | Recent command journal entries; query param: `limit` |

### Inventory Group

| Route | Auth | Response Schema | Frontend Caller | Notes |
|---|---|---|---|---|
| `GET /api/queue` | Yes | `desktop_queue_preview.v1` | Queue | Latest backend queue snapshot; no dry run spawned |
| `GET /api/queue/priority` | Yes | `queue_priority_manifest.v1` | Queue | Reads non-destructive priority manifest; no queue/media mutation |
| `GET /api/queue/strategy` | Yes | `queue_strategy_state.v1` | Queue | Reads active queue strategy and valid backend strategy names |
| `GET /api/queue/file-overrides` | Yes | `queue_file_overrides.v1` | Queue | Reads override manifest or one source-root-contained override entry |
| `GET /api/completed` | Yes | `desktop_completed_preview.v1` | Completed | From local completed-jobs manifest; no output-share scan |
| `GET /api/failures` | Yes | `desktop_failure_preview.v1` | Reports, Diagnostics | Query params: `source` (`latest_json` or `markers`), `limit` |
| `GET /api/audit-results` | Yes | `desktop_audit_preview.v1` | Reports | Query params: `priority_only`, `limit`; no rerun CSV written |
| `GET /api/pending-publish` | Yes | `desktop_pending_publish_preview.v1` | Pending Publish | Reads manifests and parked payloads; does not drain |
| `GET /api/publish-reconciliation` | Yes | `desktop_publish_reconciliation.v1` | Completed | Manual read-only correlation of Completed rows, current Pending Publish rows, and the latest durable pending drain summary; no repair/drain/publish action |

### Workspace Group

| Route | Auth | Effect | Response Schema | Frontend Caller | Notes |
|---|---|---|---|---|---|
| `GET /api/maintenance` | Yes | `bounded-health-check` | `desktop_maintenance_workspace.v1` | Maintenance | Runs existing env/tool probes; does not repair or change anything |
| `GET /api/maintenance/progress` | Yes | `none` | `desktop_maintenance_health_progress.v1` | Maintenance | Reads latest maintenance progress; does not run probes |
| `GET /api/schedule` | Yes | `none` | `desktop_schedule_workspace.v1` | Schedule | Reads persisted schedule state; schedule saves use separate backend command routes |
| `GET /api/settings/workspace` | Yes | `none` | `desktop_settings_workspace.v1` | Settings | Read-only, redacted settings snapshot |
| `GET /api/network/workers` | Yes | `none` | `desktop_network_workers.v1` | Network | Coordinator/worker runtime state; no lifecycle controls |
| `GET /api/sample-validation` | Yes | `none` | `desktop_sample_validation_log.v1` + `desktop_sample_validation_readiness.v1` + `desktop_sample_validation_reconciliation.v1` + `desktop_real_media_pilot_plan.v1` + `desktop_real_media_execution_checklist.v1` + `desktop_real_media_worksheet_runs.v1` | Home (Validation Log) | Recent validation records plus backend-authored read-only validation readiness, stale-evidence reconciliation, pilot plan, operator sample-execution checklist, and generated worksheet evidence from `Docs\RealMediaValidationRuns`; query param: `limit` |

---

## Command Routes (POST)

All POST routes require auth. The frontend passes allowlisted parameter keys; the backend validates, plans, and executes. File-open routes do not accept arbitrary filesystem paths. Queue state routes accept only absolute paths under backend-configured `SourceMovies`/`SourceTV` roots.

### Queue State Commands (non-destructive state writes)

| Route | Effect | Request Keys | Allowed Values / Scope | Frontend Caller |
|---|---|---|---|---|
| `POST /api/queue/priority` | `queue-state-write` | `path`, `level`, `reason`, `items` | `level`: `high`, `normal`, `low`, `hold`; path must be under `SourceMovies`/`SourceTV` | Queue |
| `POST /api/queue/strategy` | `queue-state-write` | `strategy` | Backend `VALID_STRATEGIES` only | Queue |
| `POST /api/queue/file-overrides` | `queue-state-write` | `path`, `audio`, `subtitles`, `clear`, `clear_all` | Path writes must be under `SourceMovies`/`SourceTV`; `clear_all` clears manifest only | Queue |

Queue state commands write JSON state under `LocalBase\State`; they do not rename, move, delete, launch, process, or mutate source media.

### Failure Marker Commands (retry-blocker state only)

| Route | Effect | Request Keys | Allowed Values / Scope | Frontend Caller |
|---|---|---|---|---|
| `POST /api/failures/clear` | `failure-marker-write` | `scope`, `marker_path`, `marker_paths`, `source_json`, `dry_run`, `confirm_clear` | `scope`: `selected`, `visible`, `all_markers`; marker paths must resolve inside backend `State\Failures\Markers` | Reports |

Failure marker clear is backend-owned retry-blocker cleanup. It requires `confirm_clear` unless `dry_run` is true, writes a clear manifest, and moves marker JSON out of the active marker folder. It does not delete media files, failure reports, completed manifests, pending publish files, or source/output paths.

### File Open Commands (shell-open; no media mutation)

| Route | Effect | Request Keys | Allowed Targets | Frontend Caller |
|---|---|---|---|---|
| `POST /api/queue/open` | `shell-open` | `row_key`, `target`, `row_scope` | `source_file`, `source_folder`, `source_root` | Queue |
| `POST /api/completed/open` | `shell-open` | `row_key`, `target` | `output_folder`, `sidecar`, `source_folder` | Completed |
| `POST /api/pending-publish/open` | `shell-open` | `row_key`, `target` | `local_file`, `manifest`, `destination_folder`, `source_folder` | Pending Publish |
| `POST /api/pending-publish/recovery-plan` | `none` (dry-run) | `scope`, `row_key` | `all`, `selected` | Pending Publish |

`recovery-plan` effect is `none`: it builds a backend-authored dry-run plan and returns it. No files are drained, moved, deleted, or published.

### Diagnostics Open Command (shell-open; no media mutation)

| Route | Effect | Request Keys | Allowed Targets | Frontend Caller |
|---|---|---|---|---|
| `POST /api/diagnostics/open` | `shell-open` | `target` | 20 allowlisted keys (see below) | Diagnostics, all pages |

Allowed targets for `/api/diagnostics/open`: `run_logs`, `cluster_log`, `config`, `config_folder`, `workspace`, `state`, `pending_publish`, `failed_reports`, `failed_markers`, `audit_reports`, `queue_snapshot`, `active_jobs`, `completed_manifest`, `latest_failure_report`, `latest_failure_json`, `latest_audit_csv`, `latest_priority_csv`, `last_stdout_log`, `last_stderr_log`, `sample_validation_log`.

### Maintenance Commands (deployment package + process dry-run)

| Route | Effect | Key Request Keys | Frontend Caller |
|---|---|---|---|
| `POST /api/maintenance/release-dry-run` | `process-dry-run` | `destination_root`, `zip_package`, `verify`, `include_tests`, … | Maintenance |
| `POST /api/maintenance/release-build` | `deployment-write` | `destination_root`, `zip_package`, `verify`, `include_tests`, `force`, `confirm_create`, … | Maintenance |
| `POST /api/maintenance/completed-backfill-dry-run` | `process-dry-run` | `timeout_seconds` | Maintenance |

The dry-run routes run existing backend scripts with `-DryRun` and write no release folder, zip, manifest, or completed manifest. `release-build` requires explicit `confirm_create`, is blocked during active work, runs under the backend maintenance command lock, and writes only release deployment artifacts through the backend release builder.

### Rename Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/rename/preview` | `none` | `paths`, `mode`, `show_name`, `season`, `start_episode`, `movie_title`, `movie_year` | None — predictions only | Rename |
| `POST /api/rename/browse` | `shell-dialog` | `selection_mode`, `initial_path` | Low — native Windows file/folder browser only; no media mutation | Rename |
| `POST /api/rename/apply` | `filesystem-mutation` | `paths`, `selected_sources`, `confirm_apply`, `allow_outside_configured_roots` | **High** — filesystem rename | Rename |

`rename/browse` only opens the Windows file/folder browser and returns operator-selected paths for staging. `rename/apply` is the only rename mutation route. The backend rebuilds the rename plan independently from the submitted paths and applies only the explicitly selected source rows through the transactional rename service. `confirm_apply` must be set; the backend does not infer confirmation from prior preview calls. Paths outside backend-injected configured media roots also require `allow_outside_configured_roots: true` after explicit operator review.

### Settings Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/settings/validate` | `none` | `values` | None — validation only | Settings |
| `POST /api/settings/browse-path` | `shell-dialog` | `setting_key`, `selection_mode`, `initial_path` | Low — backend-owned native Windows folder browser for allowlisted path fields only | Settings |
| `POST /api/settings/preview-patch` | `none` | `changes`, `remove_keys` | None — returns redacted diff | Settings |
| `POST /api/settings/save-patch` | `config-write` | `changes`, `remove_keys`, `confirm_save` | **High** — writes PSD1 config | Settings |
| `POST /api/settings/reload` | `none` | *(none)* | None — reloads cached state | Settings |

`browse-path` opens only the backend-owned Windows folder browser for allowlisted Settings path fields (`SourceMovies`, `SourceTV`, `Outsource`, `LocalBase`) and returns selected-folder validation evidence for WebView staging. It does not save the PSD1, launch work, rewrite queue state, or touch media files. `save-patch` performs backup, atomic write, and backend state reload. `confirm_save` must be set. The browser smoke explicitly verifies that `save-patch` is NOT called during the staged-settings handoff test.

### Schedule Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/schedule/preview` | `none` | `enabled`, `day_windows`, `grid` | None — validation/preview only | Schedule |
| `POST /api/schedule/save` | `app-state-write` | `enabled`, `day_windows`, `grid`, `confirm_save` | Medium — writes desktop app state schedule keys | Schedule |

`schedule/preview` parses operator day-window text through the backend schedule policy and reports changed days without writing app state. `schedule/save` requires `confirm_save` and persists only `schedule_enabled` and `schedule_grid` through the backend app-state service; it cannot launch work, mutate queue state, bypass schedule gates, or touch media files.

### Sample Validation Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/sample-validation/preview` | `none` | `schema`, `source_path`, `output_path`, `proof_strength`, `operator_decision`, … | None — preview only; returns current-evidence, pilot evidence packet, and append-readiness guidance | Home (Validation Log) |
| `POST /api/sample-validation/append` | `validation-log-write` | `schema`, `source_path`, `output_path`, `proof_strength`, `operator_decision`, … | Low — appends to `sample_validation_log.jsonl` only; returns current-evidence, pilot evidence packet, and append-readiness guidance | Home (Validation Log) |

`append` must not mark jobs complete, clear failures, drain pending publish, rewrite manifests, launch work, or mutate media files. It is scoped to the operator's evidence log only.

### Process Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/pipeline/control` | `control-flag-write` | `action` (`pause`, `stop`, `rescan`) | Medium — writes control flags | Launch |
| `POST /api/pipeline/start` | `process-launch` | `mode`, `sleep_seconds`, `show_config`, `show_console`, `single_file`, `schedule_override` | **High** — spawns pipeline process | Launch |
| `POST /api/audit/start` | `process-launch` | `library_root`, `include_sidecars`, `show_console` | **High** — spawns audit process | Launch, Reports |
| `POST /api/rerun/start` | `process-launch` | `csv_path`, `dry_run`, `stage_mode`, `original_mode`, `return_mode`, `show_console` | **High** — spawns rerun process | Reports |
| `POST /api/backend/shutdown` | `backend-lifecycle` | `reason`, `force_active_work_shutdown` | **Critical** — requests graceful shutdown only after safe close-readiness unless explicit force cleanup is requested | Tauri shell (close flow) |

`pipeline/start` allowed modes: `once`, `continuous`, `validate`, `drain_pending_pushes`. `schedule_override` allowed values: `""`, `run_once`, `ignore`. `rerun/start` defaults are media-safe (`dry_run: false`, `stage_mode: copy`, `original_mode: keep`, `return_mode: park`).

---

## Mutation Risk Summary

| Effect tag | Routes | Risk level |
|---|---|---|
| `none` | 31 routes (read-only GET routes except maintenance, rename/preview, settings/validate, settings/preview-patch, settings/reload, recovery-plan, sample-validation/preview, schedule/preview) | None |
| `bounded-health-check` | `GET /api/maintenance` | Read-only probes |
| `shell-open` | `POST /api/queue/open`, `POST /api/completed/open`, `POST /api/pending-publish/open`, `POST /api/diagnostics/open` | OS open only; no file mutation |
| `shell-dialog` | `POST /api/rename/browse`, `POST /api/settings/browse-path` | Native Windows picker only; no file mutation |
| `queue-state-write` | `POST /api/queue/priority`, `POST /api/queue/strategy`, `POST /api/queue/file-overrides` | Non-destructive queue state JSON only |
| `failure-marker-write` | `POST /api/failures/clear` | Moves retry-blocker marker JSON out of the active marker folder only |
| `process-dry-run` | `POST /api/maintenance/release-dry-run`, `POST /api/maintenance/completed-backfill-dry-run` | No output written |
| `deployment-write` | `POST /api/maintenance/release-build` | Writes deployable release folder, manifest, and optional zip only |
| `control-flag-write` | `POST /api/pipeline/control` | Pause/stop/rescan signal only |
| `validation-log-write` | `POST /api/sample-validation/append` | Appends to operator evidence log only |
| `app-state-write` | `POST /api/schedule/save` | Writes desktop app schedule keys only |
| `config-write` | `POST /api/settings/save-patch` | Writes and reloads PSD1 config |
| `filesystem-mutation` | `POST /api/rename/apply` | Renames files on disk |
| `process-launch` | `POST /api/pipeline/start`, `POST /api/audit/start`, `POST /api/rerun/start` | Spawns backend processes |
| `backend-lifecycle` | `POST /api/backend/shutdown` | Initiates graceful shutdown |

---

## Auth Coverage

All routes require the bootstrap token (`X-Desktop-Token` header or equivalent) except `GET /api/health`, which is deliberately unauthenticated for Tauri shell startup probing before the token is passed to WebView2. No route exposes the auth token to the WebView or browser storage.

---

## Backend Ownership Confirmation

Every mutation route enforces backend ownership:

- **File open** (`queue/open`, `completed/open`, `pending-publish/open`): backend selects the path from its own manifest/snapshot by `row_key` and `target` key; the frontend cannot pass a raw path.
- **Rename browse** (`rename/browse`): backend opens the native Windows file/folder browser and returns operator-selected paths for staging only; preview/apply still use separate backend routes.
- **Settings path browse** (`settings/browse-path`): backend opens the native Windows folder browser for allowlisted source/output/scratch settings and returns validation evidence for staging only; Preview/Save remains the only settings persistence path.
- **Diagnostics open/tail**: frontend passes an allowlisted target key string; backend resolves the real path and rejects any key not in the allowlist.
- **Queue state writes**: backend rejects priority/file-override path writes unless the path is absolute and under configured `SourceMovies`/`SourceTV`; strategy writes are constrained to backend valid strategy names.
- **Recovery plan**: backend authors the dry-run plan; the frontend receives it read-only.
- **Deployment build**: backend owns release packaging, active-work checks, confirmation, command locking, destination replacement, manifest creation, and optional zip creation; the frontend cannot copy files, write manifests, or zip folders itself.
- **Rename apply**: backend rebuilds the rename plan from its own state; it does not execute the frontend-submitted plan as-is. `confirm_apply` is required.
- **Settings save-patch**: backend merges, validates, backs up, and atomically writes; the frontend cannot write the PSD1 directly.
- **Schedule save**: backend parses and validates day windows, requires `confirm_save`, and writes only schedule app-state keys; the frontend cannot write state JSON directly.
- **Pipeline/audit/rerun start**: backend owns the process launch, launch-lock, and command journal; the frontend cannot exec processes or bypass launch guards.
- **Shutdown**: Tauri shell issues this after `GET /api/backend/close-readiness` confirms it is safe; the backend controls the shutdown sequence.

---

## See Also

- Route handler dispatch: `DesktopApp/mediapipeline_desktop_app/api/routes_read.py`, `routes_command.py`
- Contract source: `DesktopApp/mediapipeline_desktop_app/api/contract_read.py`, `contract_command.py`
- Diagnostics target allowlist: `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Lifecycle boundary: `Docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
- Settings coverage: `Docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
