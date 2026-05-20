# Generated/Vendor Artifact Exclusion Review

Date: 2026-05-14

Checks that docs and release scripts consistently exclude generated/vendor artifacts from release and audit scope. Source: `Docs\RELEASE_PACKAGE_ADMIN_INVENTORY.md`, `Docs\PACKAGING_DEPENDENCY_INVENTORY.md`.

---

## Summary

Generated and vendor artifact exclusions are correctly documented and consistently applied. The release builder explicitly excludes all known generated directories. The release self-test gates catch accidental inclusion of key dev artifacts. No ambiguous directories were found.

---

## Generated Artifacts — Excluded by Default

| Directory / Pattern | Type | Excluded by | Self-test gate |
|---|---|---|---|
| `__pycache__\`, `*.pyc`, `*.pyo` | Python bytecode | Release builder default | No gate — excluded by pattern |
| `.pytest_cache\`, `.mypy_cache\`, `.ruff_cache\` | Test/tool caches | Release builder default | No gate |
| `DesktopApp\tauri_shell\node_modules\` | Tauri JS dependencies | Release builder default | Yes — self-test fails if included |
| `DesktopApp\tauri_shell\src-tauri\gen\` | Tauri generated schema | Release builder default | No gate |
| `DesktopApp\tauri_shell\src-tauri\target\` | Rust build output | Release builder default | Yes — self-test fails if included |
| `Pipeline\*.log`, `Pipeline\*.tmp`, `Pipeline\*.bak` | Runtime artifacts | Release builder default | No gate |
| `LocalBase\State\*` | Runtime state | Release builder default | No gate |
| `DesktopApp\RunLogs\` | Desktop run logs | Release builder default | Yes — self-test fails if included |

---

## Vendor/Bundled Artifacts — Included by Design

These are vendor binaries or runtimes that ARE included in release packages. They are not "generated" — they are curated static packages shipped with the release.

| Directory | Type | Included by |
|---|---|---|
| `Pipeline\PowerShell-7.6.0-win-x64\` | Bundled PS7 runtime | Release builder inclusion |
| `Pipeline\Tools\ffmpeg\bin\` | FFmpeg/ffprobe binary | Release builder inclusion (ffplay excluded by default) |
| `Pipeline\Tools\MKVToolNix\mkvmerge.exe` | MKVToolNix core tool | Release builder inclusion |
| `Pipeline\Tools\PgsToSrt\` | PgsToSrt tool + tessdata | Release builder inclusion |
| `DesktopApp\Runtime\Python\` | Bundled Python runtime | Release builder inclusion |

These bundled runtimes are explicitly listed in `PACKAGING_DEPENDENCY_INVENTORY.md`. They are curated static payloads, not outputs of the project's own build process.

---

## Ambiguous Directories

| Directory | Status | Notes |
|---|---|---|
| `DesktopApp\tauri_shell\node_modules\` | Excluded — confirmed | This is the npm vendor directory; confirmed excluded by release builder and self-test gate |
| `DesktopApp\tauri_shell\src-tauri\gen\` | Excluded — confirmed | Tauri CLI-generated schema output; ephemeral |
| `DesktopApp\tauri_shell\src-tauri\target\` | Excluded — confirmed | Rust cargo build artifacts; large and ephemeral |
| `Docs\RealMediaValidationRuns\*` (except README.md) | Excluded — confirmed | Operator evidence with personal paths; release builder excludes explicitly |

No ambiguous directories found. All three Tauri build artifact directories are correctly excluded.

---

## Release Self-Test Coverage of Exclusions

The release self-test (`Test-MediaPipelineRemuxEncodeAIO-Release.ps1`) explicitly fails if:
- `Pipeline\MediaPipeline_config_chatgpt.psd1` (live personal config) is present
- `DesktopApp\RunLogs\` (runtime logs) is present
- `node_modules\` (JS dependencies) is present
- Rust `target\` (build artifacts) is present

This covers the highest-risk accidental inclusions. Python caches (`__pycache__`, `.pyc`) are not individually self-tested but are excluded by pattern.

---

## Acceptance Criteria

| Criterion | Status |
|---|---|
| Bundled runtime/tool payloads vs generated dependency folders are described correctly | Pass — bundled runtimes are inclusions; generated/vendor JS/Rust/Python caches are exclusions |
| Ambiguous directories are called out | Pass — all three Tauri directories confirmed excluded |
| No deletions | Pass — this is a review doc only |

---

## Files Inspected

- `Docs\RELEASE_PACKAGE_ADMIN_INVENTORY.md`: inclusions and exclusions tables; self-test gates
- `Docs\PACKAGING_DEPENDENCY_INVENTORY.md`: bundled vs external dependency classification

---

## Task Output

```
Task ID: CLN-023
Files inspected: Docs\RELEASE_PACKAGE_ADMIN_INVENTORY.md, Docs\PACKAGING_DEPENDENCY_INVENTORY.md
Files changed: Docs\GENERATED_VENDOR_EXCLUSION_REVIEW.md (created)
Validation: Cross-referenced exclusions list against bundled inclusions. Verified self-test gate coverage.
Findings: All generated/vendor directories are explicitly excluded. No ambiguous directories found. Self-test gates cover the highest-risk inclusions.
Open questions: None.
Risk: Low — documentation only.
```
