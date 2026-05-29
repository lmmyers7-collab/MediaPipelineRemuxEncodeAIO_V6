# MediaPipelineRemuxEncodeAIO V6

MediaPipelineRemuxEncodeAIO V6 is a Windows-first, single-operator media
pipeline for a Plex-style library. It discovers source media, copies sources
to scratch, decides remux versus encode, runs FFmpeg/ffprobe plus helper
tools, handles subtitles and audio, writes sidecars and manifests, publishes
completed outputs, and parks unsafe final-output moves for later drain.

This repository is still a V6.x maintenance/overhaul workspace, not a V7
release. V7 remains unreleased until legacy public paths are removed and the
PG-3 clean-machine package-mode gate is complete. Representative real-media
validation is complete by operator attestation as of 2026-05-28.

## Start Here

For operators:

```powershell
.\OPEN_API_AND_BROWSER.cmd
.\scripts\verify-env.bat
.\scripts\dev\start-api-and-browser.bat
.\scripts\dev\start-tauri-preview.bat -CheckOnly
.\scripts\release\test.ps1
.\scripts\operator\New-RealMediaValidationWorksheet.ps1
```

The root `OPEN_API_AND_BROWSER.cmd` tile is the quickest double-click path
when browsing the V6 folder. The canonical launcher remains
`scripts\dev\start-api-and-browser.bat`; both start the Local API and open the
backend-served browser WebView.

For AI/code agents, start with [AGENTS.md](AGENTS.md). For current project
state and open gates, read [Docs/CURRENT_PROJECT_STATE.md](Docs/CURRENT_PROJECT_STATE.md)
and [OPEN_WORK_CHECKLIST.md](OPEN_WORK_CHECKLIST.md).

## Supported Operator Paths

- `scripts\dev\start-local-api.bat` starts the local Python API.
- `scripts\dev\start-api-and-browser.bat` starts the API and opens the
  backend-served WebView.
- `OPEN_API_AND_BROWSER.cmd` is a root-folder operator convenience tile that
  forwards to `scripts\dev\start-api-and-browser.bat`.
- `scripts\dev\start-tauri-preview.bat` starts the Tauri/WebView2 shell;
  `-CheckOnly` validates prerequisites without opening the shell.
- `scripts\release\test.ps1` runs the release self-test.
- `scripts\operator\New-RealMediaValidationWorksheet.ps1` creates a
  worksheet for representative real-media validation.

One-release root launcher shims may still exist for migration, but new
documentation and automation should use the `scripts\` paths above.

## Current Architecture

- `DesktopApp/mediapipeline_desktop_app/` hosts the current Python Local API,
  services, facades, contracts, and WebView integration.
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/` contains the vanilla
  JavaScript WebView SPA.
- `DesktopApp/tauri_shell/` contains the Tauri/WebView2 shell.
- `Pipeline/` contains the current PowerShell media engine and bundled tools.
- `app/`, `engine/`, `schemas/`, and `tests/` contain the additive
  overhaul-era target architecture foundations.

The backend owns media policy, filesystem mutation, settings persistence,
queue mutation, pending-publish drain, rename apply, and process lifecycle.
The WebView/Tauri surface must stay an operator UI over backend-owned routes.

## Promotion Gates

Before any daily-driver or V7 promotion claim:

- PG-3 package-mode launch/close must pass on a separate clean Windows
  machine.
- Phase 6 legacy removal must finish without active import, route, launcher,
  or operator-doc dependencies on removed paths.

Representative real-media validation has covered remux, encode/size,
subtitle conversion, audio policy, and pending-publish/final placement by
operator attestation. Rerun it after any media-policy, subtitle, audio,
publish, drain, source/scratch/output movement, or cleanup behavior change.

Until the remaining gates pass, keep the external V5 fallback available.

## Documentation

- [CHANGELOG.md](CHANGELOG.md): shipped-status log.
- [Docs/architecture/ARCHITECTURE.md](Docs/architecture/ARCHITECTURE.md):
  concise architecture map.
- [Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md](Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md): plan of
  record until V7 ships.
- [Docs/generated/PROJECT_INDEX.md](Docs/generated/PROJECT_INDEX.md) and
  [Docs/generated/PIPELINE_MAP.md](Docs/generated/PIPELINE_MAP.md):
  generated navigation artifacts.
- [Docs/DOCS_INDEX.md](Docs/DOCS_INDEX.md): active documentation map.
- [Docs/adr/README.md](Docs/adr/README.md): architecture decision records.
