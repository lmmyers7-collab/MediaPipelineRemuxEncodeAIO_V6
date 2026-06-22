---
file: ops/pipeline/engine/probe/media_probe.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-06-22
last_reviewed: 2026-06-04
sha256: 0f3c57c8e54bcaa0dbb587e87508bda3a3f6a321adb86d240d88c5cd77910823
---
# `ops/pipeline/engine/probe/media_probe.ps1`

**Purpose:** Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL

**Functions:** `ConvertTo-DynamicHdrInt`, `Get-DefaultAudioLang`, `Get-DolbyVisionState`, `Get-DynamicHdrObjectValue`, `Get-DynamicHdrProbeFailureReason`, `Get-HDRState`, `Get-MediaDuration`, `Get-PrimaryAVEndTime`, `Get-SourceHdr10MasteringMetadata`, `Get-SourceMediaRouteProfile`, `Get-SourceTitleTag`, `Get-SourceVideoCodec`, `Get-SourceVideoStreamInventory`, `New-DynamicHdrEvidence`, `New-FileIntegrityResult`, `Test-DurationMatch`, `Test-DynamicHdrFlag`, `Test-FileIntegrity`, `Test-FileIntegrityDetailed`, `Test-FileStable`, `Test-Hdr10PlusPresence`, `Test-IsHDR`, `Test-OutputVideoStreamPreservation`, `Test-SourceVideoStreamAttachedPicture`, `Test-SourceVideoStreamPublishPolicy`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe.ps1`._
