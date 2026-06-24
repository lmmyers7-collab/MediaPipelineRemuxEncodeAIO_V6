---
file: ops/pipeline/engine/decide/encode_policy.ps1
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-06-23
last_reviewed: 2026-06-04
sha256: db687ef1f6000b7b122480687bcb7440a7de9144fd8cae0f33e22745d0fbe366
---
# `ops/pipeline/engine/decide/encode_policy.ps1`

**Purpose:** F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on

**Functions:** `Acquire-CpuEncodeMutex`, `Convert-DescriptorProbeToNvencProbeResult`, `Get-EncodeArgumentValue`, `Get-EncodeEncoderKind`, `Get-EncodeSelectedGpuDevice`, `Get-MediaEncodeBoundedQuality`, `Get-MediaEncodeLadderNames`, `Get-MediaEncodeLadderProfile`, `Get-MediaEncodeOutputMuxerName`, `Invalidate-NvencAvailableProbe`, `New-EncodeAttemptDescriptorSelectionEvidence`, `New-EncodeAttemptPlan`, `New-EncodeFfmpegArgumentList`, `New-EncodeVideoFlags`, `New-EncodeWasteGuardSampleArgumentList`, `Resolve-MediaEncodeLadderName`, `Resolve-MediaEncoderActivationReadiness`, `Resolve-NvencProbeDescriptor`, `Test-IsHardwareEncoderFailure`, `Test-NvencAvailable`, `Test-NvencEncoderListMatch`, `Test-NvencProbeReportsAvailable`, `Test-ShouldRetryEncodeWithCpuFallback`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encode_policy.ps1`._
