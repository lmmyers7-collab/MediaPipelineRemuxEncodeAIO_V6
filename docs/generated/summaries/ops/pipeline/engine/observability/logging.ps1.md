---
file: ops/pipeline/engine/observability/logging.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: observability
token_priority: medium
owner_domain: observability
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: b37fe1c9fa3ba22e587d9d7c89ed5108b389990ae1003b05a8449c46e53828a9
---
# `ops/pipeline/engine/observability/logging.ps1`

**Purpose:** PowerShell implementation for logging; exposes Add-StartupWarning, ConvertTo-PipelineEventData, DebugLog.

**Public symbols:** `Add-StartupWarning`, `ConvertTo-PipelineEventData`, `DebugLog`, `Get-EffectiveConfigSummary`, `Get-LogLevelRank`, `Get-PipelineDebugLogMaxBytes`, `Get-PipelineEventLogArchivePath`, `Invoke-LogRotation`, `Invoke-LogRotationCore`, `Invoke-PipelineEventLogRotation`, `Should-WriteLog`, `Write-EffectiveConfigSummary`, `Write-JsonLineAppend`, `Write-Log`, `Write-MediaPipelineStartupConfigLog`, `Write-PipelineEvent`, `Write-StartupEnvironmentSummary`, `Write-StartupWarnings`
**Invoked stages:** `startup`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/observability/logging.ps1`._
