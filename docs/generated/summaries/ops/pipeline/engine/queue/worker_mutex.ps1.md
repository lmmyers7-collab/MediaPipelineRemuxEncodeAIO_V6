---
file: ops/pipeline/engine/queue/worker_mutex.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: 1b784758d15b46058b4089410d475ca5eb590d65367acd4d21ee6baebcf22491
---
# `ops/pipeline/engine/queue/worker_mutex.ps1`

**Purpose:** PowerShell implementation for worker mutex; exposes Get-MediaPipelineLocalWorkerMutexName, Get-MediaPipelineLocalWorkerTimestamp, Get-MediaPipelineStableHash.

**Public symbols:** `Get-MediaPipelineLocalWorkerMutexName`, `Get-MediaPipelineLocalWorkerTimestamp`, `Get-MediaPipelineStableHash`, `Get-MediaPipelineWorkerMutexSuffix`, `Invoke-MediaPipelineFinalStateWrite`, `Invoke-MediaPipelineMutexProtected`, `Read-MediaPipelineJsonFile`, `Write-MediaPipelineJsonAtomic`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/worker_mutex.ps1`._
