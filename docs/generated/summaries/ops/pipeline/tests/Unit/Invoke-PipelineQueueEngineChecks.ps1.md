---
file: ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: tests
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: d7b6bd27448f1a3d96de68f453e128981b6876b335b6f419fb1f0e5192031754
---
# `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Already-Processed`, `Assert-Equal`, `Assert-True`, `Build-QueuePlanSnapshotRows`, `Check-ControlFlags`, `Consume-RescanFlag`, `Get-MediaQueueDiscoveryPlan`, `Get-ProcessedIndexCached`, `Get-ProcessingStats`, `Get-TVInfoFromFile`, `Invalidate-ProcessedIndexCache`, `Invoke-CorruptPriorityManifestFailsClosedCheck`, `Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck`, `Invoke-GlobalRunnableQueueSnapshotMetadataCheck`, `Invoke-ManualOrderSortsHighPriorityBucketsCheck`, `Invoke-MediaQueuePhasePlan`, `Invoke-MediaQueuePhasePlanLocalWorkerSlots`, `Invoke-QueueSnapshotHoldRowsRunnableCountCheck`, `Invoke-QueueSnapshotRowsAreCappedButTotalsRemainAccurateCheck`, `Invoke-RetryPendingPushes`, `Invoke-SerialQueueDispatchUsesGlobalRunnableMetadataCheck`, `New-ManualOrderSortEntry`, `New-QueueEngineSyntheticEntry`, `New-QueueEngineTestEntry`, `New-TestQueuePlan`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`._
