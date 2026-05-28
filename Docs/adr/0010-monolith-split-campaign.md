# 0010. Historical: monolith-split campaign

Status: historical
Date: 2026-05-28

## Context

This ADR records, in a fixed and small form, the monolith-split
campaign that produced the current `facade_*.py` / `service_*.py` /
`command_payloads_*.py` / `Pipeline/Modules/*.ps1` shape. The original
plan was `MONOLITH_SPLIT_PLAN.md` (~141 KB). That document is too large
to be a living artifact; this ADR is the durable summary that survives
when `MONOLITH_SPLIT_PLAN.md` is archived in Phase 7.

A future contributor reading the codebase for the first time will see
the *result* of the campaign (108 service files, 65 facades, 168
PowerShell modules) and reasonably ask "why?". The honest answer is:
the campaign solved a worse problem and stopped one step short of
folding the output into domain folders.

## Decision

This ADR documents — it does not propose. The decisions recorded here
are historical and are not in force; ADR-0001 (folder-by-domain
layout) is what's in force.

What the campaign did:

- Broke five Python "god files"
  (`mediapipeline_desktop_app/services.py`, `models.py`, the original
  config schema, and others) into single-responsibility siblings.
- Broke `Pipeline/MediaPipeline_chatgpt.ps1` and several large
  `Pipeline/Modules/*.ps1` files into smaller modules, named with
  dotted suffixes for cohesion (`Audit.Audio.ps1`,
  `Subtitles.Common.Config.ps1`).
- Introduced the contracts and command-payload validation layer in
  Python.
- Migrated test files 1:1 with source files
  (`test_facade_<name>.py`, `test_service_<name>.py`).

What the campaign did **not** do:

- Group split files into folders. Files landed as flat siblings.
- Establish naming rules to prevent re-fragmentation.
- Collapse the 1:1 test mapping into behavior-grouped tests.

Why it stopped short:

- The campaign's scope ended at "break the god files". Folder grouping
  was tabled as a follow-up that did not get scheduled until V7
  planning.

What replaces it:

- ADR-0001 (folder-by-domain layout) establishes the target shape.
- The forbidden-name list in ADR-0001 prevents new files at the legacy
  paths.
- Phases 3 and 6 of `ARCHITECTURAL_OVERHAUL_PLAN.md` execute the fold.

## Consequences

Code and structure:

- The current flat trees are a snapshot of the campaign's stopping
  point. They are intentional, not accidental, and the path forward
  (re-fold) is documented.
- `MONOLITH_SPLIT_PLAN.md` can be archived in Phase 7 without losing
  context, because this ADR is the durable record.

Operational surface:

- No operator-visible change. This ADR is for engineering and AI
  sessions.

Testing and CI:

- The 1:1 test mapping persists until Phase 5 collapses it into
  behavior tests. That work is referenced here but owned by ADR-0001
  and the migration plan.

Migration cost:

- Zero — this is a record, not a change.

Reversibility:

- Not applicable; historical.

## Alternatives considered

**Delete `MONOLITH_SPLIT_PLAN.md` without an ADR.** Loses the "why" of
the current shape and invites a future contributor to "fix" it by
re-merging files back into god files. Rejected.

**Keep `MONOLITH_SPLIT_PLAN.md` as a living document.** It was used as
a checklist during the campaign; once the campaign is done, a living
141 KB document is itself a drift surface. Archive is the right
treatment.

## Validation

- `MONOLITH_SPLIT_PLAN.md` can be moved to `Docs/archive/` without
  breaking any link from a current canonical doc. ADR-0001 cites this
  ADR for the historical context.
