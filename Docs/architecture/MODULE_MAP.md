# Module Map

> **Purpose:** Answer the question **"where does X live?"** in under two minutes for any feature, helper, route, or state field in the codebase.
> **Audience:** Anyone (human or LLM agent) opening this repo for the first time, or anyone planning a new feature and needing to know which layer it belongs in.
> **Companion to:** `CODE_MANAGEMENT_CLEANUP_PLAN.md` §3.10, which proposed this doc. Inventory files (`Docs/inventories/*`) are the line-by-line registries; this doc is the architectural overview.

---

## 1. The layer cake

```
┌────────────────────────────────────────────────────────────────────┐
│ TAURI SHELL  (DesktopApp/tauri_shell/src-tauri/src/)              │
│   Rust process that owns app lifecycle, launches the backend,     │
│   hosts the WebView2 window, enforces close-readiness.            │
│   File: lib.rs  (and forthcoming sub-modules per GOD_FILE_SPLIT)  │
└────────────────────────────────────────────────────────────────────┘
                              │  spawns
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│ LOCAL HTTP BACKEND  (DesktopApp/mediapipeline_desktop_app/)        │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ ENTRY  local_api_main.py                                     │ │
│  │   Starts the HTTP server, prints the bootstrap JSON.         │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ HTTP LAYER  api/                                             │ │
│  │   server.py   ── http.server wiring                          │ │
│  │   handler.py  ── per-request dispatch                        │ │
│  │   routes_read.py, routes_command.py                          │ │
│  │       ── single registry of routes  →  payload handler name  │ │
│  │   read_payloads_*.py, app/api/commands_*.py                  │ │
│  │       ── per-route payload builders and command handlers     │ │
│  │   handler_policy.py, queue_source_path_policy.py, …          │ │
│  │       ── allowlists and path validation                      │ │
│  │   contract*.py  ── HTTP contract evidence (route inventory)  │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              │  calls facade methods               │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ APPLICATION LAYER  app/<domain>/                             │ │
│  │   *_facade.py  ── orchestrate one operator-visible action    │ │
│  │   policy.py    ── pure policy/validation helpers             │ │
│  │   app/sample_validation/                                      │ │
│  │       worksheet/readiness/reconciliation/evidence/pilot/policy│ │
│  │       behind application facade imports                       │ │
│  │   dto*.py       ── typed payload dataclasses                 │ │
│  │   runtime_outcomes.py  ── shared outcome / posture types     │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              │  calls services                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ DOMAIN SERVICE LAYER  app/<domain>/                          │ │
│  │   Pure read/write of local state and outsource SMB shares.   │ │
│  │   No HTTP, no orchestration — narrow, testable.              │ │
│  │   Examples:                                                  │ │
│  │     app/paths/layout.py        ── state-root directory map   │ │
│  │     app/queue/strategy.py     ── queue_strategy.json I/O     │ │
│  │     app/queue/file_overrides.py ─ file_overrides.json I/O    │ │
│  │     app/queue/priority_manifest.py ─ priority_manifest.json  │ │
│  │     app/completed/manifest.py ── completed_jobs.jsonl        │ │
│  │     app/publish/pending_service.py ─ PendingServerPush/...   │ │
│  │     app/status/*.py            ── progress / events / files  │ │
│  │     config_keys.py             ── Python config-key registry │ │
│  │     app/shared/protocols.py ── Protocol contracts for        │ │
│  │                                    service-helper runners    │ │
│  │     app/config/*.py            ── load/save MediaPipeline-   │ │
│  │                                    Config.psd1 via PS1       │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              │  reads/writes                       │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ LOCAL STATE  LocalBase/State/  (versioned layout v1)         │ │
│  │   App/         ── desktop app state                           │ │
│  │   Pipeline/    ── pause/stop/rescan flags                     │ │
│  │   Progress/    ── pipeline_progress.json, events.jsonl, …     │ │
│  │   ActiveJobs/  ── per-job heartbeat files                     │ │
│  │   Completed/   ── completed_jobs.jsonl                        │ │
│  │   Failures/    ── per-job marker + artifact + report          │ │
│  │   PendingServerPush/ ── parked outputs awaiting drain         │ │
│  │   priority_manifest.json  ── DesktopApp ↔ PS1 priority bus    │ │
│  │   queue_strategy.json     ── queue ordering strategy state    │ │
│  │   file_overrides.json     ── per-file processing overrides    │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
                              ▲  reads/writes the same state
                              │
┌────────────────────────────────────────────────────────────────────┐
│ PIPELINE RUNTIME  (Pipeline/)                                      │
│                                                                    │
│  MediaPipeline.ps1  ── orchestrator (entry + main loop)    │
│      ── Loads config, dot-sources compatibility Modules/*.ps1,     │
│         and runs pipeline rounds (queue build → process → publish).│
│                                                                    │
│  Pipeline/Modules/*.ps1  ── current dot-source compatibility path  │
│      These files are temporary shims to engine/<domain>/ modules.  │
│      Keep them only until full release, package-mode, and          │
│      representative real-media evidence prove the old paths can be │
│      deleted without changing operator behavior.                   │
│                                                                    │
│  engine/<domain>/*.ps1 ── active PowerShell implementations        │
│      Examples (grouped):                                           │
│        observability/logging.ps1, shared/path_helpers.ps1          │
│        config/config_keys.ps1, config/config_schema.ps1            │
│        storage/state_store.ps1, storage/scratch_copy.ps1           │
│        decide/routing.ps1, decide/encode_policy.ps1                │
│        policy/folder_policy.ps1, queue/file_overrides.ps1          │
│        audio/audio.ps1, subtitles/*.ps1                            │
│        shared/native.ps1, process/ffmpeg_progress.ps1              │
│        status/progress_state.ps1, queue/queue_plan.ps1             │
│        naming/naming.ps1, shared/source_identity.ps1               │
│        publish/*.ps1, library/library_index.ps1                    │
│        process/pipeline_processing.ps1, queue/pipeline_engine.ps1  │
│                                                                    │
│  Audit-PendingPublishOutsourcedFiles.ps1, Backfill-*.ps1, Release- │
│  CompletedOutsourceShare.ps1  ── scripts invoked by DesktopApp     │
│                                  (audit, backfill, release).       │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ WEBVIEW FRONTEND  (DesktopApp/mediapipeline_desktop_app/ui_web/)   │
│                                                                    │
│  static/index.html  ── single page; one <section data-page-panel=> │
│                        per page (home, launch, queue, completed, … )│
│  static/assets/*.js ── forty IIFE modules, no bundler.             │
│                                                                    │
│  Each module exports a namespace object + flat re-exports:         │
│    window.mediaPipelineXxxView = { renderXxx, … };                 │
│    window.renderXxx = renderXxx;  // for cross-module use          │
│                                                                    │
│  Module groupings:                                                 │
│    apiClient.js, domHelpers.js, formatters.js   (infrastructure)   │
│    app.js                                       (orchestrator)     │
│    crossPageContextView.js + .sampleValidation  (cross-page board) │
│    commandHistory.js                            (shared module)    │
│    homePage/dashboard (in app.js + crossPage*)                     │
│    progressView.js (Live page)                                     │
│    queueView.js, completedView.js + .evidence + .proof + .review + │
│    .diagnostics,                                                   │
│    pendingPublishView.js + .recovery/.diagnostics/.drain +         │
│    .confidence,                                                    │
│    launchView.js + .risk + .scope + .realmedia + .preflight,       │
│    settingsView.js,                                                │
│    telemetryView.js,                                               │
│    reportsView.js, scheduleView.js, networkView.js,                │
│    contractView.js, renameView.js, diagnosticsView.js, …           │
│                                                                    │
│  Cross-module communication: via `typeof window.X === "function"`  │
│  guards on flat exports. No imports, no requires, no bundler.      │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. Directionality rules

Each arrow is a **call direction**, not a data flow. Calls go one way; data flows in both directions through return values.

| Caller | May call | May NOT call |
|---|---|---|
| Tauri shell (Rust) | Backend HTTP endpoints; OS dialogs | Frontend JS directly; PS1 directly |
| HTTP layer (`api/`) | Application facades | Services directly; PS1 directly |
| Application facades | Services; other facades (cautiously); `runtime_outcomes` | HTTP layer; frontend; PS1 binaries (use a service) |
| Services | Other services (narrowly); filesystem under `LocalBase/State`; subprocess calls to `MediaPipelineConfig.psd1` reader | HTTP layer; facades; frontend |
| Pipeline runtime (PS1) | Filesystem under `LocalBase/State`; ffmpeg/ffprobe/mkvmerge binaries; outsource SMB shares | Backend HTTP; frontend; tauri shell |
| Frontend JS | Backend HTTP via `apiClient.js`; other JS modules via `window.*` flat exports | Anything that mutates state directly (must go through HTTP) |

**The strict rule of the codebase:** every mutation must come through an authenticated HTTP route, every read must come from `LocalBase/State` (DesktopApp side) or be produced by PS1 (Pipeline side). The frontend never writes to disk directly. The backend never invokes ffmpeg directly. The PS1 never reaches into HTTP.

---

## 3. Where do I add my feature?

Use this decision tree:

### "I want a new operator-visible action (button, toggle, command)."

1. Add a new route to `api/routes_command.py` or `api/routes_read.py`.
2. Add a command handler in `app/api/commands_*.py` (write actions) or a payload handler in `api/read_payloads_*.py` (read actions). Often this is a mixin class.
3. Wire write handlers into `app/api/command_handlers.py` and route names into `app/api/commands.py`.
4. Add a domain facade method under `app/<domain>/` that orchestrates the action.
5. Add or reuse a focused module under the relevant `app/<domain>/` package for the actual state read/write.
6. If the action affects pipeline behaviour: add a state file that PS1 reads (see §4), and add an `engine/<domain>/*.ps1` reader/applier while keeping any existing `Pipeline/Modules/*.ps1` compatibility path working until Phase 6 deletion gates close.
7. Wire the UI in the relevant `assets/xxxView.js` plus `index.html`.
8. **Update inventories** (see §6).

### "I want a new piece of local state."

1. Add the path to `app/paths/layout.py` or the path-resolution runner, plus the `ResolvedPaths` dataclass.
2. Add the path to `engine/storage/state_store.ps1` and keep the current `Pipeline/Modules/StateStore.ps1` compatibility path working until Phase 6 removes it.
3. Both sides now have a deterministic path derived from `LocalBase`. Add a service file (DesktopApp side) and an `engine/<domain>/` file (PS1 side) for the read/write logic.

### "I want a new pipeline processing override."

1. Extend the current file-overrides implementation behind `engine/queue/file_overrides.ps1`; keep `Pipeline/Modules/FileOverrides.ps1` as a compatibility shim only. New PowerShell files should use `engine/<domain>/`, not a new dotted `Pipeline/Modules` file.
2. Wire its merge into `PipelineProcessing.ps1` at the right point in the per-file loop.
3. Surface it via `app/queue/file_overrides.py` and the `/api/queue/file-overrides` route.
4. Add a UI control to the per-file settings drawer in `queueView.js`.

### "I want a new diagnostics or evidence panel."

1. Add a payload builder in the matching domain policy module (e.g., `app/completed/policy.py` for completed-side evidence).
2. Add a read route + handler.
3. Render in the matching `xxxView.js`.
4. Add DOM IDs to `WEBVIEW_DOM_ID_INVENTORY.md`.

---

## 4. State files cross-reference

Each persistent state file is read by both DesktopApp and PS1 in different ways. The deterministic-path contract is:

| State file (under `LocalBase/State/`) | Written by | Read by |
|---|---|---|
| `priority_manifest.json` | `app/queue/priority_manifest.py` (POST `/api/queue/priority`) | `engine/queue/queue_plan.ps1` at queue-build time |
| `queue_strategy.json` | `app/queue/strategy.py` (POST `/api/queue/strategy`) | `engine/queue/queue_plan.ps1` at queue-build time |
| `file_overrides.json` | `app/queue/file_overrides.py` (POST `/api/queue/file-overrides`) | `engine/queue/file_overrides.ps1` per file |
| `Progress/pipeline_progress.json` | PS1 (`engine/status/progress_state.ps1`) | `app/status/*.py` (GET `/api/status`, `/api/progress`) |
| `Progress/pipeline_events.jsonl` | PS1 (`engine/queue/pipeline_engine.ps1`) | `app/status/events.py` (GET `/api/progress`) |
| `Progress/queue_snapshot.json` | PS1 (`engine/queue/pipeline_engine.ps1`) | `app/queue/snapshot.py` (GET `/api/queue`) |
| `Pipeline/pipeline_{pause,stop,rescan}.flag` | `app/processes/control_flags.py` (POST `/api/pipeline/control`) | PS1 main loop (`MediaPipeline.ps1`) |
| `ActiveJobs/*.json` | PS1 (`ProgressState.ps1`) | `app/processes/active_jobs.py` |
| `Completed/completed_jobs.jsonl` | PS1 (`engine/publish/publish_completion.ps1`) and `Backfill-CompletedManifest.ps1` | `app/completed/manifest.py` |
| `Failures/{Markers,Reports,Artifacts}/` | PS1 (`engine/failures/failure_state.ps1`, `engine/publish/publish_completion.ps1`) | `app/failures/markers.py`, `app/failures/facade.py` |
| `PendingServerPush/<job>/` | PS1 (`engine/publish/pending_push.ps1`, `engine/publish/pending_transactions.ps1`) | `app/publish/pending_*.py` |

**Anytime a new piece of state is added, both sides of this table get a new row.** That's the cross-machine integrity contract.

### Pending Publish Ownership Boundary

Parked output is media plus sidecars. The backend owns every decision about what is safe to park, drain, reveal, roll back, discard, or present as already published. WebView/Tauri surfaces can display backend-authored rows and invoke documented backend commands only; they must not infer drain safety or move parked payloads.

| Module | Owns | Must not own |
|---|---|---|
| `engine/publish/publish_completion.ps1` | Immediate publish flow, low-space/unknown-space deferred parking decision, and calls into pending park helpers when verified output must be parked. | Pending drain loop, manifest row presentation, or WebView readiness decisions. |
| `engine/publish/publish_partial.ps1` | Partial media reveal and sidecar backup/restore primitives shared by immediate publish and pending drain. | Publish policy, source identity validation, manifest indexing, or UI state. |
| `engine/publish/publish_sidecars.ps1` | Sidecar publish helper mechanics shared by immediate and pending paths. | Deciding whether parked output is safe to discard, drain, or mark accepted. |
| `engine/publish/pending_manifest_store.ps1` | Pending manifest read/write/round-trip validation and retry-state serialization. | Moving media, copying sidecars, publishing final output, or formatting UI rows. |
| `engine/publish/pending_transactions.ps1` | Durable media-plus-sidecar park transaction, drain transaction, server-copy validation, sidecar rollback, and `pending_move` crash recovery. | Operator command routing, frontend policy, or read-only row shaping. |
| `engine/publish/pending_push.ps1` | Public PowerShell facade for park/retry/drain commands, drain summary, event/log emission, and pending index refresh calls. | Low-level copy/reveal rollback details already owned by `PendingTransactions.ps1`. |
| `engine/publish/pending_publish_index.ps1` | Read-only in-memory index and health rows for parked manifests and missing payloads. | Moving, deleting, draining, repairing, or accepting parked payloads. |
| `app/publish/pending_*.py` | Read-only desktop scan, row shaping, open-target support, and API DTO normalization over backend-authored manifests. | Media copy/reveal policy, discard decisions, manifest repair side effects, or drain safety inference. |

---

## 5. Config flow

`MediaPipelineConfig.psd1` is the single config file. Read by:

1. **PS1 entry** (`MediaPipeline.ps1`) at startup — via PowerShell `Import-PowerShellDataFile`.
2. **DesktopApp** at API-resolution time — via the config PSD1 reader in `app/config/` invoking a PS1 helper to read and emit JSON.

Both sides ingest the same keys. **Config-key names are documented in `Docs/architecture/CONFIG_KEY_GLOSSARY.md`**. Python-side key names are guarded in `DesktopApp/mediapipeline_desktop_app/config_keys.py`; PowerShell-side key names are guarded in `engine/config/config_keys.ps1` with `Pipeline/Modules/ConfigKeys.ps1` kept as a compatibility shim. Drift tests are `DesktopApp/tests/test_config_keys.py` and `Pipeline/Tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1`.

---

## 6. Inventories — the per-layer registry

Each layer has at least one inventory file that lists what's in it. Updating these files in the same chunk as a feature is mandatory:

| Layer | Inventory |
|---|---|
| Frontend DOM | `Docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md` |
| Frontend JS exports | `Docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` |
| HTTP routes | `Docs/inventories/API_ROUTE_INVENTORY.md` |
| Tests | `Docs/testing/TEST_COVERAGE_MATRIX.md` |
| Smoke mutation matrix | `Docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` |
| Validation ladder rungs | `Docs/testing/VALIDATION_LADDER_RUNBOOK.md` |
| Config keys | `Docs/architecture/CONFIG_KEY_GLOSSARY.md` |
| Settings raw-key triage | `Docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md` |
| Architecture decisions | `Docs/architecture/DECISIONS_AND_HISTORY.md` |
| Master doc index | `Docs/DOCS_INDEX.md` |
| Per-chunk audit log | `Docs/DOC_TOUCH_LOG.md` |
| Chronological changelog | `Docs/REMEDIATION_CHANGELOG.md` |

If you add a state file, route, DOM ID, or window-export and you do not update the corresponding inventory in the same chunk, the inventory drift tests will fail (`test_webview_inventory_docs.py`, etc.).

---

## 7. Module naming conventions

| Pattern | Layer | Example |
|---|---|---|
| `app/<domain>/*.py` | Domain service layer | `app/queue/file_overrides.py` |
| `app/<domain>/*_runner.py` | Service-layer entrypoint that wires multiple modules | `app/paths/resolution_runner.py` |
| `app/<domain>/*_facade.py` | Application facade adapter | `app/queue/facade.py` |
| `app/<domain>/policy.py` | Pure policy/validation companion to a facade | `app/queue/policy.py` |
| `application/dto_*.py` | Typed payload dataclasses | `dto_status.py` |
| `api/routes_*.py` | Route registry | `routes_command.py` |
| `app/api/commands_*.py` | Mixin with per-route POST handlers | `commands_queue_priority.py` |
| `api/read_payloads_*.py` | Mixin with per-route GET handlers | `read_payloads_inventory.py` |
| `api/*_policy.py` | Per-route policy/validation | `queue_source_path_policy.py` |
| `Pipeline/Modules/*.ps1` | Current PS1 dot-source compatibility path; do not add new files here | `FileOverrides.ps1` |
| `assets/xxxView.js` | One page-view module per WebView page | `queueView.js` |
| `assets/xxxView.<slice>.js` | Split child of a page-view (per `GOD_FILE_SPLIT_PLAN.md`) | `completedView.evidence.js`, `completedView.proof.js`, `completedView.review.js`, `completedView.diagnostics.js`, `launchView.risk.js`, `launchView.scope.js`, `launchView.realmedia.js`, `launchView.preflight.js`, `pendingPublishView.recovery.js`, `pendingPublishView.diagnostics.js`, `pendingPublishView.drain.js`, `pendingPublishView.confidence.js` |
| `assets/xxxHistory.js`, `xxxBridge.js`, `xxxLabels.js` | Sub-modules under a page view | `launchHistoryView.js` |

If a new file does not match one of these patterns, it likely belongs in an existing layer using one of these names. Inventing new patterns adds discovery cost.

---

## 8. When this map gets out of date

This map is **curated, not generated**. When any of the following happen, this doc gets a chunk:

- A new layer is introduced (very rare).
- A directionality rule changes (calls now allowed across a boundary that wasn't before).
- A new state file is added that's read by both PS1 and DesktopApp.
- A new top-level directory appears under `DesktopApp/`, `Pipeline/`, or `ui_web/static/assets/`.

Adding a new file inside an existing layer using an existing naming pattern does **not** require updating this doc — the pattern is already documented in §7.
