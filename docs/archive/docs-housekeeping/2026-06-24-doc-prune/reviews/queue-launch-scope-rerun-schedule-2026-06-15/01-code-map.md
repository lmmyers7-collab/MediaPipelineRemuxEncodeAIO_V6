# Code Map

This map traces the review surfaces from WebView controls through local API handlers, core facades, launch-plan builders, PowerShell entrypoints, and tests.

## Launch UI and Operator Scope

- `apps/desktop/webview/static/partials/page-launch.html`
  - Pipeline start controls, CSV rerun controls, launch status panes, and command buttons.
  - CSV rerun currently exposes CSV path, show-console, fixed copy/keep/park labels, and `Start CSV Rerun` at lines 344-363.
- `apps/desktop/webview/static/assets/launch/startRequest.js`
  - `collectPipelineStartRequest()` submits mode, sleep, schedule override, `show_config`, and optional `single_file` at lines 20-33.
  - `collectRerunStartRequest()` submits `csv_path`, hard-coded `dry_run: false`, copy/keep/park modes, and show-console at lines 44-52.
- `apps/desktop/webview/static/assets/launchView.scope.js`
  - Shows that selected Queue table state is advisory only. It says single file is an operator-provided backend request at line 174.
  - Warns not to treat visible Queue subsets as launch scope at lines 199-205.
  - States launch requests do not include Queue filters, selected rows, or visible-row subsets at lines 205-206.
- `apps/desktop/webview/static/assets/launch/commandButtons.js`
  - Owns start/control button labels, disabled state, in-flight guards, and confirmation copy for Stop/Force Stop.

## Local API and Command Routing

- `src/mediapipeline/desktop/api/handler.py`
  - POST routes validate body shape, execute command methods, and journal successful HTTP responses with request evidence at lines 96-113 and 139-153.
- `src/mediapipeline/desktop/api/handler_policy.py`
  - Decides whether route validation failures and result payloads should be journaled.
- `src/mediapipeline/desktop/api/command_journal.py`
  - Persists bounded command history newest-first and mirrors command summaries.
- `src/mediapipeline/desktop/api/command_journal_policy.py`
  - Redacts sensitive evidence terms, bounds nested data/request evidence, and preserves key fields at lines 17-28 and 90-110.
- `src/mediapipeline/core/api/commands_process.py`
  - API command handlers for process launch/control, file browsing, and preflight. File browsing validates selected file existence but pipeline start does not bind `single_file` to the browse route.
- `src/mediapipeline/core/api/commands_queue_priority.py`
  - Queue priority command handler validates each target path through `validate_queue_source_path()` before manifest writes at lines 138-140 and 174-176.

## Pipeline Launch

- `src/mediapipeline/core/processes/pipeline_facade.py`
  - `start_pipeline_process()` applies config identity block, schedule gate, process launch lock, active-work block, then service launch.
  - Passes `single_file=str(request.get("single_file") or "").strip() or None` through to the service at line 124.
- `src/mediapipeline/core/processes/launch_plans.py`
  - `build_pipeline_launch_plan()` appends `-SingleFile` when provided at line 65 and stores request metadata at lines 79-85.
  - `build_rerun_csv_launch_plan()` validates script and CSV path existence, builds `Invoke-RerunCsv.ps1`, and appends `-DryRun` when requested at lines 158-170.
- `ops/pipeline/entrypoints/MediaPipeline.ps1`
  - `-SingleFile` skips queue discovery and processes exactly one file.
  - Single-file mode checks only that the path exists at lines 594-604, resolves media kind at line 622, then calls `Invoke-MediaPipelineProcessFile` at line 629.
- `ops/pipeline/engine/shared/path_helpers.ps1`
  - `Resolve-SingleFileMediaKind()` matches configured movie/TV roots when possible, but falls back to `default_movie` with empty root at lines 216-287.

## Queue Preview, Dry Run, Source Scan, and Priority

- `src/mediapipeline/core/queue/service.py`
  - `build_queue_preview()` mirrors the live pipeline queue plan and can spawn `-EmitQueuePlan`; docstring says rows are exactly what `Invoke-MediaQueuePhasePlan` would process at lines 399-409.
  - `start_queue_source_scan()` accepts only scope `all`, rejects unsupported scopes, and returns duplicate observation when a scan is already running at lines 166-243.
- `src/mediapipeline/core/queue/dry_run.py`
  - Builds the dry-run queue command with `-EmitQueuePlan` at line 27.
  - Formats evidence as runnable plus filtered counts at lines 48-68.
- `src/mediapipeline/core/queue/dry_run_runner.py`
  - Runs queue dry-run with timeout, validates snapshot freshness, writes snapshot, and mirrors rows.
- `src/mediapipeline/core/queue/source_inventory.py`
  - Source inventory rows are explicitly non-launchable and read-only; backend queue curation remains authoritative.
- `src/mediapipeline/core/queue/priority_manifest.py`
  - Stores high/normal/low/hold manifest entries and resolves exact/deepest-parent matches.
- `src/mediapipeline/desktop/api/queue_source_path_policy.py`
  - Requires priority/source path updates to be absolute and under configured source roots at lines 69-81.
- `ops/pipeline/engine/queue/phase_plan.ps1`
  - Runnable entries include high, normal, and low. Hold entries are tracked separately and displayed but excluded from runnable processing at lines 26-47 and 119-144.

## CSV Rerun

- `src/mediapipeline/core/audit/rerun_export.py`
  - Exports safe copy/keep/park defaults and source identity evidence.
- `src/mediapipeline/core/audit/rerun_csv.py`
  - Defines CSV columns including `enabled`, `source_path`, source identity, source size/mtime, stage mode, original mode, return mode, and issue metadata.
- `src/mediapipeline/core/processes/rerun_policy.py`
  - Normalizes rerun CSV request fields and returns command success/failure payloads with `dry_run`, modes, pid, and log paths.
- `src/mediapipeline/core/processes/rerun_facade.py`
  - Requires CSV path and copy/keep/park modes, applies launch lock and active-work block, then starts rerun process.
- `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1`
  - Reads row fields at lines 484-491.
  - Rejects unsafe row-level policy overrides at lines 518-531.
  - Checks source identity/mtime/size at lines 548-550.
  - Writes queue items as `QueueSource 'csv_rerun'` at lines 587-594.
  - Writes a manifest with `dry_run` and mode evidence at lines 732-735.
  - If `-DryRun`, marks `dry_run_complete` and exits before staging/nested pipeline at lines 751-754.

## Schedule Start and Stop

- `src/mediapipeline/core/processes/schedule_policy.py`
  - Continuous mode is blocked when schedule enforcement is enabled and backend schedule-stop watcher is unavailable at lines 8-15 and 171-174.
  - Outside-window starts require explicit run-once or ignore override at lines 181-190.
  - Preflight describes watcher ownership and explicit ignore risk at lines 47-149.
- `src/mediapipeline/core/processes/pipeline_facade.py`
  - Applies the schedule gate before acquiring the process launch lock at lines 95-97.
  - Arms the schedule-stop watcher only after successful continuous launch when requested mode and actual mode are continuous and schedule enforcement applies.
- `src/mediapipeline/desktop/application/schedule_stop_watcher.py`
  - Arms watcher state for a launched PID/deadline and writes Stop After Current at the schedule boundary.
- `src/mediapipeline/core/schedule/facade.py`
  - Loads, previews, validates, and saves schedule state with confirmation and a save lock.

## Stop, Force Stop, and Duplicate Guards

- `src/mediapipeline/core/processes/control_facade.py`
  - Uses the process control lock for pause, stop, rescan, and kill.
  - Stop writes the stop flag at lines 135-140.
  - Kill calls `kill_related_pipeline_processes(resolved)` at lines 148-156.
- `src/mediapipeline/core/processes/kill.py`
  - When `job_kinds` is omitted, related needles include pipeline, audit, and rerun scripts at lines 105-113.
  - Finder and killer use those needles to terminate matching PowerShell processes.
- `src/mediapipeline/core/processes/guard_facade.py`
  - Launch lock blocks duplicate launch commands at lines 29-40.
  - Active-work checks include related process scan, schedule watcher state, ActiveJobs, fresh pipeline progress, and audit progress at lines 62-103.
  - ActiveJobs failures fail closed at lines 150-168.
- `src/mediapipeline/core/processes/active_jobs.py`
  - Writes launch records with command line, args, cwd, logs, job kind, status, PID, return code, and timestamps.
  - Blocks close when jobs are active or PID verification is unavailable.
- `src/mediapipeline/core/processes/spawn_runner.py`
  - Spawns hidden or visible process, writes ActiveJobs launch records, registers lifecycle state, starts heartbeat/completion watchers, and stops a process if readiness verification fails.

## Test Files Reviewed

- `tests/python/desktop/test_application_facade_process_launch.py`
- `tests/python/desktop/test_application_facade_process_control.py`
- `tests/python/desktop/test_application_facade_schedule.py`
- `tests/python/desktop/test_schedule_stop_watcher.py`
- `tests/python/desktop/test_service_process_launch_plans.py`
- `tests/python/desktop/test_service_process_spawn_runner.py`
- `tests/python/desktop/test_service_process_kill.py`
- `tests/python/desktop/test_service_process_active_jobs.py`
- `tests/python/desktop/test_queue_source_path_policy.py`
- `tests/python/desktop/test_service_queue_priority.py`
- `tests/python/desktop/test_service_queue_dry_run.py`
- `tests/python/desktop/test_service_queue_snapshot.py`
- `tests/python/desktop/test_application_facade_queue.py`
- `tests/python/desktop/test_api_command_journal_policy.py`
- `tests/python/desktop/test_application_facade_core_contracts.py`
- `tests/python/desktop/test_application_facade_local_api.py`
- `tests/python/desktop/test_api_contract_payload.py`
- `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1`
