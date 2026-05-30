---
file: engine/status/progress_state.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: status
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: e4918220ae3d1962e477d6398c1716f10b5a6dd824cf2e820e0b0c2742eba7e5
---
# `engine/status/progress_state.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-RetryNotice`, `Add-SkipStat`, `Check-ControlFlags`, `Convert-CopyPercentToStagePercent`, `Format-SkipSummary`, `Get-ControlFlagInfo`, `Get-ControlFlagProperty`, `Get-ProcessingStats`, `Get-ProgressIsoTimestamp`, `Get-StatsDelta`, `Get-StatsSnapshot`, `New-ControlRequestProgressState`, `New-SkipStats`, `Register-ControlFlagObservation`, `Reset-ProgressCopyTelemetry`, `Reset-ProgressItemContext`, `Reset-RoundTracking`, `Save-Progress`, `Set-ProgressCopyTelemetry`, `Set-ProgressItemContext`, `Set-ProgressStage`, `Set-ProgressSubtitleSidecarWrite`, `Set-ProgressSubtitleTrack`, `Test-ProgressPersistence`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/status/progress_state.ps1`._
