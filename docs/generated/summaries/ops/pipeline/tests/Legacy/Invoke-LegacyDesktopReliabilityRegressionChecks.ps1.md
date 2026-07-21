---
file: ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 9e1bdd14b6c61f8e332bd6abd18d5606494ee1dec51e65acc9834bfd7849d94d
---
# `ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1`

**Purpose:** PowerShell implementation for invoke legacy desktop reliability regression checks; exposes Add-CompletedJobsManifestEntryFromSidecar, Add-RoundFailureRecord, Add-TestEvent.

**Public symbols:** `Add-CompletedJobsManifestEntryFromSidecar`, `Add-RoundFailureRecord`, `Add-TestEvent`, `Already-Processed`, `Assert-True`, `Assert-TV`, `Build-QueuePlanSnapshotRows`, `Check-ControlFlags`, `Clear-SourceFailureState`, `Complete-PublishMediaReveal`, `Consume-RescanFlag`, `Convert-ToLowerInvariantSafe`, `ConvertTo-BdpgsEmbeddedSrtTrackRecords`, `ConvertTo-Tx3gEmbeddedSrtTrackRecords`, `Copy-FileRobocopy`, `Copy-SrtAtomic`, `DebugLog`, `Get-ActiveMediaRouteHints`, `Get-CachedSourceFiles`, `Get-ErrorTextSummary`, `Get-FailureSuggestedAction`, `Get-FFmpegFailureCode`, `Get-FFprobeFailureCode`, `Get-FreeSpaceGBAny`, `Get-FunctionText`, `Get-LastAudioDecisionRecords`, `Get-LastSubtitleDecisionRecords`, `Get-MediaDuration`, `Get-MediaFailureCode`, `Get-MediaQueueDiscoveryPlan`, `Get-MkvmergeFailureCode`, `Get-ProcessedIndexCached`, `Get-ProcessingStats`, `Get-QueuedEntries`, `Get-SidecarPath`
**State/config identifiers:** `.manifest.json`, `bad-current.manifest.json`, `completed_manifest_backfill_progress.json`, `config.psd1`, `ignored-config.psd1`, `legacyLocal.manifest.json`, `media_pipeline_config.schema.json`, `media_pipeline_pending_push_manifest.schema.json`, `mediaLocal.manifest.json`, `MediaPipeline_config_chatgpt.psd1`, `MediaPipeline_config_template.psd1`, `MediaPipeline_config_test.psd1`, `missingMediaLocal.manifest.json`, `missingPayloadLocal.manifest.json`, `movie.mkv.manifest.json`, `parked.manifest.json`, `queue_snapshot.json`, `retryLocal.manifest.json`, `revealMediaLocal.manifest.json`
**Invoked stages:** `check`, `encode`, `encode-cpu`, `encode-verify`, `failure`, `Prefix`, `remux-av`, `retry-limit`, `scratch-integrity`, `subtitle-extract`, `subtitle-tx3g-extract`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvextract`, `mkvmerge`, `pgstosrt`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1`._
