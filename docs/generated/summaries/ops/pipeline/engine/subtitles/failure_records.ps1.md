---
file: ops/pipeline/engine/subtitles/failure_records.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: ebe0ba0e70dfb0d77cdb495fe0fc1fec5f39604d16247786c19fae6d2cb50aae
---
# `ops/pipeline/engine/subtitles/failure_records.ps1`

**Purpose:** PowerShell implementation for failure records; exposes ConvertTo-SubtitleFailureEvidence, Get-SubtitleFailureProperty, Get-SubtitleFailureStreamIndex.

**Public symbols:** `ConvertTo-SubtitleFailureEvidence`, `Get-SubtitleFailureProperty`, `Get-SubtitleFailureStreamIndex`, `Get-SubtitleFailureStreamText`, `Get-SubtitleFailureText`, `Register-SubtitleExtractionFailure`, `Register-Tx3gSubtitleFailure`
**Invoked tools:** `ffmpeg`, `pgstosrt`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/failure_records.ps1`._
