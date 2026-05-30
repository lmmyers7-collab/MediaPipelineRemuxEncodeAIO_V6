# MediaPipelineRemuxEncodeAIO V6

MediaPipelineRemuxEncodeAIO V6 is a Windows-first, single-operator media
pipeline for a Plex-style library. It discovers source media, copies sources
to scratch, decides remux versus encode, runs FFmpeg/ffprobe plus helper
tools, handles subtitles and audio, writes sidecars and manifests, publishes
completed outputs, and parks unsafe final-output moves for later drain.

This repository is still a V6.x maintenance/overhaul workspace, not a V7
release. The local Phase 6 legacy-surface burn-down is complete, but V7/default
launcher promotion remains blocked until the PG-3 clean-machine package-mode
gate and operator acceptance are complete. Representative real-media validation
is complete by operator attestation as of 2026-05-28.

## Start Here

For operators:

```powershell
.\scripts\verify-env.bat
.\scripts\dev\start-api-and-browser.bat
.\scripts\dev\start-tauri-preview.bat -CheckOnly
.\scripts\release\test.ps1
.\scripts\operator\New-RealMediaValidationWorksheet.ps1
```

The canonical browser launcher is `scripts\dev\start-api-and-browser.bat`.
It starts the Local API and opens the backend-served browser WebView.

For AI/code agents, start with [AGENTS.md](AGENTS.md). For current project
state and open gates, read [Docs/CURRENT_PROJECT_STATE.md](Docs/CURRENT_PROJECT_STATE.md)
and [OPEN_WORK_CHECKLIST.md](OPEN_WORK_CHECKLIST.md).

## Supported Operator Paths

- `scripts\dev\start-local-api.bat` starts the local Python API.
- `scripts\dev\start-api-and-browser.bat` starts the API and opens the
  backend-served WebView.
- `scripts\dev\start-tauri-preview.bat` starts the Tauri/WebView2 shell;
  `-CheckOnly` validates prerequisites without opening the shell.
- `scripts\release\test.ps1` runs the release self-test.
- `scripts\operator\New-RealMediaValidationWorksheet.ps1` creates a
  worksheet for representative real-media validation.

The old root launcher shims were removed during the local Phase 6 burn-down.
Documentation and automation should use the `scripts\` paths above.

## Current Progress

As of 2026-05-30:

- Phase 6 local legacy removal is complete: removed root launcher shims, flat
  Python facade/service compatibility paths, old command-payload adapters, and
  `Pipeline\Modules` are no longer active surfaces.
- Active domain code now lives under `app\<domain>` and `engine\<domain>`,
  while `DesktopApp\mediapipeline_desktop_app` remains the Local API/WebView
  host.
- WebView split guardrails, generated WebView baselines, route-ownership checks,
  public-contract checks, and lint-budget checks are in place for continued
  plain-script asset cleanup.
- PG-3 clean-machine package-mode validation is still open and remains the hard
  default-launcher promotion gate.

## Current Architecture

- `app/` contains the active domain-organized Python contracts, services,
  facades, orchestration, storage, validation, and policy adapters created by
  the overhaul.
- `DesktopApp/mediapipeline_desktop_app/` hosts the current Python Local API,
  compatibility package, and backend-served WebView integration.
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/` contains the vanilla
  JavaScript WebView SPA.
- `DesktopApp/tauri_shell/` contains the Tauri/WebView2 shell.
- `engine/` contains the active domain-organized PowerShell implementation.
- `Pipeline/` contains root engine entry scripts, config/profiles, schemas,
  bundled tools, helper scripts, and PowerShell tests.
- `schemas/`, `tests/`, `summaries/`, and `Docs/generated/` contain generated
  contracts, behavior tests, AI navigation summaries, and drift-check outputs.

The backend owns media policy, filesystem mutation, settings persistence,
queue mutation, pending-publish drain, rename apply, and process lifecycle.
The WebView/Tauri surface must stay an operator UI over backend-owned routes.

## Promotion Gates

Before any daily-driver or V7 promotion claim:

- PG-3 package-mode launch/close must pass on a separate clean Windows
  machine.
- Operator acceptance must confirm WebView/Tauri package-mode workflows on the
  target machine.

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
