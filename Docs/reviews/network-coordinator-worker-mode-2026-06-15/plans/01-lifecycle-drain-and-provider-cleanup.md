# Plan 01 - Lifecycle Drain And Provider Cleanup

Date: 2026-06-15

## Goal

Fix remaining lifecycle reliability issues without changing media policy,
queue processing semantics, source/scratch/output movement, publish/drain, or
FFmpeg behavior.

## Findings Covered

- REM-NCW-01: coordinator lifecycle active-work evidence ignores remote
  in-flight claims.
- REM-NCW-02: ordinary coordinator stop can close HTTP routes while remote
  workers still need heartbeat and done/reporting routes.
- REM-NCW-03: worker provider can leave a runtime entry if polling startup
  fails.
- REM-NCW-04: coordinator provider can leave a partial dispatcher if queue
  refresh or local-worker loop startup fails after dispatcher construction.

## Primary Files

- `src/mediapipeline/core/network/lifecycle_facade.py`
- `src/mediapipeline/desktop/application/network_lifecycle_provider.py`
- `src/mediapipeline/desktop/network/coordinator.py`
- `src/mediapipeline/desktop/network/coordinator_lifecycle.py`
- `src/mediapipeline/desktop/network/registry.py`
- `tests/python/desktop/test_network_lifecycle_fixes.py`
- `tests/python/desktop/test_network_workflow.py`

## Implementation Steps

1. Add coordinator active-claim evidence.
   - Add a coordinator dispatcher method such as
     `active_network_jobs()` or `active_claims_snapshot()`.
   - Return bounded, token-free data from the registry snapshot:
     `job_id`, `worker_id`, `worker_name`, `source_path`, source basename,
     `last_heartbeat`, and heartbeat age when available.
   - Keep `WorkerDispatcher.get_active_job()` unchanged for worker-local
     evidence.

2. Teach lifecycle dry-run evidence about remote claims.
   - In `_network_lifecycle_active_work_evidence`, read the new coordinator
     active-claim method when role is `coordinator`.
   - Count remote claims separately from local coordinator-worker process jobs:
     `remote_active_claim_count`, `local_active_job_count`,
     `active_job_count`.
   - For coordinator stop dry-runs with remote active claims, append an
     `active_network_work` precondition with status `review`.
   - For coordinator start dry-runs with preserved active work, keep status
     `blocked`.

3. Replace ordinary coordinator stop teardown with cooperative drain.
   - Add a dispatcher method such as `begin_drain()`:
     - set `_accepting_claims = False`;
     - keep HTTP routes required for `/api/heartbeat`, `/api/done`,
       `/api/log`, `/api/workers`, and `/api/health`;
     - make `/api/claim` return no claim with a retry/backoff hint;
     - keep registry persistence active.
   - Keep full `shutdown()` for no-active-work teardown and final drain
     completion.

4. Keep runtime entry while draining.
   - In `stop_network_coordinator`, if local or remote active work exists:
     - set `entry["stop_requested"] = True`;
     - call `dispatcher.begin_drain()` instead of `dispatcher.shutdown()`;
     - do not pop `runtime["coordinator"]`;
     - start a bounded drain monitor thread or register a callback to perform
       final `shutdown()` and runtime pop when `active_count == 0`.
   - If no active work exists, keep current full shutdown path.

5. Add provider startup cleanup.
   - Wrap coordinator post-construction startup:
     `CoordinatorDispatcher(app)`, queue-refresh loop, optional local-worker
     loop, and runtime insertion.
   - If anything after dispatcher construction fails, signal any events that
     were created, call `dispatcher.shutdown()`, join started threads, avoid
     runtime insertion, and re-raise.
   - Wrap worker `start_polling()` after runtime insertion. If it fails, call
     `dispatcher.shutdown(release_active_job=False)` when available, pop
     `runtime["worker"]`, and re-raise.

## Regression Tests

Add or update:

- `test_coordinator_stop_dry_run_reports_remote_active_claims`
- `test_coordinator_start_dry_run_blocks_with_preserved_remote_claims`
- `test_confirmed_coordinator_stop_with_remote_claim_enters_drain_without_http_shutdown`
- `test_coordinator_drain_finalizes_shutdown_after_registry_idle`
- `test_worker_start_polling_failure_cleans_runtime_entry`
- `test_coordinator_start_loop_failure_shuts_down_partial_dispatcher`

Use fakes for dispatcher, registry, HTTP server, and threads. Do not start real
media processing.

## Validation Commands

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_network_lifecycle_fixes tests.python.desktop.test_network_workflow
apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_application_facade_network
```

Run the common acceptance validation in
`plans/04-acceptance-validation-runbook.md` after all plans are complete.

## Rollback Plan

Revert changes in lifecycle facade, lifecycle provider, coordinator dispatcher,
coordinator lifecycle helpers, and the focused tests. Confirm existing
coordinator start/stop, worker start/stop, and registry tests return to their
previous passing state.

## Acceptance Criteria

- Dry-run evidence shows remote active claims.
- Ordinary stop does not close done/heartbeat routes while active remote claims
  remain.
- Runtime entries are not left behind after startup failures.
- No test or implementation path launches normal local processing from Network
  lifecycle.
