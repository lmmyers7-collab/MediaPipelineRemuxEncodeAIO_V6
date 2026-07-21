---
file: ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: orchestration
token_priority: medium
owner_domain: tests
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 42ef8496c95d0709f8308e5fe229247511ca94d685b7a8502d4f240a973801b7
---
# `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`

**Purpose:** PowerShell implementation for invoke pipeline queue engine checks; exposes Already-Processed, Assert-Equal, Assert-True.

**Public symbols:** `Already-Processed`, `Assert-Equal`, `Assert-True`, `Build-QueuePlanSnapshotRows`, `Check-ControlFlags`, `Complete-MediaPipelineRunMonitor`, `Consume-RescanFlag`, `Get-MediaPipelinePendingPublishBackpressure`, `Get-MediaPipelineRunMonitorAcceptedSeedRows`, `Get-MediaQueueDiscoveryPlan`, `Get-ProcessedIndexCached`, `Get-ProcessingStats`, `Get-TVInfoFromFile`, `Invalidate-ProcessedIndexCache`, `Invoke-AcceptedRunBlocksWhenBackendNamingEvidenceFailsCheck`, `Invoke-AcceptedRunRowsMustMatchActiveEvidenceExactlyCheck`, `Invoke-AcceptedRunSeedRequiresPlannedNameEvidenceCheck`, `Invoke-AcceptedRunUsesBackendRenameDisplayNameCheck`, `Invoke-ActiveBadRenameCorpusQueueChecks`, `Invoke-CorruptPriorityManifestFailsClosedCheck`, `Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck`, `Invoke-GlobalRunnableQueueSnapshotMetadataCheck`, `Invoke-KananRevisionQueueSnapshotParseReuseCheck`, `Invoke-ManualOrderSortsHighPriorityBucketsCheck`, `Invoke-MediaPipelineQueueSnapshot`, `Invoke-MediaPipelineRound`, `Invoke-MediaQueuePhasePlan`, `Invoke-MediaQueuePhasePlanLocalWorkerSlots`, `Invoke-PendingPublishBackpressureBlocksBeforeExecutionCheck`, `Invoke-PerFileUnexpectedExceptionContinuesSerialQueueCheck`, `Invoke-PeriodicLocalEncodedDirectoryCleanup`, `Invoke-PerRoundUnexpectedExceptionContinuousRetryCheck`, `Invoke-QueueExecutionCapLimitsRunnableWindowCheck`, `Invoke-QueuePlanFingerprintGuardCheck`, `Invoke-QueueSnapshotHoldRowsRunnableCountCheck`
**State/config identifiers:** `MediaPipeline_config.psd1`, `one.manifest.json`, `priority_manifest.json`, `queue_snapshot.json`, `two.manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`._
