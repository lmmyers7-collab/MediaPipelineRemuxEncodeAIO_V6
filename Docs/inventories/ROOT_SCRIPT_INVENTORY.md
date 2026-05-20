# Root Script Inventory and Purpose Table

Date: 2026-05-20

Concise inventory of root-level `.ps1` and `.bat` scripts. Smoke wrappers no longer live at repository root; they were moved to `SmokeTests/` and are inventoried in `Docs/inventories/SMOKE_TEST_INVENTORY.md`.

## Summary Counts

| Type | Count |
| --- | --- |
| Root `.ps1` files | 4 |
| Root `.bat` files | 6 |
| `SmokeTests/*.ps1` files | 26 |
| **Root total** | **10** |

## Root Release And Validation Tools (`.ps1`)

| Script | Purpose | Safe to run? | Mutates files? | Browser required? | Media required? | Duration |
| --- | --- | --- | --- | --- | --- | --- |
| `Build-MediaPipelineRemuxEncodeAIO-Release.ps1` | Release builder. Copies workspace to a release folder with selective inclusions/exclusions. | Yes with `-DryRun`; caution otherwise | Yes without `-DryRun` | No | No | Long |
| `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` | Release self-test. Checks layout, parses scripts, verifies web assets, and runs selected gates. | Yes | No | No | No | Moderate to long |
| `New-RealMediaValidationWorksheet.ps1` | Creates a timestamped real-media validation worksheet. | Yes | Yes, creates one `.md` worksheet | No | No | Fast |
| `Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1` | Verifies runtime/tool layout: PowerShell, Python, FFmpeg, MKVToolNix, PgsToSrt. | Yes | No | No | No | Fast |

## Root Launchers (`.bat`)

| Script | Purpose | Safe to run? | Mutates files/state? | Notes |
| --- | --- | --- | --- | --- |
| `Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat` | Starts the local API and opens the backend-served WebView in a browser. | Caution | Yes, backend commands can write state/logs after operator action | V6 WebView launcher. |
| `Run-MediaPipelineRemuxEncodeAIO.bat` | Runs the pipeline directly without desktop UI. | Caution | Yes, may process/rename/move media | Highest-risk root launcher. |
| `Setup-MediaPipelineRemuxEncodeAIO.bat` | First-run/re-run setup and directory/config validation. | Yes | Yes, creates/updates setup artifacts | Idempotent setup path. |
| `Verify-MediaPipelineRemuxEncodeAIO-Environment.bat` | BAT wrapper for the environment verifier. | Yes | No | Thin wrapper. |
| `Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat` | Starts the local API backend for browser/Tauri work. | Yes | Usually read-only serve path | Does not process media by itself. |
| `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat` | Starts the Tauri/WebView2 shell. | Caution | Backend commands can write state/logs after operator action | V6 native shell path. |

## Dedicated Smoke Folder

Smoke wrappers are now under `SmokeTests/`:

- `SmokeTests/Test-WebView*.ps1`
- `SmokeTests/Test-LocalApi*.ps1`

Run examples:

```powershell
.\SmokeTests\Test-WebViewRowDetailSmoke.ps1
.\SmokeTests\Test-WebViewRenameReadinessSmoke.ps1
.\SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1
.\SmokeTests\Test-WebViewBrowserHighRiskSmoke.ps1
```

See `Docs/inventories/SMOKE_TEST_INVENTORY.md` for the complete list, purpose, underlying unittest/module, and mutation boundary for every wrapper.

## Danger Summary

| Script | Risk Level | Reason |
| --- | --- | --- |
| `Run-MediaPipelineRemuxEncodeAIO.bat` | High | Runs the real pipeline and may process/move media depending on config. |
| `Build-MediaPipelineRemuxEncodeAIO-Release.ps1` without `-DryRun` | Medium | Copies a full release folder. |
| `Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat` | Medium | Starts the live API/WebView surface with live config; backend commands can write state/logs. |
| Smoke wrappers under `SmokeTests/` | Low | Bounded validation wrappers; generated/temp state unless documented otherwise. |
| Other root scripts | Low | Read-only or bounded setup/preview actions. |
