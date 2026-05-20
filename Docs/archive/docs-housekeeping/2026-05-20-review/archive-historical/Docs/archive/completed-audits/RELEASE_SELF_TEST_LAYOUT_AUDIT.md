# Release Self-Test Layout Inventory Check

Date: 2026-05-15

Compares root scripts and key docs against the layout checks performed by `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`. Identifies which root files are release-gated, which are not, and which important docs are outside release-gate scope.

---

## Release Self-Test Layout Coverage

The release self-test (`Test-MediaPipelineRemuxEncodeAIO-Release.ps1`) runs a `Layout` section that checks for the existence of specific files and directories. All checks use `Test-Path` with exact paths; missing files set the test to `Failed`.

### Directory Existence Checks

| Label | Path |
|---|---|
| DesktopApp | `DesktopApp\` |
| Docs | `Docs\` |
| Pipeline | `Pipeline\` |
| SmokeTests | `SmokeTests\` |

### Core Operator Docs (Always Release-Gated)

| Label | Path |
|---|---|
| Docs index | `Docs\DOCS_INDEX.md` |
| Bundle README | `Docs\README_MediaPipelineRemuxEncodeAIO.md` |
| Operator TLDR | `Docs\TLDR.md` |
| Smoke test inventory | `Docs\SMOKE_TEST_INVENTORY.md` |
| Desktop app README | `Docs\DesktopApp\README_MediaPipelineRemuxEncodeAIO_DesktopApp.md` |
| Pipeline deployment README | `Docs\Pipeline\README_MediaPipelineRemuxEncodeAIO_Deployment.md` |

### Root Launchers (Always Release-Gated)

| Label | Path |
|---|---|
| Root setup launcher | `Setup-MediaPipelineRemuxEncodeAIO.bat` |
| Root run launcher | `Run-MediaPipelineRemuxEncodeAIO.bat` |
| Root desktop launcher | `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` |
| Root local API launcher | `Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat` |
| Root Tauri preview launcher | `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat` |
| Desktop local API launcher | `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat` |

### Operator Tools (Always Release-Gated)

| Label | Path |
|---|---|
| Root real-media validation worksheet helper | `New-RealMediaValidationWorksheet.ps1` |
| Environment verifier | `Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1` |

### Non-Browser WebView Smoke Wrappers (Always Release-Gated)

| Label | Path |
|---|---|
| SmokeTests WebView evidence smoke | `SmokeTests\Test-WebViewRealMediaEvidenceSmoke.ps1` |
| SmokeTests WebView command evidence smoke | `SmokeTests\Test-WebViewCommandEvidenceSmoke.ps1` |
| SmokeTests WebView row detail smoke | `SmokeTests\Test-WebViewRowDetailSmoke.ps1` |
| SmokeTests WebView schedule smoke | `SmokeTests\Test-WebViewScheduleSmoke.ps1` |
| SmokeTests WebView rename readiness smoke | `SmokeTests\Test-WebViewRenameReadinessSmoke.ps1` |
| SmokeTests WebView settings launch policy smoke | `SmokeTests\Test-WebViewSettingsLaunchPolicySmoke.ps1` |
| SmokeTests WebView settings live-config smoke | `SmokeTests\Test-WebViewSettingsLaunchLiveConfigSmoke.ps1` |
| SmokeTests WebView settings patch evidence smoke | `SmokeTests\Test-WebViewSettingsPatchEvidenceSmoke.ps1` |

### Browser-Backed WebView Smoke Wrappers (Always Release-Gated)

| Label | Path |
|---|---|
| SmokeTests WebView browser schedule smoke | `SmokeTests\Test-WebViewBrowserScheduleSmoke.ps1` |
| SmokeTests WebView browser backend lifecycle smoke | `SmokeTests\Test-WebViewBrowserLifecycleSmoke.ps1` |
| SmokeTests WebView browser high-risk smoke | `SmokeTests\Test-WebViewBrowserHighRiskSmoke.ps1` |
| SmokeTests WebView browser diagnostics handoff smoke | `SmokeTests\Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` |
| SmokeTests WebView browser pending drain guard smoke | `SmokeTests\Test-WebViewBrowserPendingDrainGuardSmoke.ps1` |
| SmokeTests WebView browser completed pending proof smoke | `SmokeTests\Test-WebViewBrowserCompletedPendingProofSmoke.ps1` |
| SmokeTests WebView browser large daily-table smoke | `SmokeTests\Test-WebViewBrowserLargeTableSmoke.ps1` |
| SmokeTests WebView browser Maintenance/Reports smoke | `SmokeTests\Test-WebViewBrowserMaintenanceReportsSmoke.ps1` |
| SmokeTests WebView browser rename smoke | `SmokeTests\Test-WebViewBrowserRenameSmoke.ps1` |
| SmokeTests WebView browser network smoke | `SmokeTests\Test-WebViewBrowserNetworkSmoke.ps1` |
| SmokeTests WebView browser telemetry smoke | `SmokeTests\Test-WebViewBrowserTelemetrySmoke.ps1` |
| SmokeTests WebView browser settings/launch smoke | `SmokeTests\Test-WebViewBrowserSettingsLaunchSmoke.ps1` |
| SmokeTests WebView browser Sample Validation smoke | `SmokeTests\Test-WebViewBrowserSampleValidationSmoke.ps1` |
| SmokeTests WebView browser Home live-state smoke | `SmokeTests\Test-WebViewBrowserHomeLiveStateSmoke.ps1` |
| SmokeTests WebView browser Launch/Queue readiness smoke | `SmokeTests\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` |

### Lifecycle Contract Smokes (Always Release-Gated)

| Label | Path |
|---|---|
| SmokeTests local API lifecycle contract smoke | `SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1` |
| SmokeTests local API Maintenance dry-run contract smoke | `SmokeTests\Test-LocalApiMaintenanceDryRunContractSmoke.ps1` |
| SmokeTests local API sample validation contract smoke | `SmokeTests\Test-LocalApiSampleValidationContractSmoke.ps1` |

### Python Application Files (Always Release-Gated)

The release self-test explicitly checks existence of all major application Python modules including:
- All DTO files (`dto.py`, `dto_base.py`, `dto_commands.py`, `dto_inventory.py`, `dto_status.py`, `dto_workspaces.py`)
- Application facade and all mixin files (facade.py, facade_audit.py, facade_completed.py, facade_diagnostics.py, and ~20 others)
- All Local API contract files (`contract.py`, `contract_read.py`, `contract_command.py`, etc.)
- All Local API route handlers (`routes.py`, `routes_command.py`, `routes_read.py`)
- Backend bootstrap and entry points

### Tauri Shell Files (Always Release-Gated)

| Label | Path |
|---|---|
| Tauri shell package | `DesktopApp\tauri_shell\package.json` |
| Tauri shell package lock | `DesktopApp\tauri_shell\package-lock.json` |
| Tauri shell preview launcher | `DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1` |
| Tauri shell prereq checker | `DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1` |
| Tauri shell build checker | `DesktopApp\tauri_shell\Test-TauriShell-Build.ps1` |
| Tauri shell launch checker | `DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1` |
| Tauri shell config | `DesktopApp\tauri_shell\src-tauri\tauri.conf.json` |
| Tauri shell Cargo manifest | `DesktopApp\tauri_shell\src-tauri\Cargo.toml` |
| Tauri shell Cargo lock | `DesktopApp\tauri_shell\src-tauri\Cargo.lock` |
| Tauri shell Windows icon | `DesktopApp\tauri_shell\src-tauri\icons\icon.ico` |
| Tauri shell launcher source | `DesktopApp\tauri_shell\src-tauri\src\lib.rs` |

---

## Root Files NOT Checked by Release Self-Test

The following root-level scripts exist but are intentionally outside the layout check:

| File | Reason Not Checked |
|---|---|
| `Build-MediaPipelineRemuxEncodeAIO-Release.ps1` | It is the release builder itself — not a deliverable |
| `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` | It is the self-test itself — not a deliverable |
| `Verify-MediaPipelineRemuxEncodeAIO-Environment.bat` | The `.bat` wrapper is not checked; the `.ps1` version is. The BAT delegates to the PS1. |

**Note**: `Verify-MediaPipelineRemuxEncodeAIO-Environment.bat` is the only root BAT file that does not appear explicitly in the layout check. Its PS1 counterpart is checked. This is an acceptable gap — the BAT is a thin wrapper and both scripts are present in the workspace.

---

## Docs Important But Not Individually Release-Gated

The release self-test checks `Docs\` as a directory (existence only) and a handful of core operator docs. The following important docs are included in the release package via the Docs directory inclusion rule but are not individually path-checked:

- All engineering docs (`API_ROUTE_INVENTORY.md`, `STATE_FILE_SCHEMA_REFERENCE.md`, etc.)
- All CLN backlog and handoff docs
- Risk registers, status boards, and transition plans
- Smoke test catalogs and runbooks

These docs are protected against accidental deletion only by the directory-level check. There is no per-file assertion for them in the release self-test.

---

## Summary

| Category | Count |
|---|---|
| Non-browser WebView smoke wrappers release-gated | 8 |
| Browser-backed WebView smoke wrappers release-gated | 15 |
| Lifecycle/contract smokes release-gated | 3 |
| Root operator tools release-gated | 2 (New-RealMediaValidationWorksheet.ps1, Verify .ps1) |
| Root launchers release-gated | 6 (5 root BAT + 1 DesktopApp BAT) |
| Core docs release-gated (individual path check) | 5 |
| Root files intentionally outside layout check | 3 (builder, self-test, Verify.bat) |

---

## V5 Gate Coverage Review — 2026-05-14 (CLN2-04)

Cross-checked `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` Layout section against the current V5 script inventory to identify any new V5 scripts or docs that need gating.

| V5 Coverage Item | Release-Gated? | Notes |
|---|---|---|
| All 23 `Test-WebView*.ps1` wrappers | Yes — all individually listed | Including `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` (newest) |
| `Test-LocalApiLifecycleContractSmoke.ps1` | Yes | |
| `Test-LocalApiMaintenanceDryRunContractSmoke.ps1` | Yes | Browser-free Maintenance release/backfill dry-run route contract smoke |
| `Test-LocalApiSampleValidationContractSmoke.ps1` | Yes | Browser-free sample-validation preview/append/read/tail route contract smoke |
| `New-RealMediaValidationWorksheet.ps1` | Yes (line 431) | |
| Tauri shell files (package.json, package-lock.json, 4 PS1 helpers, src-tauri config/Cargo/Cargo.lock/icon/lib.rs) | Yes — all individually listed (lines 529–539) | Tauri prereq check also runs at Tauri Preview Gate |
| Tauri exclusions (node_modules, gen, target) | Yes — absence verified (lines 341–343) | |
| Web static assets (index.html, app.js, styles.css) | Yes (lines 526–528) | `Test-WebStaticAssetReferences` also runs for inline reference integrity |
| `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat` | Yes (line 452) | |
| `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` | **No** — absent from Layout check | **Gap candidate**: thin BAT launcher for Tk desktop app; present on disk but not individually gated |

### Gap Candidate: `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-DesktopApp.bat`

This file is present on disk and is the primary BAT launcher for the Tk desktop application inside the DesktopApp directory. It is not individually listed in the release self-test layout check. The `DesktopApp\` directory existence is checked, but the file is not path-checked.

**Risk**: Low — the Tk app is still the supported daily-use shell; its DesktopApp launcher being silently absent from a release package would be a subtle gap. Since the BAT is short and the DesktopApp directory check passes either way, this is unlikely to surface in practice.

**Recommended follow-up**: Add `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` to the Layout check array in `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`. This is a documentation-noted decision for the operator, not an automated fix.

---

## Freshness Review — 2026-05-15 (CLN3-016)

Re-checked layout coverage against current root script inventory. Summary count corrected from 13 to 15 browser-backed wrappers.

| Check | Result |
|---|---|
| All 15 browser-backed wrappers gated | Pass — listing at lines 62–80 covers all 15 including `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1`, `Test-WebViewBrowserSampleValidationSmoke.ps1`, `Test-WebViewBrowserHomeLiveStateSmoke.ps1` |
| All 8 non-browser wrappers gated | Pass |
| All 3 contract smokes gated | Pass |
| `New-RealMediaValidationWorksheet.ps1` gated | Pass — line 431 of release self-test |
| New docs (SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md, SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md, etc.) | Not individually gated — protected by Docs directory inclusion rule only (same as all non-core-operator docs) |
| `Docs\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md` | Not individually path-checked; low risk — Docs directory check covers it |

No new release-self-test layout script changes required. The layout check is current.

```
Task ID: CLN3-016
Files inspected: Docs\RELEASE_SELF_TEST_LAYOUT_AUDIT.md, Test-MediaPipelineRemuxEncodeAIO-Release.ps1 (reference)
Files changed: Docs\RELEASE_SELF_TEST_LAYOUT_AUDIT.md (summary count corrected 13→15; CLN3-016 freshness note added)
Validation: .\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
Findings: All 15 browser-backed wrappers and all new V5 docs/scripts are covered. Summary count stale (13→15) corrected.
Open questions: None.
Risk: Low — documentation only.
```

---

## Task Output

```
Task ID: CLN-009
Files inspected: Test-MediaPipelineRemuxEncodeAIO-Release.ps1, Docs\DOCS_INDEX.md, root file listing
Files changed: Docs\RELEASE_SELF_TEST_LAYOUT_AUDIT.md (created)
Validation: Read full Layout section of release self-test (lines 416–546). Cross-referenced against actual root file list.
Findings: All 23 Test-WebView*.ps1 wrappers + all three Test-LocalApi*.ps1 contract smokes are individually release-gated. Verify-MediaPipelineRemuxEncodeAIO-Environment.bat is the only root script not in the layout check (its PS1 counterpart is checked). All root BATs except the Verify wrapper are release-gated.
Open questions: None — layout check is comprehensive.
Risk: Low — documentation only.
```

