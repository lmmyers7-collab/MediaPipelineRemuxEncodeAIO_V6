# 2026.06.04.001 Release Foundation

Purpose: define small, controlled planning and execution phases for a
maintainable Windows 11 `2026.06.04.001` portable Tauri release.

This folder is an implementation planning pack. It does not replace the
canonical project status/checklist sources: `README.md`, `CHANGELOG.md`,
`AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, and `docs/OPEN_WORK_CHECKLIST.md`.

Required supporting references:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/DOCS_INDEX.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`

## Independent Phase Contract

Each phase is independently assignable. Before starting a phase, the
implementation agent must verify that the phase-specific prerequisites exist
and match the same version, candidate folder, and evidence set named by the
phase. If a prerequisite is missing, stale, or for a different candidate, stop
and report the phase as not ready instead of proceeding.

Phase completion means only the exit criteria in that phase are met. A built
candidate is not handoff-ready until package/open/close validation passes for
that same candidate, and a finalized release is not acceptable until package
validation and real-media pilot evidence both reconcile to the same candidate.

## Operator Decisions

- Release label: `2026.06.04.001`
- Delivery model: portable bundle only
- Update model: manual download/copy/install only
- Signing: unsigned
- Runtime state: externalized outside the install folder
- Personal release artifacts: no tests or dev docs
- Friend handoff bundles: keep Tauri source with runnable artifacts
- Validation environment: clean Windows account or separate Windows machine
- Release label identity: use `2026.06.04.001` for release folders/manifests while
  preserving backend `2026.06.04.001` product-version contracts unless a separate
  compatibility migration is approved and validated.

## Phase Files

- `PHASE_0_DOCS_ONLY_PLANNING.md`
- `PHASE_1_RELEASE_IDENTITY.md`
- `PHASE_2_FILE_LAYOUT_CLEANUP.md`
- `PHASE_3_DOCUMENTATION_CLEANUP.md`
- `PHASE_4_TAURI_RELEASE_CANDIDATE.md`
- `PHASE_5_PACKAGE_OPEN_CLOSE_VALIDATION.md`
- `PHASE_6_REAL_MEDIA_PILOT.md`
- `PHASE_7_FINALIZATION.md`

## Guardrails

- Do not mutate source media.
- Do not change FFmpeg, subtitle, audio, remux, encode, publish, drain,
  queue, cleanup, or source/scratch/output behavior in these phases unless a
  later phase is explicitly widened and revalidated.
- Do not move backend-owned policy into WebView or Tauri.
- Do not reintroduce removed root launchers.
- Do not create new flat `facade_*.py`, `service_*.py`, or
  `command_payloads_*.py` files.
- Do not create dotted PowerShell files under `Pipeline/Modules`.
- Do not create new top-level Markdown status/checklist/report files.

## Required Reporting

Every implementation phase should report:

- change packet ID
- files touched
- validation commands and results
- strict change-packet coverage result
- unrelated dirty files not absorbed into the packet
- rollback plan

