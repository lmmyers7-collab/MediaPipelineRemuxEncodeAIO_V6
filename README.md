# MediaPipelineRemuxEncodeAIO

MediaPipelineRemuxEncodeAIO is a Windows-first, single-operator media
pipeline for a Plex-style library. It discovers source media, copies sources
to scratch, decides remux versus encode, runs FFmpeg/ffprobe plus helper
tools, handles subtitles and audio, writes sidecars and manifests, publishes
completed outputs, and parks unsafe final-output moves for later drain.

This repository is the active promoted current workspace. The legacy-surface
cleanup and default-launcher promotion are complete by operator confirmation
on 2026-05-30. Representative real-media validation is complete by operator
attestation as of 2026-05-28 and becomes stale after high-risk media behavior
changes.

## Start Here

For operators:

```powershell
.\ops\scripts\dev\verify-env.bat
.\ops\scripts\dev\start-api-and-browser.bat
.\ops\scripts\dev\start-tauri-preview.bat -CheckOnly
.\ops\scripts\release\test.ps1
.\ops\scripts\operator\New-RealMediaValidationWorksheet.ps1
```

The canonical browser launcher is `ops\scripts\dev\start-api-and-browser.bat`.
It starts the Local API and opens the backend-served browser WebView.

For AI/code agents, start with [AGENTS.md](AGENTS.md). For current project
state and remaining work, read [docs/CURRENT_PROJECT_STATE.md](docs/CURRENT_PROJECT_STATE.md)
and [docs/OPEN_WORK_CHECKLIST.md](docs/OPEN_WORK_CHECKLIST.md).

## Supported Operator Paths

- `ops\scripts\dev\start-local-api.bat` starts the local Python API.
- `ops\scripts\dev\start-api-and-browser.bat` starts the API and opens the
  backend-served WebView.
- `ops\scripts\dev\start-tauri-preview.bat` starts the Tauri/WebView2 shell;
  `-CheckOnly` validates prerequisites without opening the shell.
- `ops\scripts\release\test.ps1` runs the release self-test.
- `ops\scripts\operator\New-RealMediaValidationWorksheet.ps1` creates a
  worksheet for representative real-media validation.

The old root launcher shims were removed during the legacy-surface cleanup.
Documentation and automation should use the `ops\scripts\` paths above.

## Root Shell Contract

The repository root is intentionally small. Tracked root files are limited to
conventional repository controls and package entrypoints:

- VCS/editor/automation controls: `.gitignore`, `.rgignore`,
  `.pre-commit-config.yaml`, `.github/`, `.claude/`.
- Package/tool manifests that tools discover at root: `pyproject.toml`,
  `package.json`, `package-lock.json`, `eslint.config.js`, `requirements/`.
- Human entry documents: `README.md`, `AGENTS.md`, `CHANGELOG.md`.
- Grouped project trees: `src/`, `apps/`, `ops/`, `tests/`, `docs/`.

Do not add loose Python implementation modules, launchers, generated docs,
runtime state, logs, local configs, bundled tools, or build output at root.
Generated/runtime material belongs under ignored grouped locations such as
`apps/desktop/runtime/`, `ops/pipeline/runtime/`, `ops/pipeline/tools/`,
`ops/pipeline/config/MediaPipeline_config*.psd1`, `LocalBase/`, or `RunLogs/`.

## Current Progress

As of 2026-06-04:

- Legacy-surface removal is complete: removed root launcher shims, flat
  Python facade/service compatibility paths, old command-payload adapters, and
  `Pipeline\Modules` are no longer active surfaces.
- Active Python backend code now lives under the `mediapipeline` namespace in
  `src\mediapipeline\core`, `src\mediapipeline\contracts`,
  `src\mediapipeline\desktop`, `src\mediapipeline\pipeline`, and
  `src\mediapipeline\tools`.
- Active PowerShell pipeline code and operator automation live under
  `ops\pipeline` and `ops\scripts`; release packets/metadata live under
  `ops\release`.
- WebView split guardrails, generated WebView baselines, route-ownership checks,
  public-contract checks, and lint-budget checks are in place for continued
  plain-script asset cleanup.
- Default-launcher promotion is complete by operator confirmation on
  2026-05-30.

## Target Layout

- `src/mediapipeline/core/`: backend domain services, policies, orchestration,
  storage, config, queue, rename, publish, telemetry, and status code.
- `src/mediapipeline/contracts/`: Python contracts and generated JSON schemas.
- `src/mediapipeline/desktop/`: Local API host and desktop-facing adapters.
- `src/mediapipeline/pipeline/`: Python helpers used by the media pipeline,
  including the ASS-to-SRT CLI package.
- `src/mediapipeline/tools/`: Python developer/release/change-control tools.
- `apps/desktop/webview/static/`: backend-served vanilla JavaScript WebView SPA.
- `apps/desktop/tauri/`: Tauri/WebView2 shell.
- `apps/desktop/launchers/`: desktop launcher wrappers.
- `ops/pipeline/entrypoints/`: stable PowerShell entry scripts.
- `ops/pipeline/engine/`: domain-organized PowerShell implementation.
- `ops/pipeline/config/`: templates, profiles, schemas, and ignored local PSD1s.
- `ops/pipeline/tests/`: PowerShell pipeline tests.
- `ops/scripts/dev|operator|release|smoke/`: development, operator, release,
  and smoke wrappers.
- `ops/release/changes|metadata/`: structured change packets and release state.
- `tests/python/` and `tests/webview/`: Python/backend and WebView tests.
- `docs/` and `docs/generated/`: active docs plus generated navigation output.

The backend owns media policy, filesystem mutation, settings persistence,
queue mutation, pending-publish drain, rename apply, and process lifecycle.
The WebView/Tauri surface must stay an operator UI over backend-owned routes.

## Validation And Revalidation

Default-launcher promotion is complete by operator confirmation on
2026-05-30. Continue to validate package launch, close behavior, and the
operator surface after launcher, packaging, Local API, or Tauri changes.

Representative real-media validation has covered remux, encode/size,
subtitle conversion, audio policy, and pending-publish/final placement by
operator attestation. Rerun it after any media-policy, subtitle, audio,
publish, drain, source/scratch/output movement, or cleanup behavior change.

## Documentation

- [CHANGELOG.md](CHANGELOG.md): shipped-status log.
- [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md):
  concise architecture map.
- [docs/generated/PROJECT_INDEX.md](docs/generated/PROJECT_INDEX.md) and
  [docs/generated/PIPELINE_MAP.md](docs/generated/PIPELINE_MAP.md):
  generated navigation artifacts.
- [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md): active documentation map.
- [docs/adr/README.md](docs/adr/README.md): architecture decision records.

