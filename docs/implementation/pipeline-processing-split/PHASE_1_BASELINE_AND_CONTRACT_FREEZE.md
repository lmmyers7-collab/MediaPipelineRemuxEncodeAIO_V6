# Phase 1 - Baseline And Contract Freeze

## Goal

Create enough characterization coverage and written inventory to make later
extractions behavior-preserving.

This phase may add tests and documentation. It should avoid changing runtime
media behavior.

## Scope

In scope:

- Inventory current public functions and call sites.
- Strengthen tests around module load order, public function availability, and
  command-shape parity.
- Add focused characterization checks for encode/remux route dispatch when
  existing tests are too broad.
- Record current progress stages, failure stages, and repro labels used by
  encode/remux.
- Freeze exact fallback switch behavior for `Do-Remux`.

Out of scope:

- Moving encode/remux implementation.
- Changing FFmpeg or mkvmerge arguments.
- Changing route decisions.
- Changing subtitle, audio, publish, pending publish, or drain behavior.

## Context Brief For Fresh Agents

The repo currently keeps the large encode/remux functions in entrypoint child
files:

- `ops/pipeline/entrypoints/MediaPipeline/encode.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/remux.ps1`

The dispatcher in `ops/pipeline/engine/process/pipeline_processing.ps1` calls
`Do-Encode` or `Do-Remux`. The main entry script loads engine modules first
through `module_loader.ps1`, then dot-sources the entrypoint child files.

Before extracting code, prove the current public functions are loaded and prove
the tests know the current command/failure evidence shape.

## Tasks

1. Confirm baseline worktree state.

   ```powershell
   git status --short
   ```

   Do not absorb unrelated dirty files into the phase packet.

2. Read generated summaries for all source files in this phase.

3. Capture current function/call inventory.

   ```powershell
   rg -n "function (Do-Encode|Do-Remux|Invoke-MediaPipelineProcessFile|Invoke-MediaPipelineRun)" ops/pipeline
   rg -n "Do-Encode|Do-Remux" ops/pipeline tests docs
   ```

4. Capture evidence labels used by encode/remux.

   ```powershell
   rg -n "Set-ProgressStage|Write-PipelineEvent|Register-SourceFailure|ReproStage|ErrorCode|RouteReasonCode" `
     ops/pipeline/entrypoints/MediaPipeline/encode.ps1 `
     ops/pipeline/entrypoints/MediaPipeline/remux.ps1 `
     ops/pipeline/engine/process/pipeline_processing.ps1
   ```

5. Add or strengthen module load order and public function availability
   coverage. This is mandatory for this split because later phases add many
   runtime-loaded files.

   The test must prove:

   - every new module path is present in `$engineModulePaths`;
   - every new module name appears exactly once in `$engineModuleLoadOrder`;
   - no manifest/load-order count drift exists;
   - `Do-Encode`, `Do-Remux`, `Invoke-MediaPipelineProcessFile`,
     `Invoke-MediaPipelineEncode`, and `Invoke-MediaPipelineRemux` are available
     through the real startup load path when those helpers exist;
   - worker-child `-SingleFile` and `-DrainPendingPushes` use the same module
     graph.

   Validate `-DrainPendingPushes` with a non-mutating load-path harness only.
   The test must prove the drain-only startup path loads the same module graph
   and exits before `Invoke-RetryPendingPushes` or any scan/process/publish
   mutation can run. Do not run a live drain just to prove loader behavior.

6. Check command builder parity coverage in
   `Invoke-PipelinePlanExecutorChecks.ps1`. If it does not pin command
   structures needed by the extraction, add cases there instead of creating a
   parallel test surface.

   Required fixture families:

   - primary encode command;
   - safe hardware retry command;
   - CPU fallback command;
   - Dynamic HDR preserve encode command;
   - remux FFmpeg AV stage command;
   - mkvmerge remux command with attachments/subtitles;
   - MP4 remux command when that route is supported.

7. Freeze the exact `Do-Remux` fallback contract:

   ```powershell
   function Do-Remux {
       param(
           $file,
           [bool]$isTV,
           $tvInfo,
           [switch]$FallbackFromOversizedEncode,
           [switch]$FallbackFromDynamicHdrEncode
       )
   }
   ```

   Characterization must cover fallback-specific rejection evidence,
   `LastRemuxFallbackRejection`, `LastDynamicHdrRemuxFallbackRejection`,
   route reason restoration, and scratch retention.

8. Add or strengthen route dispatch characterization.

   Preferred target:

   - `ops/pipeline/tests/Unit/Invoke-PipelineProcessingPreflightChecks.ps1`
   - `ops/pipeline/tests/Unit/Invoke-PipelineProcessingSourceProbeChecks.ps1`
   - `ops/pipeline/tests/Unit/Invoke-MediaRouteSelectionChecks.ps1`

9. Run targeted tests.

10. Record the phase results in the change packet.

## Required Characterization Tests

Add or strengthen these tests before moving implementation code. They are not
optional suggestions because later phases rely on them as drift detectors.

| Test | Why |
|---|---|
| Module loader exposes every required helper before `Invoke-MediaPipelineRun`. | Prevents silent startup failures after adding new modules. |
| `Do-Encode` and `Do-Remux` are available after `MediaPipeline.ps1` startup load path. | Preserves dispatcher contract. |
| `Do-Remux` fallback switches retain behavior from encode call sites. | Protects oversized encode and Dynamic HDR fallback. |
| `pipeline_processing.ps1` dispatches encode routes only to `Do-Encode` and remux routes only to `Do-Remux`. | Detects accidental route inversion during extraction. |
| `pipeline_plan_executor.ps1` still builds the expected encode/remux native command shape. | Prevents duplicate command-builder drift. |
| Known progress stages and failure stages remain in source. | Catches accidental evidence rename. |
| Drain-only startup loads the same module graph without invoking pending-publish drain mutation. | Proves load order without accidentally moving parked files. |

Avoid tests that require real media unless this phase intentionally moves to
Rung 7 validation.

For progress stages, route labels, failure codes, event names, repro labels,
and completed/failure evidence fields, build fixture-based snapshots or
structured assertions from the current source/tests. A scan-only `rg` check is
acceptable for discovery, but it is not enough for the phase gate because it
cannot prove the evidence shape consumers depend on.

## Validation

Minimum:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PipelineProcessingPreflightChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PipelineProcessingSourceProbeChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-MediaRouteSelectionChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-FFmpegProgressChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerSlotChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerClaimLifecycleChecks.ps1
```

If tests are added or changed, also run:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ReliabilityRegressionChecks.ps1
```

Finish with change-packet validation:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py `
  mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

## Exit Criteria

- Public contracts are documented in the phase notes.
- Tests fail if `Do-Encode` or `Do-Remux` are not available.
- Tests fail if `Do-Remux` fallback switches or fallback evidence regress.
- Tests fail if the command builder shape drifts for covered routes.
- Tests fail if a new live helper delegates to `pipeline_plan_executor.ps1`
  without loader support.
- No production behavior has moved yet.
- Change packet has touched files and validation evidence.

## Common Pitfalls

- Treating a clean release self-test as enough. It is not enough for later
  PowerShell extraction.
- Adding broad tests that execute real FFmpeg unexpectedly.
- Pinning brittle line numbers instead of stable function/evidence names.
- Adding a new command-builder test that duplicates existing plan executor
  coverage instead of extending it.
