# Canonical Script Inventory and Purpose Table

Date: 2026-05-20

Concise inventory of supported script entrypoints. Root launcher shims have been removed; smoke wrappers live under `ops/scripts/smoke/` and are inventoried in `docs/inventories/SMOKE_TEST_INVENTORY.md`.

## Summary Counts

| Type | Count |
| --- | --- |
| `scripts/**/*.ps1` operator/release/dev tools | 7 |
| `scripts/**/*.bat` launcher wrappers | 6 |
| `ops/scripts/smoke/*.ps1` files | 26 |
| **Canonical script total** | **13** |

## Release And Validation Tools (`.ps1`)

| Script | Purpose | Safe to run? | Mutates files? | Browser required? | Media required? | Duration |
| --- | --- | --- | --- | --- | --- | --- |
| `ops\scripts\release\build.ps1` | Release builder. Copies workspace to a release folder with selective inclusions/exclusions. | Yes with `-DryRun`; caution otherwise | Yes without `-DryRun` | No | No | Long |
| `ops\scripts\release\test.ps1` | Release self-test. Checks layout, parses scripts, verifies web assets, and runs selected gates. | Yes | No | No | No | Moderate to long |
| `ops\scripts\release\Initialize-CiPythonRuntime.ps1` | Provisions the expected bundled Python runtime layout from CI's setup-python interpreter for release validation jobs. | Yes in CI; caution locally with `-Force` | Yes, creates or updates runtime folders | No | No | Moderate |
| `ops\scripts\operator\New-RealMediaValidationWorksheet.ps1` | Creates a timestamped real-media validation worksheet. | Yes | Yes, creates one `.md` worksheet | No | No | Fast |
| `ops\scripts\dev\verify-env.ps1` | Verifies runtime/tool layout: PowerShell, Python, FFmpeg, MKVToolNix, PgsToSrt. | Yes | No | No | No | Fast |
| `ops\scripts\dev\check-github-audit-spine.ps1` | Validates local GitHub audit-spine files, labels, workflows, and AI templates. | Yes | No | No | No | Fast |
| `ops\scripts\dev\bootstrap-github-audit-spine.ps1` | Dry-runs or applies GitHub audit labels from `.github\audit-labels.json`. | Yes in dry-run; caution with `-Apply` | No local file mutation; `-Apply` mutates GitHub labels | No | No | Fast |

## Launchers (`.bat`)

| Script | Purpose | Safe to run? | Mutates files/state? | Notes |
| --- | --- | --- | --- | --- |
| `ops\scripts\dev\start-api-and-browser.bat` | Starts the local API and opens the backend-served WebView in a browser. | Caution | Yes, backend commands can write state/logs after operator action | current WebView launcher. |
| `ops\scripts\dev\run.bat` | Runs the pipeline directly without desktop UI. | Caution | Yes, may process/rename/move media | Highest-risk root launcher. |
| `ops\scripts\dev\setup.bat` | First-run/re-run setup and directory/config validation. | Yes | Yes, creates/updates setup artifacts | Idempotent setup path. |
| `ops\scripts\dev\verify-env.bat` | BAT wrapper for the environment verifier. | Yes | No | Thin wrapper. |
| `ops\scripts\dev\start-local-api.bat` | Starts the local API backend for browser/Tauri work. | Yes | Usually read-only serve path | Does not process media by itself. |
| `ops\scripts\dev\start-tauri-preview.bat` | Starts the Tauri/WebView2 shell. | Caution | Backend commands can write state/logs after operator action | native shell path. |

## Dedicated Smoke Folder

Smoke wrappers are now under `ops/scripts/smoke/`:

- `ops/scripts/smoke/Test-WebView*.ps1`
- `ops/scripts/smoke/Test-LocalApi*.ps1`

Run examples:

```powershell
.\ops/scripts/smoke\Test-WebViewRowDetailSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRenameReadinessSmoke.ps1
.\ops/scripts/smoke\Test-LocalApiLifecycleContractSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserHighRiskSmoke.ps1
```

See `docs/inventories/SMOKE_TEST_INVENTORY.md` for the complete list, purpose, underlying unittest/module, and mutation boundary for every wrapper.

## Danger Summary

| Script | Risk Level | Reason |
| --- | --- | --- |
| `ops\scripts\dev\run.bat` | High | Runs the real pipeline and may process/move media depending on config. |
| `ops\scripts\release\build.ps1` without `-DryRun` | Medium | Copies a full release folder. |
| `ops\scripts\dev\start-api-and-browser.bat` | Medium | Starts the live API/WebView surface with live config; backend commands can write state/logs. |
| Smoke wrappers under `ops/scripts/smoke/` | Low | Bounded validation wrappers; generated/temp state unless documented otherwise. |
| `ops\scripts\dev\bootstrap-github-audit-spine.ps1 -Apply` | Low | Mutates GitHub labels in the selected remote repository; dry-run is read-only. |
| Other canonical scripts | Low | Read-only or bounded setup/preview actions. |
