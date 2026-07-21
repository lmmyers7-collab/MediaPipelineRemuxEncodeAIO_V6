---
file: ops/pipeline/engine/audit/probe.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: 4b9c4561fe3baa7953243039a7f80a968b77c79884da22c2f2ebf9f9b30679c7
---
# `ops/pipeline/engine/audit/probe.ps1`

**Purpose:** PowerShell implementation for probe; exposes Clear-ProbeCache, Get-ProbeCacheEntry, Get-ProbeCacheIdentity.

**Public symbols:** `Clear-ProbeCache`, `Get-ProbeCacheEntry`, `Get-ProbeCacheIdentity`, `Get-ProbeCachePath`, `Get-ProbeCacheSampleHash`, `Get-Sha256Hex`, `Invoke-FfprobeJson`, `Invoke-FfprobeJsonCached`, `Save-ProbeCacheEntry`, `Test-ProbeCacheCleanupBoundary`, `Write-ProbeCacheBoundaryLog`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/audit/probe.ps1`._
