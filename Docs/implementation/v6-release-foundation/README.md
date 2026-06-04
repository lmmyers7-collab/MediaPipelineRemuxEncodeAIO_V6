# V6.0.0 Release Foundation

Purpose: define small, controlled planning and execution phases for a
maintainable Windows 11 `V6.0.0` portable Tauri release.

This folder is an implementation planning pack. It does not replace the
canonical project sources:

- `AGENTS.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/DOCS_INDEX.md`
- `Docs/generated/PROJECT_INDEX.md`
- `Docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`
- `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `Docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md`

## Operator Decisions

- Release label: `V6.0.0`
- Delivery model: portable bundle only
- Update model: manual download/copy/install only
- Signing: unsigned
- Runtime state: externalized outside the install folder
- Personal release artifacts: no tests or dev docs
- Friend handoff bundles: keep Tauri source with runnable artifacts
- Validation environment: clean Windows account or separate Windows machine
- Backend version identity: align backend `v6.000` surfaces to `V6.0.0`

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

