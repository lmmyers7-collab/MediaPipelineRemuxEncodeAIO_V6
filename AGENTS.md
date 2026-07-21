# AGENTS.md - AI Entry Point

This is the canonical entry point for AI/code agents working in this
repository. It is a stable project operating contract, not a status log. Use
it to understand the project shape, safety boundaries, placement rules,
navigation workflow, and validation expectations.

For current status, shipped changes, or active backlog, delegate to:

- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `CHANGELOG.md`
- `docs/DOCS_INDEX.md`

Old Claude/Codex handoff files (`AI_AGENT_START_HERE.md`,
`AI_DIRECTIVE.md`, `AI_HANDOFF.md`) are historical only and are not active
guidance unless a current doc explicitly reopens them.

---

## 1. Project Model

MediaPipelineRemuxEncodeAIO is a Windows-first, single-operator media
pipeline for a Plex-style library. It discovers source media, copies sources
to scratch, decides remux versus encode, runs FFmpeg/ffprobe plus helper
tools, handles subtitles and audio, writes sidecars/manifests, publishes
completed outputs, parks unsafe final-output moves for later drain, and
exposes operator controls through a local Python API plus WebView/Tauri shell.

The active architecture is layered:

```text
Tauri/WebView2 shell
  -> backend-served WebView SPA
  -> Python Local API
  -> Python core domain services and contracts
  -> PowerShell media engine
  -> FFmpeg/ffprobe/MKVToolNix/PgsToSrt and filesystem state
```

Ownership rule: the frontend displays state, stages operator intent, and calls
backend routes. Backend services and the PowerShell engine own media policy,
state mutation, filesystem mutation, process lifecycle, and evidence.

Primary project areas:

| Path | Purpose |
| --- | --- |
| `src/mediapipeline/core/` | Backend domain services, policies, orchestration, storage, config, queue, rename, publish, telemetry, status |
| `src/mediapipeline/contracts/` | Python contracts and generated JSON schemas |
| `src/mediapipeline/desktop/` | Local API host and desktop-facing adapters |
| `src/mediapipeline/pipeline/` | Python pipeline helpers, including ASS-to-SRT CLI |
| `src/mediapipeline/tools/` | Developer, release, generated-context, and change-control tooling |
| `apps/desktop/webview/static/` | Backend-served vanilla-JS WebView SPA |
| `apps/desktop/tauri/` | Tauri/WebView2 shell |
| `apps/desktop/launchers/` | Desktop launcher wrappers |
| `ops/pipeline/entrypoints/` | Stable PowerShell entry scripts |
| `ops/pipeline/engine/` | Domain-organized PowerShell implementation |
| `ops/pipeline/config/` | Templates, profiles, schemas, and ignored local PSD1s |
| `ops/scripts/` | Development, operator, release, and smoke wrappers |
| `ops/release/` | Structured change packets and release metadata |
| `tests/` | Python/backend, WebView, tooling, and integration tests |
| `docs/` | Operator docs, architecture docs, inventories, testing docs, current state, generated maps |
| `LocalBase/` | Gitignored runtime state, JSON files, manifests, SQLite mirror |

---

## 2. Non-Negotiable Invariants

These rules protect source media, operator trust, and release safety.

1. **Source mutation is forbidden by default.** Source media may be read,
   probed, or copied to scratch. Do not delete, overwrite, rename, or transcode
   source media unless an explicitly named safe-delete policy is intentionally
   enabled and validated.
2. **Backend owns mutation and media policy.** WebView/Tauri must not implement
   filesystem mutation, settings persistence, queue mutation, pending-publish
   drain, rename apply, repair/reconcile apply, network lifecycle policy, or
   FFmpeg/media policy independently.
3. **Scratch isolation is part of the safety model.** Pipeline processing uses
   scratch copies so failed or interrupted work cannot corrupt sources.
4. **Pending publish is manifest-backed.** Unsafe final output is parked and
   drained later with evidence. Do not bypass park/drain flows or infer drain
   safety in the frontend.
5. **Original subtitles are preserved by default.** Preferred-language SRT
   generation may be added when configured. OCR/conversion failure routes to
   review, never silent bad publish.
6. **Audio is profile/config driven.** Do not casually alter passthrough,
   downmix, default-language, or transcode policy.
7. **Strict JSON confirmations matter.** Routes that require fields such as
   `confirm_save`, `confirm_apply`, `confirm_promote`, or lifecycle
   confirmations must reject missing or non-boolean confirmation values.
8. **Command journal, duplicate-command guards, and close-readiness are
   release-critical.** They protect operators from hidden failures, duplicate
   pipeline starts, and unsafe shutdown during active work.
9. **Generated mirrors are not automatically authoritative.** JSON state files,
   manifests, sidecars, SQLite mirrors, generated summaries, and WebView
   evidence must keep authority boundaries explicit.

### Right-Sized Safety Protocol

The safety rules above protect source media and irreversible operations. They
must not be expanded into redundant warnings, confirmations, review queues, or
manual checklists unless the added control reduces a specific, named risk.

When proposing or implementing a safety control:

- Start from the existing invariant or backend boundary that already covers the
  risk. Reuse it before adding a new surface.
- Use the least cumbersome control that prevents the concrete hazard. Prefer
  backend validation, clear disabled states, and actionable error messages over
  extra operator prompts.
- Do not stack frontend warnings or confirmations on top of backend strict
  confirmations, dry-runs, or manifest-backed flows unless there is a
  demonstrated gap.
- Treat read-only, preview-only, and already reversible operations as normal
  operator workflows. Do not add mutation-level ceremony to them.
- If a new block, confirmation, quarantine, or review step is still needed,
  document the hazard, the existing control that was insufficient, and the
  condition that lets the operator proceed.
- Remove or simplify obsolete safety layers when a stronger lower-level control
  makes them redundant.

Safety is successful when it prevents corruption or hidden loss while keeping
routine operation fast and predictable.

Before touching any high-risk area, read
`docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`.

---

## 3. Placement Rules

Use the existing domain layout. Do not create new compatibility surfaces or
loose files because they increase discovery cost and weaken guardrails.

- Do not create loose Python implementation modules at repository root.
  Python implementation belongs under `src/mediapipeline/`.
- Do not create new `facade_*.py`, `service_*.py`, or
  `command_payloads_*.py` files at old flat paths. Use
  `src/mediapipeline/core/<domain>/<role>.py` or
  `src/mediapipeline/desktop/` adapters.
- Do not create new PowerShell files in `Pipeline/Modules/` or new dotted
  module-shim paths. Active PowerShell implementation belongs under
  `ops/pipeline/engine/<domain>/<role>.ps1`.
- Do not reintroduce removed root launcher callers. Use canonical launcher
  wrappers under `ops/scripts/`.
- Do not create new top-level Markdown status/report/checklist files such as
  `*_REPORT.md`, `*_FIXES.md`, or `*_CHECKLIST.md`. Put project status in the
  canonical docs or the release/change record.
- Do not invent a new single source of truth. The stable active set is
  `README.md`, `AGENTS.md`, `CHANGELOG.md`, `docs/CURRENT_PROJECT_STATE.md`,
  `docs/OPEN_WORK_CHECKLIST.md`, and `docs/DOCS_INDEX.md`.
- Put new smoke wrappers in `ops/scripts/smoke/`, never at repository root.
- When adding routes, DOM IDs, command surfaces, config keys, state files, or
  public WebView exports, update the matching inventory or generated contract
  in the same change.

For feature placement, use `docs/architecture/MODULE_MAP.md`. For architecture
orientation, use `docs/architecture/ARCHITECTURE.md`.

---

## 4. AI Navigation Workflow

This repository is large. After reading this file, use the read-only
`mediapipeline-code` MCP server when available:

1. Call `repo_context` with the actual task and its default 2,000-token budget.
2. Use `code_lookup` for ownership, relationships, tests, and validation.
3. Use bounded `code_read` calls only for returned paths that need exact detail.
4. Use `code_search` only for a precise symbol/string or a low-confidence
   context result.

If the MCP server is unavailable, run the deterministic CLI fallback:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.context_slice --task "<task>" --budget 2000
```

Open only the summaries, boundary docs, source, and tests returned by that
workflow. Read `docs/CURRENT_PROJECT_STATE.md` only when current status matters
and `docs/OPEN_WORK_CHECKLIST.md` only when backlog state matters. The full
Markdown/JSONL indexes and broad orientation documents are query aids, not
ordinary startup reads.

Generated navigation remains available for focused follow-up:

- `docs/generated/PROJECT_INDEX.md` for per-file domain/priority lookup.
- `docs/generated/PIPELINE_MAP.md` for stage contracts.
- `docs/generated/FEATURE_FILE_MAP.md` for feature-to-file placement.
- `docs/generated/DEPENDENCY_GRAPH.md` for cross-domain dependencies.
- `docs/generated/summaries/<path>.md` before opening source.

Rules:

- Prefer `rg` and `rg --files` for discovery.
- Before opening a source file, read its generated summary when available.
- Open full source when the summary marks `token_priority: high`, when the
  requested change needs details the summary does not expose, or when exact
  behavior/evidence is required.
- Do not hand-edit files under `docs/generated/` unless the file explicitly says
  it is human-maintained. Regenerate generated artifacts through tooling.
- Avoid historical or archived docs unless a current doc points there for
  evidence or the task explicitly asks for history.
- Treat `docs/ai-audits/` and `docs/reviews/` as evidence snapshots, not active
  instructions, unless current docs or the user make one authoritative.

---

## 5. Change Workflow

Every meaningful AI/code-agent change needs a structured change packet under
`ops/release/changes/unreleased/`. This includes meaningful docs, tooling,
tests, schemas, UI, config, and code changes.

Use the bundled Python runtime unless the task explicitly validates a system
Python install:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.new_change --title "Short title" --type docs --risk low --version-target 2026.06.04.001
```

During the change:

1. Create or identify the packet.
2. Record touched paths as work progresses:

   ```powershell
   .\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.record_change_touch MP-CHANGE-YYYY-MMDD-### path/to/file --area docs --note "Why this file changed."
   ```

3. Keep `files_touched`, affected areas, summary/reason, validation evidence,
   rollback plan, status, and Python-impact notes current.
4. Before final response when feasible, run:

   ```powershell
   .\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
   ```

When the worktree already contains unrelated dirty files, do not absorb them
into your packet. Report any uncovered unrelated dirty files separately.

Do not commit unless the user explicitly asks.

---

## 6. Validation Workflow

Use the smallest safe rung that matches the touched behavior. Do not treat a
clean smoke as proof for behavior outside its scope.

Primary reference:

- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`

Quick guide:

| Change | Minimum validation |
| --- | --- |
| Docs only | Link/path checks if links changed, plus change-packet validation |
| Generated context only | Relevant generator `--check` and summary integrity checks |
| WebView JS/HTML/CSS | Targeted static/non-browser checks plus affected WebView smokes |
| Local API read routes/contracts | Targeted route tests plus `Test-LocalApi*` smoke when affected |
| Local API command/mutation routes | Targeted route tests, command journal/strict JSON tests, affected smokes |
| Settings, queue, rename, pending publish, diagnostics, maintenance | Targeted unit tests plus affected WebView/API smokes |
| Tauri shell | Tauri `-CheckOnly`, shell checks, and affected WebView rendering checks |
| PowerShell media engine | Pipeline unit/reliability checks and tool integration where relevant |
| Release/packaging | Release self-test and package/open/close validation when the operator surface changes |
| FFmpeg/media policy/subtitle/audio/publish/source movement | Release gate plus representative real-media validation |

AI guardrail tooling can plan or run repository safety checks:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.ai_guardrail preflight --no-run
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.ai_guardrail postflight
```

After source edits, refresh generated summaries:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --changed
```

The pre-commit configuration also checks generated context, dependency
boundaries, naming, active doc references, architecture guardrails, risky files,
typing, PowerShell analysis, and change-packet staged coverage. Do not weaken
these checks without explicit reason and validation.

---

## 7. High-Risk Areas

Treat these as separate, validation-first tasks:

- FFmpeg command generation, stream mapping, remux/encode routing, and size
  policy.
- Subtitle ASS/TX3G/BDPGS/SRT conversion, OCR, preservation/drop policy, and
  sidecar behavior.
- Audio passthrough, transcode, downmix, default-language, and channel policy.
- Source, scratch, output, final-library, cleanup, and partial-file movement.
- Pending publish manifests, park/drain, sidecar carry-forward, final-placement
  proof, repair, and reconcile flows.
- Queue launch scope, source discovery, priority/hold manifests, CSV rerun, and
  schedule start behavior.
- Settings schema/defaults/persistence, LibraryProfiles, profile inheritance,
  and runtime overlay evidence.
- Rename preview/apply/undo, path-boundary checks, collision handling, and
  sidecar updates.
- Network coordinator/worker lifecycle, claim/done/release, path identity,
  provider hooks, auth/secret handling, and recovery.
- Command journal, strict JSON route handling, duplicate-command guards,
  close-readiness, shutdown, and process lifecycle.
- Tauri backend lifecycle, bootstrap token handling, single-instance guard, and
  native close behavior.
- Release packaging, personal-config exclusion, runtime/tool bundling, and
  package open/close validation.

If a change touches one of these, read the boundary register, identify the
validation rung before editing, and report whether real-media validation is
required.

---

## 8. Launchers

Use canonical launchers under `ops/scripts/` from the repository root:

```powershell
.\ops\scripts\dev\start-local-api.bat
.\ops\scripts\dev\start-api-and-browser.bat
.\ops\scripts\dev\start-tauri-preview.bat -CheckOnly
.\ops\scripts\dev\start-tauri-preview.bat
.\ops\scripts\dev\run.bat
.\ops\scripts\dev\setup.bat
.\ops\scripts\dev\verify-env.bat
.\ops\scripts\dev\verify-env.ps1
.\ops\scripts\release\build.ps1
.\ops\scripts\release\test.ps1
.\ops\scripts\operator\New-RealMediaValidationWorksheet.ps1
```

Do not reintroduce legacy root launcher callers. Python validation should use
`apps/desktop/runtime/Python/python.exe`; system Python may not have the
project's expected packages.

---

## 9. Documentation Authority

Use each documentation surface for its intended job:

- `README.md`: human/operator entry point.
- `AGENTS.md`: stable AI/code-agent operating contract.
- `docs/DOCS_INDEX.md`: active documentation map.
- `docs/CURRENT_PROJECT_STATE.md`: volatile current project state.
- `docs/OPEN_WORK_CHECKLIST.md`: active backlog and gate status.
- `CHANGELOG.md`: shipped-status log.
- `docs/architecture/ARCHITECTURE.md`: concise architecture map.
- `docs/architecture/MODULE_MAP.md`: feature placement and ownership map.
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`: high-risk boundary rules.
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`: validation selection.
- `docs/change_control/README.md`: change-packet workflow.
- `docs/inventories/`: route, command, state, artifact, test, WebView, and
  package inventories.
- `docs/generated/`: generated maps and summaries.
- `docs/archive/`: historical material only.

When docs conflict, prefer durable architecture/boundary docs for invariants,
current-state docs for status, generated maps for current file placement, and
source/tests for executable truth. Update stale docs rather than adding another
source of truth.

---

## 10. Final Response Checklist

Before final response after edits:

1. Summarize what changed.
2. Report the change packet ID.
3. Report validation commands and outcomes.
4. Report strict change-packet coverage status when feasible.
5. Call out unrelated dirty/uncovered files separately.
6. Note any validation that was not run and why.

Keep the final response concise and specific.
