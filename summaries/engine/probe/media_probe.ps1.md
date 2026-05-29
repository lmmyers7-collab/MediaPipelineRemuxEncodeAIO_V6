---
file: engine/probe/media_probe.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: 35d43d4fe80a5f86b8fa77c0c66a36197efaebf94a234c014d722d7023fcf132
---
# `engine/probe/media_probe.ps1`

**Purpose:** Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL

**Functions:** `Get-DefaultAudioLang`, `Get-HDRState`, `Get-MediaDuration`, `Get-PrimaryAVEndTime`, `Get-SourceHdr10MasteringMetadata`, `Get-SourceMediaRouteProfile`, `Get-SourceTitleTag`, `Get-SourceVideoCodec`, `New-FileIntegrityResult`, `Test-DurationMatch`, `Test-FileIntegrity`, `Test-FileIntegrityDetailed`, `Test-FileStable`, `Test-IsHDR`, `Write-OutputSummary`, `Write-PlexCompatibilityReport`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/probe/media_probe.ps1`._
