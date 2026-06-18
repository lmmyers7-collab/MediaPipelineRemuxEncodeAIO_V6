# Test Coverage Review

## Validation Performed During This Review

Initial direct `unittest` invocation without `PYTHONPATH` failed at import time with `ModuleNotFoundError: No module named 'mediapipeline'`. The targeted suites were rerun with `PYTHONPATH=src`.

Commands rerun successfully:

```powershell
$env:PYTHONPATH=(Resolve-Path '.\src').Path
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_process_launch tests.python.desktop.test_service_process_launch_plans tests.python.desktop.test_application_facade_process_control -q
```

Result: 33 tests, OK.

```powershell
$env:PYTHONPATH=(Resolve-Path '.\src').Path
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_queue_source_path_policy tests.python.desktop.test_service_queue_priority tests.python.desktop.test_service_queue_dry_run tests.python.desktop.test_service_queue_snapshot tests.python.desktop.test_application_facade_queue -q
```

Result: 37 tests, OK.

```powershell
$env:PYTHONPATH=(Resolve-Path '.\src').Path
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_schedule tests.python.desktop.test_schedule_stop_watcher tests.python.desktop.test_service_process_kill tests.python.desktop.test_service_process_active_jobs tests.python.desktop.test_service_process_spawn_runner tests.python.desktop.test_api_command_journal_policy tests.python.desktop.test_application_facade_core_contracts -q
```

Result: 66 tests, OK.

```powershell
$env:PYTHONPATH=(Resolve-Path '.\src').Path
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_service_audit_rerun_csv tests.python.desktop.test_application_facade_reports tests.python.desktop.test_api_contract_payload -q
```

Result: 38 tests, OK.

Total targeted Python validation: 174 tests, OK after setting `PYTHONPATH=src`.

## Coverage Strengths

## Queue Launch Scope

Covered:

- Queue preview and snapshot behavior.
- Queue dry-run command construction and evidence shape.
- Queue priority manifest operations.
- Queue source path validation for priority writes.
- Queue API/facade behavior.

Important covered boundary:

- Priority/source path writes reject paths outside configured source roots.

Gap:

- No test asserts that normal pipeline start cannot consume selected Queue rows or filters, because the request shape deliberately does not include those fields. Existing UI source wording covers this boundary, but a contract test could lock it down.

## Single-File Launch

Covered:

- Single-file request pass-through into pipeline launch plan.
- `-SingleFile` argument placement.
- Start/preflight request handling with `single_file`.

Gap:

- There is no rejection test for `single_file` outside configured source roots because the current implementation allows it.
- There is no preflight test requiring matched source root/media kind evidence before single-file launch.

Risk implication:

- Current tests preserve the unsafe pass-through behavior identified in Finding 1.

## CSV Rerun

Covered:

- CSV rerun export and service-level CSV handling.
- API contract default payload includes safe copy/keep/park modes and current `dry_run: false`.
- Rerun process launch rejects invalid modes and missing CSV path.
- Backend PowerShell smoke coverage exists in `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` for CSV rerun dry-run manifest behavior, although that PowerShell smoke was not executed in this review.

Gap:

- WebView does not have a dry-run control to test.
- No UI test proves an operator sees `dry_run_complete` manifest evidence before live rerun.
- No test binds a live CSV rerun request to a previously reviewed dry-run manifest or CSV fingerprint.

Risk implication:

- Current tests encode live-start default behavior rather than an evidence-first CSV rerun flow.

## Schedule Start/Stop

Covered:

- Schedule gate blocks outside-window starts.
- `run_once` override resolves to once.
- `ignore` override is represented as an explicit bypass.
- Continuous schedule-stop watcher state is exposed.
- Watcher writes Stop After Current at deadline.
- Schedule save/preview state is validated by facade tests.

Gap:

- No major gap found for the requested scheduled launch conditions. Continue adding tests if the watcher is moved to a different process boundary.

## Stop After Current and Force Stop

Covered:

- Process control lock blocks duplicate pause/stop/rescan.
- Stop writes a flag rather than killing.
- Related process finder can filter by job kind.
- Broad kill path can terminate related audit/rerun/pipeline PowerShell processes.

Gap:

- No operator-facing test asserts Force Stop label/scope wording.
- No API test records requested kill scope and actual killed process kinds in command history.

Risk implication:

- Tests verify broad kill behavior, which supports Finding 3. They do not verify that the UI communicates that breadth.

## Duplicate Process Prevention

Covered:

- Launch lock blocks duplicate launch commands.
- Active related process blocks duplicate launch.
- Active audit/rerun/pipeline job kinds block incompatible starts.
- Queue source scan duplicate requests observe an active scan.
- ActiveJobs records block close and fail closed when verification is unavailable.

Gap:

- Combined failure-mode tests could be stronger for cases where related process scan is unavailable, ActiveJobs is stale, and progress has `StopRequested=True`.

Risk implication:

- No high-risk duplicate start path was found in the reviewed code, but layered-state failure modes should stay covered.

## ActiveJobs and Spawn Runner

Covered:

- ActiveJobs launch records.
- Active PID/blocker handling.
- Completion and heartbeat behavior.
- Spawn runner process registration and cleanup.

Gap:

- No end-to-end WebView/browser run was performed in this review. Coverage is service/API-level.

## Command Journaling

Covered:

- Command history persistence and newest-first behavior.
- Command summary field preservation.
- Secret redaction.
- Validation failure journaling.
- Command request evidence for launch/rerun commands.

Gap:

- Finding 1 remediation should add journal coverage for rejected `single_file`.
- Finding 2 remediation should add journal coverage for CSV dry-run and live rerun transitions.
- Finding 3 remediation should add journal coverage for kill scope and killed job kinds.

## Tests Not Run

- Full repository test suite.
- PowerShell end-to-end smoke suite.
- Playwright/WebView browser tests.
- Real media processing, real queue launch, or real live CSV rerun.

Reason:

- The task requested code review artifacts and no code edits. The selected validation was targeted and non-mutating.
