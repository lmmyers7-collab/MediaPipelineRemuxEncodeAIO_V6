---
file: ops/pipeline/engine/process/remux_ffmpeg_av_stage.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: transcode
token_priority: medium
owner_domain: process
last_modified: 2026-07-16
last_reviewed: 2026-06-24
sha256: 62601a158b9f428ef1ba3a30961a79fecab6b0dc6b8d6b514f56dbc22e84e521
---
# `ops/pipeline/engine/process/remux_ffmpeg_av_stage.ps1`

**Purpose:** PowerShell implementation for remux ffmpeg av stage; exposes ConvertTo-MediaPipelineRemuxStreamBool, Get-MediaPipelineRemuxInventoryVideoStreams, Get-MediaPipelineRemuxStreamProperty.

**Public symbols:** `ConvertTo-MediaPipelineRemuxStreamBool`, `Get-MediaPipelineRemuxInventoryVideoStreams`, `Get-MediaPipelineRemuxStreamProperty`, `Invoke-MediaPipelineRemuxFfmpegAvStage`, `New-MediaPipelineRemuxVideoArgumentList`
**Invoked stages:** `remux-av`, `remux_av`
**Invoked tools:** `ffmpeg`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/remux_ffmpeg_av_stage.ps1`._
