# Local API Route Ownership Map

Documents all Local API routes, their mutation risk, auth requirements, backend owner confirmation, and primary frontend caller. Source of truth is `contract_read.py` and `contract_command.py`; handler dispatch is in `routes_read.py` and `routes_command.py`.

Total routes: 161 (53 read, 108 command).

All routes that mutate state are backend-owned. The WebView never resolves filesystem paths, selects output targets, chooses encode settings, or launches processes directly — it forwards requests with allowlisted parameters and the backend validates, plans, and executes.

---

## Read Routes (GET)

All GET routes have `"effect": "none"` unless noted. None touch media files, launch pipeline work, write config, or change queue/manifest state. `/api/maintenance` is the one exception: it runs bounded health checks (read-only tool probes) and is marked `"effect": "bounded-health-check"`.

### Status Group

| Route | Auth | Response Schema | Frontend Caller | Notes |
|---|---|---|---|---|
| `GET /api/health` | No | `desktop_backend_health.v1` | Tauri shell (startup) | No token required — used before WebView2 opens |
| `GET /api/contract` | Yes | `desktop_local_api_contract.v1` | Tauri shell (startup) | Self-describing route/command contract; Tauri validates before opening WebView2 |
| `GET /api/snapshot` | Yes | `desktop_app_snapshot.v1` | Home, all pages (refresh) | Core pipeline/audit status payload plus read-only long-run reliability counters |
| `GET /api/telemetry` | Yes | `desktop_telemetry.v1` | Home, Diagnostics | CPU/RAM/GPU sample; cached by backend |
| `GET /api/diagnostics` | Yes | `desktop_diagnostics.v1` | Diagnostics, Home | Recent events, errors, launch-log summary, and backend-owned autonomy health evidence |
| `GET /api/diagnostics/tail` | Yes | `desktop_diagnostics_tail.v1` | Diagnostics | Query params: `target` (allowlisted key only), `max_bytes` (1 KB–256 KB); backend rejects arbitrary paths; response evidence is marked `evidence_authority=backend` |
| `GET /api/diagnostics/state-summary` | Yes | `desktop_diagnostics_state_summary.v1` | Diagnostics | Bounded inline artifact summary; no arbitrary path accepted |
| `GET /api/diagnostics/tdarr-matrix/latest` | Yes | `desktop_tdarr_matrix_console.v1` | Diagnostics | Query params: `run_id`, `finding_limit`; reads a selected or latest Tdarr Matrix run and evidence target keys without opening files or launching work |
| `GET /api/diagnostics/tdarr-matrix/runs` | Yes | `desktop_tdarr_matrix_runs.v1` | Diagnostics | Lists sentinel-marked Tdarr Matrix sample runs under the approved Scratch/TestLibraries/TdarrMatrixRuns root |
| `GET /api/diagnostics/tdarr-matrix/compare` | Yes | `desktop_tdarr_matrix_compare.v1` | Diagnostics | Query params: `left_run_id`, `right_run_id`, `left`, `right`; compares existing reports without opening files or launching work |
| `GET /api/backend/close-readiness` | Yes | `desktop_close_readiness.v1` | Tauri shell (close flow) | Backend has authority over whether it is safe to close; shell must not decide unilaterally |
| `GET /api/ui-preferences` | Yes | `desktop_ui_preferences.v1` | Chrome WebView, Tauri shell | Shared UI preference state for layout/theme/tab parity; no settings, queue, or media mutation |
| `GET /api/launch/preflight` | Yes | `desktop_launch_preflight.v1` | Launch | Backend-authored pre-launch checks from read-only start-intent query fields, including pipeline single-file intent, extra-argument posture, and encoder capability diagnostic evidence that may refresh when missing or stale; no locks reserved, no processes started, no media touched |
| `GET /api/commands` | Yes | `desktop_command_history.v1` | Diagnostics, Home | Recent command journal entries; query param: `limit` |
| `GET /api/rerun/results` | Yes | `desktop_rerun_results.v1` | Launch | Reads completed/current CSV rerun manifests, rerun review outputs, and backend-known import/scoped CSV candidates; no file movement or media mutation |

### Inventory Group

| Route | Auth | Response Schema | Frontend Caller | Notes |
|---|---|---|---|---|
| `GET /api/queue` | Yes | `desktop_queue_preview.v1` | Queue | Latest backend queue snapshot plus latest scan status/source inventory evidence; no dry run spawned |
| `GET /api/queue/priority` | Yes | `queue_priority_manifest.v1` | Queue | Reads non-destructive priority manifest; no queue/media mutation |
| `GET /api/queue/strategy` | Yes | `queue_strategy_state.v1` | Queue | Reads active queue strategy and valid backend strategy names |
| `GET /api/queue/file-overrides` | Yes | `queue_file_overrides.v1` | Queue | Reads override manifest or one source-root-contained override entry |
| `GET /api/queue/file-overrides/effective` | Yes | `queue_file_overrides_effective.v1` | Queue | Reads inherited/effective file override metadata for one source-root-contained path; no manifest write |
| `GET /api/queue/file-overrides/tracks` | Yes | `queue_file_override_tracks.v1` | Queue | Reads normalized track metadata for one source-root-contained path; no queue preview mutation |
| `GET /api/completed` | Yes | `desktop_completed_preview.v1` | Completed | From local completed-jobs manifest; no output-share scan |
| `GET /api/subtitle-qa/summary` | Yes | `subtitle_qa_summary.v1` | Queue, Completed | Reads backend-authored subtitle QA evidence already loaded in Queue and Completed payloads; no probing, conversion, repair, or media touch |
| `GET /api/subtitle-qa/item` | Yes | `subtitle_qa_result.v1` | Queue, Completed | Reads one Queue or Completed row's subtitle QA evidence by backend row key/source/output identity; no arbitrary path probing or mutation |
| `GET /api/metrics` | Yes | `desktop_metrics.v1` | Metrics | Backend-owned route, storage, production, and worker/coordinator metrics from completed manifest, pending publish, worker runtime, and final-library promotion evidence; no launch, drain, promote, config save, queue mutation, or media touch |
| `GET /api/final-library-promotion/status` | Yes | `desktop_final_library_promotion_status.v1` | Completed | Reads backend-owned final-library promotion readiness, run state, pause state, counts, and destinations; no copy/move/delete action |
| `GET /api/failures` | Yes | `desktop_failure_preview.v1` | Reports, Diagnostics | Query params: `source` (`latest_json` or `markers`), `limit`; includes backend-authored `resolution_summary`, `resolution_groups`, and row `evidence_details` |
| `GET /api/failures/artifacts` | Yes | `failure_artifact_summary.v1` | Home, Reports | Reads backend-resolved current and legacy failure artifact folders for size, age, largest-file, threshold, cleanup-policy, and scan-error evidence only; touches no media and performs no cleanup action |
| `GET /api/audit-results` | Yes | `desktop_audit_preview.v1` | Reports | Query params: `priority_only`, `limit`; no rerun CSV written |
| `GET /api/audit-controls` | Yes | `desktop_audit_controls.v1` | Reports | Reads audit score policy and audit-only ignore state; no save/export/media mutation |
| `GET /api/audit-sources` | Yes | `desktop_audit_sources.v1` | Reports | Reads backend-owned audit source locations and last scan metrics; no scan, launch, save, queue mutation, or media touch |
| `GET /api/rename/cleaning-filters` | Yes | `desktop_rename_cleaning_filter_catalog.v1` | Rename, Settings | Reads backend-owned movie and TV cleaning filter catalogs only |
| `GET /api/rename/movie-cleaning-filters` | Yes | `desktop_rename_movie_filter_catalog.v1` | Rename | Reads backend-owned movie filename cleaning filter catalog only |
| `GET /api/rename/clean-filename-preview` | Yes | `desktop_rename_clean_filename_preview.v1` | Rename | Read-only clean-filename preview and optional workbench comparison/suggestion payload; accepts query fields and writes nothing |
| `GET /api/pending-publish` | Yes | `desktop_pending_publish_preview.v1` | Pending Publish | Reads manifests and parked payloads; does not drain |
| `GET /api/publish-reconciliation` | Yes | `desktop_publish_reconciliation.v1` | Completed | Manual read-only correlation of Completed rows, current Pending Publish rows, and the latest durable pending drain summary; no repair/drain/publish action |

### Workspace Group

| Route | Auth | Effect | Response Schema | Frontend Caller | Notes |
|---|---|---|---|---|---|
| `GET /api/maintenance` | Yes | `bounded-health-check` | `desktop_maintenance_workspace.v1` | Maintenance | Runs existing env/tool probes; does not repair or change anything |
| `GET /api/maintenance/progress` | Yes | `none` | `desktop_maintenance_health_progress.v1` | Maintenance | Reads latest maintenance progress; does not run probes |
| `GET /api/maintenance/change-ledger` | Yes | `none` | `desktop_change_ledger.v1` | Maintenance | Reads structured change-control packets, changelog source status, and hygiene; does not run probes or regenerate files |
| `GET /api/maintenance/productization` | Yes | `none` | `desktop_productization_status.v1` | Maintenance | Reads backend-owned installer/updater/AppData productization readiness, migration posture, release channel, and close-readiness evidence only |
| `GET /api/schedule` | Yes | `none` | `desktop_schedule_workspace.v1` | Schedule | Reads persisted schedule state; schedule saves use separate backend command routes |
| `GET /api/watch-folders/status` | Yes | `none` | `desktop_watch_folders.v1` | Schedule | Reads watch-folder manager state, roots, pending-work status, and recent detections; does not scan on demand or mutate queue/process state |
| `GET /api/settings/workspace` | Yes | `none` | `desktop_settings_workspace.v1` | Settings | Read-only, redacted settings snapshot plus JSON-authority, projection, migration, legacy-extra, and PSD1 drift evidence |
| `GET /api/settings/preset-library` | Yes | `none` | `preset_library.v1` | Settings | Reads backend PresetV2 library State JSON only; no active config save, queue mutation, launch, or media touch |
| `GET /api/libraries/summary` | Yes | `none` | `desktop_libraries_summary.v1` | Libraries | Backend-authored saved LibraryProfiles summary with queue source scan media and sidecar aggregate counts; no settings save, scan, launch, queue mutation, or media touch |
| `GET /api/libraries/route-map` | Yes | `none` | `library_route_map.v1` | Libraries | Backend-authored Library Route Map and decision-matrix evidence from config, Library Profile inheritance state, and field metadata; no save, launch, plugin execution, queue mutation, or media touch |
| `GET /api/libraries/route-map/trace` | Yes | `none` | `library_route_trace.v1` | Libraries | Selected-file dry-run trace from existing Queue, Completed, and Sample Validation row evidence only; no probing or media mutation |
| `GET /api/libraries/route-map/compare` | Yes | `none` | `library_profile_compare.v1` | Libraries | Backend-authored Library Profile diff with explicit/inherited evidence and designation filtering; edits still use existing Library Profile Preview/Save |
| `GET /api/libraries/route-map/validation` | Yes | `none` | `library_route_validation_handoff.v1` | Libraries | Validation handoff from Sample Validation, Completed, Pending Publish, Diagnostics, and command evidence with distinct proof categories; no launch, drain, accept, repair, rename, save, plugin execution, or media mutation |
| `GET /api/settings/wizard/status` | Yes | `none` | `desktop_settings_wizard_status.v1` | Settings Wizard | Reads availability and first-run recommendation state only |
| `GET /api/settings/wizard/defaults` | Yes | `none` | `desktop_settings_wizard.v1` | Settings Wizard | Reads wizard defaults and tool candidates only |
| `GET /api/network/workers` | Yes | `none` | `desktop_network_workers.v1` | Network | Coordinator/worker persisted runtime state; lifecycle start/stop uses separate backend-owned command routes |
| `GET /api/sample-validation` | Yes | `none` | `desktop_sample_validation_log.v1` + summary + readiness + reconciliation + worksheet runs + pilot plan/checklist + sample set + evidence gaps + pilot runbook + policy alignment + validation audit | Home (Validation Log) | Recent validation records plus backend-authored read-only validation readiness, stale-evidence reconciliation, pilot plan, operator sample-execution checklist, generated worksheet evidence from `docs\RealMediaValidationRuns`, representative category coverage, evidence gaps, pilot runbook, saved-policy alignment, and conservative validation audit; query param: `limit` |

---

## Command Routes (POST)

All POST routes require auth. The frontend passes allowlisted parameter keys; the backend validates, plans, and executes. File-open routes do not accept arbitrary filesystem paths. Queue state routes accept only absolute paths under backend-configured `SourceMovies`/`SourceTV` roots. Queue source scan is a backend-owned command that writes scan evidence and refreshes the queue snapshot through the existing dry-run path.

### Queue Scan And State Commands

| Route | Effect | Request Keys | Allowed Values / Scope | Frontend Caller |
|---|---|---|---|---|
| `POST /api/queue/priority` | `queue-state-write` | `path`, `level`, `reason`, `items`, `clear_all` | `level`: `high`, `normal`, `low`, `hold`; path writes must be under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots); `clear_all` clears manifest state only | Queue |
| `POST /api/queue/strategy` | `queue-state-write` | `strategy` | Backend `VALID_STRATEGIES` only | Queue |
| `POST /api/queue/scan` | `process-dry-run` | `mode`, `force`, `scope`, `reason` | `mode`: `inventory_then_curate`, `inventory_only`, `curate_only`; `scope`: `all`; duplicate scans observe the active backend scan | Queue |
| `POST /api/queue/file-overrides` | `queue-state-write` | `path`, `audio`, `subtitles`, `routing`, `video`, `clear`, `clear_all`, `clear_fields` | Path writes must be under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots); `clear_all` clears manifest only | Queue |
| `POST /api/queue/file-overrides/route-preview` | `read-only-preview` | `path`, `proposed_override` | Path must be under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots); previews route impact only | Queue |
| `POST /api/queue/file-overrides/series-preview` | `read-only-preview` | `path`, `proposed_override` | Selected TV file path must be under configured source roots; previews current queue rows under the same detected source/show root only | Queue |
| `POST /api/queue/file-overrides/series-apply` | `queue-state-write` | `path`, `proposed_override`, `confirm_apply`, `preview_fingerprint` | Requires `confirm_apply: true` and a matching preview fingerprint; writes exact current-row file overrides only, protects exact manual rows, and creates no future show/folder policy | Queue |
| `POST /api/queue/file-overrides/series-clear-preview` | `read-only-preview` | `path` | Selected TV file path must be under configured source roots; previews exact current-row file overrides that would clear under the same detected source/show root only | Queue |
| `POST /api/queue/file-overrides/series-clear-apply` | `queue-state-write` | `path`, `confirm_apply`, `preview_fingerprint` | Requires `confirm_apply: true` and a matching preview fingerprint; clears exact current-row file overrides only, leaves inherited folder rules untouched, and creates no future show/folder policy | Queue |
| `POST /api/queue/file-overrides/remux-pilot-promote` | `queue-state-write` | `pilot_source_paths`, `confirm_apply`, `reason` | Requires `confirm_apply: true`; writes exact per-file remux overrides for eligible current queue rows in the detected pilot series only | Queue |
| `POST /api/queue/file-overrides/folder-preview` | `read-only-preview` | `folder_path`, `proposed_override`, `options` | Folder must be under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots); previews bounded known-file impact only | Queue |
| `POST /api/queue/file-overrides/folder-rule` | `queue-state-write` | `folder_path`, `override`, `confirmation`, `clear` | Folder must be under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots) but not equal a source/library root; stream indexes and raw map fields rejected; save requires future-file and exact-file precedence acknowledgement | Queue |
| `POST /api/subtitle-qa/preview` | `read-only-preview` | `id`, `row_key`, `path`, `source_path`, `output_path`, `scope`, `limit` | Reads already-loaded Queue and Completed subtitle QA evidence only; no probing, conversion, repair, sidecar rewrite, publish, drain, or media touch | Queue, Completed |

Queue state write commands write JSON state under `LocalBase\State`; preview commands are read-only. Queue source scan writes scan-status/source-inventory evidence and refreshes `queue_snapshot.json` through backend curation. Series clear and remux pilot promotion write exact current-row file overrides only after backend eligibility checks. These routes do not rename, move, delete, launch processing work, or mutate source media.

### Failure Resolution Commands

| Route | Effect | Request Keys | Allowed Values / Scope | Frontend Caller |
|---|---|---|---|---|
| `POST /api/failures/clear` | `failure-marker-write` | `scope`, `marker_path`, `marker_paths`, `source_json`, `dry_run`, `confirm_clear` | `scope`: `selected`, `visible`, `all_markers`; marker paths must resolve inside backend `State\Failures\Markers` | Reports |
| `POST /api/failures/archive-evidence` | `failure-evidence-archive` | `scope`, `include_markers`, `include_reports`, `dry_run`, `dry_run_fingerprint`, `confirm_archive`, `reason` | v1 `scope`: `all_active`; confirmed archive requires `confirm_archive: true`; reason/fingerprint are optional for routine current-plan archive, and supplied fingerprints are validated | Reports |
| `POST /api/failures/open` | `shell-open` | `row_key`, `target`, `source_kind` | `target`: `artifact`, `repro`, `record_file`, `record_folder`; backend resolves the selected row and accepts no arbitrary frontend path | Reports |
| `POST /api/failures/artifacts/cleanup` | `failure-artifact-delete` | `dry_run`, `dry_run_fingerprint`, `confirm_delete`, `reason`, `retention_days`, `target_gb`, `artifact_paths` | Deletes only backend-resolved failure artifact files; confirmed delete requires `confirm_delete: true`; selected `artifact_paths` still require a matching fingerprint; explicit command `target_gb: 0` targets the current artifact backlog | Reports |
| `POST /api/failures/lifecycle` | `failure-resolution-journal-write` | `journal_key`, `transition`, `step_id`, `reason`, `operator_note`, `dry_run`, `dry_run_fingerprint`, `confirm_transition` | Active backend-authored group only; resolve/reopen/waive require reason and `confirm_transition: true`; backend recomputes blockers at apply time | Reports |

Failure marker clear is backend-owned retry-blocker cleanup. It requires `confirm_clear` unless `dry_run` is true, writes a clear manifest, and moves marker JSON out of the active marker folder. It does not delete media files, failure reports, completed manifests, pending publish files, or source/output paths.
Advanced evidence archive is backend-owned cleared-evidence cleanup. It moves active marker JSON and `round_failures_*.json/.txt` reports into `State\Failures\ClearManifests\ClearedEvidence`; it does not unlink evidence directly and does not touch media, completed manifests, pending publish files, or source/output paths.
Failure evidence open is backend-owned shell-open for selected failure row evidence only. The frontend sends a row key, source kind, and allowed target; the backend resolves the path from current failure preview evidence and rejects arbitrary paths.
Failure artifact cleanup is backend-owned artifact retention cleanup. It previews candidates first, then deletes only files under current and legacy failure artifact roots after strict confirmation and fingerprint match. Reports normally passes `artifact_paths` from checked rows so deletion is selection-scoped. It does not delete source/output media, failure markers, reports, completed manifests, pending publish files, or artifact root directories.
Failure lifecycle is append-only operator resolution evidence under `State\Failures\ResolutionJournal\events.jsonl`. It does not clear markers, archive reports, retry work, mutate queue/publish/completed state, or touch media files.

### File Open, Pending Recovery, And Repair/Reconcile Dry-Run Commands

| Route | Effect | Request Keys | Allowed Targets | Frontend Caller |
|---|---|---|---|---|
| `POST /api/queue/open` | `shell-open` | `row_key`, `target`, `row_scope` | `source_file`, `source_folder`, `source_root` | Queue |
| `POST /api/completed/open` | `shell-open` | `row_key`, `target` | `output_file`, `play_output_file`, `output_folder`, `sidecar`, `source_folder` | Completed |
| `POST /api/pending-publish/open` | `shell-open` | `row_key`, `target` | `local_file`, `manifest`, `destination_folder`, `source_folder` | Pending Publish |
| `POST /api/pending-publish/recovery-plan` | `none` (dry-run) | `scope`, `row_key` | `all`, `selected` | Pending Publish |
| `POST /api/completed/reconcile-manifest-dry-run` | `none` (dry-run) | `scope`, `row_key`, `limit`, `reason` | Backend-authored dry-run only; no manifest write | Completed |
| `POST /api/completed/reconcile-manifest` | `completed-manifest-write` | `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply` | Backs up and atomically rewrites existing selected completed manifest rows only after matching dry-run fingerprint | Completed |
| `POST /api/completed/repair-sidecar-metadata-dry-run` | `none` (dry-run) | `scope`, `row_key`, `limit`, `reason` | Backend-authored dry-run only; no sidecar write | Completed |
| `POST /api/completed/repair-sidecar-metadata` | `completed-sidecar-json-write` | `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply` | Backs up and atomically rewrites backend-derived sidecar metadata fields only; unknown sidecar fields are preserved | Completed |
| `POST /api/pending-publish/repair-manifest-dry-run` | `none` (dry-run) | `scope`, `row_key`, `limit`, `reason` | Backend-authored dry-run only; can produce validated manifest-normalization candidates but writes nothing and does not drain | Pending Publish |
| `POST /api/pending-publish/repair-manifest` | `pending-manifest-write` | `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply` | Writes only backend-validated manifest-normalization candidates after matching fingerprint and strict confirmation; blocks incomplete evidence; no drain, publish, move, or delete | Pending Publish |
| `POST /api/pending-publish/reconcile-orphan-payloads-dry-run` | `none` (dry-run) | `scope`, `row_key`, `limit`, `reason` | Backend-authored dry-run only; lists missing `pending_push_manifest.v1` evidence for ordinary orphan rows, can surface a candidate only from a complete backend proposal, and performs no manifest create, drain, publish, move, or delete | Pending Publish WebView dry-run control |
| `POST /api/pending-publish/reconcile-orphan-payloads` | `pending-orphan-manifest-write` | `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply` | Manifest-only confirmed route creates only the missing payload-adjacent pending manifest from a complete backend-derived `pending_push_manifest.v1` proposal; otherwise blocks and never moves, deletes, drains, or publishes payloads | Pending Publish WebView fingerprint-gated confirmation control |
| `POST /api/startup/reconcile-dry-run` | `none` (dry-run) | `scope`, `row_key`, `limit`, `reason` | Backend-authored startup reconciliation evidence only; no repair, rebuild, migration, drain, publish, or media touch | No WebView caller; backend route only |

`recovery-plan` effect is `none`: it builds a backend-authored dry-run plan and returns it. Repair/reconcile dry-runs are unjournaled and strictly limited to `scope`, `row_key`, `limit`, and `reason`. Confirmed apply routes are backend-owned, journaled, fingerprint-gated, and confirmation-gated. No repair/reconcile route drains, moves, deletes, publishes, reruns, or touches media bytes.

### Final Library Promotion Commands

| Route | Effect | Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/final-library-promotion/promote-queue` | `filesystem-mutation` | `confirm_promote`, `row_keys` | **High** — copies verified completed outputs to configured final-library destinations after explicit confirmation, queue-wide or selected-row scoped | Completed |
| `POST /api/final-library-promotion/pause` | `control-state-write` | `run_id` | Medium — writes cooperative pause state for the active promotion run only | Completed |
| `POST /api/final-library-promotion/resume` | `control-state-write` | `run_id` | Medium — clears cooperative pause state for the active promotion run only | Completed |

Final-library promotion remains backend-owned: the backend resolves destinations, eligible completed rows, active run state, pause/resume state, copy behavior, and any configured publish-output cleanup.

### Diagnostics Commands

| Route | Effect | Request Keys | Allowed Targets | Frontend Caller |
|---|---|---|---|---|
| `POST /api/diagnostics/open` | `shell-open` | `target` | 20 allowlisted keys (see below) | Diagnostics, all pages |
| `POST /api/diagnostics/tdarr-matrix-audit` | `diagnostic-process` | `action` | `report`, `smoke`, `matrix`, `full`, `strict-report` | Diagnostics |
| `POST /api/diagnostics/tdarr-matrix/evidence/open` | `shell-open` | `run_id`, `finding_key`, `target` | `stdout`, `stderr`, `worker_result`, `source_hashes`, `failure_artifact`, `output`, `report_folder` | Diagnostics |
| `POST /api/diagnostics/tdarr-matrix/rerun` | `diagnostic-process` | `source_run_id`, `selection`, `finding_keys` | `selected`, `latest_failures` | Diagnostics |

Allowed targets for `/api/diagnostics/open`: `run_logs`, `cluster_log`, `config`, `config_folder`, `workspace`, `state`, `pending_publish`, `failed_reports`, `failed_markers`, `audit_reports`, `queue_snapshot`, `active_jobs`, `completed_manifest`, `latest_failure_report`, `latest_failure_json`, `latest_audit_csv`, `latest_priority_csv`, `last_stdout_log`, `last_stderr_log`, `sample_validation_log`.

### UI Preference Commands

| Route | Effect | Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/ui-preferences` | `ui-state-write` | `storage`, `source_surface` | Low — writes allowlisted UI preference JSON only | Chrome WebView, Tauri shell |
| `POST /api/path-picker/browse` | `shell-dialog` | `target_key`, `selection_mode`, `initial_path`, `file_filter` | Low — opens a backend-owned native Windows picker for allowlisted path targets only; stages validation evidence only | WebView path picker badges |

UI preference sync is backend-owned state persistence for browser-local customization only. It can store layout, theme, evidence visibility, and tab choices under `LocalBase\State`. Path picker browse is backend-owned staged shell-dialog evidence for allowlisted path fields only. These routes cannot save settings, mutate queue state, launch work, drain, rename, publish, or touch media files.

### Maintenance Commands (deployment package, dry-run, and tooling)

| Route | Effect | Key Request Keys | Frontend Caller |
|---|---|---|---|
| `POST /api/maintenance/release-dry-run` | `process-dry-run` | `destination_root`, `zip_package`, `verify`, `include_tests`, … | Maintenance |
| `POST /api/maintenance/release-build` | `deployment-write` | `destination_root`, `zip_package`, `verify`, `include_tests`, `force`, `confirm_create`, … | Maintenance |
| `POST /api/maintenance/completed-backfill-dry-run` | `process-dry-run` | `timeout_seconds` | Maintenance |
| `POST /api/maintenance/retention-dry-run` | `none` | `limit`, `reason` | No WebView caller; backend route only |
| `POST /api/maintenance/dependency-atlas` | `tooling-artifact-write` | `timeout_seconds`, `min_overview_edge_count`, `min_overview_files` | Maintenance |
| `POST /api/maintenance/dependency-atlas/open-folder` | `shell-open` | none | Maintenance |
| `POST /api/maintenance/support-export` | `diagnostics-artifact-write` | `reason`, `include_recent_logs`, `max_log_bytes` | Maintenance |
| `POST /api/maintenance/archive-state-journals` | `runtime-evidence-archive` | `confirm_archive`, `reason` | Maintenance |

The dry-run routes run existing backend scripts with `-DryRun` and write no release folder, zip, manifest, or completed manifest. `dependency-atlas` writes generated dependency-atlas tooling artifacts under `docs/generated/dependency-atlas/` only; `dependency-atlas/open-folder` opens that backend-resolved folder only and accepts no frontend path. State journal archive writes only runtime evidence archives after confirmation. These maintenance routes do not touch media, queue, settings, manifests, pending publish state, or pipeline state. `release-build` requires explicit `confirm_create`, is blocked during active work, runs under the backend maintenance command lock, and writes only release deployment artifacts through the backend release builder.

### Metrics Commands

| Route | Effect | Key Request Keys | Frontend Caller |
|---|---|---|---|
| `POST /api/metrics/sources` | `metrics-state-write` | `action`, `path`, `source_id`, `label`, `enabled` | Metrics |
| `POST /api/metrics/backfill` | `metrics-backfill-state-write` | `scope`, `source_id`, `path`, `max_sidecars` | Metrics |

Metrics commands write only backend Metrics state under `State\Metrics`. Source updates maintain the configured root registry. Backfill recursively reads `*.pipeline.json` sidecars under configured Metrics roots, skips symlinked folders, and refreshes Metrics cache/status files without rewriting sidecars, launching work, changing queue state, or touching media files.

### Audit Source Commands

| Route | Effect | Key Request Keys | Frontend Caller |
|---|---|---|---|
| `POST /api/audit/sources` | `audit-source-state-write` | `action`, `path`, `source_id`, `label`, `enabled` | Reports |
| `POST /api/audit/sources/scan` | `audit-source-scan-state-write` | `scope`, `source_id`, `source_ids`, `path`, `max_entries` | Reports |

Audit source commands write only backend Reports audit state under `State\Audit`. Source updates maintain the selectable scan-location registry. Scans recursively read selected roots, count aggregate media files, sidecars, and folders, skip symlinked folders, and refresh scan status without rewriting sidecars, launching work, changing queue state, or touching media files.

### Rename Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/rename/preview` | `none` | `paths`, `mode`, `show_name`, `season`, `start_episode`, `movie_title`, `movie_year` | None — predictions only | Rename |
| `POST /api/rename/browse` | `shell-dialog` | `selection_mode` (`files`, `folder`, `folder_files`), `initial_path`, `paths` | Low — native Windows file/folder browser or already-known dropped path resolution only; no media mutation | Rename |
| `POST /api/rename/filter-cases` | `test-fixture-write` | `kind`, `source_folder`, `source_file`, `expected_name`, `expected_show`, `expected_movie_title`, `expected_year`, `status`, `confirm_append` | Low — appends to rename regression fixture only; no media mutation | Rename |
| `POST /api/rename/apply` | `filesystem-mutation` | `paths`, `selected_sources`, `confirm_apply`, `allow_outside_configured_roots` | **High** — filesystem rename | Rename |
| `POST /api/rename/undo` | `filesystem-mutation` | `undo_manifest`, `confirm_undo` | **High** — reverses a backend-owned undo manifest under the resolved undo root | Rename |

`rename/browse` opens the Windows file/folder browser or resolves already-known dropped paths, then returns media paths for staging. `GET /api/rename/clean-filename-preview` powers the Settings workbench's actual/expected comparison and filter suggestions, including already-covered vs stage-recommended suggestion metadata and media-type-scoped destination choices, but writes nothing. `rename/filter-cases` appends only `tv_auto` or `movie_auto` rows to `tests/fixtures/rename/bad_rename_cases.jsonl` after `confirm_append: true`; it does not preview, apply, rename, move, delete, or touch media files. `rename/apply` and `rename/undo` are the only rename media mutation routes. The backend rebuilds the rename plan independently from the submitted paths and applies only the explicitly selected source rows through the transactional rename service. `confirm_apply` must be set for apply, and `confirm_undo` plus a backend-owned undo manifest must be set for undo; the backend does not infer confirmation from prior preview calls. Paths outside backend-injected configured media roots also require `allow_outside_configured_roots: true` after explicit operator review.

### Settings Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/settings/validate` | `none` | `values` | None — validation only | Settings |
| `POST /api/settings/browse-path` | `shell-dialog` | `setting_key`, `selection_mode`, `initial_path` | Low — backend-owned native Windows folder browser for allowlisted path fields only | Settings |
| `POST /api/settings/preview-patch` | `none` | `changes`, `remove_keys`, `library_profile_resets` | None — returns redacted diff | Settings; Network Worker Mode Settings delegates through Settings view |
| `POST /api/settings/pipeline-plan-preview` | `none` | `source_media`, `changes`, `remove_keys` | None — validates supplied source facts and returns a backend-owned dry-run pipeline plan only | Settings |
| `POST /api/settings/preset-library/validate` | `none` | `preset_v2` | None — validates inline PresetV2 only | Settings |
| `POST /api/settings/preset-library/compare` | `none` | `left_id`, `right_id`, `left_preset_v2`, `right_preset_v2` | None — compares PresetV2 records or inline presets through backend patch projection only | Settings |
| `POST /api/settings/preset-library/import-preview` | `none` | `records` | None — validates import candidates and reports State JSON target only | Settings |
| `POST /api/settings/preset-library/save` | `preset-library-state-write` | `id`, `name`, `description`, `tags`, `source`, `imported_from`, `preset_v2`, `confirm_save` | Low — writes backend PresetV2 library JSON under State/PresetLibrary only; does not save active config | Settings |
| `POST /api/settings/preset-library/export` | `none` | `id`, `preset_v2` | None — returns a preset export payload only | Settings |
| `POST /api/settings/preset-library/apply-preview` | `none` | `id`, `preset_v2` | None — converts PresetV2 to a legacy settings patch and previews through existing settings policy only | Settings |
| `POST /api/settings/preset-library/apply` | `config-write` | `id`, `preset_v2`, `confirm_apply` | **High** — converts PresetV2 to a legacy settings patch and saves through the existing backend settings save path for future launches | Settings |
| `POST /api/settings/save-patch` | `config-write` | `changes`, `remove_keys`, `library_profile_resets`, `review_confirmation`, `confirm_save` | **High** — writes JSON settings authority and generated PSD1 projection together; save requires `review_confirmation` from the matching backend preview plus `confirm_save: true` | Settings; Network Worker Mode Settings delegates through Settings view |
| `POST /api/settings/import-psd1-preview` | `none` | *(none)* | None — previews explicit PSD1 recovery import into JSON authority without writing | Settings |
| `POST /api/settings/import-psd1` | `config-write` | `confirm_import` | **High** — imports active PSD1 into JSON authority and regenerates the PSD1 projection | Settings |
| `POST /api/settings/wizard/validate-paths` | `none` | `wizard` | None — validation only | Settings Wizard |
| `POST /api/settings/wizard/validate-tools` | `none` | `wizard` | None — validation only | Settings Wizard |
| `POST /api/settings/wizard/probe-hardware` | `none` | `wizard` | None — bounded probe evidence only | Settings Wizard |
| `POST /api/settings/wizard/validate-workers` | `none` | `wizard` | None — validation only | Settings Wizard |
| `POST /api/settings/wizard/preview` | `none` | `wizard` | None — generated-patch preview only | Settings Wizard |
| `POST /api/settings/wizard/save` | `config-write` | `wizard`, `confirm_save` | **High** — writes PSD1 config through the normal backend save path | Settings Wizard |
| `POST /api/settings/reload` | `none` | *(none)* | None — reloads cached state | Settings |

`browse-path` opens only the backend-owned Windows folder browser for allowlisted Settings path fields (`SourceMovies`, `SourceTV`, `Outsource`, `LocalBase`, `FinalLibraryPromotionRuleSourceRoot`, `FinalLibraryPromotionRuleDestinationRoot`) and returns selected-folder validation evidence for WebView staging. It does not save settings, launch work, rewrite queue state, or touch media files. Preset library save writes `State/PresetLibrary/presets.json` only; preset apply uses existing settings preview/save policy and affects future launches only. Settings Wizard validation/preview routes do not write config. `settings/wizard/save`, `save-patch`, explicit `import-psd1`, and preset apply perform backup, atomic write, projection validation, and backend state reload. Confirmation must be set for config writes. The Network page's Worker Mode Settings panel delegates to these same backend Settings routes for config preview/save only; lifecycle start/stop uses the separate Network Lifecycle routes below.

### Schedule Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/schedule/preview` | `none` | `enabled`, `day_windows`, `grid` | None — validation/preview only | Schedule |
| `POST /api/schedule/save` | `app-state-write` | `enabled`, `day_windows`, `grid`, `confirm_save` | Medium — writes desktop app state schedule keys | Schedule |

`schedule/preview` parses operator day-window text through the backend schedule policy and reports changed days without writing app state. `schedule/save` requires `confirm_save` and persists only `schedule_enabled` and `schedule_grid` through the backend app-state service; it cannot launch work, mutate queue state, bypass schedule gates, or touch media files.

### Sample Validation Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/sample-validation/preview` | `none` | `schema`, `shell`, `source_path`, `output_path`, `sample_label`, `sample_category`, `proof_strength`, `operator_decision`, `checks`, `evidence`, `operator_notes` | None — preview only; returns current-evidence, pilot evidence packet, post-run capture, and append-readiness guidance | Home (Validation Log) |
| `POST /api/sample-validation/append` | `validation-log-write` | `schema`, `shell`, `source_path`, `output_path`, `sample_label`, `sample_category`, `proof_strength`, `operator_decision`, `checks`, `evidence`, `operator_notes` | Low — appends to `sample_validation_log.jsonl` only; returns current-evidence, pilot evidence packet, post-run capture, and append-readiness guidance | Home (Validation Log) |

`append` must not mark jobs complete, clear failures, drain pending publish, rewrite manifests, launch work, or mutate media files. It is scoped to the operator's evidence log only.

### Audit Control Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/audit/score-policy` | `audit-state-write` | `policy`, `reset` | Medium — writes backend-owned audit score policy only | Reports |
| `POST /api/audit/ignore` | `audit-state-write` | `action`, `row_keys`, `paths`, `reason`, `priority_only`, `limit` | Medium — writes audit-only ignore state without queue holds or media mutation | Reports |
| `POST /api/audit/export-rerun-csv` | `report-file-write` | `row_keys`, `priority_only`, `limit` | Medium — writes a backend-owned rerun CSV artifact only; does not launch rerun work | Reports |

Audit control commands are backend-owned report/state helpers. They do not write
queue priority, apply holds, launch rerun work, change settings, or touch media
files.

### Network Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/network/coordinator/start-dry-run` | `none` | `reason` | None — lifecycle dry-run evidence only | Network |
| `POST /api/network/coordinator/stop-dry-run` | `none` | `reason` | None — lifecycle dry-run evidence only | Network |
| `POST /api/network/worker/start-dry-run` | `none` | `reason` | None — lifecycle dry-run evidence only | Network |
| `POST /api/network/worker/stop-dry-run` | `none` | `reason` | None — lifecycle dry-run evidence only | Network |
| `POST /api/network/worker/test-connection` | `none` | `timeout_seconds` | None — read-only worker TCP/auth/path preflight only | Network |
| `POST /api/network/worker/discover-coordinators` | `none` | `timeout_seconds` | None — read-only mDNS coordinator discovery; selection only stages the Settings patch | Network |
| `POST /api/network/coordinator/join-blob` | `secret-transfer` | `coordinator_url`, `confirm_create`, `rotate_token`, `confirm_rotate` | High — unjournaled setup blob contains the worker auth secret; no media or lifecycle mutation | Network |
| `POST /api/network/worker/join-cluster` | `config-write` | `join_blob`, `confirm_import`, `timeout_seconds` | High — imports worker URL/token/path-map settings through backend settings save, then runs read-only test-connection | Network |
| `POST /api/network/coordinator/start` | `backend-lifecycle` | `confirm_start`, `reason` | **High** — starts only the real coordinator lifecycle provider after confirmation and preconditions | Network |
| `POST /api/network/coordinator/stop` | `backend-lifecycle` | `confirm_stop`, `reason` | **High** — stops only the coordinator lifecycle provider while preserving claims/state files | Network |
| `POST /api/network/worker/start` | `backend-lifecycle` | `confirm_start`, `reason` | **High** — starts only the worker polling provider; no local queue scan or normal Launch | Network |
| `POST /api/network/worker/stop` | `backend-lifecycle` | `confirm_stop`, `reason` | **High** — requests worker lifecycle stop while preserving pending done reports | Network |

Network lifecycle dry-runs return preconditions, active-work posture, state-file posture, pending done posture, redacted config evidence, and `would_not_touch` evidence. Confirmed routes require explicit confirmation fields and fail closed when the real coordinator/worker lifecycle provider is unavailable.

### Process Commands

| Route | Effect | Key Request Keys | Mutation Risk | Frontend Caller |
|---|---|---|---|---|
| `POST /api/pipeline/control` | `control-flag-write` | `action` (`pause`, `stop`, `rescan`, `kill`) | Medium — writes control flags or runs backend-owned emergency process cleanup for `kill` | Launch |
| `POST /api/pipeline/browse-file` | `shell-dialog` | `selection_mode` (`files`), `initial_path` | Low — backend-owned native Windows file browser for Launch single-file staging only; no config save, launch, queue mutation, or media mutation | Launch |
| `POST /api/pipeline/start` | `process-launch` | `mode`, `sleep_seconds`, `show_config`, `show_console`, `single_file`, `schedule_override` | **High** — spawns pipeline process | Launch |
| `POST /api/audit/start` | `process-launch` | `library_root`, `library_roots`, `source_ids`, `include_sidecars`, `show_console` | **High** — spawns audit process for one or more selected audit source locations | Launch, Reports |
| `POST /api/audit/stop` | `process-control` | `confirm_stop`, `reason` | **High** — after explicit confirmation, stops audit process trees only and marks audit progress stopped | Reports |
| `POST /api/rerun/preview` | `read-only-preview` | `csv_path`, `execution_mode`, `destination_mode`, `original_policy`, `collision_policy`, `window_size`, confirmations, `scope` filters | None — backend parses and summarizes CSV rerun rows, import/scoped CSV candidates, lifecycle warnings, filter options, tiles, and scoped counts without launch or media mutation | Launch |
| `POST /api/rerun/start` | `process-launch` | `csv_path`, `dry_run`, `plan_only`, `execution_mode`, `destination_mode`, `original_policy`, `collision_policy`, `window_size`, confirmations, `scope` filters | **High** — spawns backend-owned CSV rerun v2; default execution is one-at-a-time, scoped starts write under `State\Rerun\ScopedCsv`, and replace/original policies require strict confirmation and output proof | Launch |
| `POST /api/rerun/open` | `shell-open` | `target`, `row_key`, `csv_key` | Low — opens only backend-derived rerun review outputs, manifests, import/scoped CSVs, or folders; arbitrary filesystem paths are rejected | Launch |
| `POST /api/rerun/promote-dry-run` | `read-only-preview` | `row_key` | None — computes dry-run evidence for promoting an existing rerun review output into Pending Publish without moving files or writing manifests | Launch |
| `POST /api/rerun/promote` | `pending-manifest-write` | `row_key`, `dry_run_fingerprint`, `confirm_promote` | Medium — after matching dry-run evidence and strict confirmation, moves an existing rerun review output into Pending Publish and writes a pending-publish manifest; it does not directly publish or touch source media | Launch |
| `POST /api/backend/shutdown` | `backend-lifecycle` | `reason`, `force_active_work_shutdown` | **Critical** — requests graceful shutdown only after safe close-readiness unless literal boolean `true` force cleanup is requested | Tauri shell (close flow) |

`pipeline/start` allowed modes: `once`, `continuous`, `validate`, `drain_pending_pushes`. `schedule_override` allowed values: `""`, `run_once`, `ignore`. `rerun/preview` backs auto-preview for Review & Start and is no-write. `rerun/start` defaults are media-safe (`dry_run: false`, `execution_mode: one_at_a_time`, `destination_mode: review_workspace`, `original_policy: keep`, `collision_policy: suffix`, `enabled_only: true`); legacy `stage_mode`/`original_mode`/`return_mode` values are compatibility aliases only, and source/final replacement policies are strict-confirmation gated.

---

## Mutation Risk Summary

| Effect tag | Routes | Risk level |
|---|---|---|
| `none` | 81 routes (read-only GET routes except maintenance, rename/preview, settings/validate, settings/preview-patch, settings/pipeline-plan-preview, settings/import-psd1-preview, preset library preview/export routes, Settings Wizard validation/preview routes, settings/reload, recovery-plan, repair/reconcile dry-runs, startup reconcile dry-run, maintenance retention dry-run, sample-validation/preview, schedule/preview, Network lifecycle dry-runs, worker test-connection/discovery) | None |
| `bounded-health-check` | `GET /api/maintenance` | Read-only probes |
| `read-only-preview` | `POST /api/queue/file-overrides/route-preview`, `POST /api/queue/file-overrides/series-preview`, `POST /api/queue/file-overrides/series-clear-preview`, `POST /api/queue/file-overrides/folder-preview`, `POST /api/subtitle-qa/preview`, `POST /api/rerun/preview`, `POST /api/rerun/promote-dry-run` | Advisory backend previews only |
| `shell-open` | `POST /api/queue/open`, `POST /api/completed/open`, `POST /api/pending-publish/open`, `POST /api/diagnostics/open`, `POST /api/diagnostics/tdarr-matrix/evidence/open`, `POST /api/failures/open`, `POST /api/maintenance/dependency-atlas/open-folder`, `POST /api/rerun/open` | OS open only; no file mutation |
| `shell-dialog` | `POST /api/rename/browse`, `POST /api/settings/browse-path`, `POST /api/path-picker/browse`, `POST /api/pipeline/browse-file` | Native Windows picker or already-known path resolution only; no file mutation |
| `test-fixture-write` | `POST /api/rename/filter-cases` | Appends backend-validated JSONL rows to `tests/fixtures/rename/bad_rename_cases.jsonl` only |
| `diagnostic-process` | `POST /api/diagnostics/tdarr-matrix-audit`, `POST /api/diagnostics/tdarr-matrix/rerun` | Backend-owned Tdarr Matrix scratch audit presets and isolated reruns only |
| `diagnostics-artifact-write` | `POST /api/maintenance/support-export` | Backend-owned redacted support export under per-user AppData DiagnosticsExports only |
| `runtime-evidence-archive` | `POST /api/maintenance/archive-state-journals` | Backend-owned state journal archive evidence only |
| `ui-state-write` | `POST /api/ui-preferences` | Allowlisted UI preference JSON only |
| `metrics-state-write` | `POST /api/metrics/sources` | Metrics source registry JSON under `State\Metrics` only |
| `metrics-backfill-state-write` | `POST /api/metrics/backfill` | Recursive sidecar read plus Metrics cache/status writes under `State\Metrics` only |
| `audit-source-state-write` | `POST /api/audit/sources` | Reports audit source registry JSON under `State\Audit` only |
| `audit-source-scan-state-write` | `POST /api/audit/sources/scan` | Recursive read-only metric counts plus audit source scan status writes under `State\Audit` only |
| `queue-state-write` | `POST /api/queue/priority`, `POST /api/queue/strategy`, `POST /api/queue/file-overrides`, `POST /api/queue/file-overrides/series-apply`, `POST /api/queue/file-overrides/series-clear-apply`, `POST /api/queue/file-overrides/remux-pilot-promote`, `POST /api/queue/file-overrides/folder-rule` | Non-destructive queue state JSON only |
| `failure-marker-write` | `POST /api/failures/clear` | Moves retry-blocker marker JSON out of the active marker folder only |
| `failure-evidence-archive` | `POST /api/failures/archive-evidence` | Moves active failure markers and round failure reports into manifest-backed cleared evidence only |
| `failure-artifact-delete` | `POST /api/failures/artifacts/cleanup` | Deletes backend-owned failure artifact files only after strict confirmation; selected `artifact_paths` limit the Reports action to checked rows and still require a dry-run fingerprint; policy cleanup can use the current backend plan |
| `failure-resolution-journal-write` | `POST /api/failures/lifecycle` | Appends operator lifecycle evidence for active failure groups only |
| `audit-state-write` | `POST /api/audit/score-policy`, `POST /api/audit/ignore` | Audit-only score/ignore state; no queue/media mutation |
| `report-file-write` | `POST /api/audit/export-rerun-csv` | Writes a backend-owned report CSV artifact only |
| `process-dry-run` | `POST /api/queue/scan`, `POST /api/maintenance/release-dry-run`, `POST /api/maintenance/completed-backfill-dry-run` | Backend dry-run/process evidence only; no media output written |
| `tooling-artifact-write` | `POST /api/maintenance/dependency-atlas` | Generated dependency-atlas tooling artifacts under `docs/generated/dependency-atlas/` only |
| `deployment-write` | `POST /api/maintenance/release-build` | Writes deployable release folder, manifest, and optional zip only |
| `control-state-write` | `POST /api/final-library-promotion/pause`, `POST /api/final-library-promotion/resume` | Writes cooperative final-library promotion control state only |
| `control-flag-write` | `POST /api/pipeline/control` | Pause/stop/rescan signal or backend-owned emergency kill cleanup only |
| `process-control` | `POST /api/audit/stop` | Confirmation-gated audit-only process cleanup and terminal `audit_progress.json` write |
| `validation-log-write` | `POST /api/sample-validation/append` | Appends to operator evidence log only |
| `app-state-write` | `POST /api/schedule/save` | Writes desktop app schedule keys only |
| `secret-transfer` | `POST /api/network/coordinator/join-blob` | Returns an unjournaled setup blob containing the worker auth secret; no media or lifecycle mutation |
| `preset-library-state-write` | `POST /api/settings/preset-library/save` | Writes PresetV2 library State JSON only |
| `config-write` | `POST /api/settings/save-patch`, `POST /api/settings/import-psd1`, `POST /api/settings/preset-library/apply`, `POST /api/settings/wizard/save`, `POST /api/network/worker/join-cluster` | Writes and reloads JSON-authoritative settings plus PSD1 projection |
| `completed-manifest-write` | `POST /api/completed/reconcile-manifest` | Backs up and rewrites existing selected completed manifest rows only |
| `completed-sidecar-json-write` | `POST /api/completed/repair-sidecar-metadata` | Backs up and rewrites backend-derived sidecar metadata fields only |
| `pending-manifest-write` | `POST /api/pending-publish/repair-manifest`, `POST /api/rerun/promote` | Manifest routes are fingerprint-gated, write only backend-validated pending-publish manifest evidence, and block incomplete backend evidence |
| `pending-orphan-manifest-write` | `POST /api/pending-publish/reconcile-orphan-payloads` | Manifest-only orphan route is fingerprint-gated, creates only a missing payload-adjacent manifest from complete backend proposal evidence, and never moves/deletes/drains/publishes payloads |
| `filesystem-mutation` | `POST /api/rename/apply`, `POST /api/rename/undo`, `POST /api/final-library-promotion/promote-queue` | Renames files, reverses backend-owned rename manifests, or promotes completed outputs through backend-owned file operations |
| `process-launch` | `POST /api/pipeline/start`, `POST /api/audit/start`, `POST /api/rerun/start` | Spawns backend processes |
| `backend-lifecycle` | `POST /api/backend/shutdown`, `POST /api/network/coordinator/start`, `POST /api/network/coordinator/stop`, `POST /api/network/worker/start`, `POST /api/network/worker/stop` | Initiates guarded backend lifecycle operations; forced active-work cleanup requires literal boolean `true` for shutdown, and Network lifecycle start/stop requires confirmation plus provider preconditions |

---

## Auth Coverage

All routes require the bootstrap token (`Authorization: Bearer` or `X-MediaPipeline-Token` header) except `GET /api/health`, which is deliberately unauthenticated for Tauri shell startup probing before the token is passed to WebView2. No route exposes the auth token to the WebView or browser storage.

---

## Backend Ownership Confirmation

Every mutation route enforces backend ownership:

- **File open** (`queue/open`, `completed/open`, `pending-publish/open`): backend selects the path from its own manifest/snapshot by `row_key` and `target` key; the frontend cannot pass a raw path.
- **Rename browse** (`rename/browse`): backend opens the native Windows file/folder browser or resolves already-known dropped paths and returns media paths for staging only; preview/apply still use separate backend routes.
- **Settings path browse** (`settings/browse-path`): backend opens the native Windows folder browser for allowlisted source/output/scratch and final-library promotion root settings and returns validation evidence for staging only; Preview/Save remains the only settings persistence path.
- **Path picker browse** (`path-picker/browse`): backend opens the native Windows file/folder browser for allowlisted real path fields and returns staged-only validation evidence; it does not save settings, launch work, or touch media files.
- **Diagnostics open/tail**: frontend passes an allowlisted target key string; backend resolves the real path and rejects any key not in the allowlist.
- **UI preferences**: frontend sends only allowlisted `mediapipeline-*`/`mediapipeline.*` local customization keys; backend stores them as UI state under `LocalBase\State` and never treats them as config or media policy.
- **Queue source scan and state writes**: backend serializes source scans, writes scan evidence under `LocalBase\State\Progress`, curates queue rows through the existing queue-plan dry-run, rejects priority/file-override path writes unless the path is absolute and under configured `SourceMovies`/`SourceTV`, and constrains strategy writes to backend valid strategy names.
- **Recovery plan**: backend authors the dry-run plan; the frontend receives it read-only.
- **Deployment build**: backend owns release packaging, active-work checks, confirmation, command locking, destination replacement, manifest creation, and optional zip creation; the frontend cannot copy files, write manifests, or zip folders itself.
- **Rename apply**: backend rebuilds the rename plan from its own state; it does not execute the frontend-submitted plan as-is. `confirm_apply` is required.
- **Settings save-patch/import**: backend merges or imports, validates, backs up, and atomically writes JSON-authoritative settings plus the generated PSD1 projection; the frontend cannot write either file directly.
- **Schedule save**: backend parses and validates day windows, requires `confirm_save`, and writes only schedule app-state keys; the frontend cannot write state JSON directly.
- **Pipeline/audit/rerun start and audit stop**: backend owns process launch/stop, locks, command journal, audit-only cleanup scope, and progress state; the frontend cannot exec or kill processes directly.
- **Network lifecycle start/stop**: backend owns dry-run preconditions, confirmation-gated start/stop, command journaling, and provider availability. Network mode never falls through to normal Launch or frontend queue scanning.
- **Shutdown**: Tauri shell issues this after `GET /api/backend/close-readiness` confirms it is safe; the backend controls the shutdown sequence.

---

## See Also

- Route handler dispatch: `src/mediapipeline/desktop/api/routes_read.py`, `routes_command.py`
- Contract source: `src/mediapipeline/desktop/api/contract_read.py`, `contract_command.py`
- Diagnostics target allowlist: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Lifecycle boundary: `docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
- Settings coverage: `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
