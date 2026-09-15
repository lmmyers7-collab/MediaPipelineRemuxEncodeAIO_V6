---
file: ops/pipeline/engine/status/progress_state.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: status
last_modified: 2026-09-14
last_reviewed: 2026-06-04
sha256: 398ee345d97b64ed4e240ef9f41d6d9b48b3bc06e7001160af5bf55fde175e02
---
# `ops/pipeline/engine/status/progress_state.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-PushThroughputSample`, `Add-RetryNotice`, `Add-SkipStat`, `Check-ControlFlags`, `Convert-CopyPercentToStagePercent`, `Format-SkipSummary`, `Get-ControlFlagAgeSeconds`, `Get-ControlFlagInfo`, `Get-ControlFlagProperty`, `Get-ProcessingStats`, `Get-ProgressIsoTimestamp`, `Get-ProgressSaveRetryDelaysMs`, `Get-PushAverageBytesPerSecond`, `Get-StatsDelta`, `Get-StatsSnapshot`, `Initialize-MediaPipelineSessionState`, `Move-ProgressFileIntoPlace`, `New-ControlRequestProgressState`, `New-SkipStats`, `Register-ControlFlagObservation`, `Reset-ProgressCopyTelemetry`, `Reset-ProgressItemContext`, `Reset-RoundTracking`, `Save-Progress`, `Set-ProgressAudioTrack`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/status/progress_state.ps1`._
