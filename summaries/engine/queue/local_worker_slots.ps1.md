---
file: engine/queue/local_worker_slots.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-05-30
last_reviewed: 2026-05-29
sha256: 319fc13f291741fbfbc60218ee666c258ee804c794be92bbe18c4582ccb67796
---
# `engine/queue/local_worker_slots.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `ConvertTo-MediaPipelineLocalWorkerPathKey`, `Get-MediaPipelineLocalWorkerClaimActiveStatuses`, `Get-MediaPipelineLocalWorkerClaimStore`, `Get-MediaPipelineLocalWorkerMutexName`, `Get-MediaPipelineLocalWorkerTimestamp`, `Get-MediaPipelineQueuePlanRunnableEntries`, `Get-MediaPipelineStableHash`, `Get-MediaPipelineWorkerMutexSuffix`, `Get-MediaPipelineWorkerProgressSnapshot`, `Initialize-MediaPipelineWorkerSlotLayout`, `Invoke-MediaPipelineFinalStateWrite`, `Invoke-MediaPipelineLocalWorkerClaim`, `Invoke-MediaPipelineMutexProtected`, `Invoke-MediaQueuePhasePlanLocalWorkerSlots`, `Join-MediaPipelineProcessArgument`, `New-MediaPipelineLocalWorkerClaimStore`, `New-MediaPipelineWorkerSlotLayout`, `Read-MediaPipelineJsonFile`, `Release-MediaPipelineLocalWorkerClaim`, `Repair-MediaPipelineLocalWorkerClaims`, `Start-MediaPipelineLocalWorkerChild`, `Stop-MediaPipelineLocalWorkerProcess`, `Test-MediaPipelineProcessAlive`, `Update-MediaPipelineLocalWorkerClaim`, `Update-MediaPipelineParentCountersFromWorkerResult`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/queue/local_worker_slots.ps1`._
