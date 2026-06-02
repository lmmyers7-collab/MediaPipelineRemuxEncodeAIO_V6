# Architecture

Short human-maintained map of how MediaPipelineRemuxEncodeAIO V6 is put
together. For the *why*, see the ADRs under `Docs/adr/`. For current
operating state, see `../CURRENT_PROJECT_STATE.md`. For the *change log*,
see `../../CHANGELOG.md`. For the *per-file map*, see
`../generated/PROJECT_INDEX.md` and `../../summaries/`.

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
│  ORCHESTRATOR — Python (app/<domain>/ plus DesktopApp Local API   │
│  host and WebView compatibility package)                         │
│                                                                  │
│  api/ orchestration/ processes/ queue/ decide/ publish/          │
│  rename/ storage/ network/ observability/ config/ contracts/     │
│  common/                                                         │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ subprocess(stage, payload-json)
┌──────────────────────────────────▼───────────────────────────────┐
│  EXECUTOR — PowerShell (engine/<domain>/<role>.ps1 loaded by      │
│  Pipeline entry scripts and wrapped by engine/entrypoint.ps1)     │
│                                                                  │
│  FFmpeg, MKVToolNix, PgsToSrt invocations                        │
└──────────────────────────────────────────────────────────────────┘

State:  LocalBase/State/*.json authoritative; SQLite mirror is shadow-only
Files:  scratch → output → pending-publish → published
```

## Where the canonical pieces live

| Concern                  | Active V6 locations                                         | Continuing direction                | ADR    |
| ------------------------ | ----------------------------------------------------------- | ----------------------------------- | ------ |
| Operator API             | `DesktopApp/mediapipeline_desktop_app/api/`, `app/api/`     | Keep backend authority centralized  | 0006   |
| Job lifecycle, queue     | `app/processes/`, `app/orchestration/`, `app/queue/`        | Continue domain-owned orchestration | 0001   |
| Source discovery, scratch| `Pipeline/MediaPipeline.ps1`, `engine/storage/`, `engine/queue/` | Keep source-copy and scratch policy backend-owned | 0001/2 |
| Probe, naming parse      | `engine/probe/`, `engine/naming/`, `app/contracts/source_media*.py` | Keep source facts read-only before routing | 0001/2 |
| Remux-vs-encode policy   | `app/decide/`, `engine/decide/`                             | Keep decisions separate from FFmpeg args | 0001/2 |
| FFmpeg invocation        | `Pipeline/MediaPipeline/`, `engine/process/`                | Keep tool execution in PowerShell   | 0002   |
| Subtitle conversion      | `engine/subtitles/`, `Pipeline/ass_to_srt*`                 | Keep conversion failures review-bound | 0002 |
| Audio policy             | `engine/audio/`                                             | Keep profile/config-driven routing  | 0002   |
| Pending publish + drain  | `app/publish/`, `engine/publish/`                           | Keep park/drain manifest-backed     | 0001/2 |
| Rename plan/apply/undo   | `app/rename/`, `engine/naming/`                             | Keep apply/undo backend-owned       | 0001   |
| State store              | `LocalBase/State/*.json`, `app/storage/db.py` mirror        | JSON remains authoritative for now  | 0003   |
| Logs / events            | `RunLogs/*.txt`, JSON-line helpers, SQLite mirror events    | Continue structured evidence rollout | 0005 |
| Config shape             | PSD1 + `app/config/metadata*.py` + WebView JSON             | `app/contracts/config.py` (pydantic)| 0004   |
| Stage I/O contracts      | `Pipeline/Schemas/*.json` (hand-written)                    | `app/contracts/stages.py` to generated `schemas/`| 0004 |
| Coordinator/worker       | `DesktopApp/.../network/`, `app/network/`                   | WebView lifecycle remains read-only | —      |
| Desktop shell            | `DesktopApp/tauri_shell/` (Tauri + WebView2)                | unchanged                           | 0008   |
| WebView SPA              | `DesktopApp/.../ui_web/static/` (vanilla JS)                | unchanged for now                   | 0007   |

## Boundaries (which module owns what)

The rows below are ownership domains. Active V6 package/script paths are in
the table above and in `../generated/PROJECT_INDEX.md`; not every domain has
a same-named folder in the current compatibility window.

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

Nine canonical stages are defined in `app/contracts/stages.py` with
explicit `schema_version: "v1"`:

`ingest` → `probe` → `decide` → `transcode` → `subtitle-convert`
→ `audio-mix` → `publish` (or park) → `drain` (when parked) → `rename`.

`../generated/PIPELINE_MAP.md` enumerates each stage with its payload and result
types. The Phase 3 runner boundary calls
`engine/entrypoint.ps1 -Stage <stage> -PayloadJson <payload-json-or-path>`
per ADR-0002. In the current V6.x maintenance state, the read-only
`probe` and `decide` stages are enabled through that dispatcher;
mutation-capable stages remain modeled but disabled until safety coverage
and real-media validation prove the replacement path.

## State and files

- **Scratch → output → pending-publish → published.** Files move
  forward, never overwrite a source. `pending-publish` parks output
  when the final root is unsafe; `drain` later moves parked output to
  `published` with manifest evidence.
- **State** today is JSON files in `LocalBase/State/`. Phase 4 mirrors
  selected command, event, queue, and completed-job records into a
  SQLite database under the runtime state root, but JSON remains
  authoritative until a later cutover.

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
- **Config.** Pydantic in `app/contracts/config.py` is the contract
  source of truth for generated schemas and Python validation
  (ADR-0004). PSD1 remains the operator-facing seed/runtime file during
  this V6.x compatibility window.

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
- Current operating state: `Docs/CURRENT_PROJECT_STATE.md`
- Stage contracts: `app/contracts/stages.py`, `../generated/PIPELINE_MAP.md`
- Config contract: `app/contracts/config.py`
- Per-file map: `../generated/PROJECT_INDEX.md`, `../../summaries/`
- Operator boundaries: `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Testing: `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`
