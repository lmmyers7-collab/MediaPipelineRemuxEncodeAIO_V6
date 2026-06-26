# Browser Smoke Failure Triage Cheatsheet

Date: 2026-05-14

Quick reference for interpreting browser-backed WebView smoke failures. For the full runbook, see `docs\testing\BROWSER_SMOKE_TEST_RUNBOOK.md`.

---

## Skip Vs Fail Distinction

| Exit | Meaning | Action needed |
|---|---|---|
| Exit 0 + `SkipTest` message | Environment prerequisite missing | Install missing tool; not a code failure |
| Exit 0 + `ok` | Test passed | None |
| Non-zero exit + `FAIL` | Assertion failure or runtime error | Read traceback; investigate code |

**Key rule**: A `SkipTest` is not a failure. Browser smokes are designed to skip cleanly on CI agents without Chrome/Edge. Only non-zero exits require investigation.

---

## Failure Signatures And First Actions

### 1. `SkipTest: Node.js is required`

**Cause**: `node` is not on PATH or Node version is below 18.

**Check**:
```powershell
node --version
```

**Fix**: Install Node 18+ and ensure `node` is accessible on PATH. Earlier Node versions may lack `WebSocket` in global scope.

---

### 2. `SkipTest: Chrome or Edge is required`

**Cause**: No Chrome or Edge binary found at expected install paths.

**Check**:
```powershell
Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe"
Test-Path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

**Fix**: Install Google Chrome or Microsoft Edge. On CI agents without a browser, this skip is intentional and expected.

---

### 3. `AssertionError:` during CDP runner

**Cause**: WebView JavaScript behavior did not match expectations.

**Common sub-causes**:

| Sub-cause | Symptom |
|---|---|
| Backend API response changed shape | Rendering assertion fails; look for missing DOM content |
| DOM element ID renamed | CDP selector returned null or wrong element |
| Local API server timed out at startup | Timeout assertion; try increasing `--timeout` |
| JS threw an exception during evaluation | CDP evaluation failure with exception description |

**What to read**:
- The assertion text includes: smoke label, return code, bounded stdout, bounded stderr
- CDP failures include browser exception description/value/detail text
- The failing DOM ID or rendering assertion is usually named directly in the output

**First investigation step**: Find the DOM element ID in the assertion text. Search `WEBVIEW_DOM_ID_INVENTORY.md` for its owning JS file. Check the corresponding backend payload and JS rendering function.

---

### 4. `ConnectionRefusedError` or `TimeoutError` during CDP setup

**Cause**: The local API backend did not start in time, or the CDP port did not open.

**Check**:
```powershell
$python = "apps\desktop\runtime\Python\python.exe"
& $python -c "import mediapipeline.desktop; print('ok')"
```

**Sub-causes**:
- Bundled Python not resolved correctly (check wrapper uses `apps\desktop\runtime\Python\python.exe`)
- Another process using the same port range (smokes allocate a free port; port conflicts are rare but possible)
- Backend module import error (run `python -m mediapipeline.desktop.local_api_main --help`)

---

### 5. Non-zero exit with `FAIL` in output

**Cause**: One or more test assertions explicitly failed.

**Read**:
- Failing test method name
- The assertion that failed
- Any captured browser console errors or network request failures

This is the most common investigation path. Browser console errors in the output usually point directly at the broken rendering path.

---

### 6. Timed-out smoke (no output, then kill)

**Cause**: Browser CDP process or local API hung during startup.

**What the runner does**: Browser stdout/stderr is ignored (not piped) to avoid undrained-pipe hangs. The runner uses a bounded browser termination helper. A pre-exited browser cannot hang the Python process.

**If it still hangs**: The Python process itself is blocking, not the browser. Check for import errors or blocking calls in the local API module.

---

### 7. `Return code: 124` with `Timed out after Ns.` in STDERR

**Cause**: The Node/CDP runner process hit the configured timeout. The shared runner (`webview_browser_smoke_support.py`) catches `subprocess.TimeoutExpired` and converts it to an `AssertionError` in the standard bounded-failure format. No raw `TimeoutExpired` traceback is produced.

**Signature in output**:
```
<label> failed.
Return code: 124
STDOUT:
<partial output up to truncation limit>
STDERR:
<partial stderr>
Timed out after 60s.
```

**First check**: The Node/CDP runner may be waiting for the browser CDP port (`waitForPageWebSocket` retries for 15 s). If the backend local API is slow to bind its port, the 15 s page-socket wait may consume most of the timeout budget. Verify the API starts cleanly and the browser is not stalling at launch.

**Not the same as section 6**: Section 6 covers Python-level hangs (import errors, blocking API calls). Return-code-124 means the Node runner process itself exceeded timeout — the Python runner is not blocked, it terminated the Node process and raised the assertion.

---

### 8. `Smoke runner produced no JSON result line.`

**Cause**: The Node/CDP runner exited with code 0 but its stdout was empty or contained no parseable lines. The shared runner appends this message to STDERR and raises `AssertionError`.

**Signature in STDERR suffix**:
```
Smoke runner produced no JSON result line.
```

**Return code**: Inherits the Node runner's return code (usually 0, since `assert_browser_smoke_process_ok` passed before this check).

**First check**: The Node runner is expected to write a single JSON object as its last stdout line (e.g. `{"status":"ok","findings":[]}`). If the runner exits before reaching its final `console.log(JSON.stringify(...))`, inspect the bounded STDOUT for the last line printed — that is where the runner stopped. Check for unhandled promise rejections or early exits in the scenario script.

---

### 9. `Return code: 3221226505` or `Return code: -1073740791` with empty STDOUT/STDERR

**Cause**: On Windows this is a native crash code observed from the headless Node/CDP runner path during long browser-smoke groups. If the runner produced no stdout/stderr, the shared support layer treats it as environmental/browser-runner instability and retries exactly once.

**Expected behavior**: A single transient occurrence should be hidden by the retry. If the second attempt also fails, the assertion includes the same standard bounded failure text plus retry context.

**Not retried**: Any failure with actionable stdout/stderr, normal assertion failures, timeout failures, malformed JSON, WebView exceptions, or backend API contract failures. Those should be investigated directly.

**First check if persistent**: Run the failing module alone, then check Chrome/Edge version, GPU/headless stability, antivirus interference around the temporary browser profile, and whether another browser smoke suite is running concurrently.

---

### 10. `Return code: 1` with `[object ErrorEvent]` or `CDP websocket error while opening`

**Cause**: The Node/CDP runner failed while opening the DevTools WebSocket to the headless browser page. This has been observed as a transient during long full-suite runs even when the same smoke passes alone.

**Expected behavior**: The shared runner retries once for this exact no-output connection-open transient. If it persists after retry, the final failure includes bounded stdout/stderr and the CDP open text.

**Not retried**: Browser assertion failures, WebView exceptions after CDP connection, route-contract failures, timeouts, malformed JSON, or any failure that emits meaningful scenario output.

**First check if persistent**: Run the failing smoke alone, then verify Chrome/Edge is not being updated or blocked and no other browser-smoke suite is running concurrently.

---

### 11. `Last stdout line was not JSON:` or `Smoke runner JSON result was not an object.`

**Cause**: The Node/CDP runner's last stdout line was not valid JSON, or it was valid JSON but not an object (e.g. a string or array). The shared runner appends the `json.JSONDecodeError` detail or the type mismatch message to STDERR and raises `AssertionError`.

**Signature variants in STDERR suffix**:
```
Last stdout line was not JSON: Expecting value: line 1 column 1 (char 0)
```
or
```
Smoke runner JSON result was not an object.
```

**First check**: Look at the last STDOUT line in the assertion text. If the runner hit a JavaScript exception, the final output may be a stringified error rather than the expected result object. CDP `Runtime.evaluate` exceptions are captured in the `exceptions` array in the runner prelude; check whether the scenario script calls `cdp.send("Runtime.evaluate", ...)` and the result included an error code.

---

### 10. Browser termination does not hang the Python runner

**Expected behavior** (not a failure): The shared Node/CDP prelude launches the browser with `stdio: ["ignore","ignore","ignore"]` — browser stdout/stderr is never piped, so undrained-pipe hangs cannot occur. On runner exit, `terminateBrowser` sends `SIGKILL` if the graceful kill does not complete within 2500 ms, then waits another 1000 ms. After that, the Node process exits regardless. The Python runner sees a normal process exit.

**If you see the smoke taking unusually long after its assertions finish**: The Node process may be waiting in `terminateBrowser`. This is bounded and self-resolving (≤ 3.5 s worst case). It is not a hang — the Python test will complete. If you want to confirm, check whether the smoke passes immediately after a brief extra delay.

---

## What Browser Smoke Failures Do NOT Prove

A browser smoke failure means the WebView UI assertion failed — it does not mean the backend pipeline is broken. Specifically, browser smokes do not exercise:

- FFmpeg behavior, encoder choices, subtitle conversion, audio routing
- Real media files, source paths, output paths, or scratch paths
- Settings persistence (config file is never written)
- Rename filesystem operations (`rename.apply` is verified NOT called)
- Pending publish drain (no files are moved or published)
- Live telemetry (fixture payloads only)
- Network lifecycle control (coordinator/worker start/stop)

For real-media behavior, use `docs/implementation/release-foundation/PHASE_6_REAL_MEDIA_PILOT.md`.

---

## Which Smoke Covers What

| Wrapper | First thing to check when it fails |
|---|---|
| `Test-WebViewBrowserHighRiskSmoke.ps1` | Backend-produced blocked Queue/Completed/Pending Publish row shape |
| `Test-WebViewBrowserScheduleSmoke.ps1` | Schedule Editor staging or `POST /api/schedule/save` response shape |
| `Test-WebViewBrowserLifecycleSmoke.ps1` | Close-readiness payload or shutdown confirmation rendering |
| `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` | Row click → diagnostics bridge DOM IDs; tail/open button rendering |
| `Test-WebViewBrowserPendingDrainGuardSmoke.ps1` | Recovery dry-run payload shape; `frontend_guard` command evidence rendering |
| `Test-WebViewBrowserCompletedPendingProofSmoke.ps1` | Proof ladder DOM IDs; missing-output blocker text; reconciliation endpoint shape |
| `Test-WebViewBrowserLargeTableSmoke.ps1` | 260-row render-cap disclosure wording; filter warning rendering |
| `Test-WebViewBrowserMaintenanceReportsSmoke.ps1` | Maintenance dry-run result text; Reports failure/audit triage and selected-row detail DOM IDs |
| `Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1` | Maintenance Change Ledger DOM IDs; ledger summary/detail/hygiene text; filter and empty-state rendering |
| `Test-WebViewBrowserRenameSmoke.ps1` | Apply Readiness DOM IDs; duplicate-target blocking text |
| `Test-WebViewBrowserNetworkSmoke.ps1` | Worker detail rendering; filter warning wording |
| `Test-WebViewBrowserTelemetrySmoke.ps1` | Zero-percent NVENC rendering without duplicate idle wording; CPU/RAM-only fallback wording |
| `Test-WebViewBrowserSettingsLaunchSmoke.ps1` | Staged patch handoff DOM IDs; cancellation command-history assertion |
| `Test-WebViewBrowserSampleValidationSmoke.ps1` | Sample Validation pilot/readiness/reconciliation DOM IDs; execution checklist row text; worksheet match assertion; preview evidence packet shape |
| `Test-WebViewBrowserHomeLiveStateSmoke.ps1` | Home Daily-Driver / Operator Readiness rendering; ActiveJobs fixture shape; generated command journal; Sample Validation posture panel DOM IDs |
| `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` | Launch readiness/preflight DOM IDs; Launch Scope Reconciliation rows; Launch Real-Media Sample Proof rows; Launch Sample Validation record evidence rows; generated validation-record fixture shape; temporary validation record creation |
| `Test-WebViewBrowserLayoutManagerSmoke.ps1` | Customize button, generated panel wrapping, inactive subtab visibility, and draggable panel handle selectors |

### Launch/Queue Readiness Smoke — Failure Detail

The `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` smoke uses a more complex fixture than earlier smokes:

| Fixture component | What it provides |
|---|---|
| Generated launch command history | `launch.start` command entries for timing trust assertion |
| Generated Sample Validation record | Temporary JSONL record written to a temp log path; smoke verifies selected-sample match in Launch proof handoff |
| Backend launch preflight | Real `GET /api/launch/preflight` response from temporary backend state |
| Worksheet evidence | Real generated worksheet read from temporary `RealMediaValidationRuns` directory |

**Common failure causes for this smoke**:
- DOM ID `launch-real-media-proof-rows` or `launch-scope-reconciliation-rows` not found — check `launchView.js` export and index.html DOM ID presence
- Sample Validation record not matching the selected sample — check generated record fixture's `source_path` / `output_path` match against the queue fixture
- Worksheet evidence rendering assertion — check `crossPageContextView.js` `crossPageRealMediaWorksheetRows` function and worksheet fixture path
- Missing validation record log assertion — check temporary log path and that `sample_validation_log.jsonl` was created by the fixture setup

---

## Freshness Review — 2026-05-15 (CLN3-027)

Added triage entries for three newer browser smokes (`SampleValidation`, `HomeLiveState`, `LaunchQueueReadiness`) and a detailed Launch/Queue readiness fixture breakdown.

```
Task ID: CLN3-027
Files inspected: docs\testing\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md, docs\testing\BROWSER_SMOKE_TEST_RUNBOOK.md, tests\python\desktop\test_webview_browser_launch_queue_readiness_smoke.py (reference)
Files changed: docs\testing\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md (3 smoke entries added to "Which Smoke Covers What"; Launch/Queue readiness detail section added)
Validation: Select-String -Path docs\testing\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md -Pattern "LaunchQueue|Launch/Queue|validation record|worksheet"
Findings: Cheatsheet was missing entries for 3 newer smokes. Added triage guidance. No generic failure categories changed.
Open questions: None.
Risk: Low — documentation only.
```

---

## See Also

- `docs\testing\BROWSER_SMOKE_TEST_RUNBOOK.md` — full prerequisites, invocation, and interpretation
- `docs\testing\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` — explicit mutation boundary guarantees
- `docs\inventories\WEBVIEW_DOM_ID_INVENTORY.md` — DOM ID to JS file mapping for selector debugging

---

## Task Output

```
Task ID: CLN-025
Files inspected: docs\testing\BROWSER_SMOKE_TEST_RUNBOOK.md, docs\testing\WEBVIEW_SMOKE_TEST_CATALOG.md
Files changed: docs\testing\BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md (created)
Validation: Cross-referenced with BROWSER_SMOKE_TEST_RUNBOOK.md failure interpretation section.
Findings: All failure categories from the runbook are represented. Skip vs fail distinction documented. Per-smoke first-check column added.
Open questions: None.
Risk: Low — documentation only.
```
