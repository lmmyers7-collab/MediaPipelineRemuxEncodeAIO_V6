# AGENTS.md — AI Entry Point

This is the canonical entry point for AI coding agents (Claude Code, Codex,
etc.) working in this repository. It supersedes the archived
`Docs/archive/ai/AI_AGENT_START_HERE.md`, `Docs/archive/ai/AI_DIRECTIVE.md`,
and `AI_HANDOFF.md`.

If you are a human, you probably want `README.md` and
`Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md`.

---

## 1. What this project is (60-second version)

MediaPipelineRemuxEncodeAIO V6 is a Windows-first, single-operator media
pipeline for a Plex-style library. It discovers source media, copies
sources to scratch, decides remux vs encode, runs FFmpeg/ffprobe plus
helper tools, handles subtitles and audio, writes sidecars/manifests,
publishes completed outputs, parks pending publishes when final output is
unsafe, and exposes operator controls through a local Python API plus
WebView/Tauri shell.

Components:

| Path                                                 | Purpose                                           |
| ---------------------------------------------------- | ------------------------------------------------- |
| `app/`                                              | Domain-organized Python contracts, services, facades, orchestration, storage, validation |
| `engine/`                                           | Domain-organized PowerShell implementation for media policy, FFmpeg, queue, probe, audit |
| `Pipeline/`                                         | Root engine entry scripts, config/profiles, schemas, bundled tools, helper scripts, tests |
| `DesktopApp/mediapipeline_desktop_app/` (Python)    | Local API host, compatibility package, backend-served WebView integration |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/`| Vanilla-JS WebView SPA and split asset folders    |
| `DesktopApp/tauri_shell/`                           | Tauri/WebView2 desktop shell                      |
| `Docs/`, `Docs/generated/`, `summaries/`            | Operator/engineering docs, generated maps, AI navigation summaries |
| `LocalBase/` (gitignored)                           | Runtime state, JSON files, SQLite mirror          |

V5 remains the external fallback/rollback workspace. V6 is where active
work happens.

---

## 2. The overhaul context (read before editing structure)

This repository is mid-overhaul. The plan is in
`Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md`; execution status lives in
`CHANGELOG.md`, `Docs/CURRENT_PROJECT_STATE.md`, and
`OPEN_WORK_CHECKLIST.md`. Phase 6 local legacy-surface removal is complete as
of 2026-05-29, but PG-3 clean-machine package-mode validation is still open.
Highlights you must respect:

- **Do not create new `facade_*.py`, `service_*.py`, or
  `command_payloads_*.py` files at the existing flat paths.** The target
  layout is `app/<domain>/<role>.py`. Add new code under `app/` when
  possible, not under `DesktopApp/mediapipeline_desktop_app/`.
- **Do not create new PowerShell files in `Pipeline/Modules/` with
  dotted suffixes.** The target is `engine/<domain>/<role>.ps1`.
- **Do not create new top-level Markdown status files**
  (`*_REPORT.md`, `*_FIXES.md`, `*_CHECKLIST.md`). PR descriptions belong
  in the commit/PR, not the repo. Doc updates go in `CHANGELOG.md` and the
  relevant `Docs/`.
- **Do not invent new "single source of truth" documents.** The canonical
  set is:
  - `README.md`
  - `CHANGELOG.md`
  - `AGENTS.md` (this file)
  - `Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md` (plan of record until V7 ships)
  - `Docs/CURRENT_PROJECT_STATE.md` (interim until consolidated)
  - `OPEN_WORK_CHECKLIST.md` (interim until moved to issues)

---

## 3. Hard rules (project-specific, do not violate)

These come from `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` and the
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
8. **V5 fallback** must remain available externally until V6 package-mode
   launch and operator workflows are proven. Representative real-media
   validation is operator-attested complete as of 2026-05-28, but must be
   rerun after media-policy, FFmpeg, subtitle, audio, publish/drain, source
   movement, or cleanup behavior changes.

---

## 4. AI token-conservation rules

These rules exist because this repository is large (~900 source files,
~165 markdown files) and traditional "read everything" workflows cost too
many tokens.

1. **Start each session by reading**, in order:
   - This file (`AGENTS.md`)
   - `Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md`
   - `Docs/CURRENT_PROJECT_STATE.md`
   - `OPEN_WORK_CHECKLIST.md`
   - `Docs/generated/PROJECT_INDEX.md` (once it exists)
2. **Before opening any source file**, check `summaries/<path>.md` first.
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
6. **After editing**, run `python scripts/dev/refresh_summaries.py`
   (or let the pre-commit hook do it).
7. **Do not duplicate long code blocks into summaries.** Summaries name
   symbols and intent; source files contain code.

---

## 5. Validation ladder (use the smallest safe rung)

| Change                                                | Rung                                                       |
| ----------------------------------------------------- | ---------------------------------------------------------- |
| Docs only                                             | Link/file-existence checks if links changed                |
| WebView static JS/HTML/CSS                            | Targeted Python/Node smokes plus `SmokeTests/Test-WebView*`|
| Local API / contract changes                          | Targeted route tests plus `Test-LocalApi*`                 |
| Settings, queue, rename, pending publish, diagnostics | Targeted unit tests plus affected smokes                   |
| Tauri files                                           | Tauri shell checks                                         |
| Media policy / FFmpeg / subtitle / audio / publish    | Release gate plus real-media validation                    |

At the end of every overhaul phase, agents must also prove the operator
surface still opens: start the local API from the `DesktopApp` working
directory, confirm it reaches the bootstrap/listening state, and run the
app-opening smoke appropriate to the changed surface (`start-api-and-browser`
or Tauri preview/check-only). If a GUI/browser open cannot be performed in
the current environment, report the exact substitute command and evidence.

References:

- `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `Docs/testing/TEST_COVERAGE_MATRIX.md`
- `Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- `Docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`

---

## 6. Launchers

From the V6 repository root (Windows). Canonical paths under `scripts\`:

```powershell
.\scripts\dev\start-local-api.bat
.\scripts\dev\start-tauri-preview.bat -CheckOnly
.\scripts\dev\start-tauri-preview.bat
.\scripts\dev\start-api-and-browser.bat
.\scripts\dev\run.bat
.\scripts\dev\setup.bat
.\scripts\verify-env.bat
.\scripts\verify-env.ps1
.\scripts\release\build.ps1
.\scripts\release\test.ps1
.\scripts\operator\New-RealMediaValidationWorksheet.ps1
```

The legacy root launcher paths
(`.\Start-MediaPipelineRemuxEncodeAIO-*.bat`,
`.\Run-MediaPipelineRemuxEncodeAIO.bat`,
`.\Setup-MediaPipelineRemuxEncodeAIO.bat`,
`.\Verify-MediaPipelineRemuxEncodeAIO-Environment.{bat,ps1}`,
`.\Build-MediaPipelineRemuxEncodeAIO-Release.ps1`,
`.\Test-MediaPipelineRemuxEncodeAIO-Release.ps1`,
`.\New-RealMediaValidationWorksheet.ps1`) were removed during the local Phase 6
burn-down. **Do not reintroduce root launcher callers.** Use the canonical
`scripts\` paths only.

Python validation uses the bundled interpreter at
`DesktopApp\Runtime\Python\python.exe`. System Python may lack `pytest`
and is not the canonical portable-bundle test environment.

---

## 7. High-risk areas (do not casually change)

- External rollback workspace and removed legacy desktop-shell
  assumptions.
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
`Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` first.

---

## 8. Conventions

- **Search**: use `.rgignore` for routine searches. Use `rg -u` only for
  intentional audits of runtime, vendor, generated, or archived trees.
- **Smoke wrappers**: put new smoke wrappers in `SmokeTests/`, never at
  the repo root.
- **Commits**: do not commit without an explicit user instruction. Mark
  authorship as Codex unless otherwise specified.
- **Dates in saved notes**: convert relative dates to absolute
  (`2026-05-28` not "today").
- **No emojis** in source, docs, or commit messages unless explicitly
  requested.

---

## 9. Obsolete or non-authoritative material

Do not treat the following as active guidance:

- Old Claude or Codex handoff files (`AI_HANDOFF.md`,
  `Docs/archive/ai/AI_DIRECTIVE.md`,
  `Docs/archive/ai/AI_AGENT_START_HERE.md`) — superseded by this file.
- `MONOLITH_SPLIT_PLAN.md` — the split campaign is complete; archived.
- `md_documentation_audit*` — one-shot audit.
- `*_REPORT.md`, `*_FIXES.md` at the repo root — PR descriptions, not
  docs.
- Completed UI/control/checklist archives in `Docs/archive/` — historical
  only.
- V3/V4 historical docs — context only.
- `node_modules` Markdown — vendor material.
- "Tauri/WebView2 preview is the production replacement" — not yet true;
  PG-3 clean-machine validation is still required. Representative real-media
  validation is operator-attested complete as of 2026-05-28, but becomes stale
  after future media behavior changes.

---

## 10. Where to look next

- Engineering plan: `Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md`
- Current state: `Docs/CURRENT_PROJECT_STATE.md`
- Backlog: `OPEN_WORK_CHECKLIST.md`
- ADRs: `docs/adr/` (once seeded)
- Boundaries: `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Architecture: `Docs/architecture/`
- Generated maps: `Docs/generated/`
- Smoke catalogs: `Docs/testing/`
- File summaries: `summaries/` (once generated by
  `scripts/dev/refresh_summaries.py`)
