---
file: ops/pipeline/engine/subtitles/common.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: e5082a2f3b48ceb659e33ed85a5e2bcb27f3ab96dfa7ca3ee6703ae8c5ad987c
---
# `ops/pipeline/engine/subtitles/common.ps1`

**Purpose:** Creates a throttled native poll callback for one exact subtitle track stage.

**Public symbols:** `Add-SubtitleConfiguredPathBaseDirectory`, `Add-SubtitlePipelineDirectoryCandidates`, `ConvertTo-SubtitleBool`, `Get-ConfiguredOutputContainerName`, `Get-ConvertedSrtCodecForFfmpegOutput`, `Get-EffectiveSubtitleSwitch`, `Get-SafeSubtitleFileToken`, `Get-SubtitleConfiguredPathBaseDirectories`, `Get-SubtitleOperationTimeoutSeconds`, `Get-SubtitleScriptScopedValue`, `New-SubtitleTrackHeartbeatHandler`, `Resolve-SubtitleConfiguredPath`, `Test-ConfiguredOutputContainerIsMp4`, `Write-SubtitleSidecarProgress`, `Write-SubtitleTrackProgress`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/common.ps1`._
