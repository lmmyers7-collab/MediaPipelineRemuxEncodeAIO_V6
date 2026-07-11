# Release Package Admin Inventory

Documents what a clean release package is expected to include and exclude. Sources: `ops\scripts\release\build.ps1`, `ops\scripts\release\test.ps1`, `docs/CURRENT_PROJECT_STATE.md`, and `docs/testing/VALIDATION_LADDER_RUNBOOK.md`.

---

## Building a Release

### Default clean package (new-user deployable)

```powershell
.\ops\scripts\release\build.ps1 -Zip
```

### Portable deployable acceptance package

```powershell
.\ops\scripts\release\build.ps1 -Deployable -Zip -Verify
```

`-Deployable` requires the compiled Tauri executable, runs the full source
self-test before staging, omits tests from the ZIP, records SHA-256 hashes and
normalized release identity, then validates an extracted copy with
`-PackageAcceptance`. It must never be combined with `-KeepPersonalConfig`.

### Engineering handoff with tests and verification

```powershell
.\ops\scripts\release\build.ps1 -Zip -Verify -IncludeTests
```

### Private backup / machine-to-machine mirror

```powershell
.\ops\scripts\release\build.ps1 -Zip -KeepPersonalConfig
```

**Warning**: `-KeepPersonalConfig` includes `ops\pipeline\config\MediaPipeline_config.psd1` and the legacy `ops\pipeline\config\MediaPipeline_config_chatgpt.psd1` when present. These files may contain the operator's private UNC paths, source/output locations, and scheduling settings. Use only for private machine-to-machine mirrors — never for distribution.

---

## Expected Inclusions

### Bundle Root

| File / Path | Included by default | Notes |
|---|---|---|
| `docs\README_MediaPipelineRemuxEncodeAIO.md` | Yes | Bundle overview and first-run order |
| `docs\testing\WEBVIEW_SMOKE_TEST_CATALOG.md` | Yes | Smoke wrapper catalog |
| `docs\inventories\SMOKE_TEST_INVENTORY.md` | Yes | Canonical smoke wrapper location and boundary inventory |
| `docs\testing\BROWSER_SMOKE_TEST_RUNBOOK.md` | Yes | Browser smoke runbook |
| Other operator docs in `docs\` | Yes (unless dev-only) | See exclusions list below |
| `ops\scripts\dev\start-api-and-browser.bat` | Yes | Local API plus backend-served browser WebView launcher |
| `ops\scripts\dev\start-local-api.bat` | Yes | Optional headless backend API launcher |
| `ops\scripts\dev\start-tauri-preview.bat` | Yes | Tauri/WebView2 shell launcher |
| `ops\scripts\dev\setup.bat` | Yes | Config wizard launcher |
| `ops\scripts\dev\run.bat` | Yes | Pipeline runner launcher |
| `ops\scripts\dev\verify-env.bat` | Yes | Environment verifier launcher |
| `ops\scripts\release\build.ps1` | Yes | Release builder |
| `ops\scripts\release\test.ps1` | Yes | Release self-test |
| `ops/scripts/smoke\Test-WebView*.ps1` and `ops/scripts/smoke\Test-LocalApi*.ps1` | Yes | WebView and local API smoke wrappers |
| `release_manifest.json` | Yes (generated) | Records included/excluded files, normalized version/source revision, tool versions, and SHA-256 hashes |

### Desktop App

| File / Path | Included by default | Notes |
|---|---|---|
| `src\mediapipeline\desktop\` | Yes | Python package |
| `apps\desktop\runtime\Python\` | Yes | Bundled Python runtime |
| `apps\desktop\tauri\` | Yes | Tauri/WebView2 preview shell source |
| `apps\desktop\launchers\Launch-*.bat` | Yes | Desktop batch launchers |

### Pipeline Backend

| File / Path | Included by default | Notes |
|---|---|---|
| `ops\pipeline\entrypoints\MediaPipeline.ps1` | Yes | Backend pipeline entry point |
| `ops\pipeline\engine\**\*.ps1` | Yes | Active PowerShell engine implementations |
| `Pipeline\Modules\*.ps1` | No | Removed legacy shim surface; active PowerShell implementations live under `ops\pipeline\engine\` |
| `ops\pipeline\entrypoints\Setup-MediaPipeline.ps1` and `ops\pipeline\config\setup\*.ps1` | Yes | Setup wizard entry point and helper slices |
| `ops\pipeline\entrypoints\Audit-MediaLibrary.ps1` | Yes | Audit script |
| `ops\pipeline\entrypoints\Invoke-RerunCsv.ps1` | Yes | CSV rerun script |
| `ops\pipeline\entrypoints\Backfill-CompletedManifest.ps1` | Yes | Backfill script |
| `ops\pipeline\config\MediaPipeline_config_template.psd1` | Yes | New-user config template |
| `ops\pipeline\runtime\PowerShell-7.6.0-win-x64\` | Yes | Bundled PowerShell 7 runtime |
| `ops\pipeline\tools\ffmpeg\bin\` | Yes (core tools) | FFmpeg, ffprobe (ffplay excluded by default) |
| `ops\pipeline\tools\MKVToolNix\mkvmerge.exe` | Yes | Core MKVToolNix tool |
| `ops\pipeline\tools\PgsToSrt\` | Yes | PgsToSrt OCR tool + English tessdata |
| `ops\pipeline\tests\` | No (default) | Included with `-IncludeTests` |

---

## Expected Exclusions (Default)

### Personal and Runtime State

| Excluded | Reason |
|---|---|
| `ops\pipeline\config\MediaPipeline_config.psd1` | Live personal config — stripped unless `-KeepPersonalConfig` |
| `ops\pipeline\config\MediaPipeline_config_chatgpt.psd1` | Live personal config — stripped unless `-KeepPersonalConfig` |
| `ops\pipeline\config\MediaPipeline_config*.backup_*.psd1` | Generated config backups |
| `ops\pipeline\config\backups\*.psd1` | Generated config backup folder |
| `Pipeline\MediaPipeline_config_chatgpt.backup_*.psd1` | Generated config backups |
| `Pipeline\*.log`, `Pipeline\*.tmp`, `Pipeline\*.bak` | Pipeline runtime artifacts |
| `apps\desktop\runlogs\` | Desktop run logs |
| `DesktopApp\*.log` | Desktop runtime logs |
| `src\*.log`, `src\*.egg-info\*` | Source-checkout runtime and packaging artifacts |
| `DesktopApp\*.state.json` | Desktop local state |
| `DesktopApp\encode_speed_history.json` | Desktop local telemetry |
| `docs\RealMediaValidationRuns\*` (except README.md) | Operator real-media validation evidence |
| `LocalBase\*` (if present in source folder) | Runtime state |
| `ops\release\changes\unreleased\*`, its generated summaries, `docs\CURRENT_PROJECT_STATE.md`, `docs\OPEN_WORK_CHECKLIST.md`, and `docs\REMEDIATION_CHANGELOG.md` | Developer history, volatile status, and remediation ledger |
| `docs\reviews\*`, clean-machine reports, real-media worksheets, generated evidence | Operator/review evidence that can contain personal paths or runtime history |

### Development and Build Artifacts

| Excluded | Reason |
|---|---|
| `.git\` | Git metadata |
| `.github\` | Source-control workflow metadata |
| `.gitignore`, `.gitattributes` | Source-control metadata |
| `.claude\` | Local assistant metadata |
| `.codex\`, `.codex-plugin\` | Local assistant metadata |
| `__pycache__\`, `*.pyc`, `*.pyo` | Python bytecode cache |
| `.pytest_cache\`, `.mypy_cache\`, `.ruff_cache\` | Test/tool caches |
| `node_modules\` | Root Node.js packages |
| `apps\desktop\tauri\node_modules\` | Tauri Node.js packages |
| `apps\desktop\tauri\src-tauri\gen\` | Tauri generated schema output |
| `apps\desktop\tauri\src-tauri\target\` | Rust build output |
| Windows reserved device-name paths such as `CON`, `PRN`, `AUX`, `NUL`, `COM1`, or `LPT1` | Invalid Windows package paths |

### Development-Only Docs (without `-IncludeDevDocs`)

| Excluded | Reason |
|---|---|
| `docs\archive\docs-housekeeping\2026-05-20-review\archive-historical\...` | Completed and historical docs quarantined during housekeeping |
| `docs\archive\docs-housekeeping\2026-05-20-review\delete-candidates\...` | Quarantine-only delete candidates |
| `docs\ui\UI_IMPROVEMENT_CHECKLIST.md` | Completed UI improvement backlog closure record |

### Optional Tools (without `-IncludeOptionalTools`)

| Excluded | Reason |
|---|---|
| `ops\pipeline\tools\ffmpeg\bin\ffplay.exe` | Media playback tool (not needed for pipeline) |
| MKVToolNix GUI, `mkvextract`, `mkvinfo`, `mkvpropedit`, uninstaller | Optional MKV tools |
| `ops\pipeline\tools\MKVToolNix\tools\`, `data\`, `locale\libqt\` | MKVToolNix GUI assets |

### Tool Documentation (without `-IncludeToolDocs`)

| Excluded | Reason |
|---|---|
| `ops\pipeline\tools\MKVToolNix\doc\` | Bundled tool documentation |
| `ops\pipeline\tools\MKVToolNix\examples\` | Bundled tool examples |

---

## Release Manifest

`release_manifest.json` is written by the build and records:
- Included file count
- Excluded file count and reasons
- Tool versions (FFmpeg, MKVToolNix, Python, bundled packages)
- Build options used
- Config policy (template vs live)
- Normalized version and source revision without absolute local paths
- SHA-256 for every copied file

The release self-test (`ops\scripts\release\test.ps1`) validates the manifest after build.
For a deployable manifest, `-PackageAcceptance` also rescans included text,
audits the Tauri production surface, launches and closes the copied shell using
a temporary AppData root, and rejects mutable bundle-root files or orphaned
backend/media-tool processes.

---

## Release Self-Test Gates

The self-test fails a default package that:
- Accidentally includes `ops\pipeline\config\MediaPipeline_config_chatgpt.psd1` (live config)
- Includes `apps\desktop\runlogs\` or runtime state
- Includes `node_modules\` or Rust `target\` build artifacts
- Missing the release manifest itself

Run after every build:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1
```

---

## Desktop App: Maintenance Release Package

From the WebView, the operator can also trigger a release dry-run or build via **Maintenance → Release Package**. This invokes the same `ops\scripts\release\build.ps1` script through the local API dry-run route. The **Plan Only** option runs with `-DryRun`; **Build Package** runs without.

---

## See Also

- Validation ladder: `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- Packaging dependency inventory: `docs/inventories/PACKAGING_DEPENDENCY_INVENTORY.md`
- PowerShell host expectations: `docs/operator/POWERSHELL_HOST_EXPECTATIONS.md`
- Bundle release packaging overview: `docs/README_MediaPipelineRemuxEncodeAIO.md`
