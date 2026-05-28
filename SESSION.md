# SESSION.md — Current session scope

Last updated: 2026-05-28
Branch: `master`
Operator: project maintainer

## Task

Phase 0 / Phase 1 completion of the V6 → V7 architectural overhaul described in
`ARCHITECTURAL_OVERHAUL_PLAN.md`. Specifically: finish the documentation
scaffolding that earlier commits referenced but did not actually land
(`Docs/adr/`, `CHANGELOG.md`, `ARCHITECTURE.md`, `PIPELINE_MAP.md`,
`FILE_SUMMARIES.md`), add the missing operator-facing audit and session
files that `CLAUDE.md` now expects, and stage a release-time backup script
the operator can run manually before deeper phases begin.

Phase 0 — Inventory and safety backup — is already materially complete:

- Tag `v6-pre-overhaul` exists on commit `8d6d9f6` (Phase 0 anchor).
- Branch `pre-overhaul-snapshot` exists (created from stash
  `pre-overhaul-WIP-snapshot-2026-05-28`), preserving the ~200 file
  uncommitted churn from the doc-cleanup pass as a passive archive.
- `scripts/release/Backup-PreOverhaul.ps1` (added this session) wraps the
  remaining Phase 0 actions: zipped source archive of the tag, release
  build, `LocalBase/State` snapshot, manifest with SHA-256 evidence. The
  operator runs it manually with an external `-Destination`.

## In-scope paths for this session

Additive only. No edits to existing files except `MEMORY.md` (its dedicated
index file at `~/.claude/projects/<project>/memory/MEMORY.md`).

- `SESSION.md` (this file)
- `CHANGELOG.md`
- `ARCHITECTURE.md`
- `PIPELINE_MAP.md`
- `FILE_SUMMARIES.md`
- `Docs/adr/README.md`
- `Docs/adr/0000-template.md`
- `Docs/adr/0001-folder-by-domain-layout.md`
- `Docs/adr/0002-python-orchestrates-powershell-executes.md`
- `Docs/adr/0003-sqlite-as-state-store.md`
- `Docs/adr/0004-pydantic-as-contract-source-of-truth.md`
- `Docs/adr/0005-structured-json-logging.md`
- `Docs/adr/0006-local-api-as-only-operator-surface.md`
- `Docs/adr/0007-webview-framework-choice.md`
- `Docs/adr/0008-tauri-webview2-shell.md`
- `Docs/adr/0009-one-canonical-changelog.md`
- `Docs/adr/0010-monolith-split-campaign.md`
- `Docs/audits/latest.md`
- `scripts/release/Backup-PreOverhaul.ps1`

Note: `Docs/adr/` uses the same capitalization as the existing `Docs/`
tree to avoid Windows case-folding collisions on `core.ignorecase`. The
`ARCHITECTURAL_OVERHAUL_PLAN.md` reference to lowercase `docs/adr/` is
slated for a future `Docs/` → `docs/` rename, which will be its own ADR
and merge commit.

## Out-of-scope for this session

These directories are explicitly **not** touched here, even though the
plan eventually changes them:

- `Pipeline/Modules/` and `Pipeline/*.ps1` (PowerShell engine).
- `DesktopApp/mediapipeline_desktop_app/**` (Python services/facades).
- `app/**` (already populated by commit `77b8b4c`; modifying it is Phase 2
  / Phase 3 work).
- `engine/**` (does not yet exist; Phase 3).
- `Pipeline/Schemas/` (Phase 4 regenerator territory).
- `LocalBase/` (runtime state, gitignored).
- `AGENTS.md`, `CLAUDE.md`, `.claude/**` (governing files; flag drift in
  the wrap-up note but do not edit silently).
- Removing or moving any of the legacy `*_REPORT.md`, `*_FIXES.md`
  redirect stubs already committed.

If the next edit would cross any of those, stop and ask.

## Validation rung (per AGENTS.md §5)

Docs-only changes. Validation is:

1. `git diff --stat` review — no source files altered.
2. Link/path existence check — every relative link in the new files
   resolves to an existing target.
3. `python scripts/dev/refresh_summaries.py` if any of the new files lands
   under a path the summary generator covers (it does not — Markdown is
   not walked).

No real-media validation, no SmokeTests run, no release build invoked.

## Rollback

`git reset --hard <commit-before-this-session>` reverts every file. None
of the new files are imported by code, so nothing breaks if deleted.

Tag `v6-pre-overhaul` is the deeper rollback target and is not moved.
