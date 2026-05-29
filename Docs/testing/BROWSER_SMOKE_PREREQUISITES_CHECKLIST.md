# Browser Smoke Prerequisites Checklist

Status: operator/testing reference only. This is not an implementation backlog or daily-driver promotion checklist.

Use this checklist when browser-backed smokes skip unexpectedly, fail with connection errors, or produce misleading results. Work through the sections in order.

For full coverage and failure interpretation, see `Docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`.

---

## When Not To Run Browser Smokes

- When doing docs-only changes — the release self-test with `-SkipEndToEndSmoke` is sufficient.
- When Node.js is not on PATH — fix the PATH issue first; the smoke will skip cleanly, but a skip is not a pass.
- In headless CI environments with no Chrome/Edge installation — browser smokes skip cleanly and are designed for this. Non-browser smokes are the CI-suitable alternative.
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
- If a browser cannot be installed, use the non-browser smokes instead — they do not require a browser and cover the same JS behavior with mocked DOM state.

---

## Checklist 3: Bundled Python

The `SmokeTests/` wrapper scripts use the bundled Python automatically. If running `python -m unittest` directly, confirm the bundled runtime path:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
Test-Path $py
& $py --version
```

Expected: `Python 3.x.x`. If the bundled Python is missing:
- Check whether the DesktopApp Runtime folder exists.
- If the workspace is a partial clone or missing the bundled runtime, run `scripts\verify-env.bat` to identify what is missing.

---

## Checklist 4: Local API Startup

Browser smokes start a temporary local API process. If the API fails to start, the CDP test cannot connect.

To diagnose manually:

```powershell
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m mediapipeline_desktop_app.local_api_main --help
```

If this fails with `ModuleNotFoundError`:
- Confirm `DesktopApp\mediapipeline_desktop_app\` exists and contains `__init__.py`.
- Confirm the working directory is the bundle root when running the command.

If the local API starts but the smoke fails with `ConnectionRefusedError`:
- Another process may be using the same port range. The smoke picks a random high port; collisions are rare but possible. Retry.
- If consistently failing, check firewall rules blocking loopback connections on high ports.

---

## Checklist 5: Bootstrap Token Auth

All command routes and most read routes require a `X-Desktop-Token` header. The smoke generates the token automatically and injects it into the browser CDP runner. If you see `401 Unauthorized` errors:
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

| Exit code | Outcome | Meaning |
|---|---|---|
| 0 with `OK` | Pass | Test assertions all passed |
| 0 with `s` or `skipped` | Skip | Expected skip (no browser, no Node) — not a failure |
| Nonzero with `FAIL` | Test failure | An assertion failed — read the traceback |
| Nonzero with `ERROR` | Runtime error | The smoke crashed before assertions — read the traceback |

Skips are not failures. A skip means the environment prerequisites were not met and the test exited cleanly without testing anything. Record skips in your smoke result log (`Docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`).

---

## Checklist 8: Non-Mutation Boundary Verification

After a pass or skip, confirm the smoke did not mutate state:

- No pipeline process was started (no new `State\ActiveJobs\` entries).
- No settings were written (live config PSD1 modified time unchanged).
- No files were renamed (check source folder modified time if concerned).
- No pending publish was drained (no new drain summary or manifest changes).

If unexpected state changes appear after a smoke run, check the smoke's known mutation boundary in `Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md` and compare against what you observed.

---

## Checklist 9: Console Error Capture

The browser-backed smokes capture browser console errors and include them in failure output. If a smoke passes but you see unexpected console errors in the output:
- Copy the errors to your smoke result log (`Docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`).
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
Test-Path "DesktopApp\Runtime\Python\python.exe"

# 4. Local API importable?
$py = "DesktopApp\Runtime\Python\python.exe"
& $py -m mediapipeline_desktop_app.local_api_main --help

# 5. Run one non-browser smoke first to confirm JS eval works
.\SmokeTests\Test-WebViewRowDetailSmoke.ps1

# 6. Run one browser smoke
.\SmokeTests\Test-WebViewBrowserHighRiskSmoke.ps1
```

---

## See Also

- Full browser smoke runbook: `Docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- Smoke catalog: `Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- Smoke result template: `Docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`
- Validation ladder: `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- PowerShell host expectations: `Docs/operator/POWERSHELL_HOST_EXPECTATIONS.md`

