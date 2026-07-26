---
file: ops/pipeline/engine/queue/phase_executor.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: df46b96fe1226630019aafc6b132b4b5aaf2a4aa3a9611d27d4871cfe25c81c4
---
# `ops/pipeline/engine/queue/phase_executor.ps1`

**Purpose:** PowerShell implementation for phase executor; exposes Complete-MediaPipelineRunMonitorQueueEntry, Get-MediaPipelineQueueDispatchBoundaryState, Get-MediaPipelineRunMonitorFirstResultValue.

**Public symbols:** `Complete-MediaPipelineRunMonitorQueueEntry`, `Get-MediaPipelineQueueDispatchBoundaryState`, `Get-MediaPipelineRunMonitorFirstResultValue`, `Get-MediaPipelineRunMonitorResultValue`, `Get-MediaPipelineRunMonitorTerminalTrackAction`, `Invoke-MediaPipelineProcessQueueEntry`, `Invoke-MediaPipelineProcessQueueEntrySafely`, `Invoke-MediaQueuePhasePlan`, `Resolve-MediaPipelineRunMonitorTerminalArtifact`, `Resolve-MediaPipelineRunMonitorTerminalAudioAction`, `Resolve-MediaPipelineRunMonitorTerminalSubtitleAction`, `Start-MediaPipelineRunMonitorQueueEntry`, `Sync-MediaPipelineRunMonitorTerminalTracks`, `Write-MediaPipelineUnexpectedQueueEntryFailure`
**Invoked stages:** `Id`, `processing`, `queue-item`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/phase_executor.ps1`._
