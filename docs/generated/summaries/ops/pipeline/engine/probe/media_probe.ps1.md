---
file: ops/pipeline/engine/probe/media_probe.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: d023fbf2bd85b12e36b0d581a13952a11928ac569f66065f41d22b3478d049c7
---
# `ops/pipeline/engine/probe/media_probe.ps1`

**Purpose:** Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL

**Functions:** `ConvertTo-DynamicHdrInt`, `ConvertTo-VideoStreamEvidenceBool`, `ConvertTo-VideoStreamEvidenceInt`, `ConvertTo-VideoStreamEvidenceRows`, `ConvertTo-VideoStreamFailureEvidence`, `Get-DefaultAudioLang`, `Get-DolbyVisionState`, `Get-DynamicHdrObjectValue`, `Get-DynamicHdrProbeFailureReason`, `Get-HDRState`, `Get-MediaDuration`, `Get-PrimaryAVEndTime`, `Get-SourceHdr10MasteringMetadata`, `Get-SourceMediaRouteProfile`, `Get-SourceTitleTag`, `Get-SourceVideoCodec`, `Get-SourceVideoStreamInventory`, `Get-VideoStreamEvidenceProperty`, `New-DynamicHdrEvidence`, `New-FileIntegrityResult`, `Test-DurationMatch`, `Test-DynamicHdrFlag`, `Test-FileIntegrity`, `Test-FileIntegrityDetailed`, `Test-FileStable`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe.ps1`._
