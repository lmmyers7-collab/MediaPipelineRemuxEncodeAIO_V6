---
file: ops/pipeline/engine/probe/media_probe.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-06-22
last_reviewed: 2026-06-04
sha256: 25a643aeef4c8cf53a9bb3c78a4532824c9a4c29a9f22477d92f0290aa74e0a0
---
# `ops/pipeline/engine/probe/media_probe.ps1`

**Purpose:** Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL

**Functions:** `ConvertTo-DynamicHdrInt`, `Get-DefaultAudioLang`, `Get-DolbyVisionState`, `Get-DynamicHdrObjectValue`, `Get-DynamicHdrProbeFailureReason`, `Get-HDRState`, `Get-MediaDuration`, `Get-PrimaryAVEndTime`, `Get-SourceHdr10MasteringMetadata`, `Get-SourceMediaRouteProfile`, `Get-SourceTitleTag`, `Get-SourceVideoCodec`, `Get-SourceVideoStreamInventory`, `New-DynamicHdrEvidence`, `New-FileIntegrityResult`, `Test-DurationMatch`, `Test-DynamicHdrFlag`, `Test-FileIntegrity`, `Test-FileIntegrityDetailed`, `Test-FileStable`, `Test-Hdr10PlusPresence`, `Test-IsHDR`, `Test-SourceVideoStreamAttachedPicture`, `Test-SourceVideoStreamPublishPolicy`, `Write-OutputSummary`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe.ps1`._
