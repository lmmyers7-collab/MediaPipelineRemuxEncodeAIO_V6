# 0001. Folder-by-domain layout

Status: accepted
Date: 2026-05-28

## Context

The Python application layer accumulated 65 `facade_*.py` and 108
`service_*.py` files as flat siblings under
`DesktopApp/mediapipeline_desktop_app/`, named by suffix
concatenation (`service_audit_rerun_csv.py`,
`facade_settings_patch_candidate.py`). The natural cohesion of a single
feature — settings, audit, rename, pending publish — is now scattered
across 5-22 files at the same directory level. The PowerShell engine has
the same shape: 168 `.ps1` files in `Pipeline/Modules/`, named with dotted
suffixes (`Audit.Audio.ps1`, `Subtitles.Common.Config.ps1`) that mimic
folders without being folders.

This makes feature work expensive: every change requires `Grep`-ing the
flat tree to find sibling files that share state. AI sessions spend
tokens reconstructing which files belong together. The naming convention
prevents IDE folder grouping from helping.

`ARCHITECTURAL_OVERHAUL_PLAN.md` §Target Architecture proposes re-folding
by domain.

## Decision

Group source files by **domain** (what they're about), not by **role
suffix** (what kind of file they are). Folders name domains; files name
roles.

Target Python layout:

```
app/
  api/           # HTTP transport
  orchestration/ # Job lifecycle, queue, scheduling
  ingest/        # Source discovery, scratch copy
  metadata/      # Probe, naming parse, sidecar read
  decide/        # Remux-vs-encode, ladder, size policy
  transcode/     # FFmpeg invocation, attempt loop
  subtitles/     # ASS/SRT/PGS/TX3G adapters
  audio/         # Channel/codec policy
  publish/       # Pending park, drain, final placement
  rename/        # Plan/apply/undo
  storage/       # State DB, locks, paths
  network/       # Coordinator/worker (optional)
  observability/ # Logs, journal, metrics
  config/        # Schema, load/save
  contracts/     # Pydantic models, schema generation
  common/        # Paths, errors, retries
```

Target PowerShell layout:

```
engine/<domain>/<role>.ps1
```

Rules in force:

- Files name roles (`publish/drain.py`, `subtitles/srt.py`), not concerns
  (`drain_publish.py`).
- No suffix-concatenated filenames
  (no `facade_settings_patch_candidate.py`).
- No `_chatgpt`, `_v2`, `_new`, `_old`, `_copy` suffixes.
- No PowerShell files with more than one dot
  (so no `Audit.Audio.ps1`; that becomes `engine/audit/audio.ps1`).
- No `helpers.py`, `utils.py`, `common.py` files; `app/common/` is allowed
  as a package, not a junk drawer.
- Tests mirror source paths: `tests/python/unit/publish/test_drain.py`.

Today the `app/` skeleton exists (commit `77b8b4c`) with empty domain
directories and a populated `app/contracts/`. The migration of existing
flat trees into the domain layout happens in Phase 3 / Phase 6 of the
overhaul plan and is **not** in scope of this ADR — this ADR establishes
only the target shape and the naming rules.

## Consequences

Code and structure:

- New code lands in the domain folder it belongs to, not under
  `DesktopApp/mediapipeline_desktop_app/`.
- Old paths remain valid until Phase 6 removes them; the AGENTS.md
  blocklist already prevents new files at the legacy paths.

Operational surface:

- IDE folder collapsing and `Grep -path` filters become useful.
- Token cost for AI agents reading a feature drops because one folder
  contains its files.

Testing and CI:

- A naming-lint script (`scripts/lint-naming.py`, Phase 5) enforces the
  forbidden-suffix rules in CI.
- Test paths mirror source paths, removing a guess step.

Migration cost:

- The re-fold is Phase 3 (PowerShell into `engine/<domain>/`) and Phase 6
  (Python services/facades into `app/<domain>/`). Both proceed
  domain-at-a-time, each domain reversible by reverting one merge.

Reversibility:

- High. The naming rules are CI-enforced; reverting would require
  removing the lint and (separately) folding files back. The folded
  layout is the cheaper-to-maintain state.

## Alternatives considered

**Keep the flat tree, document the implicit grouping.** The original
fragmenters chose this implicitly. The result is documented in
`MONOLITH_SPLIT_PLAN.md`. It does not scale — the count grew, not shrank,
and naming reviewers cannot stop drift. Rejected.

**Rename the existing files in place to encode the domain in the
prefix** (e.g. `audit__rerun__csv.py`). Cheaper than folders but defeats
IDE tools, defeats `git mv`-by-folder, and looks like a workaround.
Rejected.

**One package per `facade_*.py` / `service_*.py` pair.** Too granular at
this scale — would land 100+ tiny packages. The plan's coarser ~12-15
domain folders matches how operators reason about the pipeline.
Rejected.

## Validation

- `scripts/lint-naming.py` (Phase 5) — fails CI on banned suffixes and
  banned file names listed in `Decision`.
- `summaries/<path>.md` frontmatter carries `owner_domain`; a drift
  check can assert every file under a domain folder declares that
  domain.
