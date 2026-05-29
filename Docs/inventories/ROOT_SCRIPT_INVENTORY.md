# Canonical Script Inventory and Purpose Table

Date: 2026-05-20

Concise inventory of supported script entrypoints. Root launcher shims have been removed; smoke wrappers live under `SmokeTests/` and are inventoried in `Docs/inventories/SMOKE_TEST_INVENTORY.md`.

## Summary Counts

| Type | Count |
| --- | --- |
| `scripts/**/*.ps1` operator/release tools | 4 |
| `scripts/**/*.bat` launcher wrappers | 6 |
| `SmokeTests/*.ps1` files | 26 |
| **Canonical script total** | **10** |

## Release And Validation Tools (`.ps1`)

| Script | Purpose | Safe to run? | Mutates files? | Browser required? | Media required? | Duration |
| --- | --- | --- | --- | --- | --- | --- |
| `scripts\release\build.ps1` | Release builder. Copies workspace to a release folder with selective inclusions/exclusions. | Yes with `-DryRun`; caution otherwise | Yes without `-DryRun` | No | No | Long |
| `scripts\release\test.ps1` | Release self-test. Checks layout, parses scripts, verifies web assets, and runs selected gates. | Yes | No | No | No | Moderate to long |
| `scripts\operator\New-RealMediaValidationWorksheet.ps1` | Creates a timestamped real-media validation worksheet. | Yes | Yes, creates one `.md` worksheet | No | No | Fast |
| `scripts\verify-env.ps1` | Verifies runtime/tool layout: PowerShell, Python, FFmpeg, MKVToolNix, PgsToSrt. | Yes | No | No | No | Fast |

## Launchers (`.bat`)

| Script | Purpose | Safe to run? | Mutates files/state? | Notes |
| --- | --- | --- | --- | --- |
| `scripts\dev\start-api-and-browser.bat` | Starts the local API and opens the backend-served WebView in a browser. | Caution | Yes, backend commands can write state/logs after operator action | V6 WebView launcher. |
| `scripts\dev\run.bat` | Runs the pipeline directly without desktop UI. | Caution | Yes, may process/rename/move media | Highest-risk root launcher. |
| `scripts\dev\setup.bat` | First-run/re-run setup and directory/config validation. | Yes | Yes, creates/updates setup artifacts | Idempotent setup path. |
| `scripts\verify-env.bat` | BAT wrapper for the environment verifier. | Yes | No | Thin wrapper. |
| `scripts\dev\start-local-api.bat` | Starts the local API backend for browser/Tauri work. | Yes | Usually read-only serve path | Does not process media by itself. |
| `scripts\dev\start-tauri-preview.bat` | Starts the Tauri/WebView2 shell. | Caution | Backend commands can write state/logs after operator action | V6 native shell path. |

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
| `scripts\dev\run.bat` | High | Runs the real pipeline and may process/move media depending on config. |
| `scripts\release\build.ps1` without `-DryRun` | Medium | Copies a full release folder. |
| `scripts\dev\start-api-and-browser.bat` | Medium | Starts the live API/WebView surface with live config; backend commands can write state/logs. |
| Smoke wrappers under `SmokeTests/` | Low | Bounded validation wrappers; generated/temp state unless documented otherwise. |
| Other canonical scripts | Low | Read-only or bounded setup/preview actions. |
