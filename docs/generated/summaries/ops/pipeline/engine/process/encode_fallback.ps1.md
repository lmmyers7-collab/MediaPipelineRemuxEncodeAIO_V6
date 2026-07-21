---
file: ops/pipeline/engine/process/encode_fallback.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-17
last_reviewed: 2026-06-24
sha256: b91fc8dc37d8f4dee585bb9e8423906122f2bc20af0c1f195cab3a0ccff77e51
---
# `ops/pipeline/engine/process/encode_fallback.ps1`

**Purpose:** PowerShell implementation for encode fallback; exposes Add-RemuxFallbackRejectionToFailureReason, Get-CurrentEncodeRouteIntentReasonCode, Get-LastRemuxFallbackRejection.

**Public symbols:** `Add-RemuxFallbackRejectionToFailureReason`, `Get-CurrentEncodeRouteIntentReasonCode`, `Get-LastRemuxFallbackRejection`, `Get-LastRemuxFallbackRejectionReasonText`, `Get-MediaPipelineEncodeFallbackBoundaryVersion`, `Get-RemuxFallbackRejectionValue`, `Invoke-MediaPipelineEncodeAttemptLadder`, `Invoke-MediaPipelineEncodeDynamicHdrPolicy`, `New-RemuxFallbackFailureProperties`, `Set-MediaPipelineEncodeRemuxFallbackRouteEvidence`, `Set-MediaPipelineEncodeRuntimeRouteEvidence`
**Invoked stages:** `dynamic-hdr-extraction`, `dynamic-hdr-policy`, `dynamic-hdr-remux-fallback`, `encode`, `encode-attempts`, `encode-command`, `encode-cpu-mutex`, `encode-policy`, `encode-size-policy`, `encode_cpu`, `encode_prepare`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/encode_fallback.ps1`._
