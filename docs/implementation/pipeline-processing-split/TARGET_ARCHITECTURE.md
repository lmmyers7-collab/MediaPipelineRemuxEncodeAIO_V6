# Target Architecture - Pipeline Processing Split

## Goal

Make the PowerShell processing path easier to troubleshoot by aligning file
boundaries with operational failure boundaries.

## Ownership Model

The split should preserve this ownership model:

| Layer | Owns | Must not own |
|---|---|---|
| `MediaPipeline.ps1` | Startup, flags, config projection validation, runtime state layout, top-level handoff to queue engine. | Encode/remux implementation details, FFmpeg argument decisions, mkvmerge argument decisions. |
| `queue/pipeline_engine.ps1` | Queue rounds, queue snapshots, pending retry before source discovery, local worker slot dispatch. | Per-file encode/remux internals. |
| `process/pipeline_processing.ps1` | Per-file route dispatch, progress preamble, counters, completed event. | FFmpeg attempts, mkvmerge mechanics, encode fallback internals, publish transaction internals. |
| `process/encode_*.ps1` | Encode stage mechanics. | Remux-specific muxing, queue scans, route decision policy. |
| `process/remux_*.ps1` | Remux stage mechanics. | Encode fallback policy except accepting a fallback call from encode. |
| `decide/*.ps1` | Codec/container/route/size decision policy. | Tool execution. |
| `audio/*.ps1` | Audio stream decisions and argument contributions. | Video route policy, publish. |
| `subtitles/*.ps1` | Subtitle preservation/conversion/filtering decisions. | Audio policy, publish. |
| `publish/*.ps1` | Publish, park, drain, sidecar carry-forward, manifest evidence. | Route decision, FFmpeg args. |

## Public Function Boundary

Keep these stable through the first split:

```powershell
function Do-Encode { ... }
function Do-Remux { ... }
function Invoke-MediaPipelineProcessFile { ... }
```

The preferred transition shape is:

```powershell
# entrypoints/MediaPipeline/encode.ps1
function Do-Encode {
    param($file, [bool]$isTV, $tvInfo)
    return Invoke-MediaPipelineEncode -File $file -IsTV:$isTV -TvInfo $tvInfo
}

# entrypoints/MediaPipeline/remux.ps1
function Do-Remux {
    param($file, [bool]$isTV, $tvInfo, [switch]$FallbackFromOversizedEncode, [switch]$FallbackFromDynamicHdrEncode)
    return Invoke-MediaPipelineRemux -File $file -IsTV:$isTV -TvInfo $tvInfo -FallbackFromOversizedEncode:$FallbackFromOversizedEncode -FallbackFromDynamicHdrEncode:$FallbackFromDynamicHdrEncode
}
```

Only perform this wrapper reduction after tests prove the new orchestrator
functions are loaded before the wrappers are invoked.

## Encode Target Modules

| Target file | Responsibility | Inputs | Outputs |
|---|---|---|---|
| `encode_context.ps1` | Build a normalized encode context object from current script state, source file, route plan, paths, subtitle result, dynamic HDR evidence, and policy values. | Source file, media kind, current script globals. | Context object. |
| `encode_preflight.ps1` | Scratch/source/tool readiness, Dynamic HDR preconditions, immediate block decisions. | Context. | Preflight result with `Ok`, `Reason`, `ErrorCode`, evidence. |
| `encode_attempt_plan.ps1` | Select primary, safe retry, CPU fallback, timeout, label, selected encoder, output temp path. | Context, preflight result, encoder descriptors. | Attempt plan. |
| `encode_command_builder.ps1` | Build FFmpeg argument lists or delegate to/reconcile with `pipeline_plan_executor.ps1`. | Attempt plan, stream/subtitle/audio decisions. | Native command representation and repro metadata. |
| `encode_execution.ps1` | Call `Invoke-FFmpegWithProgress`, capture exit/stderr, record attempt status, manage CPU encode mutex. | Attempt plan and command. | Execution result. |
| `encode_fallback.ps1` | Hardware safe retry, CPU fallback, Dynamic HDR preserve/remux fallback, oversized encode remux fallback. | Failed execution result, context. | Next attempt or terminal fallback result. |
| `encode_verification.ps1` | Duration, real video stream count, Dynamic HDR output verification, quality verification. | Encoded temp output, context. | Verification result. |
| `encode_size_guard.ps1` | Waste guard and post-encode size policy. | Encoded temp output, context. | Accept/reject/fallback decision. |
| `encode_publish.ps1` | Encode-specific call into `Complete-PipelineOutputPublish` and route evidence propagation. | Verified output, context. | Publish result and boolean success. |
| `encode_orchestrator.ps1` | High-level encode sequence only. | Source file, media kind, TV info. | Boolean success matching `Do-Encode`. |

## Remux Target Modules

| Target file | Responsibility | Inputs | Outputs |
|---|---|---|---|
| `remux_context.ps1` | Build a normalized remux context object from source, paths, route fallback flags, and current script state. | Source file, media kind, TV info, fallback flags. | Context object. |
| `remux_preflight.ps1` | Scratch checks, remux-safe codec policy, fallback eligibility, source video stream publish policy, dynamic HDR remux evidence. | Context. | Preflight result. |
| `remux_subtitle_plan.ps1` | Subtitle filtering, TX3G/BDPGS/VobSub sidecar candidate handling, mkvmerge subtitle track mapping readiness. | Context and probe facts. | Subtitle/remux stream plan. |
| `remux_ffmpeg_av_stage.ps1` | Build and execute the FFmpeg AV copy/transcode temp stage. | Context, subtitle/audio plan. | Temp AV result. |
| `remux_mkvmerge_args.ps1` | Build mkvmerge arguments, attachment preservation, title/global metadata, default-track flags. | Temp AV result, subtitle plan, context. | Argument list and repro metadata. |
| `remux_mkvmerge_stage.ps1` | Execute mkvmerge, classify warnings/errors/timeouts/stops, save repro evidence. | Argument list, context. | Mux result. |
| `remux_verification.ps1` | Confirm output exists, non-empty, and any required stream preservation checks pass. | Mux output, context. | Verification result. |
| `remux_publish.ps1` | Remux-specific call into `Complete-PipelineOutputPublish`. | Verified output, context. | Publish result and boolean success. |
| `remux_orchestrator.ps1` | High-level remux sequence only. | Source file, media kind, TV info, fallback flags. | Boolean success matching `Do-Remux`. |

## Shared Data Shape

Prefer explicit context/result objects over scattered script globals for new
module boundaries. Do not try to eliminate all existing script globals in the
first split. Instead:

```powershell
$context = [pscustomobject]@{
    SourceFile = $file
    IsTV = [bool]$isTV
    TvInfo = $tvInfo
    LocalInputPath = $localIn
    Paths = $paths
    OutputContainer = [string]$script:OutputContainer
    RouteReasonCode = [string]$script:CurrentRouteReasonCode
    RouteReason = [string]$script:CurrentRouteReason
}
```

The object above is illustrative, not complete. Before moving a stage, inventory
the exact current variables read after that stage and add them to the handoff
contract. Required examples include fallback switches, temp output path, route
intent reason code, selected encoder/backend, CPU/safe-retry flags, Dynamic HDR
working directory, subtitle sidecar candidates, audio transcode state,
`LastPublishResult`, `CurrentSizePolicyResult`, and scratch-retention flags.

Result objects should be easy to inspect in a failure report:

```powershell
[pscustomobject]@{
    Ok = $false
    Stage = 'encode-preflight'
    ErrorCode = 'ENCODE_INSUFFICIENT_SPACE'
    Reason = 'Insufficient scratch space before encode'
    SuggestedAction = 'Free space on the scratch volume or move LocalBase.'
    ReproPath = ''
}
```

Do not introduce new serialized state formats unless a phase explicitly needs
one and updates inventories/contracts.

## Module Loader Rules

When adding engine modules:

1. Add paths to `MediaPipeline/module_loader.ps1`.
2. Add names to the documented topological load order.
3. Load low-level helpers before orchestrators.
4. Load encode/remux helpers before the entrypoint wrapper slices call them.
5. Keep `PipelineProcessing.ps1` load order stable unless a test proves a
   change is required.
6. Add or update a targeted load-order test in Phase 1. This is mandatory for
   this split, not optional.
7. Run a full startup load path check after every loader edit so
   `MediaPipeline.ps1`, worker-child `-SingleFile`, and `-DrainPendingPushes`
   all see the same module graph.

`-DrainPendingPushes` loader validation must be non-mutating. Use a harness
that stops after module load/top-level dispatch proof, or stub
`Invoke-RetryPendingPushes` so the test fails if drain, scan, process, publish,
or filesystem mutation starts. Never run a live drain only to prove module load
order.

Do not rely on alphabetical discovery. This repo intentionally uses explicit
module loading so startup failures are deterministic.

## Relationship To `pipeline_plan_executor.ps1`

`pipeline_plan_executor.ps1` already owns plan-to-command functions such as:

- `New-PipelinePlanExecutorEncodeCommand`
- `New-PipelinePlanExecutorMkvmergeArgumentList`
- `New-PipelinePlanExecutorMp4RemuxArgumentList`
- `New-PipelinePlanExecutorNativeCommand`

Before adding `encode_command_builder.ps1` or `remux_mkvmerge_args.ps1`,
decide whether the new module:

- delegates to `pipeline_plan_executor.ps1`
- wraps it with encode/remux-specific context conversion
- extracts shared command-shape code from it
- or intentionally remains separate with parity tests

Command-builder authority rule:

- Live runtime command shape is authoritative for media behavior.
- Any plan-executor surface used for dry-run, tests, or planning must either
  call the same shared command-shape helper as live runtime code or prove exact
  argument-array parity against the live helper in the same change.
- Do not let `pipeline_plan_executor.ps1` and live encode/remux builders become
  parallel authorities. Temporary separate builders are allowed only inside one
  phase, with parity fixtures and a follow-up step that removes or delegates the
  duplicate path.

`pipeline_plan_executor.ps1` is currently a source file and test target, not
automatically a live runtime dependency unless `module_loader.ps1` loads it. If
an implementation delegates live encode/remux command construction to
`pipeline_plan_executor.ps1`, the same change must:

1. add it to `$engineModulePaths`;
2. add it to `$engineModuleLoadOrder` before any helper that calls it;
3. add a startup/load-order test proving those functions are available through
   the real `MediaPipeline.ps1` load path;
4. keep command-shape parity fixtures for live and plan-executor builders.

## Encode Attempt Result Contract

Before Phase 3 moves encode execution, define an explicit result object. The
fields below are required because fallback, verification, size guard, evidence,
and cleanup currently depend on values that are local/script-scoped in
`Do-Encode`.

```powershell
[pscustomobject][ordered]@{
    Ok                  = [bool]$success
    AttemptKind         = 'primary' # primary | safe_retry | cpu_fallback | forced_cpu
    SelectedEncoder     = [string]$encodePlan.SelectedEncoder
    EncoderKind         = [string]$encodePlan.EncoderKind
    ArgumentList        = @($ffArgs)
    OutputPath          = [string]$tempOut
    ProgressStage       = [string]$encodePlan.ProgressStage
    ProgressRoute       = [string]$encodePlan.ProgressRoute
    ReproStage          = [string]$encodePlan.ReproStage
    ReproPath           = [string]$script:LastFFmpegReproPath
    ExitCode            = [int]$script:LastFFmpegExit
    ErrorText           = [string]$script:LastFFmpegStderr
    AbortCode           = [string]$script:LastFFmpegAbortCode
    AbortReason         = [string]$script:LastFFmpegAbortReason
    TimeoutSeconds      = [int]$timeoutSeconds
    WorkingDirectory    = [string]$dynamicHdrWorkingDirectory
    CpuMutexRequired    = [bool]$cpuMutexRequired
    CpuMutexAcquired    = [bool]$cpuMutexAcquired
    DynamicHdrEvidence  = $script:CurrentDynamicHdrEvidence
    CleanupOwnsTempOut  = [bool]$true
}
```

If a field above is not available for a specific attempt, set it explicitly to
an empty value instead of omitting it. Fallback code must not read stale
script-scope variables when the result object has a current value.

## Troubleshooting Improvements Expected

After the split:

| Failure symptom | First file to inspect |
|---|---|
| Source skipped before tool execution | `pipeline_processing.ps1`, `encode_preflight.ps1`, or `remux_preflight.ps1` |
| Wrong encode command shape | `encode_command_builder.ps1` and `pipeline_plan_executor.ps1` |
| FFmpeg exits nonzero | `encode_execution.ps1` or `remux_ffmpeg_av_stage.ps1` |
| NVENC retry/CPU fallback behaves wrong | `encode_fallback.ps1` |
| Output too large | `encode_size_guard.ps1` |
| Dynamic HDR preserve fails | `encode_preflight.ps1`, `encode_fallback.ps1`, `encode_verification.ps1` |
| mkvmerge warning blocks publish | `remux_mkvmerge_stage.ps1` |
| Audio default track wrong after remux | `remux_mkvmerge_args.ps1` and `audio/audio.ps1` |
| Subtitle sidecar missing | `remux_subtitle_plan.ps1`, `encode_publish.ps1`, or `publish/publish_sidecars.ps1` |
| Completed output not visible | `encode_publish.ps1`, `remux_publish.ps1`, and `publish/*.ps1` |
