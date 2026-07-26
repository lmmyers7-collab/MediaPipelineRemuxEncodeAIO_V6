---
file: ops/pipeline/engine/process/encode_preflight.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-20
last_reviewed: 2026-06-24
sha256: 6a35dccb9dd6d7e775437ddd68681d5d709a6c1b83df747725a6d7cd35a5bd66
---
# `ops/pipeline/engine/process/encode_preflight.ps1`

**Purpose:** PowerShell implementation for encode preflight; exposes Invoke-MediaPipelineEncodePreflight, Invoke-MediaPipelineEncodeStreamPreparation.

**Public symbols:** `Invoke-MediaPipelineEncodePreflight`, `Invoke-MediaPipelineEncodeStreamPreparation`
**Invoked stages:** `audio-probe`, `copy_to_scratch`, `disk-space`, `encode-preflight`, `encode-space`, `encode-stream-preparation`, `encode_prepare`, `existing-output`, `existing-output-sidecar`, `hdr-detection`, `subtitle-burn-video-stream-policy`, `subtitle-extract`, `subtitle-probe`, `video-stream-policy`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/encode_preflight.ps1`._
