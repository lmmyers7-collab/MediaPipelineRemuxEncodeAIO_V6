---
file: ops/pipeline/engine/probe/media_probe_hdr.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 967bada68f8f0648509d921b4cfbb257b26d0a432fb374f57bcbc49e5f78ae2d
---
# `ops/pipeline/engine/probe/media_probe_hdr.ps1`

**Purpose:** Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL

**Functions:** `ConvertTo-DynamicHdrInt`, `Get-DefaultAudioLang`, `Get-DolbyVisionState`, `Get-DynamicHdrObjectValue`, `Get-DynamicHdrProbeFailureReason`, `Get-HDRState`, `Get-SourceHdr10MasteringMetadata`, `Get-SourceMediaRouteProfile`, `New-DynamicHdrEvidence`, `Test-DynamicHdrFlag`, `Test-Hdr10PlusPresence`, `Test-IsHDR`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe_hdr.ps1`._
