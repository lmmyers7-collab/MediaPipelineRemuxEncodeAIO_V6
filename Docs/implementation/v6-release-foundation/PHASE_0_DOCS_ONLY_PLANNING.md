# Phase 0 - Docs-Only Planning

## Goal

Create the release-foundation planning docs and index links without changing
code, package behavior, media policy, runtime paths, or launcher behavior.

## Scope

- Add or update docs under `Docs/implementation/v6-release-foundation/`.
- Update `Docs/DOCS_INDEX.md` so agents can find the planning pack.
- Keep this planning pack subordinate to existing authority docs.

## Out Of Scope

- No Python, PowerShell, JavaScript, Rust, schema, package-script, or Tauri
  config behavior changes.
- No real-media processing.
- No release candidate build.
- No installer or portable-bundle generation.

## Steps

1. Read `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
   `OPEN_WORK_CHECKLIST.md`, and `Docs/generated/PROJECT_INDEX.md`.
2. Create a change packet under `changes/unreleased/`.
3. Add or update this planning folder.
4. Update `Docs/DOCS_INDEX.md`.
5. Run docs-only validation.
6. Refresh summaries for touched files.
7. Run change-packet validation and strict coverage.

## Validation

Minimum:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

Also run when feasible:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py --require-worktree-coverage
```

If strict coverage fails because unrelated files were already dirty, do not
absorb unrelated paths into this packet. Report the failure and list the
unrelated uncovered count or representative paths.

