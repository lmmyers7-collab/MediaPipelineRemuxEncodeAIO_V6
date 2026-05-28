# Changelog

All notable changes to this project are recorded here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to a date-based release cadence rather than semantic
versioning until V7 ships.

This is the single canonical changelog (ADR-0009). Per-feature
`*_REPORT.md` and `*_FIXES.md` at the repo root are deprecated; if a PR's
intent is worth keeping, it goes here and/or in an ADR.

## [Unreleased]

### Added

- `CHANGELOG.md` (this file) as the single canonical changelog (ADR-0009).
- `ARCHITECTURE.md` at the repo root — short, human-maintained
  architecture summary that cites the ADRs and the overhaul plan.
- `PIPELINE_MAP.md` at the repo root — auto-generatable index of the
  nine canonical stages and their payload/result types from
  `app/contracts/stages.py`.
- `FILE_SUMMARIES.md` at the repo root — pointer to the `summaries/`
  directory, the per-source-file summary scheme, and the SHA-256 drift
  rule.
- `SESSION.md` at the repo root — current session scope per the
  updated `CLAUDE.md` startup procedure.
- `Docs/adr/` seeded with `README.md`, `0000-template.md`, and
  ADRs `0001`–`0010`. ADR-0011 is intentionally absent until
  `V6_SPLIT_NOTES.md` (or equivalent source material) surfaces.
- `Docs/audits/latest.md` capturing current known issues distilled from
  `ARCHITECTURAL_OVERHAUL_PLAN.md` §Current-State Audit.
- `scripts/release/Backup-PreOverhaul.ps1` — operator-run script that
  produces a tagged source archive, a release-package copy, and a
  `LocalBase/State/` snapshot under an external `-Destination`, with
  manifest + SHA-256 evidence.
- Branch `pre-overhaul-snapshot` (passive archive) created from stash
  `pre-overhaul-WIP-snapshot-2026-05-28`. Tag `v6-pre-overhaul` is
  unchanged.

### Notes

- ADR-0001 and ADR-0002 are the load-bearing decisions for the
  re-fold of Python facades/services and PowerShell modules.
- ADR-0003, ADR-0005 are `proposed`; their implementations are Phase 3/4
  work.
- ADR-0007 is `deferred`; vanilla JS continues to be the WebView default.

## [2026-05-28] — Phase 0 / Phase 1 scaffolding (prior commits)

### Added

- `ARCHITECTURAL_OVERHAUL_PLAN.md` — V6 → V7 plan of record.
- `AGENTS.md` — canonical AI entry point, superseding
  `AI_AGENT_START_HERE.md`, `AI_DIRECTIVE.md`, `AI_HANDOFF.md`.
- `app/` Python skeleton with empty domain dirs; `app/contracts/`
  populated with `config.py` (mirrors PSD1) and `stages.py` (nine
  canonical stages, payload + result per stage,
  `STAGE_SCHEMA_VERSION = "v1"`).
- `scripts/dev/refresh_summaries.py` — Python + PowerShell summary
  generator with SHA-256 drift detection.
- `scripts/dev/generate_project_index.py` — renders `PROJECT_INDEX.md`
  and `DEPENDENCY_GRAPH.md` from summaries.
- `summaries/` — 540 per-source-file summaries (~2.0 MB total versus
  ~30 MB of source).
- `PROJECT_INDEX.md`, `DEPENDENCY_GRAPH.md` at the repo root.
- Tag `v6-pre-overhaul` on commit `8d6d9f6` as the deep rollback
  target.

### Changed

- `AI_AGENT_START_HERE.md`, `AI_DIRECTIVE.md` reduced to redirect stubs
  pointing at `AGENTS.md`.

### Removed

- Root noise: per-feature `*_REPORT.md`, `*_FIXES.md`,
  `DOCS_HOUSEKEEPING_CHECKLIST.md`, and the doc-cleanup-in-progress
  workspace files.

### Notes

- Commit `77b8b4c`'s message references "ADRs 0001 and 0002 anchor the
  direction"; that commit did not actually land ADR files. The ADRs
  are landed in the current `Unreleased` section.

## [2026-04-20] — Initial V6 baseline

- First V6 baseline (`da13cd2`). See `Docs/CURRENT_PROJECT_STATE.md` and
  `Docs/architecture/` for the inherited shape.

---

[Unreleased]: about:blank
[2026-05-28]: about:blank
[2026-04-20]: about:blank
