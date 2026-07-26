---
file: ops/pipeline/engine/process/pipeline_processing.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: e269367a69639b302622f904084d779b1bae94b45e8165584008f103970eab7c
---
# `ops/pipeline/engine/process/pipeline_processing.ps1`

**Purpose:** PowerShell implementation for pipeline processing; exposes Invoke-MediaPipelineProcessFile, Invoke-MediaPipelineProcessPreflightDecision, New-MediaPipelineProcessFileResult.

**Public symbols:** `Invoke-MediaPipelineProcessFile`, `Invoke-MediaPipelineProcessPreflightDecision`, `New-MediaPipelineProcessFileResult`, `Resolve-MediaPipelineSourceProbeFailure`, `Write-MediaPipelineProcessCompletedEvent`
**Invoked stages:** `completed`, `encode_prepare`, `failed`, `file-override`, `file_override`, `Id`, `probe`, `processing`, `remux_prepare`, `route`, `source-probe`, `stopped`
**Invoked tools:** `ffmpeg`, `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/pipeline_processing.ps1`._
