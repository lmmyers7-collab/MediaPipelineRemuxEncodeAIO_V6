---
file: engine/status/progress_state.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: status
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: da9121243fddc496c82149fd6fac155b5931d5c4b15786a4d77f4bdd3f5217a3
---
# `engine/status/progress_state.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-RetryNotice`, `Add-SkipStat`, `Check-ControlFlags`, `Convert-CopyPercentToStagePercent`, `Format-SkipSummary`, `Get-ControlFlagInfo`, `Get-ControlFlagProperty`, `Get-ProcessingStats`, `Get-ProgressIsoTimestamp`, `Get-StatsDelta`, `Get-StatsSnapshot`, `New-ControlRequestProgressState`, `New-SkipStats`, `Register-ControlFlagObservation`, `Reset-ProgressCopyTelemetry`, `Reset-ProgressItemContext`, `Reset-RoundTracking`, `Save-Progress`, `Set-ProgressCopyTelemetry`, `Set-ProgressItemContext`, `Set-ProgressStage`, `Set-ProgressSubtitleSidecarWrite`, `Set-ProgressSubtitleTrack`, `Test-ProgressPersistence`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/status/progress_state.ps1`._
