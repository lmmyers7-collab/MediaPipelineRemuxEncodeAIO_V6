# Local API Evidence vs Mutation Matrix

Companion to `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`. This document separates every route into its mutation class, states whether the frontend can own the behavior, and notes the key restriction on each command route.

Total routes: 98 (42 read, 56 command). Source of truth remains `LOCAL_API_ROUTE_CONTRACT`, assembled from `contract_read.py` and `contract_command.py`.

---

## Read Routes (GET) - Evidence Only

All GET routes are read-only. None touch media, launch pipeline work, write config, or change queue/manifest state. The exception is `GET /api/maintenance`, which runs bounded read-only tool probes and is marked `bounded-health-check`.

### Status Routes

| Route | Class | Frontend can own? | Key restriction |
|---|---|---|---|
| `GET /api/health` | `read` | No | Public startup probe before the token is passed to WebView |
| `GET /api/contract` | `read` | No | Self-describing route contract; Tauri validates before opening WebView |
| `GET /api/snapshot` | `read` | No | Backend assembles pipeline, audit, and process state |
| `GET /api/telemetry` | `read` | No | CPU/RAM/GPU sample cached by backend |
| `GET /api/diagnostics` | `read` | No | Recent backend events, errors, and launch-log summary |
| `GET /api/diagnostics/tail` | `read` | No | `target` must be allowlisted; `max_bytes` is capped at 256 KB; no arbitrary path accepted |
| `GET /api/diagnostics/state-summary` | `read` | No | Bounded inline artifact summary; no arbitrary path accepted |
| `GET /api/backend/close-readiness` | `read` | No | Backend has authority over safe-to-close; shell must not decide unilaterally |
| `GET /api/ui-preferences` | `read` | No | Reads shared UI customization only; no settings, queue, or media mutation |
| `GET /api/launch/preflight` | `read` | No | Backend-authored pre-launch checks; no locks reserved, no processes started |
| `GET /api/commands` | `read` | No | Recent command journal entries; bounded query |

### Inventory Routes

| Route | Class | Frontend can own? | Key restriction |
|---|---|---|---|
| `GET /api/queue` | `read` | No | Latest backend queue snapshot plus queue-scan status and source-inventory evidence; no dry run spawned |
| `GET /api/queue/priority` | `read` | No | Reads backend-owned priority manifest; no queue/media mutation |
| `GET /api/queue/strategy` | `read` | No | Reads backend-owned strategy state and valid strategy names |
| `GET /api/queue/file-overrides` | `read` | No | Reads override manifest or one source-root-contained override entry |
| `GET /api/queue/file-overrides/effective` | `read` | No | Reads inherited/effective override metadata for one source-root-contained path; no manifest write |
| `GET /api/queue/file-overrides/tracks` | `read` | No | Reads normalized track metadata for one source-root-contained path; no queue preview mutation |
| `GET /api/completed` | `read` | No | Completed-jobs manifest; no output-share scan |
| `GET /api/subtitle-qa/summary` | `read` | No | Backend-authored subtitle QA evidence already loaded in Queue and Completed payloads; no probing, conversion, repair, or media touch |
| `GET /api/subtitle-qa/item` | `read` | No | One loaded Queue or Completed row's subtitle QA evidence by backend row key/source/output identity; no arbitrary path probing or mutation |
| `GET /api/metrics` | `read` | No | Backend aggregates completed manifest, pending publish, worker runtime, and final-library promotion evidence; no launch, drain, promote, settings, queue, or media mutation |
| `GET /api/final-library-promotion/status` | `read` | No | Reads final-library promotion readiness/run state; no copy, move, delete, or cleanup action |
| `GET /api/failures` | `read` | No | Failure markers and reports; query-bounded |
| `GET /api/audit-results` | `read` | No | Audit CSV preview; no rerun CSV written |
| `GET /api/audit-controls` | `read` | No | Reads audit score policy and audit-only ignore state; no save/export/media mutation |
| `GET /api/rename/movie-cleaning-filters` | `read` | No | Reads backend-owned movie filename cleaning filter catalog only |
| `GET /api/rename/clean-filename-preview` | `read` | No | Read-only clean-filename preview; accepts query fields and writes nothing |
| `GET /api/pending-publish` | `read` | No | Reads manifests and parked payloads; does not drain |
| `GET /api/publish-reconciliation` | `read` | No | Correlates Completed, Pending Publish, and durable drain-summary evidence; no repair, drain, publish, or write action |

### Workspace Routes

| Route | Class | Frontend can own? | Key restriction |
|---|---|---|---|
| `GET /api/maintenance` | `bounded-health-check` | No | Runs existing env/tool probes; does not repair, install, remove, or change anything |
| `GET /api/maintenance/progress` | `read` | No | Reads latest maintenance health-progress state; does not run probes or repair |
| `GET /api/maintenance/change-ledger` | `read` | No | Reads structured change-control packets, changelog source status, and hygiene; no probes, codegen, packet writes, or media/state mutation |
| `GET /api/schedule` | `read` | No | Reads persisted schedule state; does not save or edit |
| `GET /api/settings/workspace` | `read` | No | Read-only, redacted settings snapshot |
| `GET /api/libraries/route-map` | `read` | No | Backend-authored Library Route Map and decision-matrix evidence only; no save, launch, plugin execution, queue mutation, or media touch |
| `GET /api/libraries/route-map/trace` | `read` | No | Selected-file trace from existing Queue, Completed, and Sample Validation row evidence only; no probing, launch, save, repair, drain, rename, or media mutation |
| `GET /api/libraries/route-map/compare` | `read` | No | Backend-authored Library Profile diff with explicit/inherited evidence and designation filtering; no staging or saving |
| `GET /api/libraries/route-map/validation` | `read` | No | Validation handoff evidence keeps Sample Validation, Completed, Pending Publish, Diagnostics, and command proof distinct; no launch, drain, accept, repair, rename, save, plugin execution, or media mutation |
| `GET /api/settings/wizard/status` | `read` | No | Reads wizard availability and first-run recommendation state only |
| `GET /api/settings/wizard/defaults` | `read` | No | Reads wizard defaults and tool candidates only |
| `GET /api/network/workers` | `read` | No | Coordinator/worker persisted state; no lifecycle controls |
| `GET /api/sample-validation` | `read` | No | Recent validation records plus backend-authored readiness, reconciliation, worksheet, sample-set, evidence-gap, pilot-runbook, saved-policy-alignment, and validation-audit evidence; query-bounded; no acceptance, repair, arbitrary media scan, or media/state mutation |

---

## Command Routes (POST) - Classified by Mutation Class

All POST routes require authentication. The frontend can submit allowlisted request fields, but it cannot own the operation, resolve paths directly, write state directly, launch processes, scan sources independently, or choose media policy.

### process-dry-run (backend source scan)

Runs backend-owned source inventory and queue-plan dry-run behavior. It writes scan evidence and an authoritative queue snapshot, but it does not process, rename, move, delete, publish, drain, or mutate source media.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/queue/scan` | `process-dry-run` | Frontend cannot enumerate launchable queue rows or run queue policy independently | `mode`: `inventory_then_curate`, `inventory_only`, or `curate_only`; `scope`: `all`; duplicate requests observe the active backend scan |

### metrics-state-write / metrics-backfill-state-write (Metrics state only)

Writes backend-owned Metrics source registry, cache, and status files under `State\Metrics`. Backfill recursively reads configured sidecar roots but does not rewrite sidecars, launch work, change queue state, drain, publish, rename, or touch media files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/metrics/sources` | `metrics-state-write` | Frontend cannot persist Metrics source roots directly | `action`: `add`, `remove`, `enable`, or `disable`; registry writes stay under `State\Metrics` |
| `POST /api/metrics/backfill` | `metrics-backfill-state-write` | Frontend cannot recursively scan sidecars independently | `scope`: `enabled` or `all`, or one configured `source_id`; reads `*.pipeline.json` only and writes Metrics cache/status under `State\Metrics` |

### queue-state-write (medium risk, non-destructive source state)

Writes backend-owned queue state manifests. These routes never rename, move, delete, launch, process, or mutate source media, and path-bearing writes must stay under configured `SourceMovies` or `SourceTV` roots.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/queue/priority` | `queue-state-write` | Frontend cannot write priority manifests directly | `path`/`items` must be absolute source-root-contained paths; `level` is limited to `high`, `normal`, `low`, or `hold`; `clear_all` clears priority manifest state only |
| `POST /api/queue/strategy` | `queue-state-write` | Frontend cannot write queue strategy state directly | `strategy` must be one of the backend-declared valid strategy names |
| `POST /api/queue/file-overrides` | `queue-state-write` | Frontend cannot write per-file media-policy override manifests directly | `path` must be source-root-contained unless `clear_all` is requested; writes non-destructive audio/subtitle/routing/video override metadata only |
| `POST /api/queue/file-overrides/series-apply` | `queue-state-write` | Frontend cannot decide or write series batch override scope directly | Requires `confirm_apply: true` plus a matching backend preview fingerprint; writes exact overrides only for eligible current queue rows, protects exact manual rows, and creates no future show/folder policy |
| `POST /api/queue/file-overrides/folder-rule` | `queue-state-write` | Frontend cannot write folder override manifests directly | `folder_path` must be under source roots but not a source/library root; raw FFmpeg map fields and file-only stream indexes are rejected; explicit confirmation evidence is required |

### read-only-preview (no output or state written)

Returns backend-authored previews. No files, manifests, config, or queue state are changed.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/queue/file-overrides/route-preview` | `read-only-preview` | Frontend cannot decide media route impact | Backend uses a source-root-contained path plus proposed override; advisory only |
| `POST /api/queue/file-overrides/series-preview` | `read-only-preview` | Frontend cannot infer or approve TV series batch scope independently | Backend uses the current queue snapshot, selected TV path, same source/show root detection, manual-protection evidence, and a preview fingerprint; no state write |
| `POST /api/queue/file-overrides/folder-preview` | `read-only-preview` | Frontend cannot scan or approve folder rules independently | Backend uses bounded known-file/cached-track evidence only; no source folder scan or state write |
| `POST /api/subtitle-qa/preview` | `read-only-preview` | Frontend cannot probe, convert, repair, or author subtitle QA evidence | Backend reads already-loaded Queue and Completed subtitle QA evidence only; no sidecar rewrite, publish, drain, or media touch |

### failure-marker-write (medium risk, retry-blocker state)

Moves backend-owned failure marker JSON out of the active marker folder after explicit confirmation. This lets the next queue build retry those sources. It does not delete media, failure reports, completed manifests, pending publish state, or source/output files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/failures/clear` | `failure-marker-write` | Frontend cannot delete or move marker files directly | `confirm_clear` required unless `dry_run` is true; marker paths must resolve inside backend `State\Failures\Markers` |

### shell-open (no media mutation)

Opens a file or folder in the OS shell. Backend resolves the path from its own state using `row_key` plus an allowlisted `target` key, or from a fixed backend-owned artifact folder. The frontend cannot pass a raw filesystem path.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/queue/open` | `shell-open` | Frontend cannot select the path directly | Allowed targets: `source_file`, `source_folder`, `source_root` |
| `POST /api/completed/open` | `shell-open` | Frontend cannot select the path directly | Allowed targets: `output_file`, `output_folder`, `sidecar`, `source_folder` |
| `POST /api/pending-publish/open` | `shell-open` | Frontend cannot select the path directly | Allowed targets: `local_file`, `manifest`, `destination_folder`, `source_folder` |
| `POST /api/diagnostics/open` | `shell-open` | Frontend cannot select arbitrary files | `target` must be one of the diagnostics allowlist keys; see `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` |
| `POST /api/maintenance/dependency-atlas/open-folder` | `shell-open` | Frontend cannot select arbitrary files | Opens fixed backend-resolved `docs/generated/dependency-atlas/`; request payload must be empty |

### diagnostic-process (scratch test harness)

Runs a backend-owned developer diagnostic process against scratch test-library roots. The frontend supplies a preset action only and cannot provide paths, tool arguments, source-delete settings, live operator config, or output destinations.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/diagnostics/tdarr-matrix-audit` | `diagnostic-process` | Frontend cannot construct commands or choose paths | `action`: `report`, `smoke`, `matrix`, `full`, or `strict-report`; backend expands fixed Tdarr Matrix audit presets under `LocalBase/Scratch/TestLibraries` |

### shell-dialog (no media mutation)

Opens a backend-owned native Windows dialog and returns operator-selected paths for staging. The dialog result does not preview, rename, move, delete, save settings, or touch media files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/rename/browse` | `shell-dialog` | Frontend cannot enumerate or mutate files directly | `selection_mode`: `files`, `folder`, or `folder_files`; selected paths are staged only and must still go through `rename/preview` and guarded `rename/apply` |
| `POST /api/settings/browse-path` | `shell-dialog` | Frontend cannot browse or resolve settings paths directly | Folder-only browser for allowlisted source/output/scratch and final-library promotion root settings; result is staged evidence only and does not save config |
| `POST /api/pipeline/browse-file` | `shell-dialog` | Frontend cannot browse or validate single-file paths directly | File-only browser for Launch single-file staging; result does not save config, launch work, mutate queue state, or touch media |

### dry-run / validation / preview (effect `none`)

Returns backend-computed plans, diffs, validation results, or reload status. No files are moved, created, published, deleted, or written.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/pending-publish/recovery-plan` | `none` | Frontend cannot author the plan | `scope`: `all` or `selected` only; dry-run result is read-only |
| `POST /api/rename/preview` | `none` | Frontend cannot run pipeline rename planning | Predictions only; no files touched |
| `POST /api/settings/validate` | `none` | Frontend cannot validate config schema independently | Validation only |
| `POST /api/settings/preview-patch` | `none` | Frontend cannot diff or persist config independently | Returns redacted diff; no config written |
| `POST /api/settings/pipeline-plan-preview` | `none` | Frontend cannot make source/probe/media-policy decisions | Validates supplied source facts and staged patch; returns backend-owned dry-run plan only |
| `POST /api/settings/wizard/validate-paths` | `none` | Frontend cannot validate wizard paths independently | Validation only |
| `POST /api/settings/wizard/validate-tools` | `none` | Frontend cannot validate tool paths independently | Validation only |
| `POST /api/settings/wizard/probe-hardware` | `none` | Frontend cannot run hardware probes independently | Bounded backend hardware probe evidence only |
| `POST /api/settings/wizard/validate-workers` | `none` | Frontend cannot decide worker/concurrency policy independently | Validation only |
| `POST /api/settings/wizard/preview` | `none` | Frontend cannot generate authoritative config patches independently | Generated patch preview only |
| `POST /api/settings/reload` | `none` | Frontend cannot reload in-memory backend state directly | Backend reloads cached state; no config written |
| `POST /api/schedule/preview` | `none` | Frontend cannot parse or validate schedule windows independently | Backend parses schedule input and returns changed days; no app-state write |
| `POST /api/sample-validation/preview` | `none` | Frontend cannot run sample validation logic independently | Preview warnings and evidence reconciliation only; no validation log append |

### app-state-write / ui-state-write (non-media app state)

Writes bounded desktop app state. These routes cannot save media settings, mutate queue state, launch work, drain, rename, publish, or touch media files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/schedule/save` | `app-state-write` | Frontend cannot write app-state JSON directly | `confirm_save` required; backend writes only schedule app-state keys |
| `POST /api/ui-preferences` | `ui-state-write` | Frontend cannot write arbitrary state directly | Stores allowlisted UI preference keys only, such as layout/theme/tab state, under app state |

### control-state-write / control-flag-write (medium risk)

Writes backend-owned control state or control flag files. The running pipeline or promotion process reads these signals cooperatively.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/final-library-promotion/pause` | `control-state-write` | Frontend cannot edit promotion state directly | `run_id` only; pauses an active backend-owned promotion run |
| `POST /api/final-library-promotion/resume` | `control-state-write` | Frontend cannot edit promotion state directly | `run_id` only; resumes a paused backend-owned promotion run |
| `POST /api/pipeline/control` | `control-flag-write` | Frontend cannot write flag files or kill processes directly | `action`: `pause`, `stop`, `rescan`, or `kill`; backend owns flag writes and emergency cleanup |

### validation-log-write (low risk, evidence only)

Appends to the operator evidence log. It does not mark jobs complete, clear failures, accept output, drain pending publish, or mutate media.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/sample-validation/append` | `validation-log-write` | Frontend cannot write to State directly | Scoped to `sample_validation_log.jsonl` only; returns evidence and append-readiness guidance |

### audit-state-write / report-file-write (medium risk, audit-only state)

Writes backend-owned audit control state or report artifacts. These routes cannot write queue holds, settings, media-policy overrides, launch rerun work, or touch media files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/audit/score-policy` | `audit-state-write` | Frontend cannot persist audit scoring policy directly | `policy` is backend-normalized; `reset` must be a JSON boolean when present |
| `POST /api/audit/ignore` | `audit-state-write` | Frontend cannot write audit ignore state directly | `action`: `add` or `remove`; row keys/paths are reconciled by backend audit state only |
| `POST /api/audit/export-rerun-csv` | `report-file-write` | Frontend cannot write rerun CSV artifacts directly | Backend exports a rerun CSV artifact only; it does not launch rerun work |

### config-write (high risk)

Writes and atomically reloads the live config PSD1 through backend-owned settings policy. Requires explicit confirmation.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/settings/save-patch` | `config-write` | Frontend cannot write PSD1 directly | `confirm_save` required; backend validates, backs up, writes, and reloads |
| `POST /api/settings/wizard/save` | `config-write` | Frontend cannot write PSD1 directly | `confirm_save` required; backend uses normal settings save path |

### filesystem-mutation (high risk)

Performs backend-owned filesystem mutation after explicit confirmation. The frontend must not execute these operations directly or choose unchecked filesystem targets.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/rename/apply` | `filesystem-mutation` | Frontend cannot execute filesystem renames | `confirm_apply` required; backend rebuilds plan from state and applies only selected rows; outside configured roots require explicit override |
| `POST /api/final-library-promotion/promote-queue` | `filesystem-mutation` | Frontend cannot copy/promote outputs or choose destinations directly | `confirm_promote` required; backend resolves eligible completed rows, destinations, copy behavior, and cleanup policy |

### process-dry-run / tooling-artifact-write / deployment-write

Runs backend maintenance tooling. Dry runs write no ops/release/metadata/backfill artifacts; write routes are bounded to development/deployment artifacts and do not touch media or queue state.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/maintenance/release-dry-run` | `process-dry-run` | Frontend cannot invoke the release script directly | Runs release builder with dry-run semantics; no release folder or zip written |
| `POST /api/maintenance/completed-backfill-dry-run` | `process-dry-run` | Frontend cannot invoke the backfill script directly | Runs backfill dry-run; no completed manifest written |
| `POST /api/maintenance/dependency-atlas` | `tooling-artifact-write` | Frontend cannot regenerate tooling artifacts directly | Writes generated dependency-atlas artifacts under `docs/generated/dependency-atlas/` only; no media, queue, settings, manifests, pending publish, or pipeline state touched |
| `POST /api/maintenance/release-build` | `deployment-write` | Frontend cannot create release packages directly | `confirm_create` required; backend checks active work, owns destination replacement, manifest creation, and optional zip creation |

### process-launch (high risk)

Spawns backend processes. The backend owns launch locks, command journal entries, process arguments, and all process lifecycle behavior.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/pipeline/start` | `process-launch` | Frontend cannot exec processes or bypass launch guards | `mode`: `once`, `continuous`, `validate`, or `drain_pending_pushes`; backend owns launch lock and process args |
| `POST /api/audit/start` | `process-launch` | Frontend cannot exec audit scripts directly | Backend owns audit script invocation |
| `POST /api/rerun/start` | `process-launch` | Frontend cannot exec rerun scripts directly | Media-safe defaults: `stage_mode: copy`, `original_mode: keep`, `return_mode: park` |

### backend-lifecycle (critical)

Initiates graceful backend shutdown. Issued by the Tauri shell only after close-readiness is checked.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/backend/shutdown` | `backend-lifecycle` | Shell must not decide unilaterally | Requires safe close-readiness unless `force_active_work_shutdown` is literal JSON boolean `true`; backend controls shutdown sequence |

---

## Design-Only Repair/Reconcile Boundary

Repair/reconcile is not an active command surface. `/api/contract` publishes design-only entries for Completed manifest reconciliation, Completed sidecar metadata repair, Pending Publish manifest repair, and orphan pending payload reconciliation. Every entry keeps `mutation_enabled=false` and `frontend_allowed=false`.

Required before any future implementation:

- A backend dry-run route with `effect=none`, `dry_run_only=true`, exact backend-selected scope, precondition results, diff summary, and `would_not_touch` evidence for source media, scratch media, parked payloads, destination output, and unrelated state.
- A mutation route only after backup/rollback semantics, command journal fields, atomic write or verified-move rules, and failure rollback tests exist.
- Route inventory, command ownership, WebView mutation-boundary tests, browser no-mutation evidence, and change-control evidence before any WebView control is exposed.

The current source-of-truth details are in `docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md`.

---

## Network Lifecycle Boundary

Network lifecycle controls remain design-only. `/api/contract` publishes future dry-run, cleanup/rollback, source-file, and route-exposure gates, but there are no Network start/stop/reclaim/ops/release/metadata/worker-polling POST routes. No WebView control may call one until `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` is satisfied.

---

## Summary: What the Frontend Can Never Do

The WebView and Tauri shell are explicitly prohibited from:

- Resolving filesystem paths for mutation or shell-open routes; backend state and allowlisted keys choose paths.
- Executing FFmpeg, PowerShell scripts, release scripts, or any subprocess directly.
- Reading arbitrary files from disk; diagnostics tail/open use allowlisted targets only.
- Writing config, manifests, command journals, validation logs, UI/app state, or control flags directly.
- Renaming, moving, deleting, repairing, publishing, or promoting files directly.
- Selecting encode settings, route decisions, audio policy, subtitle policy, or final-library destinations independently.
- Bypassing launch guards, launch locks, command journaling, confirmation fields, or close-readiness checks.

These restrictions are enforced by the backend at the API layer, not only by frontend convention.

---

## See Also

- Full route detail: `docs/inventories/API_ROUTE_INVENTORY.md`
- Route ownership map: `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Command ownership: `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- Diagnostics target allowlist: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- No-touch boundaries: `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Lifecycle boundary: `docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
