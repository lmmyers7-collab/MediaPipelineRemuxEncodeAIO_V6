# Phase 4 - Encode Fallback, Verification, Size Guard, And Publish

## Goal

Split the second half of encode behavior after Phase 3 has stabilized:

- hardware safe retry
- CPU fallback
- Dynamic HDR preserve/remux fallback
- post-encode verification
- quality checks
- size/waste guard
- encode publish handoff

This is the highest-risk phase because it touches many paths that decide
whether an output is accepted, rejected, parked, or routed to review.

## Scope

In scope:

- Add encode fallback, verification, size guard, publish, and orchestrator
  modules.
- Preserve public `Do-Encode` behavior.
- Preserve route reason/evidence propagation.
- Preserve publish handoff semantics.

Out of scope:

- Changing size thresholds.
- Changing Dynamic HDR policy.
- Changing quality thresholds.
- Changing pending publish drain.
- Changing source/scratch/output cleanup semantics.

## Context Brief For Fresh Agents

Encode has multiple terminal outcomes:

- primary FFmpeg encode succeeds and verifies
- hardware encode fails, safe retry succeeds
- hardware encode fails, CPU fallback succeeds
- Dynamic HDR preserve requires CPU/libx265 path
- oversized encode falls back to remux if policy allows
- output fails verification and is blocked from publish
- publish parks output in pending publish when final output is unsafe

The split must preserve all of these outcomes and their evidence. Do not
"simplify" control flow unless tests and real-media validation prove equivalence.

## Proposed Extraction Order

### Step 1: Fallback

Create:

```text
ops/pipeline/engine/process/encode_fallback.ps1
```

Move:

- hardware safe retry orchestration
- CPU fallback orchestration
- Dynamic HDR preserve CPU path
- Dynamic HDR preserve-or-remux handling
- oversized encode remux fallback trigger

Preserve:

- fallback start/completed events
- route labels: `encode`, `encode-safe-retry`, `encode-cpu-fallback`
- route reason codes
- selected encoder metadata
- CPU mutex behavior
- fallback failure properties
- calls to `Do-Remux` for remux fallback until remux fallback has its own
  stable wrapper contract
- both `Do-Remux` fallback switches and their rejection evidence:
  `-FallbackFromOversizedEncode` and `-FallbackFromDynamicHdrEncode`

### Step 2: Verification

Create:

```text
ops/pipeline/engine/process/encode_verification.ps1
```

Move:

- duration verification
- real video stream count verification
- Dynamic HDR output verification
- quality verification
- terminal verification failure registration

Preserve:

- `encode_verify` progress stage
- `dynamic-hdr-output-verify` failure stage
- `encode-quality-verify` stage
- multi-video fail-closed behavior
- review classification for verification failures

### Step 3: Size Guard

Create:

```text
ops/pipeline/engine/process/encode_size_guard.ps1
```

Move:

- live encode waste guard finalization
- post-encode size policy
- oversized encode rejection
- oversized encode remux fallback acceptance/rejection

Preserve:

- `ENCODE_SIZE_GUARD_EXCEEDED`
- remux fallback rejection evidence
- direct-copy size/bitrate cap bypass only where current fallback behavior
  already allows it
- deletion behavior for rejected temp output

### Step 4: Publish

Create:

```text
ops/pipeline/engine/process/encode_publish.ps1
```

Move:

- encode-specific call to `Complete-PipelineOutputPublish`
- sidecar candidate forwarding
- route reason and route reason code forwarding
- route label after CPU fallback or safe retry

Preserve:

- context text = `ENCODE: `
- progress route = `encode`
- stage prefix = `encode`
- sidecar metadata flow
- pending publish parking behavior owned by publish modules
- publish cannot run until verification and size guard have both accepted the
  output

### Step 5: Orchestrator

Create:

```text
ops/pipeline/engine/process/encode_orchestrator.ps1
```

The orchestrator should read like an operational story:

1. build context
2. run preflight
3. create attempt plan
4. build command
5. execute attempt
6. resolve fallback until terminal
7. verify output
8. apply size guard
9. publish or register failure
10. clean up according to existing policy

Do not hide failure registration in generic catch blocks if the existing code
has specific failure evidence for that stage.

Before moving publish handoff, add a publish-order characterization test. The
test should stub or instrument `Complete-PipelineOutputPublish` and fail if it
is called before:

- output exists and is non-empty;
- duration verification passes;
- video-stream preservation passes;
- Dynamic HDR output verification passes when Dynamic HDR preserve applies;
- quality verification has accepted or explicitly fail-opened according to
  current config;
- size/waste guard has accepted the output or completed an accepted remux
  fallback.

## Validation

Run targeted checks after each extracted block:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-EncodeSizeGuardInspectionChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-DynamicHdrDetectionChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-DynamicHdrToolingChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-QualityVerificationChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-MultiVideoTopologyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-MediaVerificationSafetyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-FFmpegProgressChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishSafetyChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-PendingPublishOwnershipChecks.ps1
```

After the full phase:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-AdversarialForceKillEncodeChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ReliabilityRegressionChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Invoke-ToolIntegrationChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerSlotChecks.ps1

.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\pipeline\tests\Unit\Invoke-LocalWorkerClaimLifecycleChecks.ps1
```

Real-media validation is required before accepting this phase.

Minimum sample coverage:

- normal remux-safe source that routes to remux fallback after oversized encode
- normal encode source that completes primary encode
- source that forces CPU fallback or configured CPU primary
- Dynamic HDR preserve sample
- multi-video sample
- subtitle-bearing sample
- multi-audio sample
- pending publish/deferred publish sample

If a required sample is not available, record that as an unresolved validation
gap. The phase may be useful for review, but it is not release-ready until the
missing real-media case is either run or explicitly waived by the operator.

## Exit Criteria

- Fallback outcomes match pre-split behavior.
- Verification blocks publish on the same failures as before.
- Size guard accepts/rejects/falls back the same way as before.
- Publish handoff forwards the same route and sidecar evidence.
- Publish-order characterization proves publish cannot run before verification
  and size guard acceptance.
- Pending publish safety and ownership checks pass.
- Force-kill encode safety still blocks partial output acceptance.
- Real-media validation evidence is recorded when required.

## Common Pitfalls

- Returning success after a fallback path only partially completed.
- Losing route label after CPU fallback, causing Completed evidence to look like
  normal encode.
- Deleting an oversized temp output before remux fallback has finished using
  the scratch copy.
- Letting verification read stale context from the primary attempt after CPU
  fallback changes the selected encoder.
- Treating Dynamic HDR metadata extraction failure as advisory when current
  behavior fails closed.
- Moving publish behavior into encode instead of preserving publish module
  ownership.
