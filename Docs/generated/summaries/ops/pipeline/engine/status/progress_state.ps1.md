---
file: ops/pipeline/engine/status/progress_state.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: status
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: c6287eb08997391a2fea3caca46a0e7c08f482d9ee0b2d2aa3122c0b8b04ff53
---
# `ops/pipeline/engine/status/progress_state.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-RetryNotice`, `Add-SkipStat`, `Check-ControlFlags`, `Convert-CopyPercentToStagePercent`, `Format-SkipSummary`, `Get-ControlFlagInfo`, `Get-ControlFlagProperty`, `Get-ProcessingStats`, `Get-ProgressIsoTimestamp`, `Get-StatsDelta`, `Get-StatsSnapshot`, `New-ControlRequestProgressState`, `New-SkipStats`, `Register-ControlFlagObservation`, `Reset-ProgressCopyTelemetry`, `Reset-ProgressItemContext`, `Reset-RoundTracking`, `Save-Progress`, `Set-ProgressCopyTelemetry`, `Set-ProgressItemContext`, `Set-ProgressStage`, `Set-ProgressSubtitleSidecarWrite`, `Set-ProgressSubtitleTrack`, `Test-ProgressPersistence`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/status/progress_state.ps1`._
