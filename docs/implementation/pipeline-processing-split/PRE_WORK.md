# Pre-Work - Pipeline Processing Split

## Goal

Prepare for a behavior-preserving split of the encode/remux processing path.
This phase should produce evidence, not production behavior changes.

## Required Reads

Read these before touching PowerShell source:

1. `AGENTS.md`
2. `docs/DOCS_INDEX.md`
3. `docs/CURRENT_PROJECT_STATE.md`
4. `docs/architecture/ARCHITECTURE.md`
5. `docs/architecture/MODULE_MAP.md`
6. `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
7. `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
8. `docs/generated/FEATURE_FILE_MAP.md`
9. `docs/generated/PIPELINE_MAP.md`
10. Generated summaries for every source file that will be opened.

Minimum generated summaries for this work:

- `docs/generated/summaries/ops/pipeline/entrypoints/MediaPipeline.ps1.md`
- `docs/generated/summaries/ops/pipeline/entrypoints/MediaPipeline/encode.ps1.md`
- `docs/generated/summaries/ops/pipeline/entrypoints/MediaPipeline/remux.ps1.md`
- `docs/generated/summaries/ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/process/pipeline_processing.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/process/pipeline_plan_executor.ps1.md`
- `docs/generated/summaries/ops/pipeline/engine/queue/pipeline_engine.ps1.md`

If a summary is missing or stale, open the source only after noting why.

## Stop Conditions

Stop and report instead of editing when any of these are true:

- The change requires source-media deletion or overwrite.
- The change requires changing route decisions, codec policy, audio policy,
  subtitle policy, pending publish safety, or drain semantics in the same step
  as an extraction.
- The current worktree contains user changes in the same files and you cannot
  distinguish them from the planned extraction.
- Targeted baseline tests fail before the extraction and the failure is not
  clearly unrelated.
- The split requires moving logic into WebView, Tauri, or Python API ownership.
- A new file would need to live outside `ops/pipeline/engine/<domain>/` or the
  existing entrypoint slice area without an architecture explanation.

## Current Behavior Inventory

Before extraction, capture this inventory in the phase notes or change packet:

```powershell
rg -n "function (Do-Encode|Do-Remux|Invoke-MediaPipelineProcessFile|Invoke-MediaPipelineRun)" `
  ops/pipeline/entrypoints/MediaPipeline.ps1 `
  ops/pipeline/entrypoints/MediaPipeline/encode.ps1 `
  ops/pipeline/entrypoints/MediaPipeline/remux.ps1 `
  ops/pipeline/engine/process/pipeline_processing.ps1 `
  ops/pipeline/engine/queue/pipeline_engine.ps1

rg -n "Invoke-FFmpegWithProgress|Invoke-MkvmergeWithProgress|Complete-PipelineOutputPublish|Register-SourceFailure|Write-PipelineEvent|Set-ProgressStage" `
  ops/pipeline/entrypoints/MediaPipeline/encode.ps1 `
  ops/pipeline/entrypoints/MediaPipeline/remux.ps1 `
  ops/pipeline/engine/process/pipeline_processing.ps1

rg -n "Do-Encode|Do-Remux|New-PipelinePlanExecutorEncodeCommand|New-PipelinePlanExecutorMkvmergeArgumentList|New-PipelinePlanExecutorMp4RemuxArgumentList" `
  ops/pipeline
```

Save the output summary in the implementation notes. Do not paste huge command
output into active docs unless it is curated and durable.

## Public Contracts To Freeze

Freeze these before the first move:

| Contract | Current expectation |
|---|---|
| `Do-Encode $file $isTV $tvInfo` | Returns truthy on successful publish or accepted route completion, false on handled failure. Records source failures for blocked paths. May call `Do-Remux` for Dynamic HDR preserve/remux and oversized encode fallback. |
| `Do-Remux $file $isTV $tvInfo -FallbackFromOversizedEncode -FallbackFromDynamicHdrEncode` | Returns truthy on successful publish or accepted route completion, false on handled failure. Both fallback switches are public contract because encode paths call them. Preserve fallback-specific route reason restoration, rejection evidence objects, scratch-retention behavior, and pending-publish handoff. |
| `Invoke-MediaPipelineProcessFile` | Probes and routes a source, sets progress, dispatches to `Do-Encode` or `Do-Remux`, increments counters, writes completed event. |
| `Invoke-MediaPipelineRun` | Runs queue rounds and repeats or exits according to engine plan. |
| `MediaPipeline/module_loader.ps1` | Dot-sources engine modules into the shared entrypoint scope in deterministic order. |
| `MediaPipeline.ps1` single-file mode | Processes exactly one source path through the same per-file processing function and writes worker child result evidence when required. |

If a phase needs to change one of these contracts, split that into a separate
design decision and validation plan.

### Terminal Outcome Matrix

Freeze these return and cleanup semantics before moving encode/remux behavior.
Do not reduce them to a bare boolean in new orchestrators.

| Outcome | Public return | Required publish/result state | Cleanup rule |
|---|---:|---|---|
| Existing final output accepted or skipped | `$true` | `LastPublishResult.Ok = true`, `PublishState = published`, `PublishMode = existing-output` | Scratch copy may be cleaned normally after sidecar/export handling. Do not delete existing final output. |
| Immediate publish succeeds | `$true` | `LastPublishResult.Ok = true`, `PublishState = published`, `PublishMode = immediate`, `DeleteLocalOutput = true` | Delete local completed output only after publish result explicitly requests it. |
| Output is parked for pending publish/deferred publish | `$true` | `LastPublishResult.Ok = true`, `PublishState = pending_publish`, publish mode reflects deferred/retry/output-space reason | Do not delete parked payload. Let pending publish modules own manifest, drain, and cleanup. |
| Oversized encode remux fallback publishes | `$true` | `Do-Remux -FallbackFromOversizedEncode` returns true and `LastPublishResult` describes accepted remux publish/park state | Encode must honor `KeepScratchInput` and delete only rejected encode temp output. |
| Dynamic HDR preserve/remux fallback publishes | `$true` | `Do-Remux -FallbackFromDynamicHdrEncode` returns true and Dynamic HDR fallback evidence is recorded | Encode must stop its own path without publishing the rejected encode output. |
| Tool, verification, size, subtitle, audio, or policy failure | `$false` | Source failure state registered with current stage/error/suggested action; `LastPublishResult` absent or failed | Do not publish. Cleanup only temp outputs/scratch according to existing policy. |
| Publish attempt fails before a pending-publish manifest is accepted | `$false` | `LastPublishResult.Ok = false` or absent, with publish failure evidence from `Complete-PipelineOutputPublish` | Do not delete local or parked output unless publish result explicitly permits it. |
| Publish attempt cannot complete final move but is accepted as pending publish | `$true` | `LastPublishResult.Ok = true`, `PublishState = pending_publish`, publish mode reflects deferred/retry/output-space reason | Do not delete parked payload. Let pending publish modules own manifest, drain, and cleanup. |
| Unexpected exception | `$false` | Source failure registered with `*-exception` stage and stack/log evidence | Do not publish. Cleanup temp/scratch only through existing finally semantics. |

For every moved block, add or update tests that assert the public boolean,
`LastPublishResult`, `PublishState`, `PublishMode`, `DeleteLocalOutput`, and
`KeepScratchInput` remain coupled exactly as they are before the split.

## Evidence To Freeze

For every extracted block, preserve:

- log text that tests or operator docs rely on
- `Set-ProgressStage` stage names and route labels
- `Write-PipelineEvent` event types, status names, stage names, and route names
- `Register-SourceFailure` stage names, classifications, error codes, repro
  paths, and suggested-action wording unless intentionally improved
- repro-command stage labels such as `encode`, `encode-cpu`,
  `remux-av`, and `remux-mkvmerge`
- cleanup behavior for temp outputs, scratch copies, sidecars, and parked
  pending publish payloads
- CPU/GPU mutex acquire/release behavior
- route reason code and route reason propagation into completed/publish records
- `Do-Remux` fallback switch behavior for oversized encode and Dynamic HDR
  preserve/remux fallback
- command argument array shape and repro command content for FFmpeg, mkvmerge,
  and MP4 remux cases
- runtime loader availability for every helper used by `Do-Encode`,
  `Do-Remux`, and worker-child `-SingleFile`

## Change Packet Setup

Each implementation slice should create or continue a change packet:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.change_control.new_change `
  --title "Short title" --type refactor --risk high --version-target 2026.06.04.001
```

Record touched files as they change:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.change_control.record_change_touch `
  MP-CHANGE-YYYY-MMDD-### path/to/file --area pipeline `
  --note "Why this file changed."
```

Use `risk high` for implementation phases that touch FFmpeg, remux, encode,
subtitle, audio, publish, drain, source/scratch/output movement, or process
lifecycle behavior.

## Baseline Validation Before Extraction

Run the smallest baseline that matches the phase. For the first implementation
phase, run at least:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PipelineProcessingPreflightChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-MediaRouteSelectionChecks.ps1
```

If those fail before any changes, stop. Do not start extraction on a red
baseline unless the failure is independently understood and documented.

Also identify whether `pipeline_plan_executor.ps1` is only a test helper or will
become a live runtime dependency. If any live helper delegates to it, update
`module_loader.ps1` and add load-order coverage in the same implementation
slice before the delegated call is introduced.

## AI Executor Notes

Work in small slices:

1. Read summaries.
2. Open only the source files needed for the slice.
3. Add or strengthen characterization tests before moving logic.
4. Extract one function group.
5. Run targeted validation.
6. Record the touched file.
7. Refresh generated summaries for changed source.
8. Run adversarial review on the slice.

Do not run broad refactors, formatting sweeps, or variable-renaming cleanups in
the same change. Those make behavior preservation harder to prove.
