# MediaPipelineRemuxEncodeAIO V5 Deployability Checklist

Status legend:

- `[x]` Ready now
- `[~]` Works, but needs hardening before treating the folder as a clean release
- `[ ]` Not done yet

## Current Audit Result

Checked on 2026-05-18 from the V5 source/dev bundle root after the transition-review remediation pass. Source/dev deployability gates are green: full unskipped release self-test, bundled Python `unittest`/`pytest`, browser no-mutation smokes, and Tauri prereq/build gates passed. A fresh current-handoff package was also built and package-mode Tauri launch/close passed locally from the copied bundle. This still does not prove PG-3 clean-machine package-mode launch or broader representative real-media daily-driver readiness.

- [x] Root release layout exists: `DesktopApp`, `Docs`, `Pipeline`, root setup/run/desktop/verifier launchers.
- [x] Environment verifier passes in the current folder.
- [x] Bundled PowerShell host exists at `Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe`.
- [x] Bundled desktop Python exists at `DesktopApp\Runtime\Python\python.exe` and `pythonw.exe`.
- [x] Desktop Python imports `customtkinter`, `psutil`, and `pysubs2`.
- [x] Bundled FFmpeg tools exist under `Pipeline\Tools\ffmpeg\bin`.
- [x] Bundled MKVToolNix tools exist under `Pipeline\Tools\MKVToolNix`.
- [x] Bundled PgsToSrt and English tessdata exist under `Pipeline\Tools\PgsToSrt`.
- [x] Setup validator passes against the current `Pipeline\MediaPipeline_config_chatgpt.psd1`.
- [~] Current config is operator-specific and contains live UNC/source/output/scratch paths. That is correct for this machine, but not a generic release template.
- [~] The working V5 folder still contains generated logs, app state, Python bytecode caches, config backups, and local assistant metadata. These are ignored by `.gitignore`, but they are still present in the folder.
- [x] Repeatable packaging script exists to build a clean deployable copy or zip from the working V5 folder: `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`.
- [x] Release manifest records included/excluded file counts, excluded runtime clutter, tool versions, package versions, and config policy.
- [x] Verifier explicitly validates PgsToSrt/tessdata when OCR is enabled and reports optional network-mode dependency status.
- [x] Full unskipped release self-test passed from the source/dev bundle on 2026-05-18 with bundled tool integration and end-to-end smoke included.
- [x] Bundled Python `unittest` and `pytest` suites passed from source/dev on 2026-05-18.
- [x] Browser-backed WebView no-mutation smoke suite passed from source/dev on 2026-05-18.
- [x] Tauri prerequisite `-CheckOnly` and Tauri build gates passed from source/dev on 2026-05-18.
- [x] Fresh current-handoff package `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` built on 2026-05-18 with `-IncludeTauriPreviewBinary -Verify`; copied-bundle release self-test passed. The package name is transfer evidence, not a hardcoded local path for future validation.
- [x] Copied-bundle package-mode Tauri launch/close smoke passed locally from the 2026-05-18 current-handoff package.
- [~] Local PG-3 boundary report `%TEMP%\pg3_current_handoff_local_dev_boundary_20260518_140116.md` showed `Bundle layout mismatches: 0` but `Developer tools detected outside bundle: 8`, so it is transfer readiness evidence only.
- [~] PG-3 clean-machine package-mode launch validation remains open and must be run on a separate clean Windows machine before default-launcher promotion.
- [~] Broader representative real-media validation remains open before WebView/Tauri daily-driver claims.

## Deployable Parts

### 1. Bundle Root

- [x] `Docs\README_MediaPipelineRemuxEncodeAIO.md` explains the bundle and first-run order.
- [x] `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` delegates to `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-DesktopApp.bat`.
- [x] `Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat` launches the headless localhost backend for web/Tauri preview work.
- [x] `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat` launches the explicit opt-in Tauri/WebView2 preview without replacing the supported desktop app.
- [x] `Setup-MediaPipelineRemuxEncodeAIO.bat` delegates to `Pipeline\Setup-MediaPipelineRemuxEncodeAIO.bat`.
- [x] `Run-MediaPipelineRemuxEncodeAIO.bat` delegates to `Pipeline\Run-MediaPipelineRemuxEncodeAIO.bat`.
- [x] `Verify-MediaPipelineRemuxEncodeAIO-Environment.bat` launches the PowerShell verifier with bundled PowerShell when present.
- [~] `Docs` also contains cleanup/UI/network archive documents. Useful for development, but not needed in a clean operator-facing release.

### 2. Desktop App

- [x] `DesktopApp\mediapipeline_desktop_app\__main__.py` is the Python module entry point.
- [x] `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-DesktopApp.bat` prefers bundled Python and supports `console` diagnostic mode.
- [x] `DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat` starts the token-protected local API.
- [x] `DesktopApp\Runtime\Python` contains a working Python runtime and required packages.
- [x] Desktop service resolves pipeline scripts/config relative to the bundle instead of relying on the current shell directory.
- [x] Desktop process launching prepends bundled tool folders to `PATH`.
- [~] `DesktopApp\RunLogs`, `DesktopApp\*.log`, `DesktopApp\*.state.json`, and app `__pycache__` directories are runtime artifacts and should not ship in a clean package.

### 3. Pipeline Backend

- [x] `Pipeline\MediaPipeline_chatgpt.ps1` is the backend processing entry point.
- [x] `Pipeline\Modules\*.ps1` contains the refactored pipeline modules.
- [x] `Pipeline\Setup-MediaPipeline_chatgpt.ps1` creates/validates config.
- [x] `Pipeline\Audit-MediaLibrary_chatgpt.ps1`, `Pipeline\Invoke-RerunCsv.ps1`, and `Pipeline\Backfill-CompletedManifest.ps1` are deployable helper scripts.
- [x] `Pipeline\Run-MediaPipelineRemuxEncodeAIO.bat` and `Pipeline\Setup-MediaPipelineRemuxEncodeAIO.bat` resolve bundled PowerShell and tool paths.
- [x] `Pipeline\MediaPipeline_config_chatgpt.psd1` remains the live machine config. New-user packages strip it by default and include `Pipeline\MediaPipeline_config_template.psd1`.
- [~] `Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1` files are generated backups and should not ship.

### 4. Bundled Tools And Runtimes

- [x] PowerShell is bundled under `Pipeline\PowerShell-7.6.0-win-x64`.
- [x] FFmpeg, ffprobe, and ffplay are bundled under `Pipeline\Tools\ffmpeg\bin`; clean releases include only runtime-required `ffmpeg.exe`/`ffprobe.exe` unless `-IncludeOptionalTools` is used.
- [x] MKVToolNix command tools are bundled under `Pipeline\Tools\MKVToolNix`; clean releases include runtime-required `mkvmerge.exe` and omit GUI/diagnostic utilities unless `-IncludeOptionalTools` is used.
- [x] PgsToSrt, DLL dependencies, and `tessdata\eng.traineddata` are bundled under `Pipeline\Tools\PgsToSrt`.
- [x] Pipeline falls back to system tools only when `AllowSystemTools` is explicitly enabled.
- [x] Add a release manifest with tool versions and package versions.
- [x] Decide whether `ffplay.exe`, `mkvtoolnix-gui.exe`, `mkvextract.exe`, `mkvinfo.exe`, `mkvpropedit.exe`, `uninst.exe`, MKVToolNix GUI assets, diagnostics, docs, and examples are intentionally part of clean releases. They are removable bulk by default and remain opt-in through `-IncludeOptionalTools` / `-IncludeToolDocs`.

### 5. Local State And Generated Output

- [x] Runtime app/pipeline state is centered under `LocalBase\State`.
- [x] Pipeline logs remain under `LocalBase` during normal operation.
- [x] Desktop active job records and run logs support troubleshooting.
- [~] Working-folder logs and state should be cleared or excluded when building a clean deployable package.
- [x] Add a package preflight that excludes generated state/log/cache files, including local API command-history JSON under `DesktopApp\RunLogs` and local Tauri/WebView2 build artifacts, and reports exclusions during dry runs.

### 6. Verification And Test Gates

- [x] `Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1` validates layout, key runtimes, Python packages, tool paths, config writability, and setup validation.
- [x] `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` validates `release_manifest.json`, rejects default packages that accidentally include live config/run logs/state/generated config backups/Tauri build artifacts/optional tool binaries/tool docs/examples, parses core PowerShell scripts, syntax-checks core Python API/facade files, and runs the non-destructive Tauri preview prereq gate.
- [x] `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` covers cleanup and behavior regressions.
- [x] `Pipeline\Tests\Invoke-ToolIntegrationChecks.ps1` covers bundled tool integration.
- [x] `Pipeline\Tests\Invoke-EndToEndSmokeChecks.ps1` covers smoke behavior.
- [x] Extend the verifier to check PgsToSrt/tessdata when BDPGS OCR is enabled.
- [x] Extend the verifier to report optional network-mode dependency status separately from standalone-mode readiness.
- [x] Add a one-command release verification script that runs verifier plus parser/regression/tool/smoke checks when tests are present.
- [x] 2026-05-18 source/dev validation passed with the full unskipped release self-test, bundled Python test suites, browser-backed WebView smokes, and Tauri prereq/build gates.
- [x] 2026-05-18 current-handoff package `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` built; copied-bundle release self-test and package-mode launch/close smoke passed locally.
- [~] Package-mode Tauri launch on a separate clean Windows machine remains a PG-3 gate.
- [~] Representative real-media validation remains required before daily-driver promotion.

## Current Residual Gates

- [~] Run PG-3 clean-machine package-mode launch validation from the copied or rebuilt `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` package on a separate clean Windows machine.
- [~] Run the representative real-media validation playbook and record current evidence under `Docs\RealMediaValidationRuns`.
- [~] Build an engineering handoff package with `-Verify -IncludeTests` if transfer validation needs bundled tests; the current PG-3 handoff package intentionally excludes tests and is ready for package-mode launch validation outside this source/dev checkout.

## Recommended Cleanup Chunks

### Chunk 1: Release Hygiene Manifest

Goal: define exactly what is included and excluded in a deployable V5 package.

Likely files:

- `Docs\architecture\DEPLOYABILITY_CHECKLIST.md`
- `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`
- `Docs\README_MediaPipelineRemuxEncodeAIO.md`

Checks:

- Packaging dry run lists runtime clutter instead of copying it.
- Source folder remains untouched.
- Generated release folder contains root launchers, DesktopApp source/runtime, Pipeline source/runtime/tools, config/template/docs, and tests only if requested.

Status: Implemented. Source/dev release self-test passed on 2026-05-18; PG-3 clean-machine package-mode launch remains a separate gate.

Risk: Low.

### Chunk 2: Verifier Coverage

Goal: make the existing verifier catch missing OCR and optional dependency gaps before runtime.

Likely files:

- `Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1`
- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
- `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`

Checks:

- Verifier still passes current standalone bundle.
- Missing PgsToSrt/tessdata is reported only as required when BDPGS OCR is enabled.
- Optional network dependency status is informational unless network mode is enabled.

Status: Implemented.

Risk: Low to medium.

### Chunk 3: Config Template Boundary

Goal: separate current operator config from reusable deployable defaults.

Likely files:

- `Pipeline\MediaPipeline_config_template.psd1`
- `Pipeline\Setup-MediaPipeline_chatgpt.ps1`
- docs

Checks:

- Existing config remains untouched.
- Setup can still validate current config.
- Template contains no operator-specific UNC paths or drive letters.

Status: Implemented as a packaging boundary. Setup behavior is unchanged.

Risk: Medium, because config behavior must remain backward compatible.

### Chunk 4: Clean Release Builder

Goal: produce a clean release folder or zip without logs, state, bytecode, backup configs, assistant metadata, or transient test output.

Likely files:

- `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`
- maybe root README

Checks:

- Build output can run `Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1`.
- Build output preserves relative launcher behavior.
- Build output excludes generated clutter found in the current V5 folder.

Status: Implemented for clean copy/zip creation and optional `-Verify` package self-test.

Risk: Medium.

### Chunk 5: Release Smoke Gate

Goal: make deployability verifiable after packaging.

Likely files:

- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
- `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`
- docs

Checks:

- Fresh package passes verifier.
- PowerShell parser checks and core Python API/facade syntax checks pass.
- Reliability, tool integration, and smoke tests pass from the packaged path when the package is built with `-IncludeTests`.

Status: Implemented.

Risk: Medium, mostly around runtime duration and machine-specific config.
