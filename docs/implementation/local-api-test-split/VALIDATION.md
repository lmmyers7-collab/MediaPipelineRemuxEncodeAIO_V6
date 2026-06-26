# Validation Plan

Status: applies to every implementation phase

## Validation Philosophy

This split is a test-suite refactor. If only tests and documentation change,
real-media validation is not required. If product code changes, reclassify the
work under `docs/testing/VALIDATION_LADDER_RUNBOOK.md` and run the route,
WebView, or media validation rung appropriate to the product behavior touched.

Use the bundled Python runtime. Do not validate this project with system Python
unless the task explicitly requires it.

## Baseline Validation

Before moving tests:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Phase 1 Validation

After extracting shared support:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Phase 2 Validation

After each Web static target file, run the specific target module just created
or updated. Replace `<target_module>` with the module under migration, for
example `test_application_facade_web_static_completed`.

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.<target_module> -q
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
```

After Phase 2 completes:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_web_static*.py" -q
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Phase 3 Validation

After each Local API target file:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.<target_module> -q
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
```

Replace `<target_module>` with the specific target module being moved.

After Phase 3 completes:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_local_api*.py" -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Phase 4 Validation

After decomposing queue/rename contracts:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.test_application_facade_local_api_queue -q
& $py -m unittest tests.python.desktop.test_application_facade_local_api_rename -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_local_api*.py" -q
```

## Phase 5 Validation

After cleanup/docs/discovery:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_local_api*.py" -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_web_static*.py" -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

If strict worktree coverage is blocked by unrelated dirty files, record:

- normal `validate_changes` result;
- list of unrelated dirty files;
- reason strict worktree coverage was not feasible.

## Docs-Only Planning Validation

For edits to this planning pack only, run change-control validation during
drafting:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes
```

Before marking a docs-only planning packet complete, run the release self-test
required by Rung 0:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

## Evidence To Record

Every phase should record:

- exact commands;
- pass/fail result;
- baseline failures, if any;
- skipped commands and why;
- assertion migration ledger rows resolved in the phase;
- generated summary refresh result;
- change packet validation result.
