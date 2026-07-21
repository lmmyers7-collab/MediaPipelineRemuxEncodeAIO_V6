---
file: ops/pipeline/engine/subtitles/tx3g.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: subtitles
token_priority: high
owner_domain: subtitles
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: f55b2737e0504704c079ee71e31fbbb261bb2d2d7afac815dff9e23abde5265c
---
# `ops/pipeline/engine/subtitles/tx3g.ps1`

**Purpose:** PowerShell implementation for tx3g; exposes Convert-Tx3gToSrt, ConvertTo-Tx3gEmbeddedSrtTrackRecords, Export-Tx3gSrtSidecarsFromSource.

**Public symbols:** `Convert-Tx3gToSrt`, `ConvertTo-Tx3gEmbeddedSrtTrackRecords`, `Export-Tx3gSrtSidecarsFromSource`, `Get-Tx3gSidecarObjectValue`, `Get-Tx3gSidecarTextValue`, `Get-Tx3gSrtSidecarConversionKind`, `Get-Tx3gSrtSidecarSourceSubtitleKind`, `New-Tx3gFailureRecord`, `New-Tx3gSrtRecord`, `New-Tx3gSrtSidecarPublishPlan`, `Publish-Tx3gSrtSidecars`, `Resolve-Tx3gSrtDestination`, `Test-CanPreserveTx3gInFfmpegOutput`, `Test-IsTx3gSubtitleStream`, `Write-SubtitleTrackProgress`
**Invoked stages:** `convert`, `extract`, `sidecar_write`, `validate`
**Invoked tools:** `ffmpeg`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/subtitles/tx3g.ps1`._
