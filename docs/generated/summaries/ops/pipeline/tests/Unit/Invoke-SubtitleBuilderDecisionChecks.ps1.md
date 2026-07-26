---
file: ops/pipeline/tests/Unit/Invoke-SubtitleBuilderDecisionChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 6a87e302cfadf000feb23007a3efa2e8b5a5e643db13f69098b76eb8b929b290
---
# `ops/pipeline/tests/Unit/Invoke-SubtitleBuilderDecisionChecks.ps1`

**Purpose:** PowerShell implementation for invoke subtitle builder decision checks; exposes Acquire-CpuEncodeMutex, Assert-ContainsText, Assert-Equal.

**Public symbols:** `Acquire-CpuEncodeMutex`, `Assert-ContainsText`, `Assert-Equal`, `Assert-True`, `Convert-AssToSrt`, `Convert-BdpgsToSrt`, `Convert-Tx3gToSrt`, `Convert-VobSubToSrt`, `DebugLog`, `Extract-BdpgsToSup`, `Get-ConfiguredOutputContainerName`, `Get-ConvertedSrtCodecForFfmpegOutput`, `Get-EffectiveSubtitleSwitch`, `Get-FileOverrideSubtitleSettings`, `Get-MkvmergeTidMap`, `Get-NormalizedSubtitleLanguage`, `Get-SubtitleLanguageDisplayMap`, `Get-SubtitleLanguagePolicy`, `Get-SubtitleOperationTimeoutSeconds`, `Get-SubtitleTrackTitleOverride`, `Invoke-BdpgsOcrCommand`, `Invoke-FFprobeCommand`, `New-BdpgsFailureRecord`, `New-StandardFailureRecord`, `New-SubtitleTrackHeartbeatHandler`, `New-TestSubtitleEntry`, `New-Tx3gFailureRecord`, `New-VobSubFailureRecord`, `Resolve-SubtitleConfiguredPath`, `Set-MediaPipelineRunMonitorSubtitleRecords`, `Test-CanPreserveBdpgsInFfmpegOutput`, `Test-CanPreserveTx3gInFfmpegOutput`, `Test-CanPreserveVobSubInFfmpegOutput`, `Test-IsBdpgsSubtitleStream`, `Test-IsTx3gSubtitleStream`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-SubtitleBuilderDecisionChecks.ps1`._
