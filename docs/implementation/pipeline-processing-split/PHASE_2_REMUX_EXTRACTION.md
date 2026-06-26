# Phase 2 - Remux Extraction

## Goal

Split the smaller `Do-Remux` path first while preserving behavior and public
callers.

Remux is the better first extraction because it is smaller than encode and has
a clear sequence:

1. preflight and fallback safety
2. subtitle/audio plan
3. FFmpeg AV temp stage
4. mkvmerge final mux
5. verification
6. publish handoff

## Scope

In scope:

- Add remux helper modules as flat files under `ops/pipeline/engine/process/`
  using the `remux_<stage>.ps1` pattern.
- Keep `ops/pipeline/entrypoints/MediaPipeline/remux.ps1` as a thin public
  `Do-Remux` wrapper or reduce it gradually toward that shape.
- Add new modules to `MediaPipeline/module_loader.ps1`.
- Add/extend tests for remux helper functions and module load order.

Out of scope:

- Changing remux-safe codec policy.
- Changing subtitle preservation/drop policy.
- Changing audio transcode or default-track policy.
- Changing mkvmerge warning classification.
- Changing publish, pending publish, drain, or sidecar transaction behavior.

## Context Brief For Fresh Agents

`Do-Remux` currently lives in
`ops/pipeline/entrypoints/MediaPipeline/remux.ps1`. It can be called directly by
the per-file dispatcher or as a fallback from encode. It uses FFmpeg for the AV
stage and mkvmerge for final muxing. It then calls
`Complete-PipelineOutputPublish`.

This phase must keep `Do-Remux` callable by existing code. The safest first
step is to extract internal helper functions while keeping the original
function as the high-level sequence.

## Proposed Extraction Order

### Step 1: Context Builder

Create:

```text
ops/pipeline/engine/process/remux_context.ps1
```

Responsibility:

- Normalize function parameters and current script state into a context object.
- Include both public fallback switches:
  `FallbackFromOversizedEncode` and `FallbackFromDynamicHdrEncode`.
- Include source path, scratch path, output path, route reason, route reason
  code, output container, and media kind.
- Include fallback rejection state and scratch-retention decisions that encode
  depends on after calling `Do-Remux`.

Do not move behavior yet. Just create the object and use it internally.

### Step 2: Preflight

Create:

```text
ops/pipeline/engine/process/remux_preflight.ps1
```

Move only pre-tool checks:

- scratch-copy readiness
- scratch-space checks
- codec/policy fallback rejection
- dynamic HDR remux fallback rejection or evidence
- source video stream publish policy

Return a result object instead of directly continuing when practical:

```powershell
[pscustomobject]@{
    Ok = $true
    Stage = 'remux-preflight'
    Reason = ''
    ErrorCode = ''
}
```

If current behavior directly registers a failure and returns `$false`, preserve
that behavior. Do not make preflight "pure" if purity would change evidence.

### Step 3: Subtitle Plan

Create:

```text
ops/pipeline/engine/process/remux_subtitle_plan.ps1
```

Move subtitle routing/filtering preparation that is specific to remux. Keep
shared subtitle policy in `ops/pipeline/engine/subtitles/`.

Preserve:

- original subtitle preservation defaults
- conversion failure routing to review
- TX3G/BDPGS/VobSub sidecar candidate evidence
- mkvmerge track ID mapping behavior

### Step 4: FFmpeg AV Stage

Create:

```text
ops/pipeline/engine/process/remux_ffmpeg_av_stage.ps1
```

Move the FFmpeg AV temp stage:

- argument construction for stream-copy/audio-transcode temp output
- CPU encode mutex when audio transcode makes remux CPU-bound
- `Invoke-FFmpegWithProgress`
- stderr/error classification for `remux-av`
- repro command stage preservation

Preserve `remux_av` progress stage and `remux-av` repro/failure stage.

### Step 5: mkvmerge Arguments

Create:

```text
ops/pipeline/engine/process/remux_mkvmerge_args.ps1
```

Move argument construction only:

- attachments
- title/global metadata
- subtitle inputs
- default audio track flags
- destination output path

Before moving this, compare with `pipeline_plan_executor.ps1` functions:

- `New-PipelinePlanExecutorMkvmergeArgumentList`
- `New-PipelinePlanExecutorMp4RemuxArgumentList`

Do not create untested command-shape divergence. Add parity fixtures before
accepting this move, including attachments, subtitle inputs, audio default-track
flags, and MP4-remux argument shape where applicable.

### Step 6: mkvmerge Stage

Create:

```text
ops/pipeline/engine/process/remux_mkvmerge_stage.ps1
```

Move mkvmerge execution and result classification:

- `Invoke-MkvmergeWithProgress`
- timeout/stopped/warning classification
- stderr/stdout tail logging
- repro path recording
- `Register-SourceFailure` for mkvmerge failures

Preserve `remux_mux` progress stage and `remux-mkvmerge` failure/repro stage.

### Step 7: Verification

Create:

```text
ops/pipeline/engine/process/remux_verification.ps1
```

Move output existence/non-empty checks and any remux-specific stream
verification. If verification is currently minimal, keep it minimal and add
tests before widening it.

### Step 8: Publish Handoff

Create:

```text
ops/pipeline/engine/process/remux_publish.ps1
```

Move the remux-specific call to `Complete-PipelineOutputPublish`.

Before moving this block, add remux-specific publish-order characterization.
The test must stub or instrument `Complete-PipelineOutputPublish` and fail if
it can be called before these remux gates have succeeded:

- final remux output exists and is non-empty;
- remux duration verification has accepted the output;
- real source video-stream preservation checks have accepted the output;
- mkvmerge execution result has been accepted, including warning handling;
- subtitle/sidecar forwarding state is ready for the publish module.

Preserve:

- route = `remux`
- progress route = `remux`
- stage prefix = `remux`
- context text = `REMUX: `
- route reason and route reason code
- subtitle sidecar candidate forwarding
- pending-publish parking remains owned by `publish/*.ps1`
- publish is called only after output existence, duration, and video-stream
  preservation checks pass

### Step 9: Orchestrator

Create:

```text
ops/pipeline/engine/process/remux_orchestrator.ps1
```

Move the high-level sequence into `Invoke-MediaPipelineRemux`. Then reduce
`Do-Remux` to a wrapper when all targeted tests pass.

## Module Loader Changes

Add remux modules to `MediaPipeline/module_loader.ps1` in dependency order:

1. `remux_context.ps1`
2. `remux_preflight.ps1`
3. `remux_subtitle_plan.ps1`
4. `remux_ffmpeg_av_stage.ps1`
5. `remux_mkvmerge_args.ps1`
6. `remux_mkvmerge_stage.ps1`
7. `remux_verification.ps1`
8. `remux_publish.ps1`
9. `remux_orchestrator.ps1`

Do not rely on directory enumeration.

## Validation

Minimum after each extraction step:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-AudioPolicyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-SubtitleBuilderDecisionChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-MediaVerificationSafetyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-FFmpegProgressChecks.ps1
```

After the full remux extraction:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ReliabilityRegressionChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ToolIntegrationChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishSafetyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishOwnershipChecks.ps1
```

Add or update targeted fallback-switch tests before accepting this phase:

- `Do-Remux -FallbackFromOversizedEncode` preserves fallback rejection objects,
  route reason restoration, `LastPublishResult`, scratch-retention behavior,
  and boolean return semantics.
- `Do-Remux -FallbackFromDynamicHdrEncode` preserves Dynamic HDR rejection or
  preserve/remux evidence, route reason restoration, `LastPublishResult`,
  scratch-retention behavior, and boolean return semantics.
- Both fallback paths prove `KeepScratchInput` and parked/published output
  cleanup decisions remain coupled to the publish result, not inferred from a
  generic true/false return.

Real-media validation is required before accepting this phase because this
phase moves command construction, FFmpeg/mkvmerge execution, verification, and
publish handoff. Minimum proof:

- remux sample publishes and ffprobe confirms expected container and streams;
- source hash is unchanged before/after;
- subtitle-bearing sample preserves/converts sidecars according to current
  policy when subtitle planning moved;
- multi-audio sample preserves default-track and transcode behavior when audio
  or mkvmerge argument handoff moved;
- deferred publish sample parks and drains through manifest-backed flow when
  publish handoff moved.

## Exit Criteria

- Existing `Do-Remux` callers still work.
- `Do-Remux` returns the same boolean success/failure contract.
- Remux progress stages and failure stages are unchanged.
- mkvmerge command shape has test coverage or parity coverage.
- Remux publish handoff forwards the same sidecar and route evidence.
- `Do-Remux` fallback switches still protect oversized encode and Dynamic HDR
  fallback semantics.
- Publish cannot be called before remux verification passes.
- New modules are in explicit load order.
- Generated summaries are refreshed through tooling.

## Common Pitfalls

- Forgetting encode can call `Do-Remux` as fallback.
- Breaking fallback-specific reason codes while extracting preflight.
- Releasing CPU mutex only on success and leaking it on exception.
- Losing mkvmerge warning text that operators rely on.
- Moving shared subtitle/audio policy into remux instead of calling existing
  domain helpers.
- Treating "output file exists" as full remux correctness without stream
  preservation evidence.
