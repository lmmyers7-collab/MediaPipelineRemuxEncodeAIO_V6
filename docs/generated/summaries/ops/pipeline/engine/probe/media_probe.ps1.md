---
file: ops/pipeline/engine/probe/media_probe.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: f4aebec3dbc6d37baa3839556108ca28f31b9b2d3e3bd5c2f851bd4d23cde3ed
---
# `ops/pipeline/engine/probe/media_probe.ps1`

**Purpose:** Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL

**Functions:** `ConvertTo-DynamicHdrInt`, `ConvertTo-VideoStreamEvidenceBool`, `ConvertTo-VideoStreamEvidenceInt`, `ConvertTo-VideoStreamEvidenceRows`, `ConvertTo-VideoStreamFailureEvidence`, `Get-DefaultAudioLang`, `Get-DolbyVisionState`, `Get-DynamicHdrObjectValue`, `Get-DynamicHdrProbeFailureReason`, `Get-HDRState`, `Get-MediaDuration`, `Get-PrimaryAVEndTime`, `Get-SourceHdr10MasteringMetadata`, `Get-SourceMediaRouteProfile`, `Get-SourceTitleTag`, `Get-SourceVideoCodec`, `Get-SourceVideoStreamInventory`, `Get-VideoStreamEvidenceProperty`, `New-DynamicHdrEvidence`, `New-FileIntegrityResult`, `Test-DurationMatch`, `Test-DynamicHdrFlag`, `Test-FileIntegrity`, `Test-FileIntegrityDetailed`, `Test-FileStable`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe.ps1`._
