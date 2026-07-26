# MediaPipelineRemuxEncodeAIO

MediaPipelineRemuxEncodeAIO is a Windows-first, single-operator media
pipeline for a Plex-style library. It discovers source media, copies sources
to scratch, decides whether each item should remux or encode, runs FFmpeg,
ffprobe, MKVToolNix, and subtitle helpers, writes sidecars and manifests,
publishes completed outputs, and parks unsafe final-output moves for later
pending-publish drain.

The promoted operator surface is a local Python API with a backend-served
vanilla JavaScript WebView, normally hosted in the Tauri/WebView2 shell. The
PowerShell media engine remains the active executor for media work. The WebView
is an operator control surface only: it displays backend-authored state and
sends route intent to the Local API. It must not implement media policy,
filesystem mutation, queue mutation, settings persistence, pending-publish
drain, rename apply, or process lifecycle behavior itself.

For AI/code agents, start with [AGENTS.md](AGENTS.md). For current state and
active backlog, use [docs/CURRENT_PROJECT_STATE.md](docs/CURRENT_PROJECT_STATE.md)
and [docs/OPEN_WORK_CHECKLIST.md](docs/OPEN_WORK_CHECKLIST.md).

## Quick Start

Run commands from the repository root.

```powershell
.\ops\scripts\dev\verify-env.bat
.\ops\scripts\dev\start-api-and-browser.bat
.\ops\scripts\dev\start-tauri-preview.bat -CheckOnly
.\ops\scripts\release\test.ps1
.\ops\scripts\operator\New-RealMediaValidationWorksheet.ps1
```

Use `ops\scripts\dev\start-api-and-browser.bat` when you want the Local API
and the backend-served browser WebView. Use
`ops\scripts\dev\start-tauri-preview.bat` for the Tauri/WebView2 shell; add
`-CheckOnly` to verify prerequisites without opening the shell.

The old root launcher shims and legacy desktop shell are no longer active
surfaces. Use the canonical wrappers under `ops\scripts\`.

## What Runs Today

- The WebView/Tauri path is the promoted daily operator surface.
- The Local API is the long-term boundary between UI and backend behavior.
- The PowerShell engine under `ops\pipeline\engine\` owns current media
  processing, FFmpeg orchestration, subtitle/audio policy, queue planning, and
  publish behavior.
- JSON state files under `LocalBase\State\` remain authoritative. SQLite is a
  shadow/mirror surface for selected records.
- The additive Python/PowerShell stage dispatcher currently enables `ingest`,
  `probe`, and `decide`. Only `ingest` is mutation-capable, and it requires
  strict execute intent plus `confirm_ingest=true`. `transcode`,
  `subtitle-convert`, `audio-mix`, `publish`, `drain`, and `rename` are modeled
  in the stage contract but disabled until each has separate safety coverage.
- Representative real-media validation is operator-attested complete as of
  2026-05-28, and default-launcher/package-mode promotion is operator-confirmed
  complete as of 2026-05-30. Re-run those gates after changes in their risk
  areas.

## Architecture

```text
Tauri/WebView2 shell
  -> backend-served WebView SPA
  -> Python Local API
  -> Python core domain services and contracts
  -> PowerShell media engine
  -> FFmpeg/ffprobe/MKVToolNix/PgsToSrt and filesystem state
```

Primary ownership boundaries:

- Tauri owns desktop lifecycle, backend launch, WebView2 hosting,
  single-instance behavior, and close-readiness enforcement.
- The WebView renders state, stages operator intent, and calls Local API
  routes.
- The Local API owns route contracts, command journal entries, strict JSON
  confirmations, and backend-authored payloads.
- Python core services own domain policy, state readers/writers, DTOs,
  settings/config handling, queue, rename, publish, diagnostics, maintenance,
  network mode, and validation helpers.
- PowerShell owns current pipeline execution, FFmpeg and helper-tool
  invocation, scratch/output movement, subtitle/audio processing, sidecars,
  and publish/drain mechanics.

## Repository Map

| Path | Purpose |
| --- | --- |
| `src\mediapipeline\core\` | Backend domain services, policies, storage, config, queue, rename, publish, diagnostics, maintenance, network, validation, and orchestration |
| `src\mediapipeline\contracts\` | Pydantic contracts and generated JSON schemas |
| `src\mediapipeline\desktop\` | Local API host, route registries, desktop application facade, WebView adapters, and network coordinator/worker code |
| `src\mediapipeline\pipeline\` | Python pipeline helpers, including ASS-to-SRT support |
| `src\mediapipeline\tools\` | Developer, release, generated-context, and change-control tooling |
| `apps\desktop\webview\static\` | Backend-served vanilla-JS WebView SPA, HTML partials, and CSS |
| `apps\desktop\tauri\` | Tauri/WebView2 shell, Rust lifecycle code, and shell validation scripts |
| `apps\desktop\launchers\` | Desktop launcher wrappers |
| `ops\pipeline\entrypoints\` | Stable PowerShell operator/media entry scripts |
| `ops\pipeline\engine\` | Domain-organized PowerShell implementation |
| `ops\pipeline\config\` | Config templates, profiles, setup helpers, schemas, and ignored local PSD1s |
| `ops\pipeline\tests\` | PowerShell pipeline, reliability, unit, and tool-integration checks |
| `ops\scripts\` | Development, operator, release, and smoke wrappers |
| `ops\release\` | Release metadata and structured change packets |
| `tests\python\` | Python/backend/unit/contract tests |
| `tests\webview\` | WebView static and browser-oriented tests |
| `docs\` | Operator docs, architecture docs, inventories, testing runbooks, generated maps, and current state |
| `LocalBase\` | Gitignored local runtime state, manifests, JSON files, and SQLite mirror |

Generated navigation is available in
[docs/generated/PROJECT_INDEX.md](docs/generated/PROJECT_INDEX.md),
[docs/generated/FEATURE_FILE_MAP.md](docs/generated/FEATURE_FILE_MAP.md),
[docs/generated/PIPELINE_MAP.md](docs/generated/PIPELINE_MAP.md), and
[docs/generated/DEPENDENCY_GRAPH.md](docs/generated/DEPENDENCY_GRAPH.md).

## Operator Surfaces

The current WebView exposes pages for Home, Launch, Queue, Completed, Pending
Publish, Rename, Settings, Diagnostics, Maintenance, Network, Telemetry,
Schedule, Reports, Commands, and Contract coverage. These pages are evidence
and command surfaces over backend-owned routes. Browser and WebView smokes are
expected to preserve no-mutation guarantees where a view is read-only.

Important backend capabilities include:

- queue building, source scope evidence, priority, strategy, and per-file
  overrides;
- remux/encode routing, size policy, codec policy, dynamic HDR handling, and
  encoder descriptor evidence;
- subtitle preservation and optional ASS/TX3G/BDPGS to SRT conversion;
- audio passthrough, transcode, downmix, language/default-track policy;
- completed-job manifests, sidecars, pending-publish park/drain, and repair or
  reconcile routes with strict confirmations;
- standalone rename preview/apply/undo with collision and path-boundary checks;
- settings builders, library profiles, runtime evidence, and PSD1 projection;
- diagnostics, command history, maintenance, release packaging, sample
  validation, and network coordinator/worker setup.

## Safety Model

Source media is read, probed, and copied to scratch. It must not be deleted,
overwritten, renamed, or transcoded in place by default. Scratch isolation,
manifest-backed pending publish, strict route confirmations, command journaling,
duplicate-command guards, and close-readiness checks are part of the release
safety model.

High-risk changes include FFmpeg stream mapping, remux/encode routing, subtitle
conversion, audio policy, source/scratch/output movement, pending-publish
manifests and drain, queue launch scope, settings persistence, rename apply,
network lifecycle, command journal behavior, Tauri backend lifecycle, and
release packaging. Read
[docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md](docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md)
before touching those areas.

## Development And Validation

Use the bundled Python runtime for repository tooling and Python validation:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py <module> [args]
```

Useful guardrails:

```powershell
npm run webview:prework:check
npm run webview:check
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.ai_guardrail preflight --no-run
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.ai_guardrail postflight
```

Validation is selected by touched behavior. Docs-only changes should at least
run the docs rung in
[docs/testing/VALIDATION_LADDER_RUNBOOK.md](docs/testing/VALIDATION_LADDER_RUNBOOK.md).
WebView, Local API, settings, rename, pending publish, Tauri, PowerShell media
engine, and real-media policy changes each have stronger rungs.

Every meaningful code, docs, schema, tooling, UI, config, or test change needs
a structured change packet under `ops\release\changes\unreleased\`. See
[docs/change_control/README.md](docs/change_control/README.md).

## Current Open Work

The active checklist is [docs/OPEN_WORK_CHECKLIST.md](docs/OPEN_WORK_CHECKLIST.md).
The current open implementation streams are:

- encoder breadth and AV1/hardware backend activation;
- mutation-capable Python stage dispatch beyond guarded `ingest`;
- opportunistic cleanup of transitional WebView flat `window.*` exports.

Recurring gates remain for representative real-media validation and
package/open/close validation after changes that affect those surfaces.

## Release And Runtime Notes

The release builder creates a cleaned deployable copy or zip and strips live
operator config, generated state/logs, and optional tool bulk unless explicitly
requested.

```powershell
.\ops\scripts\release\build.ps1
.\ops\scripts\release\build.ps1 -Zip -Verify -IncludeTests
```

`-Force` replaces only a directory whose partial or completed release marker is
bound to that exact destination, source root, version, and source revision.
Legacy, copied, mismatched, or reparse-point destinations fail closed; move
them aside manually and build into a new directory. A valid replacement moves
the prior output to a recoverable sibling quarantine and restores it if the new
build fails. Inspect and remove successful-build quarantines manually.

Preferred bundled runtime/tool locations include:

- `apps\desktop\runtime\Python\python.exe`
- `ops\pipeline\runtime\Python\python.exe`
- `ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe`
- `ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe`
- `ops\pipeline\tools\ffmpeg\bin\ffprobe.exe`
- `ops\pipeline\tools\MKVToolNix\mkvmerge.exe`
- `ops\pipeline\tools\PgsToSrt\PgsToSrt.exe`

Local operator config may exist under `ops\pipeline\config\` and can contain
machine-specific paths. Do not include personal config in public or new-user
release packages unless intentionally making a private mirror.

## Documentation

- [AGENTS.md](AGENTS.md): AI/code-agent operating contract.
- [CHANGELOG.md](CHANGELOG.md): shipped-status log.
- [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md): active documentation map.
- [docs/CURRENT_PROJECT_STATE.md](docs/CURRENT_PROJECT_STATE.md): volatile
  current project state.
- [docs/OPEN_WORK_CHECKLIST.md](docs/OPEN_WORK_CHECKLIST.md): active backlog
  and recurring gates.
- [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md):
  concise architecture map.
- [docs/architecture/MODULE_MAP.md](docs/architecture/MODULE_MAP.md): feature
  placement and ownership map.
- [docs/testing/VALIDATION_LADDER_RUNBOOK.md](docs/testing/VALIDATION_LADDER_RUNBOOK.md):
  validation selection.
