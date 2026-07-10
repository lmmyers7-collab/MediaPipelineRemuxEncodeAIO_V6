# Network CSV Rerun Prework

Date: 2026-07-05
Status: investigation and planning only
Change packet: MP-CHANGE-2026-0705-005
Risk class: high

## Purpose

This document is the common source for future work that makes CSV rerun usable
with Network coordinator/worker mode.

The local CSV rerun path is working and is now operationally valuable enough to
consider as a distributed workload. The current network path does not distribute
CSV rerun rows. Workers claim normal coordinator queue records, while CSV rerun
launches a separate `rerun_csv` process that stages rows locally, launches nested
pipeline chunks, and then applies rerun destination policy on the same machine.

The first required step is investigation. This document defines what a future AI
coding agent must read, what facts are already known, which architecture
decisions must be made before implementation, and how to stage the work without
breaking source safety, worker claim ownership, pending publish, or command
journal evidence.

This pack is subordinate to:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/change_control/README.md`

If this file conflicts with those authority docs or with executable source and
tests, stop and update the stale planning text. Do not let this plan become a
parallel source of truth.

## Current Verified Facts

These facts were verified on 2026-07-05.

### Local CSV Rerun Shape

| Surface | Current behavior |
|---|---|
| `POST /api/rerun/preview` | Backend read-only preview. Parses CSV rows, classifies blockers, and reports `writes_queue=false`. |
| `POST /api/rerun/start` | Backend process launch. Calls `start_rerun_csv_process()` and spawns `Invoke-RerunCsv.ps1`. |
| `src/mediapipeline/core/processes/rerun_facade.py` | Validates config identity, CSV path, lifecycle policy, `dry_run`/`plan_only`, preview blockers, launch lock, active-work guard, optional scoped CSV materialization, then calls `service.start_rerun_csv(...)`. |
| `src/mediapipeline/core/processes/launch_plans.py` | Builds a PowerShell launch plan for `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1` and records `job_kind="rerun_csv"`. |
| `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1` | Imports the CSV, resolves rerun plans, creates a rerun workspace, stages rows into `RerunQueue`, writes manifests except in `-PlanOnly`, launches nested `MediaPipeline.ps1 -Once` chunks, applies rerun destination policy, and updates the rerun manifest. |
| `src/mediapipeline/core/processes/rerun_results.py` | Presents rerun rows as `queue_source="csv_rerun"` and `uses_pipeline_start=false`. |
| `src/mediapipeline/core/queue/facade.py` | Can display active rerun manifest rows as read-only queue-like evidence, but those rows are not normal coordinator queue records. |

CSV rerun has three local execution modes:

| Mode | Meaning today |
|---|---|
| `one_at_a_time` | Stage one executable CSV row, run one nested pipeline chunk, apply destination policy, repeat. |
| `windowed` | Stage up to `window_size` rows per nested pipeline chunk. |
| `batch_stage_all` | Stage all pending rows into one chunk. |

Those are local chunking modes. They are not network scheduling modes.

### Network Coordinator/Worker Shape

| Surface | Current behavior |
|---|---|
| `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` | Network work starts only through backend-owned lifecycle routes. Normal Launch is blocked when `NetworkRole` is `coordinator` or `worker`. |
| `src/mediapipeline/desktop/network/coordinator_queue.py` | Coordinator claims from `app.queue_records`, tracks in-flight sources, persists `coordinator_inflight.json`, and marks done/release through coordinator ownership. |
| `src/mediapipeline/desktop/network/worker_loops.py` | Worker polls `/api/claim`, resolves coordinator-visible source paths into worker-local paths, builds a synthetic `QueueRecord`, and starts one claimed job. |
| `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | Worker and coordinator-local execution call the backend pipeline launcher with `mode="once"`, `single_file=<claimed source>`, and worker result arguments such as `-WorkerClaimId` and `-WorkerResultPath`. |
| `src/mediapipeline/core/processes/pipeline_policy.py` | Normal `/api/pipeline/start` is blocked for any `NetworkRole` other than `standalone`. |

Network workers currently process one coordinator-assigned source at a time.
They do not run the CSV rerun wrapper and do not apply CSV rerun destination
policy themselves.

### Existing Contract Statement

`docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md` currently states that:

- `/api/rerun/results` marks CSV rerun rows as `uses_pipeline_start=false`.
- `/api/rerun/start` remains CSV-rerun-specific.
- CSV rerun rows are not converted into normal queue rows.
- CSV rerun rows are not submitted to `/api/pipeline/start`.

Any implementation that makes CSV rerun rows distributable must deliberately
change this contract, update inventories, update route contracts, and add tests.

## Problem Statement

The operator needs an option to run a vetted CSV rerun workload through the
network coordinator and workers, not only through the local machine.

The feature is not just "let workers run this CSV." CSV rerun currently combines
five responsibilities in one local wrapper:

1. CSV row validation and scoping.
2. Source staging into a rerun workspace.
3. Nested pipeline execution against staged roots.
4. Per-row result classification.
5. Destination policy application: review workspace, pending publish, direct
   replacement, final-output collision handling, sidecar carry-forward, and
   manifest evidence.

Network workers currently own only one narrower responsibility:

1. Claim one source from the coordinator.
2. Run the normal pipeline once for that source.
3. Report a worker result artifact and done/release evidence back to the
   coordinator.

The future feature must decide how to split CSV rerun responsibilities between
coordinator, worker, and existing PowerShell while preserving safety.

## Goals

- Let the operator choose a CSV rerun workload as a Network coordinator job
  source.
- Let remote workers process CSV rerun rows under coordinator ownership.
- Preserve CSV row validation: duplicate source rows, relative paths, missing
  sources, invalid extensions, blocked rule decisions, and unsafe lifecycle
  rows must remain fail-closed before execution.
- Preserve source safety: workers must never delete, rename, overwrite, or
  transcode source files in place.
- Preserve scratch isolation on the executing host.
- Preserve CSV rerun destination policy semantics, including pending publish and
  final replacement confirmations.
- Preserve coordinator ownership of claim, done, release, retry, and stale
  heartbeat decisions.
- Preserve command journal evidence for operator-visible start/stop/failure
  outcomes.
- Preserve close-readiness and duplicate-command guards.
- Make progress and per-row evidence understandable in Home, Queue, Network,
  Diagnostics, and Command History.

## Non-Goals

- Do not move media policy into WebView or Tauri.
- Do not let the frontend author queue, claim, done-report, publish, drain,
  repair, rename, or filesystem mutation decisions.
- Do not make worker machines scan local media roots for CSV rerun rows.
- Do not let workers decide final publish/replacement policy independently from
  coordinator-authored CSV rerun policy.
- Do not bypass pending publish manifest-backed flows.
- Do not redefine `-DryRun` as no-write. `-PlanOnly` is the no-write planning
  mode.
- Do not add source-delete or source-cleanup behavior to CSV rerun.
- Do not make Network lifecycle start a normal local Launch fallback.
- Do not reintroduce legacy root launcher paths or `Pipeline/Modules` files.
- Do not hand-edit generated files under `docs/generated/`.

## Safety Invariants For This Feature

1. The coordinator must own CSV batch identity, row identity, row lifecycle, and
   final row status.
2. A worker may execute one assigned row or row shard, but it must not choose
   another row on its own.
3. A worker may report execution output and evidence, but it must not apply
   final replacement or pending-publish policy unless an explicit architecture
   decision assigns that authority and validates it.
4. Source paths in claims must remain coordinator-authoritative and must still
   resolve through library-relative fields or `WorkerSourcePathMap`.
5. Destination paths must not be inferred by workers from local output names
   unless the coordinator-authored row plan carries the destination contract.
6. Pending publish manifests must remain manifest-backed and duplicate
   `server_out` protection must remain active.
7. A network CSV rerun stop must be cooperative and must preserve in-flight
   claims, pending done reports, and rerun row state.
8. Any output trust decision must be backed by completed, pending-publish, drain,
   sidecar, and worker result evidence.

## Required Investigation Reads

Start every future implementation session with these files:

1. `AGENTS.md`
2. `docs/CURRENT_PROJECT_STATE.md`
3. `docs/architecture/ARCHITECTURE.md`
4. `docs/architecture/MODULE_MAP.md`
5. `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
6. `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
7. `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
8. `docs/inventories/API_ROUTE_INVENTORY.md`
9. `docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md`
10. `docs/testing/VALIDATION_LADDER_RUNBOOK.md`

Then read generated summaries before source for:

- `src/mediapipeline/core/processes/rerun_facade.py`
- `src/mediapipeline/core/processes/rerun_preview.py`
- `src/mediapipeline/core/processes/rerun_policy.py`
- `src/mediapipeline/core/processes/rerun_results.py`
- `src/mediapipeline/core/processes/launch_plans.py`
- `src/mediapipeline/core/processes/launch_runner.py`
- `src/mediapipeline/core/processes/preflight_facade.py`
- `src/mediapipeline/core/queue/facade.py`
- `src/mediapipeline/desktop/application/network_lifecycle_provider.py`
- `src/mediapipeline/desktop/network/coordinator_queue.py`
- `src/mediapipeline/desktop/network/worker_loops.py`
- `src/mediapipeline/desktop/network/protocol.py`
- `src/mediapipeline/desktop/network/worker_record.py`
- `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1`
- `ops/pipeline/entrypoints/MediaPipeline.ps1`

Open full source only when changing behavior or when the generated summary does
not expose the needed contract.

## Architecture Decisions Required Before Code

Do not start implementation until these decisions have written answers.

### D1. What Is The Distributed Unit?

Options:

| Option | Description | Initial assessment |
|---|---|---|
| Row claim | Each enabled CSV row becomes one coordinator claim. | Likely best fit with current worker one-file model. Needs row metadata and result reduction. |
| Chunk claim | A coordinator claim carries a window of CSV rows. | Higher throughput, but complicates worker failure, stop-after-current, row-level retry, and result evidence. |
| Whole CSV claim | One worker runs the current `Invoke-RerunCsv.ps1`. | Simplest dispatch, but poor distribution and high risk because the worker applies broad rerun policy locally. |
| Coordinator wrapper only | Coordinator runs current local CSV rerun while network workers remain unused. | Not a distributed feature; keep only as fallback. |

Preferred investigation path: row claim first. It aligns with current worker
claim/done/release semantics and lets the coordinator preserve per-row authority.

### D2. Where Is CSV Row State Stored?

The current local manifest lives under `LocalBase/RerunManifests` and contains
row statuses. Network mode needs coordinator-visible row state that survives
restart and stale worker recovery.

Investigate these storage options:

| Option | Description | Concern |
|---|---|---|
| Extend rerun manifest | Add network-specific row fields to the existing rerun manifest schema. | Must avoid breaking local CSV rerun readers. |
| New state file under `State/Rerun/Network` | Keep network-specific lease/result state separate, with references to the source manifest. | More files and inventories, but cleaner authority split. |
| Reuse `coordinator_inflight.json` only | Store row data only in network in-flight state. | Not enough for pending/not-yet-claimed rows or final row history. |

Likely target: existing rerun manifest remains the batch/row authority, with an
additional coordinator runtime state file only for network leases and recovery
if needed.

### D3. Who Applies Destination Policy?

Options:

| Option | Applies destination policy | Assessment |
|---|---|---|
| Coordinator reducer | Worker returns output artifact; coordinator applies CSV rerun destination policy. | Strongest authority boundary. Requires artifact transfer or shared output path handling. |
| Worker local policy | Worker applies pending-publish/final replacement policy and reports result. | Risky: workers would mutate coordinator final destinations and pending manifests. |
| Hybrid | Worker writes only a review output; coordinator later promotes/drains/replaces. | Conservative, but may reduce daily-use ergonomics. |

Preferred investigation path: coordinator reducer, or hybrid for Phase 1.
Workers should not mutate final-library destinations or coordinator pending
publish manifests until explicitly proven safe.

### D4. Where Do Worker Outputs Land?

CSV rerun currently rewrites nested pipeline `Outsource` to a local rerun
workspace output root. Distributed execution needs a coordinator-readable output
handoff.

Adopted decision:

Use a first-class Network Rerun Handoff model. Add an explicit
`NetworkRerunHandoffRoot` setting for a coordinator-readable, worker-writable
review/handoff area that is separate from source roots and final library
destinations. For each network CSV rerun row, the coordinator assigns a
per-row handoff folder under that root and gives the worker a job-scoped
effective config that rewrites `Outsource` and `LibraryProfiles.output_path`
to that handoff folder. The worker also rewrites `LocalBase` to an isolated
worker-local runtime root under its existing configured `LocalBase` for the
batch, row, worker, and claim.

Contract:

- Setting name: `NetworkRerunHandoffRoot`.
- Handoff path shape: `<NetworkRerunHandoffRoot>/<batch_id>/<row_key>/`.
- Remote workers require a UNC/shared path, not a coordinator-local drive path.
  Local drive handoff roots are valid only for coordinator-local workers.
- The handoff root must not overlap any configured source root, `Outsource`,
  `LibraryProfiles.output_path`, `LocalBase`, or pending-publish state root.
- The coordinator must be able to create, list, read, and later clean up the
  batch/row handoff folder.
- A worker must prove it can create, write, read, and delete a small probe file
  in its assigned row handoff folder before it can claim that row.
- If handoff validation fails before claim, the row is blocked and remains
  unclaimable.
- If handoff write fails during execution, the worker reports a failed or
  retryable row result with handoff-failure evidence.
- Handoff outputs remain in place until the coordinator reducer accepts,
  rejects, or explicitly cleans them up.
- Cleanup is coordinator-owned. Workers may clean only probe files and their
  own worker-local runtime files.

Workers may write only handoff output and result evidence for CSV rerun jobs.
They must not write directly to final library destinations, create final
pending-publish manifests, or apply CSV destination policy. The coordinator
reducer remains the owner of final promotion, pending publish, replacement,
review, and rejection decisions.

If the normal pipeline would otherwise park a failed handoff copy into
worker-owned `PendingServerPush`, Phase 4B must add a rerun handoff execution
mode that reports the row as a handoff failure instead. Worker-owned
pending-publish manifests are not an accepted Network CSV rerun handoff result.

This is the preferred permanent model because it reuses the normal pipeline
engine while preserving source safety, backend authority, coordinator-owned
destination policy, and durable row/result evidence. Worker-local-only output
should remain a fallback or future transport option because it requires a
separate artifact transfer protocol, retention policy, and retry model.

### D5. How Does Source Path Mapping Work For CSV Rows?

Current worker claims can carry `library_id` and `relative_path`. CSV rows often
carry absolute `source_path`. Future row plans should prefer:

1. `library_id` plus safe `relative_path` when the CSV row can be tied to a
   configured library profile.
2. Coordinator absolute `source_path` plus existing worker path map fallback.
3. Blocked row when neither path authority can be proven safe.

Do not add worker-local CSV path interpretation as a shortcut.

### D6. How Are Stop, Pause, Retry, And Continuation Modeled?

Local CSV rerun has stop-after-current via a rerun control marker. Network mode
has claim/release/done semantics plus coordinator lifecycle stop.

Investigate how to map:

- Stop after current row.
- Stop after currently claimed workers finish.
- Release claimed but unstarted rows.
- Retry failed or released rows.
- Continue pending rows only.
- Preserve failed/review/completed rows without automatic retry.

Stop behavior must not silently abandon worker done reports or leave rows stuck
as in-flight.

### D7. How Are Worker Result Artifacts Extended?

Current network worker result artifacts report one normal pipeline result. CSV
rerun network needs row-specific fields such as:

- rerun batch id
- original CSV path or import key
- source CSV row index
- rerun row key
- source path as coordinator saw it
- worker-local source path after mapping
- planned output path
- local output artifact path
- sidecar evidence
- route, publish state, output size, failure code
- whether destination policy was applied
- whether coordinator reduction is still pending

Any extension must be additive and backwards-compatible with existing network
worker result parsing.

### D8. How Is Progress Rendered?

Local CSV rerun status is visible as `Local rerun_csv`, active stdout tail, child
pipeline progress, and manifest rows.

Network mode needs distinct operator language:

- Coordinator: "Network CSV rerun batch", row counts, claimed count, pending
  count, completed count, failed/review count, stopped count.
- Worker: "CSV rerun row from coordinator", source display name, row index,
  batch id, current pipeline stage.
- Queue: show rerun rows as network-dispatched, not normal local queue rows.
- Network page: show claimed CSV rerun rows alongside normal worker claims.
- Diagnostics: show source row, worker, output handoff, and reducer state.

Avoid naming a remote worker as `Local rerun_csv`; that label is correct only
for the local process.

## Candidate Target Architecture

This is a candidate only. It must be confirmed or revised during investigation.

```text
Queue CSV Rerun tab
  -> /api/rerun/network-preview       (new, read-only, no mutation)
  -> /api/rerun/network/start-dry-run (new, read-only, no mutation)
  -> /api/rerun/network/start         (new, confirmed coordinator batch start)
  -> /api/rerun/network/control       (new, stop/continue controls)

Coordinator runtime
  -> creates network CSV rerun batch manifest
  -> exposes claimable row records through coordinator claim provider
  -> tracks leases in network in-flight registry
  -> receives worker done reports with rerun row metadata
  -> reduces worker output into rerun manifest row status
  -> applies or queues destination policy through backend-owned policy service

Worker runtime
  -> claims one rerun row
  -> resolves source path through library-relative/path-map rules
  -> runs normal pipeline once against a worker-owned scratch/runtime root
  -> reports result artifact plus rerun row metadata
  -> does not choose final publish/replacement policy independently
```

This model implies a new "claim provider" concept in the coordinator: normal
queue records and network CSV rerun rows must be claimable through one protocol
without racing or mixing identities.

## Investigation Phases

### Phase 0: Baseline And Contract Freeze

Goal: record current local CSV rerun and current network behavior before
changing anything.

Tasks:

- Create a fresh change packet for the investigation phase.
- Capture current route contracts for `/api/rerun/preview`, `/api/rerun/start`,
  `/api/rerun/results`, `/api/network/*`, and `/api/claim`.
- Capture current `ClaimResponse`, `DoneRequest`, and worker result artifact
  fields.
- Capture current rerun manifest row fields for a local successful run,
  review-workspace row, pending-publish row, and failed/blocked row.
- Capture active docs statements that say CSV rerun uses
  `uses_pipeline_start=false`.
- Add characterization tests only if current behavior lacks coverage.
- No behavior changes.

Exit criteria:

- A short evidence note or packet notes section lists the exact current
  contracts that future phases must intentionally change.
- No tests imply network CSV rerun support yet.

### Phase 1: Read-Only Network CSV Rerun Model

Goal: add backend read-only modeling for what a network CSV rerun batch would
look like, without starting workers or writing batch state.

Candidate route:

- `POST /api/rerun/network-preview`

Required evidence:

- CSV row validation reuses existing preview classifiers.
- Preview reports claimable rows, blocked rows, skipped rows, duplicate rows,
  source mapping readiness, output handoff readiness, and destination policy
  risk.
- Preview explicitly says `effect=none`, `writes_queue=false`,
  `writes_network_state=false`, `touches_media=false`.
- Preview indicates whether each row can produce `library_id` and
  `relative_path`, or whether worker path mapping would be required.
- Preview exposes a proposed row key that is stable enough for future claims.

Validation:

- Python route/unit tests for read-only behavior.
- Contract inventory update.
- WebView static test if surfaced in UI.
- No real-media validation required if this phase remains read-only.

### Phase 2: Network CSV Rerun Start Dry-Run Contract

Goal: define and test the confirmed-start contract without starting workers.

Candidate route:

- `POST /api/rerun/network/start-dry-run`

Required evidence:

- Validates `NetworkRole=coordinator`.
- Validates coordinator lifecycle readiness.
- Validates no conflicting local pipeline, local CSV rerun, audit, or existing
  network CSV rerun batch is active unless a specific continuation mode is
  requested.
- Validates worker availability only as evidence, not as a hard requirement
  unless the operator asks for a minimum worker count.
- Validates destination policy confirmations and collision policy.
- Reports exact state files the confirmed start would write.
- Reports exact media paths it would not touch.
- Reports rollback and cleanup expectations.
- Requires no source media, output, pending-publish, or queue mutation.

Validation:

- Strict command contract tests.
- Dry-run no-write tests with temp state root.
- Network lifecycle provider-precondition tests.
- Route inventory and command ownership updates.

### Phase 3: Coordinator Batch State Without Worker Execution

Goal: add the confirmed start path that creates a network CSV rerun batch in
coordinator-owned state, but still does not let workers process rows.

This phase should use a feature flag or disabled claim provider until row claim
execution is ready.

Candidate route:

- `POST /api/rerun/network/start`

Required behavior:

- Requires a fresh matching dry-run fingerprint or equivalent backend-owned
  proof.
- Requires strict boolean confirmation.
- Writes only coordinator network CSV rerun batch state and command journal
  evidence.
- Does not stage source files.
- Does not launch nested pipeline chunks.
- Does not mutate pending publish or final output.
- Exposes rows as not-yet-claimable or claim-disabled until Phase 4.

Validation:

- Command journal success/failure tests.
- State-file schema inventory update.
- Close-readiness tests for active network CSV batch state.
- Stop/cancel dry-run tests.
- No real-media validation unless the phase stages or processes media.

### Phase 4A: Network Rerun Handoff Foundation

Goal: make the worker output handoff path explicit and validated before any
CSV rerun row can be claimed by a worker.

Required behavior:

- Add a first-class `NetworkRerunHandoffRoot` setting.
- Validate the handoff root is outside source roots, `Outsource`,
  `LibraryProfiles.output_path`, `LocalBase`, and pending-publish state.
- Validate coordinator create/list/read/delete capability as evidence.
- Add worker handoff probe evidence before row claims are enabled.
- Validate path boundaries for local drive paths and UNC paths.
- Reject remote-worker handoff plans that use coordinator-local drive paths.
- Extend network preview and start dry-run evidence with handoff readiness.
- Block confirmed network CSV rerun start when enabled rows lack a safe
  handoff target.
- Plan per-batch and per-row handoff folders in coordinator-owned batch state.
- Do not start workers, process media, write final output, or mutate pending
  publish in this phase.

Validation:

- Settings/config validation tests for missing, unsafe, source-overlapping,
  final-output-overlapping, `LocalBase`-overlapping, and pending-state-
  overlapping handoff roots.
- Preview and start dry-run tests that report handoff readiness and blockers.
- Confirmed-start tests that write planned handoff paths into batch state
  without enabling row claims.
- Worker probe tests for writable and non-writable handoff folders.
- Path-boundary tests for local paths, UNC paths, and traversal attempts.
- No real-media validation required if this phase remains config/state only.

### Phase 4B: Claim Provider And Worker Protocol Extension

Goal: allow coordinator to hand one CSV rerun row to a worker through the
existing claim loop, without applying final destination policy.

Required design:

- Extend claim responses additively with `job_kind` or equivalent, while
  keeping existing normal queue workers compatible.
- Add rerun row metadata to claims.
- Include planned handoff root/path evidence in each rerun row claim.
- Make worker record construction preserve rerun metadata.
- Ensure workers still run exactly one assigned source.
- Ensure worker path mapping rejects unsafe relative paths.
- Materialize a job-scoped effective worker config for CSV rerun rows that
  rewrites `Outsource` and `LibraryProfiles.output_path` to the planned
  handoff folder.
- Materialize an isolated worker-local `LocalBase` for the batch, row, worker,
  and claim.
- Ensure worker-owned pending-publish manifests are not treated as successful
  Network CSV rerun handoff results.
- Ensure coordinator in-flight registry understands rerun row identity and
  source identity.
- Ensure duplicate claims cannot occur across normal queue records and CSV
  rerun rows.

Preferred first execution mode:

- Worker runs normal pipeline once for the claimed source.
- Worker writes output into a review/handoff location, not final library.
- Worker reports a result artifact with rerun metadata.
- Coordinator marks the row as `worker_completed_pending_reduction`.

Validation:

- Protocol compatibility tests.
- Claim/done/release tests for normal queue and CSV rerun rows together.
- Concurrent claim tests.
- Path mapping tests with local drive paths, UNC paths, library-relative paths,
  and rejected traversal.
- Worker crash/reclaim tests.
- Source hash preservation fixture tests.
- Handoff isolation tests proving source roots, final library roots, and
  pending-publish state are untouched.
- Real-media validation is required before this phase is considered complete,
  because a worker actually processes media.

### Phase 5: Coordinator Result Reducer

Goal: coordinator consumes worker results and updates network CSV rerun row
status without losing evidence.

Required behavior:

- Reads worker result artifacts.
- Verifies result belongs to the expected batch id, row key, claim id, worker
  id, and source identity.
- Classifies success, failed, retryable, terminal, review, and output-missing.
- Records output artifact evidence.
- Leaves final replacement/pending-publish action pending until policy reduction
  is explicitly implemented.
- Handles late done reports after stop or reclaim.
- Is idempotent on duplicate done reports.

Validation:

- Unit tests for every result classification.
- Stale claim/reclaim tests.
- Duplicate done report tests.
- Corrupt worker result artifact tests.
- UI read-model tests for row status.

Status (2026-07-06):

- Implemented under `MP-CHANGE-2026-0705-023`.
- The reducer stores worker-result snapshots, verifies batch/row/claim/worker
  and source identity, classifies success/failure/review/output-missing/corrupt
  results, records output evidence, and preserves duplicate/late done reports
  idempotently.
- `/api/rerun/results` now projects Network CSV rerun reducer rows as read-only
  Queue evidence with `pending_reduction` status and pending destination-policy
  state.
- Validation passed for Phase 5 compile and targeted reducer/read-model/network
  protocol tests. Strict change-packet coverage passed with
  `validate_changes --require-worktree-coverage`. A broader optional
  `test_network*.py` sweep exposed one existing worker crash-recovery assertion
  around corrupt `worker_state.json` quarantine behavior outside the Phase 5
  reducer path.
- No additional real-media validation was required beyond the Phase 4B worker
  gate because Phase 5 does not start new worker media processing or move media
  into final destinations.

### Phase 6: Destination Policy Integration

Goal: make network CSV rerun results land in the same daily-use destinations as
local CSV rerun, with coordinator-owned policy and manifest evidence.

This is the highest-risk phase.

Required behavior:

- Apply `review_workspace`, `pending_publish`, `publish_non_overlap`,
  `publish_replace_final`, and `auto_replace_clean_else_pending_review`
  semantics under coordinator authority.
- Preserve pending-publish duplicate destination guards.
- Preserve sidecar and subtitle evidence.
- Preserve source hash and source path safety.
- Preserve final replacement confirmations and `confirm_source_overwrite`
  semantics.
- Write manifest-backed evidence before moving media when required.
- Provide rollback/recovery evidence for partial moves.

Validation:

- Pending publish fixture tests.
- Destination collision tests.
- Sidecar carry-forward tests.
- Source/output hash preservation tests.
- PowerShell and Python integration tests.
- Representative real-media validation for at least:
  - one clean replacement
  - one pending-publish row
  - one review-workspace row
  - one failed row
  - one worker crash/retry row

Status (2026-07-06):

- Implementation is complete under `MP-CHANGE-2026-0705-024`.
- Coordinator reduction now applies destination policy only after Phase 5 accepts
  a verified handoff output. Workers still write only to
  `<NetworkRerunHandoffRoot>/<batch_id>/<row_key>/`; WebView remains
  read-only/caller-only for this policy.
- Implemented policy outcomes include review workspace, manifest-backed Pending
  Publish, non-overlapping final copy, confirmed final replacement, and
  fail-closed destination-policy failure with source and handoff preservation.
- Network batch rows now carry `destination_policy_result` evidence, and
  `/api/rerun/results` projects destination-policy status, Pending Publish
  paths, published paths, and failure state as backend-owned read-model data.
- Backend validation passed for compile, reducer/read-model tests, destination
  policy branch tests, pending-publish contracts, and network/facade regression
  tests.
- Representative real-media validation passed on 2026-07-06 using the Phase 4B
  real worker output as the Phase 6 destination-policy input. Evidence:
  `docs/RealMediaValidationRuns/network-csv-rerun-phase6-2026-07-06.md`.

### Phase 7: WebView Operator Surface

Goal: expose the feature as an option without making the frontend authoritative.

Likely placement:

- Queue CSV Rerun tab: local vs network execution mode.
- Network page: active network CSV rerun batch and worker claim rows.
- Home/Live: network CSV rerun progress summary.
- Diagnostics: row-to-worker result drilldown.
- Command History: network CSV rerun start/stop/reduce evidence.

Rules:

- WebView calls backend routes only.
- WebView must not author claim rows, row status, destination policy, or path
  decisions.
- Display filters must not narrow backend execution scope unless the backend
  preview materializes an explicit scoped CSV/batch with evidence.
- UI copy must distinguish local CSV rerun from network CSV rerun.

Validation:

- WebView static tests.
- Browser no-mutation smoke.
- Route inventory and DOM/export inventory updates.
- Network page smoke if controls are visible there.

Status (2026-07-06):

- Implementation is complete under `MP-CHANGE-2026-0705-025`.
- Queue CSV Rerun now exposes a local vs Network execution selector, Network
  minimum-worker input, backend Network preview routing, backend start dry-run,
  and confirmed Network start through `/api/rerun/network/start` with backend
  dry-run fingerprint and `confirm_start`.
- Network page now includes a read-only Network CSV Rerun evidence panel backed
  by `/api/rerun/results`, showing backend-authored batch, row, worker,
  reducer, destination-policy, Pending Publish, review, and published-output
  evidence without authoring network state.
- Command history and lifecycle evidence distinguish local CSV rerun,
  `rerun.network.start_dry_run`, and `rerun.network.start`.
- Inventories and generated summaries were refreshed for the new WebView DOM
  IDs, route ownership, and changed source/test/docs files.
- Validation passed for JavaScript syntax checks, targeted WebView static
  route/DOM/mutation-boundary tests, DOM inventory checks, and browser-backed
  Queue/Network smokes. Phase 7 did not require new real-media execution
  because it changed WebView caller/read surfaces only.

### Phase 8: End-To-End And Real-Media Gate

Goal: prove the feature works with real worker/coordinator flows and real media.

Required proof:

- Coordinator only: does not process local files unless configured for local
  worker mode.
- Worker only: claims only coordinator-assigned CSV rerun rows.
- Coordinator + local worker: local worker claims through network lifecycle, not
  normal Launch.
- Remote worker: source path mapping works for the target library layout.
- Stop after current preserves state and can continue pending rows.
- Crash/restart preserves row state and does not duplicate claims.
- Pending publish and final replacement evidence match existing local CSV rerun
  trust standards.
- Source hashes remain unchanged.

Validation should include real media because this phase touches source movement,
scratch, output movement, publish, and possibly FFmpeg execution in a new
coordination mode.

Status (2026-07-06):

- Implementation and validation are complete under `MP-CHANGE-2026-0705-027`.
- Added an executable Phase 8 integration test that starts a confirmed Network
  CSV rerun batch, claims a `csv_rerun_row`, proves duplicate-claim blocking,
  releases and reclaims the row, reports worker done, applies coordinator-owned
  Pending Publish destination policy, blocks terminal reclaim, preserves the
  source hash, and projects the result through `/api/rerun/results`.
- Real-media validation passed using the Phase 4B real source and real
  worker-produced MKV in a fresh isolated Phase 8 root. Evidence:
  `docs/RealMediaValidationRuns/network-csv-rerun-phase8-2026-07-06.md`.
- Physical remote-worker execution over SMB was not available in this
  environment. Remote-worker safety is covered by automated path/claim gating
  tests, and the remaining physical remote-worker run is site-specific to a real
  shared `NetworkRerunHandoffRoot` and deployed path mapping.
- Validation passed for the Phase 8 integration test, network claim/reducer
  destination tests, rerun results read model tests, network protocol/done
  tests, and Network CSV preview tests.

### Phase 9: Release Hardening

Goal: close the Network CSV Rerun implementation with aggregate route,
contract, WebView, generated-context, dependency-boundary, change-packet, and
real-media evidence checks.

Status (2026-07-06):

- Implementation and validation are complete under `MP-CHANGE-2026-0705-028`.
- Phase 9 did not add operator-facing Network CSV Rerun behavior. It hardened
  the release posture after Phases 4A through 8 and patched validation drift
  exposed by aggregate postflight.
- Aggregate route/contract tests passed for API payloads, command contracts,
  process launch, Network CSV claim/done/release flows, reducer read models,
  protocol runtime, and CSV preview.
- Aggregate WebView tests passed for Queue, Network, frontend mutation
  boundary, DOM/inventory coverage, diagnostics reports, and browser-backed
  Queue/Network smokes.
- AI guardrail postflight initially exposed stale generated context and a
  publish dependency-boundary cycle. Generated summaries/maps were refreshed,
  and the module-level publish cycle was removed by introducing
  `src/mediapipeline/core/publish/pending_contracts.py` as the neutral owner
  for shared Pending Publish schema constants and DTO/json helpers.
- The dependency-boundary checker now reports zero module-level cycles, no
  unused allowlist entries, and no unallowlisted hard findings. A pre-existing
  broad package-level cycle remains visible as an explicitly listed temporary
  package-cycle baseline in `docs/architecture/dependency_boundary_allowlist.txt`
  for future architecture cleanup; it was not introduced by Network CSV Rerun.
- Pending Publish focused tests passed after the publish dependency cleanup.
  No final publish, drain, source movement, sidecar, or media policy behavior
  changed in Phase 9, so no additional real-media run was required beyond the
  Phase 8 gate.
- Remaining deployment-specific limitation: no physical remote SMB worker was
  available in this environment. The release posture remains that physical
  remote validation should be run against the operator's real shared
  `NetworkRerunHandoffRoot` and worker path mapping before relying on a remote
  production worker.

## Route And Contract Sketch

Names are provisional. Update this section during Phase 0/1 if better route
names are chosen.

| Route | Effect | Purpose |
|---|---|---|
| `POST /api/rerun/network-preview` | none | Read-only analysis of CSV rows as network-claim candidates. |
| `POST /api/rerun/network/start-dry-run` | none | Backend dry-run for starting a network CSV rerun batch. |
| `POST /api/rerun/network/start` | network-state-write | Confirmed creation of coordinator-owned network CSV rerun batch. |
| `POST /api/rerun/network/control` | network-state-write | Stop-after-current, stop-after-claims-finish, cancel-not-started, or continue pending rows. |
| `GET /api/rerun/network/results` | read | Network CSV rerun batch and row read model. |

Any new command route must be added to:

- `src/mediapipeline/contracts/api_commands.py`
- `src/mediapipeline/contracts/api_routes_command.py`
- `src/mediapipeline/core/api/commands.py`
- appropriate command handler module
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- tests for strict booleans, route inventory, command journal, and contract
  payloads

Any new read route must be added to the matching read-route inventory and
contract tests.

## State And Schema Sketch

Potential state files:

| State file | Written by | Read by | Purpose |
|---|---|---|---|
| `State/Rerun/NetworkBatches/<batch_id>.json` | coordinator backend | backend read model, coordinator claim provider | Batch authority, row statuses, source CSV metadata, policy fields. |
| `State/Rerun/NetworkClaims/<batch_id>.json` | coordinator backend | coordinator lifecycle, diagnostics | Optional runtime lease/recovery supplement if `coordinator_inflight.json` is insufficient. |
| `State/Rerun/NetworkResults/<batch_id>/<row_key>.json` | coordinator backend | reducer, diagnostics | Durable copy of accepted worker result evidence. |

Before adding any state file:

- update `src/mediapipeline/core/paths/layout.py` or the appropriate path
  resolver
- update inventories
- decide whether PowerShell must read it
- add schema/reference docs
- add corrupt/missing/partial-file tests

## Claim Protocol Sketch

Potential additive `ClaimResponse` fields:

| Field | Meaning |
|---|---|
| `job_kind` | `pipeline_queue` or `csv_rerun_row`; default old behavior is normal queue. |
| `rerun_batch_id` | Coordinator-owned CSV rerun batch id. |
| `rerun_row_key` | Stable row identity. |
| `rerun_row_index` | Original CSV row index for operator evidence. |
| `rerun_policy` | Minimal destination/collision/original policy evidence needed by worker, if any. |
| `planned_output_path` | Coordinator-authored planned output, if needed for evidence. |
| `output_handoff` | Where the worker should put completed output or result evidence. |
| `source_identity` | Coordinator source identity hash/key for done-report verification. |

Rules:

- Existing workers that ignore new fields must remain safe.
- New workers must reject malformed `job_kind`.
- Worker done reports for `csv_rerun_row` must include the same row identity
  fields.
- Coordinator must reject a done report if row identity and claim identity do not
  match active state.

## Testing Matrix

Minimum future test families:

| Area | Required coverage |
|---|---|
| CSV preview | Existing blockers still block before network batch start. |
| Route contracts | New routes require strict booleans and publish correct `/api/contract` metadata. |
| Dry-run no-write | Network CSV dry-run writes no queue, network, output, source, or pending-publish state. |
| Batch start | Confirmed start writes only authorized network CSV batch state. |
| Claim concurrency | Normal queue and CSV rerun row claims cannot duplicate or race. |
| Worker path mapping | Library-relative, manual map, UNC, local drive, invalid traversal, missing path. |
| Worker result | Success, failure, retryable, terminal, corrupt result, mismatched claim, late done. |
| Stop/continue | Stop after current, stop after claims finish, continue pending, preserve failed/review rows. |
| Destination policy | Pending publish, review workspace, clean replacement, collision suffix/fail/replace. |
| Source safety | Source hash unchanged across success, failure, stop, crash, and retry. |
| Close readiness | Active network CSV batch makes close unsafe until safe stop/drain state. |
| WebView | No frontend-owned queue, claim, done, publish, drain, repair, rename, or media mutation. |

## Validation Ladder

Use the highest rung touched by the phase.

| Phase type | Minimum validation |
|---|---|
| Planning docs only | Markdown inspection plus change-packet validation. |
| Read-only preview/read model | Targeted Python route/unit tests, route inventory tests, no-write tests. |
| Command dry-run | Strict command contract tests, command journal dry-run tests, no-write tests. |
| Network lifecycle or claim protocol | Network protocol/runtime tests, concurrent claim tests, provider precondition tests. |
| Worker execution | Worker result artifact tests, process lifecycle tests, source hash tests. |
| Destination policy | Pending-publish fixture tests, publish/destination tests, sidecar evidence tests. |
| Media execution changes | Release gate plus representative real-media validation. |
| WebView controls | Static tests plus affected browser no-mutation smokes. |

Real-media validation is required once the feature processes media through a
worker or changes publish/final-placement behavior.

## Rollback Strategy

Each implementation phase must be independently revertible.

Preferred rollback sequence:

1. Disable Network CSV rerun route exposure or feature flag.
2. Leave local CSV rerun routes untouched.
3. Preserve existing network lifecycle routes.
4. Preserve existing normal queue worker claim behavior.
5. Preserve any written batch manifests for diagnostics, but block further
   claims if schema version is not supported.
6. Provide a read-only recovery/inspection route before any cleanup route.

Never roll back by deleting source media, worker outputs, pending publish
payloads, or final outputs.

## Agent Handoff Checklist

Before implementation, a future agent must answer these in its change packet:

- Which distributed unit is being implemented: row, chunk, or whole CSV?
- Which state file is the batch authority?
- Who applies destination policy?
- How does the implementation enforce `NetworkRerunHandoffRoot` and per-row
  handoff folders?
- How does source path mapping prove safety?
- How does stop-after-current work?
- How are retryable worker failures represented?
- What prevents duplicate claims?
- What makes close-readiness unsafe?
- Which route inventories and contracts changed?
- Which validation rung applies?
- Is real-media validation required for this phase?

## Recommended First Implementation Slice

The first code slice should be read-only:

1. Add a backend helper that converts existing CSV rerun preview rows into
   proposed network row candidates.
2. Do not add a visible WebView start control yet.
3. Expose the model through a read-only route or temporary test-only facade,
   depending on route policy.
4. Add tests proving no queue/network/media state is written.
5. Update inventories and generated summaries.

This gives the project an executable understanding of source mapping,
claimability, blockers, and destination-policy risk before any worker can touch
media.

## Explicit Stop Conditions

Stop and ask for operator direction if any investigation discovers that:

- workers would need write access to source roots;
- workers would need to mutate final library destinations directly in Phase 1;
- safe output handoff requires broad SMB write permissions that are not already
  part of the operator network model;
- source identity cannot be stable across coordinator and worker path mapping;
- pending-publish manifest ownership cannot stay coordinator-backed;
- duplicate claims cannot be prevented without changing normal queue semantics;
- the implementation would require reinterpreting `-DryRun`;
- the only viable design is "run whole CSV rerun wrapper on one worker".

## Open Questions

- Should network CSV rerun be allowed only when `NetworkRole=coordinator`, or
  should a standalone machine be allowed to create a network-style batch for
  local testing?
- Should coordinator-local workers be allowed to claim network CSV rerun rows,
  or should early phases require at least one remote worker?
- Should rows with unsupported source path mapping be blocked or allowed only
  for coordinator-local execution?
- For Phase 6, should coordinator-owned destination policy reduce rows
  incrementally as handoff results arrive, or only after the whole batch reaches
  a reducer phase?
- Should a network CSV rerun batch pause normal queue claims until complete, or
  should normal queue and rerun rows share one prioritized claim stream?
- Should CSV row priority be derived from CSV order, existing priority markers,
  issue severity, or an explicit rerun priority column?
- How should already completed local CSV rerun manifests interact with future
  network continuation?
- What UI wording keeps "local CSV rerun" and "network CSV rerun" distinct
  without adding redundant safety prompts?
