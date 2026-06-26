# Validation Plan

This plan separates fast local validation from release-grade active-work validation.

## Fast Local Validation

Run after remediation or before release candidate handoff:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\apps\desktop\runtime\Python\python.exe -m unittest `
  tests.python.desktop.test_api_command_journal_policy `
  tests.python.desktop.test_api_command_contracts `
  tests.python.desktop.test_api_command_results_policy `
  tests.python.desktop.test_api_read_payloads_policy `
  tests.python.desktop.test_facade_process_guard_policy `
  tests.python.desktop.test_application_facade_close_readiness `
  tests.python.desktop.test_application_facade_process_launch `
  tests.python.desktop.test_local_api_lifecycle_contract_smoke `
  tests.webview.test_webview_frontend_mutation_boundary `
  tests.python.desktop.test_tauri_shell_scaffold `
  tests.python.desktop.test_tauri_pg1_close_adversarial_scaffold `
  -q
```

Expected result:

- all tests pass
- any existing unrelated dirty-worktree failure is documented separately

## Finding-Specific Validation

### CJ-001

Add and run a route-exception journal regression test:

1. Register or monkeypatch a journaled command route to raise after validation.
2. POST a valid request.
3. Assert HTTP status 500 with sanitized error response.
4. Fetch `/api/commands`.
5. Assert a failed command-result row exists with path and error id.
6. Assert request evidence is bounded and redacted.
7. Repeat for a secret-transfer route and assert no secret request body is journaled.

### CJ-002

Add and run persistence-degradation tests:

1. Make the JSON journal path unwritable or inject a failing save dependency.
2. Record a command result.
3. Assert the system reports degraded persistence through the selected remediation surface.
4. Restore persistence.
5. Assert recovery is reported.
6. Repeat with SQLite mirror failure if mirror status is exposed.

### CH-001

Add and run WebView command history dedupe tests:

1. Append two identical local failure rows with distinct request ids or timestamps.
2. Assert both attempts remain visible.
3. Add a matching backend journal row for one request.
4. Assert only the matching local row is replaced.
5. Assert source labels remain correct.

### VAL-001

Add and run live Tauri active-work close validation:

1. Start a temp backend and Tauri shell.
2. Start a long-running encode/process fixture.
3. Attempt normal close.
4. Assert safe close is blocked or confirmation is required.
5. Cancel confirmation.
6. Assert the backend and child process are still alive.
7. Confirm force close.
8. Assert `force_active_work_shutdown: true` reaches the backend.
9. Assert cleanup or process-tree termination occurs.

## Manual Release Validation

Before release, perform a manual smoke run using real user workflows:

1. Start a pipeline encode.
2. Open Close Readiness and verify active-work blockers are visible.
3. Attempt WebView handoff and verify it stays disabled while unsafe.
4. Attempt Tauri window close and verify confirmation behavior.
5. Cancel the prompt and verify the encode remains active.
6. Trigger confirmed force only in a disposable fixture and verify cleanup.
7. Trigger a failing command and verify Command History shows durable failed evidence.
8. Restart the backend and verify persisted command history reflects the expected bounded entries.

## Change Control Validation

Run the repository change-control validator before final handoff:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

Expected result:

- every file changed by this review is covered by the change packet
- unrelated preexisting dirty files, if any, are reported separately and not attributed to this review
