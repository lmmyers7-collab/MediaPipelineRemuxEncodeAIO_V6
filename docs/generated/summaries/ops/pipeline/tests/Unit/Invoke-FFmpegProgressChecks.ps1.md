---
file: ops/pipeline/tests/Unit/Invoke-FFmpegProgressChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: high
owner_domain: tests
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 36e4e19bbc7dd25c284cf77e7e03bbc57f0ee65e05a1b9748d27461a8d79fd02
---
# `ops/pipeline/tests/Unit/Invoke-FFmpegProgressChecks.ps1`

**Purpose:** PowerShell implementation for invoke ffmpeg progress checks; exposes Assert-Equal, Assert-Near, Assert-PathUnderRoot.

**Public symbols:** `Assert-Equal`, `Assert-Near`, `Assert-PathUnderRoot`, `Assert-True`, `Complete-MediaPipelineRunMonitorAudioWork`, `ConvertTo-MediaPipelineRunMonitorStageId`, `DebugLog`, `End-MediaPipelineRunMonitorAudioWorkAttempt`, `Format-NativeCommandLine`, `Invoke-FFprobeCommand`, `Invoke-NativeProcess`, `New-MediaPipelineCurrentStageNativePollHandler`, `Save-ReproCommand`, `Set-MediaPipelineCurrentRunMonitorStage`, `Set-ProgressStage`, `Start-MediaPipelineRunMonitorAudioWork`, `Update-MediaPipelineRunMonitorActiveTrackHeartbeat`, `Write-Log`, `Write-PipelineEvent`
**Invoked stages:** `remux-mkvmerge`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-FFmpegProgressChecks.ps1`._
