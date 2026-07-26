---
file: ops/pipeline/engine/audio/audio/stream_decisions.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: audio
token_priority: medium
owner_domain: audio
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: c8fdd9da228efcaead59ef316ae2b38f064bf77983714b84941622c670237510
---
# `ops/pipeline/engine/audio/audio/stream_decisions.ps1`

**Purpose:** PowerShell implementation for stream decisions; exposes Build-AudioStreamDecisionPlan, Get-AudioDecisionOutputChannelCount, Get-AudioDecisionPreferredDefaultIndex.

**Public symbols:** `Build-AudioStreamDecisionPlan`, `Get-AudioDecisionOutputChannelCount`, `Get-AudioDecisionPreferredDefaultIndex`, `New-AudioOmitAllDecisionRecord`, `Select-Mp4CompatibilityAudioSourceKey`
**Invoked tools:** `ffmpeg`, `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/audio/audio/stream_decisions.ps1`._
