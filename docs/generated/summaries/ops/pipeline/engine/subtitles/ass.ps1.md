---
file: ops/pipeline/engine/subtitles/ass.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 70cef7d27041c079b5a8f9a3b4611cf9ec0ee5da5847f5707653c186458b95cb
---
# `ops/pipeline/engine/subtitles/ass.ps1`

**Purpose:** PowerShell implementation for ass; exposes Convert-AssToSrt, New-AssFailureRecord, Write-SubtitleTrackProgress.

**Public symbols:** `Convert-AssToSrt`, `New-AssFailureRecord`, `Write-SubtitleTrackProgress`
**Invoked stages:** `convert`, `extract`, `subtitle-ass-convert`, `validate`
**Invoked tools:** `ffmpeg`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/ass.ps1`._
