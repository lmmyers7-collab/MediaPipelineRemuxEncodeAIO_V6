---
file: ops/pipeline/engine/process/remux_verification.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-16
last_reviewed: 2026-06-24
sha256: 686e59b2364f7747f28571daaaef3a0d2c539d900f18ce9e49b4b193699a3abe
---
# `ops/pipeline/engine/process/remux_verification.ps1`

**Purpose:** PowerShell implementation for remux verification; exposes Invoke-MediaPipelineRemuxVerification, Set-MediaPipelineRemuxVerificationMonitorOutcome.

**Public symbols:** `Invoke-MediaPipelineRemuxVerification`, `Set-MediaPipelineRemuxVerificationMonitorOutcome`
**Invoked stages:** `Id`, `remux-dynamic-hdr-verify`, `remux-media-track-verify`, `remux-mkvmerge`, `remux-verify`, `remux-video-stream-verify`, `remux_verify`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/remux_verification.ps1`._
