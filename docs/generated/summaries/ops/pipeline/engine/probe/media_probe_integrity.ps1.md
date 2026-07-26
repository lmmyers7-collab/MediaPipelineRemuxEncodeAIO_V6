---
file: ops/pipeline/engine/probe/media_probe_integrity.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: probe
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 44a6ed964627296b5c20a97729bb5705607567ce92ba8b0e00cab2e4276fb54f
---
# `ops/pipeline/engine/probe/media_probe_integrity.ps1`

**Purpose:** PowerShell implementation for media probe integrity; exposes New-FileIntegrityResult, Test-FileIntegrity, Test-FileIntegrityDetailed.

**Public symbols:** `New-FileIntegrityResult`, `Test-FileIntegrity`, `Test-FileIntegrityDetailed`, `Test-FileStable`
**Invoked stages:** `integrity-ffprobe`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/probe/media_probe_integrity.ps1`._
