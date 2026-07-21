# Current Project State

Last updated: 2026-07-20

This is the fast current-state entry point for AI/code agents. It intentionally
contains present truth rather than a completion log. Use `CHANGELOG.md`,
`docs/architecture/DECISIONS_AND_HISTORY.md`, `docs/ARCHIVED_MD_INDEX.md`, and
the change packets under `ops/release/changes/` for historical evidence.

## What This Project Is

MediaPipelineRemuxEncodeAIO is a Windows-first, single-operator media pipeline
for a Plex-style library. It discovers source media, copies it to scratch,
chooses remux versus encode, runs FFmpeg/ffprobe and helper tools, handles
subtitle/audio policy, writes sidecars and manifests, publishes completed
outputs, and parks unsafe final placement for manifest-backed drain later.

The promoted operator surface is a backend-served WebView SPA in a
Tauri/WebView2 shell. A local Python API owns desktop-facing contracts and
domain services; the PowerShell engine remains the production media engine.

## Current UI Reality

- Tauri/WebView2 is the promoted desktop shell. The removed legacy desktop
  shell is historical and is not an active fallback in this tree.
- The frontend displays backend state, stages operator intent, and calls Local
  API routes. It does not own filesystem mutation, settings persistence, queue
  mutation, media policy, repair/apply, pending-publish drain, rename apply, or
  process lifecycle policy.
- Home is the primary Current Work view. Queue owns planning, Launch owns
  readiness/start, Completed/Pending/Reports own terminal proof, and
  Telemetry/Diagnostics provide supporting evidence and escalation.
- `GET /api/queue` reads the latest backend snapshot without launching work.
  `POST /api/queue/scan` owns source inventory and queue-plan curation. Blank
  Run Once requires a completed scope-matching preview and exact accepted plan
  fingerprint; the PowerShell engine rebuilds and verifies the active plan
  before dispatch. CSV rerun and Network queue workflows remain separate.
- Standard Run Once monitoring is backend-owned through
  `pipeline_run_monitor.v1` and the freshness-gated
  `GET /api/run-monitor` projection. Stale, future, partial, or contradictory
  evidence cannot populate current file, route, worker, stage, or progress
  claims. Synthetic coverage exists; representative real-media coverage for
  this newer monitor remains part of the open rerun gate.
- Network lifecycle/setup and selected Completed/Pending repair/reconcile
  operations are exposed only through backend dry-run and strictly confirmed
  routes. WebView controls send intent and matching fingerprints, not paths or
  mutation policy.

## Main Launchers

Run canonical launchers from the repository root:

```powershell
.\ops\scripts\dev\start-local-api.bat
.\ops\scripts\dev\start-api-and-browser.bat
.\ops\scripts\dev\start-tauri-preview.bat -CheckOnly
.\ops\scripts\dev\start-tauri-preview.bat
.\ops\scripts\release\test.ps1
```

Use `apps\desktop\runtime\Python\python.exe` for repository Python validation.
See `README.md` and `AGENTS.md` for the complete launcher and tooling list.

## Current Architecture

```text
Tauri/WebView2 shell
  -> backend-served WebView SPA
  -> Python Local API
  -> Python domain services and contracts
  -> PowerShell media engine
  -> FFmpeg/ffprobe/MKVToolNix/PgsToSrt and filesystem state
```

- `src/mediapipeline/core/`: backend domain services and policy.
- `src/mediapipeline/contracts/`: Pydantic contracts and generated schemas.
- `src/mediapipeline/desktop/`: Local API host and desktop adapters.
- `apps/desktop/webview/static/` and `apps/desktop/tauri/`: promoted UI/shell.
- `ops/pipeline/`: PowerShell entrypoints, engine, config, runtime, and tests.
- `ops/scripts/`: canonical dev, smoke, operator, and release wrappers.

Use `docs/architecture/ARCHITECTURE.md` for the concise architecture map and
`docs/architecture/MODULE_MAP.md` for feature placement and ownership.

## Known-Good Behavior To Preserve

The durable safety contract is in `AGENTS.md`; high-risk boundaries are in
`docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`. In particular:

- Source mutation is forbidden by default; processing uses scratch copies.
- Pending publish is manifest-backed and drained only through backend policy.
- Original subtitles are preserved by default; failed conversion/OCR routes to
  review rather than silent bad publish.
- Audio and remux/encode behavior are profile/config driven.
- Strict JSON confirmations, command journaling, duplicate-command guards, and
  close-readiness are release-critical.
- JSON files remain authoritative where documented; the SQLite state database
  is an optional, rebuildable observability mirror.

## Current Operating State

- The promoted WebView exposes Home, Queue, Launch, Completed, Pending Publish,
  Rename, Settings, Diagnostics, Maintenance, Network, Telemetry, Schedule,
  Reports, Commands, Contract, Metrics, and Sample Validation workflows.
- Settings metadata and Library Profile inheritance are backend-owned. The
  WebView stages edits; backend Preview/Save decides validity and persistence.
  Runtime-effective evidence is diagnostic and is not persisted policy.
- Queue, Completed, Pending Publish, Diagnostics, and Sample Validation expose
  read-only trust/evidence handoffs without expanding frontend mutation
  authority. Selected repair/reconcile applies remain backend validated,
  fingerprint bound, journaled, and strictly confirmed.
- The Python stage dispatcher supports read-only `probe`/`decide`, guarded
  source-to-scratch `ingest`, scratch-only single-file `rename`, and standalone
  scratch ASS/SSA-to-SRT `subtitle-convert`. PowerShell still owns production
  transcode, audio, integrated subtitle, publish, drain, and final placement.
- WebView access is namespace-first. The authoritative generated inventory
  currently reports 532 flat `window.*` assignments across 235 files; cleanup
  is opportunistic by touched domain and requires page-owned static/browser
  evidence.
- Queue/run-monitor, settings/library, network, repair/reconcile, lifecycle
  recovery, redacted support bundles, and effective-settings provenance are
  backend-authored operator surfaces rather than independent frontend policy.

## Present Release Posture

- WebView/Tauri default-launcher promotion is closed by operator confirmation
  from 2026-05-30.
- Package/open/close acceptance is current for integrated runtime commit
  `52e9be6564aeb13571c0231e2b55ea2903cbc0c0`: copied-folder and extracted-ZIP
  startup, AppData state externalization, safe close, immutable install-root,
  and no-leftover-child checks passed. Re-run after launcher, packaging, Tauri,
  Local API bootstrap, or release-layout changes.
- The latest accepted broad media-policy proof remains
  MP-CHANGE-2026-0622-001: 92 cases executed, 76 outputs published and
  ffprobe-verified, and 92/92 source hashes unchanged. Targeted 2026-06-22
  evidence also covers two-real-video topology, Dolby Vision P8.1 metadata, and
  HDR10+ metadata preservation.
- The newer representative real-media rerun is not complete. Its 2026-07-11
  attempt stopped at strict Policy Proof preflight because all 15 catalog
  SHA-256 values are placeholders, the external fixture root is absent, and
  `policy_proof_sources.json` is not provisioned. Therefore no current
  release-ready claim is made for later high-risk monitor/encoder/media slices.
  Exact prerequisites are in `docs/RealMediaValidationRuns/README.md`.

## Recent Important Completion Notes

This anchor is retained for older links, but completed detail no longer lives in
the active status document. Use:

- `CHANGELOG.md` for notable shipped/unreleased changes;
- `docs/REMEDIATION_CHANGELOG.md` for the compact index into detailed,
  mechanically preserved remediation history;
- `docs/architecture/DECISIONS_AND_HISTORY.md` for durable decisions and
  milestones;
- `docs/ARCHIVED_MD_INDEX.md` for completed plans, audits, and checklist
  locations; and
- `ops/release/changes/` plus `docs/RealMediaValidationRuns/README.md` for
  change-scoped validation evidence.

## Active Gaps

`docs/OPEN_WORK_CHECKLIST.md` is authoritative for unresolved work and gates.
The current high-level gaps are:

- representative real-media rerun prerequisites and execution;
- representative AV1/NVENC validation plus separate QSV/AMF activation work;
- separately gated Python mutation-stage expansion beyond the narrow dispatcher;
- opportunistic WebView flat-export reduction; and
- upstream-blocked Linux GTK `glib` dependency remediation.

## Validation Expectations

Select the smallest safe rung from
`docs/testing/VALIDATION_LADDER_RUNBOOK.md`. Documentation-only changes require
active-reference/path checks and change-packet validation. Any FFmpeg/media,
subtitle, audio, publish/drain, source/scratch/output movement, packaging, or
shell-lifecycle change must also satisfy its named recurring gate in
`docs/OPEN_WORK_CHECKLIST.md`.

## High-Risk Areas

Read `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` before changing media policy,
source/scratch/output movement, pending publish/drain, queue launch, settings,
rename, network lifecycle, command journal/close-readiness, Tauri lifecycle, or
release packaging. `AGENTS.md` contains the stable invariant summary.

## Obsolete Or Non-Authoritative Instructions

Old Claude/Codex handoffs, completed checklists, archived audits, and historical
plans are evidence only unless a current authority doc explicitly reopens them.
Vendor Markdown is not project guidance. Documentation authority and conflict
resolution follow `AGENTS.md` and `docs/DOCS_INDEX.md`.

## Best First Reads

1. `AGENTS.md`
2. `docs/CURRENT_PROJECT_STATE.md`
3. `docs/OPEN_WORK_CHECKLIST.md`
4. `docs/architecture/MODULE_MAP.md`
5. `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
6. `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
7. `docs/DOCS_INDEX.md`
