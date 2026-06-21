---
file: ops/pipeline/engine/decide/encode_policy.ps1
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-06-21
last_reviewed: 2026-06-04
sha256: 909fb6715ab976a772120e40530f874a49897f4a9c3823e626c6b70efbb84f05
---
# `ops/pipeline/engine/decide/encode_policy.ps1`

**Purpose:** F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on

**Functions:** `Acquire-CpuEncodeMutex`, `Get-EncodeArgumentValue`, `Get-EncodeEncoderKind`, `Get-EncodeSelectedGpuDevice`, `Get-MediaEncodeBoundedQuality`, `Get-MediaEncodeLadderNames`, `Get-MediaEncodeLadderProfile`, `Get-MediaEncodeOutputMuxerName`, `Invalidate-NvencAvailableProbe`, `New-EncodeAttemptDescriptorSelectionEvidence`, `New-EncodeAttemptPlan`, `New-EncodeFfmpegArgumentList`, `New-EncodeVideoFlags`, `New-EncodeWasteGuardSampleArgumentList`, `Resolve-MediaEncodeLadderName`, `Resolve-MediaEncoderActivationReadiness`, `Test-IsHardwareEncoderFailure`, `Test-NvencAvailable`, `Test-NvencEncoderListMatch`, `Test-NvencProbeReportsAvailable`, `Test-ShouldRetryEncodeWithCpuFallback`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encode_policy.ps1`._
