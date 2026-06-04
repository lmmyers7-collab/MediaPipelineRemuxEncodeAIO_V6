---
file: engine/decide/encode_policy.ps1
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-06-03
last_reviewed: 2026-05-29
sha256: dd670b64b95cbe471285604e9876e68778e2dffee6c6a8af9abf75e8d5c98ec7
---
# `engine/decide/encode_policy.ps1`

**Purpose:** F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on

**Functions:** `Acquire-CpuEncodeMutex`, `Get-EncodeArgumentValue`, `Get-EncodeEncoderKind`, `Get-EncodeSelectedGpuDevice`, `Get-MediaEncodeBoundedQuality`, `Get-MediaEncodeLadderNames`, `Get-MediaEncodeLadderProfile`, `Get-MediaEncodeOutputMuxerName`, `Invalidate-NvencAvailableProbe`, `New-EncodeAttemptPlan`, `New-EncodeFfmpegArgumentList`, `New-EncodeVideoFlags`, `Resolve-MediaEncodeLadderName`, `Test-IsHardwareEncoderFailure`, `Test-NvencAvailable`, `Test-NvencProbeReportsAvailable`, `Test-ShouldRetryEncodeWithCpuFallback`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/decide/encode_policy.ps1`._
