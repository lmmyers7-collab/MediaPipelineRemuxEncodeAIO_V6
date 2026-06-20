---
file: ops/pipeline/engine/decide/encode_policy.ps1
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-06-19
last_reviewed: 2026-06-04
sha256: 7d64f7d461ba895cfbf0c78c13cc47b29c9c71405daf38974104b0e6d8ec80cc
---
# `ops/pipeline/engine/decide/encode_policy.ps1`

**Purpose:** F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on

**Functions:** `Acquire-CpuEncodeMutex`, `Get-EncodeArgumentValue`, `Get-EncodeEncoderKind`, `Get-EncodeSelectedGpuDevice`, `Get-MediaEncodeBoundedQuality`, `Get-MediaEncodeLadderNames`, `Get-MediaEncodeLadderProfile`, `Get-MediaEncodeOutputMuxerName`, `Invalidate-NvencAvailableProbe`, `New-EncodeAttemptPlan`, `New-EncodeFfmpegArgumentList`, `New-EncodeVideoFlags`, `New-EncodeWasteGuardSampleArgumentList`, `Resolve-MediaEncodeLadderName`, `Test-IsHardwareEncoderFailure`, `Test-NvencAvailable`, `Test-NvencProbeReportsAvailable`, `Test-ShouldRetryEncodeWithCpuFallback`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encode_policy.ps1`._
