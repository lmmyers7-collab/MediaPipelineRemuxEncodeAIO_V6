# Worker Review: W05 - Worker Runtime Loop, HTTP Calls, Heartbeats, And Shutdown

## Scope

Review-only audit of worker runtime loop, HTTP request signing, heartbeat behavior, hot-apply, and worker lifecycle start/stop paths for network coordinator/worker mode.

Assigned source scope:

- `src/mediapipeline/desktop/network/worker.py`
- `src/mediapipeline/desktop/network/worker_loops.py`
- `src/mediapipeline/desktop/network/worker_http.py`
- `src/mediapipeline/desktop/network/poll_policy.py`
- `src/mediapipeline/desktop/network/threading_helpers.py`
- `src/mediapipeline/desktop/network/worker_parts/reporting.py`
- `src/mediapipeline/desktop/application/network_lifecycle_provider.py`

Supporting context read for claim handoff/state evidence:

- `src/mediapipeline/desktop/network/worker_claims.py`
- `src/mediapipeline/desktop/network/worker_state.py`
- `src/mediapipeline/desktop/network/worker_parts/tasks.py`
- `src/mediapipeline/desktop/network/http_json.py`
- `src/mediapipeline/desktop/network/auth.py`

Assigned tests/evidence:

- `tests/python/desktop/test_network_worker_runtime.py`
- `tests/python/desktop/test_network_worker_source_policy.py`
- `tests/python/desktop/test_network_drift_descriptor.py`
- `tests/python/desktop/test_network_lifecycle_fixes.py`
- `tests/python/desktop/test_network_security.py`
- `tests/python/desktop/test_application_facade_network.py`

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
- Generated summaries for all assigned source and test files.
- Generated summaries for supporting context files opened during the review.
- Shared output contract and W05 prompt in `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`.

No source, generated summaries, runtime state, settings, queue state, media, pending publish, completed output, or aggregate review files were edited. No worker code was pointed at a live coordinator.

## Coverage Ledger

| Area | Files / symbols reviewed | Coverage | Notes |
| --- | --- | --- | --- |
| Worker construction and hot-apply | `WorkerDispatcher.__init__`, `update_auth_token`, `update_coordinator_url`, `update_source_path_map`, `runtime_descriptor` | Complete for W05 symbols | URL validation is applied before swapping; token update logs no token; descriptor uses fingerprints. |
| Worker HTTP | `_headers`, `_runtime_http_context`, `_sign_request`, `_http_get`, `_http_post`, `http_get_json`, `http_post_json`, `sign_request` | Complete for W05 symbols | Requests are capped, signed with HMAC headers, and URL errors are redacted by helper paths. |
| Poll loop and claim handoff | `_poll_loop`, `_resolve_wait_seconds`, `_wait_interruptible`, `claim_failure_status_message`, malformed/path-map/build-record release paths | Complete for assigned symbols; supporting paths targeted | Finding W05-002 covers pre-start release failure handling. |
| Heartbeats | `_heartbeat_loop`, `_stop_heartbeat`, progress snapshot handling, repeated heartbeat warnings, reclaim abort scheduling | Complete for assigned symbols | Heartbeat POSTs are signed through `_http_post`; repeated warning text is de-duplicated. |
| Worker shutdown | `shutdown`, `stop_network_worker`, app active-process wait/release decision | Complete for assigned symbols | Stop avoids clean release while process is still running; watcher startup failure is the gap in W05-001. |
| Lifecycle worker launch | `start_network_worker`, `_NetworkRuntimeApp._worker_start_single_file`, `_start_network_claimed_job`, `_watch_claimed_process` | Targeted | Source launches `start_pipeline(..., mode="once", single_file=source_path)` rather than normal queue scan. Finding W05-001 covers watcher-thread failure after process launch. |
| Assigned tests | Six assigned test files | Complete targeted read and execution | `99 passed in 1.26s` with bundled Python. |

Validation run:

```powershell
apps\desktop\runtime\Python\python.exe -m pytest tests\python\desktop\test_network_worker_runtime.py tests\python\desktop\test_network_worker_source_policy.py tests\python\desktop\test_network_drift_descriptor.py tests\python\desktop\test_network_lifecycle_fixes.py tests\python\desktop\test_network_security.py tests\python\desktop\test_application_facade_network.py
```

Result: `99 passed in 1.26s`.

## Findings

| id | severity | file | line / symbol | summary |
| --- | --- | --- | --- | --- |
| W05-001 | P1 | `src/mediapipeline/desktop/application/network_lifecycle_provider.py`; `src/mediapipeline/desktop/network/worker_claims.py` | `network_lifecycle_provider.py:126-170`, `worker_claims.py:142-156`, `worker_claims.py:158-176` | Watcher-thread startup failure after launching the pipeline is treated as encode-start failure and clean-releases the coordinator claim while the launched process can keep running. |
| W05-002 | P2 | `src/mediapipeline/desktop/network/worker_claims.py`; `src/mediapipeline/desktop/network/worker_loops.py` | `worker_claims.py:34-51`, `worker_claims.py:53-74`, `worker_loops.py:126-168`, `worker_loops.py:189-203`, `worker_loops.py:241-253` | Pre-start malformed/path-map/record-build release POST failures are swallowed, so the poll loop can resume without accepted release evidence or pending retry state. |

## Detailed Findings

### W05-001 - Watcher-thread startup failure can release a claim while the launched process keeps running

- id: `W05-001`
- severity: `P1`
- file: `src/mediapipeline/desktop/application/network_lifecycle_provider.py`; `src/mediapipeline/desktop/network/worker_claims.py`
- line or narrow symbol reference: `network_lifecycle_provider.py:126-170`, `network_lifecycle_provider.py:585-593`, `worker_claims.py:142-156`, `worker_claims.py:158-176`
- symbol: `_NetworkRuntimeApp._watch_claimed_process`, `_start_network_claimed_job`, `WorkerClaimMixin._start_claimed_encode`, `WorkerClaimMixin._do_release`
- problem: `_start_network_claimed_job` launches `start_pipeline(..., mode="once", single_file=source_path)` and returns a process object. `_watch_claimed_process` then stores that process as active and starts the daemon watcher thread without a startup failure guard. If `thread.start()` raises after the process has been launched, the exception propagates back through `app._worker_start_single_file(job)` into `WorkerClaimMixin._start_claimed_encode`, which treats it as an encode-start failure and calls `_do_release(job)`. `_do_release` sends a clean release report and clears the dispatcher's active job, but it does not abort the already-launched process or clear `_NetworkRuntimeApp._active_proc`.
- impact: The coordinator can accept the release and reassign/requeue the same source while the first worker process continues running without a watcher to report done. That creates duplicate active processing and loses terminal success/failure evidence for the launched process. It also crosses the queue/publish boundary because a worker can continue toward final publish after giving up the coordinator claim.
- evidence: `network_lifecycle_provider.py:126-130` sets `_active_job` and `_active_proc`; `network_lifecycle_provider.py:165-170` starts the watcher thread without `try/except`; `worker_claims.py:142-156` catches the propagated exception as encode-start failure; `worker_claims.py:158-176` clean-releases the job on `/api/done`.
- suggested fix direction: Treat watcher startup failure as a post-launch failure, not a clean unstarted release. Wrap watcher thread construction/start in a failure path that aborts or terminates the launched process, waits a bounded interval, clears `_NetworkRuntimeApp` active state, and reports a failed done outcome or preserves a pending failure report. Do not send `released=True` while the process may still be running.
- suggested validation/tests: Add a test that patches `network_lifecycle_provider.threading.Thread.start` to raise after `start_pipeline` returns a fake running process. Assert the process is terminated or killed, `_active_job/_active_proc` are cleared, and the dispatcher does not clean-release the claim while the process can still run. Include a variant where done reporting fails and pending evidence is retained.

### W05-002 - Failed release of unstartable claims is treated as if release succeeded

- id: `W05-002`
- severity: `P2`
- file: `src/mediapipeline/desktop/network/worker_claims.py`; `src/mediapipeline/desktop/network/worker_loops.py`
- line or narrow symbol reference: `worker_claims.py:34-51`, `worker_claims.py:53-74`, `worker_loops.py:126-168`, `worker_loops.py:189-203`, `worker_loops.py:241-253`
- symbol: `_release_claim_identity`, `_release_malformed_claim_response`, `_poll_loop`
- problem: Before a `ClaimedJob` exists, malformed claim bodies, source path-map failures, and invalid queue-record construction all release by raw `job_id` through `_release_claim_identity`. That helper catches `_http_post("/api/done", released=True)` failures and only logs/statuses them. It returns no success indicator, and `_release_malformed_claim_response` still returns `True` after calling it. The poll loop then sleeps once and continues as though the coordinator accepted the release.
- impact: If the release POST fails, the coordinator still has an in-flight claim with no worker heartbeat, no active local `ClaimedJob`, and no pending retry state. The stale claim is bounded by coordinator reaper behavior, but the worker can keep polling and claim additional work while the earlier claim remains active. Path-map and malformed-claim evidence can be lost except for local logs.
- evidence: `worker_claims.py:37-51` swallows release POST exceptions; `worker_claims.py:53-74` always reports the malformed claimed response as handled when identity exists; `worker_loops.py:126-168` continues after malformed release handling; `worker_loops.py:189-203` and `worker_loops.py:241-253` release unstartable claims and then continue without checking whether the release landed. Assigned tests cover successful malformed/path-map release and cluster-log failure, but not `/api/done` release failure in these pre-start paths.
- suggested fix direction: Make raw-identity release return an accepted/persisted/failed result. On release POST failure, hold polling until the claim is released, or persist a minimal pending release report keyed by `job_id` and `source_path` so startup/poll recovery retries it before new claims. Avoid returning `True` from malformed-claim handling unless the release was accepted or durable retry evidence was saved.
- suggested validation/tests: Add tests where `_http_post` raises during `_release_malformed_claim_response`, path-map failure, and record-build failure. Assert the poll loop does not proceed to normal claiming as if release succeeded, and assert either pending release state is saved or operator-visible held-poll status is emitted.

## Test Coverage Gaps

- No assigned test covers watcher-thread startup failure after `start_pipeline` has returned a process. Existing tests cover poll thread startup failure, heartbeat thread startup failure, cluster-log thread startup failure, and app callback scheduling failure, but not the process watcher thread in `network_lifecycle_provider.py`.
- No assigned test covers `/api/done` failure when releasing malformed/path-map/record-build pre-start claims by raw identity.
- No assigned test directly asserts that `start_network_worker` reaches `start_pipeline` with `single_file=source_path` and never launches a normal queue scan. Source inspection shows the current worker path uses `mode="once"` and `single_file=source_path`.

## Boundary Risks

- W05-001 is the main queue/publish boundary risk: a clean release can be sent while an already-launched local pipeline process remains alive and unobserved.
- W05-002 can leave coordinator in-flight state stale until reaper reclaim after malformed/path-map failures, with only local logs if release reporting fails.
- No source mutation, pending-publish drain bypass, settings write, queue-state edit, runtime-state edit, or media mutation was performed in this review.
- The current worktree already contained unrelated source and generated-summary changes before this W05 pass, including `src/mediapipeline/desktop/application/network_lifecycle_provider.py`. This review used the current working-tree contents for line evidence.

## Files With No Findings

- `src/mediapipeline/desktop/network/worker.py`: no findings in constructor, hot-apply setters, path-map update wakeups, or token-safe runtime descriptor.
- `src/mediapipeline/desktop/network/worker_http.py`: no findings in W05-scoped HTTP helpers; requests snapshot token/URL and use HMAC signing through `http_json`.
- `src/mediapipeline/desktop/network/poll_policy.py`: no findings; poll interval and retry hints are bounded for W05 concerns.
- `src/mediapipeline/desktop/network/threading_helpers.py`: no findings in the helper itself; W05-001 is a caller coverage gap where the helper pattern is not used.
- `src/mediapipeline/desktop/network/worker_parts/reporting.py`: no findings; status/app-callback failures are contained and reclaimed-job abort scheduling logs failures.
- `tests/python/desktop/test_network_worker_source_policy.py`: no test defects beyond coverage gaps listed above.
- `tests/python/desktop/test_network_drift_descriptor.py`: no findings; token fingerprints are asserted instead of token disclosure.
- `tests/python/desktop/test_network_lifecycle_fixes.py`: no findings; hot-apply and stop-with-running-process behavior are covered.
- `tests/python/desktop/test_network_security.py`: no W05 findings; signing/redaction/URL validation evidence is relevant and passing.
- `tests/python/desktop/test_application_facade_network.py`: no W05 findings; read DTO evidence only.

## Incomplete Coverage

- No live coordinator, real network coordinator, runtime queue, settings file, media, pending publish, or publish/drain operation was exercised.
- Coordinator-side claim selection, registry persistence, and reaper correctness were not re-reviewed beyond W05 call-site implications; those are owned by W03/W04.
- Full source review outside assigned symbols was not attempted. Supporting files were read only where needed to validate worker claim handoff, state, HTTP signing, and malformed-claim behavior.

## Suggested Follow-Up Prompts

- Patch W05-001: harden `_NetworkRuntimeApp._watch_claimed_process` startup failure after process launch so the worker never clean-releases a coordinator claim while a launched process can continue running; add regression tests.
- Patch W05-002: make pre-start unstartable-claim release failures durable or claim-blocking before the worker resumes polling; add malformed/path-map/record-build release-failure tests.
- Add a lifecycle regression asserting network worker launch uses coordinator-assigned `single_file` work only and does not scan the local queue as normal Launch.
