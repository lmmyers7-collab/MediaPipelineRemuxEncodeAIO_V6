# Local API Evidence vs Mutation Matrix

Companion to `Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`. This document separates every route into its mutation class, states whether the frontend can own the behavior, and notes the key restriction on each command route.

Total routes: 53 (25 read, 28 command). Source of truth remains `contract_read.py` and `contract_command.py`.

---

## Read Routes (GET) — Evidence Only

All GET routes are read-only. None touch media, launch processes, write config, or change queue/manifest state. The exception is `GET /api/maintenance`, which runs read-only tool probes (bounded-health-check).

| Route | Class | Frontend can own? | Key restriction |
|---|---|---|---|
| `GET /api/health` | `read` | — | No auth required; used before token is passed to WebView |
| `GET /api/contract` | `read` | — | Self-describing route contract; Tauri validates before opening WebView |
| `GET /api/snapshot` | `read` | — | Core status payload; backend assembles from pipeline/audit/process state |
| `GET /api/telemetry` | `read` | — | CPU/RAM/GPU sample; cached by backend |
| `GET /api/diagnostics` | `read` | — | Recent events, errors, launch-log summary |
| `GET /api/diagnostics/tail` | `read` | — | `target` must be an allowlisted key; `max_bytes` capped at 256 KB; no arbitrary path accepted |
| `GET /api/diagnostics/state-summary` | `read` | — | Bounded inline artifact summary; no arbitrary path |
| `GET /api/backend/close-readiness` | `read` | — | Backend has authority over safe-to-close; shell must not decide unilaterally |
| `GET /api/launch/preflight` | `read` | — | Backend-authored pre-launch checks; no locks reserved, no processes started |
| `GET /api/commands` | `read` | — | Recent command journal entries; in-memory bounded FIFO |
| `GET /api/queue` | `read` | — | Latest backend queue snapshot; no dry run spawned |
| `GET /api/queue/priority` | `read` | — | Reads backend-owned queue priority manifest; no queue/media mutation |
| `GET /api/queue/strategy` | `read` | — | Reads backend-owned queue strategy state and valid strategy names |
| `GET /api/queue/file-overrides` | `read` | — | Reads backend-owned non-destructive file override manifest or one source-root-contained override entry |
| `GET /api/completed` | `read` | — | Completed-jobs manifest; no output-share scan |
| `GET /api/failures` | `read` | — | Failure markers and reports; query-bounded |
| `GET /api/audit-results` | `read` | — | Audit CSV preview; no rerun CSV written |
| `GET /api/pending-publish` | `read` | — | Reads manifests and parked payloads; does not drain |
| `GET /api/publish-reconciliation` | `read` | — | Manual backend correlation of Completed, Pending Publish, and latest durable drain-summary evidence; no repair/drain/publish/write action |
| `GET /api/maintenance` | `bounded-health-check` | — | Runs existing env/tool probes; does not repair, write, or change |
| `GET /api/maintenance/progress` | `read` | — | Reads latest maintenance health-progress state; does not run probes or repair |
| `GET /api/schedule` | `read` | — | Reads persisted schedule state; does not save or edit |
| `GET /api/settings/workspace` | `read` | — | Read-only, redacted settings snapshot |
| `GET /api/network/workers` | `read` | — | Coordinator/worker persisted state; no lifecycle controls |
| `GET /api/sample-validation` | `read` | — | Recent validation records plus backend-authored validation readiness and stale-evidence reconciliation; query-bounded; no acceptance, repair, arbitrary media scan, or media/state mutation |

---

## Command Routes (POST) — Classified by Mutation Class

### queue-state-write (medium risk, non-destructive source state)

Writes backend-owned queue state manifests. These routes never rename, move, delete, launch, process, or mutate source media, and path-bearing writes must stay under configured `SourceMovies` or `SourceTV` roots.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/queue/priority` | `queue-state-write` | Frontend cannot write priority manifests directly | `path`/`items` must be absolute source-root-contained paths; `level` is limited to `high`, `normal`, `low`, or `hold` |
| `POST /api/queue/strategy` | `queue-state-write` | Frontend cannot write queue strategy state directly | `strategy` must be one of the backend-declared valid strategy names |
| `POST /api/queue/file-overrides` | `queue-state-write` | Frontend cannot write per-file media-policy override manifests directly | `path` must be source-root-contained unless `clear_all` is requested; writes non-destructive audio/subtitle override metadata only |

### failure-marker-write (medium risk, retry-blocker state)

Moves backend-owned failure marker JSON out of the active marker folder after explicit confirmation. This lets the next queue build retry those sources. It does not delete media, failure reports, completed manifests, pending publish state, or source/output files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/failures/clear` | `failure-marker-write` | Frontend cannot delete or move marker files directly | `confirm_clear` required unless `dry_run` is true; marker paths must resolve inside backend `State\Failures\Markers` |

### shell-open (no media mutation)

Opens a file or folder in the OS shell. Backend resolves the path from its own state using `row_key` + allowlisted `target` key. The frontend cannot pass a raw filesystem path.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/queue/open` | `shell-open` | Frontend cannot select the path — backend resolves via `row_key` + allowlisted `target` | Allowed targets: `source_file`, `source_folder`, `source_root` |
| `POST /api/completed/open` | `shell-open` | Same — backend resolves from completed manifest | Allowed targets: `output_folder`, `sidecar`, `source_folder` |
| `POST /api/pending-publish/open` | `shell-open` | Same — backend resolves from pending manifest | Allowed targets: `local_file`, `manifest`, `destination_folder`, `source_folder` |
| `POST /api/diagnostics/open` | `shell-open` | Same — backend resolves from 20-key allowlist | See `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` for full list |

### shell-dialog (no media mutation)

Opens a backend-owned native Windows dialog and returns operator-selected paths for staging. The dialog result does not preview, rename, move, delete, or touch media files.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/rename/browse` | `shell-dialog` | Frontend cannot enumerate or mutate files directly — backend owns native path selection | `selection_mode`: `files` or `folder`; selected paths are staged only and must still go through `rename/preview` and guarded `rename/apply` |

### dry-run (no output written)

Returns a backend-authored plan. No files are moved, created, published, or deleted.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/pending-publish/recovery-plan` | `none` (dry-run) | Frontend cannot author the plan — backend owns the logic | `scope`: `all` or `selected` only; dry-run result is read-only |
| `POST /api/maintenance/release-dry-run` | `process-dry-run` | Frontend cannot run the build script directly | Runs builder with `-DryRun`; no release folder or zip written |
| `POST /api/maintenance/completed-backfill-dry-run` | `process-dry-run` | Same — frontend cannot invoke PS scripts | Runs backfill with `-DryRun`; no manifest written |

### validation / preview (no state change)

Returns backend-computed diff or validation result. The frontend cannot implement this logic.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/rename/preview` | `none` | Frontend cannot run pipeline rename planning | Predictions only; no files touched |
| `POST /api/settings/validate` | `none` | Frontend cannot validate config schema | Validation only |
| `POST /api/settings/preview-patch` | `none` | Frontend cannot diff config | Returns redacted diff; no config written |
| `POST /api/settings/reload` | `none` | Frontend cannot reload in-memory backend state | Reloads cached state; no config written |
| `POST /api/sample-validation/preview` | `none` | Frontend cannot run sample validation logic | Preview warnings only |
| `POST /api/schedule/preview` | `none` | Frontend cannot parse or validate schedule windows | Backend parses half-hour windows and returns changed days; no app-state write |

### app-state-write (medium risk)

Writes desktop app state, not media state or config PSD1. Requires explicit confirmation.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/schedule/save` | `app-state-write` | Frontend cannot write app-state JSON directly | `confirm_save` required; backend validates schedule windows and writes only `schedule_enabled`/`schedule_grid` through the app-state service |

### control-flag-write (medium risk)

Writes a control flag file. The running pipeline reads it to pause, stop, or rescan.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/pipeline/control` | `control-flag-write` | Frontend cannot write flag files directly | `action`: `pause`, `stop`, `rescan` only |

### validation-log-write (low risk, evidence only)

Appends to the operator evidence log. Does not mark jobs complete, clear failures, or drain pending publish.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/sample-validation/append` | `validation-log-write` | Frontend cannot write to State directly | Scoped to `sample_validation_log.jsonl` only |

### config-write (high risk)

Writes and atomically reloads the live config PSD1. Requires `confirm_save`.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/settings/save-patch` | `config-write` | Frontend cannot write PSD1 directly | `confirm_save` required; backend backs up before writing |

### filesystem-mutation (high risk)

Renames files on disk. The backend rebuilds the rename plan independently and requires `confirm_apply`.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/rename/apply` | `filesystem-mutation` | Frontend cannot execute filesystem renames — backend owns the transactional rename service | `confirm_apply` required; backend rebuilds plan from state, not from frontend-submitted plan |

### process-launch (high risk)

Spawns a backend process (pipeline, audit, or rerun). The backend owns launch-lock, command journal, and all process lifecycle.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/pipeline/start` | `process-launch` | Frontend cannot exec processes or bypass launch guards | `mode`: `once`, `continuous`, `validate`, `drain_pending_pushes` |
| `POST /api/audit/start` | `process-launch` | Same | Backend owns audit script invocation |
| `POST /api/rerun/start` | `process-launch` | Same | Default media-safe: `dry_run: false`, `stage_mode: copy`, `original_mode: keep`, `return_mode: park` |

### backend-lifecycle (critical)

Initiates graceful backend shutdown. Issued by the Tauri shell only after `GET /api/backend/close-readiness` confirms safe.

| Route | Mutation class | Frontend cannot own? | Key restriction |
|---|---|---|---|
| `POST /api/backend/shutdown` | `backend-lifecycle` | Shell must not decide unilaterally — backend controls shutdown sequence | Requires close-readiness confirmation first |

---

## Design-Only Repair/Reconcile Boundary

Repair/reconcile is not an active command surface. `/api/contract` publishes design-only entries for Completed manifest reconciliation, Completed sidecar metadata repair, Pending Publish manifest repair, and orphan pending payload reconciliation. Every entry keeps `mutation_enabled=false` and `frontend_allowed=false`.

Required before any future implementation:

- A backend dry-run route with `effect=none`, `dry_run_only=true`, exact backend-selected scope, precondition results, diff summary, and `would_not_touch` evidence for source media, scratch media, parked payloads, destination output, and unrelated state.
- A mutation route only after backup/rollback semantics, command journal fields, atomic write or verified-move rules, and failure rollback tests exist.
- Route inventory, command ownership, WebView mutation-boundary tests, browser no-mutation evidence, and `DOC_TOUCH_LOG.md` updates before any WebView control is exposed.

The current source-of-truth details are in `Docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md`.

---

## Summary: What the Frontend Can Never Do

The WebView and Tauri shell are explicitly prohibited from:

- Resolving filesystem paths (all paths come from backend state via `row_key` + `target` key)
- Executing FFmpeg, PowerShell scripts, or any subprocess
- Reading arbitrary files from disk (only allowlisted tail targets)
- Writing config, manifests, or log files directly
- Writing desktop app state directly
- Renaming, moving, deleting, or publishing files
- Selecting the encode settings, route decisions, or audio/subtitle policy
- Bypassing launch guards, launch locks, or command journaling

These restrictions are enforced by the backend at the API layer, not only by frontend convention.

---

## See Also

- Full route detail (auth, schemas, callers): `Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Diagnostics target allowlist: `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- No-touch boundaries: `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Lifecycle boundary: `Docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`
