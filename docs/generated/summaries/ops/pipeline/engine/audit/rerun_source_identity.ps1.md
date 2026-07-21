---
file: ops/pipeline/engine/audit/rerun_source_identity.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: observability
token_priority: medium
owner_domain: audit
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 835787081f7c9433e7aaa3c8b41873e383ad51e5407a26cbc86f3d89bebb5ec4
---
# `ops/pipeline/engine/audit/rerun_source_identity.ps1`

**Purpose:** PowerShell implementation for rerun source identity; exposes Get-RerunCompletedTaskText, Get-RerunContentSha256, Get-RerunSourceIdentityV2.

**Public symbols:** `Get-RerunCompletedTaskText`, `Get-RerunContentSha256`, `Get-RerunSourceIdentityV2`, `Get-RerunSourceSampleHash`, `Invoke-RerunNativeCommand`, `Stop-RerunNativeProcessTree`, `Write-RerunIdentityLog`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/audit/rerun_source_identity.ps1`._
