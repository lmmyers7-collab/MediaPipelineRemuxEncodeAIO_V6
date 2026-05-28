# Architecture

Short human-maintained map of how MediaPipelineRemuxEncodeAIO V6 is put
together. For the *why*, see the ADRs under `Docs/adr/`. For the *plan
to get to V7*, see `ARCHITECTURAL_OVERHAUL_PLAN.md`. For the *change
log*, see `CHANGELOG.md`. For the *per-file map*, see
`PROJECT_INDEX.md` and `summaries/`.

If those four pointers conflict, treat the ADRs as authoritative and
update this file to match.

## One-paragraph summary

V6 is a Windows-first, single-operator media pipeline: discover source
media, copy to scratch, decide remux vs encode, run FFmpeg (and helpers
for subtitles, audio, naming), publish results or park them in a
pending-publish area for later drain. Operator control is a local
Python HTTP API rendered by a vanilla-JS WebView SPA inside a
Tauri/WebView2 shell.

## Top-level shape

```
┌──────────────────────────────────────────────────────────────────┐
│  OPERATOR SURFACE                                                │
│                                                                  │
│   Tauri / WebView2 shell  ◄──HTTP──►  Local API (Python)         │
│   (DesktopApp/tauri_shell)            (DesktopApp/mediapipeline_ │
│                                        desktop_app/api/)         │
└────────────────────────────────────┬─────────────────────────────┘
                                     │ JSON @ 127.0.0.1
┌────────────────────────────────────▼─────────────────────────────┐
│  ORCHESTRATOR — Python (today: DesktopApp/.../service_*,         │
│  facade_*; target: app/<domain>/)                                │
│                                                                  │
│  api/ orchestration/ ingest/ metadata/ decide/ transcode/        │
│  subtitles/ audio/ publish/ rename/ storage/ network/            │
│  observability/ config/ contracts/ common/                       │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ subprocess(stage, payload-json)
┌──────────────────────────────────▼───────────────────────────────┐
│  EXECUTOR — PowerShell (today: Pipeline/Modules/*.ps1;           │
│  target: engine/<domain>/<role>.ps1 behind engine/entrypoint.ps1)│
│                                                                  │
│  FFmpeg, MKVToolNix, PgsToSrt invocations                        │
└──────────────────────────────────────────────────────────────────┘

State:  LocalBase/State/*.json today → state/state.sqlite (ADR-0003)
Files:  scratch → output → pending-publish → published
```

## Where the canonical pieces live

| Concern                  | Today                                                       | Target                              | ADR    |
| ------------------------ | ----------------------------------------------------------- | ----------------------------------- | ------ |
| Operator API             | `DesktopApp/mediapipeline_desktop_app/api/`                 | `app/api/`                          | 0006   |
| Job lifecycle, queue     | `DesktopApp/.../service_queue*.py`, `service_processes*.py` | `app/orchestration/`                | 0001   |
| Source discovery, scratch| `Pipeline/Modules/Ingest*.ps1`                              | `app/ingest/` + `engine/ingest/`    | 0001/2 |
| Probe, naming parse      | `Pipeline/Modules/MediaProbe.*.ps1`, `Naming.*.ps1`         | `app/metadata/` + `engine/...`      | 0001/2 |
| Remux-vs-encode policy   | `Pipeline/Modules/Routing.*.ps1`                            | `app/decide/`                       | 0001/2 |
| FFmpeg invocation        | `Pipeline/Modules/Ffmpeg.*.ps1`                             | `engine/ffmpeg/`, `engine/transcode/`| 0002  |
| Subtitle conversion      | `Pipeline/Modules/Subtitles.*.ps1`                          | `engine/subtitles/`                 | 0002   |
| Audio policy             | `Pipeline/Modules/Audio.*.ps1`                              | `engine/audio/`                     | 0002   |
| Pending publish + drain  | `Pipeline/Modules/Pending*.ps1`, `service_pending_publish*` | `app/publish/`, `engine/publish/`   | 0001/2 |
| Rename plan/apply/undo   | `Pipeline/Modules/Naming.*.ps1`, `service_rename*.py`       | `app/rename/`                       | 0001   |
| State store              | `LocalBase/State/*.json`                                    | `state/state.sqlite`                | 0003   |
| Logs / events            | `RunLogs/*.txt`, ad-hoc `logging`                           | JSON Lines → `state.sqlite.events`  | 0005   |
| Config shape             | PSD1 + `config_schema*.py` (5 files) + WebView JSON         | `app/contracts/config.py` (pydantic)| 0004   |
| Stage I/O contracts      | `Pipeline/Schemas/*.json` (hand-written)                    | `app/contracts/stages.py` → generated `schemas/`| 0004 |
| Coordinator/worker       | `DesktopApp/.../network/`                                   | `app/network/`                      | —      |
| Desktop shell            | `DesktopApp/tauri_shell/` (Tauri + WebView2)                | unchanged                           | 0008   |
| WebView SPA              | `DesktopApp/.../ui_web/static/` (vanilla JS)                | unchanged for now                   | 0007   |

## Boundaries (which module owns what)

| Module           | Owns                                              | Does not own                          |
| ---------------- | ------------------------------------------------- | ------------------------------------- |
| `api/`           | HTTP transport, payload schemas, journal          | Pipeline behavior, file I/O           |
| `orchestration/` | Job lifecycle, queue, scheduling, retries         | Media decisions, file moves           |
| `ingest/`        | Source discovery, scratch copy, dedupe            | Probing decisions, output paths       |
| `metadata/`      | Probe, naming parse, sidecar read                 | Routing decisions                     |
| `decide/`        | Remux-vs-encode, ladder, size policy              | FFmpeg args                           |
| `transcode/`     | FFmpeg invocation, attempt loop, result classify  | Decisions about what to encode        |
| `subtitles/`     | Subtitle conversions, fallbacks                   | Audio, video                          |
| `audio/`         | Channel/codec policy plus args                    | Subtitles, video                      |
| `publish/`       | Pending park, drain, final placement, manifest    | Source/scratch                        |
| `rename/`        | Plan/apply/undo, parsers                          | Pipeline orchestration                |
| `storage/`       | SQLite state DB, locks, path layout               | Business logic                        |
| `network/`       | Coordinator/worker                                | Pipeline decisions                    |
| `observability/` | Logs, journal, metrics, telemetry                 | Business decisions                    |
| `config/`        | Schema, load/save, drift checks                   | Runtime state                         |
| `contracts/`     | Pydantic models, schema generation                | Behavior                              |
| `common/`        | Paths, errors, retries                            | Anything domain-specific              |

## Pipeline stages

Nine canonical stages, defined as dataclasses in
`app/contracts/stages.py` with explicit `schema_version: "v1"`:

`ingest` → `probe` → `decide` → `transcode` → `subtitle-convert`
→ `audio-mix` → `publish` (or park) → `drain` (when parked) → `rename`.

`PIPELINE_MAP.md` enumerates each stage with its payload and result
types. The orchestrator calls `engine/entrypoint.ps1 <stage>
<payload-json>` per ADR-0002.

## State and files

- **Scratch → output → pending-publish → published.** Files move
  forward, never overwrite a source. `pending-publish` parks output
  when the final root is unsafe; `drain` later moves parked output to
  `published` with manifest evidence.
- **State** today is JSON files in `LocalBase/State/`. ADR-0003 moves
  this to `state/state.sqlite` (queue, jobs, attempts, events,
  commands, pending publish index, audit records, probe cache, config
  history). File-state stays only where the artifact is genuinely
  external (e.g. parked-payload manifest next to the payload).

## Cross-cutting concerns

- **Errors.** Hierarchy under `MediaPipelineError`
  (`{Ingest,Probe,Routing,Transcode,Subtitle,Audio,Publish,Rename,Network,Config}Error`).
  Each carries a stable `code` and `context` dict (ADR-0005,
  Phase 4).
- **Retries.** Centralized policy in `app/common/retries.py`
  (Phase 4): ingest = 3 + backoff, transcode = 1, publish/drain = 5 +
  backoff, network = 5 + jitter. Retries persisted to the journal.
- **Logs.** JSON Lines on stderr from `engine/`, structured records
  from `app/`. Orchestrator persists into `events` table (ADR-0005).
- **Config.** Pydantic in `app/contracts/config.py` is the source of
  truth (ADR-0004). PSD1 is the operator-facing seed/runtime file;
  PowerShell never reads it directly.

## High-risk areas (do not casually change)

Per `AGENTS.md §7` and `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`:

- FFmpeg command generation and stream mapping.
- Subtitle ASS/TX3G/BDPGS/SRT conversion paths.
- Audio passthrough/transcode/downmix policy.
- Source/scratch/output file movement and cleanup.
- Pending publish manifests, drain, sidecar carry-forward, repair logic.
- Queue launch scope, CSV rerun, schedule start behavior.
- Settings schema/defaults/persistence.
- Command journal and backend close-readiness.
- Tauri backend lifecycle ownership.

Any change touching these requires the validation rung named in
`AGENTS.md §5`, up to and including real-media samples.

## Where to look next

- ADRs: `Docs/adr/`
- Plan of record: `ARCHITECTURAL_OVERHAUL_PLAN.md`
- Stage contracts: `app/contracts/stages.py`, `PIPELINE_MAP.md`
- Config contract: `app/contracts/config.py`
- Per-file map: `PROJECT_INDEX.md`, `summaries/`
- Operator boundaries: `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Testing: `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`
