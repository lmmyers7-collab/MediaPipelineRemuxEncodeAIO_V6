---
file: ops/pipeline/engine/process/remux_preflight.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-20
last_reviewed: 2026-06-24
sha256: 234d904c2eaf6126c688bc7cb4cc4304ab61d8f98c178d091d62bf32a9e999e6
---
# `ops/pipeline/engine/process/remux_preflight.ps1`

**Purpose:** PowerShell implementation for remux preflight; exposes Invoke-MediaPipelineRemuxPreflight.

**Public symbols:** `Invoke-MediaPipelineRemuxPreflight`
**Invoked stages:** `copy_to_scratch`, `disk-space`, `dynamic-hdr-remux-fallback-rejection`, `existing-output`, `existing-output-sidecar`, `remux-codec-fallback-encode`, `remux-dynamic-hdr-probe`, `remux-fallback-rejection`, `remux-preflight`, `remux-space`, `remux_prepare`, `video-stream-policy`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/remux_preflight.ps1`._
