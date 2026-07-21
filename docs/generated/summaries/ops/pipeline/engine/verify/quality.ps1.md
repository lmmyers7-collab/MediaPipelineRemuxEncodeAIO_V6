---
file: ops/pipeline/engine/verify/quality.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: verify
last_modified: 2026-07-16
last_reviewed: 2026-06-11
sha256: af6b8d0a7a9a57d37793bb0da9831ce7400d942b25436c33fe14ca793adf95ab
---
# `ops/pipeline/engine/verify/quality.ps1`

**Purpose:** PowerShell implementation for quality; exposes ConvertFrom-MediaQualityToolOutput, ConvertTo-MediaQualityDouble, ConvertTo-MediaQualityFilterPath.

**Public symbols:** `ConvertFrom-MediaQualityToolOutput`, `ConvertTo-MediaQualityDouble`, `ConvertTo-MediaQualityFilterPath`, `ConvertTo-MediaQualityInvariantString`, `Get-MediaQualityObjectValue`, `Get-MediaQualitySampleWindows`, `Get-MediaQualityStreamInfo`, `Invoke-MediaQualityVerification`, `New-MediaQualityFilterGraph`, `New-MediaQualityVerificationRecord`, `Resolve-MediaQualityLogDirectory`, `Resolve-MediaQualityOutcome`, `Set-MediaQualityObjectValue`
**Invoked stages:** `encode-quality-verify`, `quality-probe`
**Invoked tools:** `ffmpeg`, `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/verify/quality.ps1`._
