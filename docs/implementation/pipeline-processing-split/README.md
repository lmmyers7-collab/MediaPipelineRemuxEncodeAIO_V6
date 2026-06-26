# Pipeline Processing Split Planning Pack

Date: 2026-06-24
Status: planning only
Change packet: MP-CHANGE-2026-0624-019

## Purpose

This planning pack describes how to split the critical media-processing
PowerShell path into smaller, troubleshooting-oriented modules without changing
pipeline behavior first.

The target outcome is not "many files for its own sake." The target outcome is
one clear failure boundary per file so an operator or AI coding tool can answer:

> Which part failed: startup, queue, route decision, encode command
> construction, FFmpeg execution, fallback, verification, publish, or remux
> muxing?

This pack is subordinate to the active authority docs:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`

If this pack conflicts with those files, stop and update this pack or the
canonical authority document as appropriate. Do not invent a new source of
truth.

## Current Critical Path

The current operational spine is:

| Current file | Current role |
|---|---|
| `ops/pipeline/entrypoints/MediaPipeline.ps1` | Top-level remux/encode/publish entry script. Loads config, modules, runtime paths, control flags, and starts the queue engine. |
| `ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1` | Dot-sources engine modules into the entrypoint scope in a documented load order. |
| `ops/pipeline/engine/queue/pipeline_engine.ps1` | Owns scan -> queue -> process rounds. Calls queue snapshot and phase execution helpers. |
| `ops/pipeline/engine/process/pipeline_processing.ps1` | Per-file dispatcher. Probes, decides encode vs remux, then calls `Do-Encode` or `Do-Remux`. |
| `ops/pipeline/entrypoints/MediaPipeline/encode.ps1` | Large encode implementation. Owns `Do-Encode`, FFmpeg attempts, fallback, verification, size guard, and encode publish handoff. |
| `ops/pipeline/entrypoints/MediaPipeline/remux.ps1` | Remux implementation. Owns `Do-Remux`, remux fallback checks, FFmpeg AV stage, mkvmerge mux, and remux publish handoff. |
| `ops/pipeline/engine/process/pipeline_plan_executor.ps1` | Existing plan-to-command builder surface for encode/remux command parity. Must be reconciled before adding new command builders. |

The key dispatch boundary is in `pipeline_processing.ps1`, where the route plan
sets `$encode` and dispatches to `Do-Encode` or `Do-Remux`. Preserve that
public boundary until the split is proven.

## Split Principle

Use this rule for every extraction:

> Extract a module only when the extracted unit has its own failure mode, log
> stage, validation target, rollback story, or troubleshooting question.

Do not split purely by line count. Do not split so aggressively that a failure
requires jumping through ten files to understand one command. The right unit is
a stage a human would name while debugging.

## Non-Negotiable Guardrails

- Source media must remain read-only except for explicitly approved safe-delete
  policy work, which is out of scope here.
- Scratch isolation must remain intact.
- Pending publish and drain must remain manifest-backed.
- `Do-Encode` and `Do-Remux` must keep their existing public return contract
  until an explicit later migration changes callers and tests together.
- Existing log stages, repro-command stage labels, failure codes, route reason
  codes, progress stages, and event names must remain stable unless a phase
  explicitly says they are being changed and validates every consumer.
- Do not move media policy into WebView, Tauri, or Python API code.
- Do not recreate `Pipeline/Modules` or any legacy dotted module-shim path.
- Do not hand-edit generated summaries under `docs/generated/`.
- Every implementation phase needs its own change packet or an explicitly
  continued packet, with touched files, validation evidence, rollback notes,
  and Python-impact notes.

## Target File Shape

The first behavior-preserving split should keep the current entrypoint slices
as stable public wrappers, while moving mechanics into active engine modules.

Proposed target:

```text
ops/pipeline/entrypoints/MediaPipeline.ps1
ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1
ops/pipeline/entrypoints/MediaPipeline/encode.ps1       # thin Do-Encode wrapper during transition
ops/pipeline/entrypoints/MediaPipeline/remux.ps1        # thin Do-Remux wrapper during transition

ops/pipeline/engine/process/pipeline_processing.ps1     # route dispatcher only
ops/pipeline/engine/process/pipeline_plan_executor.ps1  # existing plan command builder, reconciled

ops/pipeline/engine/process/encode_context.ps1
ops/pipeline/engine/process/encode_preflight.ps1
ops/pipeline/engine/process/encode_attempt_plan.ps1
ops/pipeline/engine/process/encode_command_builder.ps1
ops/pipeline/engine/process/encode_execution.ps1
ops/pipeline/engine/process/encode_fallback.ps1
ops/pipeline/engine/process/encode_verification.ps1
ops/pipeline/engine/process/encode_size_guard.ps1
ops/pipeline/engine/process/encode_publish.ps1
ops/pipeline/engine/process/encode_orchestrator.ps1

ops/pipeline/engine/process/remux_context.ps1
ops/pipeline/engine/process/remux_preflight.ps1
ops/pipeline/engine/process/remux_subtitle_plan.ps1
ops/pipeline/engine/process/remux_ffmpeg_av_stage.ps1
ops/pipeline/engine/process/remux_mkvmerge_args.ps1
ops/pipeline/engine/process/remux_mkvmerge_stage.ps1
ops/pipeline/engine/process/remux_verification.ps1
ops/pipeline/engine/process/remux_publish.ps1
ops/pipeline/engine/process/remux_orchestrator.ps1
```

Use flat files under `ops/pipeline/engine/process/` for the first split because
`AGENTS.md` and `MODULE_MAP.md` document active PowerShell modules as
`ops/pipeline/engine/<domain>/*.ps1`. Do not introduce nested
`process/encode/` or `process/remux/` folders unless the same change first
updates the architecture docs and loader tests to make that pattern official.

Before creating any file above, apply this file-creation gate:

- the file represents a named operational failure boundary, not just line-count
  reduction;
- the module has a concrete load-order position;
- the module has a targeted validation owner;
- rollback is possible by returning the wrapper to the pre-split body.

## Phase Files

Execute these in order. Do not parallelize phases that touch the loader,
wrappers, command builders, fallback paths, verification, or publish handoff.

| Phase | File | Purpose |
|---|---|---|
| Pre-work | `PRE_WORK.md` | Read required context, map current functions, freeze behavior evidence, and define stop conditions. |
| Target architecture | `TARGET_ARCHITECTURE.md` | Defines the target module boundaries, contracts, and ownership map. |
| Phase 1 | `PHASE_1_BASELINE_AND_CONTRACT_FREEZE.md` | Add or strengthen characterization coverage before moving behavior. |
| Phase 2 | `PHASE_2_REMUX_EXTRACTION.md` | Split the smaller remux path first while preserving `Do-Remux`. |
| Phase 3 | `PHASE_3_ENCODE_CORE_EXTRACTION.md` | Split encode preflight, attempt planning, command construction, and execution scaffolding. |
| Phase 4 | `PHASE_4_ENCODE_FALLBACK_VERIFICATION_SIZE.md` | Split encode fallback, verification, size guard, and publish handoff. |
| Phase 5 | `PHASE_5_DISPATCHER_LOAD_ORDER_CLEANUP.md` | Clean up module loading, dispatcher ownership, docs, summaries, and optional wrapper reduction. |
| Validation | `VALIDATION.md` | Gives the per-phase validation ladder and real-media evidence requirements. |
| Adversarial review | `ADVERSARIAL_REVIEW.md` | Failure-first review gate: assume the split broke something and audit accordingly. |
| Execution prompts | `EXECUTION_PROMPTS.md` | Goal-oriented prompts for executing each planning document with a fresh AI coding tool. |

## Dependency Graph

```text
PRE_WORK
  -> PHASE_1_BASELINE_AND_CONTRACT_FREEZE
      -> PHASE_2_REMUX_EXTRACTION
          -> PHASE_3_ENCODE_CORE_EXTRACTION
              -> PHASE_4_ENCODE_FALLBACK_VERIFICATION_SIZE
                  -> PHASE_5_DISPATCHER_LOAD_ORDER_CLEANUP
                      -> VALIDATION full pass
                      -> ADVERSARIAL_REVIEW final pass
```

Do not run Phase 2 and Phase 3 in parallel. They both affect shared wrapper
contracts and `MediaPipeline/module_loader.ps1`, so parallel branches create
startup-order and function-availability risks that are hard to review. Phase 4
depends on Phase 3 because fallback and verification use encode attempt
context.

## Definition Of Done

The whole split is not done until:

- `Do-Encode` and `Do-Remux` still behave the same for supported routes.
- All existing command/repro/progress/failure evidence is still emitted.
- The split files are named and placed according to `AGENTS.md` and
  `MODULE_MAP.md`.
- Module loader order is deterministic and tested.
- `pipeline_plan_executor.ps1` is either explicitly runtime-loaded before any
  live helper delegates to it, or command builders stay independent with
  parity fixtures proving no drift.
- Targeted PowerShell unit checks pass.
- Reliability regression checks pass.
- Tool integration checks pass when FFmpeg/MKVToolNix/PgsToSrt are available.
- Adversarial force-kill encode safety passes after encode execution or publish
  behavior is touched.
- Real-media validation is rerun for every phase that moves FFmpeg, mkvmerge,
  fallback, verification, size guard, publish, subtitle, audio, pending publish,
  or drain behavior.
- Generated summaries are refreshed through tooling.
- Change packets cover every touched file.

## Required Final Report For Each Phase

Every implementation phase should end with:

- change packet ID
- files touched
- public functions changed or confirmed unchanged
- validation commands and outcomes
- real-media validation status, if required
- strict change-packet coverage result
- unrelated dirty files not absorbed into the packet
- rollback plan
- adversarial review findings and fixes
