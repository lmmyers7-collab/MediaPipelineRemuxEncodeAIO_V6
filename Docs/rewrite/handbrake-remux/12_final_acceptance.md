# Phase 12 Final Acceptance

Last updated: 2026-05-31

Phase 12 finalizes documentation for the HandBrake/remux rewrite. It does not
change runtime behavior, remove compatibility code, commit, push, or approve
production cutover.

## Phase Confirmations

- Approved docs/tracker location:
  `Docs/rewrite/handbrake-remux/`, with tracker
  `Docs/rewrite/handbrake-remux/00_execution_tracker.md`.
- Edit domain: documentation and tracker only in the approved rewrite subtree.
- High-risk areas touched: yes, conceptually, because the docs describe media
  policy contracts, settings/preset migration, pending-publish guard posture,
  and rollout/cutover gates. No high-risk implementation was changed.

## Inputs Read

- `AGENTS.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/generated/PROJECT_INDEX.md`
- `Docs/audits/latest.md`
- `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/12_FINAL_DOCS_OPERATOR_GUIDE_AND_CLEANUP.md`
- `Docs/rewrite/handbrake-remux/00_execution_tracker.md`
- Prior rewrite phase docs `01_repo_audit.md` through `11_rollout_plan.md`
- Relevant source summaries for `SourceMediaInfo`, `PresetV2`,
  `ProcessingDecision`, `PipelinePlan`, verification, rollout, planner, and
  Phase 07B executor files

## Outputs

New Phase 12 docs:

- `Docs/rewrite/handbrake-remux/12_operator_guide.md`
- `Docs/rewrite/handbrake-remux/12_developer_guide.md`
- `Docs/rewrite/handbrake-remux/12_migration_rollback_cleanup.md`
- `Docs/rewrite/handbrake-remux/12_final_acceptance.md`

Tracker updated:

- `Docs/rewrite/handbrake-remux/00_execution_tracker.md`

## Final Status

The rewrite foundation is documented through Phase 12:

- operators have a guide for the Settings preview, decision vocabulary,
  source facts, dimensions, filters, video/audio/subtitle/container policy,
  Output Size Check, presets, rollout, and rollback;
- developers have a guide for the Python-owned source facts, preset policy,
  decision, plan, verification, rollout, and PowerShell dry-run executor
  boundaries;
- migration and rollback posture is explicit;
- cleanup candidates are identified but not deleted;
- known gaps are recorded honestly.

This is not a production cutover. The active production path remains the
legacy PowerShell execution path.

## Known Gaps

- Production route replacement is not approved.
- Live PowerShell old-path comparison logging still needs future work before
  real cutover.
- `PresetV2` is not the persisted write format.
- `block_publish` is a dry-run model only; current production `strict`
  Output Size Check behavior remains fail-job.
- The Phase 07B executor is dry-run-only and intentionally limited for
  subtitle burn-in and non-MKV concrete parity.
- Settings does not persist rollout controls as a dedicated UI/schema feature.
- Cleanup of old labels, adapters, schema paths, or duplicated policy code is
  deferred until after explicit human approval.
- Representative real-media validation must be rerun after any future
  media-policy, FFmpeg, subtitle, audio, publish/drain,
  source/scratch/output movement, or cleanup behavior change.
- Guardrail preflight for Phase 12 remained red only because the existing
  risky-file registry baseline still references removed legacy paths.

## Acceptance Checklist

- [x] A user can understand COPY, REMUX, ENCODE, per-stream actions, preview
  labels, source facts, dimensions, filters, video settings, size/bitrate
  guards, presets, and legacy migration from the Phase 12 operator guide.
- [x] A developer can find SourceMediaInfo, PresetV2, ProcessingDecision,
  PipelinePlan, verification, rollout, and plan-executor boundaries from the
  Phase 12 developer guide.
- [x] Migration, rollback, cleanup candidates, and future validation gates are
  documented.
- [x] No compatibility code was removed.
- [x] No runtime behavior was changed.
- [x] The docs do not mark production cutover complete.

## Validation

Passed docs/generated-context checks:

```powershell
DesktopApp\Runtime\Python\python.exe scripts\dev\refresh_summaries.py --check
DesktopApp\Runtime\Python\python.exe scripts\dev\generate_project_index.py --check
DesktopApp\Runtime\Python\python.exe scripts\dev\check_active_doc_references.py
DesktopApp\Runtime\Python\python.exe scripts\dev\check_architecture_guardrails.py
DesktopApp\Runtime\Python\python.exe scripts\lint-naming.py
DesktopApp\Runtime\Python\python.exe scripts\dev\check_marketecture.py
```

Guardrail comparison:

```powershell
DesktopApp\Runtime\Python\python.exe scripts\dev\ai_guardrail.py preflight --json
DesktopApp\Runtime\Python\python.exe scripts\dev\ai_guardrail.py postflight --json
```

Both guardrail runs remained red only because
`scripts/dev/check_risky_file_registry.py` still references removed legacy
paths. Summary freshness, project index, generated maps/schemas, active doc
references, architecture guardrails, naming lint, god-file guard, and
marketecture guard passed inside postflight. No Phase 12 changed path matched
the risky-file registry.

No unit, browser, PowerShell, Tauri, release, or real-media tests were run for
Phase 12 because this phase changed only documentation in the approved rewrite
subtree.

## Next-Phase Readiness

There is no automatic next implementation phase. The rewrite documentation
phase is complete when validation is recorded.

The next runnable work, if the operator chooses it, should be a separately
approved high-risk production cutover or cleanup phase. It must not be inferred
from Phase 12 documentation completion.
