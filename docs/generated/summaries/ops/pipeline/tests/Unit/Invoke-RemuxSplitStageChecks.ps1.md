---
file: ops/pipeline/tests/Unit/Invoke-RemuxSplitStageChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-10
last_reviewed: 2026-06-24
sha256: 06a9ed2cc5f7cf4e9ffa07ed417e2fb345a438ee1199bf0d8a2bd93fc9144748
---
# `ops/pipeline/tests/Unit/Invoke-RemuxSplitStageChecks.ps1`

**Purpose:** PowerShell implementation for invoke remux split stage checks; exposes Acquire-CpuEncodeMutex, Assert-ContainsSubsequence, Assert-Equal.

**Public symbols:** `Acquire-CpuEncodeMutex`, `Assert-ContainsSubsequence`, `Assert-Equal`, `Assert-False`, `Assert-OrderContainsBefore`, `Assert-True`, `Build-AudioArgs`, `Build-SubtitleTracksForMkvmerge`, `Clear-SourceFailureState`, `Complete-PipelineOutputPublish`, `DebugLog`, `Do-Encode`, `Ensure-ScratchCopy`, `Filter-SubtitleStreams`, `Get-DefaultAudioLang`, `Get-DolbyVisionState`, `Get-ErrorTextSummary`, `Get-FFmpegFailureCode`, `Get-HDRState`, `Get-LastAudioDecisionRecords`, `Get-MediaTrackVerificationFacet`, `Get-MediaVideoCodecHevcNames`, `Get-MkvmergeAudioTids`, `Get-MkvmergeFailureCode`, `Get-OutputPaths`, `Get-SafeLocalName`, `Get-SourceTitleTag`, `Get-SourceVideoCodec`, `Invoke-FFmpegWithProgress`, `Invoke-MkvmergeWithProgress`, `Invoke-Tx3gSidecarExportForExistingOutput`, `New-DynamicHdrEvidence`, `New-ExistingOutputPublishResult`, `New-MediaRouteDecisionTraceEntry`, `New-MediaTrackOutputVerificationPlan`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-RemuxSplitStageChecks.ps1`._
