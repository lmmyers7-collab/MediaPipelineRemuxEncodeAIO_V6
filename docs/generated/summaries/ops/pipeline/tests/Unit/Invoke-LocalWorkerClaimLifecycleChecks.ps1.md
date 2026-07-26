---
file: ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-16
last_reviewed: 2026-06-10
sha256: 1e02604797ac2303847069d91af9b7af762998d2ade6fe7fc66234978c91bd13
---
# `ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1`

**Purpose:** PowerShell implementation for invoke local worker claim lifecycle checks; exposes Assert-Equal, Assert-True, Check-ControlFlags.

**Public symbols:** `Assert-Equal`, `Assert-True`, `Check-ControlFlags`, `Get-MediaPipelineQueuePlanRunnableEntries`, `Invalidate-ProcessedIndexCache`, `Invoke-LocalWorkerChildHardTimeoutKillReleasesCheck`, `Invoke-LocalWorkerPostSpawnClaimFailureStopsChildCheck`, `Invoke-LocalWorkerStaleHeartbeatKillReleasesCheck`, `Invoke-MediaPipelineLocalWorkerClaim`, `Invoke-StaleClaimWithReusedPidReleasesCheck`, `Invoke-StaleResultReadyClaimReleasesForRetryCheck`, `Invoke-VerifiedLiveWorkerClaimIsProtectedCheck`, `New-LocalWorkerLifecycleEntry`, `Release-MediaPipelineLocalWorkerClaim`, `Repair-MediaPipelineLocalWorkerClaims`, `Start-MediaPipelineLocalWorkerChild`, `Stop-MediaPipelineLocalWorkerProcess`, `Test-MediaPipelineStopAfterCurrentBoundary`, `Update-MediaPipelineLocalWorkerClaim`, `Write-Log`, `Write-MediaPipelineLocalWorkerActiveJobs`, `Write-PipelineEvent`
**State/config identifiers:** `MediaPipeline_config.psd1`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1`._
