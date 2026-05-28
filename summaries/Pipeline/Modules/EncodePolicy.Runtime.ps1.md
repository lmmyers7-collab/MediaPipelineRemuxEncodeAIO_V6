---
file: Pipeline/Modules/EncodePolicy.Runtime.ps1
pipeline_stage: decide
token_priority: high
owner_domain: EncodePolicy
last_modified: 2026-05-24
last_reviewed: 2026-05-28
sha256: ae07c09dde0c7e375003401eed34dcdf5e98f215949c288cd4da70cc69ce99c4
---
# `Pipeline/Modules/EncodePolicy.Runtime.ps1`

**Purpose:** F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on

**Functions:** `Acquire-CpuEncodeMutex`, `Invalidate-NvencAvailableProbe`, `Test-IsHardwareEncoderFailure`, `Test-NvencAvailable`, `Test-NvencProbeReportsAvailable`, `Test-ShouldRetryEncodeWithCpuFallback`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths Pipeline/Modules/EncodePolicy.Runtime.ps1`._
