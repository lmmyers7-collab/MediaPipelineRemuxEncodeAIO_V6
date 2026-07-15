# Packaging Dependency Inventory

Documents bundled and external dependencies relevant to packaging, validation, and admin work. Use this when setting up a new machine, troubleshooting missing tools, or verifying a release package.

This document does not install or verify tools. To check tool availability, run `ops\scripts\dev\verify-env.bat`.

---

## Bundled Dependencies (Included in Release Package)

These are shipped with the package and do not require a separate install.

### Bundled PowerShell 7.6.0

| Field | Value |
|---|---|
| Role | Primary runtime for all pipeline, test, and build scripts |
| Status | Bundled |
| Expected path | `ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe` |
| Checked by | `ops\scripts\dev\verify-env.bat`, release self-test |
| Failure symptom | Scripts fall back to system `pwsh`; if system `pwsh` is also absent, scripts throw with a human-readable error |
| Notes | Scripts that detect PS5 re-invoke under `pwsh`; batch wrappers resolve `pwsh.exe` with bundled-first, cmd-native discovery and do not execute through `powershell.exe` |

See `docs/operator/POWERSHELL_HOST_EXPECTATIONS.md` for full resolution order and prohibited patterns.

### Bundled Python (DesktopApp Runtime)

| Field | Value |
|---|---|
| Role | Local API runtime, backend-served WebView runner, WebView smoke test runner |
| Status | Bundled |
| Expected paths | `apps\desktop\runtime\Python\python.exe`, `apps\desktop\runtime\Python\pythonw.exe` |
| Checked by | `ops\scripts\dev\verify-env.bat`, release self-test |
| Failure symptom | Local API/WebView fails to launch; smoke wrappers fail to find Python; all Python tests unavailable |
| Required packages | `psutil`, `pysubs2`, `packaging`, `darkdetect` |

### Bundled FFmpeg

| Field | Value |
|---|---|
| Role | Video/audio remux and encode, subtitle probing |
| Status | Bundled |
| Expected path | `ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe`, `ffprobe.exe` |
| Checked by | `ops\scripts\dev\verify-env.bat`, `Invoke-ToolIntegrationChecks.ps1` |
| Failure symptom | Pipeline cannot process media; all encodes and remuxes fail |
| Optional | `ffplay.exe` excluded from default release (include with `-IncludeOptionalTools`) |

### Bundled MKVToolNix

| Field | Value |
|---|---|
| Role | MKV container inspection and subtitle extraction (`mkvmerge`) |
| Status | Bundled (core tool) |
| Expected path | `ops\pipeline\tools\MKVToolNix\mkvmerge.exe` |
| Checked by | `ops\scripts\dev\verify-env.bat`, `Invoke-ToolIntegrationChecks.ps1` |
| Failure symptom | MKV subtitle extraction fails; pipeline falls back or errors |
| Optional | GUI, `mkvextract`, `mkvinfo`, `mkvpropedit`, GUI assets excluded from default release |

### Bundled PgsToSrt and tessdata (OCR)

| Field | Value |
|---|---|
| Role | BDPGS subtitle OCR conversion (PGS → SRT) |
| Status | Bundled (optional capability — only active if `ConvertBdpgsToSrt` is enabled in config) |
| Expected path | `ops\pipeline\tools\PgsToSrt\PgsToSrt.exe` (or similar), `ops\pipeline\tools\PgsToSrt\tessdata\eng.traineddata` |
| Checked by | `ops\scripts\dev\verify-env.bat` (when OCR enabled in config) |
| Failure symptom | BDPGS OCR silently skipped or errors; SRT not produced for Blu-ray PGS subtitles |
| Config keys | `BdpgsOcrToolPath`, `BdpgsOcrTessdataPath` (raw/advanced keys — must match actual paths) |

---

## External Dependencies (Not Bundled — Operator-Installed)

These must be installed separately and are not included in the release package.

### Node.js

| Field | Value |
|---|---|
| Role | WebView smoke test runner (both browser-backed and non-browser smokes) |
| Status | External — must be on operator PATH |
| Minimum version | Node 18+ (required for global `WebSocket` in scope) |
| Check | `node --version` |
| Checked by | Smoke wrappers (`Test-WebView*.ps1`) check for `node` before running |
| Failure symptom | A direct Python smoke may report `SkipTest`; canonical PowerShell wrappers fail that prerequisite skip unless explicitly invoked with `-AllowSkippedTests` |
| Notes | Not required for pipeline operation — only for WebView validation |

### Chrome or Edge (for browser-backed smokes)

| Field | Value |
|---|---|
| Role | Browser-backed WebView smoke tests via Chrome DevTools Protocol (CDP) |
| Status | External — must be installed for canonical browser-smoke validation |
| Required version | Any modern Chrome or Edge (no specific version requirement beyond CDP support) |
| Check | `Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe"` |
| Checked by | Browser smoke wrappers at startup |
| Failure symptom | The Python module reports `SkipTest: Chrome or Edge is required`; the canonical wrapper converts that prerequisite skip into a failure unless `-AllowSkippedTests` was explicitly requested |
| Notes | No Playwright or Puppeteer install needed; smokes use CDP directly |

See `docs/testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md` for full browser discovery diagnostics.

### Tauri Prerequisites (for Tauri shell build)

These are only needed when building the Tauri/WebView2 shell (`apps\desktop\tauri\`) from source. Operators who use pre-built shells do not need these.

| Dependency | Role | Check |
|---|---|---|
| Node.js (see above) | npm package management for Tauri WebView assets | `node --version` |
| npm | Package installation for Tauri build | `npm --version` |
| Rust / Cargo | Builds the Tauri shell binary | `cargo --version` |
| Tauri CLI | Tauri build tool | `cargo tauri --version` or `npx tauri --version` |

Check Tauri prereqs without building:

```powershell
.\ops\scripts\dev\start-tauri-preview.bat -CheckOnly
```

The release self-test verifies Tauri prerequisite availability:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1
```

#### Tauri Linux GTK/glib advisory posture

Reviewed 2026-07-11 against the locked graph, a normal Cargo update in an
isolated copy, current crates.io releases, and the upstream Tauri/Wry `dev`
manifests.

| Field | Verified state |
|---|---|
| Advisory | `GHSA-wrw7-89jp-8q8g` / `RUSTSEC-2024-0429`; `glib >=0.15,<0.20` is affected and `0.20.0` is the first patched release |
| Repository lock | `tauri 2.11.1` -> `tauri-runtime-wry 2.11.1` -> `wry 0.55.1` -> Linux-only `gtk 0.18.2` -> `glib 0.18.5` |
| Latest normal compatible resolution tested | `tauri 2.11.5` -> `tauri-runtime-wry 2.11.4` -> `wry 0.55.1` -> Linux-only `gtk 0.18.2` -> `glib 0.18.5`; alert remains |
| Current upstream dependency constraint | Tauri, tauri-runtime-wry, and Wry `dev` manifests still require GTK `0.18`; GTK 0.18 requires glib `0.18` |
| Windows application | Not affected by this GTK/glib chain. The Windows target resolves Wry to WebView2 and does not include GTK or glib. |
| Linux packaging | Affected if a Linux GTK/WebKit package is built; this repository's current Windows portable ZIP lane does not ship that target. |
| Exposure note | The advisory is an unsoundness in `glib::VariantStrIter`. The application has no direct glib dependency, and a static scan found no `VariantStrIter` references in current Tauri, tauri-runtime-wry, Wry, or GTK sources. This lowers observed reachability but is not proof that all indirect runtime paths are unreachable. |
| Required action | Do not force glib 0.20 with a patch or override. Re-test when Tauri/Wry moves off GTK 0.18, before adding Linux packaging, or by 2026-08-07, whichever comes first. |

The detailed decision record and upgrade trigger are in
`docs/inventories/RELEASE_DEPENDENCY_REVIEW.md`.

---

## Browser Smoke Skip Behavior

The repository currently has **24 canonical browser wrappers** and **26 browser-backed Python modules** under `ops\scripts\smoke\` and `tests\webview\`, respectively. The two additional direct modules are `test_webview_browser_metrics_degraded_state_smoke.py` and `test_webview_browser_settings_builder_flush_smoke.py`; they are exercised directly or through broader gates rather than one-to-one wrappers.

Browser-backed Python modules may emit a `SkipTest:` result when Node.js, Chrome, Edge, or another declared prerequisite is unavailable. Canonical `Test-WebViewBrowser*.ps1` wrappers fail such prerequisite skips by default so a green wrapper is positive evidence that browser assertions executed. Use `-AllowSkippedTests` only when intentionally collecting a non-gating environmental result, and record the skip reason.

The 24 wrappers include the lifecycle, lifecycle-reconciliation, Queue file-overrides, Queue→Launch→Completed, Settings launch, Settings field-matrix, Library Profiles save, Prose Box audit, and Visual Clutter screenshot surfaces. See `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md` and `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md` for the complete command inventory.

Non-browser WebView smokes (`Test-WebViewRealMediaEvidenceSmoke.ps1`, `Test-WebViewCommandEvidenceSmoke.ps1`, `Test-WebViewRowDetailSmoke.ps1`, `Test-WebViewScheduleSmoke.ps1`, `Test-WebViewRenameReadinessSmoke.ps1`, `Test-WebViewSettingsLaunchPolicySmoke.ps1`, `Test-WebViewSettingsLaunchLiveConfigSmoke.ps1`, `Test-WebViewSettingsPatchEvidenceSmoke.ps1`) require Python and, where the smoke evaluates WebView JavaScript, Node.js. They are suitable for lightweight automated checks and do not require Chrome/Edge.

`Test-LocalApiLifecycleContractSmoke.ps1` is not a WebView smoke. It requires Python only and validates the token-protected close-readiness/shutdown route contract against temporary local API instances.

---

## Version Verification

To verify all bundled dependencies:

```powershell
.\ops\scripts\dev\verify-env.bat
```

To see tool versions in the release manifest after building a package:

```powershell
Get-Content release_manifest.json | ConvertFrom-Json | Select-Object bundled_tools, python_packages
```

---

## Dependency Inventory Summary

| Dependency | Bundled | Required for pipeline? | Required for WebView smokes? | Required for Tauri build? |
|---|---|---|---|---|
| PowerShell 7.6.0 | Yes | Yes | Yes (test runners) | No |
| Python (DesktopApp Runtime) | Yes | Yes (desktop app) | Yes | No |
| FFmpeg / ffprobe | Yes | Yes | No | No |
| MKVToolNix (mkvmerge) | Yes | Yes | No | No |
| PgsToSrt / tessdata | Yes | Only if OCR enabled | No | No |
| Node.js | No | No | Yes | Yes |
| Chrome or Edge | No | No | Browser smokes only; canonical wrappers fail prerequisite skips unless explicitly allowed | No |
| Rust / Cargo | No | No | No | Yes |
| npm | No | No | No | Yes |

---

## See Also

- PowerShell host expectations: `docs/operator/POWERSHELL_HOST_EXPECTATIONS.md`
- Browser smoke prerequisites: `docs/testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md`
- Release package inventory: `docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`
- Environment verification script: `ops\scripts\dev\verify-env.bat`
