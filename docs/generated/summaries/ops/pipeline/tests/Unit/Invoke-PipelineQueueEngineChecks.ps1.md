---
file: ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: tests
last_modified: 2026-06-30
last_reviewed: 2026-06-04
sha256: df33e3ebb2e637bc7ecbb3332c1a67774358e8923270912301fbaba4a9913992
---
# `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Already-Processed`, `Assert-Equal`, `Assert-True`, `Build-QueuePlanSnapshotRows`, `Check-ControlFlags`, `Consume-RescanFlag`, `Get-MediaQueueDiscoveryPlan`, `Get-ProcessedIndexCached`, `Get-ProcessingStats`, `Get-TVInfoFromFile`, `Invalidate-ProcessedIndexCache`, `Invoke-CorruptPriorityManifestFailsClosedCheck`, `Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck`, `Invoke-GlobalRunnableQueueSnapshotMetadataCheck`, `Invoke-ManualOrderSortsHighPriorityBucketsCheck`, `Invoke-MediaPipelineRound`, `Invoke-MediaQueuePhasePlan`, `Invoke-MediaQueuePhasePlanLocalWorkerSlots`, `Invoke-PendingPublishBackpressureSkipsDiscoveryCheck`, `Invoke-PerFileUnexpectedExceptionContinuesSerialQueueCheck`, `Invoke-PerRoundUnexpectedExceptionContinuousRetryCheck`, `Invoke-PeriodicLocalEncodedDirectoryCleanup`, `Invoke-QueueExecutionCapLimitsRunnableWindowCheck`, `Invoke-QueueSnapshotHoldRowsRunnableCountCheck`, `Invoke-QueueSnapshotRowsAreCappedButTotalsRemainAccurateCheck`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`._
