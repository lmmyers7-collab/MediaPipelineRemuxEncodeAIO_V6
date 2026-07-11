---
file: ops/pipeline/engine/observability/logging.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: a6e91ecfad86c28310f1081b0fceee94b8f4c5a599fb6ea592739c4e668d8553
---
# `ops/pipeline/engine/observability/logging.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-StartupWarning`, `ConvertTo-PipelineEventData`, `DebugLog`, `Get-EffectiveConfigSummary`, `Get-LogLevelRank`, `Get-PipelineDebugLogMaxBytes`, `Get-PipelineEventLogArchivePath`, `Invoke-LogRotation`, `Invoke-LogRotationCore`, `Invoke-PipelineEventLogRotation`, `Should-WriteLog`, `Write-EffectiveConfigSummary`, `Write-JsonLineAppend`, `Write-Log`, `Write-MediaPipelineStartupConfigLog`, `Write-PipelineEvent`, `Write-StartupEnvironmentSummary`, `Write-StartupWarnings`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/observability/logging.ps1`._
