# Browser Smoke Prerequisites Checklist

Status: operator/testing reference only. This is not an implementation backlog or daily-driver promotion checklist.

Use this checklist when browser-backed smokes skip unexpectedly, fail with connection errors, or produce misleading results. Work through the sections in order.

For full coverage and failure interpretation, see `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`.

---

## When Not To Run Browser Smokes

- When doing docs-only changes — the release self-test with `-SkipEndToEndSmoke` is sufficient.
- When Node.js is not on PATH — fix the PATH issue first. A direct module may report a skip, but canonical wrappers fail prerequisite skips by default.
- In headless CI environments with no Chrome/Edge installation — use browser-free smokes or explicitly invoke a wrapper with `-AllowSkippedTests` for a non-gating environmental result. A skip is not browser evidence.
- When you want to test only backend API shapes, use `test_api_read_payloads_policy.py` and `test_api_command_results_policy.py` instead.

---

## Checklist 1: Node.js

Node.js is required for both browser-backed and non-browser smokes.

```powershell
node --version
```

Expected: `v18.x.x` or later. Node 18+ required for global `WebSocket` in scope.

If not found:
- Install Node.js from the official site or a package manager.
- Ensure `node` is on the system or user PATH.
- Reopen the PowerShell terminal after install.

---

## Checklist 2: Chrome or Edge

Browser smokes use Chrome DevTools Protocol (CDP). No Playwright or Puppeteer install is needed.

```powershell
# Chrome typical paths
Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe"
Test-Path "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

# Edge typical paths
Test-Path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
Test-Path "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
```

If none return `True`:
- Install Chrome or Edge from the official source.
- If on a locked machine, check whether Chrome/Edge is installed to a non-standard path.
- If a browser cannot be installed, use the non-browser smokes for their documented scope. They do not prove actual browser rendering, CDP interaction, focus behavior, or layout.

---

## Checklist 3: Bundled Python

The `ops/scripts/smoke/` wrapper scripts use the bundled Python automatically. If running `python -m unittest` directly, confirm the bundled runtime path:

```powershell
$py = "apps\desktop\runtime\Python\python.exe"
Test-Path $py
& $py --version
```

Expected: `Python 3.x.x`. If the bundled Python is missing:
- Check whether the DesktopApp Runtime folder exists.
- If the workspace is a partial clone or missing the bundled runtime, run `ops\scripts\dev\verify-env.bat` to identify what is missing.

---

## Checklist 4: Local API Startup

Browser smokes start a temporary local API process. If the API fails to start, the CDP test cannot connect.

To diagnose manually:

```powershell
$py = "apps\desktop\runtime\Python\python.exe"
& $py -m mediapipeline.desktop.local_api_main --help
```

If this fails with `ModuleNotFoundError`:
- Confirm `src\mediapipeline\desktop\` exists and contains `__init__.py`.
- Confirm the working directory is the bundle root when running the command.

If the local API starts but the smoke fails with `ConnectionRefusedError`:
- Another process may be using the same port range. The smoke picks a random high port; collisions are rare but possible. Retry.
- If consistently failing, check firewall rules blocking loopback connections on high ports.

---

## Checklist 5: Bootstrap Token Auth

All command routes and most read routes require an `Authorization: Bearer` or `X-MediaPipeline-Token` header. The smoke generates the token automatically and injects it into the browser CDP runner. If you see `401 Unauthorized` errors:
- Do not run the smoke from a manual `curl` or browser tab — the smoke manages token generation internally.
- If modifying the auth layer or token format, recheck `test_backend_bootstrap.py` unit tests first.

---

## Checklist 6: CDP Connection

The browser smoke launches Chrome/Edge with `--remote-debugging-port` and connects via WebSocket. If `ConnectionRefusedError` or `TimeoutError` appears during CDP setup:

1. Check whether another Chrome instance is already running with debugging enabled on the same port. Close it.
2. Check whether antivirus or security software is blocking the loopback WebSocket connection.
3. The smoke uses a timeout for the initial connection — on slow machines, increase the timeout in the test or allow more time before retrying.

---

## Checklist 7: Smoke Skip vs Smoke Fail

| Invocation/result | Outcome | Meaning |
|---|---|---|
| Canonical wrapper exits 0 with `OK` | Pass | Browser assertions all passed |
| Direct Python module reports `s`, `skipped`, or `SkipTest` | Skip | Prerequisite absent; no browser proof |
| Canonical wrapper, default, sees prerequisite skip | Gating failure | Wrapper converts the skip to nonzero; install/fix prerequisite |
| Canonical wrapper with explicit `-AllowSkippedTests` reports skip | Non-gating skip | Record the environmental reason; do not count as a pass |
| Nonzero with `FAIL` | Test failure | An assertion failed — read the traceback |
| Nonzero with `ERROR` | Runtime error | The smoke crashed before assertions — read the traceback |

Canonical wrappers fail prerequisite skips by default. `-AllowSkippedTests` is an explicit exception for environmental evidence only. Record every skip in `docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`.

---

## Checklist 8: Non-Mutation Boundary Verification

Run browser smokes only through their generated disposable roots and temporary local API instances. Do not point a browser smoke at live/operator roots merely to verify that it “does not mutate.”

After a pass, verify the smoke's declared temporary mutations and fixture guards:

- Source-like media/subtitle/sidecar/manifest fixtures covered by the SHA-256/size guard are unchanged.
- Any allowed config, app-state, queue, command-journal, lifecycle archive, completed-manifest, or sidecar writes occurred only under the disposable root named by the smoke.
- No pending publish drain, rename apply/undo, or real FFmpeg/remux/encode ran unless the smoke catalog explicitly adds and validates that behavior.
- Prose/visual screenshots and manifests exist only in the disposable evidence directory.

A prerequisite skip ran no scenario assertions and therefore supplies no non-mutation proof. Compare observed fixture changes with `docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`; any undeclared write is a failure.

---

## Checklist 9: Console Error Capture

The browser-backed smokes capture browser console errors and include them in failure output. If a smoke passes but you see unexpected console errors in the output:
- Copy the errors to your smoke result log (`docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`).
- Check whether the errors relate to a resource that failed to load (JS asset, API endpoint, CORS).
- A pass with console errors may indicate a non-critical warning in the JS that did not break the tested assertion, but is worth reviewing.

---

## Quick Diagnostic Sequence

```powershell
# 1. Node available?
node --version

# 2. Chrome available?
Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe"

# 3. Bundled Python available?
Test-Path "apps\desktop\runtime\Python\python.exe"

# 4. Local API importable?
$py = "apps\desktop\runtime\Python\python.exe"
& $py -m mediapipeline.desktop.local_api_main --help

# 5. Run one non-browser smoke first to confirm JS eval works
.\ops/scripts/smoke\Test-WebViewRowDetailSmoke.ps1

# 6. Run one browser smoke
.\ops/scripts/smoke\Test-WebViewBrowserHighRiskSmoke.ps1
```

---

## See Also

- Full browser smoke runbook: `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- Smoke catalog: `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- Smoke result template: `docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`
- Validation ladder: `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- PowerShell host expectations: `docs/operator/POWERSHELL_HOST_EXPECTATIONS.md`

---

## Current Inventory Note — 2026-07-13

The canonical browser suite has 24 wrappers and 26 Python modules under `tests\webview\`. The metrics-degraded-state and Settings builder-flush modules are direct-only. Use `Get-ChildItem tests\webview -Filter "test_webview_browser*.py"` for discovery.
