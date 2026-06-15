---
file: ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: tests
last_modified: 2026-06-12
last_reviewed: 2026-06-04
sha256: 040eb7901eb68b339d5756317791722dbd8c2278a6d93a7855032c72adddee4c
---
# `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Already-Processed`, `Assert-Equal`, `Assert-True`, `Build-QueuePlanSnapshotRows`, `Check-ControlFlags`, `Consume-RescanFlag`, `Get-MediaQueueDiscoveryPlan`, `Get-ProcessedIndexCached`, `Get-ProcessingStats`, `Get-TVInfoFromFile`, `Invalidate-ProcessedIndexCache`, `Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck`, `Invoke-GlobalRunnableQueueSnapshotMetadataCheck`, `Invoke-ManualOrderSortsHighPriorityBucketsCheck`, `Invoke-MediaQueuePhasePlan`, `Invoke-MediaQueuePhasePlanLocalWorkerSlots`, `Invoke-QueueSnapshotHoldRowsRunnableCountCheck`, `Invoke-RetryPendingPushes`, `Invoke-SerialQueueDispatchUsesGlobalRunnableMetadataCheck`, `New-ManualOrderSortEntry`, `New-QueueEngineTestEntry`, `New-TestQueuePlan`, `Process-File`, `Refresh-PendingPublishIndex`, `Reset-ProgressItemContext`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`._
