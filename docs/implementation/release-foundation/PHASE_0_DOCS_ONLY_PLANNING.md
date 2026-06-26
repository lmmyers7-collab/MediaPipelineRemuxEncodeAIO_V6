# Phase 0 - Docs-Only Planning

## Goal

Create the release-foundation planning docs and index links without changing
code, package behavior, media policy, runtime paths, or launcher behavior.

## Scope

- Add or update docs under `docs/implementation/release-foundation/`.
- Update `docs/DOCS_INDEX.md` so agents can find the planning pack.
- Keep this planning pack subordinate to existing authority docs.

## Prerequisites

- Read the required context docs listed in `AGENTS.md`.
- Confirm this is a docs-only planning change.
- Stop if the requested work requires code, package behavior, launcher,
  runtime-path, or media-policy changes.

## Out Of Scope

- No Python, PowerShell, JavaScript, Rust, schema, package-script, or Tauri
  config behavior changes.
- No real-media processing.
- No release candidate build.
- No installer or portable-bundle generation.

## Steps

1. Read `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`,
   `docs/OPEN_WORK_CHECKLIST.md`, and `docs/generated/PROJECT_INDEX.md`.
2. Create a change packet under `ops/ops/release/metadata/changes/unreleased/`.
3. Add or update this planning folder.
4. Update `docs/DOCS_INDEX.md`.
5. Run docs-only validation.
6. Refresh summaries for touched files.
7. Run change-packet validation and strict coverage.

## Change Ledger And Rollback

- Record this phase in one change packet under `ops/ops/release/metadata/changes/unreleased/`.
- Keep `files_touched`, validation evidence, and rollback notes current.
- Roll back by reverting only the planning-folder and index edits from this
  phase; do not touch unrelated dirty files.

## Validation

Minimum:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

Also run when feasible:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\check_active_doc_references.py
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py --require-worktree-coverage
```

If strict coverage fails because unrelated files were already dirty, do not
absorb unrelated paths into this packet. Report the failure and list the
unrelated uncovered count or representative paths.
