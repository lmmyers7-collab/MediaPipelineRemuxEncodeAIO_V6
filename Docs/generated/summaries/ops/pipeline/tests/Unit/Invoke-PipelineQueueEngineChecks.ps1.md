---
file: ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: tests
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 86e79041f65a414c8b99e549b72e7584ca7ef5c80a67b7685e52ea7e68fa142d
---
# `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Already-Processed`, `Assert-Equal`, `Assert-True`, `Build-QueuePlanSnapshotRows`, `Check-ControlFlags`, `Consume-RescanFlag`, `Get-MediaQueueDiscoveryPlan`, `Get-ProcessedIndexCached`, `Get-ProcessingStats`, `Get-TVInfoFromFile`, `Invalidate-ProcessedIndexCache`, `Invoke-GlobalRunnableQueueSnapshotMetadataCheck`, `Invoke-ManualOrderSortsHighPriorityBucketsCheck`, `Invoke-MediaQueuePhasePlan`, `Invoke-MediaQueuePhasePlanLocalWorkerSlots`, `Invoke-QueueSnapshotHoldRowsRunnableCountCheck`, `Invoke-RetryPendingPushes`, `Invoke-SerialQueueDispatchUsesGlobalRunnableMetadataCheck`, `New-ManualOrderSortEntry`, `New-QueueEngineTestEntry`, `New-TestQueuePlan`, `Process-File`, `Refresh-PendingPublishIndex`, `Reset-ProgressItemContext`, `Reset-RoundTracking`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`._
