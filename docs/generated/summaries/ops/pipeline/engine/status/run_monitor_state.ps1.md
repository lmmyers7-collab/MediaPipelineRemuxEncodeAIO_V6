---
file: ops/pipeline/engine/status/run_monitor_state.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: observability
token_priority: medium
owner_domain: status
last_modified: 2026-07-19
last_reviewed: 2026-07-16
sha256: 44c35c81b1325bcaf8e4cc18cd7d53f2d8cbe760891bd0f599e1cad093b3bcd9
---
# `ops/pipeline/engine/status/run_monitor_state.ps1`

**Purpose:** Reads immutable accepted destination-name evidence for one executing job.

**Public symbols:** `Add-MediaPipelineRunMonitorTerminalReference`, `Assert-MediaPipelineRunMonitorPayload`, `Assert-MediaPipelineRunMonitorSafeRunId`, `Complete-MediaPipelineRunMonitor`, `Complete-MediaPipelineRunMonitorAudioPolicy`, `Complete-MediaPipelineRunMonitorAudioWork`, `Complete-MediaPipelineRunMonitorTrackStageFromEvidence`, `ConvertTo-MediaPipelineRunMonitorStageId`, `End-MediaPipelineRunMonitorAudioWorkAttempt`, `Get-MediaPipelineRunMonitorAcceptedNamingEvidence`, `Get-MediaPipelineRunMonitorAcceptedSeedRows`, `Get-MediaPipelineRunMonitorItem`, `Get-MediaPipelineRunMonitorMembershipSignature`, `Get-MediaPipelineRunMonitorMutexName`, `Get-MediaPipelineRunMonitorPath`, `Get-MediaPipelineRunMonitorPointerPath`, `Get-MediaPipelineRunMonitorRoot`, `Get-MediaPipelineRunMonitorTimestamp`, `Get-MediaPipelineRunMonitorValue`, `Invoke-MediaPipelineRunMonitorUpdate`, `New-MediaPipelineAcceptedDestinationNameEvidenceResult`, `New-MediaPipelineRunMonitorEvidence`, `New-MediaPipelineRunMonitorProgress`, `New-MediaPipelineRunMonitorRouteEvidence`, `New-MediaPipelineRunMonitorStageLedger`, `New-MediaPipelineSourceDiscoveryPollHandler`, `Remove-MediaPipelineRunMonitorExpiredHistory`, `Set-MediaPipelineCurrentRunMonitorOutput`, `Set-MediaPipelineCurrentRunMonitorStage`, `Set-MediaPipelineRunMonitorAudioRecords`, `Set-MediaPipelineRunMonitorExecutedRoute`, `Set-MediaPipelineRunMonitorFinalRoute`, `Set-MediaPipelineRunMonitorFinalRouteState`, `Set-MediaPipelineRunMonitorItemLifecycle`, `Set-MediaPipelineRunMonitorOutput`
**Invoked stages:** `Id`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/status/run_monitor_state.ps1`._
