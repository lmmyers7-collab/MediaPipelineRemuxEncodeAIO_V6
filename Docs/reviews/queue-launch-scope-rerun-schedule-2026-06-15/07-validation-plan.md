# Validation Plan

This plan covers validation for the current review evidence and for the proposed remediations.

## Current Review Validation

Completed targeted validation:

- Process launch, single-file launch-plan pass-through, schedule gates, duplicate launch lock, and process controls: 33 Python tests, OK.
- Queue source path policy, priority, dry-run, snapshots, and facade queue behavior: 37 Python tests, OK.
- Schedule facade/watcher, kill, ActiveJobs, spawn runner, command journal policy, and core contracts: 66 Python tests, OK.
- Audit rerun CSV, report export, and API contract payloads: 38 Python tests, OK.

Total: 174 targeted Python tests, OK after setting `PYTHONPATH=src`.

Not run:

- Full repository test suite.
- PowerShell end-to-end smoke tests.
- Browser/WebView E2E.
- Real media processing or live CSV rerun.

## Validation for Finding 1 - Single-File Source-Root Constraint

Automated tests:

1. API/facade rejects `single_file` outside configured roots.
2. API/facade rejects relative `single_file`.
3. API/facade rejects missing `single_file`.
4. API/facade rejects directory `single_file`.
5. API/facade accepts file under `SourceMovies`.
6. API/facade accepts file under `SourceTV`.
7. Backend preflight reports matched source root and media kind for accepted single-file.
8. Backend preflight blocks outside-root single-file.
9. Command journal records blocked single-file request with bounded evidence.
10. Existing queue launch tests still pass and remain unaffected.

Manual smoke:

- Enter an outside-root path in the single-file field and verify Start is blocked with configured-root language.
- Enter a valid movie-root file and verify preflight shows movie root evidence.
- Enter a valid TV-root file and verify preflight shows TV root evidence.

Success criteria:

- No outside-root existing local file can reach `MediaPipeline.ps1 -SingleFile`.

## Validation for Finding 2 - CSV Rerun Dry-Run Evidence

Automated tests:

1. `collectRerunStartRequest()` supports `dry_run: true`.
2. Dry-run button posts `/api/rerun/start` with `dry_run: true`.
3. Live button posts `dry_run: false` only after explicit confirmation.
4. Rerun preflight displays CSV path, dry-run/live mode, and safe copy/keep/park policy.
5. Dry-run result rendering displays manifest path and `dry_run_complete`.
6. Dry-run result rendering displays planned, failed, duplicate-output, and unsafe-policy counts when available.
7. Command journal records dry-run and live rerun distinctly.
8. Backend rerun mode validation still rejects unsafe modes.

PowerShell smoke:

- Run the existing CSV rerun dry-run smoke from `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` in an isolated fixture.
- Verify manifest status is `dry_run_complete`.
- Verify no staging/nested pipeline execution happens during dry-run.

Manual smoke:

- Select a CSV path, run Preview CSV Rerun, and inspect manifest evidence.
- Start live rerun only after dry-run evidence is displayed.
- Confirm command history shows both events distinctly.

Success criteria:

- Operators can see dry-run evidence before live CSV rerun.
- Live rerun cannot be mistaken for dry-run.

## Validation for Finding 3 - Force Stop Scope

Automated tests:

Option A, scoped model:

- Pipeline Force Stop passes `job_kinds={"pipeline"}`.
- Pipeline Force Stop does not kill audit/rerun processes.
- Emergency Stop All kills pipeline/audit/rerun processes.
- Command journal records requested and actual scope.

Option B, broad model:

- Existing broad kill behavior remains covered.
- UI/copy tests assert wording includes pipeline, audit, and CSV rerun processes.
- Command result includes requested broad scope and actual killed process evidence.
- Command journal records requested and actual scope.

Manual smoke:

- Start fixture processes for pipeline, audit, and rerun in a controlled test environment.
- Trigger the relevant stop control.
- Verify killed process set matches the UI label and journal evidence.

Success criteria:

- There is no mismatch between operator wording, backend kill scope, and journaled evidence.

## Regression Gate After Remediation

Run at minimum:

```powershell
$env:PYTHONPATH=(Resolve-Path '.\src').Path
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_process_launch tests.python.desktop.test_service_process_launch_plans tests.python.desktop.test_application_facade_process_control -q
```

```powershell
$env:PYTHONPATH=(Resolve-Path '.\src').Path
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_queue_source_path_policy tests.python.desktop.test_service_queue_priority tests.python.desktop.test_service_queue_dry_run tests.python.desktop.test_service_queue_snapshot tests.python.desktop.test_application_facade_queue -q
```

```powershell
$env:PYTHONPATH=(Resolve-Path '.\src').Path
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_schedule tests.python.desktop.test_schedule_stop_watcher tests.python.desktop.test_service_process_kill tests.python.desktop.test_service_process_active_jobs tests.python.desktop.test_service_process_spawn_runner tests.python.desktop.test_api_command_journal_policy tests.python.desktop.test_application_facade_core_contracts -q
```

```powershell
$env:PYTHONPATH=(Resolve-Path '.\src').Path
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_service_audit_rerun_csv tests.python.desktop.test_application_facade_reports tests.python.desktop.test_api_contract_payload -q
```

Also run any new remediation-specific tests and the relevant PowerShell smoke for CSV rerun dry-run before release.
