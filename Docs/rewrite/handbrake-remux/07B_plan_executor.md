# Phase 07B PowerShell Plan Executor and Parity Harness

Date: 2026-05-30

Scope: additive PowerShell-domain `pipeline_plan.v1` validator, dry-run command
builder, and Phase 03 fixture parity harness. This phase does not change the
default production execution path, queue launch behavior, settings persistence,
publish/drain behavior, source/scratch/output movement, cleanup behavior,
command journal behavior, UI, or Tauri lifecycle behavior.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: PowerShell implementation under `engine/`,
  PowerShell unit/parity harness under `Pipeline/Tests/Unit/`, generated
  summaries/index context, and this approved rewrite docs/tracker subtree
- High-risk areas touched: yes. The phase models FFmpeg command generation,
  stream mapping, audio/subtitle mapping, and execution posture. The
  implementation is additive, dry-run-only, test-only, and does not wire into
  production execution.

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
- `Docs/rewrite/handbrake-remux/07_pipeline_plan_contract.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/07B_POWERSHELL_PLAN_EXECUTOR.md`

## Implemented Executor

New files:

- `engine/process/pipeline_plan_executor.ps1`
- `engine/process/pipeline_plan_executor/validation.ps1`

Public functions:

- `ConvertFrom-PipelinePlanJson`
- `Read-PipelinePlanJson`
- `Assert-PipelinePlanValid`
- `New-PipelinePlanExecutorDryRun`
- `ConvertTo-PipelinePlanExecutorJson`
- `Invoke-PipelinePlanExecutorDryRun`

The validator accepts serialized `pipeline_plan.v1` JSON and rejects:

- unknown top-level, output, stream action, reason, runtime fallback, command
  plan, or command step fields;
- non-`pipeline_plan.v1` schema versions;
- non-`dry_run` intents;
- command plans that set `dryRunOnly=false` or `canExecute=true`;
- `UNKNOWN` route plans;
- COPY/REMUX plans that encode video;
- ENCODE plans without `video=encode`;
- subtitle burn-in when no approved existing PowerShell burn-in command builder
  exists for Phase 07B.

The dry-run builder returns `pipeline_plan_executor_dry_run.v1` records with
`dryRunOnly=true` and `wouldExecute=false`. It prints command lines only through
the explicit dry-run function and does not execute native tools.

## Command Mapping

ENCODE plans call the existing PowerShell encode builders:

- `New-EncodeAttemptPlan`
- `New-EncodeFfmpegArgumentList`

Plan audio and subtitle stream actions are mapped into FFmpeg stream arguments
and passed into the existing encode builder. Video flags, ladder handling, and
primary encode command shape remain owned by `engine/decide/encode_policy.ps1`.

REMUX plans build a dry-run representation of the current two-stage remux
shape:

- FFmpeg `REMUX-AV`: input, `-map 0:V`, `-c:v copy`, optional HEVC bitstream
  filter, attachments, chapters/metadata, plan-derived audio arguments, and a
  temp AV output.
- mkvmerge `REMUX-MUX`: output, title, temp AV input, and plan-derived subtitle
  source references.

The current production remux command shape is inline in
`Pipeline/MediaPipeline/remux.ps1`, not a standalone builder. Phase 07B keeps
production code unchanged and protects the new dry-run shape with parity tests
instead of refactoring `Do-Remux`.

## Parity Harness

New file: `Pipeline/Tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1`

The harness generates `pipeline_plan.v1` JSON for every Phase 03 source-media
fixture through the existing Python planner, then feeds each plan to the
PowerShell executor. It asserts:

- all 10 Phase 03 fixtures are covered;
- every executor result is dry-run-only and non-executing;
- REMUX fixtures produce FFmpeg `REMUX-AV` plus mkvmerge `REMUX-MUX` dry-run
  commands;
- REMUX AV commands preserve the existing video-copy posture and never include
  `hevc_nvenc` or `libx265`;
- ENCODE fixtures produce one FFmpeg command built through
  `New-EncodeAttemptPlan`;
- ENCODE commands retain key existing builder invariants: `-map 0:V`,
  `-map 0:t?`, Matroska muxer posture, and the plan-selected encoder;
- malformed plans with unknown fields are rejected;
- REMUX/COPY plans containing `encode_video` steps are rejected.

Normalization used by the harness:

- input/output/temp paths are normalized to placeholders for comparison;
- Phase 07 plan stream indexes are treated as source stream indexes. The
  production audio/subtitle builders may translate source streams into audio
  ordinals or mkvmerge TIDs after probing real files, so Phase 07B parity is a
  dry-run command-shape and invariant check, not a substitute for real-media
  stream-ID validation.

## Acceptance Notes

- A serialized `PipelinePlan` can be validated and converted into a dry-run
  command record.
- Remux/copy plans are guarded so they cannot invoke video encode.
- Encode dry-runs reuse existing encode command builders.
- Production execution remains unchanged; no caller was switched to the new
  executor.
- Non-MKV/Matroska command parity and subtitle burn-in remain intentionally
  unsupported in Phase 07B until a later phase explicitly scopes the existing
  command-builder behavior and real-media validation.

## Required Operator Validation Before Any Cutover

Because this phase touches AGENTS.md high-risk media-command areas, this code
evidence is not production approval. Before any production route replacement
or real-job execution through the new path, the operator must review parity
results and rerun the appropriate validation rung:

- PowerShell unit tests for route, audio, subtitle, and plan executor behavior;
- reliability regression wrapper;
- tool integration checks;
- representative real-media validation covering at least one remux and one
  encode sample, plus subtitle/audio samples when those mappings are promoted.

## Risks And Follow-Ups

- Remux command parity is protected without refactoring `Do-Remux`; the real
  production builder remains inline until a later explicit refactor.
- Runtime remux codec recheck and NVENC CPU fallback remain plan records and
  dry-run metadata only. They are not production back-edges yet.
- Subtitle burn-in is deliberately rejected because the current approved
  PowerShell builders do not provide a burn-in path for this phase.
- Non-MKV outputs are rejected for concrete command parity because the current
  existing encode/remux builders in this path are Matroska-oriented.

## Next Phase Readiness

Phase 08 can use the abstract plan and dry-run evidence for UI planning after
human review accepts the Phase 07B parity limitations and the current
non-Phase-07B reliability-wrapper blocker is resolved or explicitly waived.
Production execution cutover remains blocked until the later rollout gate
proves zero unexplained divergences and completes high-risk real-media
validation.
