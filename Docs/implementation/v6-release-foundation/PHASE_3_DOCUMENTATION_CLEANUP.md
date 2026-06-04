# Phase 3 - Documentation Cleanup

## Goal

Reduce agent confusion before `V6.0.0` without creating another source of
truth.

## Required Outcomes

- Broad proposal docs are clearly labeled as non-authoritative.
- Active sample-validation docs do not imply V5 is the current app identity.
- Historical material stays under `Docs/archive/`.
- `Docs/DOCS_INDEX.md` remains the navigation map.
- Current status remains in `Docs/CURRENT_PROJECT_STATE.md` and
  `OPEN_WORK_CHECKLIST.md`.

## Priority Cleanup Targets

- Active sample-validation files whose filenames or first paragraphs still say
  `V5` while describing current V6 validation.
- Broad proposal folders such as `Docs/rewrite/` when they are future-facing
  rather than current implementation instructions.
- Redirect stubs that point agents at obsolete active paths.

## Rules

- Prefer narrow redirect stubs over deleting useful history.
- Move completed or historical bodies under dated `Docs/archive/` folders.
- Do not create new root-level reports, checklists, or handoff files.
- Do not edit archived docs as if they were active guidance.

## Steps

1. Use `Docs/DOCS_INDEX.md` and `Docs/ARCHIVED_MD_INDEX.md` to classify docs.
2. Rename or replace V5-named active validation docs only if references are
   updated in the same phase.
3. Add short non-authoritative banners to future-facing proposal docs that must
   remain active.
4. Run active-doc reference checks.
5. Update summaries.

## Validation

Minimum:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

If files are moved, also run a focused `rg` check for stale paths and V5/V6
ambiguity in active docs.

