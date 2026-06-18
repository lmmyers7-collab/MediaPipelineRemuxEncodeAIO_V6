# Plan 03 - Auth Redaction And UI Contract Cleanup

Date: 2026-06-15

## Goal

Close the remaining redaction and WebView copy issues while preserving the
already-fixed auth, route metadata, join, and command-journal behavior.

## Findings Covered

- REM-NCW-07: worker local cluster-log mirror writes message text before
  coordinator-side redaction.
- REM-NCW-08: WebView stop tooltip still says stop may abort active worker work.
- REM-NCW-09: add focused tests so these regressions stay closed.

## Primary Files

- `src/mediapipeline/desktop/network/worker.py`
- `src/mediapipeline/core/network/url_policy.py`
- `apps/desktop/webview/static/assets/networkView.js`
- `tests/python/desktop/test_network_security.py`
- `tests/python/desktop/test_network_worker_runtime.py`
- `tests/webview/test_webview_network_read_only_boundary.py`
- `tests/webview/test_webview_browser_network_smoke.py`

## Implementation Steps

1. Redact worker local cluster-log mirror fields.
   - In `WorkerDispatcher.log_cluster_event()`, sanitize and redact before
     writing to the local Python logger.
   - Apply `redact_network_secret_text()` to `event`, `message`, `job_id`, and
     `source_path` display values.
   - Keep coordinator POST payload behavior unchanged; coordinator-side
     `cluster_log.py` remains the final formatter for cluster log files.

2. Add redaction regression tests.
   - Exercise local mirror logging with:
     - token-like assignments, for example `token=super-secret`;
     - URL query secrets;
     - URL fragments;
     - source paths containing query-like text.
   - Assert raw secrets do not appear in captured log output.

3. Correct WebView stop tooltip.
   - Replace the title text that says stop may abort active worker work.
   - Use cooperative wording:
     `stop polling/new claims; active work is preserved for done reporting`.
   - Do not add new frontend lifecycle behavior.

4. Add WebView fixture checks.
   - Assert Network lifecycle stop copy does not contain `abort active worker`.
   - Assert it contains cooperative stop or preserve-active-work language.
   - Keep browser smoke allowlist for exact `/api/ui-preferences`
     `mediapipeline-network-tab` sync.

## Regression Tests

Add or update:

- `test_worker_local_cluster_log_mirror_redacts_token_assignment`
- `test_worker_local_cluster_log_mirror_redacts_url_query_and_fragment`
- `test_network_lifecycle_stop_tooltip_describes_cooperative_stop`
- Existing browser smoke should continue to pass.

## Validation Commands

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_network_security tests.python.desktop.test_network_worker_runtime tests.webview.test_webview_network_read_only_boundary
apps/desktop/runtime/Python/python.exe -m pytest tests/webview/test_webview_browser_network_smoke.py -q
powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\scripts\smoke\Test-WebViewBrowserNetworkSmoke.ps1
```

Run the common acceptance validation in
`plans/04-acceptance-validation-runbook.md` after all plans are complete.

## Rollback Plan

Revert the worker local mirror redaction change, WebView copy change, and
focused tests. Confirm existing Network security and WebView smoke tests return
to their previous passing state.

## Acceptance Criteria

- Worker local logs do not expose raw tokens or URL query/fragment secrets.
- Coordinator cluster-log redaction remains unchanged and tested.
- WebView lifecycle copy accurately describes cooperative stop behavior.
- No frontend code gains mutation authority.
