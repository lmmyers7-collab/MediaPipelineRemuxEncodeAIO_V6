# Phase 07 Pipeline Planner and Dry-Run Command Builder

Date: 2026-05-30

Scope: additive Python-owned abstract `PipelinePlan` contract, dry-run command
preview builder, focused planner tests, generated context, and tracker update.
This phase does not change PowerShell FFmpeg/remux command generation, runtime
route execution, queue behavior, UI, settings persistence, subtitle/audio
execution, source/scratch/output movement, publish/drain behavior, command
journal behavior, or Tauri lifecycle behavior.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: Python contracts/orchestration under `app/`,
  Python tests under `tests/`, generated summaries/index context, and this
  approved rewrite docs/tracker subtree
- High-risk areas touched: yes. The phase models FFmpeg/remux/encode command
  intent and runtime fallback posture, but it remains abstract dry-run preview
  only. No production execution path, PowerShell command builder, stream mapper,
  queue mutation, publish/drain mutation, source movement, cleanup, or command
  journal behavior was changed.

## Input Documents Read

- `AGENTS.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/generated/PROJECT_INDEX.md`
- `Docs/audits/latest.md`
- `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `Docs/rewrite/handbrake-remux/00_execution_tracker.md`
- `Docs/rewrite/handbrake-remux/01_repo_audit.md`
- `Docs/rewrite/handbrake-remux/02_taxonomy_and_terms.md`
- `Docs/rewrite/handbrake-remux/03_source_media_model.md`
- `Docs/rewrite/handbrake-remux/04_decision_engine_contract.md`
- `Docs/rewrite/handbrake-remux/05_preset_schema_migration.md`
- `Docs/rewrite/handbrake-remux/06_encoding_model.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/07_PIPELINE_PLANNER_AND_DRY_RUN_COMMAND_BUILDER.md`

## Current Command Generation Located

Existing production command behavior remains PowerShell-owned:

- `Pipeline/MediaPipeline/remux.ps1` owns `Do-Remux`.
- `Pipeline/MediaPipeline/encode.ps1` owns `Do-Encode`.
- `engine/decide/encode_policy.ps1` owns encode command policy helpers such as
  encode video flags, attempt plans, NVENC checks, and CPU fallback checks.
- `engine/process/pipeline_processing.ps1` dispatches the current route to
  `Do-Remux` or `Do-Encode`.
- `engine/process/ffmpeg_progress.ps1` and `engine/shared/native.ps1` wrap
  native process execution.

Phase 07 did not edit those files. Concrete FFmpeg argument construction stays
there until Phase 07B explicitly scopes the PowerShell plan executor and parity
harness.

## Implemented Plan Contract

New file: `app/contracts/pipeline_plan.py`

The contract is `pipeline_plan.v1` and is intentionally abstract:

- `PipelinePlan`: dry-run plan record with source identity, route summary,
  output proposal, per-stream actions, reason summary, publish strategy,
  verification requirements, runtime fallback posture, command plans, effective
  preset snapshot, and decision snapshot.
- `CommandPlan`: abstract dry-run command preview. It is not executable and
  has `canExecute=false`.
- `CommandPreviewStep`: step-level preview for source copy, video copy, video
  encode, audio copy/transcode/drop, subtitle copy/convert/burn/drop,
  container muxing, output verification, and publish safety.
- `RuntimeFallbackBranch`: explicit representation of the current migration
  risks: remux codec recheck feedback and NVENC CPU fallback.

The contract has no concrete FFmpeg argument list, no executable path, and no
frontend-owned routing logic.

## Implemented Planner

New file: `app/orchestration/planner.py`

Public functions:

- `build_pipeline_plan(source, decision, preset=None, plan_id=None)`
- `build_pipeline_plan_from_preset(source, preset=None, plan_id=None)`

The planner consumes `SourceMediaInfo`, `ProcessingDecision`, and optional
`PresetV2`/legacy policy input. It builds:

- deterministic dry-run plan ids unless one is supplied;
- collision-avoiding output path proposals such as `name.planned.mkv`;
- per-stream plan actions copied from `ProcessingDecision`;
- abstract preview lines with route and reason codes;
- abstract command preview steps;
- publish strategy from rejected/deferred/default safety posture;
- verification requirements copied from the decision;
- effective policy and optional `PresetV2` snapshots.

The planner does not read files, write files, call tools, run encoders, build
FFmpeg args, switch production route execution, or mutate queue/publish state.

## Copy, Remux, And Encode Plan Shape

COPY:

- Used when video/audio/subtitle actions copy and container action is `keep`.
- Preview step is `copy_source`, followed by verification and publish safety.
- `copyUnchangedPossible=true`.

REMUX:

- Used when video is copied and container/audio/subtitle actions require a new
  muxed output.
- Preview includes `copy_video` and `mux_container`.
- Tests prove no `encode_video` step appears on the remux plan.

ENCODE:

- Used when the decision requires video encode, subtitle burn-in, filters,
  downscale, bitrate/codec policy, or other hard route triggers.
- Preview includes planned codec/backend/target mode/quality, output height,
  filters, audio stream actions, subtitle stream actions, and container muxing.
- NVENC plans include an explicit future CPU fallback branch without building
  CPU FFmpeg arguments in Python.

## Runtime Fallback Model

Phase 01 found two current mid-execution route changes:

- remux can fall back to encode after remux codec recheck;
- hardware encode can fall back to CPU encode.

Phase 07 models them without changing behavior:

- COPY/REMUX plans with copied video include
  `fallbackId=remux-codec-recheck`, a typed executor outcome requiring Python
  re-plan rather than silent PowerShell route switching in the future.
- NVENC encode plans include `fallbackId=nvenc-cpu-fallback`, a conditional
  branch placeholder for Phase 07B/rollout.

This resolves the Option A flow tension at the contract level while preserving
the current production path.

## Tests Added

New files:

- `tests/orchestration/__init__.py`
- `tests/orchestration/test_pipeline_planner.py`

Coverage:

- COPY plan keeps source payload unchanged when the container is kept.
- REMUX plan is distinct from ENCODE and never emits an `encode_video` step.
- ENCODE plan includes dimensions, filters, video codec/target, audio
  transcode, subtitle burn, and container choices from the effective policy.
- `build_pipeline_plan_from_preset(...)` carries a `PresetV2` snapshot and
  deferred-publish strategy.
- Serialized plans expose camelCase contract fields such as `schemaVersion`,
  `commandPlans`, and `dry_run`.

## Acceptance Notes

- Dry-run plans exist for copy, remux, and encode paths.
- Remux and encode plans are distinct in tests.
- The contract can power future Summary/log surfaces without frontend routing
  duplication.
- Existing production jobs still run through the old PowerShell path because
  no execution caller was changed.
- The plan is abstract enough for Phase 07B to build concrete commands from
  existing PowerShell builders; Python does not emit FFmpeg args.

## Risks And Follow-Ups

- This is not a production executor. Phase 07B must add the PowerShell plan
  executor and golden parity harness before any new-path real execution.
- Runtime fallback branches are modeled as contract records only; current
  PowerShell fallback behavior is unchanged.
- Real-media validation remains required after any future cutover that changes
  FFmpeg/media-policy, subtitle/audio, publish/drain, source movement, or
  cleanup behavior.
- Guardrail preflight was red before this phase because of pre-existing
  summary-freshness and risky-file-registry drift.

## Next Phase Readiness

Phase 07B can consume `pipeline_plan.v1`, build concrete PowerShell execution
from existing builders, and add parity tests against the legacy path. Phase 08
should not start before Phase 07B if the UI would imply that the new plan can
execute real jobs.
