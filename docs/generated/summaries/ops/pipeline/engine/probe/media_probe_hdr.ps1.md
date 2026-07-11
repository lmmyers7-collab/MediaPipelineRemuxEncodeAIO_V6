---
file: ops/pipeline/engine/probe/media_probe_hdr.ps1
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 0adacc33eceedf8bc398ef4daeab55a9ee1e58132528d3f51fdba4dd7fcd8b3b
---
# `ops/pipeline/engine/probe/media_probe_hdr.ps1`

**Purpose:** Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL

**Functions:** `ConvertTo-DynamicHdrInt`, `Get-DefaultAudioLang`, `Get-DolbyVisionState`, `Get-DynamicHdrObjectValue`, `Get-DynamicHdrProbeFailureReason`, `Get-HDRState`, `Get-SourceHdr10MasteringMetadata`, `Get-SourceMediaRouteProfile`, `New-DynamicHdrEvidence`, `Test-DynamicHdrFlag`, `Test-Hdr10PlusPresence`, `Test-IsHDR`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe_hdr.ps1`._
