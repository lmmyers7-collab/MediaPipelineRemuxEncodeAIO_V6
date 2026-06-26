---
file: ops/pipeline/engine/decide/encode_policy.ps1
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: a3a8bf360d65177019ec3c0554db436ffb7dd9c1babd6c94723d91865299c8f8
---
# `ops/pipeline/engine/decide/encode_policy.ps1`

**Purpose:** F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on

**Functions:** `Acquire-CpuEncodeMutex`, `Convert-DescriptorProbeToNvencProbeResult`, `Get-EncodeArgumentValue`, `Get-EncodeEncoderKind`, `Get-EncodeSelectedGpuDevice`, `Get-MediaEncodeBoundedQuality`, `Get-MediaEncodeLadderNames`, `Get-MediaEncodeLadderProfile`, `Get-MediaEncodeOutputMuxerName`, `Invalidate-NvencAvailableProbe`, `New-EncodeAttemptDescriptorSelectionEvidence`, `New-EncodeAttemptPlan`, `New-EncodeFfmpegArgumentList`, `New-EncodeVideoFlags`, `New-EncodeWasteGuardSampleArgumentList`, `Resolve-MediaEncodeLadderName`, `Resolve-MediaEncoderActivationReadiness`, `Resolve-NvencProbeDescriptor`, `Test-IsHardwareEncoderFailure`, `Test-NvencAvailable`, `Test-NvencEncoderListMatch`, `Test-NvencProbeReportsAvailable`, `Test-ShouldRetryEncodeWithCpuFallback`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encode_policy.ps1`._
