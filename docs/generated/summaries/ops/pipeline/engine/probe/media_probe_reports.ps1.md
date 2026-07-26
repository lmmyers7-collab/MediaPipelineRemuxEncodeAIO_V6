---
file: ops/pipeline/engine/probe/media_probe_reports.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-07-16
last_reviewed: 2026-07-11
sha256: 90b1adabf190e695d7f76e2da95467e6c61b6427769353b5889df7013b23bc2f
---
# `ops/pipeline/engine/probe/media_probe_reports.ps1`

**Purpose:** PowerShell implementation for media probe reports; exposes Get-MediaDuration, Get-PrimaryAVEndTime, Test-DurationMatch.

**Public symbols:** `Get-MediaDuration`, `Get-PrimaryAVEndTime`, `Test-DurationMatch`, `Write-OutputSummary`, `Write-PlexCompatibilityReport`
**Invoked stages:** `media-duration`, `output-summary-probe`, `plex-compatibility-probe`, `primary-av-end-time`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe_reports.ps1`._
