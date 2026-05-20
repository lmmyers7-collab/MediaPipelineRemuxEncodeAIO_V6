# Documentation Housekeeping Checklist

Date: 2026-05-20

Use this checklist before adding, moving, or reviving Markdown documentation in this V6 folder.

## Canonical-First Rule

- Update an existing canonical document when the change is setup, operation, architecture, troubleshooting, validation, or AI-agent context.
- Create a new Markdown file only when the content has a durable owner, a clear audience, and will still be useful after the current task is closed.
- Do not create a new root-level Markdown file unless it is a cross-repo entry point, current audit, active checklist, or explicit operator request.
- Put topic docs under `Docs/architecture`, `Docs/operator`, `Docs/testing`, `Docs/inventories`, `Docs/sample-validation`, or `Docs/ui`.

## Temporary Notes

- Name temporary AI-agent notes with `YYYY-MM-DD_<short-topic>_AI_NOTE.md`.
- Store temporary notes under `Docs/archive/docs-housekeeping/<date>/` or a task-specific archive folder unless the operator asks for a root handoff.
- Do not leave completed plans, TLDRs, migration notes, or handoff notes scattered at the repo root.
- Convert useful final decisions into `Docs/CURRENT_PROJECT_STATE.md`, `Docs/architecture/DECISIONS_AND_HISTORY.md`, or the relevant operator/testing doc.

## Archive Rules

- Archive completed plans after their checklist is closed and the result is reflected in a canonical doc.
- Move superseded audit outputs under `Docs/archive/docs-housekeeping/<date>/`.
- Keep `Docs/ARCHIVED_MD_INDEX.md` current when files move into archive or quarantine.
- Mark delete candidates in `DOCS_HOUSEKEEPING_AUDIT.md`; do not delete without explicit operator confirmation.

## Anti-Sprawl Checks

- Search active docs before adding a new file: `rg -n "<topic>" Docs *.md`.
- Search for stale removed desktop-shell framework terms and old launcher names after edits; active docs should describe the V6 WebView-first surface.
- Verify new references point to existing files, especially when referencing archived docs.
- Run `Pipeline\Tests\Unit\Invoke-ActiveDocsReferenceChecks.ps1` after substantial doc movement or navigation edits.

## Closeout

- Update `Docs/DOCS_INDEX.md` when adding a durable doc.
- Update `Docs/DOC_TOUCH_LOG.md` only when the change is part of the normal engineering/documentation touch-log discipline.
- Keep the active root set small: `AI_AGENT_START_HERE.md`, `AI_DIRECTIVE.md`, `OPEN_WORK_CHECKLIST.md`, `V6_SPLIT_NOTES.md`, `DOCS_HOUSEKEEPING_AUDIT.md`, and this checklist.
