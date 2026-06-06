---
file: ops/pipeline/engine/status/progress_state.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: status
last_modified: 2026-06-05
last_reviewed: 2026-06-04
sha256: 838c5789a656ed49c320a78c550414f8b00725a431138e2593d2b6335d894b8e
---
# `ops/pipeline/engine/status/progress_state.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-PushThroughputSample`, `Add-RetryNotice`, `Add-SkipStat`, `Check-ControlFlags`, `Convert-CopyPercentToStagePercent`, `Format-SkipSummary`, `Get-ControlFlagInfo`, `Get-ControlFlagProperty`, `Get-ProcessingStats`, `Get-ProgressIsoTimestamp`, `Get-PushAverageBytesPerSecond`, `Get-StatsDelta`, `Get-StatsSnapshot`, `Initialize-MediaPipelineSessionState`, `New-ControlRequestProgressState`, `New-SkipStats`, `Register-ControlFlagObservation`, `Reset-ProgressCopyTelemetry`, `Reset-ProgressItemContext`, `Reset-RoundTracking`, `Save-Progress`, `Set-ProgressCopyTelemetry`, `Set-ProgressItemContext`, `Set-ProgressStage`, `Set-ProgressSubtitleSidecarWrite`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/status/progress_state.ps1`._
