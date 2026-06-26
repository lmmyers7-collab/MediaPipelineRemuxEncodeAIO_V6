# Phase 3 - Encode Core Extraction

## Goal

Split the first half of `Do-Encode`: context, preflight, attempt planning,
command construction, and primary execution.

This phase should not yet reorganize every fallback and verification branch.
Those are high-risk enough to isolate in Phase 4.

## Scope

In scope:

- Add encode helper modules as flat files under `ops/pipeline/engine/process/`
  using the `encode_<stage>.ps1` pattern.
- Extract encode context/preflight.
- Extract encode attempt planning.
- Extract or wrap command construction.
- Extract primary FFmpeg execution handling.
- Preserve the current `Do-Encode` public function and return contract.

Out of scope:

- Rewriting route decisions.
- Rewriting encoder descriptor policy.
- Changing Dynamic HDR preserve/remux decisions.
- Changing CPU fallback semantics.
- Changing quality verification or size guard behavior.
- Changing publish handoff.

## Context Brief For Fresh Agents

`Do-Encode` currently lives in
`ops/pipeline/entrypoints/MediaPipeline/encode.ps1`. It is large because it
owns the primary encode attempt, safe retry, CPU fallback, Dynamic HDR logic,
size guard, verification, remux fallback, and publish handoff.

This phase extracts only the core path that prepares and launches encode
attempts. Keep fallback and verification in the old file until the core
extraction is stable.

## Proposed Extraction Order

### Step 1: Context Builder

Create:

```text
ops/pipeline/engine/process/encode_context.ps1
```

The context should include:

- source file object
- media kind and TV info
- scratch/local input path
- output container
- output paths
- route reason and code
- selected encoder/backend fields already available in script state
- dynamic HDR evidence pointer, if current behavior uses one
- relevant timeout/process-priority policy values
- temp output path and cleanup ownership
- route intent reason code, route reason, and route reason code
- CPU/safe-retry flags and selected encoder kind

Do not try to eliminate all script globals. The first split should create a
stable handoff object while leaving existing globals intact where needed.

### Step 2: Preflight

Create:

```text
ops/pipeline/engine/process/encode_preflight.ps1
```

Move:

- scratch/source readiness checks
- early no-tool/no-space checks
- Dynamic HDR preconditions that happen before command construction
- any preflight failure registration that blocks before FFmpeg starts

Preserve:

- existing error codes
- existing suggested actions
- failure classifications
- progress stage names

### Step 3: Attempt Plan

Create:

```text
ops/pipeline/engine/process/encode_attempt_plan.ps1
```

Move planning for:

- selected encoder
- hardware vs CPU kind
- safe retry label
- timeout
- temporary output path
- progress stage and progress route
- repro stage
- working directory
- process priority

The output should be an inspectable object. It should not execute FFmpeg.
It must carry every value later fallback/verification/size/publish code reads,
including selected encoder, encoder kind, progress route, repro stage, timeout,
working directory, output path, CPU mutex requirement, and Dynamic HDR metadata
paths.

### Step 4: Command Builder

Create:

```text
ops/pipeline/engine/process/encode_command_builder.ps1
```

Before adding this file, reconcile with:

- `ops/pipeline/engine/process/pipeline_plan_executor.ps1`
- `ops/pipeline/engine/decide/encode_policy.ps1`
- `ops/pipeline/engine/decide/encoder_descriptors.ps1`
- `ops/pipeline/engine/audio/audio.ps1`
- `ops/pipeline/engine/subtitles/*.ps1`

Acceptable approaches:

1. Wrapper only: convert encode context to an existing pipeline plan executor
   call.
2. Shared extraction: move duplicate command-shape code into one helper used by
   both current encode and plan executor tests.
3. Temporary parity: keep builders separate but add tests proving parity for
   representative plans.

Unacceptable approach:

- two independent FFmpeg argument builders with no parity test.

If the live command builder delegates to `pipeline_plan_executor.ps1`, add that
file to `module_loader.ps1` in this phase before the first live call. Unit tests
that dot-source the file directly are not enough.

### Step 5: Execution

Create:

```text
ops/pipeline/engine/process/encode_execution.ps1
```

Move:

- `Invoke-FFmpegWithProgress`
- stderr/exit capture handling
- attempt result recording
- repro command path handling
- CPU encode mutex only if the attempt plan already identifies the attempt as
  CPU-bound

Preserve:

- `FFmpegEncodeTimeoutSeconds`
- `FFmpegCpuEncodeTimeoutSeconds`
- progress route and stage names
- `encode`, `encode-safe-retry`, and `encode-cpu-fallback` route labels
- failure code classification

## Module Loader Changes

Add encode core modules in dependency order:

1. `encode_context.ps1`
2. `encode_preflight.ps1`
3. `encode_attempt_plan.ps1`
4. `encode_command_builder.ps1`
5. `encode_execution.ps1`

Do not add fallback/verification modules until Phase 4 unless this phase is
explicitly expanded and revalidated.

## Validation

Minimum during extraction:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-EncodeFlagPolicyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-EncoderRuntimeMatrixChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-EncoderCapabilityProbeChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-FFmpegProgressChecks.ps1
```

Because this phase moves FFmpeg execution handling, run:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-AdversarialForceKillEncodeChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerSlotChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerClaimLifecycleChecks.ps1
```

After full phase:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ReliabilityRegressionChecks.ps1
```

Real-media validation is required before accepting this phase because moving
command construction or FFmpeg execution can drift command shape even when the
intended change is mechanical. Minimum proof:

- normal encode sample publishes;
- output ffprobe confirms expected codec/profile/container/tags;
- source hash is unchanged before/after;
- repro command can be rerun or inspected with the same argument shape;
- forced CPU primary or CPU fallback path records the expected route evidence.

## Exit Criteria

- `Do-Encode` still owns or wraps the same public entry behavior.
- Primary encode command shape is unchanged for covered routes.
- FFmpeg execution still records repro evidence.
- CPU/hardware labels remain stable.
- Encoder descriptor tests still pass.
- Module loader order is explicit and tested.
- Any live dependency on `pipeline_plan_executor.ps1` is explicitly loaded
  through `module_loader.ps1`.

## Common Pitfalls

- Accidentally using a stale `$encodePlan` after fallback.
- Converting a script-scoped variable to local scope when later verification
  still reads the script variable.
- Changing output temp path naming and breaking cleanup or repro evidence.
- Losing Dynamic HDR working-directory behavior.
- Forgetting local worker child mode invokes the same `Do-Encode` path.
- Duplicating `pipeline_plan_executor.ps1` command logic without parity tests.
