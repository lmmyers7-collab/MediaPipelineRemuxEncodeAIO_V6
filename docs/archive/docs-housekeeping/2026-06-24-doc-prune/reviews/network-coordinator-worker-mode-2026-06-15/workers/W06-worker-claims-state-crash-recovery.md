# Worker Review: W06 - Worker Claims, State, Pending Done, And Crash Recovery

## Scope

Reviewed worker claim parsing, synthetic queue-record handoff, worker state persistence, pending done retry, crash recovery, terminal done/release reporting, and the network provider single-file start handoff.

Assigned source scope:

- `src/mediapipeline/desktop/network/worker_claims.py`
- `src/mediapipeline/desktop/network/worker_state.py`
- `src/mediapipeline/desktop/network/worker_done.py`
- `src/mediapipeline/desktop/network/worker_record.py`
- `src/mediapipeline/desktop/network/worker_parts/tasks.py`
- `src/mediapipeline/desktop/network/worker_parts/state_reports.py`
- `src/mediapipeline/desktop/network/worker_parts/results.py`
- `_NetworkRuntimeApp` and `_start_network_claimed_job` in `src/mediapipeline/desktop/application/network_lifecycle_provider.py`

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/FILE_LIFECYCLE_MAP.md`
- `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
- Generated summaries for all assigned source and assigned test files.
- Full assigned source files listed in Scope.
- Assigned tests/evidence: `tests/python/desktop/test_network_worker_state.py`, `tests/python/desktop/test_network_crash_recovery.py`, `tests/python/desktop/test_network_done_release.py`, targeted sections of `tests/python/desktop/test_network_worker_runtime.py`, `tests/python/desktop/test_network_worker_source_policy.py`, and `tests/python/desktop/test_network_library_relative_claim.py`.
- Contextual reads after summaries: relevant sections of `worker.py`, `worker_loops.py`, `protocol.py`, `http_json.py`, `worker_http.py`, `library_roots.py`, `core/kernel/models.py`, and `tests/python/desktop/test_application_facade_process_launch.py`.

## Coverage Ledger

| File / symbol | Coverage | Notes |
|---|---|---|
| `worker_claims.py` | Reviewed | Finding W06-003 on one-shot release failure for wire-only malformed/unstartable claims. Done/release paths otherwise preserve pending retry when a `ClaimedJob` exists. |
| `worker_state.py` | Reviewed | Finding W06-002 on active-only state being treated as claim-safe after unresolved crash recovery. Atomic write and strict JSON behavior reviewed. |
| `worker_done.py` | Reviewed | Reviewed: no findings. Completion/release/crash request builders preserve done fields; inbound protocol validation is in `protocol.py`. |
| `worker_record.py` | Reviewed | Finding W06-001 on empty claim source becoming `Path('.')`. |
| `worker_parts/tasks.py` | Reviewed | Finding W06-001 on missing identity validation before `ClaimedJob` construction. |
| `worker_parts/state_reports.py` | Reviewed | Reviewed: no findings in wrapper behavior; save failures are surfaced and return/raise as intended. |
| `worker_parts/results.py` | Reviewed | Reviewed: no findings. Cluster-log messages are bounded to short detail slices. |
| `_NetworkRuntimeApp` | Reviewed | Reviewed: no findings. Watch thread reports process result through dispatcher and clears provider-local process state after watch cleanup. |
| `_start_network_claimed_job` | Reviewed | Finding W06-001 reaches this handoff because only empty string is rejected before `single_file=source_path`. |
| Assigned tests | Reviewed | Findings below include coverage gaps where tests assert or omit unsafe cases. |

## Findings

| id | severity | file | line | symbol | summary |
|---|---|---|---|---|---|
| W06-001 | P1 | `src/mediapipeline/desktop/network/worker_parts/tasks.py`; `worker_record.py`; `network_lifecycle_provider.py` | `tasks.py:14`, `tasks.py:51`, `worker_record.py:14`, `network_lifecycle_provider.py:556` | `parse_claim_response_payload`, `build_claimed_job`, `make_queue_record`, `_start_network_claimed_job` | An `ok` claim with missing `job_id` or `source_path` is accepted and can be handed to the backend as `single_file='.'`. |
| W06-002 | P1 | `src/mediapipeline/desktop/network/worker_state.py`; `worker.py`; `worker_loops.py` | `worker_state.py:152`, `worker_state.py:198`, `worker.py:169`, `worker_loops.py:108` | `_crash_recover`, `_flush_pending_done_report`, `WorkerDispatcher.__init__`, `_poll_loop` | If crash recovery cannot report an active job, the worker keeps active-only state but still starts polling and can claim new work. |
| W06-003 | P2 | `src/mediapipeline/desktop/network/worker_claims.py`; `worker_loops.py` | `worker_claims.py:34`, `worker_claims.py:51`, `worker_loops.py:201`, `worker_loops.py:252` | `_release_claim_identity`, `_release_unstartable_claim`, `_release_malformed_claim_response` | Unstartable/malformed claim release POST failures are not persisted for retry, so the coordinator must rely on stale in-flight timeout. |

## Detailed Findings

### W06-001

- `id`: W06-001
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/worker_parts/tasks.py`; `src/mediapipeline/desktop/network/worker_record.py`; `src/mediapipeline/desktop/application/network_lifecycle_provider.py`
- `line`: `tasks.py:14`, `tasks.py:51`, `worker_record.py:14`, `worker_record.py:15`, `network_lifecycle_provider.py:556`, `network_lifecycle_provider.py:592`
- `symbol`: `parse_claim_response_payload`, `build_claimed_job`, `make_queue_record`, `_start_network_claimed_job`
- `problem`: The worker accepts `ClaimResponse.from_dict({"status": "ok"})` because `protocol.py:152-153` defaults missing `job_id` and `source_path` to empty strings. `build_claimed_job()` then calls the record builder without enforcing non-empty claim identity. `make_queue_record()` turns the empty source into `Path("")`, which becomes `Path('.')`. `_start_network_claimed_job()` rejects only an empty string, so `str(Path('.')).strip()` passes and is sent to the backend as `single_file='.'`.
- `impact`: A malformed coordinator response or coordinator bug can make a worker attempt a backend single-file launch against the process current directory instead of a coordinator-selected media file. That violates claim handoff source-path safety and can create wrong-file processing, confusing done/release reports, or launch-side failures that no longer identify the originally claimed row.
- `evidence`: Source path: `parse_claim_response_payload()` delegates directly to `ClaimResponse.from_dict()` at `tasks.py:14`; `build_claimed_job()` accepts the result at `tasks.py:51`; `make_queue_record()` sets `source_path=src` and `source_root=src.parent` at `worker_record.py:14-15`; `_start_network_claimed_job()` only checks `if not source_path` at `network_lifecycle_provider.py:557` and passes `single_file=source_path` at `network_lifecycle_provider.py:592`. Temp-only in-memory probe with bundled Python confirmed `ClaimResponse.from_dict({"status":"ok"})` builds a job whose record source path and source root both stringify as `"."`.
- `suggested fix direction`: Treat `status == "ok"` claims as malformed unless `job_id` and `source_path` are non-empty after trimming and `source_path` is a file-like absolute or UNC path acceptable to the worker source policy. Enforce this before `make_queue_record()`. If a trustworthy `job_id` exists but source path is invalid, POST a release and persist it for retry per W06-003; otherwise reject without starting backend work.
- `suggested validation/tests`: Add worker poll-loop tests for `{"status":"ok"}` missing `job_id`, missing `source_path`, and blank `source_path`. Assert no `_on_job_claimed`, no backend `_worker_start_single_file`, no `single_file='.'`, and a bounded release/log path when a job id is present.

### W06-002

- `id`: W06-002
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/worker_state.py`; `src/mediapipeline/desktop/network/worker.py`; `src/mediapipeline/desktop/network/worker_loops.py`
- `line`: `worker_state.py:152`, `worker_state.py:153`, `worker_state.py:196`, `worker_state.py:198`, `worker.py:169`, `worker.py:172`, `worker_loops.py:108`, `worker_loops.py:116`
- `symbol`: `_crash_recover`, `_flush_pending_done_report`, `WorkerDispatcher.__init__`, `_poll_loop`
- `problem`: On startup, `_crash_recover()` attempts to report an active-only `worker_state.json` as failed. If that POST fails, it logs and returns, leaving the state file unresolved. `WorkerDispatcher.__init__` then starts the poll thread anyway. The poll loop calls `_flush_pending_done_report()`, but that helper returns `True` for any readable state without a valid `pending_done_report`, so the worker can call `/api/claim` and overwrite the single-slot state before the previous interrupted job is reported.
- `impact`: A worker restart while the coordinator is temporarily offline can lose the interrupted job's crash/failure evidence and claim new work against the same single-slot `worker_state.json`. This is a realistic distributed-work correctness failure: the coordinator may keep the old job in flight until timeout while the worker starts another job, and subsequent state saves can erase the only local recovery evidence.
- `evidence`: `_crash_recover()` logs `Crash recovery done-report failed` and returns at `worker_state.py:152-153`. `WorkerDispatcher.__init__` calls `_crash_recover()` at `worker.py:169` and starts `_poll_thread` at `worker.py:172` regardless of unresolved state. `_flush_pending_done_report()` reads `pending = state.get("pending_done_report")` at `worker_state.py:196` and returns `True` when no valid pending report exists at `worker_state.py:198`. `_poll_loop()` proceeds to `/api/claim` after `_flush_pending_done_report()` returns true at `worker_loops.py:108` and `worker_loops.py:116`. Tests confirm the pieces but not the unsafe sequence: `test_crash_recover_keeps_state_when_done_post_fails` leaves the active state on disk, and `test_flush_keeps_active_claim_record_without_pending_report` asserts that active-only state is claim-safe.
- `suggested fix direction`: Distinguish active-only unresolved state from no state. After crash-recovery POST failure, either do not start polling or make `_flush_pending_done_report()` return `False` while a readable active state remains without an accepted crash recovery report. Only clear or downgrade active-only state after an accepted `/api/done`, a deliberate unknown-job discard policy, or an operator-visible repair action.
- `suggested validation/tests`: Add a startup/poll-loop test where `worker_state.json` has `job_id` and `source_path`, crash recovery POST fails, and `_http_get("/api/claim")` must not be called. Add a companion test proving that once the crash recovery report is accepted and cleanup succeeds, polling resumes.

### W06-003

- `id`: W06-003
- `severity`: P2
- `file`: `src/mediapipeline/desktop/network/worker_claims.py`; `src/mediapipeline/desktop/network/worker_loops.py`
- `line`: `worker_claims.py:34`, `worker_claims.py:40`, `worker_claims.py:51`, `worker_claims.py:73`, `worker_loops.py:201`, `worker_loops.py:252`
- `symbol`: `_release_claim_identity`, `_release_unstartable_claim`, `_release_malformed_claim_response`
- `problem`: Wire-only unstartable claims are released with a single POST. If that POST fails, `_release_claim_identity()` logs and updates status but does not save a pending release report. The normal `_do_release()` path has retry persistence, but path-map failures, malformed claim responses, and record-build failures use the wire-only helper before a `ClaimedJob` exists.
- `impact`: The worker can leave a coordinator claim in flight until the coordinator's stale timeout/reaper path notices it. That violates the prompt's no stale-timeout reliance requirement for unstartable and malformed claims, and it can block the source from being reassigned even though the worker already knows it cannot start the job.
- `evidence`: `_release_claim_identity()` posts `build_release_done_request()` at `worker_claims.py:34-40`; the exception path only logs and calls `_notify_status()` at `worker_claims.py:45-51`. `_release_malformed_claim_response()` routes to the same helper at `worker_claims.py:73`. Poll-loop path-map and record-build failures call `_release_unstartable_claim()` at `worker_loops.py:201` and `worker_loops.py:252`. `tests/python/desktop/test_network_done_release.py:453-455` asserts only the operator status for a failed unstartable release and does not expect persisted retry state.
- `suggested fix direction`: Add a small pending-release persistence path for trustworthy wire identities, using the existing `worker_state.json` single-slot format with `pending_done_report` and enough `source_path` evidence to retry before future claims. If the job identity is not trustworthy, log a bounded local/cluster event and avoid starting work.
- `suggested validation/tests`: Add tests for path-map failure, malformed claim response, and record-build failure where `/api/done` release returns a transient error. Assert `worker_state.json` contains a pending release report, the next poll flushes it before `/api/claim`, and diagnostics remain bounded.

## Test Coverage Gaps

- No assigned test covers an `ok` claim missing `job_id` or `source_path`; current malformed-claim tests cover bad `encode_config` and parse failures but not missing identity.
- No test covers the full sequence of crash recovery POST failure followed by the poll loop. Existing tests independently assert state remains after crash recovery failure and that active-only state without `pending_done_report` lets `_flush_pending_done_report()` return true.
- No test proves failed wire-only release reports for unstartable/malformed claims are persisted and retried before the next claim.
- Provider coverage proves a claimed job starts backend `single_file` and reports done for a simple path, but assigned W06 tests do not assert provider handoff for a library-relative resolved worker path or for a malformed synthetic record that resolves to `"."`.

## Boundary Risks

- Source path safety: W06-001 can pass `"."` as `single_file`, which breaks the guarantee that worker mode only runs coordinator-assigned media paths.
- Claim/state correctness: W06-002 and W06-003 can leave coordinator in-flight state unresolved while the worker proceeds or waits for stale timeout.
- Source mutation: no direct source delete/overwrite path was found in W06 source, but wrong `single_file` handoff could route an unintended filesystem target into the normal backend launch path.
- Pending publish and final publish: no W06 source path directly bypasses pending-publish or final publish policy. Done payloads can carry publish evidence, but final publish remains backend pipeline behavior.

## Files With No Findings

| File / symbol | Result |
|---|---|
| `src/mediapipeline/desktop/network/worker_done.py` | Reviewed: no findings. |
| `src/mediapipeline/desktop/network/worker_parts/state_reports.py` | Reviewed: no findings. |
| `src/mediapipeline/desktop/network/worker_parts/results.py` | Reviewed: no findings. |
| `_NetworkRuntimeApp._watch_claimed_process` | Reviewed: no findings in assigned scope. |
| `_NetworkRuntimeApp.abort_current_worker_job` | Reviewed: no findings in assigned scope. |
| `tests/python/desktop/test_network_worker_source_policy.py` | Reviewed: no findings; it is mostly source-string guard coverage. |
| `tests/python/desktop/test_network_library_relative_claim.py` | Reviewed: no findings in covered cases; missing malformed identity coverage is listed above. |

## Incomplete Coverage

- Did not run real media, start a live worker/coordinator, mutate settings, touch queue/runtime state, or probe a live LAN.
- Did not run the full assigned pytest/unittest set; this review used source/test inspection plus a temp-only bundled-Python in-memory probe for malformed claim construction.
- Read only relevant contextual sections of unassigned files (`worker.py`, `worker_loops.py`, `protocol.py`, `http_json.py`, `library_roots.py`, `processing_policy.py`, and provider-related tests) after checking summaries where available.
- `src/mediapipeline/desktop/network/processing_policy.py` had no generated summary and was untracked in the current worktree; only the narrow imported helper context was inspected.

## Suggested Follow-Up Prompts

- "Fix W06-001 by rejecting or safely releasing `ok` claims with missing `job_id` or invalid `source_path`, and add malformed-identity worker poll-loop tests."
- "Fix W06-002 by making unresolved active worker state block polling until crash recovery is accepted or explicitly discarded, with tests for coordinator-offline restart."
- "Fix W06-003 by persisting wire-only release failures for retry before future claims, with path-map, malformed-response, and record-build failure tests."
