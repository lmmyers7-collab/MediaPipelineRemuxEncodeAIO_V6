---
file: ops/pipeline/tests/Unit/Invoke-ProgressStateTelemetryChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-16
last_reviewed: 2026-06-08
sha256: 429566da196014f40866f15b241c61b6f80575d90248cc374f325242ba6d5d35
---
# `ops/pipeline/tests/Unit/Invoke-ProgressStateTelemetryChecks.ps1`

**Purpose:** PowerShell implementation for invoke progress state telemetry checks; exposes Assert-Equal, Assert-True, ConvertTo-MediaPipelineRunMonitorStageId.

**Public symbols:** `Assert-Equal`, `Assert-True`, `ConvertTo-MediaPipelineRunMonitorStageId`, `Set-MediaPipelineCurrentRunMonitorStage`, `Set-MediaPipelineRunMonitorRunState`, `Set-MediaPipelineRunMonitorStage`, `Set-MediaPipelineRunMonitorTrackProgress`, `Update-MediaPipelineRunMonitorActiveTrackHeartbeat`, `Write-Log`, `Write-MediaPipelineWorkerChildHeartbeat`, `Write-PipelineEvent`
**Invoked stages:** `audio_policy`, `convert_ocr`, `copy_to_scratch`, `encode_cpu`, `encode_prepare`, `encode_verify`, `sidecar_write`, `validate`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-ProgressStateTelemetryChecks.ps1`._
