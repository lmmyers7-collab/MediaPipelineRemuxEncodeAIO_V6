# Release Package Admin Inventory

Documents what a clean release package is expected to include and exclude. Sources: `scripts\release\build.ps1`, `scripts\release\test.ps1`, `Docs/CURRENT_PROJECT_STATE.md`, and `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`.

---

## Building a Release

### Default clean package (new-user deployable)

```powershell
.\scripts\release\build.ps1 -Zip
```

### Engineering handoff with tests and verification

```powershell
.\scripts\release\build.ps1 -Zip -Verify -IncludeTests
```

### Private backup / machine-to-machine mirror

```powershell
.\scripts\release\build.ps1 -Zip -KeepPersonalConfig
```

**Warning**: `-KeepPersonalConfig` includes `Pipeline\MediaPipeline_config_chatgpt.psd1` with the operator's private UNC paths, source/output locations, and scheduling settings. Use only for private machine-to-machine mirrors — never for distribution.

---

## Expected Inclusions

### Bundle Root

| File / Path | Included by default | Notes |
|---|---|---|
| `Docs\README_MediaPipelineRemuxEncodeAIO.md` | Yes | Bundle overview and first-run order |
| `Docs\TLDR.md` | Yes | Operator daily-use summary |
| `Docs\testing\WEBVIEW_SMOKE_TEST_CATALOG.md` | Yes | Smoke wrapper catalog |
| `Docs\inventories\SMOKE_TEST_INVENTORY.md` | Yes | Canonical smoke wrapper location and boundary inventory |
| `Docs\testing\BROWSER_SMOKE_TEST_RUNBOOK.md` | Yes | Browser smoke runbook |
| Other operator docs in `Docs\` | Yes (unless dev-only) | See exclusions list below |
| `scripts\dev\start-api-and-browser.bat` | Yes | Local API plus backend-served browser WebView launcher |
| `scripts\dev\start-local-api.bat` | Yes | Optional headless backend API launcher |
| `scripts\dev\start-tauri-preview.bat` | Yes | Tauri/WebView2 shell launcher |
| `scripts\dev\setup.bat` | Yes | Config wizard launcher |
| `scripts\dev\run.bat` | Yes | Pipeline runner launcher |
| `scripts\verify-env.bat` | Yes | Environment verifier launcher |
| `scripts\release\build.ps1` | Yes | Release builder |
| `scripts\release\test.ps1` | Yes | Release self-test |
| `SmokeTests\Test-WebView*.ps1` and `SmokeTests\Test-LocalApi*.ps1` | Yes | WebView and local API smoke wrappers |
| `release_manifest.json` | Yes (generated) | Written by build; records included/excluded/tool versions |

### Desktop App

| File / Path | Included by default | Notes |
|---|---|---|
| `DesktopApp\mediapipeline_desktop_app\` | Yes | Python package |
| `DesktopApp\Runtime\Python\` | Yes | Bundled Python runtime |
| `DesktopApp\tauri_shell\` | Yes | Tauri/WebView2 preview shell source |
| `DesktopApp\Launch-*.bat` | Yes | Batch launchers |

### Pipeline Backend

| File / Path | Included by default | Notes |
|---|---|---|
| `Pipeline\MediaPipeline_chatgpt.ps1` | Yes | Backend pipeline entry point |
| `engine\**\*.ps1` | Yes | Active PowerShell engine implementations |
| `Pipeline\Modules\*.ps1` | Yes | Temporary compatibility shims for legacy dot-source paths |
| `Pipeline\Setup-MediaPipeline_chatgpt.ps1` | Yes | Setup wizard |
| `Pipeline\Audit-MediaLibrary_chatgpt.ps1` | Yes | Audit script |
| `Pipeline\Invoke-RerunCsv.ps1` | Yes | CSV rerun script |
| `Pipeline\Backfill-CompletedManifest.ps1` | Yes | Backfill script |
| `Pipeline\MediaPipeline_config_template.psd1` | Yes | New-user config template |
| `Pipeline\PowerShell-7.6.0-win-x64\` | Yes | Bundled PowerShell 7 runtime |
| `Pipeline\Tools\ffmpeg\bin\` | Yes (core tools) | FFmpeg, ffprobe (ffplay excluded by default) |
| `Pipeline\Tools\MKVToolNix\mkvmerge.exe` | Yes | Core MKVToolNix tool |
| `Pipeline\Tools\PgsToSrt\` | Yes | PgsToSrt OCR tool + English tessdata |
| `Pipeline\Tests\` | No (default) | Included with `-IncludeTests` |

---

## Expected Exclusions (Default)

### Personal and Runtime State

| Excluded | Reason |
|---|---|
| `Pipeline\MediaPipeline_config_chatgpt.psd1` | Live personal config — stripped unless `-KeepPersonalConfig` |
| `Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1` | Generated config backups |
| `Pipeline\*.log`, `Pipeline\*.tmp`, `Pipeline\*.bak` | Pipeline runtime artifacts |
| `DesktopApp\RunLogs\` | Desktop run logs |
| `DesktopApp\*.log` | Desktop runtime logs |
| `DesktopApp\*.state.json` | Desktop local state |
| `DesktopApp\encode_speed_history.json` | Desktop local telemetry |
| `Docs\RealMediaValidationRuns\*` (except README.md) | Operator real-media validation evidence |
| `LocalBase\State\*` (if present in source folder) | Runtime state |

### Development and Build Artifacts

| Excluded | Reason |
|---|---|
| `.git\` | Git metadata |
| `.claude\` | Local assistant metadata |
| `__pycache__\`, `*.pyc`, `*.pyo` | Python bytecode cache |
| `.pytest_cache\`, `.mypy_cache\`, `.ruff_cache\` | Test/tool caches |
| `DesktopApp\tauri_shell\node_modules\` | Tauri Node.js packages |
| `DesktopApp\tauri_shell\src-tauri\gen\` | Tauri generated schema output |
| `DesktopApp\tauri_shell\src-tauri\target\` | Rust build output |

### Development-Only Docs (without `-IncludeDevDocs`)

| Excluded | Reason |
|---|---|
| `Docs\archive\docs-housekeeping\2026-05-20-review\archive-historical\...` | Completed and historical docs quarantined during housekeeping |
| `Docs\archive\docs-housekeeping\2026-05-20-review\delete-candidates\...` | Quarantine-only delete candidates |
| `Docs\ui\UI_IMPROVEMENT_CHECKLIST.md` | Completed UI improvement backlog closure record |

### Optional Tools (without `-IncludeOptionalTools`)

| Excluded | Reason |
|---|---|
| `Pipeline\Tools\ffmpeg\bin\ffplay.exe` | Media playback tool (not needed for pipeline) |
| MKVToolNix GUI, `mkvextract`, `mkvinfo`, `mkvpropedit`, uninstaller | Optional MKV tools |
| `Pipeline\Tools\MKVToolNix\tools\`, `data\`, `locale\libqt\` | MKVToolNix GUI assets |

### Tool Documentation (without `-IncludeToolDocs`)

| Excluded | Reason |
|---|---|
| `Pipeline\Tools\MKVToolNix\doc\` | Bundled tool documentation |
| `Pipeline\Tools\MKVToolNix\examples\` | Bundled tool examples |

---

## Release Manifest

`release_manifest.json` is written by the build and records:
- Included file count
- Excluded file count and reasons
- Tool versions (FFmpeg, MKVToolNix, Python, bundled packages)
- Package version and build options used
- Config policy (template vs live)

The release self-test (`scripts\release\test.ps1`) validates the manifest after build.

---

## Release Self-Test Gates

The self-test fails a default package that:
- Accidentally includes `Pipeline\MediaPipeline_config_chatgpt.psd1` (live config)
- Includes `DesktopApp\RunLogs\` or runtime state
- Includes `node_modules\` or Rust `target\` build artifacts
- Missing the release manifest itself

Run after every build:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\release\test.ps1
```

---

## Desktop App: Maintenance Release Package

From the WebView, the operator can also trigger a release dry-run or build via **Maintenance → Release Package**. This invokes the same `scripts\release\build.ps1` script through the local API dry-run route. The **Plan Only** option runs with `-DryRun`; **Build Package** runs without.

---

## See Also

- Validation ladder: `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- Packaging dependency inventory: `Docs/inventories/PACKAGING_DEPENDENCY_INVENTORY.md`
- PowerShell host expectations: `Docs/operator/POWERSHELL_HOST_EXPECTATIONS.md`
- TLDR release packaging section: `Docs/TLDR.md`
