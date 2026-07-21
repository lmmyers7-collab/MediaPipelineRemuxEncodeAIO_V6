---
file: ops/pipeline/tests/Unit/Invoke-FFmpegProgressChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: high
owner_domain: tests
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: fdb6b0bc7c6868e64d93a2cc6ba71e4ec66288d3cbbecd89b8419982c5767837
---
# `ops/pipeline/tests/Unit/Invoke-FFmpegProgressChecks.ps1`

**Purpose:** PowerShell implementation for invoke ffmpeg progress checks; exposes Assert-Equal, Assert-PathUnderRoot, Assert-True.

**Public symbols:** `Assert-Equal`, `Assert-PathUnderRoot`, `Assert-True`, `Complete-MediaPipelineRunMonitorAudioWork`, `ConvertTo-MediaPipelineRunMonitorStageId`, `DebugLog`, `End-MediaPipelineRunMonitorAudioWorkAttempt`, `Format-NativeCommandLine`, `Invoke-FFprobeCommand`, `Invoke-NativeProcess`, `New-MediaPipelineCurrentStageNativePollHandler`, `Save-ReproCommand`, `Set-MediaPipelineCurrentRunMonitorStage`, `Set-ProgressStage`, `Start-MediaPipelineRunMonitorAudioWork`, `Update-MediaPipelineRunMonitorActiveTrackHeartbeat`, `Write-Log`, `Write-PipelineEvent`
**Invoked stages:** `remux-mkvmerge`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-FFmpegProgressChecks.ps1`._
