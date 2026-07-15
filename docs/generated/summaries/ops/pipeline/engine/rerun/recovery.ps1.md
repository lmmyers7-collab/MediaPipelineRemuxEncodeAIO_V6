---
file: ops/pipeline/engine/rerun/recovery.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: rerun
last_modified: 2026-07-14
last_reviewed: 2026-07-14
sha256: 1ad3a2f0e59724f39183dc85aedc17dd95b967131411cc7d624f652992965693
---
# `ops/pipeline/engine/rerun/recovery.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-RerunLifecycleTransition`, `Clear-RerunStageAttemptArtifacts`, `Copy-RerunRecoveryHistory`, `Get-RerunHighestAllocatedChunkIndex`, `Get-RerunRecoveryFirstText`, `Get-RerunRecoveryValue`, `Get-RerunResumeDisposition`, `Get-RerunRetryDelaySeconds`, `Get-RerunSourceExceptionCode`, `Get-RerunSourceHealth`, `Get-RerunSourceRootPath`, `Get-RerunSourceWorkOrder`, `Invoke-RerunBoundedProbeJob`, `Invoke-RerunSourceAvailabilityRecovery`, `Merge-RerunResumePlans`, `New-RerunChunkAllocation`, `New-RerunSourceHealthResult`, `Resolve-RerunConfiguredSourceRoot`, `Set-RerunManifestLifecycle`, `Set-RerunPlanLifecycle`, `Set-RerunRecoveryValue`, `Test-RerunRecoveryPathUnderRoot`, `Test-RerunStagedPlanEvidence`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/rerun/recovery.ps1`._
