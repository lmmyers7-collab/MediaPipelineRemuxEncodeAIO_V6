# Command Ownership Matrix

Date: 2026-06-13

Documents every POST command route in the Local API: command type, backend
contract group, primary frontend owner, mutation class, and key restrictions.
Source: `src/mediapipeline/desktop/api/contract_command.py`,
`src/mediapipeline/core/api/commands.py`, and the WebView `apiPost` call
inventory.

Total command routes: 91 POST routes across 11 contract groups.

Network lifecycle start/stop now has backend-owned dry-run and confirmed POST
routes. Confirmed coordinator/worker lifecycle routes are confirmation-gated,
command-journaled, and provider-guarded. Repair/reconcile has backend-owned
dry-run and confirmed apply routes; confirmed apply routes require matching
dry-run fingerprints and backend backups.

---

## Contract Groups

| Contract constant | Routes |
|---|---|
| `LOCAL_API_FILE_COMMAND_ROUTE_CONTRACT` | queue/scan, queue/priority, queue/strategy, queue/file-overrides, queue/file-overrides/route-preview, queue/file-overrides/series-preview, queue/file-overrides/series-apply, queue/file-overrides/remux-pilot-promote, queue/file-overrides/folder-preview, queue/file-overrides/folder-rule, failures/clear, queue/open, completed/open, subtitle-qa/preview, pending-publish/open, pending-publish/recovery-plan, completed/reconcile-manifest-dry-run, completed/reconcile-manifest, completed/repair-sidecar-metadata-dry-run, completed/repair-sidecar-metadata, pending-publish/repair-manifest-dry-run, pending-publish/repair-manifest, pending-publish/reconcile-orphan-payloads-dry-run, pending-publish/reconcile-orphan-payloads, startup/reconcile-dry-run, final-library-promotion/promote-queue, final-library-promotion/pause, final-library-promotion/resume |
| `LOCAL_API_MAINTENANCE_COMMAND_ROUTE_CONTRACT` | maintenance/release-dry-run, maintenance/release-build, maintenance/completed-backfill-dry-run, maintenance/retention-dry-run, maintenance/dependency-atlas, maintenance/dependency-atlas/open-folder, maintenance/archive-state-journals, maintenance/support-export |
| `LOCAL_API_METRICS_COMMAND_ROUTE_CONTRACT` | metrics/sources, metrics/backfill |
| `LOCAL_API_DIAGNOSTICS_COMMAND_ROUTE_CONTRACT` | diagnostics/open, diagnostics/tdarr-matrix-audit, diagnostics/tdarr-matrix/evidence/open, diagnostics/tdarr-matrix/rerun |
| `LOCAL_API_RENAME_COMMAND_ROUTE_CONTRACT` | rename/preview, rename/browse, rename/filter-cases, rename/apply |
| `LOCAL_API_SETTINGS_COMMAND_ROUTE_CONTRACT` | settings/validate, settings/preset-library/validate, settings/preset-library/compare, settings/preset-library/import-preview, settings/preset-library/save, settings/preset-library/export, settings/preset-library/apply-preview, settings/preset-library/apply, settings/browse-path, settings/preview-patch, settings/pipeline-plan-preview, settings/save-patch, settings/wizard/validate-paths, settings/wizard/validate-tools, settings/wizard/probe-hardware, settings/wizard/validate-workers, settings/wizard/preview, settings/wizard/save, settings/reload |
| `LOCAL_API_SCHEDULE_COMMAND_ROUTE_CONTRACT` | schedule/preview, schedule/save |
| `LOCAL_API_SAMPLE_VALIDATION_COMMAND_ROUTE_CONTRACT` | sample-validation/preview, sample-validation/append |
| `LOCAL_API_UI_COMMAND_ROUTE_CONTRACT` | ui-preferences |
| `LOCAL_API_PROCESS_COMMAND_ROUTE_CONTRACT` | pipeline/control, pipeline/browse-file, pipeline/start, audit/start, audit/score-policy, audit/ignore, audit/export-rerun-csv, rerun/start, backend/shutdown |
| `LOCAL_API_NETWORK_COMMAND_ROUTE_CONTRACT` | network/coordinator/start-dry-run, network/coordinator/stop-dry-run, network/coordinator/join-blob, network/worker/start-dry-run, network/worker/stop-dry-run, network/worker/test-connection, network/worker/discover-coordinators, network/worker/join-cluster, network/coordinator/start, network/coordinator/stop, network/worker/start, network/worker/stop |

---

## Full Command Route Matrix

### Queue Scan, State, And Override Preview

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/queue/scan` | Queue | `queueView.js` | `process-dry-run` | Starts or observes a serialized backend source scan; fast inventory writes non-launchable candidates before queue-plan curation refreshes authoritative rows |
| `POST /api/queue/priority` | Queue | `queueView.js` | `queue-state-write` | `level`: `high`, `normal`, `low`, `hold`; path writes must be under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots); `clear_all` clears manifest state only |
| `POST /api/queue/strategy` | Queue | `queueView.js` | `queue-state-write` | Strategy must be one of backend `VALID_STRATEGIES` |
| `POST /api/queue/file-overrides` | Queue | `queue/fileOverrides.drawer.js` | `queue-state-write` | Path writes must be under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots); `clear_all` clears the override manifest only |
| `POST /api/queue/file-overrides/route-preview` | Queue | `queue/fileOverrides.routePreview.js` | `read-only-preview` | Backend-scoped path under configured source roots plus proposed routing/video override; advisory only |
| `POST /api/queue/file-overrides/series-preview` | Queue | `queue/fileOverrides.drawer.js` | `read-only-preview` | Current queue snapshot only; selected TV row detects same source/show root, manual exact file overrides are reported as protected |
| `POST /api/queue/file-overrides/series-apply` | Queue | `queue/fileOverrides.drawer.js` | `queue-state-write` | Requires `confirm_apply: true` and matching `preview_fingerprint`; writes exact current-row file overrides only, preserving manual rows |
| `POST /api/queue/file-overrides/remux-pilot-promote` | Queue | `queue/fileOverrides.drawer.series.js` | `queue-state-write` | Requires exactly three selected pilot source paths plus `confirm_apply: true`; backend verifies completed oversized-encode fallback remux evidence before writing exact remaining current-row remux overrides only |
| `POST /api/queue/file-overrides/folder-preview` | Queue | `queue/fileOverrides.drawer.js` | `read-only-preview` | Folder under configured source roots; uses bounded known-file/cached-track evidence only |
| `POST /api/queue/file-overrides/folder-rule` | Queue | `queue/fileOverrides.drawer.js` | `queue-state-write` | Folder under configured source roots but not a source/library root; save requires explicit confirmation object |

Queue scan runs backend-owned inventory and dry-run curation, writing progress
evidence plus the authoritative queue snapshot. Queue state routes write JSON
state under `LocalBase\State`. None of these routes rename, move, delete,
launch processing work, publish, drain, or mutate source media.

### Failure Marker Cleanup

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/failures/clear` | Reports | `reportsView.js` | `failure-marker-write` | `confirm_clear: true` required unless `dry_run: true`; marker paths must resolve inside backend `State\Failures\Markers` |

Failure marker clear moves marker JSON out of the active marker folder and
writes a clear manifest. It does not delete media files, failure reports,
completed manifests, pending-publish files, or source/output paths.

### File Open And Pending Recovery

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/queue/open` | Queue | `queueView.js` | `shell-open` | `row_key` plus `target`; allowed targets: `source_file`, `source_folder`, `source_root` |
| `POST /api/completed/open` | Completed | `completedView.js` | `shell-open` | `row_key` plus `target`; allowed targets: `output_file`, `play_output_file`, `output_folder`, `sidecar`, `source_folder` |
| `POST /api/pending-publish/open` | Pending Publish | `pendingPublishView.diagnostics.js` | `shell-open` | `row_key` plus `target`; allowed targets: `local_file`, `manifest`, `destination_folder`, `source_folder` |
| `POST /api/pending-publish/recovery-plan` | Pending Publish | `pendingPublishView.recovery.js` | `none` | `scope`: `all` or `selected`; backend-authored dry-run only |

Backend resolves actual filesystem paths from state. The frontend submits row
keys and allowlisted target keys, not arbitrary paths.

### Subtitle QA Preview

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/subtitle-qa/preview` | Queue, Completed | No WebView caller; backend route only | `read-only-preview` | Reads already-loaded Queue and Completed subtitle QA evidence only; does not probe files, convert/OCR/sync subtitles, repair, rewrite sidecars, publish, drain, or touch media |

### Repair/Reconcile Dry-Run

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/completed/reconcile-manifest-dry-run` | Completed | `completedView.repair.js` dry-run control | `none` | Strict keys only: `scope`, `row_key`, `limit`, `reason`; backend-authored dry-run diff over loaded Completed preview manifest rows; unjournaled, and cannot rewrite manifests, write sidecars, publish, drain, move, delete, rerun, or touch source/scratch/output media |
| `POST /api/completed/reconcile-manifest` | Completed | Backend route; WebView confirmation control | `completed-manifest-write` | Strict keys only: `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply`; reruns the backend dry-run, requires `safe_to_apply: true`, matching fingerprint, idle pipeline, backup, and explicit confirmation before updating existing selected completed manifest rows only |
| `POST /api/completed/repair-sidecar-metadata-dry-run` | Completed | `completedView.repair.js` dry-run control | `none` | Strict keys only: `scope`, `row_key`, `limit`, `reason`; backend-authored dry-run diff over Completed sidecar metadata evidence; unjournaled, and cannot write sidecar JSON, rewrite manifests, publish, drain, move, delete, rerun, or touch source/scratch/output media |
| `POST /api/completed/repair-sidecar-metadata` | Completed | Backend route; WebView confirmation control | `completed-sidecar-json-write` | Strict keys only: `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply`; reruns the backend dry-run, requires `safe_to_apply: true`, matching fingerprint, idle pipeline, backup, and explicit confirmation before updating backend-derived sidecar metadata fields only |
| `POST /api/pending-publish/repair-manifest-dry-run` | Pending Publish | `pendingPublishView.repair.js` dry-run control | `none` | Strict keys only: `scope`, `row_key`, `limit`, `reason`; backend-authored dry-run diff over pending-publish scan, recovery classification, file inventory, and drain summary evidence; may emit validated manifest-normalization candidates, remains unjournaled, and cannot rewrite pending manifests, drain, publish, move, delete, rerun, or touch source/scratch/output media |
| `POST /api/pending-publish/repair-manifest` | Pending Publish | Backend route; WebView confirmation control | `pending-manifest-write` | Strict keys only: `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply`; reruns the backend dry-run, requires `safe_to_apply: true`, matching fingerprint, idle pipeline, backup, validated backend-derived manifest evidence, and explicit confirmation before writing selected pending manifest-normalization fields |
| `POST /api/pending-publish/reconcile-orphan-payloads-dry-run` | Pending Publish | `pendingPublishView.repair.js` dry-run control | `none` | Strict keys only: `scope`, `row_key`, `limit`, `reason`; backend-authored orphan payload evidence from pending-publish scan and file inventory, including missing `pending_push_manifest.v1` fields; `mutation_enabled: false`, unjournaled, and cannot create manifests, drain, publish, move, delete, rerun, or touch source/scratch/output media |
| `POST /api/pending-publish/reconcile-orphan-payloads` | Pending Publish | Backend route; WebView confirmation control | `pending-orphan-manifest-write` | Strict keys only: `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, `confirm_apply`; manifest-only reconcile route, blocked unless backend dry-run supplies a complete backend-derived `pending_push_manifest.v1` proposal; never moves, deletes, drains, publishes, or touches payload/source/output media |
| `POST /api/startup/reconcile-dry-run` | Diagnostics, Maintenance | No WebView caller; backend route only | `none` | Strict aggregate-only keys: `scope`, `limit`, `reason`; backend-authored startup reconciliation evidence over pending manifests, orphaned parked payloads, ActiveJobs, and SQLite mirror posture; `mutation_enabled: false`, `frontend_exposed: false`, unjournaled, and cannot repair, rewrite, migrate, rebuild, drain, publish, move, delete, rerun, or touch source/scratch/output media |

### Final Library Promotion

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/final-library-promotion/promote-queue` | Completed | `completedView.js` | `filesystem-mutation` | `confirm_promote: true` required; optional `row_keys` scopes promotion to selected Completed rows |
| `POST /api/final-library-promotion/pause` | Completed | `completedView.js` | `control-state-write` | `run_id` only; cooperative pause state for active promotion run |
| `POST /api/final-library-promotion/resume` | Completed | `completedView.js` | `control-state-write` | `run_id` only; resume paused backend-owned promotion run |

Final-library promotion remains backend-owned. The frontend cannot choose copy
destinations, eligibility, cleanup behavior, or media policy.

### Maintenance Commands

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/maintenance/release-dry-run` | Maintenance | `maintenanceView.js` | `process-dry-run` | Runs release builder with `-DryRun`; no release package is written |
| `POST /api/maintenance/release-build` | Maintenance | `maintenanceView.js` | `deployment-write` | `confirm_create: true` required; writes release deployment artifacts through backend builder |
| `POST /api/maintenance/completed-backfill-dry-run` | Maintenance | `maintenanceView.js` | `process-dry-run` | Runs backfill script with `-DryRun`; no completed manifest is written |
| `POST /api/maintenance/retention-dry-run` | Maintenance | No WebView caller; backend route only | `none` | Reports allowlisted log/state/temp/failure/cache cleanup candidates only; does not delete, move, archive, truncate, rewrite, drain, publish, or touch source/output/pending-publish media |
| `POST /api/maintenance/dependency-atlas` | Maintenance | `maintenanceView.js` | `tooling-artifact-write` | Writes generated dependency-atlas artifacts under `docs/generated/dependency-atlas/` only |
| `POST /api/maintenance/dependency-atlas/open-folder` | Maintenance | `maintenanceView.js` | `shell-open` | Opens fixed backend-resolved `docs/generated/dependency-atlas/`; request payload must be empty |
| `POST /api/maintenance/archive-state-journals` | Launch, Maintenance | `launchView.js` | `runtime-evidence-archive` | Requires `confirm_archive: true` and safe close-readiness; archives only backend-resolved `State\Progress\pipeline_events.jsonl` when oversized, then creates a fresh empty replacement; does not archive completed manifests, queue snapshots, progress files, pending-publish manifests/payloads, source media, scratch media, or final outputs |
| `POST /api/maintenance/support-export` | Maintenance | No WebView caller; backend route only | `diagnostics-artifact-write` | Writes a backend-owned redacted support export under per-user AppData DiagnosticsExports; includes product/version/update/migration/health evidence and bounded redacted log tails without private config, signing material, bearer tokens, unredacted personal paths, or media mutation |

### Metrics Commands

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/metrics/sources` | Metrics | `metricsView.js` | `metrics-state-write` | Adds/removes/enables/disables Metrics source roots in `State\Metrics`; does not scan or touch media |
| `POST /api/metrics/backfill` | Metrics | `metricsView.js` | `metrics-backfill-state-write` | Recursively reads configured `*.pipeline.json` sidecars and refreshes Metrics cache/status under `State\Metrics`; skips symlinked folders and does not rewrite sidecars or media |

### Diagnostics Commands

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/diagnostics/open` | Diagnostics | `diagnosticsView.js` | `shell-open` | `target` must be one of 20 allowlisted diagnostics keys |
| `POST /api/diagnostics/tdarr-matrix-audit` | Diagnostics | `diagnosticsView.js` | `diagnostic-process` | `action` must be one of `report`, `smoke`, `matrix`, `full`, `strict-report`; backend expands fixed Tdarr Matrix audit presets only |
| `POST /api/diagnostics/tdarr-matrix/evidence/open` | Diagnostics | `diagnosticsView.js` | `shell-open` | `run_id`, `finding_key`, and allowlisted evidence `target`; backend resolves the path inside the selected Tdarr Matrix run root |
| `POST /api/diagnostics/tdarr-matrix/rerun` | Diagnostics | `diagnosticsView.js` | `diagnostic-process` | `source_run_id`, `selection`, and finding keys only; backend maps findings to manifest case IDs and creates a fresh isolated run root |

Allowed targets: `run_logs`, `cluster_log`, `config`, `config_folder`,
`workspace`, `state`, `pending_publish`, `failed_reports`, `failed_markers`,
`audit_reports`, `queue_snapshot`, `active_jobs`, `completed_manifest`,
`latest_failure_report`, `latest_failure_json`, `latest_audit_csv`,
`latest_priority_csv`, `last_stdout_log`, `last_stderr_log`,
`sample_validation_log`.

### Rename

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/rename/preview` | Rename | `renameView.js` | `none` | Predictions only; no files touched |
| `POST /api/rename/browse` | Rename | `renameView.js` | `shell-dialog` | Allowed selection modes: `files`, `folder`, `folder_files`; stages selected paths only |
| `POST /api/rename/filter-cases` | Rename | `renameView.js` | `test-fixture-write` | `confirm_append: true` required; appends backend-validated cases to `tests/fixtures/rename/bad_rename_cases.jsonl` only; no media paths are touched |
| `POST /api/rename/apply` | Rename | `renameView.js` | `filesystem-mutation` | `confirm_apply: true` required; backend rebuilds plan from state; outside configured roots also require `allow_outside_configured_roots: true` |

### Settings

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/settings/validate` | Settings | `settingsView.js` | `none` | Validation only; no config written |
| `POST /api/settings/preset-library/validate` | Settings | `settingsView.js` | `none` | Validates an inline PresetV2 document without writing the preset library or active config |
| `POST /api/settings/preset-library/compare` | Settings | `settingsView.js` | `none` | Compares two preset records or inline PresetV2 documents through backend legacy-patch projection only |
| `POST /api/settings/preset-library/import-preview` | Settings | `settingsView.js` | `none` | Validates import candidate records and reports would-write state without writing `State/PresetLibrary/presets.json` |
| `POST /api/settings/preset-library/save` | Settings | `settingsView.js` | `preset-library-state-write` | Writes a PresetV2 record to backend State JSON only; does not save active PSD1 settings or launch work |
| `POST /api/settings/preset-library/export` | Settings | `settingsView.js` | `none` | Returns a preset record or inline preset export payload without writing state or config |
| `POST /api/settings/preset-library/apply-preview` | Settings | `settingsView.js` | `none` | Converts a PresetV2 record to a legacy settings patch and runs backend settings preview semantics without saving config |
| `POST /api/settings/preset-library/apply` | Settings | `settingsView.js` | `config-write` | Requires `confirm_apply: true`; converts PresetV2 to legacy settings patch and saves through the existing backend settings save path for future launches only |
| `POST /api/settings/browse-path` | Settings | `settingsView.js` | `shell-dialog` | Folder-only browser for allowlisted source/output/scratch and final-library promotion root fields; stages selected-folder evidence only |
| `POST /api/settings/preview-patch` | Settings; Network Worker Mode Settings | `settingsView.js`; `networkView.js` delegates to `window.mediaPipelineSettingsView` | `none` | Returns redacted diff; no config written |
| `POST /api/settings/pipeline-plan-preview` | Settings | `settingsView.js` | `none` | Strict source facts plus optional staged settings patch; backend-owned dry-run plan only |
| `POST /api/settings/save-patch` | Settings; Network Worker Mode Settings | `settingsView.js`; `networkView.js` delegates to `window.mediaPipelineSettingsView` | `config-write` | `confirm_save: true` required; backend backs up, writes, and reloads |
| `POST /api/settings/wizard/validate-paths` | Settings Wizard | `settingsView.js` | `none` | Wizard path validation only |
| `POST /api/settings/wizard/validate-tools` | Settings Wizard | `settingsView.js` | `none` | Wizard tool-path validation only |
| `POST /api/settings/wizard/probe-hardware` | Settings Wizard | `settingsView.js` | `none` | Bounded hardware probe evidence only |
| `POST /api/settings/wizard/validate-workers` | Settings Wizard | `settingsView.js` | `none` | Wizard worker/concurrency validation only |
| `POST /api/settings/wizard/preview` | Settings Wizard | `settingsView.js` | `none` | Generated patch preview only |
| `POST /api/settings/wizard/save` | Settings Wizard | `settingsView.js` | `config-write` | `confirm_save: true` required; writes through normal backend settings save path |
| `POST /api/settings/reload` | Settings | `settingsView.js` | `none` | Reloads in-memory backend state; no config written |

### Schedule

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/schedule/preview` | Schedule | `scheduleView.js` | `none` | Preview without writing app state |
| `POST /api/schedule/save` | Schedule | `scheduleView.js` | `app-state-write` | `confirm_save: true` required; writes schedule app-state keys only |

### Sample Validation

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/sample-validation/preview` | Home | `crossPageContextView.sampleValidation.js` | `none` | Preview warnings; no validation log written |
| `POST /api/sample-validation/append` | Home | `crossPageContextView.sampleValidation.js` | `validation-log-write` | Appends to validation JSONL only; does not accept output, clear failures, or touch media |

### UI Preferences

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/ui-preferences` | Chrome WebView, Tauri shell | `layoutManager.js`, `app.js` | `ui-state-write` | Writes allowlisted UI preference JSON only |

### Audit Controls

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/audit/score-policy` | Reports | `launchView.js` | `audit-state-write` | Backend normalizes score policy or resets to defaults; no queue/media mutation |
| `POST /api/audit/ignore` | Reports | `launchView.js` | `audit-state-write` | `action`: `add` or `remove`; writes audit-only ignore state, not queue holds |
| `POST /api/audit/export-rerun-csv` | Reports | `launchView.js` | `report-file-write` | Writes a backend-owned rerun CSV artifact; does not launch rerun work |

Audit controls are backend-owned report helpers. They cannot apply priority,
write file overrides, launch rerun work, save settings, or touch media files.

### Network Lifecycle

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/network/coordinator/start-dry-run` | Network | `networkView.js` | `none` | Reports coordinator start preconditions, state-file posture, active-work posture, and `would_not_touch` evidence only |
| `POST /api/network/coordinator/stop-dry-run` | Network | `networkView.js` | `none` | Reports coordinator stop preconditions and state preservation posture only |
| `POST /api/network/coordinator/join-blob` | Network | `networkView.js` | `secret-transfer` | Requires `confirm_create`; returns an unjournaled setup blob containing coordinator URL, worker auth token, and advertised libraries; optional token rotation also requires `confirm_rotate` |
| `POST /api/network/worker/start-dry-run` | Network | `networkView.js` | `none` | Reports worker coordinator URL, path-map, pending-done, provider, and no-touch posture only |
| `POST /api/network/worker/stop-dry-run` | Network | `networkView.js` | `none` | Reports worker stop and pending-done posture only |
| `POST /api/network/worker/test-connection` | Network | `networkView.js` | `none` | Runs read-only L1 TCP reachability, L2 signed `/api/ping` auth, and L3 configured source/output path access checks; does not claim work, start/stop lifecycle, scan queue, save settings, publish, drain, or touch media files |
| `POST /api/network/worker/discover-coordinators` | Network | `networkView.js` | `none` | Runs read-only mDNS coordinator discovery and returns selectable coordinator URLs for worker setup; selecting a row only stages `WorkerCoordinatorUrl` in the Settings patch until the operator previews/saves |
| `POST /api/network/worker/join-cluster` | Network | `networkView.js` | `config-write` | Requires `confirm_import`; imports a join blob through backend settings save, seeds library-ID-derived WorkerSourcePathMap entries when possible, then runs read-only worker test-connection; request/response are unjournaled because the blob contains a secret |
| `POST /api/network/coordinator/start` | Network | `networkView.js` | `backend-lifecycle` | Requires `confirm_start`; starts only the real coordinator lifecycle provider after backend preconditions pass |
| `POST /api/network/coordinator/stop` | Network | `networkView.js` | `backend-lifecycle` | Requires `confirm_stop`; preserves coordinator/worker state files and does not silently release active claims |
| `POST /api/network/worker/start` | Network | `networkView.js` | `backend-lifecycle` | Requires `confirm_start`; starts only worker polling for coordinator-assigned single-file claims, not normal Launch or local queue scanning |
| `POST /api/network/worker/stop` | Network | `networkView.js` | `backend-lifecycle` | Requires `confirm_stop`; preserves pending done reports and worker state; abort remains separate |

Confirmed Network lifecycle routes fail closed when the real lifecycle provider is
unavailable. They must not scan the full queue, launch normal processing, release
claims silently, or mutate source/scratch/output/pending-publish files.

### Process And Backend Lifecycle

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/pipeline/control` | Launch | `launchView.js` | `control-flag-write` | `action`: `pause`, `stop`, `rescan`, `kill`; backend owns flag writes and emergency process cleanup |
| `POST /api/pipeline/browse-file` | Launch | `launchView.js` | `shell-dialog` | `selection_mode`: `files`; backend owns native file browser and validates single-file staging only |
| `POST /api/pipeline/start` | Launch | `launchView.js` | `process-launch` | `mode`: `once`, `continuous`, `validate`, `drain_pending_pushes`; backend owns launch lock and process args |
| `POST /api/audit/start` | Launch | `launchView.js` | `process-launch` | Backend owns audit script invocation |
| `POST /api/rerun/start` | Launch | `launchView.js` | `process-launch` | Default safe: `stage_mode: copy`, `original_mode: keep`, `return_mode: park` |
| `POST /api/backend/shutdown` | App shell | `app.js`, Tauri shell | `backend-lifecycle` | Shell must check `GET /api/backend/close-readiness`; unsafe close is rejected unless `force_active_work_shutdown` is literal boolean `true` |

---

## Mutation Class Summary

| Class | Count | Routes |
|---|---:|---|
| `none` | 25 | pending-publish/recovery-plan, completed/reconcile-manifest-dry-run, completed/repair-sidecar-metadata-dry-run, pending-publish/repair-manifest-dry-run, pending-publish/reconcile-orphan-payloads-dry-run, startup/reconcile-dry-run, maintenance/retention-dry-run, rename/preview, settings/validate, settings/preview-patch, settings/pipeline-plan-preview, settings/wizard/validate-paths, settings/wizard/validate-tools, settings/wizard/probe-hardware, settings/wizard/validate-workers, settings/wizard/preview, settings/reload, schedule/preview, sample-validation/preview, network/coordinator/start-dry-run, network/coordinator/stop-dry-run, network/worker/start-dry-run, network/worker/stop-dry-run, network/worker/test-connection, network/worker/discover-coordinators |
| `read-only-preview` | 4 | queue/file-overrides/route-preview, queue/file-overrides/series-preview, queue/file-overrides/folder-preview, subtitle-qa/preview |
| `shell-open` | 6 | queue/open, completed/open, pending-publish/open, diagnostics/open, diagnostics/tdarr-matrix/evidence/open, maintenance/dependency-atlas/open-folder |
| `shell-dialog` | 3 | rename/browse, settings/browse-path, pipeline/browse-file |
| `test-fixture-write` | 1 | rename/filter-cases |
| `queue-state-write` | 6 | queue/priority, queue/strategy, queue/file-overrides, queue/file-overrides/series-apply, queue/file-overrides/remux-pilot-promote, queue/file-overrides/folder-rule |
| `failure-marker-write` | 1 | failures/clear |
| `audit-state-write` | 2 | audit/score-policy, audit/ignore |
| `report-file-write` | 1 | audit/export-rerun-csv |
| `validation-log-write` | 1 | sample-validation/append |
| `ui-state-write` | 1 | ui-preferences |
| `metrics-state-write` | 1 | metrics/sources |
| `metrics-backfill-state-write` | 1 | metrics/backfill |
| `app-state-write` | 1 | schedule/save |
| `config-write` | 3 | settings/save-patch, settings/wizard/save, network/worker/join-cluster |
| `secret-transfer` | 1 | network/coordinator/join-blob |
| `filesystem-mutation` | 2 | rename/apply, final-library-promotion/promote-queue |
| `control-state-write` | 2 | final-library-promotion/pause, final-library-promotion/resume |
| `control-flag-write` | 1 | pipeline/control |
| `process-dry-run` | 3 | queue/scan, maintenance/release-dry-run, maintenance/completed-backfill-dry-run |
| `diagnostic-process` | 2 | diagnostics/tdarr-matrix-audit, diagnostics/tdarr-matrix/rerun |
| `diagnostics-artifact-write` | 1 | maintenance/support-export |
| `runtime-evidence-archive` | 1 | maintenance/archive-state-journals |
| `tooling-artifact-write` | 1 | maintenance/dependency-atlas |
| `deployment-write` | 1 | maintenance/release-build |
| `process-launch` | 3 | pipeline/start, audit/start, rerun/start |
| `backend-lifecycle` | 5 | backend/shutdown, network/coordinator/start, network/coordinator/stop, network/worker/start, network/worker/stop |

---

## Command Risk Tiers

**Critical** - can move/copy filesystem outputs, rename files, drain parked
outputs, force process cleanup, or shut down the backend:

- `rename/apply`
- `final-library-promotion/promote-queue`
- `pipeline/start` with `mode: drain_pending_pushes`
- `backend/shutdown`

**High** - starts long-running work, writes live config, or creates release
deployment artifacts:

- `pipeline/start` with non-drain modes
- `audit/start`
- `rerun/start`
- `network/coordinator/start`, `network/coordinator/stop`, `network/worker/start`, `network/worker/stop`
- `settings/save-patch`
- `settings/wizard/save`
- `network/coordinator/join-blob`
- `network/worker/join-cluster`
- `maintenance/release-build`

**Medium** - writes bounded backend state or control signals:

- `queue/priority`, `queue/strategy`, `queue/file-overrides`, `queue/file-overrides/series-apply`, `queue/file-overrides/remux-pilot-promote`, `queue/file-overrides/folder-rule`
- `failures/clear`
- `pipeline/control`
- `schedule/save`
- `final-library-promotion/pause`, `final-library-promotion/resume`
- `audit/score-policy`, `audit/ignore`, `audit/export-rerun-csv`
- `diagnostics/tdarr-matrix-audit`, `diagnostics/tdarr-matrix/rerun`
- `maintenance/support-export`
- `maintenance/archive-state-journals`
- `maintenance/dependency-atlas`
- `metrics/sources`, `metrics/backfill`

**Low** - opens shell dialogs/locations, writes UI preferences, or appends
operator evidence only:

- All `*/open` routes
- `maintenance/dependency-atlas/open-folder`
- `rename/browse`
- `settings/browse-path`
- `pipeline/browse-file`
- `ui-preferences`
- `sample-validation/append`

**Safe** - read-only previews, validations, reloads, and dry-runs:

- All `*/preview`, `*/validate`, and `settings/reload` routes
- `settings/pipeline-plan-preview`
- `pending-publish/recovery-plan`
- `subtitle-qa/preview`
- repair/reconcile dry-run routes
- network lifecycle dry-run routes
- `network/worker/test-connection`
- `network/worker/discover-coordinators`
- ops/release/metadata/backfill/retention dry-run routes

Network-page Worker Mode Settings preview/save is config-only through the existing Settings routes above. Coordinator/worker start and stop use the Network Lifecycle routes above. Coordinator mDNS discovery and worker test-connection are read-only setup checks; coordinator join blob creation and worker join import are secret-handling setup commands. The unjournaled setup commands still cannot claim work, launch processing, publish, drain, or touch media files. Retry, reclaim, release, abort, and worker quarantine controls remain disabled until their backend routes exist.

---

## What The Frontend Cannot Own

The backend contract independently enforces:

- Path resolution for shell-open commands; the frontend passes row keys and allowlisted targets only.
- Queue source-path scope for priority and file-override writes.
- Explicit confirmation for rename apply, settings save, schedule save, release build, final-library promotion, folder-rule save, and failure marker clear.
- Launch locks and duplicate-command protection.
- Mode validation for pipeline start and pipeline control.
- Diagnostics target allowlist.
- Close-readiness before backend shutdown; force active-work cleanup requires literal JSON boolean `true`.

These are backend/API contract requirements, not frontend conventions.

---

## Freshness Review - 2026-06-05 (MDS-005)

Re-checked `COMMAND_ROUTE_METHODS`, `LOCAL_API_COMMAND_ROUTE_CONTRACT`, and
`COMMAND_ROUTE_PAYLOAD_MODELS`; all three contain the same POST route set,
including the backend-owned queue source scan route, subtitle QA preview route,
maintenance dependency-atlas folder-open route, and audit control routes.
This review refreshed the matrix for the queue source scan, route-preview,
series-preview, series-apply, folder-preview, folder-rule, audit controls,
Settings Wizard, pipeline-plan preview, UI preferences, and final-library
pause/resume routes, and records `folder_files` rename browse mode plus the
`kill` pipeline control action. The 2026-06-05 update adds Metrics source
registry and sidecar backfill command routes.

Validation anchor: `tests/python/desktop/test_api_command_contracts.py` now checks
that this matrix lists every route in `COMMAND_ROUTE_METHODS`.

## See Also

- Route details with auth: `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Full route inventory: `docs/inventories/API_ROUTE_INVENTORY.md`
- Mutation matrix: `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Diagnostics allowlist: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
