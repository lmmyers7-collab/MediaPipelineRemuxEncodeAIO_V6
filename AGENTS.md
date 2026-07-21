# AGENTS.md - AI Entry Point

This is the stable operating contract for AI/code agents in this repository.
Use it for safety boundaries, architecture, placement, navigation, change
control, and validation. Use [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) for the
active documentation map and these files for volatile status:

- [`docs/CURRENT_PROJECT_STATE.md`](docs/CURRENT_PROJECT_STATE.md)
- [`docs/OPEN_WORK_CHECKLIST.md`](docs/OPEN_WORK_CHECKLIST.md)
- [`CHANGELOG.md`](CHANGELOG.md)

Historical Claude/Codex handoff files are not active guidance unless a current
document explicitly reopens them.

## 1. Architecture And Ownership

The active layers are:

```text
Tauri/WebView2 shell -> backend-served WebView SPA -> Python Local API
  -> Python domain services/contracts -> PowerShell media engine
  -> FFmpeg/ffprobe/MKVToolNix/PgsToSrt and filesystem state
```

The frontend displays backend-authored state, stages operator intent, and calls
backend routes. Backend services and the PowerShell engine own media policy,
state and filesystem mutation, process lifecycle, and evidence. Calls must
respect the directionality and ownership rules in
[`docs/architecture/MODULE_MAP.md`](docs/architecture/MODULE_MAP.md); use
[`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) for
concise orientation.

## 2. Non-Negotiable Invariants

1. **Source mutation is forbidden by default.** Source media may be read,
   probed, or copied to scratch. Do not delete, overwrite, rename, or transcode
   source media unless an explicitly named safe-delete policy is intentionally
   enabled and validated.
2. **Backend owns mutation and media policy.** WebView/Tauri must not implement
   filesystem mutation, settings persistence, queue mutation, pending-publish
   drain, rename apply, repair/reconcile apply, network lifecycle policy, or
   FFmpeg/media policy independently.
3. **Scratch isolation is mandatory.** Pipeline processing uses scratch copies
   so failure or interruption cannot corrupt sources.
4. **Pending publish is manifest-backed.** Park unsafe final output and drain it
   later with evidence. Never bypass park/drain flows or infer drain safety in
   the frontend.
5. **Original subtitles are preserved by default.** Configured preferred-
   language SRT generation may be added; OCR/conversion failure goes to review,
   never silent bad publish.
6. **Audio policy is profile/config driven.** Do not casually alter
   passthrough, transcode, downmix, default-language, or channel policy.
7. **Strict JSON confirmations are mandatory.** Routes requiring fields such
   as `confirm_save`, `confirm_apply`, `confirm_promote`, or lifecycle
   confirmations must reject missing or non-boolean values.
8. **Command journal, duplicate-command guards, and close-readiness are
   release-critical.** They prevent hidden failures, duplicate starts, and
   unsafe shutdown during active work.
9. **Generated mirrors are not automatically authoritative.** Keep authority
   explicit for JSON state, manifests, sidecars, SQLite mirrors, generated
   summaries, and WebView evidence.

### Right-Sized Safety Protocol

- Reuse an existing invariant or backend boundary before adding a new control.
- Use the least cumbersome control that prevents the named hazard; prefer
  backend validation, disabled states, and actionable errors.
- Do not stack frontend warnings or confirmations over backend strict
  confirmations, dry-runs, or manifest-backed flows without a demonstrated
  gap.
- Treat read-only, preview-only, and reversible operations as normal workflows.
- If a new block, confirmation, quarantine, or review step is still necessary,
  document the hazard, why existing control is insufficient, and how the
  operator proceeds.
- Remove obsolete safety layers when a stronger lower-level control makes them
  redundant.

Before touching any high-risk area, read
[`docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`](docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md).

## 3. Placement Rules

Use the existing domain layout and
[`docs/architecture/MODULE_MAP.md`](docs/architecture/MODULE_MAP.md). Do not
create compatibility surfaces or loose files.

- Python implementation belongs under `src/mediapipeline/`, never at repository
  root.
- Do not add `facade_*.py`, `service_*.py`, or `command_payloads_*.py` at old
  flat paths. Use `src/mediapipeline/core/<domain>/<role>.py` or a
  `src/mediapipeline/desktop/` adapter.
- Active PowerShell implementation belongs under
  `ops/pipeline/engine/<domain>/<role>.ps1`. Do not add files to legacy
  `Pipeline/Modules/` or dotted module-shim paths.
- Do not reintroduce removed root launcher callers; canonical wrappers live
  under `ops/scripts/`.
- Do not add top-level Markdown status/report/checklist files such as
  `*_REPORT.md`, `*_FIXES.md`, or `*_CHECKLIST.md`. Update a canonical document
  or the release/change record.
- Do not invent a new source of truth. The stable active set is `README.md`,
  `AGENTS.md`, `CHANGELOG.md`, `docs/CURRENT_PROJECT_STATE.md`,
  `docs/OPEN_WORK_CHECKLIST.md`, and `docs/DOCS_INDEX.md`.
- Put new smoke wrappers in `ops/scripts/smoke/`, never at repository root.
- When adding routes, DOM IDs, command surfaces, config keys, state files, or
  public WebView exports, update the matching inventory or generated contract
  in the same change.

## 4. Required AI Navigation Workflow

This repository is large. After reading this file:

1. Use the read-only `mediapipeline-code` MCP server when available. Call
   `repo_context` with the actual task and its default 2,000-token budget; use
   `code_lookup` for ownership, relationships, tests, and validation; then use
   bounded `code_read`. Use `code_search` only for a precise symbol/string or a
   low-confidence result.
2. If that server is unavailable, run the deterministic fallback from the
   repository root:

   ```powershell
   .\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.context_slice --task "<task>" --budget 2000
   ```

3. Open only returned summaries, boundary documents, source, and tests. Read
   `docs/CURRENT_PROJECT_STATE.md` only when current status matters and
   `docs/OPEN_WORK_CHECKLIST.md` only when backlog state matters.

Use `rg` and `rg --files` for discovery. Before opening source, read its
generated summary when one exists; open full source when exact behavior or
evidence is required or the summary marks `token_priority: high`. Generated
maps under `docs/generated/` are query aids. Never hand-edit generated files
unless they explicitly say they are human-maintained; regenerate them through
tooling. Do not use archived audits/reviews as active guidance unless the task
or a current document makes them authoritative.

## 5. Change Workflow And Dirty Worktrees

Every meaningful docs, tooling, test, schema, UI, config, or code change
requires a structured packet under `ops/release/changes/unreleased/`. Create or
identify it before editing, record touched paths as work progresses, and keep
its summary, reason, affected areas, validation evidence, rollback plan,
status, and Python-impact notes current. Use the bundled Python runtime and the
commands in
[`docs/change_control/README.md`](docs/change_control/README.md).

Before the final response, run packet validation with strict worktree coverage
when feasible. Existing dirty files belong to the user unless proven otherwise:
preserve them, do not absorb unrelated paths into the packet, avoid overlapping
edits, and report unrelated or uncovered dirty files separately. Do not commit
unless the user explicitly asks.

## 6. Validation Workflow

Select and run the smallest safe validation rung that covers every touched
behavior, using
[`docs/testing/VALIDATION_LADDER_RUNBOOK.md`](docs/testing/VALIDATION_LADDER_RUNBOOK.md).
A clean smoke proves only its stated scope. Use the bundled Python runtime;
system Python may lack required packages. Do not weaken validation, generated-
context, dependency, naming, architecture, typing, PowerShell, risky-file, or
change-packet checks without explicit reason and validation.

The repository guardrail commands and validation overview are maintained in
[`README.md`](README.md).

After source edits, refresh generated summaries:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --changed
```

Run relevant generator `--check` modes and active-document/link/reference
checks for documentation or generated-context changes.

## 7. High-Risk Areas

Treat each of these as a separate, validation-first task:

- FFmpeg command generation, stream mapping, remux/encode routing, and size
  policy.
- Subtitle ASS/TX3G/BDPGS/SRT conversion, OCR, preservation/drop policy, and
  sidecar behavior.
- Audio passthrough, transcode, downmix, default-language, and channel policy.
- Source, scratch, output, final-library, cleanup, and partial-file movement.
- Pending-publish manifests, park/drain, sidecar carry-forward,
  final-placement proof, repair, and reconcile flows.
- Queue launch scope, source discovery, priority/hold manifests, CSV rerun, and
  schedule-start behavior.
- Settings schema/defaults/persistence, LibraryProfiles, profile inheritance,
  and runtime overlay evidence.
- Rename preview/apply/undo, path-boundary checks, collision handling, and
  sidecar updates.
- Network coordinator/worker lifecycle, claim/done/release, path identity,
  provider hooks, authentication/secret handling, and recovery.
- Command journal, strict JSON route handling, duplicate-command guards,
  close-readiness, shutdown, and process lifecycle.
- Tauri backend lifecycle, bootstrap-token handling, single-instance guard,
  and native close behavior.
- Release packaging, personal-config exclusion, runtime/tool bundling, and
  package open/close validation.

Before editing one, read the exact gates in
[`docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`](docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md),
identify the required validation rung, and state whether representative
real-media validation is required.

## 8. Canonical Launchers

Run canonical launchers under `ops/scripts/` from the repository root; never
reintroduce legacy root callers. The maintained launcher and release command
catalogs are in [`README.md`](README.md) and
[`docs/README_MediaPipelineRemuxEncodeAIO.md`](docs/README_MediaPipelineRemuxEncodeAIO.md).
Python validation uses `apps/desktop/runtime/Python/python.exe` unless the task
explicitly validates a system Python installation.

## 9. Documentation Authority

Use [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) as the active documentation map.
When documents conflict, prefer durable architecture/boundary docs for
invariants, current-state docs for status, generated maps for current file
placement, and source/tests for executable truth. Update stale canonical docs
instead of adding another source of truth. Archived material is historical
unless a current document explicitly cites it as evidence.

## 10. Final Response Checklist

After edits, concisely report:

1. What changed.
2. The change packet ID.
3. Validation commands and outcomes.
4. Strict change-packet coverage status when feasible.
5. Unrelated dirty or uncovered files separately.
6. Validation not run and why.
