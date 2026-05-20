# Command Ownership Matrix

Date: 2026-05-20

Documents every POST command route in the Local API: the command type, owning backend contract group, owning frontend page, mutation class, and key restrictions. Source: `api/contract_command.py` (backend) and `apiPost` call inventory (frontend).

Total command routes: 28 POST routes across 8 contract groups.

Network lifecycle remains design-only and is intentionally absent from this command matrix. `/api/contract` publishes `network_lifecycle_contracts` for future coordinator/worker lifecycle gates, but no Network start/stop/reclaim/release/worker-polling POST route exists and no WebView Network lifecycle control is authorized until `Docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` is satisfied.

---

## Contract Groups

The backend organizes command routes into 8 groups in `contract_command.py`:

| Contract constant | Routes |
|---|---|
| `LOCAL_API_FILE_COMMAND_ROUTE_CONTRACT` | queue/priority, queue/strategy, queue/file-overrides, failures/clear, queue/open, completed/open, pending-publish/open, pending-publish/recovery-plan |
| `LOCAL_API_MAINTENANCE_COMMAND_ROUTE_CONTRACT` | maintenance/release-dry-run, maintenance/release-build, maintenance/completed-backfill-dry-run |
| `LOCAL_API_DIAGNOSTICS_COMMAND_ROUTE_CONTRACT` | diagnostics/open |
| `LOCAL_API_RENAME_COMMAND_ROUTE_CONTRACT` | rename/preview, rename/browse, rename/apply |
| `LOCAL_API_SETTINGS_COMMAND_ROUTE_CONTRACT` | settings/validate, settings/preview-patch, settings/save-patch, settings/reload |
| `LOCAL_API_SCHEDULE_COMMAND_ROUTE_CONTRACT` | schedule/preview, schedule/save |
| `LOCAL_API_SAMPLE_VALIDATION_COMMAND_ROUTE_CONTRACT` | sample-validation/preview, sample-validation/append |
| `LOCAL_API_PROCESS_COMMAND_ROUTE_CONTRACT` | pipeline/control, pipeline/start, audit/start, rerun/start, backend/shutdown |

---

## Full Command Route Matrix

### Group: Queue State (queue-state-write — non-destructive state manifests)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/queue/priority` | Queue | `queueView.js` | `queue-state-write` | `level`: `high`, `normal`, `low`, `hold`; path writes must be under `SourceMovies`/`SourceTV` |
| `POST /api/queue/strategy` | Queue | `queueView.js` | `queue-state-write` | Strategy must be one of the backend `VALID_STRATEGIES` names |
| `POST /api/queue/file-overrides` | Queue | `queueView.js` | `queue-state-write` | Path writes must be under `SourceMovies`/`SourceTV`; `clear_all` clears manifest only |

Queue state routes write JSON state under `LocalBase\State`. They do not rename, move, delete, launch, process, or mutate source media.

### Group: Failure Marker Clear (failure-marker-write — retry-blocker cleanup)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/failures/clear` | Reports | `reportsView.js` | `failure-marker-write` | `confirm_clear: true` required unless `dry_run: true`; marker paths must resolve inside backend `State\Failures\Markers` |

Failure marker clear moves marker JSON out of the active marker folder and writes a clear manifest. It does not delete media files, failure reports, completed manifests, pending publish files, or source/output paths.

### Group: File Open And Pending Recovery Plan (shell-open / dry-run — no media mutation)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/queue/open` | Queue | `queueView.js` | `shell-open` | `row_key` + `target`; allowed targets: `source_file`, `source_folder`, `source_root` |
| `POST /api/completed/open` | Completed | `completedView.js` | `shell-open` | `row_key` + `target`; allowed targets: `output_folder`, `sidecar`, `source_folder` |
| `POST /api/pending-publish/open` | Pending Publish | `pendingPublishView.diagnostics.js` | `shell-open` | `row_key` + `target`; allowed targets: `local_file`, `manifest`, `destination_folder`, `source_folder` |
| `POST /api/pending-publish/recovery-plan` | Pending Publish | `pendingPublishView.recovery.js` | `none` | `scope`: `all` or `selected`; backend-authored dry-run only |

Backend resolves the actual filesystem path from its own state. Frontend never passes a raw path.

### Group: Maintenance Commands (process-dry-run + deployment-write)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/maintenance/release-dry-run` | Maintenance | `maintenanceView.js` | `process-dry-run` | Runs `Build-MediaPipelineRemuxEncodeAIO-Release.ps1 -DryRun`; no release zip or folder written |
| `POST /api/maintenance/release-build` | Maintenance | `maintenanceView.js` | `deployment-write` | `confirm_create: true` required; writes release deployment artifacts through backend builder |
| `POST /api/maintenance/completed-backfill-dry-run` | Maintenance | `maintenanceView.js` | `process-dry-run` | Runs backfill script with `-DryRun`; no manifest written |

### Group: Diagnostics Open (shell-open — read-only)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/diagnostics/open` | Diagnostics | `diagnosticsView.js` | `shell-open` | `target` must be one of 20 allowlisted keys; no arbitrary path accepted |

20 allowlisted targets: `run_logs`, `cluster_log`, `config`, `config_folder`, `workspace`, `state`, `pending_publish`, `failed_reports`, `failed_markers`, `audit_reports`, `queue_snapshot`, `active_jobs`, `completed_manifest`, `latest_failure_report`, `latest_failure_json`, `latest_audit_csv`, `latest_priority_csv`, `last_stdout_log`, `last_stderr_log`, `sample_validation_log`.

See `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` for full per-target detail.

### Group: Rename (none + shell-dialog + filesystem-mutation)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/rename/preview` | Rename | `renameView.js` | `none` | Predictions only; no files touched |
| `POST /api/rename/browse` | Rename | `renameView.js` | `shell-dialog` | Opens native Windows file/folder browser and returns operator-selected paths for staging only |
| `POST /api/rename/apply` | Rename | `renameView.js` | `filesystem-mutation` | `confirm_apply: true` required; backend rebuilds plan from state; outside configured media roots also require `allow_outside_configured_roots: true` |

### Group: Settings (none + config-write)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/settings/validate` | Settings | `settingsView.js` | `none` | Validation only; no config written |
| `POST /api/settings/preview-patch` | Settings | `settingsView.js` | `none` | Returns redacted diff; no config written |
| `POST /api/settings/save-patch` | Settings | `settingsView.js` | `config-write` | `confirm_save: true` required; backend backs up before writing |
| `POST /api/settings/reload` | Settings | `settingsView.js` | `none` | Reloads in-memory backend state; no config written |

### Group: Schedule (none + app-state-write)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/schedule/preview` | Schedule | `scheduleView.js` | `none` | Preview without writing |
| `POST /api/schedule/save` | Schedule | `scheduleView.js` | `app-state-write` | `confirm_save: true` required; writes only `schedule_enabled`/`schedule_grid` app-state keys |

### Group: Sample Validation (none + validation-log-write)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/sample-validation/preview` | Home | `crossPageContextView.sampleValidation.js` | `none` | Preview warnings; no log written |
| `POST /api/sample-validation/append` | Home | `crossPageContextView.sampleValidation.js` | `validation-log-write` | Appends to `sample_validation_log.jsonl` only; does not accept, clear failures, or touch media |

### Group: Process (control-flag-write + process-launch + backend-lifecycle)

| Route | Owner page | Owner JS | Mutation class | Key restriction |
|---|---|---|---|---|
| `POST /api/pipeline/control` | Launch | `launchView.js` | `control-flag-write` | `action`: `pause`, `stop`, `rescan` only |
| `POST /api/pipeline/start` | Launch | `launchView.js` | `process-launch` | `mode`: `once`, `continuous`, `validate`, `drain_pending_pushes` |
| `POST /api/audit/start` | Launch | `launchView.js` | `process-launch` | Backend owns audit script invocation |
| `POST /api/rerun/start` | Launch | `launchView.js` | `process-launch` | Default safe: `stage_mode: copy`, `original_mode: keep`, `return_mode: park` |
| `POST /api/backend/shutdown` | App shell | `app.js` | `backend-lifecycle` | Shell must call `GET /api/backend/close-readiness` first; unsafe close-readiness is rejected unless explicit force cleanup is requested |

---

## Mutation Class Summary

| Class | Count | Routes |
|---|---|---|
| `shell-open` | 4 | queue/open, completed/open, pending-publish/open, diagnostics/open |
| `shell-dialog` | 1 | rename/browse |
| `queue-state-write` | 3 | queue/priority, queue/strategy, queue/file-overrides |
| `failure-marker-write` | 1 | failures/clear |
| `process-dry-run` | 2 | maintenance/release-dry-run, maintenance/completed-backfill-dry-run |
| `none` (preview/validation/dry-run) | 7 | pending-publish/recovery-plan, rename/preview, settings/validate, settings/preview-patch, settings/reload, schedule/preview, sample-validation/preview |
| `validation-log-write` | 1 | sample-validation/append |
| `app-state-write` | 1 | schedule/save |
| `config-write` | 1 | settings/save-patch |
| `filesystem-mutation` | 1 | rename/apply |
| `control-flag-write` | 1 | pipeline/control |
| `process-launch` | 3 | pipeline/start, audit/start, rerun/start |
| `backend-lifecycle` | 1 | backend/shutdown |

---

## Command Risk Tiers

**Critical** — can delete or irrecoverably change data, or shut down the backend:
- `rename/apply` (filesystem mutation — irreversible without undo manifest)
- `pipeline/start` with `mode: drain_pending_pushes` (moves parked outputs)
- `backend/shutdown`

**High** — spawns a long-running process or writes live config:
- `pipeline/start` (once/continuous/validate)
- `audit/start`
- `rerun/start`
- `settings/save-patch`

**Medium** — writes bounded state or a transient flag the pipeline reads:
- `queue/priority`, `queue/strategy`, `queue/file-overrides` (non-destructive queue state JSON)
- `failures/clear` (moves retry-blocker marker JSON out of the active marker folder)
- `pipeline/control` (pause/stop/rescan)
- `schedule/save` (writes schedule app-state keys only)

**Low** — shell opens or log appends; no media mutation:
- All `*/open` routes
- `rename/browse`
- `sample-validation/append`

**Safe** — read-only previews and validations:
- All `*/preview`, `*/validate`, `*/reload` routes
- All dry-run routes

---

## What the Frontend Cannot Own

The backend contract independently enforces:
- Path resolution (frontend passes `row_key` + allowlisted `target` key — never raw paths)
- Queue source-path scope (priority/file-overrides path writes must be absolute and under configured `SourceMovies`/`SourceTV`)
- `confirm_apply` / `confirm_save` requirements
- Launch-lock and duplicate-command protection
- Mode validation for pipeline/start
- Diagnostics target allowlist (20 keys only)
- Close-readiness before shutdown

These are not frontend conventions — they are enforced at the API contract layer regardless of frontend state.

---

## See Also

- Route details with auth: `Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Mutation matrix: `Docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Frontend apiPost review: `Docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md`
- Diagnostics allowlist: `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`

---

## Freshness Review — 2026-05-15 (CLN3-012)

Re-checked all 22 POST routes and their owner mappings against current JS exports and backend contract groups. Superseded by the current 2026-05-20 command matrix: 28 POST routes are now documented above, including queue state routes, backend shutdown, deployment build, Reports-owned marker clear, and Rename-owned `rename/browse` shell-dialog staging.

| Check | Result |
|---|---|
| `sample-validation/preview` mapped to Home / `crossPageContextView.sampleValidation.js` | Pass — correct; preview is a `none`-class route |
| `sample-validation/append` mapped to Home / `crossPageContextView.sampleValidation.js` | Pass — correct; `validation-log-write` class; does not touch media |
| `pipeline.start` still mapped to Launch / `launchView.js` | Pass |
| `rename.apply` still mapped to Rename / `renameView.js` | Pass |
| `settings.save_patch` still mapped to Settings / `settingsView.js` | Pass |
| New routes not in matrix | Superseded — queue/priority, queue/strategy, and queue/file-overrides are now documented as queue-state-write routes |

**Note on command journal recording**: `sample_validation.append` is recorded in the command journal (as a 2xx success response). It appears in WebView Command History under the `sample_validation` owner page routing in `commandHistory.js`. This is consistent with the recording policy — `sample-validation/preview` uses `"effect": "none"` and its 2xx responses would technically be recorded but are low-risk ephemeral previews.

```
Task ID: CLN3-012
Files inspected: Docs\inventories\COMMAND_OWNERSHIP_MATRIX.md, Docs\archive\completed-audits\COMMAND_HISTORY_CONSISTENCY_AUDIT.md, DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js (reference)
Files changed: Docs\inventories\COMMAND_OWNERSHIP_MATRIX.md (freshness note added)
Validation: Select-String -Path Docs\inventories\COMMAND_OWNERSHIP_MATRIX.md,Docs\archive\completed-audits\COMMAND_HISTORY_CONSISTENCY_AUDIT.md -Pattern "sample_validation|pipeline.start|settings.save|rename.apply"
Findings: All 22 routes correctly mapped. sample_validation.append correctly classified as validation-log-write. No new routes found.
Open questions: None.
Risk: Low — documentation only.
```
