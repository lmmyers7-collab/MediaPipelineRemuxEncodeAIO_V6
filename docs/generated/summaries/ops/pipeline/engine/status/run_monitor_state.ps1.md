---
file: ops/pipeline/engine/status/run_monitor_state.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: observability
token_priority: medium
owner_domain: status
last_modified: 2026-07-20
last_reviewed: 2026-07-16
sha256: 19a47391bfa8e0b672255d836a95e452fa2abbbbae300235b53bf3189c6488bf
---
# `ops/pipeline/engine/status/run_monitor_state.ps1`

**Purpose:** Reads immutable accepted destination-name evidence for one executing job.

**Public symbols:** `Add-MediaPipelineRunMonitorTerminalReference`, `Complete-MediaPipelineRunMonitor`, `Complete-MediaPipelineRunMonitorAudioPolicy`, `Complete-MediaPipelineRunMonitorAudioWork`, `Complete-MediaPipelineRunMonitorTrackStageFromEvidence`, `ConvertTo-MediaPipelineRunMonitorStageId`, `End-MediaPipelineRunMonitorAudioWorkAttempt`, `Get-MediaPipelineRunMonitorAcceptedNamingEvidence`, `Get-MediaPipelineRunMonitorItem`, `Invoke-MediaPipelineRunMonitorUpdate`, `New-MediaPipelineAcceptedDestinationNameEvidenceResult`, `New-MediaPipelineSourceDiscoveryPollHandler`, `Set-MediaPipelineCurrentRunMonitorOutput`, `Set-MediaPipelineCurrentRunMonitorStage`, `Set-MediaPipelineRunMonitorAudioRecords`, `Set-MediaPipelineRunMonitorExecutedRoute`, `Set-MediaPipelineRunMonitorFinalRoute`, `Set-MediaPipelineRunMonitorFinalRouteState`, `Set-MediaPipelineRunMonitorItemLifecycle`, `Set-MediaPipelineRunMonitorOutput`, `Set-MediaPipelineRunMonitorRouteEvidence`, `Set-MediaPipelineRunMonitorRunState`, `Set-MediaPipelineRunMonitorSourceDiscoveryState`, `Set-MediaPipelineRunMonitorStage`, `Set-MediaPipelineRunMonitorSubtitleRecords`, `Set-MediaPipelineRunMonitorTrackProgress`, `Set-MediaPipelineRunMonitorWorkers`, `Start-MediaPipelineRunMonitorAudioWork`, `Update-MediaPipelineRunMonitorActiveTrackHeartbeat`, `Write-MediaPipelineRunMonitorSeed`
**Invoked stages:** `Id`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/status/run_monitor_state.ps1`._
