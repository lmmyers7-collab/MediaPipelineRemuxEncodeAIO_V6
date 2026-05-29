---
file: engine/decide/encode_policy.ps1
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: 7011f9e6da5117f1e5ea7a8b7dbbce681b9f45911c9729bd5c6182594a9f786e
---
# `engine/decide/encode_policy.ps1`

**Purpose:** F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on

**Functions:** `Acquire-CpuEncodeMutex`, `Get-EncodeArgumentValue`, `Get-EncodeEncoderKind`, `Get-EncodeSelectedGpuDevice`, `Get-MediaEncodeBoundedQuality`, `Get-MediaEncodeLadderNames`, `Get-MediaEncodeLadderProfile`, `Invalidate-NvencAvailableProbe`, `New-EncodeAttemptPlan`, `New-EncodeFfmpegArgumentList`, `New-EncodeVideoFlags`, `Resolve-MediaEncodeLadderName`, `Test-IsHardwareEncoderFailure`, `Test-NvencAvailable`, `Test-NvencProbeReportsAvailable`, `Test-ShouldRetryEncodeWithCpuFallback`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/decide/encode_policy.ps1`._
