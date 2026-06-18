# Invariants and Boundaries

This file records the invariants that must hold for safe launch behavior. Each invariant is written as an operator-safety boundary: violating it can process the wrong file, start work twice, ignore scope, or mislead the operator.

## Launch Scope Invariants

1. Backend launch scope is authoritative.
   - The visible Queue table, text filters, status filters, investigation filters, selected rows, and visible-row subsets are not submitted in pipeline start requests.
   - Evidence: `apps/desktop/webview/static/assets/launchView.scope.js:199-206`.

2. Queue preview must mirror runnable backend queue plan order.
   - `build_queue_preview()` is documented as the same rows `Invoke-MediaQueuePhasePlan` would process, in exact order.
   - Evidence: `src/mediapipeline/core/queue/service.py:399-409`.

3. Queue dry-run evidence must distinguish runnable rows from filtered rows.
   - Dry-run runs `MediaPipeline.ps1 -EmitQueuePlan` and reports runnable plus filtered counts.
   - Evidence: `src/mediapipeline/core/queue/dry_run.py:27` and `src/mediapipeline/core/queue/dry_run.py:48-68`.

4. Source inventory is not launch scope.
   - Inventory scan rows are informational and non-launchable. Backend queue curation remains authoritative.
   - Evidence: `src/mediapipeline/core/queue/source_inventory.py` generated/source comments and row fields.

5. Single-file mode is a separate launch surface and must be scoped independently.
   - Single-file launch skips queue discovery and processes exactly one file.
   - Evidence: `ops/pipeline/entrypoints/MediaPipeline.ps1:585-629`.
   - Current boundary failure: the backend does not require `single_file` to be under configured source roots. See `05-findings.md`.

## Priority Invariants

6. Priority manifest writes must be constrained to source roots.
   - Queue priority updates require absolute paths under `SourceMovies`, `SourceTV`, or enabled library profile source roots.
   - Evidence: `src/mediapipeline/desktop/api/queue_source_path_policy.py:69-81`.

7. Hold means display-only, not runnable.
   - Queue phase planning carries hold entries separately from runnable high/normal/low entries.
   - Evidence: `ops/pipeline/engine/queue/phase_plan.ps1:26-47` and `ops/pipeline/engine/queue/phase_plan.ps1:119-144`.

8. Low priority is still runnable.
   - Low entries are included after high and normal entries. Operators should not interpret low as hold.
   - Evidence: `ops/pipeline/engine/queue/phase_plan.ps1:47` and `ops/pipeline/engine/queue/phase_plan.ps1:142-144`.

## CSV Rerun Invariants

9. CSV rerun rows are CSV-authoritative, but source identity must be rechecked.
   - `Invoke-RerunCsv.ps1` reads row source fields, verifies identity evidence, and marks invalid rows failed.
   - Evidence: `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:484-491` and `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:548-550`.

10. WebView-supported CSV rerun policy is copy/keep/park only.
   - The facade accepts only `copy`, `keep`, and `park`; the script rejects unsafe row overrides.
   - Evidence: `src/mediapipeline/core/processes/rerun_facade.py`, `src/mediapipeline/core/processes/rerun_policy.py`, and `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:518-531`.

11. CSV dry-run evidence must be available before live rerun decisions.
   - Backend support exists through `-DryRun` and `dry_run_complete` manifest status.
   - Evidence: `src/mediapipeline/core/processes/launch_plans.py:170` and `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:751-754`.
   - Current boundary failure: WebView hard-codes `dry_run: false` and has no dry-run control. See `05-findings.md`.

## Schedule Invariants

12. Schedule gate must run before process launch.
   - Pipeline start resolves schedule gate before the launch lock and process spawn path.
   - Evidence: `src/mediapipeline/core/processes/pipeline_facade.py:95-97`.

13. Scheduled continuous launch must have watcher ownership unless explicitly bypassed.
   - Continuous mode inside an enforced schedule is blocked when the backend schedule-stop watcher is unavailable.
   - Evidence: `src/mediapipeline/core/processes/schedule_policy.py:8-15` and `src/mediapipeline/core/processes/schedule_policy.py:171-174`.

14. Outside-window launch requires explicit operator override.
   - Outside-window starts are blocked unless `run_once` or `ignore` is selected.
   - Evidence: `src/mediapipeline/core/processes/schedule_policy.py:181-190`.

15. Stop-at-window-end uses Stop After Current semantics.
   - The schedule-stop watcher writes the stop flag at the boundary instead of force-killing work.
   - Evidence: `src/mediapipeline/desktop/application/schedule_stop_watcher.py`.

## Stop and Force Stop Invariants

16. Stop After Current is a cooperative stop flag.
   - Stop writes the stop flag; active pipeline logic is expected to finish current work and avoid taking new work.
   - Evidence: `src/mediapipeline/core/processes/control_facade.py:135-140`.

17. Force Stop must either be job-kind scoped or explicitly labeled as broad emergency termination.
   - Current backend kill call omits `job_kinds`, which includes pipeline, audit, and rerun script needles.
   - Evidence: `src/mediapipeline/core/processes/control_facade.py:148-156` and `src/mediapipeline/core/processes/kill.py:105-113`.
   - Current boundary weakness: UI copy describes pipeline scope more narrowly than backend behavior. See `05-findings.md`.

## Duplicate and Active-Work Invariants

18. A process launch command must not overlap another launch command.
   - Process launch lock acquisition is nonblocking and returns a duplicate launch block.
   - Evidence: `src/mediapipeline/core/processes/guard_facade.py:29-40`.

19. Active work must be checked from multiple independent sources.
   - Related PowerShell processes, queue scan state, schedule watcher state, ActiveJobs, pipeline progress, and audit progress are checked.
   - Evidence: `src/mediapipeline/core/processes/guard_facade.py:62-103`.

20. ActiveJobs uncertainty must fail closed.
   - If ActiveJobs state cannot be verified, close-readiness reports active work rather than assuming idle.
   - Evidence: `src/mediapipeline/core/processes/guard_facade.py:150-168`.

21. Queue source scan duplicate requests must observe the active scan rather than start a second scan.
   - Evidence: `src/mediapipeline/core/queue/service.py:166-243`.

## Command Journal Invariants

22. Mutating command results should be journaled with bounded request evidence.
   - Command result payloads and validation failures are summarized and persisted.
   - Evidence: `src/mediapipeline/desktop/api/handler.py:96-113` and `src/mediapipeline/desktop/api/handler.py:139-153`.

23. Journal entries must redact secrets and bound evidence.
   - Sensitive keys and network secret text are redacted; request/data evidence is bounded.
   - Evidence: `src/mediapipeline/desktop/api/command_journal_policy.py:17-28` and `src/mediapipeline/desktop/api/command_journal_policy.py:90-110`.
