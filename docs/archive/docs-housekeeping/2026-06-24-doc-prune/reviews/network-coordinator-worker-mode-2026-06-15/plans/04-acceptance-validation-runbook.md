# Plan 04 - Acceptance Validation Runbook

Date: 2026-06-15

## Goal

Define the validation required after implementing Plans 01-03. This runbook is
the minimum acceptance gate for the remaining Network Worker/Coordinator
remediation.

## Pre-Validation Checks

1. Confirm the implementation created or updated one unreleased change packet.
2. Confirm every edited source/test/doc/generated-summary path is listed in the
   packet.
3. Confirm no unrelated dirty work was reverted or absorbed.
4. Restart any already-running app/API process before manual lifecycle checks.
5. Use the bundled Python runtime:

```powershell
apps/desktop/runtime/Python/python.exe
```

## Targeted Python Validation

Run from repository root:

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
apps/desktop/runtime/Python/python.exe -m unittest `
  tests.python.desktop.test_application_facade_process_launch `
  tests.python.desktop.test_application_facade_network `
  tests.python.desktop.test_network_lifecycle_fixes `
  tests.python.desktop.test_network_worker_runtime `
  tests.python.desktop.test_network_worker_state `
  tests.python.desktop.test_network_crash_recovery `
  tests.python.desktop.test_network_workflow `
  tests.python.desktop.test_network_protocol_runtime `
  tests.python.desktop.test_network_security `
  tests.python.desktop.test_network_drift_descriptor `
  tests.python.desktop.test_watch_folder_manager `
  tests.python.desktop.test_api_command_contracts `
  tests.python.desktop.test_api_contract_payload `
  tests.python.desktop.test_tauri_shell_scaffold `
  tests.webview.test_webview_network_read_only_boundary
```

Expected result: all tests pass.

## Browser/WebView Validation

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
apps/desktop/runtime/Python/python.exe -m pytest tests/webview/test_webview_browser_network_smoke.py -q
powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\scripts\smoke\Test-WebViewBrowserNetworkSmoke.ps1
```

Expected result: pytest reports one passing smoke, and the PowerShell wrapper
reports `OK`.

## Focused Negative Checks

Add or confirm tests for these cases:

- Remote active coordinator claims appear in stop dry-run evidence.
- Confirmed coordinator stop with remote active claims does not close heartbeat
  and done/reporting routes.
- Worker polling startup failure leaves no runtime entry.
- Coordinator startup failure after dispatcher construction performs cleanup.
- Unreadable `worker_state.json` blocks claims and is not deleted.
- Present wrong-type integer fields are rejected.
- Worker local mirror logs redact token assignments and URL secrets.
- WebView stop copy describes cooperative stop.

## Optional Manual Lifecycle Check

This check uses fakes or temporary state only unless the operator explicitly
requests real media validation.

1. Start a coordinator against temporary app state with an in-flight registry
   containing one active remote worker claim.
2. Run coordinator stop dry-run and confirm:
   - `active_work.active_job_count > 0`;
   - remote claim evidence is present;
   - stop posture is `review`, not clean.
3. Run confirmed coordinator stop and confirm:
   - new claims are disabled;
   - heartbeat and done/reporting routes remain available;
   - runtime entry remains until active count reaches zero.
4. Mark the remote claim terminal and confirm final coordinator shutdown
   completes and runtime entry is removed.

Document whether this check used real media. Real-media validation is not
required for these plans unless implementation touches media policy, FFmpeg,
subtitle/audio, publish/drain, source/scratch/output movement, or cleanup.

## Generated Summaries

After source/test/doc edits, refresh summaries for touched files:

```powershell
apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths <touched paths>
```

Record generated summary paths in the change packet.

## Change-Control Validation

```powershell
apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

Expected result: validation passes. The final response must report any unrelated
uncovered dirty files if the validator reports them.

## Final Acceptance Criteria

- All targeted and browser validation commands pass.
- Change-control validation passes with strict worktree coverage.
- The implementation report lists fixed finding IDs, files changed, tests run,
  change packet ID, and uncovered unrelated dirty files.
- No frontend or Tauri code owns backend mutation policy.
- No new local launch fallback exists in Network modes.
