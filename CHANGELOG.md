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

- Configurable movie/TV remux-copy bitrate ceilings:
  `MovieRouteMaxVideoBitrateMbps` defaults to `35` Mbps and
  `TVRouteMaxVideoBitrateMbps` defaults to `18` Mbps. Routing now uses
  those saved settings before choosing encode for `bitrate_over_threshold`,
  while folder `RouteMaxVideoBitrateMbps` remains the per-job override.
- Added `RouteThresholdMode` so initial remux-vs-encode routing can use
  current compatibility-advisory behavior, size-only, bitrate-only, or
  size-or-bitrate hard thresholds.
- Phase 2 config cleanup foundation:
  `app/contracts/config.py` is now the Pydantic v2 config contract,
  `app/config/load.py` owns PSD1 import plus PSD1 serialization helpers,
  `schemas/config.v1.schema.json` is generated from the contract, and
  `scripts/dev/generate_config_schema.py --check` enforces schema drift.
- Phase 3 stage-boundary foundation:
  `app/contracts/stages.py` is now the Pydantic v2 source for stage
  request/result contracts, `app/orchestration/runner.py` is the single
  new Python subprocess boundary, `engine/entrypoint.ps1` accepts
  `-Stage` plus `-PayloadJson`, and `schemas/stages.v1.schema.json` is
  generated from the contract. Only the read-only `decide` stage is
  enabled in the PowerShell dispatcher in this additive slice.
- Phase 4 tooling/state foundation:
  `app/storage/db.py` adds a WAL-mode SQLite mirror under the runtime
  state root, `app/observability/logging.py` adds JSON-line logging
  helpers, and `app/validation/boundary.py` validates API/stage boundary
  envelopes through the generated contracts. Existing JSON state files
  and route payloads remain authoritative.
- Phase 4 check entrypoints:
  `scripts/dev/check_python_typing.py` runs the initial app-layer mypy
  scope, `scripts/dev/check_powershell_analysis.ps1` runs engine-only
  PSScriptAnalyzer when installed, and the existing architecture
  guardrail script is wired into the development safety net.
- Phase 5 drift-prevention foundation:
  `scripts/lint-naming.py` blocks new flat facade/service/payload
  modules, dotted `Pipeline/Modules` growth, deprecated suffixes, new
  root callers, and new top-level report/checklist Markdown. The new
  `tests/contract/` tree mirrors config/stage contract checks while the
  legacy `DesktopApp/tests` entrypoints remain callable.
- Phase 6 legacy-removal completion:
  root launcher shims, flat Python facade/service compatibility paths,
  old command-payload adapters, and `Pipeline/Modules` are no longer active
  surfaces. Guardrails still block reintroduced root `.bat`/`.ps1` launchers,
  new flat `facade_*`/`service_*`/payload modules, and new dotted
  `Pipeline/Modules` files.
- Phase 7 handoff documentation foundation:
  root `README.md` now exists as the operator entry point,
  `Docs/DOCS_INDEX.md` points agents to `AGENTS.md` instead of old
  redirect files, and active-doc checks now fail if the canonical
  handoff docs disappear.
- WebView split tooling and generated baselines:
  Node-based scripts now map WebView god-file candidates, check backend-served
  asset order, preserve the public global contract, track DOM-ID review gaps,
  enforce settings route ownership, and hold ESLint warning budgets. The new
  runbook and guardrail docs keep future plain-script splits scoped and
  reversible.
- Domain/UI follow-up coverage for the current overhaul surface:
  Rename Workbench V7 static/backend tests, library profile contract tests,
  final-library promotion service/WebView settings tests, and settings-libraries
  static coverage are present in the active test tree.
- `Docs/RealMediaValidationRuns/README.md` records the non-sensitive
  operator-attested representative real-media validation status for
  2026-05-28.
- `scripts/dev/check_active_doc_references.py` adds a Python active-doc
  reference check for moved docs, archived housekeeping references,
  absolute local handoff paths, and removed legacy desktop-shell wording.
- `CHANGELOG.md` (this file) as the single canonical changelog (ADR-0009).
- `Docs/architecture/ARCHITECTURE.md` — short, human-maintained
  architecture summary that cites the ADRs and the overhaul plan.
- `Docs/generated/PIPELINE_MAP.md` — auto-generatable index of the
  nine canonical stages and their payload/result types from
  `app/contracts/stages.py`.
- `Docs/generated/FILE_SUMMARIES.md` — pointer to the `summaries/`
  directory, the per-source-file summary scheme, and the SHA-256 drift
  rule.
- `Docs/archive/sessions/SESSION.md` — archived session scope notes from
  the overhaul workspace; current startup guidance lives in `AGENTS.md`.
- `Docs/adr/` seeded with `README.md`, `0000-template.md`, and
  ADRs `0001`–`0011`. ADR-0011 (V5 → V6 split) was written from the
  surviving `V6_SPLIT_NOTES.md` at the repo root; the source notes were
  moved to `Docs/archive/v6-split-notes-2026-05-20.md` in the same
  change so the validation evidence and live-API proof survive.
- `Docs/audits/latest.md` capturing current known issues distilled from
  `Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md` §Current-State
  Audit.
- `scripts/release/Backup-PreOverhaul.ps1` — operator-run script that
  produces a tagged source archive, a release-package copy, and a
  `LocalBase/State/` snapshot under an external `-Destination`, with
  manifest + SHA-256 evidence.
- Branch `pre-overhaul-snapshot` (passive archive) created from stash
  `pre-overhaul-WIP-snapshot-2026-05-28`. Tag `v6-pre-overhaul` is
  unchanged.

### Changed

- `V6_SPLIT_NOTES.md` moved from repo root to
  `Docs/archive/v6-split-notes-2026-05-20.md` (git history preserved
  via `git mv`). ADR-0011 is the durable architectural summary.
- Root launchers relocated under `scripts/`, and the one-release root shim
  phase is now complete. The old root `.bat`/`.ps1` launcher paths are removed
  from the active workspace; `AGENTS.md §6`, `README.md`, and active checklist
  docs point to the canonical `scripts\` paths.
- Phase 1 generated-context checks are now enforceable:
  `scripts/dev/generate_project_index.py --check` verifies
  `Docs/generated/PROJECT_INDEX.md` and
  `Docs/generated/DEPENDENCY_GRAPH.md`,
  `scripts/dev/generate_pipeline_map.py --check` verifies
  `Docs/generated/PIPELINE_MAP.md`, and `refresh_summaries.py --check`
  covers the active canonical script and source paths.
- `.pre-commit-config.yaml` now runs summary, project-index, and
  pipeline-map drift hooks plus the Phase 2 config schema drift hook, and
  `.github/workflows/phase1-drift.yml` runs the same generated-artifact
  checks in CI.
- `.pre-commit-config.yaml` and `.github/workflows/phase1-drift.yml` now
  run `scripts/dev/generate_stage_schema.py --check` for Phase 3 stage
  schema drift.
- Command journal entries, stage runner events, queue dry-run snapshots,
  and completed-job manifest reads now dual-write to the Phase 4 SQLite
  mirror when a runtime state root is available. Reads continue to use
  the existing JSON/state files.
- `.pre-commit-config.yaml` and `.github/workflows/phase1-drift.yml` now
  include Phase 4 architecture guardrails, app-layer typing checks, and
  engine-only PowerShell analysis. CI installs PSScriptAnalyzer before
  enforcing the PowerShell check; local runs skip that check when the
  analyzer module is absent.
- `.pre-commit-config.yaml` and `.github/workflows/phase1-drift.yml` now
  include Phase 5 naming lint and active-doc reference checks.
- Phase 7 handoff docs now treat representative real-media validation as
  closed by operator attestation and Phase 6 local legacy burn-down as
  complete, while keeping PG-3 clean-machine package-mode validation, operator
  acceptance, and future media-behavior revalidation as active gates.
- `Docs/generated/PIPELINE_MAP.md` is generated from
  `app/contracts/stages.py` instead of hand-synced. The stale summary baseline
  was refreshed from the current source tree; `Docs/generated/PROJECT_INDEX.md`
  now indexes 604 source files.

  | Old root path                                                     | New canonical path                                       |
  | ----------------------------------------------------------------- | -------------------------------------------------------- |
  | `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`                   | `scripts/release/build.ps1`                              |
  | `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`                    | `scripts/release/test.ps1`                               |
  | `Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1`              | `scripts/verify-env.ps1`                                 |
  | `Verify-MediaPipelineRemuxEncodeAIO-Environment.bat`              | `scripts/verify-env.bat`                                 |
  | `Run-MediaPipelineRemuxEncodeAIO.bat`                             | `scripts/dev/run.bat`                                    |
  | `Setup-MediaPipelineRemuxEncodeAIO.bat`                           | `scripts/dev/setup.bat`                                  |
  | `Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat`                  | `scripts/dev/start-local-api.bat`                        |
  | `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat`              | `scripts/dev/start-tauri-preview.bat`                    |
  | `Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat`             | `scripts/dev/start-api-and-browser.bat`                  |
  | `New-RealMediaValidationWorksheet.ps1`                            | `scripts/operator/New-RealMediaValidationWorksheet.ps1`  |

  `$PSScriptRoot` resolution in the four moved `.ps1` files was patched
  to step up from their new subfolders so they continue to anchor on the
  repo root. `%~dp0`-relative paths in the moved `.bat` files were
  patched to step up from their new subfolders.
  `scripts/release/Backup-PreOverhaul.ps1`
  calls `scripts/release/build.ps1` through the canonical script layout.
  Release build verification and release self-test layout checks now use the
  canonical `scripts\` paths without requiring root shims.

  `Docs/CURRENT_PROJECT_STATE.md` and `OPEN_WORK_CHECKLIST.md` were
  updated for the canonical launcher and worksheet paths.

  The remaining promotion follow-up is PG-3 package-mode launch/close on a
  separate clean Windows machine plus operator acceptance; the local shim
  removal gate is closed.

### Notes

- ADR-0001 and ADR-0002 are the load-bearing decisions for the
  re-fold of Python facades/services and PowerShell modules.
- ADR-0003, ADR-0005 are `proposed`; their implementations are Phase 3/4
  work.
- ADR-0007 is `deferred`; vanilla JS continues to be the WebView default.
- ADR-0010 and ADR-0011 are `historical`; they record the monolith-split
  campaign and the V5 → V6 split so the source documents
  (`MONOLITH_SPLIT_PLAN.md`, archived `v6-split-notes-2026-05-20.md`)
  are no longer load-bearing.

## [2026-05-28] — Phase 0 / Phase 1 scaffolding (prior commits)

### Added

- `Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md` — V6 → V7 plan of
  record.
- `AGENTS.md` — canonical AI entry point, superseding
  `AI_AGENT_START_HERE.md`, `AI_DIRECTIVE.md`, `AI_HANDOFF.md`.
- `app/` Python skeleton with empty domain dirs; `app/contracts/`
  populated with `config.py` (mirrors PSD1) and `stages.py` (nine
  canonical stages, payload + result per stage,
  `STAGE_SCHEMA_VERSION = "v1"`).
- `scripts/dev/refresh_summaries.py` — Python + PowerShell summary
  generator with SHA-256 drift detection.
- `scripts/dev/generate_project_index.py` — renders
  `Docs/generated/PROJECT_INDEX.md` and
  `Docs/generated/DEPENDENCY_GRAPH.md` from summaries.
- `summaries/` — 540 per-source-file summaries (~2.0 MB total versus
  ~30 MB of source).
- `Docs/generated/PROJECT_INDEX.md`, `Docs/generated/DEPENDENCY_GRAPH.md`.
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
