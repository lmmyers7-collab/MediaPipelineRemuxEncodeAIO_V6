---
file: ops/pipeline/tests/Unit/Invoke-MediaVerificationSafetyChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 3fb146ff08900477b72aeec8813f3640133ee7940044ed82261eb7595d6ba1e0
---
# `ops/pipeline/tests/Unit/Invoke-MediaVerificationSafetyChecks.ps1`

**Purpose:** PowerShell implementation for invoke media verification safety checks; exposes Assert-Equal, Assert-True, Get-MediaDuration.

**Public symbols:** `Assert-Equal`, `Assert-True`, `Get-MediaDuration`, `Get-SourceHdr10MasteringMetadata`, `global`, `Write-Log`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-MediaVerificationSafetyChecks.ps1`._
