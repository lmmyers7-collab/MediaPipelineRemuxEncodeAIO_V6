# Command Ownership Matrix

Date: 2026-06-01

Documents every POST command route in the Local API: command type, backend
contract group, primary frontend owner, mutation class, and key restrictions.
Source: `DesktopApp/mediapipeline_desktop_app/api/contract_command.py`,
`app/api/commands.py`, and the WebView `apiPost` call inventory.

Total command routes: 45 POST routes across 9 contract groups.

Network lifecycle and repair/reconcile mutation controls remain design-only.
`/api/contract` publishes future contract gates for those areas, but no Network
start/stop/reclaim/release/worker-polling POST route and no repair/reconcile
POST route is authorized until the matching architecture contract is satisfied.

---

## Contract Groups

| Contract constant | Routes |
|---|---|
| `LOCAL_API_FILE_COMMAND_ROUTE_CONTRACT` | queue/priority, queue/strategy, queue/file-overrides, queue/file-overrides/route-preview, queue/file-overrides/folder-preview, queue/file-overrides/folder-rule, failures/clear, queue/open, completed/open, pending-publish/open, pending-publish/recovery-plan, final-library-promotion/promote-queue, final-library-promotion/pause, final-library-promotion/resume |
| `LOCAL_API_MAINTENANCE_COMMAND_ROUTE_CONTRACT` | maintenance/release-dry-run, maintenance/release-build, maintenance/completed-backfill-dry-run, maintenance/dependency-atlas |
| `LOCAL_API_DIAGNOSTICS_COMMAND_ROUTE_CONTRACT` | diagnostics/open |
| `LOCAL_API_RENAME_COMMAND_ROUTE_CONTRACT` | rename/preview, rename/browse, rename/apply |
| `LOCAL_API_SETTINGS_COMMAND_ROUTE_CONTRACT` | settings/validate, settings/browse-path, settings/preview-patch, settings/pipeline-plan-preview, settings/save-patch, settings/wizard/validate-paths, settings/wizard/validate-tools, settings/wizard/probe-hardware, settings/wizard/validate-workers, settings/wizard/preview, settings/wizard/save, settings/reload |
| `LOCAL_API_SCHEDULE_COMMAND_ROUTE_CONTRACT` | schedule/preview, schedule/save |
| `LOCAL_API_SAMPLE_VALIDATION_COMMAND_ROUTE_CONTRACT` | sample-validation/preview, sample-validation/append |
| `LOCAL_API_UI_COMMAND_ROUTE_CONTRACT` | ui-preferences |
| `LOCAL_API_PROCESS_COMMAND_ROUTE_CONTRACT` | pipeline/control, pipeline/browse-file, pipeline/start, audit/start, rerun/start, backend/shutdown |

---

## Full Command Route Matrix

### Queue State And Override Preview

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/queue/priority` | Queue | `queueView.js` | `queue-state-write` | `level`: `high`, `normal`, `low`, `hold`; path writes must be under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots); `clear_all` clears manifest state only |
| `POST /api/queue/strategy` | Queue | `queueView.js` | `queue-state-write` | Strategy must be one of backend `VALID_STRATEGIES` |
| `POST /api/queue/file-overrides` | Queue | `queueView.js` | `queue-state-write` | Path writes must be under configured source roots (`SourceMovies`, `SourceTV`, or enabled `LibraryProfiles` source roots); `clear_all` clears the override manifest only |
| `POST /api/queue/file-overrides/route-preview` | Queue | `queueView.js` | `read-only-preview` | Backend-scoped path under configured source roots plus proposed routing/video override; advisory only |
| `POST /api/queue/file-overrides/folder-preview` | Queue | `queueView.js` | `read-only-preview` | Folder under configured source roots; uses bounded known-file/cached-track evidence only |
| `POST /api/queue/file-overrides/folder-rule` | Queue | `queueView.js` | `queue-state-write` | Folder under configured source roots but not a source/library root; save requires explicit confirmation object |

Queue state routes write JSON state under `LocalBase\State`. They do not
rename, move, delete, launch, process, scan whole source folders, or mutate
source media.

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
| `POST /api/completed/open` | Completed | `completedView.js` | `shell-open` | `row_key` plus `target`; allowed targets: `output_file`, `output_folder`, `sidecar`, `source_folder` |
| `POST /api/pending-publish/open` | Pending Publish | `pendingPublishView.diagnostics.js` | `shell-open` | `row_key` plus `target`; allowed targets: `local_file`, `manifest`, `destination_folder`, `source_folder` |
| `POST /api/pending-publish/recovery-plan` | Pending Publish | `pendingPublishView.recovery.js` | `none` | `scope`: `all` or `selected`; backend-authored dry-run only |

Backend resolves actual filesystem paths from state. The frontend submits row
keys and allowlisted target keys, not arbitrary paths.

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
| `POST /api/maintenance/dependency-atlas` | Maintenance | `maintenanceView.js` | `tooling-artifact-write` | Writes generated dependency-atlas artifacts only |

### Diagnostics Open

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/diagnostics/open` | Diagnostics | `diagnosticsView.js` | `shell-open` | `target` must be one of 20 allowlisted diagnostics keys |

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
| `POST /api/rename/apply` | Rename | `renameView.js` | `filesystem-mutation` | `confirm_apply: true` required; backend rebuilds plan from state; outside configured roots also require `allow_outside_configured_roots: true` |

### Settings

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/settings/validate` | Settings | `settingsView.js` | `none` | Validation only; no config written |
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
| `none` | 13 | pending-publish/recovery-plan, rename/preview, settings/validate, settings/preview-patch, settings/pipeline-plan-preview, settings/wizard/validate-paths, settings/wizard/validate-tools, settings/wizard/probe-hardware, settings/wizard/validate-workers, settings/wizard/preview, settings/reload, schedule/preview, sample-validation/preview |
| `read-only-preview` | 2 | queue/file-overrides/route-preview, queue/file-overrides/folder-preview |
| `shell-open` | 4 | queue/open, completed/open, pending-publish/open, diagnostics/open |
| `shell-dialog` | 3 | rename/browse, settings/browse-path, pipeline/browse-file |
| `queue-state-write` | 4 | queue/priority, queue/strategy, queue/file-overrides, queue/file-overrides/folder-rule |
| `failure-marker-write` | 1 | failures/clear |
| `validation-log-write` | 1 | sample-validation/append |
| `ui-state-write` | 1 | ui-preferences |
| `app-state-write` | 1 | schedule/save |
| `config-write` | 2 | settings/save-patch, settings/wizard/save |
| `filesystem-mutation` | 2 | rename/apply, final-library-promotion/promote-queue |
| `control-state-write` | 2 | final-library-promotion/pause, final-library-promotion/resume |
| `control-flag-write` | 1 | pipeline/control |
| `process-dry-run` | 2 | maintenance/release-dry-run, maintenance/completed-backfill-dry-run |
| `tooling-artifact-write` | 1 | maintenance/dependency-atlas |
| `deployment-write` | 1 | maintenance/release-build |
| `process-launch` | 3 | pipeline/start, audit/start, rerun/start |
| `backend-lifecycle` | 1 | backend/shutdown |

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
- `settings/save-patch`
- `settings/wizard/save`
- `maintenance/release-build`

**Medium** - writes bounded backend state or control signals:

- `queue/priority`, `queue/strategy`, `queue/file-overrides`, `queue/file-overrides/folder-rule`
- `failures/clear`
- `pipeline/control`
- `schedule/save`
- `final-library-promotion/pause`, `final-library-promotion/resume`
- `maintenance/dependency-atlas`

**Low** - opens shell dialogs/locations, writes UI preferences, or appends
operator evidence only:

- All `*/open` routes
- `rename/browse`
- `settings/browse-path`
- `pipeline/browse-file`
- `ui-preferences`
- `sample-validation/append`

**Safe** - read-only previews, validations, reloads, and dry-runs:

- All `*/preview`, `*/validate`, and `settings/reload` routes
- `settings/pipeline-plan-preview`
- `pending-publish/recovery-plan`
- release/backfill dry-run routes

Network-page Worker Mode Settings preview/save is config-only through the existing Settings routes above. It is not a Network lifecycle command surface and does not authorize coordinator/worker start, stop, retry, reclaim, release, abort, or worker-polling controls.

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

## Freshness Review - 2026-06-01 (MDS-005)

Re-checked `COMMAND_ROUTE_METHODS`, `LOCAL_API_COMMAND_ROUTE_CONTRACT`, and
`COMMAND_ROUTE_PAYLOAD_MODELS`; all three contain the same 45 POST routes.
This review refreshed the matrix for the route-preview, folder-preview,
folder-rule, Settings Wizard, pipeline-plan preview, UI preferences, and
final-library pause/resume routes, and records `folder_files` rename browse
mode plus the `kill` pipeline control action.

Validation anchor: `DesktopApp/tests/test_api_command_contracts.py` now checks
that this matrix lists every route in `COMMAND_ROUTE_METHODS`.

## See Also

- Route details with auth: `Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Full route inventory: `Docs/inventories/API_ROUTE_INVENTORY.md`
- Mutation matrix: `Docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Diagnostics allowlist: `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
