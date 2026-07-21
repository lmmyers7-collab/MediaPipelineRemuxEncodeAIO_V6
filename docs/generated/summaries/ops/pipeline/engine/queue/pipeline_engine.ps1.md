---
file: ops/pipeline/engine/queue/pipeline_engine.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 5a58c1dfae8709f2331262e528dfd5f1ab487d9dc7dbbeafb69231d4004ef7f0
---
# `ops/pipeline/engine/queue/pipeline_engine.ps1`

**Purpose:** PowerShell implementation for pipeline engine; exposes Complete-MediaPipelineBackendQueueRunOnceMonitor, Get-MediaPipelinePendingPublishBackpressure, Invoke-MediaPipelineEmitQueuePlan.

**Public symbols:** `Complete-MediaPipelineBackendQueueRunOnceMonitor`, `Get-MediaPipelinePendingPublishBackpressure`, `Invoke-MediaPipelineEmitQueuePlan`, `Invoke-MediaPipelineRound`, `Invoke-MediaPipelineRun`, `Select-MediaPipelineQueuePlanExecutionWindow`, `Write-MediaPipelinePendingPublishBackpressure`
**State/config identifiers:** `.manifest.json`, `MediaPipeline_config.psd1`
**Invoked stages:** `blocked`, `idle`, `pending_publish`, `pending_publish_backpressure`, `processing`, `queue`, `round`, `scanning`, `sleeping`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/pipeline_engine.ps1`._
