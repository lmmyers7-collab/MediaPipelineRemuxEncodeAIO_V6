# Phase 3 - Documentation Cleanup

## Goal

Reduce agent confusion before `2026.06.04.001` without creating another source of
truth.

## Required Outcomes

- Broad proposal docs are clearly labeled as non-authoritative.
- Active sample-validation docs do not imply the external rollback workspace is the current app identity.
- Historical material stays under `docs/archive/`.
- `docs/DOCS_INDEX.md` remains the navigation map.
- Current status remains in `docs/CURRENT_PROJECT_STATE.md` and
  `docs/OPEN_WORK_CHECKLIST.md`.

## Priority Cleanup Targets

- Active sample-validation files whose filenames or first paragraphs still use
  external rollback wording while describing current validation.
- Broad proposal folders such as `docs/rewrite/` when they are future-facing
  rather than current implementation instructions.
- Redirect stubs that point agents at obsolete active paths.

## Rules

- Prefer narrow redirect stubs over deleting useful history.
- Move completed or historical bodies under dated `docs/archive/` folders.
- Do not create new root-level reports, checklists, or handoff files.
- Do not edit archived docs as if they were active guidance.

## Prerequisites

- Read the required context docs listed in `AGENTS.md`.
- Confirm each target doc is active, historical, or archive-only before editing.
- Stop if cleanup would require inventing a new status, checklist, handoff, or
  source-of-truth document instead of updating the canonical set.

## Steps

1. Use `docs/DOCS_INDEX.md` and `docs/ARCHIVED_MD_INDEX.md` to classify docs.
2. Rename or replace external-rollback-named active validation docs only if references are
   updated in the same phase.
3. Add short non-authoritative banners to future-facing proposal docs that must
   remain active.
4. Run active-doc reference checks.
5. Update summaries.

## Change Ledger And Rollback

- Create or update one change packet for this phase before edits.
- Record moved docs, redirect stubs, and reference updates.
- Roll back by restoring this phase's doc moves/banners/references only; do not
  revive archived guidance as active instructions.

## Validation

Minimum:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\check_active_doc_references.py
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py --require-worktree-coverage
```

If files are moved, also run a focused `rg` check for stale release-label
ambiguity in active docs.


