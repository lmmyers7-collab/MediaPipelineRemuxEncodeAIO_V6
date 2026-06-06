# Phase 2 - File Layout Cleanup

## Goal

Make release-related file placement predictable without moving media behavior
or reviving removed legacy surfaces.

## Placement Rules

| Work Type | Location |
|---|---|
| Python app/domain code | `app/<domain>/` |
| Local API host and WebView backend integration | `src/mediapipeline/desktop/` |
| PowerShell implementation | `ops/pipeline/engine/<domain>/` |
| Stable backend entry scripts/config/templates/tools | `Pipeline/` |
| Release/package scripts | `ops/scripts/ops/release/metadata/` |
| Developer/agent helper scripts | `ops/scripts/dev/` |
| Operator helper scripts | `ops/scripts/operator/` |
| Tauri shell source and shell checks | `apps/desktop/tauri/` |
| Smoke wrappers | `ops/scripts/smoke/` |
| Active docs | existing `docs/<topic>/` folders |
| Release metadata | `ops/ops/release/metadata/changes/` and `ops/release/metadata/` |
| Large release artifacts | outside the repo, for example `C:\MediaPipelineReleases\2026.06.04.001\` |

## Document Placement Helper

Use the developer helper before adding or moving active docs:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\suggest_doc_location.py --title "Unsigned manual update runbook" --kind operator
```

The script should recommend an existing `docs/` topic folder when confidence is
high. It should print a warning and require human choice when the title/content
is ambiguous, looks like a new top-level status/checklist/report, or appears to
  belong in archive/history rather than active docs.

## Prerequisites

- Read the required context docs listed in `AGENTS.md`.
- Confirm the document placement helper exists and can run.
- Inventory proposed files before creating or moving them.
- Stop if a proposed file would create a new single-source-of-truth document,
  a top-level status/checklist/report, a root launcher, a flat Python legacy
  module, or a `Pipeline/Modules` implementation file.

## Out Of Scope

- No root launcher shims.
- No new `Pipeline/Modules` implementation files.
- No movement of authoritative JSON state, pending-publish manifests, completed
  manifests, source media, output media, scratch files, or sidecars.
- No package behavior change until Phase 4.

## Steps

1. Inventory proposed new docs/scripts before adding them.
2. Run the document placement helper for any new Markdown file.
3. Put large built artifacts outside the repo.
4. Keep release output folders named with `2026.06.04.001`.
5. Update inventories only when actual layout rules change.

## Change Ledger And Rollback

- Create or update one change packet for this phase before edits.
- Record added, moved, and deleted paths explicitly.
- Roll back by restoring only this phase's doc/script layout changes and
  reference updates. Do not move runtime state, media, manifests, sidecars, or
  unrelated dirty files.

## Validation

Minimum:

```powershell
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.dev.suggest_doc_location --title "Release foundation phase plan" --kind implementation
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.dev.check_active_doc_references
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.dev.check_architecture_guardrails
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.lint_naming
.\apps\desktop\runtime\Python\python.exe -m mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

If this phase changes only docs and helper tooling, do not run real-media
validation.

