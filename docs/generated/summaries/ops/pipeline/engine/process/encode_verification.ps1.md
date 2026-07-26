---
file: ops/pipeline/engine/process/encode_verification.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-16
last_reviewed: 2026-06-24
sha256: 19c398655f07d7c3696f597d754af9a338610b22d967d9e03a3256fdeebc72f6
---
# `ops/pipeline/engine/process/encode_verification.ps1`

**Purpose:** PowerShell implementation for encode verification; exposes Get-MediaPipelineEncodeVerificationBoundaryVersion, Invoke-MediaPipelineEncodeVerification, Set-MediaPipelineEncodeVerificationMonitorOutcome.

**Public symbols:** `Get-MediaPipelineEncodeVerificationBoundaryVersion`, `Invoke-MediaPipelineEncodeVerification`, `Set-MediaPipelineEncodeVerificationMonitorOutcome`
**Invoked stages:** `dynamic-hdr-output-verify`, `encode`, `encode-hdr10-verify`, `encode-media-track-verify`, `encode-quality-verify`, `encode-verify`, `encode-video-stream-verify`, `encode_verify`, `Id`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/encode_verification.ps1`._
