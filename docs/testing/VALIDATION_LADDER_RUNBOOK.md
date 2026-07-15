# Validation Ladder Runbook

Purpose: tell contributors and operators what to run for a given change type. Not every change needs the full suite. Running too much wastes time; running too little risks shipping a regression.

---

## Quick Reference

| Change type | Minimum required checks | Full checks if unsure |
|---|---|---|
| Docs-only (`.md` changes) | Release self-test `-SkipToolIntegration -SkipEndToEndSmoke` | Same |
| WebView JS / HTML / CSS only | Non-browser smokes + release self-test | + browser smokes if Chrome/Edge available |
| Local API route (read route) | Unit tests for that route + non-browser smokes | + browser smokes |
| Local API command route (mutation) | Unit tests + non-browser smokes + browser smokes | + real-media validation |
| Settings / rename / pending publish commands | Targeted tests + browser smokes | + real-media validation |
| Config/error-code registry cleanup | `test_config_keys.py` + `Invoke-ConfigKeyRegistryChecks.ps1` + `Invoke-FailureCodeRegistryChecks.ps1` + focused config/service tests | + reliability regression checks if pipeline config loading changes |
| Tauri shell (Rust) | Tauri prereq check + release self-test | + browser smokes |
| Pipeline PS/PS module | Pipeline unit tests + reliability regression checks | + tool integration checks |
| Release / packaging | Release self-test (full) | + `-Verify -IncludeTests` |
| Real-media routing or FFmpeg changes | All smokes + adversarial force-kill encode smoke + real-media validation | Full playbook |

---

## Rung 0: Docs Only

For changes that touch only `.md` files with no code or test changes.

```powershell
# Fastest check: verify package layout still valid, PS syntax passes
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

Expected runtime: under 30 seconds.

Skip conditions: none — always run this for docs changes that will be part of a release.

---

## Rung 1: WebView JS / HTML / CSS Changes

For changes to `apps\desktop\webview\static\` (JS, HTML, CSS).

### Non-browser smokes (Node.js required; no Chrome/Edge needed)

```powershell
$py = "apps\desktop\runtime\Python\python.exe"
.\ops/scripts/smoke\Test-WebViewCommandEvidenceSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRowDetailSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRealMediaEvidenceSmoke.ps1
.\ops/scripts/smoke\Test-WebViewScheduleSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRenameReadinessSmoke.ps1
.\ops/scripts/smoke\Test-WebViewSettingsLaunchPolicySmoke.ps1
.\ops/scripts/smoke\Test-WebViewSettingsLaunchLiveConfigSmoke.ps1
.\ops/scripts/smoke\Test-WebViewSettingsPatchEvidenceSmoke.ps1
```

`Test-WebViewSettingsLaunchLiveConfigSmoke.ps1` reads the selected saved config. Do not use it in a disposable-root-only task unless its config input is explicitly redirected to a generated temporary config.

### Browser-backed smokes (24 wrappers / 26 Python modules; Chrome or Edge required)

Canonical wrappers fail prerequisite skips by default. A green wrapper therefore means browser assertions executed. Use `-AllowSkippedTests` only for an explicitly non-gating environmental result and record that it is not a pass.

```powershell
.\ops\scripts\smoke\Test-WebViewBrowserCompletedPendingProofSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserHighRiskSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserHomeLiveStateSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserLargeTableSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserLayoutManagerSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserLibraryProfilesSaveSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserLifecycleReconciliationSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserLifecycleSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserMaintenanceReportsSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserNetworkSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserPendingDrainGuardSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserProseBoxAudit.ps1
.\ops\scripts\smoke\Test-WebViewBrowserQueueFileOverridesSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserQueueLaunchCompletedSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserRenameSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserSampleValidationSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserScheduleSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserSettingsFieldMatrixSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserSettingsLaunchSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserTelemetrySmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserVisualClutterScreenshots.ps1
```

The two additional direct modules are `test_webview_browser_metrics_degraded_state_smoke.py` and `test_webview_browser_settings_builder_flush_smoke.py`. Discover all 26 modules with:

```powershell
$py = "apps\desktop\runtime\Python\python.exe"
& $py -m unittest discover -s tests\webview -p "test_webview_browser*.py" -q
```
The browser-backed smoke modules share one Python/Node CDP runner support layer. It owns browser discovery, free-port allocation, bounded timeout/failure output, JSON result parsing, Chrome/Edge launch without undrained stdout/stderr pipes, bounded browser termination, and a single retry for the known no-output Windows native runner crash code (`3221226505` / `-1073740791`) or an explicitly recognized CDP startup/readiness transient. Actionable browser console errors and test assertions are not retried. If a browser smoke fails, prefer the bounded runner assertion text over manually rerunning random page snippets.

### Release self-test (layout + syntax)

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

What these prove: WebView JavaScript renders expected UI state, boundary guards fire, mutation routes are not called during UI interaction tests. What they do not prove: FFmpeg behavior, real route decisions, real subtitle/audio output, settings persistence.

---

## Rung 2: Local API Routes (Python)

For changes to `src\mediapipeline\desktop\api\` or facade layer.

Use the bundled interpreter from the repository root. Do not treat system Python failures such as missing `pytest` as product test failures unless the task explicitly validates a clean system-Python install.

### Targeted Python unit tests

```powershell
$py = "apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.test_api_read_payloads_policy -q
& $py -m unittest tests.python.desktop.test_api_command_results_policy -q
& $py -m unittest tests.python.desktop.test_api_command_journal_policy -q
& $py -m unittest tests.python.desktop.test_api_handler_policy -q
& $py -m unittest tests.python.desktop.test_api_static_files_policy -q
& $py -m unittest tests.python.desktop.test_api_http_helpers -q
& $py -m unittest tests.python.desktop.test_backend_bootstrap -q
& $py -m unittest tests.python.desktop.test_config_keys -q
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-FailureCodeRegistryChecks.ps1
.\ops/scripts/smoke\Test-LocalApiLifecycleContractSmoke.ps1
.\ops/scripts/smoke\Test-LocalApiMaintenanceDryRunContractSmoke.ps1
.\ops/scripts/smoke\Test-LocalApiSampleValidationContractSmoke.ps1
```

### Domain policy/facade tests if application behavior changed

```powershell
& $py -m unittest discover -s tests\python\desktop -p "test_*_policy.py" -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_*.py" -q
```

### WebView smokes (Rung 1) to verify frontend renders new payload shapes correctly.

---

## Rung 3: Settings / Rename / Pending Publish Commands

For changes to command handling in settings patch, rename apply, or pending publish drain.

### Targeted service and facade tests

```powershell
$py = "apps\desktop\runtime\Python\python.exe"
# Settings
& $py -m unittest tests.python.desktop.test_facade_settings_policy -q
& $py -m unittest tests.python.desktop.test_facade_settings_patch_policy -q
& $py -m unittest tests.python.desktop.test_service_config_save_runner -q

# Rename
& $py -m unittest tests.python.desktop.test_service_rename_apply -q
& $py -m unittest tests.python.desktop.test_service_rename_apply_runner -q
& $py -m unittest tests.python.desktop.test_service_rename_plan_policy -q

# Pending publish
& $py -m unittest tests.python.desktop.test_service_pending_publish_manifest -q
& $py -m unittest tests.python.desktop.test_service_pending_publish_manifest_rows -q
& $py -m unittest tests.python.desktop.test_pending_publish_service -q
```

### Settings patch evidence smoke (verifies no save without confirm)

```powershell
.\ops/scripts/smoke\Test-WebViewSettingsPatchEvidenceSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserSettingsFieldMatrixSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserLibraryProfilesSaveSmoke.ps1
```

The browser Settings save smokes write only generated temporary config/state and verify strict confirmation plus reload evidence.

### Browser-backed rename smoke (verifies apply is not called on blocked scope)

```powershell
.\ops/scripts/smoke\Test-WebViewBrowserRenameSmoke.ps1
```

What these prove: service/facade routing and guard logic, plus confirmed Settings persistence only in generated temporary config for the field-matrix and Library Profiles scenarios. They do not prove safety of live config writes or production-media rename.

### Browser-backed large daily-table smoke (verifies large payload visibility only)

```powershell
.\ops/scripts/smoke\Test-WebViewBrowserLargeTableSmoke.ps1
```

What this proves: Queue, Completed, and Pending Publish 260-row payloads disclose the 250-row render cap, warn when filters hide blocked/warning rows, preserve selected-row detail, and avoid mutation POSTs. The `Queue Backend Launch Scope Preview` and `Pending Backend Drain Scope Preview` panels render correctly and display loaded-row vs. visible-filtered-row boundary wording. What it does not prove: real queue launch, completed repair, pending publish drain, or media processing. The scope preview panels are evidence-only — they issue no POST routes and do not change backend scope.

---

## Rung 4: Pipeline PowerShell Modules

For changes to `ops\pipeline\engine\<domain>\*.ps1` or `ops\pipeline\entrypoints\MediaPipeline.ps1`.

### Focused pipeline unit checks

There is no aggregate `ops\pipeline\tests\Invoke-UnitChecks.ps1` wrapper in
the current tree. Run the focused `ops\pipeline\tests\Unit\Invoke-*Checks.ps1`
scripts that match the touched domain, then run the active reliability wrapper
below when the change affects shared pipeline behavior.

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-ContractSchemaChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PathBoundaryGuardChecks.ps1
```

### Active current reliability regression wrapper

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ReliabilityRegressionChecks.ps1
```

This wrapper runs the current WebView/backend reliability gate and focused backend safety checks by default. Archived legacy desktop-shell checks require the explicit `-RunLegacyDesktopChecks` switch.

### Adversarial encode force-kill safety smoke

Run this when touching encode execution, process lifecycle, publish completion, completed-manifest writes, pending-publish parking, or restart/recovery behavior:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-AdversarialForceKillEncodeChecks.ps1
```

This creates temporary generated media, starts a real backend `-Once` run, force-kills the backend process tree during CPU fallback encode, and verifies the partial temp output is not accepted as complete. It does not prove real-media output quality or Tauri close-dialog behavior.

### Tool integration checks (requires FFmpeg, MKVToolNix, PgsToSrt)

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ToolIntegrationChecks.ps1
```

What these prove: PowerShell syntax, module import, known routing and config logic, tool availability. What they do not prove: real-media routing, FFmpeg encode correctness on a specific file, subtitle OCR output.

---

## Rung 5: Tauri Shell Changes

For changes to `apps\desktop\tauri\` (Rust, Cargo.toml, tauri.conf.json).

### Check Tauri prerequisites

```powershell
.\ops\scripts\dev\start-tauri-preview.bat -CheckOnly
```

### Release self-test (includes Tauri prereq verification)

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1
```

### PG-1 adversarial close-readiness scaffold (Python, no Rust build required)

```powershell
python -m unittest tests.python.desktop.test_tauri_pg1_close_adversarial_scaffold -v
```

This proves: Tauri lib.rs contains all required structural patterns for armed-watcher + active-work combined close-readiness state, schema version validation, stop-requested and error watcher fields, empty-status guard, and the correct route is called.

### PG-1 live active-work close validation (manual, opens Tauri and starts one explicit source)

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoLogo -NoProfile `
  -File .\apps\desktop\tauri\Test-TauriShell-PG1ActiveClose.ps1 `
  -SourceFile '<absolute media source path>' `
  -ActiveJobsDir '<absolute temp LocalBase\State\ActiveJobs path>'
```

This proves: a Tauri-owned backend can start a real app-owned pipeline child, unsafe close-readiness surfaces in the native Tauri close prompt, confirming the prompt asks the backend to force-clean app-owned work, the shell/backend/pipeline child exit, and ActiveJobs reaches a terminal force-close state. This is not part of routine release validation because it opens the GUI and intentionally interrupts real media work.

### After confirming prereqs, run browser smokes to verify WebView rendering still works with Rust asset gate changes.

What these prove: Rust/Cargo available, Tauri configuration valid, WebView assets pass startup gate, PG-1 close-readiness adversarial handling patterns present in Rust source. With the live active-work harness, they can also prove the real native prompt and force-cleanup behavior for one explicit active pipeline child. What they do not prove: real-media FFmpeg routing, subtitle/audio, publish, clean-machine install, or a simultaneous live armed-watcher + active-pipeline close prompt unless that specific scenario is run.

---

## Rung 6: Release / Packaging Changes

For changes to `ops\scripts\release\build.ps1` or `ops\scripts\release\test.ps1`.

### Full release self-test

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1
```

### Engineering handoff verification (full)

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\build.ps1 -Zip -Verify -IncludeTests
```

What these prove: release manifest correctness, layout, exclusions, personal config not accidentally included. What they do not prove: any runtime media-processing behavior.

---

## Rung 7: Real-Media Routing or FFmpeg Changes

For any change that may affect FFmpeg command generation, route decisions, subtitle conversion, or audio policy.

**No automated check fully covers this rung.** All previous rungs must pass first, then run the real-media validation playbook:

```
docs/sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md
```

Follow with the evidence template:

```
docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md
```

Or generate a timestamped worksheet before the run:

```powershell
.\ops\scripts\operator\New-RealMediaValidationWorksheet.ps1 -SamplePath "D:\Samples\Movie.mkv" -Shell "WebView preview"
```

The worksheet helper is documentation-only. It writes Markdown evidence under `docs\RealMediaValidationRuns` by default and does not process media, launch the app, save settings, rename files, publish outputs, drain pending publish, mutate queue state, or touch source/output/scratch paths.

Expected evidence: Queue route reason, FFmpeg stderr/run log, Completed output/sidecar, subtitle and audio decision, size-growth policy, Pending Publish state or drain summary.

For output-verification changes, also retain source/output ffprobe stream and
frame-side-data JSON, verifier mismatch/acceptance evidence, and the selected
audio/subtitle policy plan. Preservation-policy Dynamic HDR remux evidence must
show source and output Dolby Vision/HDR10+ probe results; it must not claim RPU
frame equality unless a separate tool measurement produced that evidence.

This rung is the only rung that proves FFmpeg behavior. No smoke test, no unit test, and no release gate replaces it.

---

## Common Mistakes

- Running only the release self-test for WebView JS changes — it does not execute WebView JS or browser rendering.
- Treating a prerequisite skip as green evidence — canonical wrappers fail skips by default; `-AllowSkippedTests` is a documented non-gating exception, and final acceptance still requires a machine where assertions run.
- Treating clean smokes as real-media proof — smokes use fixture data and never run FFmpeg.
- Running `Invoke-ToolIntegrationChecks.ps1` for docs-only changes — that test requires live tools and is not needed.

---

## Freshness Review — 2026-05-15

Reviewed after adding the browser-backed Home live-state smoke.

| Check | Result |
|---|---|
| Non-browser smoke list (Rung 1) matches disk | Pass — all 8 wrappers present |
| Browser smoke list (Rung 1) matches disk | Pass — all 14 wrappers present |
| Catalog (`WEBVIEW_SMOKE_TEST_CATALOG.md`) agrees with runbook | Pass — same 8+14 split, same modules |
| Shared runner note present in Rung 1 | Pass — paragraph present; no correction needed |
| Rung ordering reflects current test layout | Pass — no new rungs needed |

All ladder entries remain accurate as of the browser Home live-state smoke addition.

---

## Freshness Review — 2026-05-15 (CLN4-014)

Checked whether scope preview panels (`Queue Backend Launch Scope Preview`, `Pending Backend Drain Scope Preview`) are reflected in the ladder.

**Stale count corrected**: Prior freshness review said "14 wrappers present" — the count moved to **15** when `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` was added, and to **16** on 2026-05-20 when `Test-WebViewBrowserLayoutManagerSmoke.ps1` was added. Rung 1 browser smoke list now lists all 16.

**Scope preview reference added**: Rung 3 LargeTable "What this proves" section now explicitly names both scope preview panels and clarifies that they are evidence-only renders that issue no POST routes.

| Check | Result |
|---|---|
| Non-browser smoke list (Rung 1) matches disk | Pass — all 8 wrappers present |
| Browser smoke list (Rung 1) matches disk | Pass — all 16 wrappers present (layout-manager smoke added) |
| Catalog (`WEBVIEW_SMOKE_TEST_CATALOG.md`) agrees with runbook | Pass — same 8+16 split |
| Shared runner note present in Rung 1 | Pass — no correction needed |
| Rung 3 LargeTable entry names scope preview panels | Pass — added in this update |
| Rung ordering reflects current test layout | Pass — no new rungs needed |

```
Task ID: CLN4-014
Files inspected: docs\testing\VALIDATION_LADDER_RUNBOOK.md (all rungs, freshness review)
Files changed: docs\testing\VALIDATION_LADDER_RUNBOOK.md (Rung 3 LargeTable "What this proves" updated; prior freshness note count corrected 14→15; CLN4-014 freshness note added)
Validation: Select-String -Path docs\testing\VALIDATION_LADDER_RUNBOOK.md -Pattern "Backend Launch Scope Preview|Backend Drain Scope Preview"
Findings: Rung 3 now names both scope preview panels. Browser smoke count corrected to 15.
Open questions: None.
Risk: Low — documentation only.
```

---

## See Also

- Smoke test catalog: `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- Browser smoke runbook: `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- Browser smoke prerequisites: `docs/testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md`
- Real-media pilot: `docs/sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md`
- Release package inventory: `docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`
- PowerShell host expectations: `docs/operator/POWERSHELL_HOST_EXPECTATIONS.md`

---

## Current Inventory Review — 2026-07-13

| Check | Result |
|---|---|
| Browser wrapper inventory | 24 canonical wrappers listed in Rung 1 |
| Browser Python inventory | 26 modules under `tests\webview`; discovery command uses the correct root |
| Skip semantics | Canonical wrappers fail prerequisite skips unless `-AllowSkippedTests` is explicit |
| Mutation boundary | Browser scenarios use generated disposable roots; permitted temporary writes are scenario-specific, never blanket live/operator access |

Use `docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` for exact allowed temporary writes by wrapper.
