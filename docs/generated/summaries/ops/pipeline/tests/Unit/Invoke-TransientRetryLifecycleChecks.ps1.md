---
file: ops/pipeline/tests/Unit/Invoke-TransientRetryLifecycleChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-15
last_reviewed: 2026-07-15
sha256: 3376d066812112edf759f501a70942ca8b096fc58437b60cd0d843f14bb0f6ea
---
# `ops/pipeline/tests/Unit/Invoke-TransientRetryLifecycleChecks.ps1`

**Purpose:** PowerShell implementation for invoke transient retry lifecycle checks; exposes Add-RetryNotice, Add-RoundFailureRecord, Assert-Equal.

**Public symbols:** `Add-RetryNotice`, `Add-RoundFailureRecord`, `Assert-Equal`, `Assert-True`, `Clear-SourceFailureState`, `Ensure-ScratchCopy`, `Get-OutputPaths`, `Get-SourceFailureState`, `Invoke-ParkPendingPushWithTx3gSidecars`, `Invoke-Tx3gSidecarExportForExistingOutput`, `New-PendingParkArguments`, `New-PublishEvidenceContext`, `Normalize-FailureCode`, `Register-SourceFailure`, `Set-ProgressStage`, `Test-OutputNeedsReprocess`, `Write-Log`
**Invoked stages:** `Prefix`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-TransientRetryLifecycleChecks.ps1`._
