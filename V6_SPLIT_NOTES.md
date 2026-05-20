# V6 Split Notes

Last updated: 2026-05-20

## Purpose

This folder is the V6 WebView-first split from the V5 transition workspace. V5 remains available externally as the rollback/fallback workspace. V6 keeps the backend media pipeline, Python local API, WebView assets, Tauri/WebView2 shell, docs, tests, smoke wrappers, bundled tools, and runtime dependencies needed to continue the WebView/Tauri refinement work.

## What Was Left Behind

- Removed root and desktop legacy GUI launchers.
- Removed `DesktopApp\mediapipeline_desktop_app\app.py`, `ui.py`, `widgets.py`, `workers.py`, `theme.py`, and the legacy GUI `controllers\` and `views\` packages.
- Legacy PowerShell GUI launcher scripts under `Pipeline\MediaPipelineRemuxEncodeAIO_LegacyGUI.*`.
- Removed legacy desktop-shell unit tests.
- Removed copied legacy GUI framework site-package files from the V6 bundled Python runtime.

## What Remains Authoritative

- Backend media policy stays in `Pipeline\` PowerShell modules and Python backend services.
- WebView remains a control, evidence, and monitoring surface. It must not implement filesystem mutation, route decisions, queue inclusion policy, publish/drain safety, subtitle/audio policy, or output acceptance independently.
- Source media must not be mutated or deleted by default. Scratch-copy-first behavior and pending-publish manifest evidence remain release-critical.
- V5 is the external fallback for any operator flow not yet validated in V6.

## Validation Performed

```powershell
.\DesktopApp\Runtime\Python\python.exe -m py_compile .\DesktopApp\mediapipeline_desktop_app\__init__.py .\DesktopApp\mediapipeline_desktop_app\__main__.py .\DesktopApp\mediapipeline_desktop_app\local_api_main.py .\DesktopApp\mediapipeline_desktop_app\services.py
node --check .\DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js
node --check .\DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\networkView.js
node --check .\DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.builders.network.js
node --check .\DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\scheduleView.js
node --check .\DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Unit\Invoke-PortablePathChecks.ps1
.\DesktopApp\Runtime\Python\python.exe -m unittest discover -s DesktopApp\tests -p "test_*.py" -q
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\DesktopApp\tauri_shell\Test-TauriShell-ProductionSurface.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1 -CheckOnly
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\DesktopApp\tauri_shell\Test-TauriShell-Build.ps1 -SkipLinkCheck
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Result: all commands above passed. The broad Python suite reported `1131 tests OK`; the Tauri build gate reported `21 passed` Rust tests. Current V6 release validation now runs the WebView/backend reliability wrapper by default; archived legacy desktop-shell checks require the explicit `-RunLegacyDesktopChecks` switch.

## Live API Proof

The V6 local API was restarted on `http://127.0.0.1:11992` with token `codex-v6-split-verify-20260520`.

Verified:

- `/api/health`: `status=ok`, `app_version=v6.000`
- `/`: 200
- `/assets/app.js`: 200
- `/assets/networkView.js`: 200
- `/api/contract`: 200
- `/api/queue`: 200

## Follow-Up Before Promotion

- Run representative real-media V6 pilot processing from the WebView/Tauri path.
- Build a clean deployable V6 package and run package-mode Tauri launch/close.
- Reconcile older V5/legacy-desktop historical docs only when they are touched for active work; archive-only docs can remain historical.
