---
file: ops/pipeline/engine/probe/media_probe.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 5626f4df1ff781f09a0fec46ee31eaf1aa21cca3cdb201b79765623b395ab081
---
# `ops/pipeline/engine/probe/media_probe.ps1`

**Purpose:** Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL

**Functions:** `Get-DefaultAudioLang`, `Get-HDRState`, `Get-MediaDuration`, `Get-PrimaryAVEndTime`, `Get-SourceHdr10MasteringMetadata`, `Get-SourceMediaRouteProfile`, `Get-SourceTitleTag`, `Get-SourceVideoCodec`, `New-FileIntegrityResult`, `Test-DurationMatch`, `Test-FileIntegrity`, `Test-FileIntegrityDetailed`, `Test-FileStable`, `Test-IsHDR`, `Write-OutputSummary`, `Write-PlexCompatibilityReport`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe.ps1`._
