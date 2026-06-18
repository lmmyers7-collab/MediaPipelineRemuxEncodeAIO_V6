# Worker Review: W13 - PowerShell Local Worker And Pipeline Compatibility

## Scope

Review-only audit of PowerShell local-worker claim/store/mutex/progress/result semantics and their compatibility with Python network worker state, done reports, diagnostics, and operator evidence.

Assigned source scope reviewed:

| File | Symbols reviewed | Coverage |
|---|---|---|
| `ops/pipeline/engine/queue/local_worker_slots.ps1` | `Invoke-MediaQueuePhasePlanLocalWorkerSlots`, `Resolve-MediaPipelineLocalWorkerSlotCompletion` | complete |
| `ops/pipeline/engine/queue/worker_claim_store.ps1` | slot layout, claim keying, claim/repair/release/update store helpers, active-status policy | complete; finding W13-003 |
| `ops/pipeline/engine/queue/worker_mutex.ps1` | worker mutex naming, protected blocks, atomic JSON read/write helpers | complete |
| `ops/pipeline/engine/queue/worker_process.ps1` | child start/argument construction, worker metadata, process stop/kill tree | complete; finding W13-003 |
| `ops/pipeline/engine/queue/worker_progress.ps1` | active job snapshots, compatibility progress, parent counter updates | complete |
| `ops/pipeline/engine/process/worker_result.ps1` | `Write-MediaPipelineWorkerChildResult`, result field extraction | complete; finding W13-002 |
| `ops/pipeline/entrypoints/MediaPipeline.ps1` | single-file worker-child result writes and fallback result path | focused supporting read |
| `ops/pipeline/engine/process/pipeline_processing.ps1` | process result schema and terminal/retry fields | focused supporting read |
| `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | worker single-file launcher and process watcher | focused compatibility read; finding W13-001 |
| `src/mediapipeline/desktop/network/worker_done.py` | completion done payload construction | focused compatibility read |
| `src/mediapipeline/desktop/network/protocol.py` | `DoneRequest` fields and coercion | focused compatibility read |
| `src/mediapipeline/desktop/network/worker_state.py`, `worker_claims.py`, `worker.py`, `worker_loops.py`, `worker_record.py`, `worker_parts/*`, `coordinator_queue.py`, `coordinator_http_handlers.py`, `dispatcher.py`, `registry.py` | network worker state, claim, done, heartbeat, release, coordinator completion flow | targeted compatibility review |

Assigned tests/evidence reviewed:

| File | Coverage |
|---|---|
| `ops/pipeline/tests/Unit/Invoke-LocalWorkerSlotChecks.ps1` | complete |
| `ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1` | complete |
| `tests/python/desktop/test_network_worker_state.py` | generated summary and targeted run |
| `tests/python/desktop/test_network_worker_runtime.py` | generated summary and targeted run |
| `tests/python/desktop/test_network_worker_source_policy.py` | generated summary and targeted run |
| `tests/python/desktop/test_network_done_release.py` | generated summary and targeted run |
| `tests/python/desktop/test_network_protocol_runtime.py` | generated summary and targeted run |
| `tests/python/desktop/test_application_facade_process_launch.py` | focused read/run of claimed-job start/done test |
| `docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md`, `docs/testing/TEST_COVERAGE_MATRIX.md`, `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`, `docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` | release/test inventory evidence for worker behavior, network smokes, and legacy-surface references |

## Required Reads Completed

Read in order: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/FILE_LIFECYCLE_MAP.md`, `docs/testing/VALIDATION_LADDER_RUNBOOK.md`, and the W13/shared output contract in `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`.

Generated summaries were read before full source for all assigned PowerShell files, assigned PowerShell tests, assigned Python network files/tests, and the two focused supporting PowerShell reads (`ops/pipeline/entrypoints/MediaPipeline.ps1`, `ops/pipeline/engine/process/pipeline_processing.ps1`).

## Coverage Ledger

| Area | Evidence | Result |
|---|---|---|
| Local worker claim/store lifecycle | `worker_claim_store.ps1:19-49`, `183-236`, `238-334`; `Invoke-LocalWorkerClaimLifecycleChecks.ps1` | Reviewed: claim keying and duplicate source prevention are compatible with retry; finding W13-003 for nondurable stale-result diagnostics after slot reuse. |
| Local worker process ownership | `worker_process.ps1:30-78`, `80-99`; claim lifecycle tests | Reviewed: production local-worker launch passes `-WorkerChild`, slot/run/claim IDs, and a result path; no source mutation found. |
| Local worker result validation | `local_worker_slots.ps1:66-107`, `207-234`; `Invoke-LocalWorkerSlotChecks.ps1` | Reviewed: local scheduler rejects missing, unreadable, wrong schema, wrong claim, wrong run, and non-boolean `Success`; no finding. |
| Worker-result payload fields | `worker_result.ps1:21-90`; `pipeline_processing.ps1:11-52`; `protocol.py:172-236` | Finding W13-002: PowerShell drops terminal/retry fields that Python done reports need. |
| Network worker process done bridge | `network_lifecycle_provider.py:126-157`, `554-593`; `MediaPipeline.ps1:592-697`; `worker_done.py:32-78` | Finding W13-001: network worker reports exit-code-only done state and does not consume the PowerShell worker result artifact. |
| Source mutation boundary | `worker_process.ps1:42-43`; `worker_mutex.ps1:91-122`; assigned source search for `Remove-Item`, `Move-Item`, source deletes | Reviewed: local-worker helper cleanup is limited to slot result/stdout/stderr and JSON temp/bak files; no source media mutation found in assigned helpers. |
| Publish/drain boundary | `worker_result.ps1:50-77`; `coordinator_queue.py:445-502`; `done_outcome.py` supporting read | Reviewed: done handling logs/removes queue records but does not publish/drain directly; finding W13-001 affects evidence fidelity, not direct publish bypass. |
| Removed `Pipeline/Modules` and root-launcher assumptions | focused search in assigned PowerShell, tests, Python network files, and release/test inventory docs | No assigned local-worker code or tests rely on removed `Pipeline/Modules` or root launchers. Inventory docs mostly reference canonical `ops/scripts`; one unrelated static-files freshness note still names an old release script in `TEST_COVERAGE_MATRIX.md:1256`. |

Validation/evidence commands:

| Command | Result |
|---|---|
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerSlotChecks.ps1` | Passed: `Local worker slot checks passed.` |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerClaimLifecycleChecks.ps1` | Passed: `Local worker claim lifecycle checks passed.` |
| `$env:PYTHONPATH='src'; .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_worker_state tests.python.desktop.test_network_worker_runtime tests.python.desktop.test_network_worker_source_policy tests.python.desktop.test_network_done_release tests.python.desktop.test_network_protocol_runtime` | Passed: 101 tests. |
| `$env:PYTHONPATH='src'; .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_process_launch.ApplicationFacadeProcessLaunchTests.test_worker_provider_claimed_job_starts_backend_single_file_and_reports_done` | Passed: 1 test. The test asserts `mode="once"`, `single_file`, and success reporting, but not worker-result parsing or publish/output fields. |

## Findings

| id | severity | file | line / symbol | problem |
|---|---|---|---|---|
| W13-001 | P1 | `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | `_watch_claimed_process`, lines 149-157; `_start_network_claimed_job`, lines 585-593 | Network workers report completion from process exit code only and do not consume the PowerShell `local_worker_result.v1` artifact. |
| W13-002 | P2 | `ops/pipeline/engine/process/worker_result.ps1` | `Write-MediaPipelineWorkerChildResult`, lines 40-81 | The local worker result schema drops `QueueTerminal` and `Retryable`, so it is not sufficient to populate Python network done retry semantics. |
| W13-003 | P2 | `ops/pipeline/engine/queue/worker_claim_store.ps1`; `ops/pipeline/engine/queue/worker_process.ps1` | `Repair-MediaPipelineLocalWorkerClaims`, lines 207-214; `Start-MediaPipelineLocalWorkerChild`, lines 41-43 | Stale worker-result diagnostics are only preserved at a per-slot path and are deleted on the next slot start. |

## Detailed Findings

### W13-001

- `id`: W13-001
- `severity`: P1
- `file`: `src/mediapipeline/desktop/application/network_lifecycle_provider.py`
- `line`: `_watch_claimed_process`, lines 149-157; `_start_network_claimed_job`, lines 585-593
- `symbol`: `_watch_claimed_process`
- `problem`: The Python network worker launcher starts a backend single-file process by passing only `single_file`/`mode="once"` into `start_pipeline`, then the watcher posts done with `success`, generic `completion_status`, generic route `network_lifecycle_single_file`, and `queue_terminal=False`. It does not provide a worker-result path to the PowerShell child and does not read `local_worker_result.v1` after the process exits.
- `impact`: Network coordinator/operator evidence can mark a claimed job as generically processed without the PowerShell-owned route, publish state, publish mode, output path, output size, error code, or result reason. Pending-publish versus published output becomes invisible to the network done report, and diagnostics cannot tie done state back to the same claim/run validation that local worker slots enforce. I did not find a direct publish/drain bypass here; the risk is that network mode loses the backend policy outcome and reports a weaker completion record.
- `evidence`: PowerShell single-file worker-child mode writes `Write-MediaPipelineWorkerChildResult` on normal completion and fallback paths (`MediaPipeline.ps1:633-639`, `666-693`). The result payload includes route, publish, output, worker slot/run/claim, reason, and error fields (`worker_result.ps1:60-81`). The Python done contract can carry output/publish/route/failure fields (`protocol.py:176-195`; `worker_done.py:32-78`). The network watcher currently sends only exit-code-derived fields (`network_lifecycle_provider.py:149-157`) and the launcher supplies no result artifact location (`network_lifecycle_provider.py:585-593`). The focused Python test for this path asserts only `single_file`, `mode`, and `success` (`test_application_facade_process_launch.py:427-433`).
- `suggested fix direction`: Launch claimed network work through a worker-child/result-artifact contract, or otherwise arrange an equivalent backend process-result artifact. After process exit, parse and validate `local_worker_result.v1` against the claimed job identity, then map `Status`, `Success`, `Reason`, `ErrorCode`, `Route`, `PublishState`, `PublishMode`, `OutputPath`, and `OutputSizeBytes` into `build_completion_done_request`.
- `suggested validation/tests`: Add a network lifecycle provider test that creates a synthetic worker result with publish/output/route fields and asserts the dispatcher receives those fields in `mark_done`. Add missing/unreadable/wrong-claim result tests mirroring `Invoke-LocalWorkerSlotChecks.ps1`, and verify pending-publish state is surfaced without invoking publish/drain from the worker.

### W13-002

- `id`: W13-002
- `severity`: P2
- `file`: `ops/pipeline/engine/process/worker_result.ps1`
- `line`: `Write-MediaPipelineWorkerChildResult`, lines 40-81
- `symbol`: `Write-MediaPipelineWorkerChildResult`
- `problem`: `New-MediaPipelineProcessFileResult` carries `QueueTerminal` and `Retryable`, but `Write-MediaPipelineWorkerChildResult` does not extract or serialize those fields into `local_worker_result.v1`.
- `impact`: Even after W13-001 is fixed, the PowerShell local-worker artifact is not sufficient to faithfully populate the Python `DoneRequest` fields that decide retry behavior (`queue_terminal` and `retry_on_failure`). A terminal failure or non-retryable decision can be reduced to `Status`/`Success`/`Reason`, leaving the coordinator to default or infer retry policy.
- `evidence`: Process results include `QueueTerminal` and `Retryable` (`pipeline_processing.ps1:16-17`, `36-37`) and write those values into job-completed event evidence (`pipeline_processing.ps1:89-104`). The worker-result writer extracts status, success, reason, error, route, publish, and output fields (`worker_result.ps1:40-55`) but its payload omits `QueueTerminal` and `Retryable` (`worker_result.ps1:60-81`). Python `DoneRequest` has explicit `queue_terminal` and `retry_on_failure` fields (`protocol.py:189-195`), and `build_completion_done_request` derives retry from `queue_terminal` (`worker_done.py:45-49`).
- `suggested fix direction`: Add `QueueTerminal` and `Retryable` to `local_worker_result.v1` as backward-compatible optional fields, sourced from `ProcessResult` with conservative defaults. Map them explicitly when building network done reports.
- `suggested validation/tests`: Extend `Invoke-PipelineQueueEngineChecks.ps1` or `Invoke-LocalWorkerSlotChecks.ps1` to assert worker-result payloads include terminal/retry fields. Add Python tests that parse a PowerShell worker result with `QueueTerminal=true`/`Retryable=false` and assert `DoneRequest.queue_terminal=True` and `retry_on_failure=False`.

### W13-003

- `id`: W13-003
- `severity`: P2
- `file`: `ops/pipeline/engine/queue/worker_claim_store.ps1`; `ops/pipeline/engine/queue/worker_process.ps1`
- `line`: `Repair-MediaPipelineLocalWorkerClaims`, lines 207-214; `Start-MediaPipelineLocalWorkerChild`, lines 41-43
- `symbol`: `Repair-MediaPipelineLocalWorkerClaims`
- `problem`: Stale active claims with an existing result file are released with a note that the prior result remains available for diagnostics, but the result path is the fixed per-slot `worker_result.json`. The next worker start for that slot deletes that file before launching.
- `impact`: If the controller dies after a child writes `worker_result.json` but before finalizing the claim, repair correctly releases the stale claim and allows retry, but the diagnostic result can disappear as soon as the slot is reused. The claim store retains release reason text, not the actual result payload, so operator evidence for the orphaned result is not durable across retry.
- `evidence`: Slot layout uses one fixed result file per slot (`worker_claim_store.ps1:25-45`). Repair marks a stale active claim with a result as `released_stale_result` and says the prior result file remains available (`worker_claim_store.ps1:207-214`). Starting the next child removes `$SlotLayout.ResultFile` before launch (`worker_process.ps1:41-43`). The claim lifecycle test proves stale-result claims release and the source can be claimed again (`Invoke-LocalWorkerClaimLifecycleChecks.ps1:61-112`), but it does not assert that the old result is archived or survives slot reuse.
- `suggested fix direction`: When repair sees a stale result file, copy or move the worker result to a per-claim diagnostic artifact under the slot `Failures/Artifacts` tree or embed a bounded result summary in the claim before releasing it. Then make the next start clean only the active per-slot result after the stale artifact is durable.
- `suggested validation/tests`: Add a claim lifecycle test that writes a stale result, runs repair, starts/reuses the same slot, and asserts the stale result evidence still exists in the per-claim archive or claim-store summary.

## Test Coverage Gaps

| Gap | Risk | Suggested coverage |
|---|---|---|
| Network lifecycle worker tests do not create or parse a `local_worker_result.v1` artifact. | Exit-code-only done reporting can pass while publish/output/route/error evidence is dropped. | Add `test_worker_provider_claimed_job_reads_worker_result_and_reports_done_fields` covering success, pending publish, failure, wrong claim/run, missing result, and unreadable result. |
| PowerShell worker-result tests assert schema/version presence but not terminal/retry fields. | Future network done mapping still cannot preserve terminal failure semantics. | Add assertions for `QueueTerminal` and `Retryable` in worker-result payload tests. |
| Stale-result repair tests release claims but do not prove diagnostic result durability after slot reuse. | Orphaned result evidence can be deleted before an operator sees it. | Add a slot reuse test that archives or embeds stale result evidence before a new child deletes the per-slot result file. |
| No combined PowerShell-result-to-Python-done contract test exists. | PowerShell and Python can drift independently even while their isolated unit suites pass. | Add a small fixture-based test that maps a representative PowerShell `local_worker_result.v1` into Python `DoneRequest` fields. |

## Boundary Risks

- No PowerShell source, Python source, generated summaries, runtime state, config, media, queue files, or aggregate review files were edited.
- The assigned local-worker helper files do not delete, overwrite, move, or publish source media. Cleanup found in scope is limited to worker slot result/stdout/stderr files and JSON temp/bak files.
- The PowerShell local-worker path preserves backend ownership of media policy: child processing still goes through `Invoke-MediaPipelineProcessFile`, and result fields are descriptive evidence rather than independent publish/drain commands.
- The Python coordinator done path reviewed does not directly publish or drain output. It records completion/failure and queue disposition. W13-001 makes that evidence incomplete for network workers, but does not show a worker-side publish bypass.
- I found no stale `Pipeline/Modules` or removed root-launcher assumptions in assigned local-worker code or tests. Legacy references returned by search were guardrail tests or inventories documenting removal, except an unrelated static-files freshness note in `docs/testing/TEST_COVERAGE_MATRIX.md:1256`.
- Locking/orphan handling is realistic for local Windows operation: named mutexes guard claim stores, abandoned mutexes are handled, atomic JSON writes use temp/bak replacement, and claim identity checks include PID, start time, metadata, owner run, claim id, and result path.

## Files With No Findings

| File / symbol | Result |
|---|---|
| `ops/pipeline/engine/queue/local_worker_slots.ps1` / `Resolve-MediaPipelineLocalWorkerSlotCompletion` | Reviewed: no findings for missing/unreadable/wrong schema/wrong claim/wrong run/non-boolean success handling. |
| `ops/pipeline/engine/queue/local_worker_slots.ps1` / `Invoke-MediaQueuePhasePlanLocalWorkerSlots` | Reviewed: no findings for post-start claim update failure cleanup, stopped-process release, parent counter application, or max-slot scheduling. |
| `ops/pipeline/engine/queue/worker_claim_store.ps1` / source keying and duplicate claim checks | Reviewed: no findings; normalized full-path source keys prevent active duplicate claims for the same source. |
| `ops/pipeline/engine/queue/worker_claim_store.ps1` / live identity verification | Reviewed: no findings outside W13-003; PID reuse is guarded by process start time and metadata checks. |
| `ops/pipeline/engine/queue/worker_mutex.ps1` | Reviewed: no findings for mutex naming, abandoned mutex handling, final-state lock suffixing, or atomic JSON write cleanup. |
| `ops/pipeline/engine/queue/worker_process.ps1` / child argument construction | Reviewed: no findings outside W13-003; production local-worker launch passes `-SingleFile`, `-WorkerChild`, `-WorkerSlotId`, `-WorkerRunId`, `-WorkerClaimId`, and `-WorkerResultPath`. |
| `ops/pipeline/engine/queue/worker_process.ps1` / process stop | Reviewed: no findings; stop attempts main-window close, bounded wait, then process-tree kill. |
| `ops/pipeline/engine/queue/worker_progress.ps1` | Reviewed: no findings for active job snapshot shape, compatibility progress fields, or parent counter increments. |
| `ops/pipeline/engine/process/worker_result.ps1` / publish/output/route fields | Reviewed: no findings for `PublishState`, `PublishMode`, `OutputPath`, `OutputSizeBytes`, route, route reason, claim/run IDs, and fallback failure fields; W13-002 covers omitted terminal/retry fields. |
| `src/mediapipeline/desktop/network/worker_state.py` | Reviewed: no findings for pending done retry before new claims, crash recovery done reports, or atomic state writes in the focused W13 compatibility scope. |
| `src/mediapipeline/desktop/network/worker_claims.py` | Reviewed: no findings for release-on-schedule/start/heartbeat setup failure and pending done preservation after failed POST. |
| `src/mediapipeline/desktop/network/protocol.py` / `DoneRequest` | Reviewed: no findings; the Python contract can represent the fields W13-001/W13-002 need to preserve. |
| `ops/pipeline/tests/Unit/Invoke-LocalWorkerSlotChecks.ps1` | Reviewed and run: no findings. |
| `ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1` | Reviewed and run: no findings outside the missing stale-result durability assertion in W13-003. |

## Incomplete Coverage

- Did not run a real pipeline process, media encode, FFmpeg/ffprobe, publish/drain, queue mutation workflow, browser smoke, or Tauri shell.
- Did not run the full Python desktop test suite or full `test_network_workflow.py`; targeted network worker/done/protocol tests passed.
- Did not inspect every release/test inventory document end to end; searches and focused reads covered worker behavior and stale launcher/module references relevant to W13.
- Did not modify or regenerate generated summaries because the W13 prompt forbids generated-summary edits.

## Suggested Follow-Up Prompts

1. Fix W13-001 by adding a worker-result artifact bridge for network claimed jobs, then test publish/output/route/error propagation without invoking publish/drain from the worker.
2. Fix W13-002 by adding `QueueTerminal` and `Retryable` to `local_worker_result.v1`, then map those fields into Python `DoneRequest`.
3. Fix W13-003 by archiving stale per-slot worker results before claim repair releases a source for retry, then add a slot reuse durability test.
