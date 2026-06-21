# Local API Evidence vs Mutation Matrix

Companion to `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`. This document separates every route into its mutation class, states whether the frontend can own the behavior, and notes the key restriction on each command route.

Total routes: 140 (49 read, 91 command). Source of truth remains `LOCAL_API_ROUTE_CONTRACT`, assembled from `contract_read.py` and `contract_command.py`.

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
| `GET /api/diagnostics/tdarr-matrix/latest` | `read` | No | Reads latest or selected Tdarr Matrix run evidence and target keys; no file open or launch |
| `GET /api/diagnostics/tdarr-matrix/runs` | `read` | No | Lists sentinel-marked Tdarr Matrix runs under the approved scratch run root |
| `GET /api/diagnostics/tdarr-matrix/compare` | `read` | No | Compares existing Tdarr Matrix reports by run IDs; no file open or launch |
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
| `GET /api/rename/cleaning-filters` | `read` | No | Reads backend-owned movie and TV cleaning filter catalogs only |
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
| `GET /api/maintenance/productization` | `read` | No | Reads installer/updater/AppData productization readiness, migration posture, release channel, and close-readiness evidence only |
| `GET /api/schedule` | `read` | No | Reads persisted schedule state; does not save or edit |
| `GET /api/watch-folders/status` | `read` | No | Reads watch-folder manager state only; does not scan on demand, launch, or mutate queue/process state |
| `GET /api/settings/workspace` | `read` | No | Read-only, redacted settings snapshot |
| `GET /api/settings/preset-library` | `read` | No | Reads backend PresetV2 library State JSON only; no active config save, queue mutation, launch, or media touch |
| `GET /api/libraries/route-map` | `read` | No | Backend-authored Library Route Map and decision-matrix evidence only; no save, launch, plugin execution, queue mutation, or media touch |
| `GET /api/libraries/route-map/trace` | `read` | No | Selected-file trace from existing Queue, Completed, and Sample Validation row evidence only; no probing, launch, save, repair, drain, rename, or media mutation |
| `GET /api/libraries/route-map/compare` | `read` | No | Backend-authored Library Profile diff with explicit/inherited evidence and designation filtering; no staging or saving |
| `GET /api/libraries/route-map/validation` | `read` | No | Validation handoff evidence keeps Sample Validation, Completed, Pending Publish, Diagnostics, and command proof distinct; no launch, drain, accept, repair, rename, save, plugin execution, or media mutation |
| `GET /api/settings/wizard/status` | `read` | No | Reads wizard availability and first-run recommendation state only |
| `GET /api/settings/wizard/defaults` | `read` | No | Reads wizard defaults and tool candidates only |
| `GET /api/network/workers` | `read` | No | Coordinator/worker persisted state; lifecycle start/stop uses separate backend-owned command routes |
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
| `POST /api/queue/file-overrides/remux-pilot-promote` | `queue-state-write` | Frontend cannot decide or write pilot series remux scope directly | Requires `confirm_apply: true`; writes exact per-file remux overrides for eligible remaining current queue rows in the detected pilot series only |
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
| `POST /api/diagnostics/tdarr-matrix/evidence/open` | `shell-open` | Frontend cannot submit arbitrary paths | Backend resolves `run_id` + `finding_key` + allowlisted evidence `target` under the selected Tdarr Matrix run root |
| `POST /api/maintenance/dependency-atlas/open-folder` | `shell-open` | Frontend cannot select arbitrary files | Opens fixed backend-resolved `docs/generated/dependency-atlas/`; request payload must be empty |

### diagnostic-process (scratch test harness)

Runs a backend-owned developer diagnostic process against scratch test-library roots. The frontend supplies a preset action only and cannot provide paths, tool arguments, source-delete settings, live operator config, or output destinations.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/diagnostics/tdarr-matrix-audit` | `diagnostic-process` | Frontend cannot construct commands or choose paths | `action`: `report`, `smoke`, `matrix`, `full`, or `strict-report`; backend expands fixed Tdarr Matrix audit presets under `LocalBase/Scratch/TestLibraries` |
| `POST /api/diagnostics/tdarr-matrix/rerun` | `diagnostic-process` | Frontend cannot construct commands or choose paths | `selection`: `selected` or `latest_failures`; backend maps finding keys to manifest case IDs and writes a fresh isolated TdarrMatrixRuns root |

### shell-dialog (no media mutation)

Opens a backend-owned native Windows dialog and returns operator-selected paths for staging. The dialog result does not preview, rename, move, delete, save settings, or touch media files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/rename/browse` | `shell-dialog` | Frontend cannot enumerate or mutate files directly | `selection_mode`: `files`, `folder`, or `folder_files`; selected paths are staged only and must still go through `rename/preview` and guarded `rename/apply` |
| `POST /api/settings/browse-path` | `shell-dialog` | Frontend cannot browse or resolve settings paths directly | Folder-only browser for allowlisted source/output/scratch and final-library promotion root settings; result is staged evidence only and does not save config |
| `POST /api/pipeline/browse-file` | `shell-dialog` | Frontend cannot browse or validate single-file paths directly | File-only browser for Launch single-file staging; result does not save config, launch work, mutate queue state, or touch media |

### test-fixture-write (low risk, regression corpus only)

Appends backend-validated regression fixture rows. This does not inspect, preview, rename, move, delete, or touch media files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/rename/filter-cases` | `test-fixture-write` | Frontend cannot choose arbitrary fixture paths or bypass confirmation | `confirm_append` required; backend writes only `tests/fixtures/rename/bad_rename_cases.jsonl` |

### dry-run / validation / preview (effect `none`)

Returns backend-computed plans, diffs, validation results, or reload status. No files are moved, created, published, deleted, or written.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/pending-publish/recovery-plan` | `none` | Frontend cannot author the plan | `scope`: `all` or `selected` only; dry-run result is read-only |
| `POST /api/completed/reconcile-manifest-dry-run` | `none` | Frontend cannot repair Completed manifests | Backend-authored dry-run diff only; no manifest write, sidecar write, publish, drain, move, delete, rerun, or media touch |
| `POST /api/completed/repair-sidecar-metadata-dry-run` | `none` | Frontend cannot repair sidecar metadata | Backend-authored dry-run diff only; no sidecar JSON write, manifest write, publish, drain, move, delete, rerun, or media touch |
| `POST /api/pending-publish/repair-manifest-dry-run` | `none` | Frontend cannot repair pending-publish manifests | Backend-authored dry-run diff only; no manifest write, drain, publish, move, delete, rerun, or media touch |
| `POST /api/pending-publish/reconcile-orphan-payloads-dry-run` | `none` | Frontend cannot create pending-publish manifests | Backend-authored orphan-payload review only; no manifest create, drain, publish, move, delete, rerun, or media touch |
| `POST /api/startup/reconcile-dry-run` | `none` | Frontend cannot reconcile startup state or repair/rebuild manifests | Backend-authored startup reconciliation evidence only; no write, repair, rebuild, migration, drain, publish, move, delete, rerun, queue mutation, or media touch |
| `POST /api/maintenance/retention-dry-run` | `none` | Frontend cannot decide or execute runtime retention cleanup | Backend-authored retention candidate report only; no delete, move, archive, truncate, rewrite, drain, publish, or source/output/pending-publish media touch |
| `POST /api/rename/preview` | `none` | Frontend cannot run pipeline rename planning | Predictions only; no files touched |
| `POST /api/settings/validate` | `none` | Frontend cannot validate config schema independently | Validation only |
| `POST /api/settings/preview-patch` | `none` | Frontend cannot diff or persist config independently | Returns redacted diff; no config written |
| `POST /api/settings/pipeline-plan-preview` | `none` | Frontend cannot make source/probe/media-policy decisions | Validates supplied source facts and staged patch; returns backend-owned dry-run plan only |
| `POST /api/settings/preset-library/validate` | `none` | Frontend cannot validate PresetV2 independently | Validates inline PresetV2 only; no State JSON or active config write |
| `POST /api/settings/preset-library/compare` | `none` | Frontend cannot compare preset media policy independently | Compares preset records or inline PresetV2 documents through backend legacy-patch projection only |
| `POST /api/settings/preset-library/import-preview` | `none` | Frontend cannot import preset records directly | Validates import candidates and reports State JSON target only |
| `POST /api/settings/preset-library/export` | `none` | Frontend cannot read arbitrary export paths | Returns a backend preset record or inline PresetV2 export payload only |
| `POST /api/settings/preset-library/apply-preview` | `none` | Frontend cannot apply PresetV2 policy independently | Converts PresetV2 to a legacy settings patch and runs existing backend settings preview semantics only |
| `POST /api/settings/wizard/validate-paths` | `none` | Frontend cannot validate wizard paths independently | Validation only |
| `POST /api/settings/wizard/validate-tools` | `none` | Frontend cannot validate tool paths independently | Validation only |
| `POST /api/settings/wizard/probe-hardware` | `none` | Frontend cannot run hardware probes independently | Bounded backend hardware probe evidence only |
| `POST /api/settings/wizard/validate-workers` | `none` | Frontend cannot decide worker/concurrency policy independently | Validation only |
| `POST /api/settings/wizard/preview` | `none` | Frontend cannot generate authoritative config patches independently | Generated patch preview only |
| `POST /api/settings/reload` | `none` | Frontend cannot reload in-memory backend state directly | Backend reloads cached state; no config written |
| `POST /api/schedule/preview` | `none` | Frontend cannot parse or validate schedule windows independently | Backend parses schedule input and returns changed days; no app-state write |
| `POST /api/sample-validation/preview` | `none` | Frontend cannot run sample validation logic independently | Preview warnings and evidence reconciliation only; no validation log append |
| `POST /api/network/coordinator/start-dry-run` | `none` | Frontend cannot decide coordinator lifecycle safety | Backend reports role/config/provider/state-file preconditions and `would_not_touch` evidence only |
| `POST /api/network/coordinator/stop-dry-run` | `none` | Frontend cannot decide coordinator stop safety | Backend reports active-work, claim, provider, and state-preservation posture only |
| `POST /api/network/worker/start-dry-run` | `none` | Frontend cannot claim work or validate path maps independently | Backend reports coordinator URL, path-map, pending-done, provider, and no-touch posture only |
| `POST /api/network/worker/stop-dry-run` | `none` | Frontend cannot abort work or clean scratch independently | Backend reports worker stop and pending-done posture only |

### repair/reconcile confirmed writes (medium risk, manifest or sidecar state only)

Confirmed repair/reconcile routes rerun the backend dry-run, require a matching `dry_run_fingerprint` plus explicit confirmation, and back up touched files before atomic writes. They never drain, move, delete, publish, rerun processing, or touch source/scratch/output media bytes.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/completed/reconcile-manifest` | `completed-manifest-write` | Frontend cannot rewrite completed manifests directly | Rewrites existing selected manifest rows only after matching backend dry-run fingerprint; no row add/remove |
| `POST /api/completed/repair-sidecar-metadata` | `completed-sidecar-json-write` | Frontend cannot rewrite sidecar JSON directly | Updates only backend-derived sidecar metadata fields; preserves unknown fields |
| `POST /api/pending-publish/repair-manifest` | `pending-manifest-write` | Frontend cannot repair pending manifests directly | Route is fingerprint-gated, writes only backend-validated manifest-normalization candidates, and blocks incomplete evidence |
| `POST /api/pending-publish/reconcile-orphan-payloads` | `pending-orphan-manifest-write` | Frontend cannot reconcile orphan payloads directly | Manifest-only route is fingerprint-gated, blocks without complete backend evidence, and never moves/deletes/drains/publishes payloads |

### preset-library-state-write (low risk, settings preset library only)

Writes backend-owned PresetV2 library state under `State\PresetLibrary`. It does not save active PSD1 settings, launch work, mutate queue state, or touch media files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/settings/preset-library/save` | `preset-library-state-write` | Frontend cannot write preset library JSON directly | Backend validates PresetV2 and writes `State/PresetLibrary/presets.json` only |

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
| `POST /api/settings/preset-library/apply` | `config-write` | Frontend cannot convert or save PresetV2 policy directly | `confirm_apply` required; backend converts PresetV2 to a legacy settings patch and saves through the existing settings policy for future launches |
| `POST /api/settings/wizard/save` | `config-write` | Frontend cannot write PSD1 directly | `confirm_save` required; backend uses normal settings save path |
| `POST /api/network/worker/join-cluster` | `config-write` | Frontend cannot import worker URL/token/path-map directly | `confirm_import` required; backend decodes the secret-safe join blob, saves worker settings through the normal settings path, then runs read-only test-connection |

### secret-transfer (high risk, setup only)

Returns a secret-bearing setup blob without journaling the secret. It must not start lifecycle, claim work, launch processing, publish, drain, or touch media.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/network/coordinator/join-blob` | `secret-transfer` | Frontend cannot mint or log worker auth secrets directly | Requires `confirm_create`; token rotation additionally requires `confirm_rotate`; response rendering must stay token/blob safe |

### filesystem-mutation (high risk)

Performs backend-owned filesystem mutation after explicit confirmation. The frontend must not execute these operations directly or choose unchecked filesystem targets.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/rename/apply` | `filesystem-mutation` | Frontend cannot execute filesystem renames | `confirm_apply` required; backend rebuilds plan from state and applies only selected rows; outside configured roots require explicit override |
| `POST /api/final-library-promotion/promote-queue` | `filesystem-mutation` | Frontend cannot copy/promote outputs or choose destinations directly | `confirm_promote` required; backend resolves eligible completed rows, destinations, copy behavior, and cleanup policy |

### process-dry-run / tooling-artifact-write / diagnostics-artifact-write / deployment-write

Runs backend maintenance tooling. Dry runs write no ops/release/metadata/backfill artifacts; write routes are bounded to development/deployment artifacts and do not touch media or queue state.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/maintenance/release-dry-run` | `process-dry-run` | Frontend cannot invoke the release script directly | Runs release builder with dry-run semantics; no release folder or zip written |
| `POST /api/maintenance/completed-backfill-dry-run` | `process-dry-run` | Frontend cannot invoke the backfill script directly | Runs backfill dry-run; no completed manifest written |
| `POST /api/maintenance/dependency-atlas` | `tooling-artifact-write` | Frontend cannot regenerate tooling artifacts directly | Writes generated dependency-atlas artifacts under `docs/generated/dependency-atlas/` only; no media, queue, settings, manifests, pending publish, or pipeline state touched |
| `POST /api/maintenance/support-export` | `diagnostics-artifact-write` | Frontend cannot assemble support bundles directly | Backend writes a redacted support export under per-user AppData DiagnosticsExports only; no config write, launch, queue, manifest, pending publish, or media mutation |
| `POST /api/maintenance/archive-state-journals` | `runtime-evidence-archive` | Frontend cannot archive state journals directly | `confirm_archive` required; archives backend state-journal evidence only and does not mutate media, queue, settings, manifests, or pending publish state |
| `POST /api/maintenance/release-build` | `deployment-write` | Frontend cannot create release packages directly | `confirm_create` required; backend checks active work, owns destination replacement, manifest creation, and optional zip creation |

### backend-lifecycle (critical)

Initiates guarded backend lifecycle operations. Network lifecycle routes are provider-guarded and confirmation-gated; they must not fall through to normal Launch, queue scanning, claim release, or media processing.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/backend/shutdown` | `backend-lifecycle` | Shell must not decide shutdown safety unilaterally | Requires safe close-readiness unless `force_active_work_shutdown` is literal JSON boolean `true`; backend controls shutdown sequence |
| `POST /api/network/coordinator/start-dry-run` | `none` | Frontend cannot decide lifecycle readiness directly | Dry-run evidence only; reports coordinator start preconditions and `would_not_touch` evidence |
| `POST /api/network/coordinator/stop-dry-run` | `none` | Frontend cannot decide lifecycle readiness directly | Dry-run evidence only; reports stop preconditions and state preservation evidence |
| `POST /api/network/worker/start-dry-run` | `none` | Frontend cannot start worker queue scanning directly | Dry-run evidence only; reports worker coordinator URL/path-map/pending-done posture |
| `POST /api/network/worker/stop-dry-run` | `none` | Frontend cannot abort worker work directly | Dry-run evidence only; reports worker stop and pending done posture |
| `POST /api/network/worker/test-connection` | `none` | Frontend cannot probe TCP/auth/path policy directly | Read-only worker preflight only; no lifecycle, claim, queue, settings, publish, drain, or media mutation |
| `POST /api/network/worker/discover-coordinators` | `none` | Frontend cannot scan/choose coordinator state outside backend policy | Read-only mDNS discovery; selecting a result only stages Settings patch values until backend preview/save |
| `POST /api/network/coordinator/start` | `backend-lifecycle` | Frontend cannot start coordinator runtime directly | Requires `confirm_start`; backend preconditions and provider availability must pass; no local file processing unless real lifecycle provider supports it |
| `POST /api/network/coordinator/stop` | `backend-lifecycle` | Frontend cannot force-release active claims or delete state | Requires `confirm_stop`; preserves `coordinator_inflight.json`, `worker_state.json`, and `cluster.log` |
| `POST /api/network/worker/start` | `backend-lifecycle` | Frontend cannot start worker queue scanning or claim work directly | Requires `confirm_start`; worker lifecycle provider claims only coordinator-assigned work one file at a time |
| `POST /api/network/worker/stop` | `backend-lifecycle` | Frontend cannot abort worker scratch cleanup directly | Requires `confirm_stop`; preserves pending done reports and worker state; abort remains a separate explicit command |

### process-launch (high risk)

Spawns backend processes. The backend owns launch locks, command journal entries, process arguments, and all process lifecycle behavior.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/pipeline/start` | `process-launch` | Frontend cannot exec processes or bypass launch guards | `mode`: `once`, `continuous`, `validate`, or `drain_pending_pushes`; backend owns launch lock and process args |
| `POST /api/audit/start` | `process-launch` | Frontend cannot exec audit scripts directly | Backend owns audit script invocation |
| `POST /api/rerun/start` | `process-launch` | Frontend cannot exec rerun scripts directly | Media-safe defaults: `stage_mode: copy`, `original_mode: keep`, `return_mode: park` |

---

## Repair/Reconcile Confirmed-Apply Boundary

Repair/reconcile is an active but constrained backend-owned command surface for selected Completed and Pending Publish repairs. Dry-runs remain `effect=none` and return a stable `dry_run_fingerprint`; confirmed apply routes rerun the dry-run, require the same fingerprint and explicit confirmation, write backups under backend State, and report rollback status.

Current limits:

- Completed manifest reconcile updates existing selected manifest rows only; it does not add or remove rows.
- Completed sidecar repair updates only backend-derived metadata fields and preserves unknown JSON fields.
- Pending manifest repair and orphan-payload reconcile WebView controls can request only backend-owned dry-run/fingerprint-gated routes. Pending manifest repair can write only backend-validated manifest-normalization candidates; orphan-payload reconcile remains blocked unless backend evidence supplies complete proposed manifest fields.
- No repair/reconcile route drains, moves, deletes, publishes, reruns processing, or mutates source/scratch/output media bytes.

The detailed contract remains in `docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md`.

---

## Network Lifecycle Boundary

Network lifecycle start/stop is now an active backend-owned, provider-guarded command surface. Dry-run routes have `effect=none` and must be used before confirmed commands. Confirmed routes require `confirm_start` or `confirm_stop`, command-journal evidence, provider availability, state-file preservation, and redacted config evidence. If the lifecycle provider is unavailable, commands fail closed and must not call normal Launch, scan the queue, release claims, publish, rename, delete, or touch source/scratch/output/pending-publish files.

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
