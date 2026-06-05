# AGENTS.md — AI Entry Point

This is the canonical entry point for AI coding agents (Claude Code, Codex,
etc.) working in this repository. It supersedes the archived
`docs/archive/ai/AI_AGENT_START_HERE.md`, `docs/archive/ai/AI_DIRECTIVE.md`,
and `AI_HANDOFF.md`.

If you are a human, you probably want `README.md` and
`docs/CURRENT_PROJECT_STATE.md`.

---

## 1. What this project is (60-second version)

MediaPipelineRemuxEncodeAIO is a Windows-first, single-operator media
pipeline for a Plex-style library. It discovers source media, copies
sources to scratch, decides remux vs encode, runs FFmpeg/ffprobe plus
helper tools, handles subtitles and audio, writes sidecars/manifests,
publishes completed outputs, parks pending publishes when final output is
unsafe, and exposes operator controls through a local Python API plus
WebView/Tauri shell.

Components:

| Path                                                 | Purpose                                           |
| ---------------------------------------------------- | ------------------------------------------------- |
| `src/mediapipeline/core/`                            | Backend domain services, policies, orchestration, storage, config, queue, rename, publish |
| `src/mediapipeline/contracts/`                       | Python contracts and generated JSON schemas       |
| `src/mediapipeline/desktop/`                         | Local API host and desktop-facing adapters        |
| `src/mediapipeline/pipeline/`                        | Python pipeline helpers, including ASS-to-SRT CLI |
| `src/mediapipeline/tools/`                           | Python developer/release/change-control tooling   |
| `ops/pipeline/entrypoints/`                          | Stable PowerShell entry scripts                   |
| `ops/pipeline/engine/`                               | Domain-organized PowerShell implementation        |
| `ops/pipeline/config/`                               | Pipeline templates, profiles, schemas, local PSD1s|
| `apps/desktop/webview/static/`                       | Vanilla-JS WebView SPA and split asset folders    |
| `apps/desktop/tauri/`                                | Tauri/WebView2 desktop shell                      |
| `apps/desktop/launchers/`                            | Desktop launcher wrappers                         |
| `ops/scripts/` and `ops/release/`                    | Dev/operator/release/smoke scripts and release packets |
| `docs/`, `docs/generated/`, `docs/generated/summaries/`            | Operator/engineering docs, generated maps, AI navigation summaries |
| `LocalBase/` (gitignored)                           | Runtime state, JSON files, SQLite mirror          |

This is the active promoted workspace for operator and AI/code-agent work.
The structural cleanup and default-launcher promotion are complete by
operator confirmation on 2026-05-30.

---

## 2. Repository structure (read before editing structure)

Current execution status lives in
`CHANGELOG.md`, `docs/CURRENT_PROJECT_STATE.md`, and
`docs/OPEN_WORK_CHECKLIST.md`. The legacy-surface removal and package/default
launcher promotion work are complete; remaining work should build on the
current domain layout.
Highlights you must respect:

- **Do not create new `facade_*.py`, `service_*.py`, or
  `command_payloads_*.py` files at the existing flat paths.** The target
  layout is `src/mediapipeline/core/<domain>/<role>.py`, with
  desktop-only adapters under `src/mediapipeline/desktop/`.
- **Do not create new loose Python modules at repository root.** Python
  implementation belongs under `src/mediapipeline/`.
- **Do not create new PowerShell files in `Pipeline/Modules/` with
  dotted suffixes.** The target is `ops/pipeline/engine/<domain>/<role>.ps1`.
- **Do not create new top-level Markdown status files**
  (`*_REPORT.md`, `*_FIXES.md`, `*_CHECKLIST.md`). PR descriptions belong
  in the commit/PR, not the repo. Doc updates go in `CHANGELOG.md` and the
  relevant `docs/`.
- **Do not invent new "single source of truth" documents.** The canonical
  set is:
  - `README.md`
  - `CHANGELOG.md`
  - `AGENTS.md` (this file)
  - `docs/CURRENT_PROJECT_STATE.md`
  - `docs/OPEN_WORK_CHECKLIST.md`

---

## 3. Hard rules (project-specific, do not violate)

These come from `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` and the
current-state doc. Internalize them.

1. **Source mutation is forbidden by default.** The pipeline copies
   sources to scratch. Never delete or overwrite a source file unless a
   specifically named, intentionally-enabled safe-delete setting is
   active.
2. **Backend owns media policy.** The WebView/Tauri shell must not
   implement filesystem mutation, settings persistence, queue mutation,
   pending-publish drain, rename apply, or media policy independently.
3. **Pending publish parks output** when the final root is unsafe; drain
   later with manifest evidence. Do not bypass the park/drain flow.
4. **FFmpeg, subtitle, audio, remux/encode, source/scratch/output,
   pending-publish, and queue behavior changes require high validation**,
   including real-media samples where practical.
5. **Subtitles**: preserve original subtitles by default; add SRT for
   preferred-language tracks when configured. OCR/conversion failure
   routes to review, never silent bad publish.
6. **Audio**: profile/config driven. Do not casually alter passthrough,
   downmix, or transcode policy.
7. **Command journal, strict JSON route handling, duplicate-command
   guards, close-readiness checks** are release-critical safety
   mechanisms.
8. **Promotion and representative real-media validation** are
   operator-confirmed complete as of 2026-05-30, but representative media
   validation must be rerun after media-policy, FFmpeg, subtitle, audio,
   publish/drain, source movement, or cleanup behavior changes.

---

## 4. AI token-conservation rules

These rules exist because this repository is large (~900 source files,
~165 markdown files) and traditional "read everything" workflows cost too
many tokens.

1. **Start each session by reading**, in order:
   - This file (`AGENTS.md`)
   - `docs/CURRENT_PROJECT_STATE.md`
   - `docs/OPEN_WORK_CHECKLIST.md`
   - `docs/generated/PROJECT_INDEX.md` (once it exists)
2. **Before opening any source file**, check `docs/generated/summaries/<path>.md` first.
   Open the full source only when the summary marks it
   `token_priority: high` *or* the change requires a function the summary
   did not list.
3. **Do not load `AI_HANDOFF.md`, `MONOLITH_SPLIT_PLAN.md`,
   `md_documentation_audit*`** unless explicitly investigating their
   history. They are 107 KB / 141 KB / 223 KB respectively and are
   historical.
4. **Prefer `Grep` and `Glob`** over `Read` when locating symbols.
5. **Maintain a context budget** of roughly 80 KB of summaries plus 50 KB
   of full sources per task. If you exceed it, the task is too big —
   split.
6. **After editing**, run
   `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries`
   (or let the pre-commit hook do it).
7. **Do not duplicate long code blocks into summaries.** Summaries name
   symbols and intent; source files contain code.

---

## 5. Validation ladder (use the smallest safe rung)

| Change                                                | Rung                                                       |
| ----------------------------------------------------- | ---------------------------------------------------------- |
| Docs only                                             | Link/file-existence checks if links changed                |
| WebView static JS/HTML/CSS                            | Targeted Python/Node smokes plus `ops/scripts/smoke/Test-WebView*`|
| Local API / contract changes                          | Targeted route tests plus `Test-LocalApi*`                 |
| Settings, queue, rename, pending publish, diagnostics | Targeted unit tests plus affected smokes                   |
| Tauri files                                           | Tauri shell checks                                         |
| Media policy / FFmpeg / subtitle / audio / publish    | Release gate plus real-media validation                    |

For broad structural, packaging, launcher, or operator-surface changes,
agents must also prove the operator surface still opens: start the local API
with `apps/desktop` as the app root, confirm it reaches the
bootstrap/listening state, and run the app-opening smoke appropriate to the
changed surface (`start-api-and-browser` or Tauri preview/check-only). If a
GUI/browser open cannot be performed in the current environment, report the
exact substitute command and evidence.

References:

- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/testing/TEST_COVERAGE_MATRIX.md`
- `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`

---

## 6. Launchers

From the repository root (Windows). Canonical paths under `ops\scripts\`:

```powershell
.\ops\scripts\dev\start-local-api.bat
.\ops\scripts\dev\start-tauri-preview.bat -CheckOnly
.\ops\scripts\dev\start-tauri-preview.bat
.\ops\scripts\dev\start-api-and-browser.bat
.\ops\scripts\dev\run.bat
.\ops\scripts\dev\setup.bat
.\ops\scripts\dev\verify-env.bat
.\ops\scripts\dev\verify-env.ps1
.\ops\scripts\release\build.ps1
.\ops\scripts\release\test.ps1
.\ops\scripts\operator\New-RealMediaValidationWorksheet.ps1
```

The legacy root launcher paths
(`.\Start-MediaPipelineRemuxEncodeAIO-*.bat`,
`.\Run-MediaPipelineRemuxEncodeAIO.bat`,
`.\Setup-MediaPipelineRemuxEncodeAIO.bat`,
`.\Verify-MediaPipelineRemuxEncodeAIO-Environment.{bat,ps1}`,
`.\Build-MediaPipelineRemuxEncodeAIO-Release.ps1`,
`.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1`,
`.\New-RealMediaValidationWorksheet.ps1`) were removed during the legacy
surface cleanup. **Do not reintroduce root launcher callers.** Use the canonical
`ops\scripts\` paths only.

Python validation uses the bundled interpreter at
`apps\desktop\runtime\Python\python.exe`. System Python may lack `pytest`
and is not the canonical portable-bundle test environment.

---

## 7. High-risk areas (do not casually change)

- Removed legacy desktop-shell and package-layout assumptions.
- FFmpeg command generation and stream mapping.
- Subtitle ASS/TX3G/BDPGS/SRT conversion paths.
- Audio passthrough/transcode/downmix policy.
- Source/scratch/output file movement and cleanup.
- Pending publish manifests, drain, sidecar carry-forward, repair logic.
- Queue launch scope, CSV rerun, schedule start behavior.
- Settings schema/defaults/persistence.
- Command journal and backend close-readiness.
- Tauri backend lifecycle ownership.

If your change touches any of these, read
`docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` first.

---

## 8. Conventions

- **Search**: use `.rgignore` for routine searches. Use `rg -u` only for
  intentional audits of runtime, vendor, generated, or archived trees.
- **Smoke wrappers**: put new smoke wrappers in `ops/scripts/smoke/`, never at
  the repo root.
- **Commits**: do not commit without an explicit user instruction. Mark
  authorship as Codex unless otherwise specified.
- **Change ledger**: every meaningful AI/code-agent change must create or
  update a structured change packet under `ops/release/changes/unreleased/` before or
  during edits. Keep `files_touched`, affected areas, summary/reason,
  validation evidence, rollback plan, status, and affected Python-script
   details current as work progresses. Use
   `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.record_change_touch`
   with the change ID plus explicit paths, or `--from-staged` for packet updates. Run
   `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage` before the final response
  when feasible. The final response must report the change packet ID and the
  strict coverage result, including any unrelated uncovered dirty files that
  were not absorbed into the packet.
- **Dates in saved notes**: convert relative dates to absolute
  (`2026-05-28` not "today").
- **No emojis** in source, docs, or commit messages unless explicitly
  requested.

---

## 9. Obsolete or non-authoritative material

Do not treat the following as active guidance:

- Old Claude or Codex handoff files (`AI_HANDOFF.md`,
  `docs/archive/ai/AI_DIRECTIVE.md`,
  `docs/archive/ai/AI_AGENT_START_HERE.md`) — superseded by this file.
- `MONOLITH_SPLIT_PLAN.md` — the split campaign is complete; archived.
- `md_documentation_audit*` — one-shot audit.
- `*_REPORT.md`, `*_FIXES.md` at the repo root — PR descriptions, not
  docs.
- Completed UI/control/checklist archives in `docs/archive/` — historical
  only.
- older historical docs — context only.
- `node_modules` Markdown — vendor material.
- Historical text that says Tauri/WebView2 is pre-promotion or not yet the
  default launcher is superseded by the 2026-05-30 operator-confirmed
  promotion. Representative real-media validation still becomes stale after
  future media behavior changes.

---

## 10. Where to look next

- Current state: `docs/CURRENT_PROJECT_STATE.md`
- Backlog: `docs/OPEN_WORK_CHECKLIST.md`
- ADRs: `docs/adr/` (once seeded)
- Boundaries: `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Architecture: `docs/architecture/`
- Generated maps: `docs/generated/`
- Smoke catalogs: `docs/testing/`
- File summaries: `docs/generated/summaries/` (once generated by
  `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries`)

