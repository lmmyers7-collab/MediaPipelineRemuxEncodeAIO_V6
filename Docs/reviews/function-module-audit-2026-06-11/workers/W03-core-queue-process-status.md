# Worker Review: W03-core-queue-process-status

## Scope
- Assigned domain: core-queue-process-status
- Assigned files: 91 files listed below
- Explicit exclusions: none yet; worker must fill this if any assigned file is not reviewed.

## Assigned File List

- `ops/pipeline/engine/process/ffmpeg_progress.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/process/ffmpeg_progress/events.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/process/ffmpeg_progress/parsing.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/process/ffmpeg_progress/tool_context.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/process/file_processor.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/process/pipeline_plan_executor.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/process/pipeline_plan_executor/validation.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/process/pipeline_processing.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/process/pipeline_processing/preflight.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/process/worker_result.ps1` (process, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/engine_plan.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/file_overrides.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/local_worker_slots.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/phase_executor.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/phase_plan.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/pipeline_engine.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/priority_manifest.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/queue_entries.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/queue_plan.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/snapshot_rows.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/snapshot_store.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/strategy_sorting.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/worker_claim_store.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/worker_mutex.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/worker_process.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/queue/worker_progress.ps1` (queue, medium, code-symbol-review, summary=yes)
- `ops/pipeline/engine/status/progress_state.ps1` (status, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/orchestration/__init__.py` (orchestration, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/orchestration/planner.py` (orchestration, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/orchestration/runner.py` (orchestration, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/orchestration/settings_patch_facade.py` (orchestration, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/__init__.py` (process, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/active_job_runner.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/active_jobs.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/audit_facade.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/audit_policy.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/constants.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/control_facade.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/control_flags.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/control_policy.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/control_runner.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/file_io.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/guard_facade.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/guard_policy.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/kill.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/launch_cleanup.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/launch_env.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/launch_plans.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/launch_runner.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/lifecycle.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/logs.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/path_evidence.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/pipeline_facade.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/pipeline_policy.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/preflight_facade.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/readiness.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/rerun_facade.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/rerun_policy.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/runtime_artifacts.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/runtime_runner.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/schedule_facade.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/schedule_policy.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/spawn.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/processes/spawn_runner.py` (process, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/__init__.py` (queue, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/contracts.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/dry_run.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/dry_run_runner.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/facade.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/file_io.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/file_overrides.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/__init__.py` (queue, low, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/file_override_rows.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/metrics.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/open_policy.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/operator_guidance.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/preview.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/route_evidence.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/row_identity.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/rows.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/rules.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/runtime_outcomes.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/policy_parts/track_metadata.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/preview_builder.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/priority_manifest.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/priority_markers.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/service.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/snapshot.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/source_inventory.py` (queue, medium, code-symbol-review, summary=yes)
- `src/mediapipeline/core/queue/strategy.py` (queue, medium, code-symbol-review, summary=yes)

## Coverage Ledger

| File | Symbols reviewed | Coverage | Notes |
|---|---:|---|---|
| `ops/pipeline/engine/process/ffmpeg_progress.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; ffmpeg progress symbol bodies not fully reviewed. |
| `ops/pipeline/engine/process/ffmpeg_progress/events.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; event parsing body not fully reviewed. |
| `ops/pipeline/engine/process/ffmpeg_progress/parsing.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; parsing symbol bodies not fully reviewed. |
| `ops/pipeline/engine/process/ffmpeg_progress/tool_context.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; tool context body not fully reviewed. |
| `ops/pipeline/engine/process/file_processor.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; file processing body not fully reviewed. |
| `ops/pipeline/engine/process/pipeline_plan_executor.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; 29 executor functions not fully reviewed. |
| `ops/pipeline/engine/process/pipeline_plan_executor/validation.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; 12 validation functions not fully reviewed. |
| `ops/pipeline/engine/process/pipeline_processing.ps1` | 4 | reviewed | Reviewed queue/process lifecycle flow; Reviewed: no findings. |
| `ops/pipeline/engine/process/pipeline_processing/preflight.ps1` | 12 | reviewed | Reviewed preflight/source routing flow; Reviewed: no findings. |
| `ops/pipeline/engine/process/worker_result.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; worker result helpers not fully reviewed. |
| `ops/pipeline/engine/queue/engine_plan.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; engine plan functions not fully reviewed. |
| `ops/pipeline/engine/queue/file_overrides.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; override persistence functions not fully reviewed. |
| `ops/pipeline/engine/queue/local_worker_slots.ps1` | 1 | reviewed | Reviewed local-worker slot lifecycle and duplicate-claim handling; finding F-W03-001. |
| `ops/pipeline/engine/queue/phase_executor.ps1` | 2 | reviewed | Reviewed phase execution/stop handling; Reviewed: no findings. |
| `ops/pipeline/engine/queue/phase_plan.ps1` | 3 | reviewed | Reviewed phase plan and hold/priority split; Reviewed: no findings. |
| `ops/pipeline/engine/queue/pipeline_engine.ps1` | 3 | reviewed | Reviewed queue round orchestration and local-worker dispatch; Reviewed: no findings. |
| `ops/pipeline/engine/queue/priority_manifest.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; priority manifest functions not fully reviewed. |
| `ops/pipeline/engine/queue/queue_entries.ps1` | 8 | reviewed | Reviewed queue entry construction and sorting interaction; Reviewed: no findings. |
| `ops/pipeline/engine/queue/queue_plan.ps1` | 0 | reviewed | Reviewed include/dot-source surface; Reviewed: no findings. |
| `ops/pipeline/engine/queue/snapshot_rows.ps1` | 3 | reviewed | Reviewed snapshot row construction and hold display behavior; Reviewed: no findings. |
| `ops/pipeline/engine/queue/snapshot_store.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; snapshot store functions not fully reviewed. |
| `ops/pipeline/engine/queue/strategy_sorting.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; strategy sorting functions not fully reviewed. |
| `ops/pipeline/engine/queue/worker_claim_store.ps1` | 11 | reviewed | Reviewed claim store lifecycle and duplicate guard; finding F-W03-001. |
| `ops/pipeline/engine/queue/worker_mutex.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; mutex helper functions not fully reviewed. |
| `ops/pipeline/engine/queue/worker_process.ps1` | 4 | reviewed | Reviewed worker child launch/stop paths; Reviewed: no findings. |
| `ops/pipeline/engine/queue/worker_progress.ps1` | 5 | reviewed | Reviewed active-job/progress write paths; Reviewed: no findings. |
| `ops/pipeline/engine/status/progress_state.ps1` | 0 | partial | Summary reviewed and included in risk-pattern scan; progress state functions not fully reviewed. |
| `src/mediapipeline/core/orchestration/__init__.py` | 0 | partial | Summary reviewed; re-export surface not fully opened. |
| `src/mediapipeline/core/orchestration/planner.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; planner classes/functions not fully reviewed. |
| `src/mediapipeline/core/orchestration/runner.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; runner classes/functions not fully reviewed. |
| `src/mediapipeline/core/orchestration/settings_patch_facade.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; settings patch functions not fully reviewed. |
| `src/mediapipeline/core/processes/__init__.py` | 0 | partial | Summary reviewed; re-export surface not fully opened. |
| `src/mediapipeline/core/processes/active_job_runner.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; active-job runner functions not fully reviewed. |
| `src/mediapipeline/core/processes/active_jobs.py` | 27 | reviewed | Reviewed active-job storage and close-readiness blocking behavior; Reviewed: no findings. |
| `src/mediapipeline/core/processes/audit_facade.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; audit facade functions not fully reviewed. |
| `src/mediapipeline/core/processes/audit_policy.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; audit policy functions not fully reviewed. |
| `src/mediapipeline/core/processes/constants.py` | 0 | partial | Summary reviewed; constants not fully opened. |
| `src/mediapipeline/core/processes/control_facade.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; control facade functions not fully reviewed. |
| `src/mediapipeline/core/processes/control_flags.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; control flag functions not fully reviewed. |
| `src/mediapipeline/core/processes/control_policy.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; control policy functions not fully reviewed. |
| `src/mediapipeline/core/processes/control_runner.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; control runner functions not fully reviewed. |
| `src/mediapipeline/core/processes/file_io.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; file I/O helpers not fully reviewed. |
| `src/mediapipeline/core/processes/guard_facade.py` | 15 | reviewed | Reviewed active-work duplicate guard and close-readiness-adjacent checks; Reviewed: no findings. |
| `src/mediapipeline/core/processes/guard_policy.py` | 3 | reviewed | Reviewed progress/stop/audit guard predicates; Reviewed: no findings. |
| `src/mediapipeline/core/processes/kill.py` | 11 | reviewed | Reviewed related-process detection and kill-tree behavior; Reviewed: no findings. |
| `src/mediapipeline/core/processes/launch_cleanup.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; launch cleanup functions not fully reviewed. |
| `src/mediapipeline/core/processes/launch_env.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; launch env functions not fully reviewed. |
| `src/mediapipeline/core/processes/launch_plans.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; launch plan functions not fully reviewed. |
| `src/mediapipeline/core/processes/launch_runner.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; launch runner functions not fully reviewed. |
| `src/mediapipeline/core/processes/lifecycle.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; lifecycle functions not fully reviewed. |
| `src/mediapipeline/core/processes/logs.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; log helpers not fully reviewed. |
| `src/mediapipeline/core/processes/path_evidence.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; path evidence functions not fully reviewed. |
| `src/mediapipeline/core/processes/pipeline_facade.py` | 4 | reviewed | Reviewed pipeline start lock, schedule watcher, readiness and failure flow; Reviewed: no findings. |
| `src/mediapipeline/core/processes/pipeline_policy.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; pipeline policy functions not fully reviewed. |
| `src/mediapipeline/core/processes/preflight_facade.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; preflight facade functions not fully reviewed. |
| `src/mediapipeline/core/processes/readiness.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; readiness functions not fully reviewed. |
| `src/mediapipeline/core/processes/rerun_facade.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; rerun facade functions not fully reviewed. |
| `src/mediapipeline/core/processes/rerun_policy.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; rerun policy functions not fully reviewed. |
| `src/mediapipeline/core/processes/runtime_artifacts.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; runtime artifact cleanup functions not fully reviewed. |
| `src/mediapipeline/core/processes/runtime_runner.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; runtime runner functions not fully reviewed. |
| `src/mediapipeline/core/processes/schedule_facade.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; schedule facade functions not fully reviewed. |
| `src/mediapipeline/core/processes/schedule_policy.py` | 5 | reviewed | Reviewed schedule window and continuous-watcher duplicate guard policy; Reviewed: no findings. |
| `src/mediapipeline/core/processes/spawn.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; spawn wrapper functions not fully reviewed. |
| `src/mediapipeline/core/processes/spawn_runner.py` | 13 | reviewed | Reviewed process spawn, active job registration, readiness failure cleanup, and completion watcher; Reviewed: no findings. |
| `src/mediapipeline/core/queue/__init__.py` | 0 | partial | Summary reviewed; re-export surface not fully opened. |
| `src/mediapipeline/core/queue/contracts.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; contract classes/functions not fully reviewed. |
| `src/mediapipeline/core/queue/dry_run.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; dry-run facade functions not fully reviewed. |
| `src/mediapipeline/core/queue/dry_run_runner.py` | 2 | reviewed | Reviewed dry-run snapshot freshness and cache fallback behavior; Reviewed: no findings. |
| `src/mediapipeline/core/queue/facade.py` | 16 | reviewed | Reviewed queue preview/open-location facade and priority-manifest application; Reviewed: no findings. |
| `src/mediapipeline/core/queue/file_io.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; queue file I/O helper not fully reviewed. |
| `src/mediapipeline/core/queue/file_overrides.py` | 34 | reviewed | Reviewed override state persistence for queue/process-status interactions; Reviewed: no findings. |
| `src/mediapipeline/core/queue/policy.py` | 0 | partial | Summary reviewed; policy re-export surface not fully opened. |
| `src/mediapipeline/core/queue/policy_parts/__init__.py` | 0 | partial | Summary reviewed; re-export surface not fully opened. |
| `src/mediapipeline/core/queue/policy_parts/file_override_rows.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; functions not fully reviewed. |
| `src/mediapipeline/core/queue/policy_parts/metrics.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; functions not fully reviewed. |
| `src/mediapipeline/core/queue/policy_parts/open_policy.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; functions not fully reviewed. |
| `src/mediapipeline/core/queue/policy_parts/operator_guidance.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; functions not fully reviewed. |
| `src/mediapipeline/core/queue/policy_parts/preview.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; functions not fully reviewed. |
| `src/mediapipeline/core/queue/policy_parts/route_evidence.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; functions not fully reviewed. |
| `src/mediapipeline/core/queue/policy_parts/row_identity.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; functions not fully reviewed. |
| `src/mediapipeline/core/queue/policy_parts/rows.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; functions not fully reviewed. |
| `src/mediapipeline/core/queue/policy_parts/rules.py` | 0 | partial | Summary reviewed; constants/rules not fully opened. |
| `src/mediapipeline/core/queue/policy_parts/runtime_outcomes.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; function not fully reviewed. |
| `src/mediapipeline/core/queue/policy_parts/track_metadata.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; functions not fully reviewed. |
| `src/mediapipeline/core/queue/preview_builder.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; preview builder function not fully reviewed. |
| `src/mediapipeline/core/queue/priority_manifest.py` | 19 | reviewed | Reviewed non-destructive priority manifest state writes; Reviewed: no findings. |
| `src/mediapipeline/core/queue/priority_markers.py` | 7 | reviewed | Reviewed source-path marker/touch helper; no current finding, see boundary risk note. |
| `src/mediapipeline/core/queue/service.py` | 25 | reviewed | Reviewed scan duplicate guard, background scan state, priority APIs, and queue preview writes; Reviewed: no findings. |
| `src/mediapipeline/core/queue/snapshot.py` | 6 | reviewed | Reviewed snapshot validation/staleness behavior; Reviewed: no findings. |
| `src/mediapipeline/core/queue/source_inventory.py` | 20 | reviewed | Reviewed source inventory scan for source read-only behavior and queue status writes; Reviewed: no findings. |
| `src/mediapipeline/core/queue/strategy.py` | 0 | partial | Summary reviewed and included in risk-pattern scan; strategy functions not fully reviewed. |

## Findings

| ID | Severity | File | Symbol | Problem | Suggested validation |
|---|---|---|---|---|---|
| F-W03-001 | High | `ops/pipeline/engine/queue/worker_claim_store.ps1`; `ops/pipeline/engine/queue/local_worker_slots.ps1` | `Repair-MediaPipelineLocalWorkerClaims`; `Invoke-MediaPipelineLocalWorkerClaim`; `Invoke-MediaQueuePhasePlanLocalWorkerSlots` | Dead-worker claims with an existing result file are preserved as `result_ready`, but `result_ready` is also treated as an active duplicate claim and startup never consumes old result files outside the current `$active` set. A controller crash/kill after a worker writes its result but before claim release can leave that source blocked from future local-worker runs. | Add a restart/recovery unit test that seeds an old-run claim with `result_path`, no live worker PID, and a worker result file; verify the next run either consumes/finalizes the result or releases the stale claim so the source can be claimed again. |

## Detailed Findings

### F-W03-001 - Stale `result_ready` local-worker claims can permanently block a source

- Severity: High.
- Files and lines:
  - `ops/pipeline/engine/queue/worker_claim_store.ps1:110` defines active claim statuses as `claimed`, `starting`, `running`, `result_ready`, and `finalizing`.
  - `ops/pipeline/engine/queue/worker_claim_store.ps1:138` preserves any dead-worker claim with an existing `result_path` by setting status to `result_ready` and continuing, before the later stale-owner release branch.
  - `ops/pipeline/engine/queue/worker_claim_store.ps1:183` rejects any future claim for the same `source_key` when the old claim status is in that active-status set.
  - `ops/pipeline/engine/queue/local_worker_slots.ps1:27` runs claim repair at startup, but `ops/pipeline/engine/queue/local_worker_slots.ps1:43` then skips the entry when the duplicate claim returns `$null`.
  - `ops/pipeline/engine/queue/local_worker_slots.ps1:70` consumes result files only for jobs in the current in-memory `$active` table, so a previous-run `result_ready` claim is not finalized by this loop.
- Problem: `Repair-MediaPipelineLocalWorkerClaims` treats a result file from a dead worker as evidence to preserve the claim, but the only result-consumption path is tied to workers launched by the current controller process. Because `result_ready` remains an active duplicate-guard status, the source is skipped instead of finalized or retried.
- Impact: If the parent/controller exits after a worker writes `worker_result.json` but before `Release-MediaPipelineLocalWorkerClaim`, the queue can repeatedly log a duplicate active claim and never process that source again. Failed worker results can also be left uncounted/unreported by the parent counters.
- Evidence: The code path is internally self-contained: `result_ready` is active at line 111, repair preserves stale result claims at lines 138-143, duplicate claim rejection uses the same status set at lines 183-187, and `local_worker_slots.ps1` has no startup path that reads result files for old claims before skipping entries at lines 43-46.
- Fix direction: Make repair/startup explicitly handle no-live-worker `result_ready` claims from prior runs. Either consume and finalize the saved result idempotently before queueing entries, or release the claim to a non-active stale-result status and allow the item to be claimed again. Keep same-run/live-worker `result_ready` behavior guarded so duplicate processing is still prevented.
- Validation: Extend the local-worker slot/claim tests with an old `owner_run_id`, absent/dead `worker_pid`, existing `result_path`, and a queued entry for the same source. Assert the claim is no longer active-blocking after repair/startup and that result finalization or retry behavior is explicit. Also keep coverage for the intended duplicate guard while a current worker is live.

## Test Coverage Gaps

- No tests were executed; this was a review-only audit and the user constrained edits to this worker markdown file.
- Observed gap for F-W03-001: local-worker claim repair needs restart/crash recovery coverage for a stale `result_ready` claim with an existing worker result file. Existing coverage observed during the audit covered stale running/no-result release behavior, but not the result-ready branch that remains duplicate-active.
- Partial coverage gap: files listed under `Incomplete Coverage` were not fully source-reviewed, so additional targeted tests may be identified by the owning follow-up worker.

## Boundary Risks

- Queue/process duplicate-command safety risk: F-W03-001 sits directly in the local-worker duplicate-claim guard. The current guard prevents concurrent duplicate work, but the stale result path can convert that guard into an indefinite skip.
- Source-mutation boundary note: `src/mediapipeline/core/queue/priority_markers.py` contains `rename`/`utime` helpers for priority marker files. No current finding was filed because the reviewed queue priority path uses non-destructive manifest state and no exposed route caller was found in this worker's assigned review, but this helper must not be newly exposed without an explicit source-mutation/safe-delete-style gate and high validation.
- No runtime, media, queue state, source media, or LocalBase artifacts were intentionally mutated during this audit.

## Files With No Findings

- Reviewed: no findings in `ops/pipeline/engine/process/pipeline_processing.ps1`.
- Reviewed: no findings in `ops/pipeline/engine/process/pipeline_processing/preflight.ps1`.
- Reviewed: no findings in `ops/pipeline/engine/queue/phase_executor.ps1`.
- Reviewed: no findings in `ops/pipeline/engine/queue/phase_plan.ps1`.
- Reviewed: no findings in `ops/pipeline/engine/queue/pipeline_engine.ps1`.
- Reviewed: no findings in `ops/pipeline/engine/queue/queue_entries.ps1`.
- Reviewed: no findings in `ops/pipeline/engine/queue/queue_plan.ps1`.
- Reviewed: no findings in `ops/pipeline/engine/queue/snapshot_rows.ps1`.
- Reviewed: no findings in `ops/pipeline/engine/queue/worker_process.ps1`.
- Reviewed: no findings in `ops/pipeline/engine/queue/worker_progress.ps1`.
- Reviewed: no findings in `src/mediapipeline/core/processes/active_jobs.py`.
- Reviewed: no findings in `src/mediapipeline/core/processes/guard_facade.py`.
- Reviewed: no findings in `src/mediapipeline/core/processes/guard_policy.py`.
- Reviewed: no findings in `src/mediapipeline/core/processes/kill.py`.
- Reviewed: no findings in `src/mediapipeline/core/processes/pipeline_facade.py`.
- Reviewed: no findings in `src/mediapipeline/core/processes/schedule_policy.py`.
- Reviewed: no findings in `src/mediapipeline/core/processes/spawn_runner.py`.
- Reviewed: no findings in `src/mediapipeline/core/queue/dry_run_runner.py`.
- Reviewed: no findings in `src/mediapipeline/core/queue/facade.py`.
- Reviewed: no findings in `src/mediapipeline/core/queue/file_overrides.py`.
- Reviewed: no findings in `src/mediapipeline/core/queue/priority_manifest.py`.
- Reviewed: no findings in `src/mediapipeline/core/queue/priority_markers.py` for current assigned queue/process exposure; see boundary risk note.
- Reviewed: no findings in `src/mediapipeline/core/queue/service.py`.
- Reviewed: no findings in `src/mediapipeline/core/queue/snapshot.py`.
- Reviewed: no findings in `src/mediapipeline/core/queue/source_inventory.py`.

## Incomplete Coverage

Coverage is partial because the turn was time-boxed before full source review of every assigned symbol. For all files below, generated summaries were read before full source access and the files were included in a broad risk-pattern scan for process launch/kill, source mutation, stale state, duplicate guards, schedule, close-readiness, and active-work terms, but the listed symbol bodies were not fully reviewed.

- `ops/pipeline/engine/process/ffmpeg_progress.ps1`: all 3 functions not fully reviewed.
- `ops/pipeline/engine/process/ffmpeg_progress/events.ps1`: 1 function not fully reviewed.
- `ops/pipeline/engine/process/ffmpeg_progress/parsing.ps1`: all 3 functions not fully reviewed.
- `ops/pipeline/engine/process/ffmpeg_progress/tool_context.ps1`: 1 function not fully reviewed.
- `ops/pipeline/engine/process/file_processor.ps1`: 1 function not fully reviewed.
- `ops/pipeline/engine/process/pipeline_plan_executor.ps1`: all 29 functions not fully reviewed.
- `ops/pipeline/engine/process/pipeline_plan_executor/validation.ps1`: all 12 functions not fully reviewed.
- `ops/pipeline/engine/process/worker_result.ps1`: both functions not fully reviewed.
- `ops/pipeline/engine/queue/engine_plan.ps1`: both functions not fully reviewed.
- `ops/pipeline/engine/queue/file_overrides.ps1`: all 22 functions not fully reviewed.
- `ops/pipeline/engine/queue/priority_manifest.ps1`: all 5 functions not fully reviewed.
- `ops/pipeline/engine/queue/snapshot_store.ps1`: both functions not fully reviewed.
- `ops/pipeline/engine/queue/strategy_sorting.ps1`: all 5 functions not fully reviewed.
- `ops/pipeline/engine/queue/worker_mutex.ps1`: all 8 functions not fully reviewed.
- `ops/pipeline/engine/status/progress_state.ps1`: all 29 functions not fully reviewed.
- `src/mediapipeline/core/orchestration/__init__.py`: re-export surface not fully opened.
- `src/mediapipeline/core/orchestration/planner.py`: all 20 classes/functions not fully reviewed.
- `src/mediapipeline/core/orchestration/runner.py`: all 15 classes/functions not fully reviewed.
- `src/mediapipeline/core/orchestration/settings_patch_facade.py`: all 8 classes/functions not fully reviewed.
- `src/mediapipeline/core/processes/__init__.py`: re-export surface not fully opened.
- `src/mediapipeline/core/processes/active_job_runner.py`: all 14 classes/functions not fully reviewed.
- `src/mediapipeline/core/processes/audit_facade.py`: both functions not fully reviewed.
- `src/mediapipeline/core/processes/audit_policy.py`: all 9 functions not fully reviewed.
- `src/mediapipeline/core/processes/constants.py`: constants not fully opened.
- `src/mediapipeline/core/processes/control_facade.py`: all 6 functions not fully reviewed.
- `src/mediapipeline/core/processes/control_flags.py`: all 7 functions not fully reviewed.
- `src/mediapipeline/core/processes/control_policy.py`: all 4 functions not fully reviewed.
- `src/mediapipeline/core/processes/control_runner.py`: all 21 classes/functions not fully reviewed.
- `src/mediapipeline/core/processes/file_io.py`: all 3 functions not fully reviewed.
- `src/mediapipeline/core/processes/launch_cleanup.py`: all 5 functions not fully reviewed.
- `src/mediapipeline/core/processes/launch_env.py`: both functions not fully reviewed.
- `src/mediapipeline/core/processes/launch_plans.py`: all 5 classes/functions not fully reviewed.
- `src/mediapipeline/core/processes/launch_runner.py`: all 5 functions not fully reviewed.
- `src/mediapipeline/core/processes/lifecycle.py`: all 47 classes/functions not fully reviewed.
- `src/mediapipeline/core/processes/logs.py`: all 3 functions not fully reviewed.
- `src/mediapipeline/core/processes/path_evidence.py`: all 28 functions not fully reviewed.
- `src/mediapipeline/core/processes/pipeline_policy.py`: all 17 functions not fully reviewed.
- `src/mediapipeline/core/processes/preflight_facade.py`: all 17 classes/functions not fully reviewed.
- `src/mediapipeline/core/processes/readiness.py`: all 5 classes/functions not fully reviewed.
- `src/mediapipeline/core/processes/rerun_facade.py`: both functions not fully reviewed.
- `src/mediapipeline/core/processes/rerun_policy.py`: all 15 classes/functions not fully reviewed.
- `src/mediapipeline/core/processes/runtime_artifacts.py`: all 7 functions not fully reviewed.
- `src/mediapipeline/core/processes/runtime_runner.py`: all 23 classes/functions not fully reviewed.
- `src/mediapipeline/core/processes/schedule_facade.py`: all 3 functions not fully reviewed.
- `src/mediapipeline/core/processes/spawn.py`: all 6 functions not fully reviewed.
- `src/mediapipeline/core/queue/__init__.py`: re-export surface not fully opened.
- `src/mediapipeline/core/queue/contracts.py`: all 11 classes/functions not fully reviewed.
- `src/mediapipeline/core/queue/dry_run.py`: all 4 functions not fully reviewed.
- `src/mediapipeline/core/queue/file_io.py`: 1 helper not fully reviewed.
- `src/mediapipeline/core/queue/policy.py`: re-export surface not fully opened.
- `src/mediapipeline/core/queue/policy_parts/__init__.py`: re-export surface not fully opened.
- `src/mediapipeline/core/queue/policy_parts/file_override_rows.py`: both functions not fully reviewed.
- `src/mediapipeline/core/queue/policy_parts/metrics.py`: all 12 functions not fully reviewed.
- `src/mediapipeline/core/queue/policy_parts/open_policy.py`: all 17 functions not fully reviewed.
- `src/mediapipeline/core/queue/policy_parts/operator_guidance.py`: all 6 functions not fully reviewed.
- `src/mediapipeline/core/queue/policy_parts/preview.py`: all 7 functions not fully reviewed.
- `src/mediapipeline/core/queue/policy_parts/route_evidence.py`: both functions not fully reviewed.
- `src/mediapipeline/core/queue/policy_parts/row_identity.py`: all 8 functions not fully reviewed.
- `src/mediapipeline/core/queue/policy_parts/rows.py`: all 7 functions not fully reviewed.
- `src/mediapipeline/core/queue/policy_parts/rules.py`: constants/rules not fully opened.
- `src/mediapipeline/core/queue/policy_parts/runtime_outcomes.py`: 1 function not fully reviewed.
- `src/mediapipeline/core/queue/policy_parts/track_metadata.py`: all 12 functions not fully reviewed.
- `src/mediapipeline/core/queue/preview_builder.py`: 1 function not fully reviewed.
- `src/mediapipeline/core/queue/strategy.py`: all 6 functions not fully reviewed.
