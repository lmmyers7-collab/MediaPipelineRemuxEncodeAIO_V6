# Browser Smoke Test Runbook

This runbook explains how to run the browser-backed WebView smoke tests, what prerequisites they need, how to interpret failures, and what they do and do not prove.

## Prerequisites

### Node.js

All browser-backed smokes require Node.js on PATH. The mocked-DOM smokes also use Node, but the browser-backed smokes additionally require it for the CDP runner script.

To check:

```powershell
node --version
```

Node 18 or later is recommended. Earlier versions may lack `WebSocket` in global scope.

### Chrome or Edge

The browser smokes use the Chrome DevTools Protocol (CDP) via headless Chrome or Edge. They do not use Playwright, Puppeteer, or any browser automation framework that requires a separate install or `npm install`.

Required: an installed Google Chrome or Microsoft Edge. The smoke finds it by checking common install paths on Windows. If neither is found, the test raises `unittest.SkipTest` and exits with code 0 (skip, not failure).

The Python smoke modules share `DesktopApp\tests\webview_browser_smoke_support.py` for browser discovery, free-port allocation, bounded stdout/stderr failure output, timeout reporting, JSON result parsing, subprocess-result assertions, and the generated Node/CDP runner prelude. If a browser runner fails, the assertion should include the runner return code plus bounded stdout/stderr before the Python traceback. The shared Node/CDP prelude launches Chrome/Edge with browser stdout/stderr ignored instead of undrained pipes, and uses a bounded browser termination helper so a pre-exited browser cannot hang the smoke runner. On Windows, the shared runner retries exactly once when the Node/CDP runner exits with the known no-output native crash return code `3221226505` / `-1073740791` or a no-output CDP WebSocket open transient (`[object ErrorEvent]` / `CDP websocket error while opening`). Actionable failures with meaningful stdout/stderr are not retried.

To check whether the smoke will find a browser:

```powershell
# Chrome typical paths
Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe"
Test-Path "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

# Edge typical paths
Test-Path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
Test-Path "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
```

### Python

The smoke tests run through the standard Python unittest runner. Use the bundled runtime when available:

```
DesktopApp\Runtime\Python\python.exe
```

The `SmokeTests/` wrapper scripts resolve this automatically.

---

## Running Browser Smokes

### Via Root Wrappers (recommended)

From the repo root:

```powershell
.\SmokeTests\Test-WebViewBrowserHighRiskSmoke.ps1
.\SmokeTests\Test-WebViewBrowserScheduleSmoke.ps1
.\SmokeTests\Test-WebViewBrowserLifecycleSmoke.ps1
.\SmokeTests\Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1
.\SmokeTests\Test-WebViewBrowserPendingDrainGuardSmoke.ps1
.\SmokeTests\Test-WebViewBrowserCompletedPendingProofSmoke.ps1
.\SmokeTests\Test-WebViewBrowserLargeTableSmoke.ps1
.\SmokeTests\Test-WebViewBrowserMaintenanceReportsSmoke.ps1
.\SmokeTests\Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1
.\SmokeTests\Test-WebViewBrowserSampleValidationSmoke.ps1
.\SmokeTests\Test-WebViewBrowserHomeLiveStateSmoke.ps1
.\SmokeTests\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1
.\SmokeTests\Test-WebViewBrowserLayoutManagerSmoke.ps1
.\SmokeTests\Test-WebViewBrowserRenameSmoke.ps1
.\SmokeTests\Test-WebViewBrowserNetworkSmoke.ps1
.\SmokeTests\Test-WebViewBrowserTelemetrySmoke.ps1
.\SmokeTests\Test-WebViewBrowserSettingsLaunchSmoke.ps1
```

Each wrapper resolves Python, sets `PYTHONDONTWRITEBYTECODE=1`, prints boundary text, and exits nonzero if the test fails.

### Via `python -m unittest` directly

From the repo root with the bundled Python:

```powershell
$python = "DesktopApp\Runtime\Python\python.exe"
& $python -m unittest DesktopApp.tests.test_webview_browser_high_risk_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_schedule_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_lifecycle_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_diagnostics_handoff_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_pending_drain_guard_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_completed_pending_proof_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_large_table_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_maintenance_reports_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_maintenance_change_ledger_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_sample_validation_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_home_live_state_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_launch_queue_readiness_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_rename_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_network_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_telemetry_smoke -q
& $python -m unittest DesktopApp.tests.test_webview_browser_settings_launch_smoke -q
```

### Running all smokes via discovery

```powershell
$python = "DesktopApp\Runtime\Python\python.exe"
& $python -m unittest discover -s DesktopApp\tests -p "test_webview_browser_*.py" -q
```

### Running an individual test case

```powershell
$python = "DesktopApp\Runtime\Python\python.exe"
& $python -m unittest DesktopApp.tests.test_webview_browser_rename_smoke.WebViewBrowserRenameSmokeTests.test_real_browser_renders_rename_readiness_and_blocks_duplicate_apply -q
```

---

## What Each Browser Smoke Verifies

| Wrapper | Test module | Verifies |
|---|---|---|
| `Test-WebViewBrowserHighRiskSmoke.ps1` | `test_webview_browser_high_risk_smoke` | Injected + backend-produced blocked Queue, broken Completed, do-not-drain Pending Publish row guidance under real browser rendering |
| `Test-WebViewBrowserScheduleSmoke.ps1` | `test_webview_browser_schedule_smoke` | Schedule Editor preview/save routing, confirmed backend app-state write for schedule keys, Schedule-owned command history, preserved save feedback after refresh, and Launch timing trust using the refreshed schedule payload |
| `Test-WebViewBrowserLifecycleSmoke.ps1` | `test_webview_browser_lifecycle_smoke` | Backend lifecycle and Close Readiness in real browser rendering: watcher-armed shutdown stays disabled/local-only, terminal stop-requested watcher evidence stays visible without blocking safe close, safe close-readiness posts backend-owned `/api/backend/shutdown` only after confirmation |
| `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` | `test_webview_browser_diagnostics_handoff_smoke` | Table row clicks, filter visibility, clear-filter behavior, diagnostics bridge, tail, allowlisted open controls, Diagnostics First Response selectable detail, Diagnostics State Artifact Summary read-order/artifact detail, local Diagnostics owner-row navigation, and API Contract Safety Review summary/detail from `/api/contract` |
| `Test-WebViewBrowserPendingDrainGuardSmoke.ps1` | `test_webview_browser_pending_drain_guard_smoke` | Pending Publish active display-filter scope is disclosed as local-only, recovery dry-run refreshes Publish Button Guard, blocked publish click records `frontend_guard`, and blocked clicks do not post `/api/pipeline/start` |
| `Test-WebViewBrowserCompletedPendingProofSmoke.ps1` | `test_webview_browser_completed_pending_proof_smoke` | Completed Real-Media Output Proof ladder detail, saved-policy reconciliation checkpoint, Completed-to-Pending proof board detail, backend publish reconciliation endpoint rendering, selected Pending row Completed Manifest correlation for exact output overlap, missing-output-without-proof blockers, same-leaf duplicate-title wording, and read-only mutation boundary |
| `Test-WebViewBrowserLargeTableSmoke.ps1` | `test_webview_browser_large_table_smoke` | Queue, Completed, and Pending Publish 260-row payloads disclose the 250-row render cap, warn when filters hide blocked/warning rows, show Queue Launch Decision / Completed Output Acceptance / Pending Drain Decision daily-use handoff and filter-scope evidence, keep hidden selected-row detail visible, and post no mutation routes |
| `Test-WebViewBrowserMaintenanceReportsSmoke.ps1` | `test_webview_browser_maintenance_reports_smoke` | Maintenance health/readiness, release dry-run result rendering, completed-manifest backfill dry-run result rendering, dry-run history, Reports failure/audit triage, selected-row details, failure-marker clear dry-run preview, read-only Launch/Diagnostics handoff navigation, and no non-dry-run mutation posts |
| `Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1` | `test_webview_browser_maintenance_change_ledger_smoke` | Maintenance Change Ledger summary/table/detail/hygiene rendering, affected Python-script detail, status/search filters, empty state, read-only `GET /api/maintenance/change-ledger`, and no media/queue/settings/pending-publish/rename mutation posts |
| `Test-WebViewBrowserSampleValidationSmoke.ps1` | `test_webview_browser_sample_validation_smoke` | Home Sample Validation pilot checkpoint/attention/readiness/reconciliation text, real-media validation audit and policy-alignment roll-ups, Completed saved-policy reconciliation handoff/detail, operator sample execution checklist detail, generated worksheet table and selected-sample match detail, Real-Media Validation Worksheet sample posture, preview-only current-evidence plus pilot evidence packet rendering, and no append or mutation posts |
| `Test-WebViewBrowserHomeLiveStateSmoke.ps1` | `test_webview_browser_home_live_state_smoke` | Home Daily-Driver Checklist, Operator Readiness, Active Work, Command Results, Sample Validation posture, generated worksheet readback, Real-Media Validation Worksheet handoff, and no POST routes |
| `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` | `test_webview_browser_launch_queue_readiness_smoke` | Launch readiness, Launch timing trust, Launch Scope Reconciliation, Launch Start Decision Summary, Launch generated-worksheet selected-sample match evidence, Launch Sample Validation record selected-sample match/reconciliation evidence, saved-policy-vs-Queue-route evidence, Launch Sample Execution Checklist, Launch Pilot Run Readiness, backend `GET /api/launch/preflight`, Queue Launch Decision, Schedule guidance/timing trust, close-readiness, launch command-review correlation, `pipeline.start` owner mapping, and no POST routes |
| `Test-WebViewBrowserLayoutManagerSmoke.ps1` | `test_webview_browser_layout_manager_smoke` | Layout Editor drawer lists representative page tabs, subtabs, and generated subsections; drawer move/drag, Hidden/Advanced toggles, selected-row preview, scoped reset, and inactive-subtab hiding are covered |
| `Test-WebViewBrowserRenameSmoke.ps1` | `test_webview_browser_rename_smoke` | Rename row selection, Apply Readiness status, Pipeline Handoff text, large-preview 250-of-260 render-cap disclosure, duplicate-target blocking does not call `rename.apply` |
| `Test-WebViewBrowserNetworkSmoke.ps1` | `test_webview_browser_network_smoke` | Read-only Network readiness, lifecycle handoff, persisted worker detail, and local filter warnings when active/problem worker rows are hidden |
| `Test-WebViewBrowserTelemetrySmoke.ps1` | `test_webview_browser_telemetry_smoke` | Idle NVENC at `0%`, synthesized GPU detail rows, and CPU/RAM-only fallback wording under real browser rendering |
| `Test-WebViewBrowserSettingsLaunchSmoke.ps1` | `test_webview_browser_settings_launch_smoke` | Staged settings patch handoff, Launch Active Media Policy Boundary for saved-vs-staged subtitle/audio/pending-publish policy, Settings-to-Launch intent including Queue display-scope evidence, backend Preview/Save result detail, backend Preview Patch evidence, cancelled Save Patch visibility; asserts cancellation does not append command history and `settings.save_patch` is NOT called |

---

## Interpreting Failures

### `SkipTest: Node.js is required`

Node.js is not on PATH or not found. Install Node 18+ and ensure `node` is accessible.

### `SkipTest: Chrome or Edge is required`

No Chrome or Edge binary was found at the expected install paths. Install either browser, or if on CI, install a headless Chrome package.

### `AssertionError: ...` during the CDP runner

The WebView JavaScript behavior did not match expectations. This usually means:

- A backend API response changed shape and the frontend rendering is broken.
- A DOM element ID changed and the CDP selector missed it.
- The local API server did not start in time (increase `--timeout` if you have a slow machine).

Read the full assertion text. Browser-runner failures include the smoke label, return code, bounded stdout, and bounded stderr. Timeout failures are converted into the same bounded assertion format instead of a raw `TimeoutExpired` traceback. CDP runtime-evaluation failures should preserve the browser exception description/value/detail text, so broken selectors and thrown WebView errors should usually point at the failing DOM ID or rendering assertion directly. Check the relevant backend payload and the corresponding JS rendering function.

### `ConnectionRefusedError` or `TimeoutError` during CDP setup

The local API server did not start or the browser CDP port did not open in time. Check:

- Whether the bundled Python resolved correctly.
- Whether another process is using the same port range.
- Whether the backend local API module can be imported: `python -m mediapipeline_desktop_app.local_api_main --help`.

### `Return code: 124` with `Timed out after Ns.` in STDERR

The Node/CDP runner hit the shared timeout. The Python runner catches `subprocess.TimeoutExpired` and converts it into the standard bounded-assertion failure format (smoke label, return code, bounded stdout, bounded stderr). No raw `TimeoutExpired` traceback is produced. Return code 124 is the sentinel for this case.

Check whether the backend local API is slow to start (the Node runner's `waitForPageWebSocket` retries for 15 s) or whether the browser failed to open a CDP port. This is distinct from a Python-level hang — the Python runner is not blocked; it terminated the Node process and raised the assertion.

### `Smoke runner produced no JSON result line.` in STDERR

The Node/CDP runner exited with code 0 but wrote nothing (or nothing parseable) to stdout. The shared runner appends this suffix to STDERR and raises `AssertionError`. Look at the bounded STDOUT for the last line printed to find where the scenario script stopped executing. Check for unhandled promise rejections or an early return before the final `console.log(JSON.stringify(...))`.

### `Last stdout line was not JSON:` or `Smoke runner JSON result was not an object.`

The runner's last stdout line was not valid JSON, or it was valid JSON but not an object. The shared runner appends the `json.JSONDecodeError` detail or the type mismatch message to STDERR. Look at the last bounded STDOUT line — if the runner hit a JavaScript exception, the output may be a stringified error rather than the expected result object.

### Non-zero exit with `FAIL` in output

One or more test assertions failed. Read the traceback — it will show the failing test method, the assertion that failed, and any captured browser console errors or network failures.

---

## What Browser Smokes Do Not Prove

This is critical for daily-driver trust decisions.

Browser smokes prove that the WebView JavaScript renders expected UI state and responds correctly to user interactions under real browser rendering. They do not prove:

- **FFmpeg behavior**: no real media is processed. Route decisions, encoder choices, subtitle conversion, and audio routing are not exercised.
- **Remux/encode correctness**: the pipeline is never launched during a browser smoke.
- **Subtitle OCR or SRT conversion**: no OCR, no PGS/TX3G/ASS processing.
- **Audio passthrough or transcode**: no audio policy is exercised against real streams.
- **Source file stability or output path availability**: no filesystem probes against real media paths.
- **Pending publish drain behavior**: no files are moved, published, or drained.
- **Backend process shutdown under real work**: lifecycle smoke uses fixture state and a test callback; it does not close a real running encode or prove crash recovery.
- **Settings persistence**: `settings.save_patch` is explicitly verified as NOT called in the settings/launch smoke, including after a cancelled Save Patch confirmation. No config file is modified.
- **Rename filesystem mutations**: `rename.apply` is verified as NOT called in the rename smokes. No files are renamed.
- **Network lifecycle control**: coordinator/worker start-stop remains outside the WebView until backend-owned lifecycle routes are deliberately promoted. The Network browser smoke renders persisted worker state only.
- **Live telemetry collection**: telemetry smoke uses fixture payloads; it does not sample the local GPU or prove NVENC load under a real encode.
- **Completed manifest correctness**: fixture data is used; no real encode output is written.

For real-media validation, follow the observational checklist in `V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` against a small known batch.

---

## CI / Automated Use Notes

- Browser smokes skip cleanly when Chrome/Edge is absent (exit 0). This is intentional — they are environment-dependent and should not block CI pipelines that run on headless agents without a browser install.
- Non-browser smokes (`Test-WebViewCommandEvidenceSmoke.ps1`, `Test-WebViewRowDetailSmoke.ps1`, `Test-WebViewRenameReadinessSmoke.ps1`, `Test-WebViewSettingsLaunchPolicySmoke.ps1`) require only Python and Node and are suitable for lightweight automated checks.
- The release self-test layout gate (`scripts\release\test.ps1`) checks that all wrapper files exist. It does not run the smokes automatically.

