# Worker Review: worker-03-core-queue-process-status

## Scope

Worker ID: `worker-03-core-queue-process-status`

Assigned slice: queue/process/status orchestration, including queue services and dry-run/snapshot logic, process launch/control/lifecycle modules, schedule/start/stop behavior, status/progress/active-job readers, launch scope, and CSV/rerun behavior.

Assigned files: the 91 W03 files listed in `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`.

Coverage status: partial. All assigned generated summaries were checked for existence before source review, and all 91 assigned paths were included in targeted launch/lifecycle/source-mutation/state-file searches. Full source review focused on the queue service, dry-run runner, process launch/control/close-readiness modules, ActiveJobs handling, PowerShell queue engine, local worker slot/claim/process/progress modules, and queue snapshot/priority/file-override modules. Deep FFmpeg/probe/codec behavior inside process helpers was not line-by-line reviewed because W05 owns media-policy semantics.

## Coverage Ledger

Required context read:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`

Summary-first checks:

- Confirmed generated summaries exist for all 91 assigned W03 paths under `docs/generated/summaries/`.
- Checked W03 summaries before opening implementation files.
- No assigned summary needed to be bypassed because of a missing summary.

Targeted full-source review:

- Queue service/dry-run/snapshot/preview: `src/mediapipeline/core/queue/service.py`, `dry_run.py`, `dry_run_runner.py`, `snapshot.py`, `preview_builder.py`, `source_inventory.py`, `priority_manifest.py`, `priority_markers.py`, `file_overrides.py`, `facade.py`, `policy_parts/rows.py`.
- Process lifecycle and launch/control: `src/mediapipeline/core/processes/pipeline_facade.py`, `rerun_facade.py`, `control_facade.py`, `guard_facade.py`, `guard_policy.py`, `kill.py`, `launch_plans.py`, `launch_runner.py`, `lifecycle.py`, `spawn_runner.py`, `active_jobs.py`, `schedule_policy.py`, `control_flags.py`.
- PowerShell queue lifecycle: `ops/pipeline/engine/queue/local_worker_slots.ps1`, `worker_claim_store.ps1`, `worker_process.ps1`, `worker_progress.ps1`, `phase_executor.ps1`, `phase_plan.ps1`, `pipeline_engine.ps1`, `snapshot_rows.ps1`, `snapshot_store.ps1`, `strategy_sorting.ps1`, `queue_entries.ps1`.
- Process/status-adjacent PowerShell: `ops/pipeline/engine/process/pipeline_plan_executor.ps1`, `pipeline_processing.ps1`, `pipeline_processing/preflight.ps1`, `ops/pipeline/engine/status/progress_state.ps1`.

Read-only probes run:

- Searched W03 directories for launch/stop/rerun primitives: `Start-Process`, `Stop-Process`, `Kill(`, `run_capture`, `Popen`, `daemon=True`, `ActiveJobs`, `SingleFile`, `Csv`, `rerun`, `force stop`.
- Searched W03 directories for source/runtime mutation primitives: `Remove-Item`, `Move-Item`, `Rename-Item`, `.rename(`, `unlink(`, `os.remove`, `rmtree`.
- Searched tests for coverage of queue source scan close-readiness, local worker `failed_start`, stale `result_ready`, priority marker mutation, and malformed file-override entries.
- Searched all active repo areas for `result_ready`; only producer/gate references were found in `ops/pipeline/engine/queue/worker_claim_store.ps1`.

## Findings Summary

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 1 |
| Medium | 2 |
| Low | 1 |

Boundary risks are listed separately below.

## Detailed Findings

### High: Local worker child can keep processing after claim update fails post-spawn

Severity: High

File: `ops/pipeline/engine/queue/local_worker_slots.ps1`

Symbol/section: `Invoke-MediaQueuePhasePlanLocalWorkerSlots`

Evidence:

- The parent starts a child process at `ops/pipeline/engine/queue/local_worker_slots.ps1:49`.
- The claim is only marked `running` after that, at `ops/pipeline/engine/queue/local_worker_slots.ps1:50`.
- The child is only added to the parent `$active` table after the claim update succeeds, at `ops/pipeline/engine/queue/local_worker_slots.ps1:53` through `ops/pipeline/engine/queue/local_worker_slots.ps1:58`.
- The `catch` block only logs and releases the claim as `failed_start`, at `ops/pipeline/engine/queue/local_worker_slots.ps1:62` through `ops/pipeline/engine/queue/local_worker_slots.ps1:64`; it does not stop an already-created `$proc`.
- The child command runs the claimed source through `-SingleFile`, shown at `ops/pipeline/engine/queue/worker_process.ps1:61`.
- A child-stop helper exists at `ops/pipeline/engine/queue/worker_process.ps1:79` and escalates to process-tree kill at `ops/pipeline/engine/queue/worker_process.ps1:90`, but that helper is not invoked on the post-spawn failure path.

Impact:

If `Start-MediaPipelineLocalWorkerChild` succeeds and `Update-MediaPipelineLocalWorkerClaim` fails because the claim store, mutex, disk write, or JSON write path fails, the child continues processing outside the parent `$active` table. The parent then releases the claim as `failed_start`, so later queue iterations or future runs can claim the same source again while the first child is still processing. Stop requests and local-worker ActiveJobs also underreport the live child.

Fix direction:

Initialize `$proc = $null` before the start attempt. In the `catch`, if `$proc` is non-null and not exited, call `Stop-MediaPipelineLocalWorkerProcess` before releasing or rewriting the claim. Prefer a distinct failure status/reason for "spawned child stopped after claim update failure" so repair logic can distinguish it from pre-spawn failures.

Validation:

Add a Pester test around `Invoke-MediaQueuePhasePlanLocalWorkerSlots` that stubs `Start-MediaPipelineLocalWorkerChild` to return a live fake process and stubs `Update-MediaPipelineLocalWorkerClaim` to throw. Assert the stop helper is called, the active-job payload does not omit a live child, and the claim is not released until the child is stopped or explicitly marked for recovery.

### Medium: Queue source scan can be abandoned because close-readiness does not know about the daemon worker

Severity: Medium

Files:

- `src/mediapipeline/core/queue/service.py`
- `src/mediapipeline/core/processes/guard_facade.py`
- `src/mediapipeline/core/queue/dry_run_runner.py`

Symbol/section:

- `QueueServiceMixin.start_queue_source_scan`
- `QueueServiceMixin._run_queue_source_scan_worker`
- `ProcessGuardFacadeMixin._active_work_block_message`

Evidence:

- `start_queue_source_scan` creates the worker thread with `daemon=True` at `src/mediapipeline/core/queue/service.py:221` through `src/mediapipeline/core/queue/service.py:226`.
- The worker is recorded only in memory as `_queue_source_scan_active` at `src/mediapipeline/core/queue/service.py:227`.
- The worker enters queue curation by calling `self.build_queue_preview(...)` at `src/mediapipeline/core/queue/service.py:326`.
- Queue preview can run the PowerShell dry-run subprocess through `run_capture(...)` with a 120-second timeout and kill-tree callback at `src/mediapipeline/core/queue/dry_run_runner.py:56` through `src/mediapipeline/core/queue/dry_run_runner.py:65`.
- Close-readiness checks related processes, final-library promotion, schedule watcher, ActiveJobs, pipeline progress, and audit progress at `src/mediapipeline/core/processes/guard_facade.py:62` through `src/mediapipeline/core/processes/guard_facade.py:100`, but has no check for `_queue_source_scan_active` or queue-scan status.

Impact:

The backend can report shell close as safe while a queue source scan is still running. Because the scan thread is daemonized, backend shutdown can terminate it mid-status update or while a queue dry-run subprocess is active. That can leave `queue_source_scan_status.json` reporting `running`, leave temp snapshots behind, or abandon a dry-run child without the normal timeout/kill-tree cleanup path.

Fix direction:

Make queue scan activity visible to process guards. Either register queue scans as a close-readiness work kind, persist a terminal status during shutdown, or avoid daemon worker semantics and join/cancel the scan during backend shutdown. If queue dry-run remains subprocess-backed, register it in the same active-work surface or ensure shutdown cancels and kills it explicitly.

Validation:

Add a Python service test that starts a long-running/fake queue source scan, calls the close-readiness endpoint or `_active_work_block_message`, and expects a blocking message until the scan reaches a terminal state. Add a shutdown test that verifies queue scan status is not left `running` when the worker is interrupted.

### Medium: Stale `result_ready` worker claims block future claims with no consumer

Severity: Medium

File: `ops/pipeline/engine/queue/worker_claim_store.ps1`

Symbol/section:

- `Get-MediaPipelineLocalWorkerClaimActiveStatuses`
- `Repair-MediaPipelineLocalWorkerClaims`
- `Invoke-MediaPipelineLocalWorkerClaim`

Evidence:

- `result_ready` is included in active claim statuses at `ops/pipeline/engine/queue/worker_claim_store.ps1:110` through `ops/pipeline/engine/queue/worker_claim_store.ps1:111`.
- Repair marks a dead worker claim as `result_ready` when its result file exists at `ops/pipeline/engine/queue/worker_claim_store.ps1:138` through `ops/pipeline/engine/queue/worker_claim_store.ps1:141`.
- New claims for the same `source_key` are rejected when an existing claim is in any active status at `ops/pipeline/engine/queue/worker_claim_store.ps1:183` through `ops/pipeline/engine/queue/worker_claim_store.ps1:186`.
- A repository-wide search for `result_ready` under `ops`, `src`, `tests`, and `apps` found no consumer other than these claim-store references.

Impact:

If the controller crashes or exits after a worker writes its result file but before the parent consumes and releases the claim, repair preserves the claim as `result_ready`. Since `result_ready` is also treated as active and no consumer path was found, subsequent runs skip the same source as a duplicate active claim indefinitely. That leaves the source unprocessed or unpublishable from the operator's perspective until the claim store is manually repaired.

Fix direction:

Add a deterministic recovery path for `result_ready`: on startup or before claiming, read and apply the worker result, transition the claim to a terminal released/completed/failed status, and only then permit a new claim. If automatic result consumption is not safe, surface a blocking diagnostic with a repair command rather than silently treating it as an ordinary active duplicate.

Validation:

Add a Pester test with a stale claim whose `worker_pid` is dead and whose `result_path` exists. After `Repair-MediaPipelineLocalWorkerClaims`, run the next claim attempt for the same source and assert either the result is consumed and the claim releases, or the operator receives an explicit recovery block instead of an indefinite duplicate-claim skip.

### Low: Malformed per-entry file override values can crash serializers

Severity: Low

File: `src/mediapipeline/core/queue/file_overrides.py`

Symbol/section:

- `read_file_overrides`
- `list_override_entries`
- `file_overrides_to_api_payload`

Evidence:

- `read_file_overrides` validates that the manifest is a dict, version is correct, and `entries` is a dict at `src/mediapipeline/core/queue/file_overrides.py:177` through `src/mediapipeline/core/queue/file_overrides.py:188`, but it does not validate that each entry value is a dict.
- `list_override_entries` expands each entry value as a mapping with `{"path": k, **v}` at `src/mediapipeline/core/queue/file_overrides.py:248` through `src/mediapipeline/core/queue/file_overrides.py:253`.
- `file_overrides_to_api_payload` assumes every entry value has `.get(...)` at `src/mediapipeline/core/queue/file_overrides.py:817` through `src/mediapipeline/core/queue/file_overrides.py:834`.

Impact:

A corrupt but version-correct `file_overrides.json` with a scalar entry value can pass `read_file_overrides` and then raise `TypeError` or `AttributeError` in API/queue serializers. This is a state-file consistency issue, not an immediate media mutation risk, but it can break queue/file-override views until the state file is manually corrected.

Fix direction:

Normalize or reject non-dict entry values at read time. Prefer dropping invalid entries into a warning/repair surface and returning the remaining valid entries rather than letting serializer code fail later.

Validation:

Add a Python unit test with `{"version": 1, "entries": {"x.mkv": "bad"}}` and assert read/list/API payload paths either return an empty repaired manifest or a payload with an explicit invalid-entry warning, without raising.

## Test Coverage Gaps

- No Pester coverage found for the local-worker path where child spawn succeeds and claim update fails before the child is added to `$active`.
- No test found that close-readiness blocks while `_queue_source_scan_active` is running.
- No recovery test found for a dead local-worker claim with an existing result file and `result_ready` status.
- Existing malformed file-override coverage exercises malformed whole manifests, but not version-correct manifests containing scalar/non-dict entry values.
- Priority marker tests exercise source-path rename behavior, but no no-mutation guard test was found around route/service exposure.

## Boundary Risks

### Medium boundary risk: Priority marker helper still physically renames/touches source paths

Files:

- `src/mediapipeline/core/queue/priority_markers.py`
- `src/mediapipeline/core/queue/service.py`

Evidence:

- `touch_priority_target` calls `os.utime` on the target path at `src/mediapipeline/core/queue/priority_markers.py:80` through `src/mediapipeline/core/queue/priority_markers.py:83`.
- `apply_priority_marker` calls `target_path.rename(destination)` and then touches the renamed file at `src/mediapipeline/core/queue/priority_markers.py:88` through `src/mediapipeline/core/queue/priority_markers.py:100`.
- `QueueServiceMixin` exposes these helpers at `src/mediapipeline/core/queue/service.py:406` through `src/mediapipeline/core/queue/service.py:410`.

Impact:

This conflicts with the repository boundary that source mutation is forbidden by default. The current active search did not find an assigned W03 route calling this helper, and the non-destructive priority manifest path exists separately, but the service-level helper remains a footgun if a route or operator command reconnects to it.

Fix direction:

Prefer the priority manifest as the only queue-priority mutation path. If physical marker rename/touch behavior must remain, gate it behind an explicit source-mutation setting, command journal entry, and operator confirmation that names the source path mutation.

Validation:

Add route/service tests proving the default priority workflow does not rename or touch source files. Add a targeted test for the explicit opt-in path if physical marker operations remain supported.

## Files Reviewed With No Findings

Process launch/control modules reviewed with no separate finding beyond the queue-scan close-readiness gap:

- `src/mediapipeline/core/processes/pipeline_facade.py`
- `src/mediapipeline/core/processes/rerun_facade.py`
- `src/mediapipeline/core/processes/control_facade.py`
- `src/mediapipeline/core/processes/control_flags.py`
- `src/mediapipeline/core/processes/control_policy.py`
- `src/mediapipeline/core/processes/control_runner.py`
- `src/mediapipeline/core/processes/guard_policy.py`
- `src/mediapipeline/core/processes/kill.py`
- `src/mediapipeline/core/processes/launch_cleanup.py`
- `src/mediapipeline/core/processes/launch_env.py`
- `src/mediapipeline/core/processes/launch_plans.py`
- `src/mediapipeline/core/processes/launch_runner.py`
- `src/mediapipeline/core/processes/lifecycle.py`
- `src/mediapipeline/core/processes/preflight_facade.py`
- `src/mediapipeline/core/processes/readiness.py`
- `src/mediapipeline/core/processes/rerun_policy.py`
- `src/mediapipeline/core/processes/runtime_artifacts.py`
- `src/mediapipeline/core/processes/runtime_runner.py`
- `src/mediapipeline/core/processes/schedule_facade.py`
- `src/mediapipeline/core/processes/schedule_policy.py`
- `src/mediapipeline/core/processes/spawn.py`
- `src/mediapipeline/core/processes/spawn_runner.py`
- `src/mediapipeline/core/processes/active_job_runner.py`
- `src/mediapipeline/core/processes/active_jobs.py`
- `src/mediapipeline/core/processes/audit_facade.py`
- `src/mediapipeline/core/processes/audit_policy.py`
- `src/mediapipeline/core/processes/constants.py`
- `src/mediapipeline/core/processes/file_io.py`
- `src/mediapipeline/core/processes/logs.py`
- `src/mediapipeline/core/processes/path_evidence.py`
- `src/mediapipeline/core/processes/pipeline_policy.py`
- `src/mediapipeline/core/processes/__init__.py`

Queue modules reviewed with no separate finding beyond the findings above:

- `src/mediapipeline/core/queue/__init__.py`
- `src/mediapipeline/core/queue/contracts.py`
- `src/mediapipeline/core/queue/dry_run.py`
- `src/mediapipeline/core/queue/dry_run_runner.py`
- `src/mediapipeline/core/queue/facade.py`
- `src/mediapipeline/core/queue/file_io.py`
- `src/mediapipeline/core/queue/policy.py`
- `src/mediapipeline/core/queue/policy_parts/__init__.py`
- `src/mediapipeline/core/queue/policy_parts/file_override_rows.py`
- `src/mediapipeline/core/queue/policy_parts/metrics.py`
- `src/mediapipeline/core/queue/policy_parts/open_policy.py`
- `src/mediapipeline/core/queue/policy_parts/operator_guidance.py`
- `src/mediapipeline/core/queue/policy_parts/preview.py`
- `src/mediapipeline/core/queue/policy_parts/route_evidence.py`
- `src/mediapipeline/core/queue/policy_parts/row_identity.py`
- `src/mediapipeline/core/queue/policy_parts/rows.py`
- `src/mediapipeline/core/queue/policy_parts/rules.py`
- `src/mediapipeline/core/queue/policy_parts/runtime_outcomes.py`
- `src/mediapipeline/core/queue/policy_parts/track_metadata.py`
- `src/mediapipeline/core/queue/preview_builder.py`
- `src/mediapipeline/core/queue/priority_manifest.py`
- `src/mediapipeline/core/queue/snapshot.py`
- `src/mediapipeline/core/queue/source_inventory.py`
- `src/mediapipeline/core/queue/strategy.py`

PowerShell queue/process/status modules reviewed or summary-plus-risk-scanned with no separate finding beyond the findings above:

- `ops/pipeline/engine/process/ffmpeg_progress.ps1`
- `ops/pipeline/engine/process/ffmpeg_progress/events.ps1`
- `ops/pipeline/engine/process/ffmpeg_progress/parsing.ps1`
- `ops/pipeline/engine/process/ffmpeg_progress/tool_context.ps1`
- `ops/pipeline/engine/process/file_processor.ps1`
- `ops/pipeline/engine/process/pipeline_plan_executor.ps1`
- `ops/pipeline/engine/process/pipeline_plan_executor/validation.ps1`
- `ops/pipeline/engine/process/pipeline_processing.ps1`
- `ops/pipeline/engine/process/pipeline_processing/preflight.ps1`
- `ops/pipeline/engine/process/worker_result.ps1`
- `ops/pipeline/engine/queue/engine_plan.ps1`
- `ops/pipeline/engine/queue/file_overrides.ps1`
- `ops/pipeline/engine/queue/phase_executor.ps1`
- `ops/pipeline/engine/queue/phase_plan.ps1`
- `ops/pipeline/engine/queue/pipeline_engine.ps1`
- `ops/pipeline/engine/queue/priority_manifest.ps1`
- `ops/pipeline/engine/queue/queue_entries.ps1`
- `ops/pipeline/engine/queue/queue_plan.ps1`
- `ops/pipeline/engine/queue/snapshot_rows.ps1`
- `ops/pipeline/engine/queue/snapshot_store.ps1`
- `ops/pipeline/engine/queue/strategy_sorting.ps1`
- `ops/pipeline/engine/queue/worker_mutex.ps1`
- `ops/pipeline/engine/queue/worker_progress.ps1`
- `ops/pipeline/engine/status/progress_state.ps1`

Orchestration modules reviewed or summary-plus-risk-scanned with no finding:

- `src/mediapipeline/core/orchestration/__init__.py`
- `src/mediapipeline/core/orchestration/planner.py`
- `src/mediapipeline/core/orchestration/runner.py`
- `src/mediapipeline/core/orchestration/settings_patch_facade.py`

## Files Marked Out Of Scope

- `src/mediapipeline/core/status/*` Python status modules are assigned to W06 in `ASSIGNMENTS.md`; W03 only included `ops/pipeline/engine/status/progress_state.ps1`.
- Local API route handler ownership for invoking queue/process commands is assigned to W01; this review cited route tests only as supporting coverage evidence.
- WebView/Tauri callers are assigned to W07, W08, and W09.
- Publish, rename, pending-publish drain, and completed-output movement are assigned to W04.
- FFmpeg codec/subtitle/audio policy correctness is assigned to W05. W03 reviewed process lifecycle and queue orchestration surfaces only.
- Tests as primary artifacts are assigned to W11; this review searched tests only to identify coverage gaps for W03 findings.

## Incomplete Coverage

- No assigned files were intentionally skipped.
- Coverage is partial because several assigned PowerShell process helpers and queue policy helpers were reviewed through generated summaries plus targeted risk-pattern scans instead of complete line-by-line function review.
- Media-policy semantics in FFmpeg/probe/subtitle/audio helper paths were not audited beyond launch/progress/lifecycle implications, per W05 ownership.
- No runtime media, queue, or LocalBase state was mutated. No tests were executed that start real pipeline workers or media tools.
