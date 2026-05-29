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
- `Docs/adr/0011-v5-to-v6-split.md` (added 2026-05-28 follow-up; written
  from the surviving `V6_SPLIT_NOTES.md`)
- `Docs/audits/latest.md`
- `scripts/release/Backup-PreOverhaul.ps1`

Scope additions (2026-05-28 follow-up, after the initial 6047dcc commit):

- `V6_SPLIT_NOTES.md` → moved (via `git mv`) to
  `Docs/archive/v6-split-notes-2026-05-20.md`.
- `Docs/adr/README.md` — table row + paragraph corrected
  (ADR-0011 is `historical`, not `absent`).
- `CHANGELOG.md`, `SESSION.md`, `Docs/audits/latest.md`, memory entry
  updated to reflect the correction.

Scope additions (2026-05-28, item #14 — launcher relocation):

- 10 root launchers moved (via `git mv`) into `scripts/{release,dev,
  operator}/` and `scripts/verify-env.*`. New SCOPE: `scripts/` tree,
  plus 10 root paths now occupied by thin deprecation shims.
- 4 moved `.ps1` files patched: `$PSScriptRoot` resolution now steps up
  from the new subfolders so the scripts still anchor on the repo root.
- 5 moved `.bat` files patched: `%~dp0` relative paths now step up from
  their new subfolders (`%~dp0..\..\Pipeline\...`,
  `%~dp0..\..\DesktopApp\...`).
- `scripts/verify-env.bat` patched to call its sibling `verify-env.ps1`
  by the new name + step up one level for the bundled `pwsh.exe`.
- `scripts/release/Backup-PreOverhaul.ps1` patched to call
  `scripts/release/build.ps1` with a root-shim fallback.
- `scripts/release/build.ps1` verification now invokes
  `scripts\release\test.ps1` in generated bundles, and
  `scripts/release/test.ps1` now checks both canonical `scripts\...`
  files and one-release root shims.

Scope additions (2026-05-28, Phase 2 config cleanup foundation):

- `app/contracts/config.py` converted from interim dataclasses to the
  Pydantic v2 source of truth for PSD1/WebView config keys.
- `app/config/load.py` added as the canonical PSD1 import and
  PSD1-serialization path; the old DesktopApp PSD1 helper now delegates to
  it as a compatibility shim.
- `schemas/config.v1.schema.json` and
  `scripts/dev/generate_config_schema.py --check` added for generated
  schema drift detection.
- `.pre-commit-config.yaml` and `.github/workflows/phase1-drift.yml`
  extended to check the generated config schema.
- `AGENTS.md §6` updated to list the new canonical paths and mark the
  root paths as deprecation shims. AGENTS.md is a governing file; the
  edit was scoped to the launcher section only.
- `Docs/CURRENT_PROJECT_STATE.md` and `OPEN_WORK_CHECKLIST.md` updated
  to use the canonical launcher / worksheet paths.

Scope additions (2026-05-28, Phase 3 pipeline stage boundary foundation):

- `app/contracts/stages.py` converted from interim dataclasses to
  Pydantic v2 stage contracts with `StageRequest`, `StageResult`,
  structured errors, stage-specific payload/data models, and explicit
  intent/confirmation fields for mutation-capable stages.
- `app/orchestration/runner.py` added as the single new Python
  subprocess boundary for stage execution. It resolves bundled
  PowerShell, invokes `engine/entrypoint.ps1`, enforces timeouts, parses
  the single JSON result, classifies malformed/nonzero/timeout failures,
  and exposes a command-journal callback.
- `engine/entrypoint.ps1` added. It accepts `-Stage` and
  `-PayloadJson <json-or-path>`, emits one `StageResult` JSON document on
  stdout, and currently enables only the read-only `decide` stage by
  wrapping the existing PowerShell routing module.
- `schemas/stages.v1.schema.json` and
  `scripts/dev/generate_stage_schema.py --check` added for generated
  stage-schema drift detection. `PIPELINE_MAP.md` now records entrypoint
  enablement and mutation capability from the stage registry.

Scope additions (2026-05-28, Phase 4 tooling and automation foundation):

- `app/storage/db.py` added a runtime-state SQLite mirror with explicit
  migrations, WAL mode, one-writer lock usage, and mirror APIs for command
  journal entries, stage events, queue snapshots, and completed-job rows.
  Existing JSON/state files remain authoritative.
- `app/observability/logging.py` added structured JSON-line logging
  helpers with run/command/stage context and token/secret-style field
  redaction.
- `app/validation/boundary.py` added compatibility-preserving API
  payload validation plus stage payload/result validation backed by the
  Phase 3 Pydantic contracts.
- `CommandJournal`, the stage runner, queue dry-run snapshot promotion,
  and completed-job manifest reads now dual-write to SQLite when a state
  root is available, swallowing mirror failures so legacy behavior is not
  masked.
- `scripts/dev/check_python_typing.py`, `mypy.ini`, and
  `requirements-dev.txt` add the initial app-layer typing check.
  `scripts/dev/check_powershell_analysis.ps1` adds the engine-only
  PSScriptAnalyzer entrypoint. `.pre-commit-config.yaml` and
  `.github/workflows/phase1-drift.yml` now include the Phase 4 checks.

Scope additions (2026-05-28, Phase 5 tests and drift prevention):

- `scripts/lint-naming.py` added as the developer-facing naming lint
  entrypoint. It blocks new flat `facade_*.py`, `service_*.py`,
  `command_payloads_*.py`, dotted `Pipeline/Modules/*.ps1`, deprecated
  `_chatgpt`/`_old`/`_new` suffixes, new root launchers, and new
  top-level report/checklist Markdown while grandfathering existing
  legacy paths unless they are new creation candidates.
- `scripts/dev/check_active_doc_references.py` added as a Python
  active-doc reference check. It mirrors the existing PowerShell
  reference guard for moved docs, archived housekeeping references,
  absolute local handoff paths, and removed legacy desktop-shell wording.
- `tests/contract/` seeded with config/stage contract tests against the
  generated schemas and representative payload/result examples.
  `tests/tooling/` seeded with naming-lint and doc-reference fixture
  coverage. Existing `DesktopApp/tests` and PowerShell smoke wrappers
  remain callable compatibility entrypoints.
- `.pre-commit-config.yaml` and `.github/workflows/phase1-drift.yml`
  now include the Phase 5 naming and active-doc checks.

Scope additions (2026-05-28, Phase 1 generated-context closure):

- `scripts/dev/generate_pipeline_map.py` added. It loads
  `app/contracts/stages.py::STAGE_REGISTRY` and regenerates
  `PIPELINE_MAP.md`; `--check` fails on drift.
- `scripts/dev/generate_project_index.py` now supports `--check` for
  `PROJECT_INDEX.md` and `DEPENDENCY_GRAPH.md` drift.
- `scripts/dev/refresh_summaries.py` now treats the one-release root
  PowerShell shims as explicit source files so their summaries are
  checked while those shims exist.
- `.pre-commit-config.yaml` now has local hooks for summary drift,
  project-index/dependency-graph drift, and pipeline-map drift.
- `.github/workflows/phase1-drift.yml` added for the same checks in CI.
- Full summary baseline refreshed: the 150 stale in-scope summaries are
  current, `PROJECT_INDEX.md` regenerated from 550 summaries, and
  `FILE_SUMMARIES.md` count updated.

Explicitly out-of-scope for this change (to be tackled in their own
sessions):

- `Pipeline\Run-MediaPipelineRemuxEncodeAIO.bat` and
  `Pipeline\Setup-MediaPipelineRemuxEncodeAIO.bat` — engine-internal,
  ADR-0001 domain.
- Doc reference updates (`Docs/operator/*`, `Docs/testing/*`,
  `Docs/inventories/*`, `Docs/CURRENT_PROJECT_STATE.md`,
  `Docs/TLDR.md`, etc.) — many of those docs are already slated for
  archive per plan §Debloat.
- Test files (`DesktopApp/tests/test_*.py`,
  `Pipeline/Tests/*.ps1`) — they continue to pass through the
  deprecation shims.
- `service_release.py` packaging-file allowlist.
- Merging the three `start-*.bat` files into one
  `scripts/dev/launch.bat <mode>` — that is a behavior change with its
  own ADR cost; left for a later session.

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
