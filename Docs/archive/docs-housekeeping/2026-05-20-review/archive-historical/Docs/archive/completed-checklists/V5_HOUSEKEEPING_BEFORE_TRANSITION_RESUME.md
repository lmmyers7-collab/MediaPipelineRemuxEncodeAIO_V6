# V5 Housekeeping Before Resuming Tauri/WebView2 Transition

Date: 2026-05-14  
Workspace: `MediaPipelineRemuxEncodeAIO_V5`  
Purpose: reduce drift, stale documentation, validation confusion, and wrapper/test inventory risk before continuing major WebView/Tauri transition work.

This checklist is intentionally non-media and non-invasive. It should not change FFmpeg behavior, remux/encode policy, subtitle/audio routing, pending publish behavior, rename filesystem mutation, Tk fallback behavior, or V4.

---

## Execution Result

Status: **completed on 2026-05-14**.

What was reconciled:

- Root validation wrapper inventory:
  - `19` `SmokeTests/Test-WebView*.ps1` wrappers.
  - `11` browser-backed WebView wrappers.
  - `8` non-browser WebView wrappers.
  - `1` browser-free Local API lifecycle contract wrapper.
- Local API route inventory:
  - `43` total routes.
  - `21` GET/read routes.
  - `22` POST/command routes.
- Diagnostics target inventory:
  - `20` backend-allowlisted diagnostics targets.
- Documentation status:
  - Route-count and command-count drift corrected.
  - WebView smoke wrapper counts corrected.
  - Diagnostics allowlist count drift corrected.
  - Completed Claude rename-readiness handoff marked archive-only.
  - Delegation/archive docs separated from active operator/engineering docs in `Docs\DOCS_INDEX.md`.
- Validation:
  - WebView wrapper boundary scan passed.
  - Tauri scaffold tests passed.
  - Local API lifecycle contract smoke passed.
  - Tauri shell build gate passed.
  - Release self-test passed with tool integration and end-to-end smoke intentionally skipped.

Result: housekeeping is complete enough to resume the original V5 Tauri/WebView2 transition work. The next recommended transition batch remains Tauri launch/close end-to-end smoke and lifecycle hardening.

---

## Ground Rules

- Do not touch `MediaPipelineRemuxEncodeAIO_V4`.
- Do not weaken Tk fallback.
- Do not remove validation gates unless they are proven obsolete and replaced.
- Do not change media policy, source/scratch/output behavior, pending publish semantics, or command contracts.
- Prefer documentation correction, inventory reconciliation, wrapper verification, and stale-reference cleanup.
- Any code changes should be limited to validation wrappers, tests, documentation references, or release/package inventory checks.

---

## Housekeeping Checklist

### 1. Validation Wrapper Inventory

- [x] List every root validation wrapper:
  - `Test-WebView*.ps1`
  - `Test-LocalApiLifecycleContractSmoke.ps1`
  - Tauri shell checks
  - release/package checks
  - real-media worksheet helper
- [x] Confirm each wrapper points at the intended test module or command.
- [x] Confirm each wrapper has accurate boundary text:
  - whether it opens a browser
  - whether it starts a temporary local API
  - whether it mutates temporary config/state
  - whether it processes media
  - whether it can launch pipeline work
  - whether it can rename, publish, save settings, or touch source/output/scratch files
- [x] Confirm wrapper names match their actual behavior.
- [x] Confirm browser-backed wrappers skip cleanly when Chrome/Edge is unavailable.
- [x] Confirm non-browser wrappers do not accidentally require Chrome/Edge.

### 2. Release Self-Test Alignment

- [x] Confirm every wrapper that should ship with the source/dev bundle is checked by `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`.
- [x] Confirm release self-test labels are current and human-readable.
- [x] Confirm new files added during the transition are represented in the layout gate where appropriate.
- [x] Confirm generated artifacts, temporary state, logs, and personal validation runs are excluded from clean release packages.
- [x] Confirm the release self-test still passes with:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

### 3. Documentation Count And Status Reconciliation

- [x] Reconcile route counts in:
  - `Docs\API_ROUTE_INVENTORY.md`
  - `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
  - `Docs\COMMAND_OWNERSHIP_MATRIX.md`
- [x] Reconcile smoke wrapper counts in:
  - `Docs\WEBVIEW_SMOKE_TEST_CATALOG.md`
  - `Docs\TEST_COVERAGE_MATRIX.md`
  - `Docs\VALIDATION_LADDER_RUNBOOK.md`
  - `Docs\TLDR.md`
- [x] Reconcile WebView parity state in:
  - `Docs\TAURI_WEBVIEW_PARITY_MATRIX.md`
  - `Docs\V5_TRANSITION_STATUS_BOARD.md`
  - `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- [x] Remove or correct stale statements that say something is missing when it has since been implemented.
- [x] Avoid overclaiming production readiness; WebView/Tauri remains preview until real-media validation and operator acceptance prove daily-driver safety.

### 4. Archive Or Mark Completed Planning Documents

- [x] Review Claude handoff documents and completed task backlogs.
- [x] Mark completed handoffs as complete/archive-only at the top of the file, or move them to an appropriate archive location if the repo already has one.
- [x] Keep still-useful runbooks and operator docs active.
- [x] Avoid deleting historical planning docs unless they are duplicated, obsolete, and already superseded by a clearer current document.
- [x] Ensure `Docs\DOCS_INDEX.md` distinguishes active operator docs, active engineering docs, archived plans, and handoff-only documents.

### 5. Validation Ladder Practicality Review

- [x] Confirm `Docs\VALIDATION_LADDER_RUNBOOK.md` still gives realistic minimum checks per change type.
- [x] Separate fast checks from expensive checks:
  - docs-only checks
  - local API unit checks
  - non-browser WebView checks
  - browser-backed checks
  - Tauri shell checks
  - release/package checks
  - real-media validation
- [x] Confirm commands use the bundled Python/PowerShell paths where appropriate.
- [x] Confirm the ladder explains what each rung does not prove.
- [x] Confirm local API lifecycle smoke is classified as a backend route-contract smoke, not a WebView rendering smoke.

### 6. Test Coverage Matrix Cleanup

- [x] Confirm every WebView page has current coverage entries:
  - Home
  - Live/Progress
  - Queue
  - Completed
  - Pending Publish
  - Rename
  - Launch
  - Settings
  - Diagnostics
  - Reports
  - Schedule
  - Network
  - Maintenance
- [x] Confirm gaps are real gaps, not stale notes.
- [x] Add explicit gap rows for:
  - Reports/Audit browser parity
  - real-media validation
  - actual drain launch validation
  - stuck process/orphan process failure handling
  - malformed state recovery
  - packaging/install confidence
- [x] Confirm every high-risk mutation route has backend tests and boundary documentation.

### 7. Local API And Command Contract Sanity Check

- [x] Confirm `GET /api/contract` still matches route implementation.
- [x] Confirm every route has:
  - method
  - effect class
  - auth requirement
  - primary frontend caller
  - backend owner
  - test coverage note
- [x] Confirm command routes still use backend-owned mutation logic.
- [x] Confirm frontend code does not introduce raw filesystem mutation or direct process execution.
- [x] Confirm backend shutdown remains guarded by close-readiness in WebView/Tauri flow.

### 8. Packaging And Dependency Notes

- [x] Confirm `Docs\PACKAGING_DEPENDENCY_INVENTORY.md` reflects current external requirements:
  - Node.js
  - Chrome/Edge for browser smokes
  - Rust/Cargo for Tauri checks
  - bundled Python
  - bundled PowerShell 7
  - FFmpeg/MKVToolNix/PgsToSrt
- [x] Confirm docs explain which dependencies are needed only for development/testing and which are needed for operator runtime.
- [x] Confirm release packaging does not accidentally include generated real-media worksheets, logs, temp state, caches, or personal files.
- [x] Confirm all new `SmokeTests/` wrappers are package-safe.

### 9. Stale Reference Sweep

- [x] Search for stale references to:
  - old wrapper counts
  - old route counts
  - old WebView parity status
  - old Tauri limitations that have since been fixed
  - old TODOs that are complete
  - old claims that Network/Telemetry/Schedule/Lifecycle are not exposed
- [x] Correct stale text or mark it historical if it is intentionally preserved.
- [x] Avoid rewriting large docs for style only; prioritize correctness and operator clarity.

### 10. Smoke And Scaffold Verification

- [x] Run focused scaffold checks:

```powershell
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
```

- [x] Run local API lifecycle smoke:

```powershell
.\SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1
```

- [x] Run Tauri shell gate:

```powershell
.\DesktopApp\tauri_shell\Test-TauriShell-Build.ps1 -SkipLinkCheck
```

- [x] Run release self-test:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

### 11. Update The Active Status Documents

- [x] Update `Docs\TLDR.md` with only high-signal operator changes.
- [x] Update `Docs\V5_TRANSITION_STATUS_BOARD.md` with current parity and validation status.
- [x] Update `Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md` only where the transition plan has materially changed.
- [x] Update `Docs\REMEDIATION_CHANGELOG.md` with the housekeeping batch summary and validation commands.
- [x] Update `Docs\DOCS_INDEX.md` if document ownership or archive status changed.

### 12. Return To The Original Transition

- [x] Resume the original V5 Tauri/WebView2 transition work after housekeeping is complete.
- [x] Recommended next transition batch: Tauri launch/close end-to-end smoke and lifecycle hardening.
- [x] Keep the same safety model:
  - Tk remains fallback.
  - V4 remains untouched.
  - backend owns mutation and media behavior.
  - WebView/Tauri remains preview until real-media validation proves daily-driver trust.

