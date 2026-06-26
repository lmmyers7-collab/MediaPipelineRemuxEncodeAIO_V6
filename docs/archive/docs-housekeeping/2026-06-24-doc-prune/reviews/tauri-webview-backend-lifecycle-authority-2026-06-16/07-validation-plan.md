# Validation Plan

This plan validates the review packet and the authority-boundary claims. It includes commands suitable for the current repo. Commands should be run from the repo root.

## Static Boundary Checks

Run:

```powershell
rg "__TAURI__|invoke|@tauri|tauri\.fs|tauri\.shell|writeFile|readTextFile|removeFile|renameFile|Command\." apps/desktop/webview/static/assets -g "*.js"
```

Expected:

- Only read-only lifecycle bridge or benign references appear.
- No WebView filesystem/shell mutation APIs are present.

Run:

```powershell
rg "apiPost\\(|fetch\\(" apps/desktop/webview/static/assets -g "*.js"
```

Expected:

- Mutation/process/settings/publish/rename/network commands are posted through Local API helpers.
- No direct filesystem paths or Tauri command invocations are used for mutation.

Run:

```powershell
Get-Content apps/desktop/tauri/src-tauri/capabilities/default.json
```

Expected:

- No filesystem, shell, or dialog mutation permissions are granted to the WebView.

## Focused Unit And Browser-Smoke Tests

Run:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_tauri_shell_scaffold tests.python.desktop.test_application_facade_local_api tests.python.desktop.test_api_command_contracts tests.python.desktop.test_network_lifecycle_fixes tests.webview.test_webview_network_read_only_boundary tests.webview.test_webview_browser_lifecycle_smoke tests.webview.test_webview_browser_network_smoke -q
```

Expected:

- Existing lifecycle, contract, network, and WebView boundary tests pass.
- Note: passing this command does not close F-01 or F-02 because current tests encode or permit the reviewed risks.

If the combined command is too slow or environment-sensitive, split it:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_tauri_shell_scaffold tests.python.desktop.test_application_facade_local_api tests.python.desktop.test_api_command_contracts -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_lifecycle_fixes -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_network_read_only_boundary tests.webview.test_webview_browser_lifecycle_smoke tests.webview.test_webview_browser_network_smoke -q
```

## Tauri Static Build Check

Run:

```powershell
npm --prefix apps/desktop/tauri run check
```

Expected:

- Tauri/Rust checks pass for lifecycle and contract code.

## Review Artifact Validation

Run:

```powershell
.\apps\desktop\runtime\Python\python.exe -m json.tool ops\release\changes\unreleased\MP-CHANGE-2026-0616-002.json
```

Expected:

- Change packet is valid JSON.

Run:

```powershell
.\apps\desktop\runtime\Python\python.exe ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths docs\reviews\tauri-webview-backend-lifecycle-authority-2026-06-16\00-review-scope.md docs\reviews\tauri-webview-backend-lifecycle-authority-2026-06-16\01-code-map.md docs\reviews\tauri-webview-backend-lifecycle-authority-2026-06-16\02-invariants-and-boundaries.md docs\reviews\tauri-webview-backend-lifecycle-authority-2026-06-16\03-risk-review.md docs\reviews\tauri-webview-backend-lifecycle-authority-2026-06-16\04-test-coverage-review.md docs\reviews\tauri-webview-backend-lifecycle-authority-2026-06-16\05-findings.md docs\reviews\tauri-webview-backend-lifecycle-authority-2026-06-16\06-remediation-plan.md docs\reviews\tauri-webview-backend-lifecycle-authority-2026-06-16\07-validation-plan.md docs\reviews\tauri-webview-backend-lifecycle-authority-2026-06-16\08-final-review-summary.md ops\release\changes\unreleased\MP-CHANGE-2026-0616-002.json
```

Expected:

- Generated summaries are created or refreshed for the review packet and change packet.

Run:

```powershell
.\apps\desktop\runtime\Python\python.exe ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

Expected:

- Ideally passes for all touched files. In the current dirty worktree, unrelated pre-existing untracked/modified files may cause coverage failures. If so, record the exact failure and do not modify unrelated work.

## Remediation Validation Gates

After source remediation, add these gates before accepting fixes:

- Corrupt each safety-critical WebView fragment and assert Tauri does not open the normal shell.
- Simulate active coordinator/worker stop and assert `state_after.status` is not plain `stopped` while active work remains.
- Browser-render active-stop result and assert UI communicates active work preserved.
- Assert WebView token is not globally readable.
- Assert release builds cannot run debug automation.
- Assert all supported package targets enforce single-instance ownership.
