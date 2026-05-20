# Claude Handoff: Root Rename Readiness Smoke Wrapper

> Archive status: completed handoff. `Test-WebViewRenameReadinessSmoke.ps1` exists, is release-gated, and remains documented with the WebView smoke wrappers. Keep this file as historical task context only.

## Purpose

Add a low-risk root smoke-test wrapper for the existing WebView Rename readiness test so operators can run it the same way they run the other WebView validation scripts.

This is intentionally a small administrative/coding task with limited dependencies. It should not touch media policy, FFmpeg behavior, queue processing, pending publish, backend mutation commands, Tk fallback, or V4.

## Repository

Work only in:

`C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5`

Do not modify:

- `MediaPipelineRemuxEncodeAIO_V4`
- FFmpeg/PowerShell pipeline behavior
- Tk fallback behavior
- Local API command contracts
- Rename backend planning/apply logic
- Any source/output/scratch media files

## Background

The repo already has:

- `DesktopApp\tests\test_webview_rename_readiness_smoke.py`
  - Node-backed mocked-DOM smoke.
  - Verifies Rename Apply Readiness for a ready single-row scope and a blocked duplicate-target scope.
  - Verifies duplicate-target readiness blocking does not post to `/api/rename/apply`.
- `Test-WebViewBrowserRenameSmoke.ps1`
  - Browser-backed Chrome/Edge smoke.
  - Starts a temporary local API and drives the real WebView page.

Missing piece:

- There is no root PowerShell wrapper for the faster non-browser readiness smoke.

## Task

Create a root-level wrapper:

`Test-WebViewRenameReadinessSmoke.ps1`

The wrapper should follow the style of existing `SmokeTests/` wrappers such as:

- `Test-WebViewCommandEvidenceSmoke.ps1`
- `Test-WebViewRowDetailSmoke.ps1`
- `Test-WebViewBrowserRenameSmoke.ps1`

It should:

1. Resolve Python from:
   - `DesktopApp\Runtime\Python\python.exe`
   - `Pipeline\Runtime\Python\python.exe`
   - `python` on PATH
2. Print explicit boundary text:
   - It evaluates WebView Rename assets in Node/mocked DOM state.
   - It verifies Apply Readiness ready and duplicate-target blocked scopes.
   - It verifies duplicate-target blocking does not call `rename.apply`.
   - It does not process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or touch source/output/scratch media.
3. Set:
   - `$env:PYTHONDONTWRITEBYTECODE = '1'`
4. Run:
   - `python -m unittest DesktopApp.tests.test_webview_rename_readiness_smoke -q`
5. Exit nonzero if the unittest exits nonzero.

## Required Supporting Updates

Update release/layout coverage:

- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
  - Add a layout entry near the other root WebView smoke scripts:
    - Label: `SmokeTests WebView rename readiness smoke`
    - Path: `Test-WebViewRenameReadinessSmoke.ps1`

Update static scaffold tests:

- `DesktopApp\tests\test_tauri_shell_scaffold.py`
  - Add assertions that release self-test references:
    - `SmokeTests WebView rename readiness smoke`
    - `Test-WebViewRenameReadinessSmoke.ps1`
  - Add a bounded-script test similar to the existing browser/smoke wrapper tests.
  - The test should assert the script includes:
    - `DesktopApp.tests.test_webview_rename_readiness_smoke`
    - `Apply Readiness`
    - `duplicate-target`
    - `does not process media`
    - `launch pipeline commands`
    - `publish, rename files, save settings`
    - `mutate queue state`
    - `DesktopApp\Runtime\Python\python.exe`
    - `Pipeline\Runtime\Python\python.exe`
    - `$env:PYTHONDONTWRITEBYTECODE = '1'`
  - The test should assert the script does not include:
    - `Remove-Item`
    - `Start-Process`
    - `/api/rename/apply`
    - `/api/settings/save-patch`
    - `/api/pending-publish/drain`

Update docs:

- `Docs\DOCS_INDEX.md`
  - Add one bullet for `Test-WebViewRenameReadinessSmoke.ps1`.
- `Docs\TLDR.md`
  - In the fast checks / WebView smoke section, add a short block explaining how to run:
    - `.\SmokeTests\Test-WebViewRenameReadinessSmoke.ps1`
  - Make the non-mutation boundary explicit.
- `Docs\REMEDIATION_CHANGELOG.md`
  - Add a short top entry with files changed and validation run.

Do not update broad planning docs unless necessary. This is a wrapper/documentation task, not a new parity feature.

## Forbidden Changes

Do not:

- Modify `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\renameView.js`.
- Modify `DesktopApp\tests\test_webview_rename_readiness_smoke.py` unless a clear typo blocks wrapper execution.
- Modify Local API routes, command payloads, command journal, rename service files, or pipeline PowerShell modules.
- Add a new Node package, Playwright, Puppeteer, npm dependency, or browser dependency.
- Add any filesystem mutation from frontend code.
- Call `/api/rename/apply` from the new wrapper or smoke.
- Make the release self-test run the smoke automatically; add only the layout/file-existence gate unless the existing release self-test pattern clearly does otherwise.

## Validation Commands

Run from repo root:

```powershell
python -m py_compile DesktopApp\tests\test_tauri_shell_scaffold.py
python -m unittest DesktopApp.tests.test_webview_rename_readiness_smoke DesktopApp.tests.test_tauri_shell_scaffold -q
.\SmokeTests\Test-WebViewRenameReadinessSmoke.ps1
```

If time allows, also run:

```powershell
Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

## Definition Of Done

- `Test-WebViewRenameReadinessSmoke.ps1` exists at repo root.
- The wrapper runs and passes.
- Release self-test layout includes the wrapper.
- Static scaffold tests cover the wrapper and release layout entry.
- Docs mention the new wrapper.
- No backend, frontend, media, FFmpeg, Tk, or V4 behavior changed.

## Expected Final Response From Claude

Use this exact structure:

```text
Changed:
Tests run:
Result:
Risks/assumptions:
Files modified:
```

Mention any skipped validation explicitly.

## Codex Verification Checklist

After Claude finishes, Codex should verify:

- `rg -n "Test-WebViewRenameReadinessSmoke|SmokeTests WebView rename readiness smoke" .`
- `python -m unittest DesktopApp.tests.test_webview_rename_readiness_smoke DesktopApp.tests.test_tauri_shell_scaffold -q`
- `.\SmokeTests\Test-WebViewRenameReadinessSmoke.ps1`
- Release self-test if not already run by Claude.

