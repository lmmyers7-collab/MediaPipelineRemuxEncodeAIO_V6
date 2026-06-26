# Execution Prompts - Pipeline Processing Split

Use these prompts one at a time from the repository root. Each prompt is meant
for a fresh AI coding tool and is intentionally under 4000 characters.

Do not use these prompts to skip the planning docs. The prompt tells the agent
which document to execute and which safety boundaries must remain in force.

## Recommended Execution Order

Use the prompts in this order:

1. Prompt 0 - Pre-Work.
2. Prompt 1 - Target Architecture Alignment.
3. Prompt 2 - Phase 1 Contract Freeze.
4. Prompt 7 - Validation Pass, scoped to Phase 1.
5. Prompt 8 - Adversarial Review, scoped to Phase 1.
6. Prompt 9 - Fix Review Findings, only if Phase 1 review finds issues.
7. Prompt 3 - Phase 2 Remux Extraction.
8. Prompt 7 - Validation Pass, scoped to Phase 2.
9. Prompt 8 - Adversarial Review, scoped to Phase 2.
10. Prompt 9 - Fix Review Findings, only if Phase 2 review finds issues.
11. Prompt 4 - Phase 3 Encode Core Extraction.
12. Prompt 7 - Validation Pass, scoped to Phase 3.
13. Prompt 8 - Adversarial Review, scoped to Phase 3.
14. Prompt 9 - Fix Review Findings, only if Phase 3 review finds issues.
15. Prompt 5 - Phase 4 Encode Fallback, Verification, Size, Publish.
16. Prompt 7 - Validation Pass, scoped to Phase 4.
17. Prompt 8 - Adversarial Review, scoped to Phase 4.
18. Prompt 9 - Fix Review Findings, only if Phase 4 review finds issues.
19. Prompt 6 - Phase 5 Dispatcher, Loader, Cleanup.
20. Prompt 7 - Validation Pass, scoped to the whole split.
21. Prompt 8 - Final Adversarial Review, scoped to the whole split.
22. Prompt 9 - Fix Review Findings, only if final review finds issues.

This order keeps architecture alignment before code movement, validates and
attacks each phase before the next one builds on it, and reserves final
whole-split validation for after loader and cleanup work.

## Prompt Design Basis

These prompts follow current coding-agent prompt patterns:

- Put the task and mode first.
- Provide explicit context files instead of vague background.
- State constraints and stop conditions before implementation details.
- Give the agent a way to verify its own work.
- Define what "done" means and what the final report must include.
- Keep each prompt focused enough that one assistant can complete and review it.

Primary references used while optimizing this sheet:

- OpenAI Codex prompting and best-practices docs:
  `https://developers.openai.com/codex/prompting`
- OpenAI Codex prompting guide:
  `https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide`
- OpenAI prompt-engineering guidance on clear front-loaded instructions,
  specificity, and output format:
  `https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-openai-api`
- Claude Code prompt-library patterns: outcome, reference artifact,
  measurable target, and self-verification:
  `https://code.claude.com/docs/en/prompt-library`

## Execution Contract For Every Prompt

When using any prompt below:

- Run exactly the named prompt scope. Do not continue into the next prompt
  unless the user explicitly starts it.
- Prefer implementation over proposal only when the prompt is an implementation
  phase. Review and validation prompts are read/check/report unless they
  explicitly authorize fixes.
- Ask at most one blocking question when required for safety. Otherwise inspect
  the repo and make the smallest defensible assumption.
- Keep edits scoped to the named phase and current change packet.
- If validation fails, diagnose and fix only issues caused by the current
  phase. If the failure is unrelated or unsafe to fix in scope, report it as a
  blocker.
- End with the same compact report shape: files changed, change packet,
  validation run, skipped validation, remaining risks, and next recommended
  prompt.

## Prompt 0 - Pre-Work

```text
Task mode: pre-work and characterization only.
You are executing the pre-work for the MediaPipelineRemuxEncodeAIO pipeline-processing split. Do not implement the split yet and do not continue into Phase 1.

Target doc:
docs/implementation/pipeline-processing-split/PRE_WORK.md

First read AGENTS.md, docs/CURRENT_PROJECT_STATE.md, docs/architecture/ARCHITECTURE.md, docs/architecture/MODULE_MAP.md, docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md, docs/testing/VALIDATION_LADDER_RUNBOOK.md, and the target doc.

Goal:
Build the baseline needed to split the PowerShell encode/remux path safely. Inventory public functions and call sites, freeze terminal outcome semantics, capture progress/failure/repro/route evidence, identify stop conditions, and record validation requirements. Do not move encode/remux behavior.

Hard rules:
- Source media remains read-only.
- Scratch isolation, pending publish, and drain ownership must not change.
- Do not edit generated docs manually.
- Do not create new runtime files unless PRE_WORK.md explicitly requires a characterization artifact.
- If you change docs/tests, create or continue the proper change packet and record touched paths.
- Stop if a requested inventory conflicts with AGENTS.md, docs/architecture/MODULE_MAP.md, or docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md.

Done when:
The current behavior inventory, terminal outcomes, evidence labels, stop conditions, and required validation are captured or confirmed in the target doc/change packet.

Verify:
Run only the checks required by PRE_WORK.md for the edits you make. If a check is unavailable or unsafe, record why. End with files touched, change packet ID, validation results, uncovered dirty files ignored, and remaining blockers.
```

## Prompt 1 - Target Architecture Alignment

```text
Task mode: architecture alignment and execution checklist only.
You are aligning implementation work to the target architecture for the MediaPipelineRemuxEncodeAIO pipeline-processing split. Do not move behavior and do not continue into Phase 1.

Target doc:
docs/implementation/pipeline-processing-split/TARGET_ARCHITECTURE.md

Also read:
docs/implementation/pipeline-processing-split/README.md
docs/implementation/pipeline-processing-split/PRE_WORK.md
AGENTS.md
docs/architecture/MODULE_MAP.md
docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md

Goal:
Translate the target module boundaries, public contracts, loader rules, command-builder authority, encode attempt result contract, and troubleshooting map into a concrete implementation checklist for the next phase. Verify that planned files belong under ops/pipeline/engine/process/ as flat encode_*.ps1 and remux_*.ps1 modules unless an authority doc is updated first.

Hard rules:
- Keep Do-Encode, Do-Remux, and Invoke-MediaPipelineProcessFile public contracts stable.
- Do not create nested process/encode or process/remux directories.
- Do not let pipeline_plan_executor.ps1 and live command builders become parallel authorities without parity fixtures.
- Drain loader validation must be non-mutating.
- Stop if the planned file placement requires changing architecture authority docs first.

Done when:
The target architecture has an executable checklist or confirmed no changes are needed, and any architecture conflict is recorded as a blocker.

Final report:
Summarize files changed, change packet, validation or doc checks run, unresolved architecture risks, and next recommended prompt.
```

## Prompt 2 - Phase 1 Contract Freeze

```text
Task mode: characterization tests and contract freeze.
You are executing Phase 1 of the pipeline-processing split. Do not move runtime encode/remux behavior and do not continue into Phase 2.

Target doc:
docs/implementation/pipeline-processing-split/PHASE_1_BASELINE_AND_CONTRACT_FREEZE.md

Before editing, read AGENTS.md, docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md, docs/testing/VALIDATION_LADDER_RUNBOOK.md, docs/implementation/pipeline-processing-split/PRE_WORK.md, docs/implementation/pipeline-processing-split/TARGET_ARCHITECTURE.md, and the target doc.

Goal:
Add or strengthen characterization coverage so later extraction phases fail fast on behavior drift. Protect module loader order, public function availability, route dispatch, command-shape parity, terminal outcome semantics, fallback switches, and evidence labels.

Required focus:
- Real startup load path exposes Do-Encode, Do-Remux, Invoke-MediaPipelineProcessFile, and new orchestrators when they exist.
- Worker-child -SingleFile and -DrainPendingPushes use the same module graph.
- Drain validation is non-mutating and stops before Invoke-RetryPendingPushes.
- Do-Remux fallback switches preserve rejection objects, route reason restoration, LastPublishResult, KeepScratchInput, and return semantics.
- Evidence freeze uses fixtures or structured assertions, not only rg scans.
- Stop if a required characterization would need real media or live drain mutation; record that as a validation gap instead.

Done when:
Phase 1 tests or fixtures can fail on public contract, command-shape, loader, fallback, or evidence drift before any behavior is moved.

Verify:
Run the Phase 1 targeted tests from the doc. Run reliability regression if tests changed. Update the change packet with touched files, validation, rollback, and skipped checks.

Final report:
List tests added/changed, files touched, validation outcomes, uncovered dirty files ignored, and whether Phase 2 is safe to start.
```

## Prompt 3 - Phase 2 Remux Extraction

```text
Task mode: behavior-preserving remux extraction.
You are executing Phase 2 of the pipeline-processing split. Split remux behavior only. Do not start encode extraction and do not continue into Phase 3.

Target doc:
docs/implementation/pipeline-processing-split/PHASE_2_REMUX_EXTRACTION.md

Before editing, read AGENTS.md, docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md, docs/testing/VALIDATION_LADDER_RUNBOOK.md, docs/implementation/pipeline-processing-split/PRE_WORK.md, docs/implementation/pipeline-processing-split/TARGET_ARCHITECTURE.md, docs/implementation/pipeline-processing-split/PHASE_1_BASELINE_AND_CONTRACT_FREEZE.md, and the target doc.

Goal:
Extract Do-Remux internals into flat ops/pipeline/engine/process/remux_*.ps1 modules while preserving the public Do-Remux wrapper and all current behavior.

Hard rules:
- Do not change remux-safe codec policy, subtitle policy, audio policy, mkvmerge warning classification, publish, pending publish, drain, or sidecar transactions.
- Add every new module to MediaPipeline/module_loader.ps1 in explicit dependency order.
- Preserve remux_av, remux_mux, remux-mkvmerge, route=remux, progress route, route reasons, sidecar forwarding, and fallback evidence.
- Before moving remux_publish.ps1, add publish-order characterization that fails if Complete-PipelineOutputPublish can run before output existence, duration verification, video-stream preservation, accepted mkvmerge result, and sidecar readiness.
- Revalidate Do-Remux -FallbackFromOversizedEncode and -FallbackFromDynamicHdrEncode after extraction.
- Stop and report a blocker if command shape, fallback behavior, or publish order cannot be proven equivalent.

Done when:
Do-Remux remains the public wrapper, remux internals are split only along the target boundaries, loader order is explicit, and tests prove behavior/evidence parity.

Verify:
Run the Phase 2 targeted checks after each extraction step and the full remux validation set before completion. Real-media validation is required before release acceptance.

Final report:
List extracted modules, wrapper status, validation outcomes, real-media status, rollback path, and whether Phase 2 is ready for validation/adversarial review.
```

## Prompt 4 - Phase 3 Encode Core Extraction

```text
Task mode: behavior-preserving encode core extraction.
You are executing Phase 3 of the pipeline-processing split. Work only on encode context, preflight, attempt planning, command construction, and FFmpeg execution scaffolding. Do not continue into Phase 4.

Target doc:
docs/implementation/pipeline-processing-split/PHASE_3_ENCODE_CORE_EXTRACTION.md

Before editing, read AGENTS.md, docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md, docs/testing/VALIDATION_LADDER_RUNBOOK.md, docs/implementation/pipeline-processing-split/PRE_WORK.md, docs/implementation/pipeline-processing-split/TARGET_ARCHITECTURE.md, docs/implementation/pipeline-processing-split/PHASE_1_BASELINE_AND_CONTRACT_FREEZE.md, docs/implementation/pipeline-processing-split/PHASE_2_REMUX_EXTRACTION.md, Phase 1/2 results, and the target doc.

Goal:
Move the first half of Do-Encode into flat ops/pipeline/engine/process/encode_*.ps1 modules while preserving Do-Encode as the public callable contract.

Hard rules:
- Do not move fallback, verification, size guard, or publish unless the target doc explicitly reaches that boundary.
- Keep FFmpeg argument shape identical unless a behavior-change plan is opened separately.
- Reconcile encode_command_builder.ps1 with pipeline_plan_executor.ps1. Either delegate to shared command-shape code or add parity fixtures proving exact argument-array parity.
- Preserve progress route, repro stage, selected encoder/backend evidence, timeout behavior, stderr capture, and CPU mutex handling.
- Use an explicit encode attempt result object. Do not let fallback later read stale script-scope values.
- Stop and report a blocker if command-builder authority or attempt-result handoff is ambiguous.

Done when:
Do-Encode remains callable, encode core helpers are loaded in deterministic order, command shape is proven unchanged, and execution evidence remains stable.

Verify:
Run Phase 3 targeted command, encoder, progress, and reliability checks as specified. Record real-media validation as required for command/execution movement.

Final report:
List extracted modules, command-builder decision, attempt-result shape, validation outcomes, real-media status, and whether Phase 3 is ready for review.
```

## Prompt 5 - Phase 4 Encode Fallback, Verification, Size, Publish

```text
Task mode: high-risk behavior-preserving encode terminal-path extraction.
You are executing Phase 4 of the pipeline-processing split. Touch only encode fallback, verification, size guard, and publish handoff as directed by the target doc. Do not continue into Phase 5.

Target doc:
docs/implementation/pipeline-processing-split/PHASE_4_ENCODE_FALLBACK_VERIFICATION_SIZE.md

Before editing, read AGENTS.md, docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md, docs/testing/VALIDATION_LADDER_RUNBOOK.md, docs/implementation/pipeline-processing-split/PRE_WORK.md, docs/implementation/pipeline-processing-split/TARGET_ARCHITECTURE.md, docs/implementation/pipeline-processing-split/VALIDATION.md, Phase 1-3 results, and the target doc.

Goal:
Extract hardware safe retry, CPU fallback, Dynamic HDR preserve/remux fallback, post-encode verification, quality checks, size/waste guard, and encode publish handoff without changing acceptance, rejection, cleanup, or evidence semantics.

Hard rules:
- Publish cannot run before output exists, duration verification, video-stream preservation, Dynamic HDR verification when applicable, quality verification, and size/waste guard acceptance.
- Preserve oversized encode remux fallback, Dynamic HDR remux fallback, route labels, route reason codes, LastPublishResult, KeepScratchInput, cleanup behavior, and source failure evidence.
- CPU mutex must release on success, failure, timeout, and exception.
- Pending publish remains owned by publish modules.
- Partial outputs must not be accepted after failures or force-kill scenarios.
- Stop and report a blocker if any terminal success/failure path cannot be mapped to the pre-split outcome matrix.

Done when:
Fallback, verification, size guard, and publish handoff are split without changing terminal outcomes, evidence, cleanup, or pending-publish behavior.

Verify:
Run all Phase 4 targeted checks, pending publish checks, adversarial force-kill encode, reliability regression, tool integration, and required real-media validation. Record any missing sample as an unresolved release gap.

Final report:
List extracted modules, terminal outcomes proven, validation outcomes, real-media status, rollback path, and whether Phase 4 is ready for review.
```

## Prompt 6 - Phase 5 Dispatcher, Loader, Cleanup

```text
Task mode: consolidation and cleanup only.
You are executing Phase 5 of the pipeline-processing split. This is consolidation only, not a behavior refactor. Do not broaden the split.

Target doc:
docs/implementation/pipeline-processing-split/PHASE_5_DISPATCHER_LOAD_ORDER_CLEANUP.md

Before editing, read AGENTS.md, docs/implementation/pipeline-processing-split/PRE_WORK.md, docs/implementation/pipeline-processing-split/TARGET_ARCHITECTURE.md, docs/implementation/pipeline-processing-split/VALIDATION.md, docs/implementation/pipeline-processing-split/ADVERSARIAL_REVIEW.md, all prior phase results, and the target doc.

Goal:
Clean up transition scaffolding after remux and encode internals are split and validated. Confirm entrypoint wrappers are thin or justified, pipeline_processing.ps1 remains a dispatcher, module_loader.ps1 has deterministic load order, and duplicate active implementations are removed only after tests prove they are unused.

Hard rules:
- Do not rename Do-Encode, Do-Remux, or Invoke-MediaPipelineProcessFile.
- Do not change queue behavior, Python orchestration, WebView controls, media policy, publish, or drain.
- Do not hand-edit generated summaries.
- Drain-only module graph proof must be non-mutating; do not run live -DrainPendingPushes as a loader check.
- Stop if duplicate implementation removal cannot be proven safe by callers/tests.

Done when:
Wrappers, dispatcher, loader order, generated summaries, inventories, and duplicate-code cleanup are all consistent with prior validated phases.

Verify:
Run full required validation from docs/implementation/pipeline-processing-split/VALIDATION.md, refresh generated summaries through tooling after source edits, update inventories/docs where required, and run adversarial review before final acceptance.

Final report:
List cleanup performed, wrapper/dispatcher status, generated context status, validation outcomes, real-media status, and final review readiness.
```

## Prompt 7 - Validation Pass

```text
Task mode: validation only.
You are performing the validation pass for the MediaPipelineRemuxEncodeAIO pipeline-processing split. Validate only; do not implement new behavior unless fixing a failed validation in the current change scope.

Target doc:
docs/implementation/pipeline-processing-split/VALIDATION.md

Also read AGENTS.md, docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md, docs/testing/VALIDATION_LADDER_RUNBOOK.md, docs/implementation/pipeline-processing-split/README.md, and the phase document for the work being validated.

Goal:
Run the smallest safe validation rung that matches the touched behavior, then escalate where the target doc requires it. Confirm targeted PowerShell checks, command-shape parity, publish-order characterization, fallback characterization, pending publish checks, reliability regression, tool integration, force-kill safety, generated summaries, and change-packet coverage as applicable.

Hard rules:
- A clean unit test does not prove FFmpeg/mkvmerge media behavior.
- Any moved FFmpeg, mkvmerge, fallback, verification, size guard, publish, subtitle, audio, pending publish, or drain behavior requires real-media validation before release acceptance.
- Drain loader validation must be non-mutating.
- Do not absorb unrelated dirty files into the packet.
- Stop if a required validation would mutate source media, parked pending-publish output, or unrelated dirty files.

Done when:
The phase has a clear pass/fail validation record, including whether it is release-ready or blocked by missing real-media evidence.

Output:
Report exact commands, pass/fail results, skipped checks with reasons, real-media evidence or missing-sample gaps, packet status, and whether the phase is release-ready.
```

## Prompt 8 - Adversarial Review

```text
Task mode: adversarial review only.
You are performing an adversarial review of the pipeline-processing split. Do not implement unless the user explicitly asks for fixes after this review.

Target doc:
docs/implementation/pipeline-processing-split/ADVERSARIAL_REVIEW.md

Also read AGENTS.md, docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md, docs/implementation/pipeline-processing-split/VALIDATION.md, docs/implementation/pipeline-processing-split/README.md, the phase documents that were executed, and the changed source/tests/docs.

Mindset:
Assume the split failed. Find unsafe assumptions, behavior drift, broken startup, lost evidence, command-shape changes, fallback mistakes, premature publish, source/scratch safety violations, pending publish/drain drift, weak validation, bad file placement, and unclear rollback.

Required focus:
- Source safety, scratch isolation, pending publish, and no source mutation.
- Do-Encode, Do-Remux, and Invoke-MediaPipelineProcessFile public contracts.
- module_loader.ps1 ordering and worker-child/drain module graph.
- pipeline_plan_executor.ps1 command-builder parity.
- FFmpeg/mkvmerge argument shape.
- safe retry, CPU fallback, Dynamic HDR, oversized encode remux fallback.
- verification/publish gates, progress stages, failure codes, repro labels, route reason codes, and operator evidence.
- Treat missing proof as a finding. Do not give credit for intent.

Output:
Start with findings ordered by severity in the requested table. Then include stop-ship summary, missing validation, plan logic risks, AI execution risks, recommended fixes, and final verdict.
```

## Prompt 9 - Fix Review Findings

```text
Task mode: scoped review-finding fixes.
You are fixing review findings against the pipeline-processing split. Implement only the fixes requested by the user, and keep the scope bounded to the planning pack or current implementation phase.

Inputs:
- The latest review findings from the user.
- docs/implementation/pipeline-processing-split/README.md
- The phase doc or docs named in the review.
- docs/implementation/pipeline-processing-split/VALIDATION.md
- docs/implementation/pipeline-processing-split/ADVERSARIAL_REVIEW.md

Goal:
Turn each accepted finding into a concrete doc, test, or implementation correction. Do not broaden the split. Do not silently change media behavior. If a finding implies a behavior change, stop and write a separate behavior-change plan instead of folding it into a refactor.

Hard rules:
- Preserve source safety, scratch isolation, pending publish ownership, and public contracts.
- Keep module placement under active repo rules.
- Update change packet touched paths and validation evidence.
- Re-run targeted validation that proves the finding is fixed.
- If dirty worktree files are unrelated, ignore them and report them separately.
- Stop if the requested fix requires a behavior change outside the current phase.

Done when:
Each accepted finding is either fixed with validation evidence or explicitly left open with a blocker reason.

Output:
List each finding fixed, files changed, validation run, remaining gaps, change packet ID, and any validation deliberately skipped.
```
