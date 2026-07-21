---
file: ops/pipeline/engine/queue/worker_progress.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 5fcc15cfc812c7d7be7b6975cd07e08695085de9e167b63badc5ca399cd5085b
---
# `ops/pipeline/engine/queue/worker_progress.ps1`

**Purpose:** PowerShell implementation for worker progress; exposes ConvertTo-MediaPipelineWorkerEvidenceTimestamp, ConvertTo-MediaPipelineWorkerPercentOrNull, Get-MediaPipelineQueueEntryRunValue.

**Public symbols:** `ConvertTo-MediaPipelineWorkerEvidenceTimestamp`, `ConvertTo-MediaPipelineWorkerPercentOrNull`, `Get-MediaPipelineQueueEntryRunValue`, `Get-MediaPipelineQueuePlanRunnableEntries`, `Get-MediaPipelineWorkerHeartbeatSnapshot`, `Get-MediaPipelineWorkerProgressSnapshot`, `Select-MediaPipelineFreshestWorkerEvidence`, `Update-MediaPipelineParentCountersFromWorkerResult`, `Write-MediaPipelineLocalWorkerActiveJobs`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/worker_progress.ps1`._
