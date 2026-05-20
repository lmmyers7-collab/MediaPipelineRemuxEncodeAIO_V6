# MediaPipeline Tauri/WebView2 Shell

This folder contains the V6 Tauri/WebView2 shell.

V6 is the WebView-first workspace. The V5 workspace remains the external fallback if this split needs to be rolled back. The shell is intentionally thin:

1. Start the bundled Python backend through `mediapipeline_desktop_app.local_api_main`.
2. Read the backend bootstrap JSON from stdout.
3. Open the backend-served web UI in a Tauri/WebView2 window.
4. Keep media logic, process control, settings, rename, queue, telemetry, and diagnostics owned by the Python backend.

## Current Status

- The web UI is still served by `LocalApiServer`.
- The shell does not own FFmpeg, PowerShell, queue state, config writes, rename apply, or pending publish behavior.
- Mutation workflows remain backend-owned through local API commands.
- Native close-readiness prompts include structured schedule-stop watcher evidence when the backend reports it, and the startup asset gate checks for the WebView Backend Lifecycle/Close Readiness shutdown guard before opening the preview window.
- Network coordinator/worker lifecycle controls are not exposed through this shell.
- This V6 folder no longer carries the removed legacy desktop-shell surface.

## Validation Ladder

Run these from the project root when validating the shell:

1. Check the basic preview layout and local API module:

```powershell
.\Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat -CheckOnly
```

2. Run the Tauri build gate. This checks WebView JavaScript syntax, cargo check, and Rust shell unit tests:

```powershell
.\DesktopApp\tauri_shell\Test-TauriShell-Build.ps1 -SkipLinkCheck
```

3. Run the fixture-backed WebView evidence smoke. This starts a temporary local API against generated state and verifies the backend-served WebView evidence path without processing media or issuing mutation commands:

```powershell
.\SmokeTests\Test-WebViewRealMediaEvidenceSmoke.ps1
```

4. Run the WebView command evidence smoke. This starts a temporary local API, evaluates backend-served WebView JavaScript with mocked DOM state, and verifies shared command owner/issue evidence across daily-use panels without issuing mutation commands:

```powershell
.\SmokeTests\Test-WebViewCommandEvidenceSmoke.ps1
```

5. Run the WebView row-detail smoke. This starts a temporary local API, evaluates backend-served WebView JavaScript with mocked DOM selected-row state, and verifies Queue, Completed, and Pending Publish selected-row details plus diagnostics handoff text without issuing mutation commands:

```powershell
.\SmokeTests\Test-WebViewRowDetailSmoke.ps1
```

6. Run the WebView schedule smoke. This evaluates Schedule WebView assets in Node with mocked DOM state and verifies Schedule Coverage Review, selected day detail, table status legend, Schedule Editor preview/save routing, and backend-owned mutation guardrails:

```powershell
.\SmokeTests\Test-WebViewScheduleSmoke.ps1
```

7. Run the browser-backed Schedule smoke. This starts a temporary local API, launches installed Chrome/Edge headless, drives real backend-served Schedule and Launch controls, verifies Schedule Editor preview/save routing, confirmed backend app-state write, command-history ownership, and refreshed Launch timing trust. It skips cleanly when Chrome/Edge is not installed:

```powershell
.\SmokeTests\Test-WebViewBrowserScheduleSmoke.ps1
```

8. Run the browser-backed backend lifecycle smoke. This starts temporary local API instances, launches installed Chrome/Edge headless, verifies close-readiness blocks shutdown while the continuous schedule-stop watcher is armed, and verifies safe close-readiness posts only through backend-owned `/api/backend/shutdown` after confirmation. It skips cleanly when Chrome/Edge is not installed:

```powershell
.\SmokeTests\Test-WebViewBrowserLifecycleSmoke.ps1
```

For the same backend close-readiness/shutdown route contract without a browser dependency, run the local API lifecycle contract smoke. It validates safe and watcher-blocked payloads plus token enforcement against temporary test backends only:

```powershell
.\SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1
```

For browser-free Maintenance dry-run route coverage, run the local API Maintenance dry-run contract smoke. It validates token enforcement, release dry-run no-manifest/no-zip evidence, completed-manifest backfill dry-run no-manifest-write evidence, command history, and unchanged temp source/output bytes:

```powershell
.\SmokeTests\Test-LocalApiMaintenanceDryRunContractSmoke.ps1
```

For browser-free sample-validation route coverage, run the local API sample validation contract smoke. It validates token enforcement, preview/append strict JSON handling, current-backend-evidence preview, validation-log readback, diagnostics tail allowlist, and command history against temporary state only:

```powershell
.\SmokeTests\Test-LocalApiSampleValidationContractSmoke.ps1
```

9. Run the browser-backed high-risk row smoke. This starts a temporary local API, launches installed Chrome/Edge headless, loads the real backend-served WebView page, and verifies injected plus backend-produced blocked Queue, broken Completed, and do-not-drain Pending Publish selected-row guidance without issuing mutation commands. It skips cleanly when Chrome/Edge is not installed:

```powershell
.\SmokeTests\Test-WebViewBrowserHighRiskSmoke.ps1
```

10. Run the browser-backed diagnostics handoff smoke. This starts a temporary local API, launches installed Chrome/Edge headless, clicks actual Queue/Completed/Pending table rows, verifies selected-row investigation signals and current-filter visibility, verifies text/status/investigation table filters warn when blocked/warning rows are hidden, verifies local clear-filter buttons restore selected-row visibility without backend mutation commands, then clicks read-only diagnostics bridge, tail, and allowlisted open controls, and verifies selected-row detail, bounded tail output, plus diagnostics.open command-result feedback without issuing mutation commands. It skips cleanly when Chrome/Edge is not installed:

```powershell
.\SmokeTests\Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1
```

11. Run the browser-backed Pending Publish drain guard smoke. This starts a temporary local API, launches installed Chrome/Edge headless, injects a backend-shaped blocked recovery dry-run result, verifies the Publish Button Guard refreshes immediately, and proves a blocked Publish Parked Outputs click records local frontend guard evidence without posting `/api/pipeline/start`:

```powershell
.\SmokeTests\Test-WebViewBrowserPendingDrainGuardSmoke.ps1
```

12. Run the browser-backed Completed/Pending proof smoke. This starts a temporary local API, launches installed Chrome/Edge headless, verifies exact completed-output to pending-destination proof, verifies selected Pending row Completed Manifest correlation, verifies missing-output-without-proof detail, and confirms same-leaf proof remains duplicate-title guidance only:

```powershell
.\SmokeTests\Test-WebViewBrowserCompletedPendingProofSmoke.ps1
```

13. Run the browser-backed large daily-table smoke. This starts a temporary local API, launches installed Chrome/Edge headless, injects 260-row Queue, Completed, and Pending Publish payloads, verifies 250-row render-cap disclosure, filter warnings, and hidden selected-row detail, and confirms no backend mutation routes are posted:

```powershell
.\SmokeTests\Test-WebViewBrowserLargeTableSmoke.ps1
```

14. Run the browser-backed Maintenance/Reports smoke. This starts a temporary local API, launches installed Chrome/Edge headless, verifies Maintenance health and dry-run result rendering, verifies Reports failure/audit triage plus row details, and confirms read-only Launch/Diagnostics handoff navigation posts no mutation routes:

```powershell
.\SmokeTests\Test-WebViewBrowserMaintenanceReportsSmoke.ps1
```

15. Run the browser-backed Sample Validation smoke. This starts a temporary local API, launches installed Chrome/Edge headless, verifies Home Sample Validation pilot-plan rendering, runs only the backend-owned preview route, and confirms no append or mutation routes are posted:

```powershell
.\SmokeTests\Test-WebViewBrowserSampleValidationSmoke.ps1
```

16. Run the browser-backed Home live-state smoke. This starts a temporary local API with generated temporary state and command history, launches installed Chrome/Edge headless, verifies Daily-Driver Checklist, Operator Readiness, Active Work, Command Results, Sample Validation posture, and the Real-Media Validation Worksheet handoff, and confirms no POST routes are sent:

```powershell
.\SmokeTests\Test-WebViewBrowserHomeLiveStateSmoke.ps1
```

17. Run the browser-backed Launch/Queue readiness smoke. This starts a temporary local API with generated temporary state and launch command history, launches installed Chrome/Edge headless, verifies Launch preflight, Queue launch decision, Schedule guidance, close-readiness, and launch command-review evidence align, and confirms no POST routes are sent:

```powershell
.\SmokeTests\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1
```

18. Run the browser-backed layout-manager smoke. This starts a temporary local API, launches installed Chrome/Edge headless, enters customize mode, and verifies tab/subtab/subsection boxes expose independent customize bars and draggable handles without posting mutation routes:

```powershell
.\SmokeTests\Test-WebViewBrowserLayoutManagerSmoke.ps1
```

19. Run the Settings/Launch policy smoke. This uses generated temporary state to verify the read-only backend media-policy readiness handoff appears in Settings, Saved Settings Trust, Launch Risk Handoff, and cross-page context:

```powershell
.\SmokeTests\Test-WebViewSettingsLaunchPolicySmoke.ps1
```

20. Run the Settings/Launch live-config smoke. This reads the current saved config through the local backend path and verifies the same read-only handoff against live config data without launching work or saving settings:

```powershell
.\SmokeTests\Test-WebViewSettingsLaunchLiveConfigSmoke.ps1
```

21. Run the Settings preview/save evidence smoke. This uses a generated temporary config and proves Preview Patch, denied Save Patch, confirmed Save Patch, reload evidence, command history, and WebView Settings result-panel assets without touching the current saved config or media:

```powershell
.\SmokeTests\Test-WebViewSettingsPatchEvidenceSmoke.ps1
```

22. Run the bounded launch smoke. This opens the Tauri shell, verifies the Rust shell can bootstrap/validate the local API backend, verifies the backend-served WebView index and critical JS assets are present, closes the window, and checks process cleanup:

```powershell
.\DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1 -TimeoutSeconds 180 -CloseTimeoutSeconds 30
```

23. Run the release self-test before treating a package as trustworthy:

```powershell
.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Tool integration and end-to-end media smoke checks are still separate. Passing the fixture, command-evidence, row-detail, schedule, browser schedule, browser backend lifecycle, local API Maintenance dry-run, local API sample validation, browser high-risk, browser diagnostics handoff, pending drain guard, completed pending proof, large-table, browser Maintenance/Reports, browser Sample Validation, browser Home live-state, browser Launch/Queue readiness, browser layout manager, settings/launch policy, live-config handoff, settings patch evidence, or preview launch smoke does not prove FFmpeg, PowerShell pipeline behavior, subtitle conversion, pending publish, Plex playback, or real-media processing.

## Launch Commands

Use the explicit preview launcher:

```powershell
.\Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat
```

For first-time setup of the preview dependencies:

```powershell
.\Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat -InstallNodePackages
```

To verify prerequisites without launching the preview window:

```powershell
.\Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat -CheckOnly
```

For PG-3 clean-machine validation, run from the copied release bundle, not from the development workspace:

```powershell
.\DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1 -CheckOnly
.\DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30
.\DesktopApp\tauri_shell\New-TauriShell-PG3CleanMachineReport.ps1 -PrereqPassed -LaunchPassed -OperatorConfirmedNoDeveloperTools -Operator "<name>" -Notes "<brief note>"
```

`-Mode Packaged` requires a compiled Tauri executable beside `Test-TauriShell-Launch.ps1`, beside `DesktopApp\tauri_shell`, or supplied with `-ExecutablePath`. The dev-mode `npm run dev` launch path is useful for preview work but does not satisfy PG-3 because it depends on Node, Rust/Cargo, and Visual Studio build tools.

`New-TauriShell-PG3CleanMachineReport.ps1` writes clean-machine evidence under `Docs\PG3CleanMachineReports` in the copied bundle. It records bundle layout, manifest posture, prereq/launch pass flags, and developer-tool scan results. It does not launch media, prove real FFmpeg routing, or replace PG-1/PG-2 validation.

When building a deployable PG-3 candidate after a Tauri release build, use the release builder's explicit preview-binary option so the copied bundle contains `DesktopApp\tauri_shell\mediapipeline-tauri-shell.exe`:

```powershell
.\Build-MediaPipelineRemuxEncodeAIO-Release.ps1 -DestinationRoot C:\Temp\MediaPipelineRemuxEncodeAIO_V6_PG3 -IncludeTauriPreviewBinary
.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -BundleRoot C:\Temp\MediaPipelineRemuxEncodeAIO_V6_PG3 -SkipToolIntegration -SkipEndToEndSmoke
```

The lower-level developer commands are:

```powershell
cd DesktopApp\tauri_shell
npm install
npm run check
cargo test --manifest-path src-tauri\Cargo.toml --lib
npm run dev
```

Keep the V5 workspace available until V6 has completed real processing, audit, rename, settings, pending-publish, network-visibility, launch/close, and release verification cycles.

