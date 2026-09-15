---
file: ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: tests
last_modified: 2026-09-15
last_reviewed: 2026-06-04
sha256: 54c6dbf45c2aa9368461c833f6437b7cd0baba639be995ff7ef7e668a6da5b63
---
# `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Already-Processed`, `Assert-Equal`, `Assert-True`, `Build-QueuePlanSnapshotRows`, `Check-ControlFlags`, `Consume-RescanFlag`, `Get-MediaQueueDiscoveryPlan`, `Get-ProcessedIndexCached`, `Get-ProcessingStats`, `Get-TVInfoFromFile`, `Invalidate-ProcessedIndexCache`, `Invoke-CorruptPriorityManifestFailsClosedCheck`, `Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck`, `Invoke-GlobalRunnableQueueSnapshotMetadataCheck`, `Invoke-ManualOrderSortsHighPriorityBucketsCheck`, `Invoke-MediaPipelineRound`, `Invoke-MediaQueuePhasePlan`, `Invoke-MediaQueuePhasePlanLocalWorkerSlots`, `Invoke-PendingPublishBackpressureSkipsDiscoveryCheck`, `Invoke-PerFileUnexpectedExceptionContinuesSerialQueueCheck`, `Invoke-PerRoundUnexpectedExceptionContinuousRetryCheck`, `Invoke-PeriodicLocalEncodedDirectoryCleanup`, `Invoke-QueueExecutionCapLimitsRunnableWindowCheck`, `Invoke-QueueSnapshotHoldRowsRunnableCountCheck`, `Invoke-QueueSnapshotRowsAreCappedButTotalsRemainAccurateCheck`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`._
