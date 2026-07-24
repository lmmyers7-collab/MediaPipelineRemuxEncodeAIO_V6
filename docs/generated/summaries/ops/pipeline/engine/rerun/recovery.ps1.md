---
file: ops/pipeline/engine/rerun/recovery.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: rerun
last_modified: 2026-07-23
last_reviewed: 2026-07-14
sha256: f7584568713295dd830ed768c3ab5f264b10d3fea49289bdbd4cf856dfcb2f22
---
# `ops/pipeline/engine/rerun/recovery.ps1`

**Purpose:** PowerShell implementation for recovery; exposes Add-RerunLifecycleTransition, Clear-RerunStageAttemptArtifacts, Copy-RerunRecoveryHistory.

**Public symbols:** `Add-RerunLifecycleTransition`, `Clear-RerunStageAttemptArtifacts`, `Copy-RerunRecoveryHistory`, `Get-RerunHighestAllocatedChunkIndex`, `Get-RerunRecoveryFirstText`, `Get-RerunRecoveryValue`, `Get-RerunResumeDisposition`, `Get-RerunRetryDelaySeconds`, `Get-RerunSourceExceptionCode`, `Get-RerunSourceHealth`, `Get-RerunSourceRootPath`, `Get-RerunSourceWorkOrder`, `Invoke-RerunBoundedProbeJob`, `Invoke-RerunSourceAvailabilityRecovery`, `Merge-RerunResumePlans`, `New-RerunChunkAllocation`, `New-RerunSourceHealthResult`, `Resolve-RerunConfiguredSourceRoot`, `Set-RerunManifestLifecycle`, `Set-RerunPlanLifecycle`, `Set-RerunRecoveryValue`, `Test-RerunRecoveryPathUnderRoot`, `Test-RerunStagedPlanEvidence`
**State/config identifiers:** `.config.psd1`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/rerun/recovery.ps1`._
