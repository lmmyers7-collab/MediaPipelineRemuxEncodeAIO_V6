# Worker Review: W04 - Done, Release, Reaper, And Outcome Handling

## Scope

Review-only audit of coordinator/worker terminal outcome handling for network mode.

Assigned source scope reviewed:

- `src/mediapipeline/desktop/network/use_cases/done_outcome.py`
- `src/mediapipeline/desktop/network/coordinator_queue.py` done/release helpers
- `src/mediapipeline/desktop/network/coordinator_lifecycle.py` reaper helpers
- `src/mediapipeline/desktop/network/coordinator_state.py`
- `src/mediapipeline/desktop/network/registry.py` completion/reclaim/unclaim paths
- `src/mediapipeline/desktop/network/worker_done.py`
- `src/mediapipeline/desktop/network/worker_parts/results.py`
- `src/mediapipeline/desktop/network/cluster_log.py`

Supporting source opened because the assigned questions require the actual HTTP and worker persistence paths:

- `src/mediapipeline/desktop/network/coordinator_http_handlers.py`
- `src/mediapipeline/desktop/network/worker_state.py`
- `src/mediapipeline/desktop/network/worker_claims.py`
- `src/mediapipeline/desktop/network/worker_parts/state_reports.py`
- `src/mediapipeline/desktop/network/worker_loops.py`
- `src/mediapipeline/desktop/network/protocol.py`

Assigned tests/evidence reviewed:

- `tests/python/desktop/test_network_done_release.py`
- `tests/python/desktop/test_network_crash_recovery.py`
- `tests/python/desktop/test_network_workflow.py`
- `tests/python/desktop/test_network_coordinator_http.py`
- `tests/python/desktop/test_network_coordinator_source_policy.py`
- `tests/python/desktop/test_network_worker_state.py`

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/FILE_LIFECYCLE_MAP.md`
- `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
- `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`
- Generated summaries for every assigned source/test file, plus summaries for supporting files opened outside the assigned scope.

## Coverage Ledger

| File | Coverage | Notes |
|---|---|---|
| `src/mediapipeline/desktop/network/use_cases/done_outcome.py` | Reviewed | Success/failure side effects, queue removal, save failure handling. |
| `src/mediapipeline/desktop/network/coordinator_queue.py` | Reviewed | `mark_done`, `release`, `_emit_done_outcome`, `_remove_from_queue`. |
| `src/mediapipeline/desktop/network/coordinator_lifecycle.py` | Reviewed | `_reaper_loop`, shutdown save behavior. |
| `src/mediapipeline/desktop/network/coordinator_state.py` | Reviewed | cluster-log append/safe logging behavior. |
| `src/mediapipeline/desktop/network/registry.py` | Reviewed | `complete`, `unclaim`, `reclaim_stale`, `save`, `load`, failure ledger. |
| `src/mediapipeline/desktop/network/worker_done.py` | Reviewed | done/release payload builders. |
| `src/mediapipeline/desktop/network/worker_parts/results.py` | Reviewed | worker terminal cluster-log payloads. |
| `src/mediapipeline/desktop/network/cluster_log.py` | Reviewed | formatting/redaction behavior relevant to terminal evidence. |
| `src/mediapipeline/desktop/network/coordinator_http_handlers.py` | Supporting review | `/api/done` terminal, release, unknown-job, and owner-mismatch handling. |
| `src/mediapipeline/desktop/network/worker_state.py` | Supporting review | pending done flush, crash recovery, accepted-report clearing. |
| `src/mediapipeline/desktop/network/worker_claims.py` | Supporting review | worker `mark_done`, `release`, `_do_release`. |
| `src/mediapipeline/desktop/network/worker_parts/state_reports.py` | Supporting review | pending report persistence. |
| `src/mediapipeline/desktop/network/worker_loops.py` | Supporting review | pre-claim pending-done flush gate. |
| `src/mediapipeline/desktop/network/protocol.py` | Supporting review | `DoneRequest` fields/coercion. |

## Findings

| id | severity | file | line | symbol | problem |
|---|---|---|---|---|---|
| W04-001 | P1 | `src/mediapipeline/desktop/network/use_cases/done_outcome.py` | `handle`, `_save_registry_after_done` | `CoordinatorDoneOutcomeService` | Terminal done/release reports are acknowledged to the worker even when durable coordinator state save fails after in-memory state mutation. |
| W04-002 | P1 | `src/mediapipeline/desktop/network/worker_state.py` | `_flush_pending_done_report` | pending done 404 handling | Pending terminal reports are discarded on coordinator 404 even though the coordinator did not accept or durably record the done payload. |
| W04-003 | P2 | `src/mediapipeline/desktop/network/coordinator_lifecycle.py` | `_reaper_loop` | stale reclaim evidence | Stale reclaim evidence depends on best-effort cluster logging; if logging fails, the saved registry only preserves the absence of the job, not the reclaim reason/evidence. |

## Detailed Findings

### W04-001

- `id`: W04-001
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/use_cases/done_outcome.py`; supporting paths `src/mediapipeline/desktop/network/coordinator_http_handlers.py`, `src/mediapipeline/desktop/network/worker_claims.py`
- `line`: `done_outcome.py:56-64`, `done_outcome.py:79-88`, `done_outcome.py:199-208`, `done_outcome.py:226-243`, `coordinator_http_handlers.py:325-341`, `coordinator_http_handlers.py:414-431`, `worker_claims.py:240-242`, `worker_claims.py:288-290`
- `symbol`: `CoordinatorDoneOutcomeService.handle`, `CoordinatorDoneOutcomeService._save_registry_after_done`, `CoordinatorHttpHandlersMixin._http_done`, `WorkerClaimMixin.mark_done`, `WorkerClaimMixin.release`
- `problem`: The coordinator mutates in-memory terminal state with `registry.complete()` or `registry.unclaim()`, then applies or schedules queue/log side effects, then catches registry save failures and still lets `/api/done` return `{"status": "ok"}`. The worker treats that HTTP success as accepted and clears its only pending done/release retry state. Release has the same acceptance problem: `_http_done` catches `registry.save()` failure after `unclaim()` and still sends `{"status": "ok"}`.
- `impact`: A worker can erase its durable terminal report while the coordinator has not durably saved the terminal transition. If the coordinator crashes after this path, `coordinator_inflight.json` can still contain stale in-flight ownership or can miss failure-ledger/session evidence, while queue removal may already have been scheduled or directly applied. This is a realistic distributed done-handling correctness failure and can obscure rerun/review evidence after a success, terminal failure, or clean release.
- `evidence`: `CoordinatorDoneOutcomeService.handle()` calls `_handle_success()` or `_handle_failure()` before `_save_registry_after_done()` (`done_outcome.py:56-64`). Success and terminal failure paths schedule or directly remove queue records before the save helper (`done_outcome.py:79-88`, `done_outcome.py:199-208`). `_save_registry_after_done()` catches save exceptions, logs an `inflight_save_failed` event, and does not raise (`done_outcome.py:226-243`). `_http_done()` sends `{"status": "ok"}` after `_emit_done_outcome()` (`coordinator_http_handlers.py:414-431`). Release catches save failures and still sends OK (`coordinator_http_handlers.py:325-341`). The worker clears state on any successful POST return (`worker_claims.py:240-242`, `worker_claims.py:288-290`).
- `suggested fix direction`: Make done/release acceptance contingent on durable coordinator state transition. Either save the registry transaction before queue removal and before HTTP 200, or return a non-OK/retryable status when the save fails so the worker keeps its pending report. Treat cluster logging as best-effort, but treat terminal registry persistence as part of acceptance. Keep queue removal behind the successful durable transition.
- `suggested validation/tests`: Add tests where `registry.save()` fails after `complete()` and after `unclaim()` and assert `/api/done` is not accepted, worker pending done/release state is retained, and queue records are not removed. Add a crash/restart regression with stale `coordinator_inflight.json` to prove a completed report is not lost.

### W04-002

- `id`: W04-002
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/worker_state.py`; supporting path `src/mediapipeline/desktop/network/coordinator_http_handlers.py`
- `line`: `worker_state.py:202-215`, `coordinator_http_handlers.py:377-393`, `coordinator_http_handlers.py:296-312`, `tests/python/desktop/test_network_worker_state.py:251-268`
- `symbol`: `WorkerStateMixin._flush_pending_done_report`, `CoordinatorHttpHandlersMixin._http_done`
- `problem`: A pending terminal done/release report is discarded when replay receives coordinator 404. A 404 is not an accepted terminal report and does not durably record the payload fields that matter for review, such as `success`, `output_path`, `completion_status`, `publish_state`, `publish_mode`, `queue_terminal`, `reason_code`, and `reason`.
- `impact`: A late success or terminal failure after stale reclaim can lose its strongest evidence. The coordinator's unknown-job response prevents active-work corruption, but the worker then clears the only persisted payload and may claim new work. If the late report represented a successful output, pending-publish park, or queue-terminal manual-review outcome, the operator is left with only local logs and a coordinator `done_not_found`/`release_not_found` event that lacks the terminal payload and usually lacks source-path context.
- `evidence`: `_http_done()` returns `{"status": "not_found"}` with HTTP 404 for unknown completion reports (`coordinator_http_handlers.py:377-393`) and unknown releases (`coordinator_http_handlers.py:296-312`). `_flush_pending_done_report()` interprets HTTP 404 as unrecoverable, clears worker state, and returns `True` so the worker can claim again (`worker_state.py:202-215`). The current test suite codifies this discard behavior in `test_flush_discards_pending_report_unknown_to_coordinator` (`tests/python/desktop/test_network_worker_state.py:251-268`).
- `suggested fix direction`: Add a coordinator-owned late-terminal-report ledger that records unknown/reclaimed done payloads without mutating active work, then return a distinct accepted-for-evidence status such as `late_recorded`. The worker should clear pending done only after `ok` or `late_recorded`; otherwise it should retain the payload and keep claims blocked or surface an operator action. At minimum, do not discard success or queue-terminal payloads on a bare 404 without preserving them in worker-visible review state.
- `suggested validation/tests`: Simulate stale reaper reclaim, then replay a pending success with `publish_state="pending_publish"` and assert the coordinator records late evidence without closing a new active claim. Add a worker test proving pending done remains on 404 unless the coordinator returns a durable `late_recorded` response.

### W04-003

- `id`: W04-003
- `severity`: P2
- `file`: `src/mediapipeline/desktop/network/coordinator_lifecycle.py`; supporting paths `src/mediapipeline/desktop/network/registry.py`, `src/mediapipeline/desktop/network/coordinator_state.py`
- `line`: `registry.py:591-622`, `coordinator_lifecycle.py:116-159`, `coordinator_state.py:116-127`, `tests/python/desktop/test_network_workflow.py:617-660`
- `symbol`: `InFlightRegistry.reclaim_stale`, `CoordinatorLifecycleMixin._reaper_loop`, `CoordinatorStateMixin._safe_log_cluster_event`
- `problem`: Reaper reclaim evidence is only projected to cluster log. `reclaim_stale()` removes jobs and marks a short recent-completion quarantine, but it does not persist a reclaimed-job ledger or update durable worker failure/reclaim evidence. `_reaper_loop()` saves the registry after reclaim, yet that saved state contains the absence of the job, not the reason it disappeared. If `_safe_log_cluster_event()` fails, the reclaim reason/source evidence can be lost.
- `impact`: The reaper avoids skipping saves when logging fails, which is good, but operator forensics are weak after a log failure. A later unknown done/release report cannot be correlated to the reclaimed job from registry state because the source/job context was deleted and not replaced with durable reclaim evidence. This increases the chance of ambiguous rerun/review decisions after stale workers.
- `evidence`: `reclaim_stale()` deletes stale jobs from `_jobs`, removes `_claimed_paths`, and stores only a transient recent-completion timestamp (`registry.py:591-622`). `_reaper_loop()` logs `reclaimed_stale` and saves when stale or active (`coordinator_lifecycle.py:116-159`). `_safe_log_cluster_event()` swallows logging failures (`coordinator_state.py:116-127`). The current regression verifies logging failure does not skip save, but does not assert durable reclaim evidence survives (`tests/python/desktop/test_network_workflow.py:617-660`).
- `suggested fix direction`: Persist a bounded reclaim ledger or worker-stats field before deleting stale jobs, including job id, worker id/name, source path, last heartbeat, reclaim time, and timeout. Treat cluster log as a view of that durable evidence, not the only evidence.
- `suggested validation/tests`: Add a stale-reaper test where cluster logging fails and assert a durable reclaim record remains after `registry.save()`/`load()`. Add a late done-after-reclaim test that can link the unknown report to the reclaimed source without mutating active work.

## Test Coverage Gaps

- There is no test that forces `registry.save()` to fail after a successful `complete()` and then asserts the worker retains its pending done report. Existing tests check diagnostics are emitted, but current behavior still returns OK to the worker.
- There is no end-to-end stale-reclaim plus late-success test that verifies publish/queue terminal payload evidence is retained without corrupting a newly active claim.
- There is no durable reaper-evidence test for cluster-log failure; the current test proves save is not skipped, but does not prove the saved state carries reclaim evidence.
- The full assigned test command is currently not green in this dirty worktree for a non-W04 claim fixture issue: `test_network_workflow.py::WorkflowEnhancementTests::test_http_claim_skips_records_outside_worker_accessible_libraries` fails because the test's `_snapshot_encode_config` lambda accepts fewer parameters than the current source call.

Validation run on 2026-06-15:

- `apps\desktop\runtime\Python\python.exe -m pytest tests\python\desktop\test_network_done_release.py tests\python\desktop\test_network_crash_recovery.py tests\python\desktop\test_network_workflow.py tests\python\desktop\test_network_coordinator_http.py tests\python\desktop\test_network_coordinator_source_policy.py tests\python\desktop\test_network_worker_state.py` -> 120 passed, 1 failed; failure was the non-W04 accessible-library claim fixture mismatch above.
- `apps\desktop\runtime\Python\python.exe -m pytest tests\python\desktop\test_network_done_release.py tests\python\desktop\test_network_crash_recovery.py tests\python\desktop\test_network_coordinator_http.py tests\python\desktop\test_network_coordinator_source_policy.py tests\python\desktop\test_network_worker_state.py tests\python\desktop\test_network_workflow.py -k "done or release or reaper or stale or pending or crash or mark_done or owner"` -> 58 passed, 63 deselected.

## Boundary Risks

- Source mutation: no direct source delete/overwrite path was found in the reviewed done/release/reaper code. The risk is indirect: lost or stale terminal evidence can cause rerun/review ambiguity while source files remain retryable.
- Queue boundary: terminal queue removal currently occurs as a side effect of worker-reported success or queue-terminal failure and is not gated on durable coordinator save success. This is the strongest queue-boundary mismatch found.
- Pending publish / publish-drain boundary: done payloads preserve `publish_state`/`publish_mode` as evidence, but unknown/reclaimed pending reports can be discarded without a durable coordinator late-report record. A worker-reported pending-publish or final-publish outcome should not become the only copy of publish evidence.
- Reaper boundary: stale reclaim does not mutate source/output/pending publish directly, but it deletes active ownership and can lose the reason/evidence if cluster logging fails.

## Files With No Findings

- `src/mediapipeline/desktop/network/worker_done.py`: reviewed payload builders; they preserve completion, publish, route, queue-terminal, retry, and classified failure fields. Concerns are in coordinator acceptance and worker replay clearing, not this builder.
- `src/mediapipeline/desktop/network/worker_parts/results.py`: reviewed cluster-log event builders; no separate issue beyond best-effort log durability covered in W04-003.
- `src/mediapipeline/desktop/network/cluster_log.py`: reviewed formatting; terminal log lines sanitize control characters and redact network secret text.
- `src/mediapipeline/desktop/network/coordinator_state.py`: reviewed append/safe logging; no separate issue beyond W04-003's reliance on best-effort logging as the only stale-reclaim evidence.

## Incomplete Coverage

- No real media, live two-machine coordinator/worker cluster, actual queue file, pending-publish manifest, completed output, or runtime state was touched or validated.
- Did not run browser/Tauri/network lifecycle smokes because this was a source/test review-only worker audit and W04 did not change operator surfaces.
- Did not review all claim/auth/lifecycle code paths outside supporting context; W01/W02/W03/W05/W06 cover those scopes.
- Did not inspect PowerShell local-worker compatibility; W13 owns that scope.

## Suggested Follow-Up Prompts

- "Patch W04-001 so `/api/done` returns retryable failure when registry persistence fails, and prove workers retain pending done reports until durable acceptance."
- "Design and implement a coordinator late-terminal-report ledger for unknown/reclaimed done reports without allowing late workers to close active claims."
- "Add durable stale-reclaim evidence to `InFlightRegistry` and tests proving cluster-log failure does not erase the reclaim reason/source/job context."
