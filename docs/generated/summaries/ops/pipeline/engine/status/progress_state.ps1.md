---
file: ops/pipeline/engine/status/progress_state.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: observability
token_priority: medium
owner_domain: status
last_modified: 2026-07-17
last_reviewed: 2026-06-04
sha256: 6914f5707079e3652a814571091cca14c5be47e5c788b22d6a6c3f59049dedd9
---
# `ops/pipeline/engine/status/progress_state.ps1`

**Purpose:** Creates a throttled native-process heartbeat for one exact run/job/stage.

**Public symbols:** `Add-PushThroughputSample`, `Add-RetryNotice`, `Add-SkipStat`, `Check-ControlFlags`, `Convert-CopyPercentToStagePercent`, `Format-SkipSummary`, `Get-ControlFlagAgeSeconds`, `Get-ControlFlagInfo`, `Get-ControlFlagProperty`, `Get-MediaPipelineCurrentControllerLaunchId`, `Get-ProcessingStats`, `Get-ProgressIsoTimestamp`, `Get-ProgressSaveRetryDelaysMs`, `Get-PushAverageBytesPerSecond`, `Get-StatsDelta`, `Get-StatsSnapshot`, `Initialize-MediaPipelineSessionState`, `Move-ProgressFileIntoPlace`, `New-ControlRequestProgressState`, `New-MediaPipelineCurrentStageNativePollHandler`, `New-SkipStats`, `Register-ControlFlagObservation`, `Reset-ProgressCopyTelemetry`, `Reset-ProgressItemContext`, `Reset-RoundTracking`, `Save-Progress`, `Set-MediaPipelinePauseMonitorState`, `Set-MediaPipelineStopAfterCurrentMonitorState`, `Set-ProgressAudioTrack`, `Set-ProgressCopyTelemetry`, `Set-ProgressItemContext`, `Set-ProgressPendingDrain`, `Set-ProgressStage`, `Set-ProgressSubtitleSidecarWrite`, `Set-ProgressSubtitleTrack`
**Invoked stages:** `blocked`, `Id`, `paused`, `processing`, `progress`, `sidecar_write`, `stopped`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/status/progress_state.ps1`._
