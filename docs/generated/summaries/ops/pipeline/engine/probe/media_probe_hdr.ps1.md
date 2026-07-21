---
file: ops/pipeline/engine/probe/media_probe_hdr.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-07-16
last_reviewed: 2026-07-11
sha256: 2b49ff9a91b9c59a0c4e8b0293f4f0522db4d6cc1405248a8607ad87881bb21d
---
# `ops/pipeline/engine/probe/media_probe_hdr.ps1`

**Purpose:** Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL from the first video frame so libx265 can emit a complete HDR10 SEI.

**Public symbols:** `ConvertTo-DynamicHdrInt`, `Get-DefaultAudioLang`, `Get-DolbyVisionState`, `Get-DynamicHdrObjectValue`, `Get-DynamicHdrProbeFailureReason`, `Get-HDRState`, `Get-SourceHdr10MasteringMetadata`, `Get-SourceMediaRouteProfile`, `New-DynamicHdrEvidence`, `Test-DynamicHdrFlag`, `Test-Hdr10PlusPresence`, `Test-IsHDR`
**Invoked stages:** `default-audio-language`, `Dolby`, `dovi-detection`, `hdr-detection`, `HDR10`, `hdr10-mastering-probe`, `hdr10plus-detection`, `source-route-profile`, `source-video-packet-probe`
**Invoked tools:** `ffmpeg`, `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe_hdr.ps1`._
