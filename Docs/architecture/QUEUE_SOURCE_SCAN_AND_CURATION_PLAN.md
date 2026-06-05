# Queue Source Scan and Curation Plan

Investigation date: 2026-06-03.

This document is an implementation plan for turning the Queue page's current
read-only snapshot reload into a real backend-owned source scan, then extending
that scan with a fast source-inventory phase followed by full queue curation.

The intended audience is a future AI coding agent working in this repository.
The plan is deliberately explicit about current behavior, ownership boundaries,
candidate file paths, and validation because queue behavior touches launch scope,
source/scratch/output safety, completed exclusions, pending publish evidence, and
operator trust.

## Current Problem

The Queue page currently shows a `Refresh Queue` button. The UI can show
`Scanning...`, but the backend call behind that button does not rebuild the
queue. It reloads the existing backend queue snapshot.

Current observed state from 2026-06-03:

- `GET /api/queue` returned quickly.
- No `MediaPipeline.ps1 -EmitQueuePlan` process was spawned when the Queue
  button was pressed.
- `E:\Videos\Scratch\State\Progress\queue_snapshot.json` was last written at
  `2026-06-02T22:10:52-04:00`.
- New TV files under
  `\\LAYNE-SERVER\Users\Layne\Videos\Encode\TV\Snow White With The Red Hair [BD][1080p][HEVC 10bit x265][Dual Audio][Tenrai-Sensei]`
  were written after that snapshot, from roughly `2026-06-02T22:20:08-04:00`
  through `2026-06-02T22:44:29-04:00`.
- The visible queue still showed Mob Psycho rows because the snapshot predated
  the newly staged TV show.

The UI wording is therefore misleading:

- The frontend says `Scanning...`.
- The backend is only reading the last `queue_snapshot.json`.
- Newly added source files do not appear until a separate pipeline queue-plan
  emission or pipeline run writes a new snapshot.

## Current Code Paths

### Frontend

Queue button wiring lives in:

- `apps/desktop/webview/static/assets/queueView.js`

The current Queue refresh button calls global refresh:

```text
refreshAll({ queueRefresh: true })
```

Global refresh lives in:

- `apps/desktop/webview/static/assets/app.js`
- `apps/desktop/webview/static/assets/app/refresh.js`

That refresh fetches `GET /api/queue` along with many other read routes.

### Local API Read Route

Read route registration:

- `src/mediapipeline/desktop/api/routes_read.py`

Relevant route:

```text
GET /api/queue -> _queue_payload
```

Payload implementation:

- `src/mediapipeline/desktop/api/read_payloads_inventory.py`

Relevant behavior:

```text
_queue_payload() -> self.facade.get_queue_preview(resolved).to_mapping()
```

### Queue Facade

Queue preview facade:

- `app/queue/facade.py`

Important current docstring:

```text
Return the last queue snapshot without spawning a dry-run process.
```

That is the core mismatch. The UI implies a scan, but the facade intentionally
reads the existing snapshot only.

### Existing Queue Dry-Run Machinery

The backend already has a queue-plan emission path:

- `app/queue/service.py`
- `app/queue/preview_builder.py`
- `app/queue/dry_run.py`
- `app/queue/dry_run_runner.py`
- `ops/pipeline/entrypoints/MediaPipeline.ps1`
- `ops/pipeline/engine/queue/pipeline_engine.ps1`

The command builder in `app/queue/dry_run.py` produces:

```text
pwsh -NoProfile -NonInteractive -File MediaPipeline.ps1
  -EmitQueuePlan
  -QueuePlanOutPath <temp snapshot path>
  -ConfigPath <config path>
```

`ops/pipeline/entrypoints/MediaPipeline.ps1` handles `-EmitQueuePlan` by calling
`Invoke-MediaPipelineEmitQueuePlan`.

`ops/pipeline/engine/queue/pipeline_engine.ps1` implements `Invoke-MediaPipelineEmitQueuePlan`
as a single scan/filter/snapshot pass:

```text
Set progress stage to scanning
Get processed index with ForceRefresh
Get media queue discovery plan with ForceRefresh
Write queue snapshot
Set progress stage to idle
```

This is the right backend authority for a true queue rebuild. The WebView must
not invent queue/media policy or perform direct filesystem mutation.

## Design Goals

1. Make the operator action honest.
   `Refresh Queue` should mean read existing backend state. `Scan Sources` should
   mean ask the backend to rebuild queue evidence.

2. Preserve backend authority.
   The WebView can request a scan and render evidence. It must not enumerate
   launchable queue rows independently, decide remux/encode routes, write queue
   snapshots directly, or mutate media.

3. Give fast feedback.
   Source inventory can usually be shown before full curation completes. The
   operator should quickly see that new files were found.

4. Prevent unsafe launches from uncurated data.
   Source-inventory rows are candidates, not queue rows. They must not be
   launchable until backend curation produces authoritative queue rows.

5. Keep scans serialized.
   Queue scan requests must have a duplicate-command guard. Repeated clicks must
   observe or join the active scan, not spawn overlapping `MediaPipeline.ps1`
   dry-run processes.

6. Keep evidence durable.
   The backend should write progress/status artifacts that survive UI reloads and
   allow Diagnostics to explain what happened.

## Proposed Route Model

Keep the existing route:

```text
GET /api/queue
```

Meaning:

- Read current authoritative queue snapshot.
- Do not spawn a process.
- Do not mutate queue state.
- Safe for automatic polling.

Add a new command route:

```text
POST /api/queue/scan
```

Meaning:

- Backend-owned scan command.
- Authenticated.
- Journaled.
- Duplicate guarded.
- Starts or observes a scan job.
- Eventually writes authoritative queue artifacts.

Suggested request shape:

```json
{
  "mode": "inventory_then_curate",
  "force": true,
  "scope": "all",
  "reason": "operator_requested_queue_scan"
}
```

Suggested response shape:

```json
{
  "schema_version": "desktop_command_result.v1",
  "ok": true,
  "command": "queue.scan",
  "severity": "info",
  "message": "Queue source scan started.",
  "refresh_hint": "queue",
  "data": {
    "scan_id": "20260603T031500Z-...",
    "status": "running",
    "mode": "inventory_then_curate",
    "state_path": "E:/Videos/Scratch/State/Progress/queue_scan_status.json",
    "inventory_path": "E:/Videos/Scratch/State/Progress/queue_source_inventory.json",
    "snapshot_path": "E:/Videos/Scratch/State/Progress/queue_snapshot.json",
    "duplicate_of_active_scan": false
  },
  "warnings": [],
  "errors": []
}
```

Also add a read route or include scan status inside `GET /api/queue`:

```text
GET /api/queue/scan-status
```

or:

```text
GET /api/queue -> queue_scan_status: {...}
```

Prefer adding scan status to `GET /api/queue` as well as exposing a dedicated
route only if tests/UI need it. The Queue page already polls `GET /api/queue`;
including scan status keeps the UI simple.

## State Artifacts

Use `resolved.state_root / "Progress"` as the root for queue scan state, matching
the existing `queue_snapshot.json` location.

Suggested artifacts:

```text
State/Progress/queue_scan_status.json
State/Progress/queue_source_inventory.json
State/Progress/queue_snapshot.json
```

### queue_scan_status.json

Purpose:

- Durable scan progress.
- Duplicate guard evidence.
- Diagnostics evidence.
- UI reload recovery.

Suggested fields:

```json
{
  "schema_version": "desktop_queue_scan_status.v1",
  "scan_id": "20260603T031500Z-...",
  "status": "running",
  "mode": "inventory_then_curate",
  "started_at": "2026-06-03T03:15:00Z",
  "updated_at": "2026-06-03T03:15:03Z",
  "completed_at": "",
  "phase": "inventory",
  "source_roots": [
    "\\\\LAYNE-SERVER\\Users\\Layne\\Videos\\Encode\\Movies",
    "\\\\LAYNE-SERVER\\Users\\Layne\\Videos\\Encode\\TV"
  ],
  "counts": {
    "inventory_candidates": 24,
    "curated_runnable": 0,
    "curated_excluded": 0,
    "warnings": 0,
    "errors": 0
  },
  "active_process": {
    "pid": 0,
    "command_label": "queue dry-run"
  },
  "paths": {
    "inventory": "E:/Videos/Scratch/State/Progress/queue_source_inventory.json",
    "snapshot": "E:/Videos/Scratch/State/Progress/queue_snapshot.json"
  },
  "warnings": [],
  "errors": [],
  "mutation_guardrail": "Queue scan is backend-owned. Inventory rows are not launchable. Source files are not modified."
}
```

### queue_source_inventory.json

Purpose:

- Fast source discovery evidence.
- Shows new files before curation completes.
- Not launch-authoritative.

Suggested fields:

```json
{
  "schema_version": "desktop_queue_source_inventory.v1",
  "scan_id": "20260603T031500Z-...",
  "produced_at": "2026-06-03T03:15:02Z",
  "status": "inventory_complete",
  "candidate_count": 24,
  "rows": [
    {
      "row_key": "inventory:...",
      "curation_state": "uncurated",
      "launchable": false,
      "source_path": "\\\\LAYNE-SERVER\\...\\Snow White With The Red Hair - S01E01.mkv",
      "root_path": "\\\\LAYNE-SERVER\\Users\\Layne\\Videos\\Encode\\TV",
      "media_kind": "tv",
      "display_name": "Snow White With The Red Hair - S01E01",
      "relative_path": "Snow White With The Red Hair.../Season 1/...",
      "size_bytes": 400000000,
      "last_write_utc": "2026-06-03T02:16:00Z",
      "inventory_reason": "found_by_source_walk",
      "safe_next_action": "Wait for backend curation before launch."
    }
  ],
  "mutation_guardrail": "Inventory rows are read-only candidates and cannot launch processing."
}
```

### queue_snapshot.json

Existing authoritative queue snapshot. It remains the only source for curated
launchable rows.

Do not replace its meaning. Add fields only if needed, and preserve existing
contract validation through `QueuePlanSnapshot.from_mapping`.

## Implementation Part 1 - True Scanner

Goal: add a backend route that actually triggers queue snapshot rebuild.

### Backend Route

Files likely involved:

- `app/api/commands.py`
- `app/contracts/api_commands.py`
- `src/mediapipeline/desktop/api/contract_command.py`
- `src/mediapipeline/desktop/api/routes_command.py`
- `app/api/commands_queue_scan.py` (new, under `app/api/`, not a flat desktop
  app file)

Add route:

```text
POST /api/queue/scan -> _queue_scan_payload
```

Route classification:

- Mutation class: `process-dry-run` or new `queue-scan-dry-run`.
- Effect: writes queue state artifacts, but does not mutate media.
- Auth required: yes.
- Command journal: yes.

Use a command result envelope.

### Service Method

Files likely involved:

- `app/queue/service.py`
- `app/queue/dry_run_runner.py`
- `app/queue/scan_status.py` (new focused helper)

Do not make the WebView call `MediaPipeline.ps1` directly.

For a minimal true scanner:

1. Add `QueueServiceMixin.start_queue_scan(...)` or equivalent.
2. Serialize with a service-level lock and active scan record.
3. If no active scan exists, spawn a background worker.
4. Worker calls existing dry-run machinery with force refresh:
   `build_queue_preview(resolved, force_refresh=True)` or a lower-level wrapper
   around `run_queue_dry_run_for_service(...)`.
5. Worker writes status before, during, and after the scan.
6. On success, existing dry-run runner atomically promotes the temp snapshot to
   `queue_snapshot.json`.
7. On timeout/error, leave the previous snapshot intact and record failure
   evidence.

Important: do not run this synchronously in the request thread unless the UI is
explicitly prepared for a long request. The current dry-run timeout is 120
seconds. Prefer request returns immediately with `scan_id`, then UI polls.

### Duplicate Guard

The duplicate guard must prevent overlapping scan processes.

If another scan is active:

- Return `ok: true`.
- Return `duplicate_of_active_scan: true`.
- Return active scan status.
- Do not spawn another process.

If an active status file exists but the process is dead/stale:

- Mark it `stale_recovered` or `failed`.
- Allow a new scan.

Use process liveness cautiously. Do not kill unrelated processes based only on a
PID from an old status file.

## Implementation Part 2 - Fast Inventory Then Curate

Goal: give the operator fast evidence that newly added files exist, while full
curation continues.

This should be added after the true scanner route is working.

### Inventory Scope

Use configured source roots from resolved paths/config:

- `SourceMovies`
- `SourceTV`

Candidate extensions should match pipeline source policy. Do not invent a
frontend-only extension list if the backend already has one. Prefer a shared
backend helper or constants from the media policy layer.

Inventory should collect only cheap facts:

- source path
- root path
- media kind
- relative path
- file size
- last write time
- coarse display name
- coarse TV season/episode hints only if cheap and already available

Inventory must not:

- run ffprobe
- decide remux/encode route
- inspect output library deeply
- mutate queue snapshot
- mark rows launchable
- touch source files

### Inventory Writer

Add focused helper under `app/queue/`, for example:

- `app/queue/source_inventory.py`

Responsibilities:

- Walk configured source roots.
- Bound errors and warnings.
- Emit `queue_source_inventory.json`.
- Return counts and rows to scan status.

This helper can run before `-EmitQueuePlan`. The UI can display the inventory
artifact while the full planner continues.

### Curation Phase

Curation remains the existing pipeline-authored queue planner:

```text
MediaPipeline.ps1 -EmitQueuePlan -QueuePlanOutPath <temp>
```

It performs the authoritative work:

- source discovery with current queue policy
- completed/outsource exclusion
- pending publish exclusion or warning
- sidecar/version checks
- priority/hold/strategy application
- route/remux/encode evidence
- final queue ordering
- authoritative `queue_snapshot.json`

After curation completes, UI should replace candidate rows with curated queue
rows from `GET /api/queue`.

## UI Plan

### Controls

Queue page should have two clear actions:

1. `Refresh`
   - Reads current backend state.
   - Calls `refreshAll({ queueRefresh: false })` or page-scoped refresh.
   - Does not show `Scanning...`.

2. `Scan Sources`
   - Calls `POST /api/queue/scan`.
   - Shows source scan progress.
   - Polls `GET /api/queue` or `GET /api/queue/scan-status`.
   - Does not allow another scan button click to spawn another scan.

Avoid using one button for both concepts unless the label changes by mode.

### Row States

Render row state explicitly:

| State | Meaning | Launchable |
|---|---|---|
| `Candidate` | Found by fast inventory only | No |
| `Curating` | Candidate is waiting for full backend planner evidence | No |
| `Runnable` | Present in authoritative `queue_snapshot.json` rows | Yes, through existing backend launch path only |
| `Excluded` | Backend planner excluded it as completed/blocked/pending/etc. | No |
| `Blocked` | Backend planner found a preflight/policy block | No |

Uncurated rows may allow safe actions:

- inspect source path
- copy path
- open containing folder if backend allowlist permits

Uncurated rows must not allow:

- launch
- queue priority writes, unless the backend validates source-root containment
  and the UI states this only affects future curation
- file overrides that assume route/track metadata

### Status Text

Use language that separates phases:

- `Scanning source folders...`
- `24 source candidates found. Backend curation pending.`
- `Curating queue evidence...`
- `Queue curation complete: 24 candidates, 18 runnable, 6 excluded.`
- `Previous snapshot shown while scan is running.`

Do not call snapshot reload "scanning".

## API Contract Updates

Update route inventories/contracts as needed:

- `src/mediapipeline/desktop/api/contract_command.py`
- `src/mediapipeline/desktop/api/contract_payload.py`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`

Route contract should make clear:

- `POST /api/queue/scan` is backend-owned.
- It may write queue scan status and queue snapshot artifacts.
- It must not modify source media, output media, pending publish manifests, or
  completed manifests.
- It must be command-journaled.
- It must be duplicate guarded.
- It may spawn `MediaPipeline.ps1 -EmitQueuePlan`.

## Testing and Validation

Use the smallest safe rung, but this change is queue behavior and process
launch behavior, so it needs more than static JS checks.

### Unit Tests

Add tests for:

- command payload validation for `/api/queue/scan`
- command registry includes `/api/queue/scan`
- route contract classifies route correctly
- duplicate scan guard returns active scan without spawning a second process
- stale active scan recovery
- scan status file write/read
- source inventory writer with temp Movie/TV roots
- source inventory rows are `launchable: false`
- curation success promotes/keeps authoritative snapshot
- curation failure leaves previous snapshot intact

Likely test files:

- `tests/python/desktop/test_api_command_contracts.py`
- `tests/python/desktop/test_application_facade_local_api.py`
- `tests/python/desktop/test_application_facade_queue.py`
- `tests/python/desktop/test_service_queue_dry_run_runner.py`
- New focused tests if needed:
  - `tests/python/desktop/test_queue_scan_service.py`
  - `tests/python/desktop/test_queue_source_inventory.py`

### WebView Static Tests

Update tests that currently assert Queue refresh behavior:

- `tests/python/desktop/test_application_facade_web_static.py`
- `tests/python/desktop/test_application_facade_local_api.py`
- `tests/python/desktop/test_webview_frontend_mutation_boundary.py`

Assert:

- `Scan Sources` posts only `/api/queue/scan`.
- `Refresh` does not post scan route.
- uncurated rows are not launchable.
- UI text distinguishes inventory from curated queue.
- no frontend filesystem scan exists.

### Browser Smoke

Update or add browser smoke:

- `tests/python/desktop/test_webview_browser_launch_queue_readiness_smoke.py`

Smoke scenario:

1. Seed a backend-shaped stale queue snapshot.
2. Seed a backend-shaped active inventory result with candidate rows.
3. Verify candidate rows render as not launchable.
4. Verify scan command post is captured.
5. Verify duplicate click does not post multiple scan commands, or verify backend
   duplicate response is rendered correctly.
6. Verify curated queue rows replace candidate rows after the mocked final
   snapshot arrives.

### Live Validation

After implementation, run a live validation with real filesystem roots:

1. Put a known TV folder under configured `SourceTV`.
2. Start the app with the canonical launcher.
3. Click `Scan Sources`.
4. Confirm inventory appears quickly and includes the new TV files.
5. Confirm rows are marked not launchable until curated.
6. Confirm `queue_snapshot.json` gets a new mtime after curation.
7. Confirm curated rows include the new TV show or explain why it was excluded.
8. Confirm no source files changed by comparing timestamps/hashes on a sample.

Because this touches queue launch scope and source discovery, rerun applicable
queue and launch smokes. If media-policy behavior changes, escalate to the
ops/release/metadata/real-media validation ladder.

## Implementation Order

### Phase 1 - Correct Semantics and True Scan

1. Rename or split UI controls so snapshot reload is not called scanning.
2. Add `POST /api/queue/scan`.
3. Implement scan status and duplicate guard.
4. Wire scan route to existing `-EmitQueuePlan` dry-run machinery.
5. Poll status and reload `GET /api/queue` on completion.
6. Test route contracts, duplicate guard, and WebView wiring.

Deliverable: pressing `Scan Sources` really rebuilds `queue_snapshot.json`.

### Phase 2 - Fast Inventory

1. Add backend source inventory helper.
2. Write `queue_source_inventory.json`.
3. Add inventory status into scan status payload.
4. Render candidate rows separately from curated rows.
5. Disable launch/route-dependent actions for candidates.
6. Test inventory writer and UI candidate safety.

Deliverable: new files appear quickly as non-launchable candidates, then become
curated rows after the planner finishes.

### Phase 3 - Diagnostics and Operator Evidence

1. Add Diagnostics open target for queue scan status and inventory if needed.
2. Add clear status messages for stale snapshot vs active scan.
3. Add command history rendering for `queue.scan`.
4. Update route inventories and evidence/mutation matrix.
5. Add live validation notes to the appropriate testing docs.

Deliverable: an operator or AI can explain exactly when the last source scan ran,
what it found, whether curation completed, and why a file is or is not launchable.

## Open Design Questions

1. Should source inventory be produced by Python or by a PowerShell helper?

   Python is faster to implement in the Local API service, but PowerShell may
   better match existing pipeline path semantics. If Python is used, keep it
   inventory-only and do not duplicate media policy.

2. Should `/api/queue/scan` run synchronously?

   Prefer asynchronous. The queue dry-run timeout is long enough that synchronous
   HTTP requests will feel broken and may fight frontend polling.

3. Should inventory rows include rough TV episode parsing?

   Only if cheap and backend-owned. Do not make frontend parsing authoritative.

4. Should priority writes be allowed on inventory rows?

   Possibly, because priority manifests already validate source-root-contained
   paths. But the UI must clearly say the priority affects future curation and
   does not make the row launchable.

5. Should completed/outsource curation start immediately after inventory, or wait
   for operator confirmation?

   Recommended default: start immediately. The operator asked for fast feedback,
   not a two-click workflow. Confirmation should be reserved for launch or media
   mutation, not read-only curation.

## Non-Goals

- Do not let the WebView build launch scope from inventory rows.
- Do not make source inventory a replacement for `queue_snapshot.json`.
- Do not bypass pending publish, completed, sidecar, priority, route, or file
  override policy.
- Do not scan output roots from the UI.
- Do not delete, move, rename, rewrite, or hash source media as part of the fast
  inventory phase.
- Do not start pipeline processing from the scan route.

## Recommended Agent Starting Point

For the next implementation agent:

1. Read this file.
2. Read `app/queue/facade.py`, `app/queue/service.py`,
   `app/queue/dry_run_runner.py`, and `app/queue/dry_run.py`.
3. Read `src/mediapipeline/desktop/api/routes_read.py`,
   `src/mediapipeline/desktop/api/routes_command.py`, and
   `app/api/commands.py`.
4. Add the route and duplicate-guarded scan service first.
5. Do not start with the fast inventory UI. Prove a true scan route can refresh
   `queue_snapshot.json` safely before adding the inventory/candidate layer.
