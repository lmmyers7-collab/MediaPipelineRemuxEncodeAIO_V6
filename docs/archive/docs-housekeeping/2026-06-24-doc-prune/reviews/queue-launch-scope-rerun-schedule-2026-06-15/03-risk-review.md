# Risk Review

## Executive Risk Summary

The main queue launch flow is deliberately backend-owned: Queue table filters and selected rows are advisory and not submitted. The backend queue preview is built from the live queue planner or a fresh `-EmitQueuePlan` dry run, and priority behavior is explicit. Duplicate launch protection, schedule gates, ActiveJobs, command journaling, and close-readiness are also well represented in code and tests.

The highest-risk gap is not the normal queued launch path. It is the separate `single_file` launch path. That path can process an arbitrary existing local file because API/facade/launch-plan code passes the operator-entered path through to `MediaPipeline.ps1 -SingleFile`, and the PowerShell entrypoint only checks that the path exists before processing.

## Queue Launch Scope

Verdict: mostly strong.

Evidence:

- `apps/desktop/webview/static/assets/launchView.scope.js:199-206` explicitly warns that visible Queue subsets, filters, and selected rows are not launch scope.
- `src/mediapipeline/core/queue/service.py:399-409` says queue preview mirrors the same rows and order the live queue phase planner would process.
- `src/mediapipeline/core/queue/dry_run.py:27` runs the pipeline in `-EmitQueuePlan` mode.
- `src/mediapipeline/core/queue/dry_run.py:48-68` reports runnable and filtered counts.

Risk:

- Normal launch intentionally ignores selected rows and filters. That is safe only because the UI repeatedly warns about it and backend start remains authoritative.
- Operators can still misunderstand scope if they expect row selection to constrain launch. The current UI mitigates this with explicit wording; no code change is required for queued launch scope based on this review.

## Which Files Can Launch

Verdict: one high-risk gap.

Launchable surfaces:

- Normal pipeline launch: backend queue plan from saved config and queue state.
- Validate/drain modes: pipeline entrypoint mode flags, not arbitrary row selection.
- Single-file launch: operator-provided path passed as `-SingleFile`.
- CSV rerun: CSV row sources become `csv_rerun` queue items after safety checks.
- Audit launch: audit script path, report root, and audit launch plan.

Single-file risk:

- `apps/desktop/webview/static/assets/launch/startRequest.js:20-33` collects free-text `single_file`.
- `src/mediapipeline/core/processes/pipeline_facade.py:124` passes it through.
- `src/mediapipeline/core/processes/launch_plans.py:65` appends `-SingleFile`.
- `ops/pipeline/entrypoints/MediaPipeline.ps1:594-629` checks path existence, resolves media kind, and processes the file.
- `ops/pipeline/engine/shared/path_helpers.ps1:216-287` falls back to `default_movie` for non-root matches.

Impact:

- An out-of-source-root file can be processed and published under default classification. This can process the wrong file and bypass the same configured-root assumptions enforced for priority/source-path writes.

## Selected-Vs-Filtered Scope

Verdict: clear boundary for queued launch.

The code makes Queue table filters and row selection read-only UI state. The start request has no fields for Queue table selected rows or filter state, and the launch scope module states this directly. The risk is mostly operator expectation, not hidden backend behavior.

Boundary:

- Normal pipeline start should continue not to accept selected-row or filter state unless a new explicit "launch selected" feature is designed with its own backend validation and dry-run evidence.

## Dry-Run Evidence

Verdict: mixed.

Strong:

- Queue dry-run evidence is strong and launch-adjacent. Queue preview can run `-EmitQueuePlan`, rejects stale snapshots, and reports runnable/filtered counts.
- CSV rerun backend dry-run exists and writes a manifest with `dry_run_complete`.

Weak:

- WebView CSV rerun hard-codes `dry_run: false` and has no visible dry-run action, despite backend dry-run support.
- This can mislead operators into thinking CSV rerun has the same visible dry-run evidence posture as Queue launch.

## Priority Behavior

Verdict: strong.

Evidence:

- Priority path updates are validated under configured source roots at `src/mediapipeline/desktop/api/queue_source_path_policy.py:69-81`.
- API priority writes call that validation at `src/mediapipeline/core/api/commands_queue_priority.py:138-140` and `src/mediapipeline/core/api/commands_queue_priority.py:174-176`.
- Hold entries are separated from runnable entries in `ops/pipeline/engine/queue/phase_plan.ps1:119-144`.

Operator boundary:

- High changes order.
- Normal is default.
- Low remains runnable, later.
- Hold is not runnable but can appear in display rows.

## Rerun CSV Interpretation

Verdict: backend interpretation is conservative, UI dry-run posture is weak.

Strong:

- Safe defaults are copy/keep/park.
- Unsafe row overrides are rejected before staging.
- Source identity evidence is checked.
- Duplicate planned outputs are detected.
- Dry-run exits before staging and nested pipeline launch.

Weak:

- WebView offers only "Start CSV Rerun" and sends a live request. The UI does not require or display dry-run manifest evidence before live rerun.

## Scheduled Launch Conditions

Verdict: strong.

Evidence:

- Schedule gate runs before process launch at `src/mediapipeline/core/processes/pipeline_facade.py:95-97`.
- Continuous scheduled launch is blocked if schedule enforcement is on and watcher ownership is unavailable at `src/mediapipeline/core/processes/schedule_policy.py:171-174`.
- Outside-window launch requires explicit `run_once` or `ignore` override at `src/mediapipeline/core/processes/schedule_policy.py:181-190`.
- The watcher writes Stop After Current at the schedule boundary.

Residual risk:

- `ignore` is intentionally allowed and is labeled high-review. This is a controlled override, not a bug.

## Stop After Current

Verdict: strong.

Stop writes a control flag and is described as allowing current work to finish. It does not terminate processes directly.

Evidence:

- `src/mediapipeline/core/processes/control_facade.py:135-140`.

## Force Stop

Verdict: behavior is defensible as emergency stop, but operator wording is under-scoped.

Evidence:

- `src/mediapipeline/core/processes/control_facade.py:148-156` calls `kill_related_pipeline_processes(resolved)` without `job_kinds`.
- `src/mediapipeline/core/processes/kill.py:105-113` includes pipeline, audit, and rerun script paths when `job_kinds` is absent.

Risk:

- The operator may believe Force Stop only targets active pipeline processes, while backend scope can include audit and rerun processes.

## Duplicate Process Prevention

Verdict: strong.

Evidence:

- Launch lock blocks duplicate launch commands.
- Control lock blocks duplicate pause/stop/rescan/kill commands.
- Related process detection catches existing pipeline/audit/rerun PowerShell processes.
- ActiveJobs records and close blockers add a durable process-state layer.
- Queue source scan duplicate requests observe the active scan rather than start another scan.

Residual risk:

- If related process checks, ActiveJobs, and progress state are all unavailable or stale, the system has fewer independent blockers. Tests cover the main fail-closed ActiveJobs behavior.

## Command Journaling

Verdict: strong.

Evidence:

- POST command handlers journal command result payloads and include request evidence for successful HTTP responses.
- Validation failures can be journaled.
- Request/data evidence is bounded and secrets are redacted.

Risk:

- New remediation for single-file rejection and CSV dry-run/live transitions should add explicit journal tests so operators can reconstruct why a launch was blocked or allowed.
