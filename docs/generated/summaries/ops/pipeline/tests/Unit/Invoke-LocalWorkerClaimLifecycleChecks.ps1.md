---
file: ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-10
last_reviewed: 2026-06-10
sha256: 89b6c49e71ef2638a676346de9d8dd6979076085723d785f4fb3b5f4ed83f115
---
# `ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Assert-Equal`, `Assert-True`, `Check-ControlFlags`, `Get-MediaPipelineQueuePlanRunnableEntries`, `Invalidate-ProcessedIndexCache`, `Invoke-LocalWorkerChildHardTimeoutKillReleasesCheck`, `Invoke-LocalWorkerPostSpawnClaimFailureStopsChildCheck`, `Invoke-LocalWorkerStaleHeartbeatKillReleasesCheck`, `Invoke-MediaPipelineLocalWorkerClaim`, `Invoke-StaleClaimWithReusedPidReleasesCheck`, `Invoke-StaleResultReadyClaimReleasesForRetryCheck`, `Invoke-VerifiedLiveWorkerClaimIsProtectedCheck`, `New-LocalWorkerLifecycleEntry`, `Release-MediaPipelineLocalWorkerClaim`, `Repair-MediaPipelineLocalWorkerClaims`, `Start-MediaPipelineLocalWorkerChild`, `Stop-MediaPipelineLocalWorkerProcess`, `Update-MediaPipelineLocalWorkerClaim`, `Write-Log`, `Write-MediaPipelineLocalWorkerActiveJobs`, `Write-PipelineEvent`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1`._
