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
sha256: afa348a527ee32f8539cb7c4b9c1b3a6190c0467ac2e12e99a02c51561553a20
---
# `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`

**Purpose:** PowerShell implementation for invoke pipeline queue engine checks; exposes Already-Processed, Assert-Equal, Assert-True.

**Public symbols:** `Already-Processed`, `Assert-Equal`, `Assert-True`, `Build-QueuePlanSnapshotRows`, `Check-ControlFlags`, `Complete-MediaPipelineRunMonitor`, `Consume-RescanFlag`, `Get-MediaPipelinePendingPublishBackpressure`, `Get-MediaPipelineRunMonitorAcceptedSeedRows`, `Get-MediaQueueDiscoveryPlan`, `Get-ProcessedIndexCached`, `Get-ProcessingStats`, `Get-TVInfoFromFile`, `Invalidate-ProcessedIndexCache`, `Invoke-AcceptedRunBlocksWhenBackendNamingEvidenceFailsCheck`, `Invoke-AcceptedRunRowsMustMatchActiveEvidenceExactlyCheck`, `Invoke-AcceptedRunSeedRequiresPlannedNameEvidenceCheck`, `Invoke-AcceptedRunUsesBackendRenameDisplayNameCheck`, `Invoke-ActiveBadRenameCorpusQueueChecks`, `Invoke-CorruptPriorityManifestFailsClosedCheck`, `Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck`, `Invoke-GlobalRunnableQueueSnapshotMetadataCheck`, `Invoke-KananRevisionQueueSnapshotParseReuseCheck`, `Invoke-ManualOrderSortsHighPriorityBucketsCheck`, `Invoke-MediaPipelineQueueSnapshot`, `Invoke-MediaPipelineRound`, `Invoke-MediaQueuePhasePlan`, `Invoke-MediaQueuePhasePlanLocalWorkerSlots`, `Invoke-PendingPublishBackpressureBlocksBeforeExecutionCheck`, `Invoke-PerFileUnexpectedExceptionContinuesSerialQueueCheck`, `Invoke-PeriodicLocalEncodedDirectoryCleanup`, `Invoke-PerRoundUnexpectedExceptionContinuousRetryCheck`, `Invoke-PriorityOnlyEntrypointBoundaryCheck`, `Invoke-PriorityOnlyQueuePlanSelectsEffectiveHighEntriesCheck`, `Invoke-QueueExecutionCapLimitsRunnableWindowCheck`
**State/config identifiers:** `MediaPipeline_config.psd1`, `one.manifest.json`, `priority_manifest.json`, `queue_snapshot.json`, `two.manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`._
