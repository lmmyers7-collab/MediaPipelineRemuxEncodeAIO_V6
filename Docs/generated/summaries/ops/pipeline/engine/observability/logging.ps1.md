---
file: ops/pipeline/engine/observability/logging.ps1
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-06-18
last_reviewed: 2026-06-04
sha256: eca1ecaac3dc364f47bed986892e7f7942ddc13af90c1fc92c68f8060d918ccf
---
# `ops/pipeline/engine/observability/logging.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Add-StartupWarning`, `ConvertTo-PipelineEventData`, `DebugLog`, `Get-EffectiveConfigSummary`, `Get-LogLevelRank`, `Get-PipelineEventLogArchivePath`, `Invoke-LogRotation`, `Invoke-PipelineEventLogRotation`, `Should-WriteLog`, `Write-EffectiveConfigSummary`, `Write-JsonLineAppend`, `Write-Log`, `Write-MediaPipelineStartupConfigLog`, `Write-PipelineEvent`, `Write-StartupEnvironmentSummary`, `Write-StartupWarnings`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/observability/logging.ps1`._
