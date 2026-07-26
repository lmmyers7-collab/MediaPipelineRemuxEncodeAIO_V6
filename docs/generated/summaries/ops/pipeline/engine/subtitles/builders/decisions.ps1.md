---
file: ops/pipeline/engine/subtitles/builders/decisions.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 300f17e525e084beace0fb958106696b8c151729640e736f2d3fedc4f4fc0a89
---
# `ops/pipeline/engine/subtitles/builders/decisions.ps1`

**Purpose:** PowerShell implementation for decisions; exposes Add-SubtitleBuilderFallbackDefaultCandidate, Get-SubtitleBuilderFfmpegBaseDisposition, Get-SubtitleBuilderFfmpegConvertedDisposition.

**Public symbols:** `Add-SubtitleBuilderFallbackDefaultCandidate`, `Get-SubtitleBuilderFfmpegBaseDisposition`, `Get-SubtitleBuilderFfmpegConvertedDisposition`, `Get-SubtitleBuilderTrackDecisionRecords`, `New-SubtitleBuilderDefaultState`, `New-SubtitleBuilderTrackDecisionRecord`, `Set-SubtitleBuilderBoolDefaultDisposition`, `Set-SubtitleBuilderFallbackDefault`, `Set-SubtitleBuilderFfmpegDefaultDisposition`, `Test-ConfiguredOutputContainerIsMp4`, `Test-SubtitleBuilderFallbackDefaultCandidate`, `Test-SubtitleBuilderPreferredDefaultCandidate`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/builders/decisions.ps1`._
