---
file: ops/pipeline/entrypoints/MediaPipeline.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: unknown
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 4db0006615c86ab80180d220b64fbdaba072b0d8cd332e9a90e6761f9cc58949
---
# `ops/pipeline/entrypoints/MediaPipeline.ps1`

**Purpose:** Entry script for the remux/encode/publish media pipeline.

**Public symbols:** `Write-MediaPipelineEarlyWorkerChildFailureResult`
**State/config identifiers:** `MediaPipeline_config.psd1`, `MediaPipeline_config_chatgpt.psd1`
**Invoked stages:** `blocked`, `failed`, `idle`, `retry_pending_push`, `shutdown`, `startup`, `subtitle-helper-selfcheck`, `write`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvextract`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/entrypoints/MediaPipeline.ps1`._
